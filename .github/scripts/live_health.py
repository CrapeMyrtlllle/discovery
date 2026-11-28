"""
パソコンが切れていても止まったことに気づくための見張り役（GitHub Actions 側。2026/11/24 追加）

パソコンの health_watch.py はパソコンが切れているあいだ動かないので、そのうち2つを Actions でも見る。
速報と同じ live_loop.sh の中で、全体の取得（3分おき）のあとに呼ばれる。読むだけで、ページは書き換えない。

見るもの
  1. 夜間の公開：日本時間 7:00 を過ぎても、公開トップの「更新 YYYY/MM/DD」が今日でなければ知らせる（1日1回）。
     今日の速報（live/results_今日.json）に開催場が無い日は見ない。今日の日付を確かめたら、その日はもう読みに行かない。
  2. 速報：今日の最初の締切の20分後〜最終締切＋15分のあいだ、live/latest.json の updated が30分以上前なら知らせる
     （取得元に断られている・取得が失敗し続けているとき）。止まっているあいだは60分おきに知らせ直し、戻ったら1回。
     ※ Actions そのものが止まったときは、これでは知らせられない（パソコンの health_watch.py が見る）。

送り先: 環境変数 NTFY_TOPIC（live-results.yml が Secrets の NTFY_TOPIC から渡す）。無ければ何もしない。
控え: live/health_state.json（{nightly: 知らせた日 or ok の日, live: {down, notified}}。日付と時刻だけ）。
      live-data に載るので次の回に引き継がれる。パソコンの health_watch.py もこれを読み、同じ件を二重に送らない。

使い方:
    python3 live_health.py --out .          # 点検して、問題があれば通知する
    python3 live_health.py --out . --dry    # 送らずに表示だけ
"""
import argparse
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
SITE = "https://discovery-kyotei.com/"   # 独自ドメインに切り替え(2026/11/26)
NIGHTLY_FROM = 7                    # この時（日本時間）を過ぎてもトップが今日でなければ知らせる
LIVE_START_AFTER_FIRST_MIN = 20     # health_watch.py と同じ
LIVE_END_AFTER_LAST_MIN = 15
LIVE_STALE_MIN = 30
LIVE_RENOTIFY_MIN = 60


def load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def send(title, message, dry, priority=4, tags=("warning",)):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if dry:
        print(f"[送らない] {title} / {message}")
        return True
    if not topic:
        print(f"送り先(NTFY_TOPIC)が無いので送りません: {title}")
        return False
    body = json.dumps({"topic": topic, "title": title, "message": message, "priority": priority,
                       "tags": list(tags), "click": SITE}).encode("utf-8")
    req = urllib.request.Request("https://ntfy.sh/", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        print(f"通知した: {title}")
        return True
    except Exception as e:  # noqa: BLE001  届かなくても止めない（次の回にもう一度）
        print(f"通知できなかった: {title} / {e}")
        return False


def deadlines(res, day):
    """速報の各場の締切（HH:MM）から（最初, 最後）。無ければ None"""
    hm = []
    for v in (res or {}).get("venues", {}).values():
        for t in v.get("deadlines") or []:
            if re.fullmatch(r"\d{1,2}:\d{2}", str(t).strip()):
                hm.append(tuple(map(int, str(t).strip().split(":"))))
    if not hm:
        return None
    hm.sort()
    base = datetime(day.year, day.month, day.day, tzinfo=JST)
    return base + timedelta(hours=hm[0][0], minutes=hm[0][1]), base + timedelta(hours=hm[-1][0], minutes=hm[-1][1])


def check_nightly(st, now, res, dry):
    today = f"{now:%Y-%m-%d}"
    if now.hour < NIGHTLY_FROM or not (res or {}).get("venues"):
        return
    if st.get("nightly") in (today, "ok " + today):
        return
    try:
        req = urllib.request.Request(f"{SITE}?t={int(now.timestamp())}", headers={"User-Agent": "live-health"})
        with urllib.request.urlopen(req, timeout=60) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        print(f"トップを読めなかった: {e}")
        return
    m = re.search(r"更新 (\d{4})/(\d{2})/(\d{2}) (\d{2}:\d{2})", html)
    if m and f"{m[1]}{m[2]}{m[3]}" == f"{now:%Y%m%d}":
        st["nightly"] = "ok " + today
        return
    shown = f"{m[1]}/{m[2]}/{m[3]} {m[4]}" if m else "読み取れない"
    if send("夜間の公開が終わっていません（Actions から）",
            f"{now:%H:%M} になっても、公開トップの更新が今日（{now:%m/%d}）になっていません（表示：{shown}）。"
            "パソコンが切れているか、夜の処理が止まっています。日中の速報は動いています。", dry):
        st["nightly"] = today


def check_live(st, now, res, latest, dry):
    lv = st.setdefault("live", {})
    dl = deadlines(res, now.date())
    if dl is None or not (dl[0] + timedelta(minutes=LIVE_START_AFTER_FIRST_MIN) <= now
                          <= dl[1] + timedelta(minutes=LIVE_END_AFTER_LAST_MIN)):
        return
    try:
        upd = datetime.fromisoformat(latest["updated"])
        same_day = str(latest.get("date")) == f"{now:%Y%m%d}"
    except (TypeError, KeyError, ValueError):
        return
    age = (now - upd).total_seconds() / 60
    if same_day and age < LIVE_STALE_MIN:
        if lv.get("down"):
            if send("速報が戻りました（Actions から）", f"最終更新 {upd:%H:%M}", dry, priority=3, tags=("white_check_mark",)):
                lv.clear()
        return
    last = lv.get("notified")
    if last and now - datetime.fromisoformat(last) < timedelta(minutes=LIVE_RENOTIFY_MIN):
        return
    why = f"最終更新 {upd:%m/%d %H:%M}（{int(age)}分前）" if same_day else f"日付が {latest.get('date')} のまま"
    if send("速報が止まっています（Actions から）",
            why + "。Actions は動いていますが、取得元から取れていません（断られている・不調）。", dry):
        lv["down"] = True
        lv["notified"] = now.isoformat(timespec="minutes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--now", help="試験用: 今の時刻の代わり（例 2026-11-24T14:00）")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now).replace(tzinfo=JST) if a.now else datetime.now(JST)
    d = Path(a.out) / "live"
    sp = d / "health_state.json"
    st = load_json(sp) or {}
    before = json.dumps(st, sort_keys=True)
    res = load_json(d / f"results_{now:%Y%m%d}.json")
    latest = load_json(d / "latest.json")
    for f, args in ((check_nightly, (st, now, res, a.dry)), (check_live, (st, now, res, latest, a.dry))):
        try:
            f(*args)
        except Exception as e:  # noqa: BLE001  1つが失敗しても残りは続ける
            print(f"{f.__name__} で失敗: {e}")
    if not a.dry and json.dumps(st, sort_keys=True) != before:
        d.mkdir(exist_ok=True)
        sp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
