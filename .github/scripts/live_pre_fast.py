r"""
直前情報（展示タイム・体重・チルト・スタート展示）だけを急いで取る（2026/11/21 追加）

live_results.py の全体の取得（結果・払戻・水面気象・オリ展。3分おき）のあいだに、1分おきに動かす。
取るのは、締切の PRE_BEFORE 分前を過ぎて、まだ結果が出ておらず、直前情報がそろっていないレースの
bc_j_tkz だけ（1回あたり数件）。開催一覧・締切・結果は、全体の取得が書いた results_YYYYMMDD.json をそのまま使う。
読み方・置き場所・数字の定義は live_results.py（parse_tkz・pre_complete・write）と同じ。

使い方:
    python live_pre_fast.py --out <Pagesリポジトリの場所>
Pages リポジトリでは .github/scripts/ に live_results.py と並べて置く（live_loop.sh から呼ぶ）。
"""

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import live_results as lr


def run(out):
    now = datetime.now(lr.JST)
    ymd = now.strftime("%Y%m%d")
    path = Path(out) / "live" / f"results_{ymd}.json"
    data = lr.load_json(path)
    if not data or data.get("date") != ymd or not data.get("venues"):
        print(f"{ymd}: 今日の速報のファイルがまだ無いので、全体の取得を待ちます")
        return 0
    t0 = time.time()
    got_n = asked = 0
    now_min = now.hour * 60 + now.minute
    for jo, ve in data["venues"].items():
        races = ve.get("races") or {}
        cancel = ve.get("cancel") or []
        dls = ve.get("deadlines") or []
        pre = data.setdefault("pre", {}).setdefault(jo, {})
        for rno in range(1, 13):
            key = str(rno)
            c = cancel[rno - 1] if rno - 1 < len(cancel) else ""
            if (c and "中止" in c) or lr.pre_complete(pre.get(key)):
                continue
            if (races.get(key) or {}).get("status"):
                continue   # 結果が出たあとは全体の取得（live_results.py の fetch_pre）にまかせる
            dl = dls[rno - 1] if rno - 1 < len(dls) else ""
            if not re.match(r"^\d\d:\d\d$", dl or ""):
                continue
            mins = int(dl[:2]) * 60 + int(dl[3:]) - now_min
            if mins > lr.PRE_BEFORE:
                continue
            p = lr.parse_tkz(lr.get(f"/hp_txt/{jo}/bc_j_tkz_{ymd}_{jo}_{rno:02d}.txt"))
            asked += 1
            if p and p != pre.get(key):
                pre[key] = p
                got_n += 1
    if not got_n:
        print(f"{ymd}: 直前情報の新しい分なし（リクエスト {asked} 件・{time.time() - t0:.0f} 秒）")
        return 0
    data["updated"] = datetime.now(lr.JST).isoformat(timespec="seconds")
    lr.write(out, data)
    print(f"{ymd}: 直前情報 {got_n} レースを更新（リクエスト {asked} 件・{time.time() - t0:.0f} 秒）")
    return got_n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Pages リポジトリの場所（live/ を読み書きする）")
    run(ap.parse_args().out)


if __name__ == "__main__":
    main()
