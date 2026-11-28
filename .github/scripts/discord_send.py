r"""
Discord の送る係（GitHub Actions 側。2026/11/28 ユーザー指定「全部PC以外から出す。日中PCが切れる可能性が高い」）

Pages リポジトリの .github/scripts/discord_send.py に置き、live_loop.sh が1分おきに呼ぶ（日本時間 7〜23時）。
元は AI作業場\自動化スクリプト\live\discord_send.py。直したら publish_dashboard.publish(…, dest='.github/scripts/discord_send.py', lock=False) で置き直す。

1) 送る予定の一覧（PC の discord_queue.py が Pages の dq/q.txt に暗号で置く）を読み、時刻が来た（at ≦ 今 ＜ until）ものを送る。
   画像は dq/i_*.txt（暗号）。thread_id があればそのスレッドへ、無ければふつうに送り、フォーラムで断られたら thread_name で新しいスレッド。
2) PC が無くても見つけられるものを、10分おきに見て送る（初めて見た種類は、今あるものを「送った」にする）
   - note の総まとめ（マガジン「Daily Report」の「M/Dのボートレース総まとめ」・今日の分）→ notice
   - note のコラム（マガジン NOTE_MAGAZINE の新しい記事）→ column
   - Discovery のコラム（公開中の column/ の記事）→ column
送った記録は live/discord_sent.json（live-data で次の回に引き継ぐ。id と時刻だけ）。

Secrets「DISCORD_CONF」＝{"key": 暗号の鍵, "hooks": {送り先: ウェブフックURL}}（PC で python discord_queue.py --secret）。無ければ何もしない。
ウェブフックURL・本文はログに出さない。
    python discord_send.py --out .             ふだん（live_loop.sh から）
    python discord_send.py --out . --dry       送らずに、送る予定を表示
"""
import base64
import gzip
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
SITE = "https://discovery-kyotei.com/"
NOTE_MAGAZINE = "https://note.com/crapemyrtlllle/m/m94b1c236424e"   # make_top_page.NOTE_MAGAZINE（コラム）
NOTE_DAILY_MAG = "https://note.com/crapemyrtlllle/m/m8d42e714b70d"  # make_top_page.NOTE_DAILY_MAG（Daily Report）
DETECT_EVERY = 600
MAX_SEND = 6
UA = "DiscoveryNotice (discovery-kyotei.com, 1.0)"


def decrypt(text, key):
    """make_ex21.decrypt と同じ（base64(nonce16 + tag16 + 暗号文)）"""
    raw = base64.b64decode(text)
    nonce, tag, ct = raw[:16], raw[16:32], raw[32:]
    if not hmac.compare_digest(tag, hmac.new(key, b"tag" + nonce + ct, hashlib.sha256).digest()[:16]):
        raise ValueError("鍵が違うか、壊れています")
    out = bytearray(len(ct))
    for blk in range((len(ct) + 31) // 32):
        ks = hmac.new(key, nonce + blk.to_bytes(4, "big"), hashlib.sha256).digest()
        for j, c in enumerate(ct[blk * 32: blk * 32 + 32]):
            out[blk * 32 + j] = c ^ ks[j]
    return bytes(out)


def repo_file(path):
    """Pages リポジトリ（main）のファイルを API で読む（キャッシュを通さない）"""
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_TOKEN")
    if not repo:
        return None
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/contents/{path}",
                                 headers={"Accept": "application/vnd.github.raw", "User-Agent": UA,
                                          **({"Authorization": f"Bearer {tok}"} if tok else {})})
    try:
        return urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:  # noqa: BLE001
        print(f"  {path} を読めませんでした（{type(e).__name__}）")
        return None


def post(url, content, files=(), thread_id=None, thread_name=None):
    """1件送る。成功で True。ウェブフックURL は出さない"""
    import requests
    if thread_id:
        url += ("&" if "?" in url else "?") + f"thread_id={thread_id}"
    msg = {"content": content, "allowed_mentions": {"parse": []}}
    if thread_name and not thread_id:
        msg["thread_name"] = thread_name[:100]
    for _ in range(2):
        if files:
            r = requests.post(url, data={"payload_json": json.dumps(msg)}, timeout=30, headers={"User-Agent": UA},
                              files={f"files[{i}]": (n, b, "image/png") for i, (n, b) in enumerate(files)})
        else:
            r = requests.post(url, json=msg, timeout=30, headers={"User-Agent": UA})
        if r.status_code == 429:
            time.sleep(min(float(r.json().get("retry_after", 2)), 30) + 0.5)
            continue
        if not r.ok:
            print(f"  送れませんでした（HTTP {r.status_code}）")
        return r.ok
    return False


