r"""
選手コメント・記者情報の速報（2026/11/23 追加。ユーザーの指示「パソコンが切れていても日中のコメントを入れ替えたい」）

GitHub Actions（速報と同じ live_loop.sh の中）で、各場の公式サイトから今日の選手コメントを取り、
live/comments_YYYYMMDD.json に置く。各ページ（Boat Board・簡易版・番組表）は DLive.comment() で読み、
パソコンが作ったときに埋め込んだコメント（boats[].cm・e.cm）より、こちらの今日の分を先に出す。
取り方はパソコンの fetch_comment.py をそのまま使う（.github/scripts/ に同じものを置く。直したら置き直す）。
どのコメントを出すかは make_today_racers.latest_comment と同じ（選手コメントがあればそれ、無ければ記者の文。
同じ日の区分は COMMENT_ORDER の順）。こちらは今日の分だけ（前の日の分はページに埋め込んだものを使う）。

取る時刻（日本時間）: SLOTS の時刻を過ぎて、その回をまだ取っていなければ取る（live_loop.sh が1分おきに起こす。
1回 数分。取っているあいだに次は起こさない）。パソコンの BoatraceComment（1:00・6:00・10:05・15:15・21:35）に合わせ、
Actions の動く 7〜23時の中で 7:05（1:00・6:00 の代わり）・10:05（戸田の記者寸評）・15:15 の3回（2026/11/23 ユーザー指定で減らした）。
取る場は、速報（live/results_今日.json）で今日開催している場だけ。
番組表: パソコンが公開する cm/timetable.json（make_today_racers.py。今日の分なら使う）。蒲郡・唐津・平和島・児島は
  番組表で艇を結び付けるので、無い日はその4場を取れない（ほかの場は取れる）。

使い方:
    python3 live_comments.py --out .            # 取る時刻なら取る
    python3 live_comments.py --out . --force    # 時刻に関係なく今すぐ取る

書き出し（--out の下）
  live/comments_YYYYMMDD.json … {date, updated, slot, v: {場コード: {R: {艇番: {t 文, k 区分, s c/k, d 月/日, reg}}}},
                                  n: {場コード: 場名}}
  live/comments_latest.json   … {date, updated, slot, file}（各ページは1分おきにこれを見て、変わったときだけ中身を取る）
"""
import argparse
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
SLOTS = ["07:05", "10:05", "15:15"]   # 2026/11/23 ユーザー指定で減らした(21:35 はその日のレースがほぼ終わっているので外す)
COMMENT_ORDER = {"c": ["当日", "前日"],     # make_today_racers.py と同じ
                 "k": ["当日", "記者の目", "記者", "記者コメント", "特注情報", "目展示評価", "前日気配", "耳より情報",
                       "M評価", "おかぺん評価"]}
JO_NAME = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖",
    "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島", "17": "宮島", "18": "徳山",
    "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}


def load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def same_name(a, b):
    """fetch_oriten_bc._same_name と同じ（番組表の選手名は4文字までに切れている）"""
    a = a.replace("　", "").replace(" ", "")
    b = b.replace("　", "").replace(" ", "")
    if not a or not b:
        return False
    if len(a) < len(b):
        a, b = b, a
    i = 0
    for ch in a:
        if i < len(b) and ch == b[i]:
            i += 1
    return i == len(b)


def write_atomic(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)   # 速報の載せる処理(git add)が書きかけを拾わないように


def pick(rows):
    """艇ごとのいちばん新しい1件(今日の分だけなので、種類と区分の順で決める)"""
    for kind in ("c", "k"):
        cand = [r for r in rows if r["kind"][0] == kind]
        if cand:
            order = COMMENT_ORDER[kind]
            x = min(cand, key=lambda r: order.index(r["区分"]) if r["区分"] in order else len(order))
            return {"t": x["本文"], "k": x["区分"], "s": kind, "d": f"{int(x['日付'][4:6])}/{int(x['日付'][6:])}",
                    "reg": x["登録番号"]}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    now = datetime.now(JST)
    day = now.strftime("%Y%m%d")
    slot = max((s for s in SLOTS if s <= now.strftime("%H:%M")), default=None)
    d = Path(a.out) / "live"
    d.mkdir(parents=True, exist_ok=True)
    out_p, latest_p = d / f"comments_{day}.json", d / "comments_latest.json"
    prev = load_json(out_p) or {}
    if not a.force and (slot is None or prev.get("slot") == slot):
        return 0   # まだ取る時刻でない・この回は取った
    res = load_json(d / f"results_{day}.json") or {}
    open_jo = set((res.get("venues") or {}).keys())
    if not open_jo:
        print("コメント: 今日の開催場が速報にまだ無いので取らない")
        return 0

    tt_raw = load_json(Path(a.out) / "cm" / "timetable.json") or {}
    tt = {}
    if tt_raw.get("date") == day:
        tt = {(j, int(r)): b for j, rs in tt_raw["tt"].items() for r, b in rs.items()}
    stub = types.ModuleType("fetch_oriten_bc")   # fetch_comment.py が読む番組表(パソコンの番組表CSVの代わり)
    stub.JO_NAME, stub._same_name = JO_NAME, same_name
    stub.meetings = lambda: ({}, day)
    stub.timetable = lambda dd: {k: {w: tuple(v) for w, v in b.items()} for k, b in tt.items()} if dd == day else {}
    sys.modules["fetch_oriten_bc"] = stub
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import fetch_comment as fc
    fc.LOG = Path("/tmp/live_comments.log")

    v = dict(prev.get("v") or {}) if prev.get("date") == day else {}
    n_ok = 0
    for jo in sorted(fc.SITES):
        if jo not in open_jo:
            continue
        try:
            rows = fc.FETCH[fc.SITES[jo]["type"]](jo, day)
        except Exception as e:  # noqa: BLE001  1場が取れなくてもほかの場は続ける(前の回の分は残す)
            print(f"コメント: {JO_NAME[jo]} 取得失敗 {type(e).__name__}: {str(e)[:120]}")
            continue
        by = {}
        for r in rows:
            by.setdefault((int(r["レース"]), int(r["枠"])), []).append(r)
        out = {}
        for (rno, w), rs in by.items():
            x = pick(rs)
            if x:
                out.setdefault(str(rno), {})[str(w)] = x
        if out:
            v[jo] = out
            n_ok += 1
        print(f"コメント: {JO_NAME[jo]} {sum(len(x) for x in out.values())}艇")
    data = {"date": day, "updated": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"), "slot": slot, "v": v,
            "n": {jo: JO_NAME[jo] for jo in v}}   # n: 場コード → 場名(ページは場名で引く)
    write_atomic(out_p, data)
    write_atomic(latest_p, {"date": day, "updated": data["updated"], "slot": slot, "file": out_p.name})
    for p in d.glob("comments_2*.json"):   # 前の日の分は要らない(ページに埋め込んだものを使う)
        if p.name != out_p.name:
            p.unlink()
    print(f"コメント: {n_ok}場 書き出し {out_p.name}（{slot or '手動'}の回）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