def send_item(hooks, key, x):
    url = hooks.get(x["ch"])
    if not url:
        print(f"  送り先 {x['ch']} の URL が Secrets にありません")
        return False
    files = []
    for i, nm in enumerate(x.get("imgs") or []):
        b = repo_file(f"dq/{nm}")
        if b is None:
            return False
        files.append((f"slit_{i + 1}.png", decrypt(b.decode("ascii"), key)))
    if x.get("thread_id"):
        return post(url, x["text"], files, thread_id=x["thread_id"])
    return post(url, x["text"], files) or (bool(x.get("thread_name")) and post(url, x["text"], files, thread_name=x["thread_name"]))


def rss(url):
    import xml.etree.ElementTree as ET
    req = urllib.request.Request(url.rstrip("/") + "/rss", headers={"User-Agent": "Mozilla/5.0"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=15).read())
    return [((it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()) for it in root.iter("item")]


def detect(now):
    """[(種類, しるし, 送り先, 本文)]。読めなかった種類は入れない"""
    out = {}
    try:
        head = f"{now.month}/{now.day}のボートレース総まとめ"
        out["daily"] = [(f"daily:{now:%Y%m%d}", "notice", f"📝 note を更新しました：{t}\n{ln}")
                        for t, ln in rss(NOTE_DAILY_MAG) if t.startswith(head) and ln][:1]
    except Exception as e:  # noqa: BLE001
        print(f"  総まとめのマガジンを読めませんでした（{type(e).__name__}）")
    try:
        out["notecol"] = [(f"note:{ln}", "column", f"📝 note にコラムを出しました：{t}\n{ln}") for t, ln in rss(NOTE_MAGAZINE)[:6] if t and ln]
    except Exception as e:  # noqa: BLE001
        print(f"  note のコラムを読めませんでした（{type(e).__name__}）")
    try:
        import html as _html
        page = SITE + "column/"
        h = urllib.request.urlopen(urllib.request.Request(page, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read().decode("utf-8")
        out["col"] = [(f"col:{aid}", "column", f"📖 Discovery のコラムを更新しました：{_html.unescape(re.sub(r'<[^>]+>', '', t)).strip()}\n{page}#{aid}")
                      for aid, t in re.findall(r'<article class="cl-art" id="([^"]+)"[^>]*>.*?<h1>(.*?)</h1>', h, re.S)]
    except Exception as e:  # noqa: BLE001
        print(f"  Discovery のコラムを読めませんでした（{type(e).__name__}）")
    return out


def main():
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path(".")
    dry = "--dry" in sys.argv
    try:
        conf = json.loads(os.environ.get("DISCORD_CONF") or "{}")
    except ValueError:
        conf = {}
    if not conf.get("key") or not conf.get("hooks"):
        print("Discord：Secrets「DISCORD_CONF」が無いので何もしません")
        return
    key, hooks = bytes.fromhex(conf["key"]), conf["hooks"]
    sf = out / "live" / "discord_sent.json"
    try:
        st = json.loads(sf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    sent, seen = st.setdefault("sent", {}), set(st.setdefault("seen", []))
    now = datetime.now(JST).replace(tzinfo=None)
    n = 0
    # 1) 送る予定の一覧
    q = repo_file("dq/q.txt")
    items = []
    if q:
        try:
            items = json.loads(gzip.decompress(decrypt(q.decode("ascii"), key)))
        except Exception as e:  # noqa: BLE001
            print(f"  送る予定を読めませんでした（{type(e).__name__}: {e}）")
    t = now.strftime("%Y-%m-%dT%H:%M")
    for x in items:
        if x["id"] in sent or not (x["at"] <= t < x["until"]) or n >= MAX_SEND:
            continue
        if dry:
            print(f"--- 送る予定 [{x['ch']}] {x['id']}（画像 {len(x.get('imgs') or [])}）\n{x['text']}")
            continue
        if send_item(hooks, key, x):
            sent[x["id"]] = t
            n += 1
            print(f"  送りました [{x['ch']}] {x['id']}")
            time.sleep(1)
    # 2) PC が無くても見つけられるもの（10分おき）
    if time.time() - st.get("detect_at", 0) >= DETECT_EVERY or dry:
        for kind, found in detect(now).items():
            init = f"初回:{kind}"
            if init not in seen:
                seen.update([init] + [k for k, _, _ in found])
                print(f"  {kind}：初めてなので、今ある {len(found)} 件を送った扱いにしました")
                continue
            for k, ch, text in found:
                if k in seen or n >= MAX_SEND:
                    continue
                if dry:
                    print(f"--- 見つけたもの [{ch}] {k}\n{text}")
                    continue
                if hooks.get(ch) and post(hooks[ch], text) or (hooks.get(ch) and post(hooks[ch], text, thread_name=text.splitlines()[0])):
                    seen.add(k)
                    n += 1
                    print(f"  送りました [{ch}] {k}")
                    time.sleep(1)
        st["detect_at"] = time.time()
    if dry:
        return
    lim = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    st["sent"] = {k: v for k, v in sent.items() if v >= lim}
    st["seen"] = sorted(seen)[-500:]
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
