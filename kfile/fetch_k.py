r"""
夜の正式な競走成績（mbrace の K ファイル）を取って kfile/ に置く

パソコンの夜の自動取得が 403 で取れないときの代わり。Claude の定期実行（毎晩）がこれを動かし、
このブランチの kfile/kYYMMDD.lzh に置く。パソコン側はここから取れる:
  https://raw.githubusercontent.com/CrapeMyrtlllle/discovery/claude/dazzling-shannon-71r8lw/kfile/kYYMMDD.lzh

使い方:
    python3 kfile/fetch_k.py                  # 今日（日本時間）と、直近 3 日のうちまだ無い日
    python3 kfile/fetch_k.py --date 20261120  # 日付を指定（あっても取り直す）
    python3 kfile/fetch_k.py --days 7         # さかのぼる日数を変える

Python の標準の部品だけで動く。取る先は www1.mbrace.or.jp/od2/K/YYYYMM/kYYMMDD.lzh（1日1件、間を 2 秒あける）。
今日の分は、あとから夜のレースが足されることがあるので毎回取り直して、中身が変わったときだけ置き換える。
終わりの値: 0 = 取れた・変化なし ／ 1 = 今日の分（または指定した日）が取れなかった
"""

import argparse
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://www1.mbrace.or.jp/od2/K"
UA = {"User-Agent": "Discovery K fetch"}
JST = timezone(timedelta(hours=9))
HERE = Path(__file__).resolve().parent


def fetch(ymd):
    """→ (状態, 中身)。状態は "ok" / "まだ無い"（404）/ "失敗: 理由" """
    url = f"{BASE}/{ymd[:6]}/k{ymd[2:]}.lzh"
    err = ""
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                body = r.read()
            # LHA の書庫は 3 バイト目から "-lh" で始まる。エラーページなどを K ファイルとして置かないため
            if len(body) < 1000 or body[2:5] != b"-lh":
                return f"失敗: K ファイルの形ではありません（{len(body)} バイト）", None
            return "ok", body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "まだ無い", None
            err = f"HTTP {e.code}"
            if e.code in (401, 403):
                break   # 断られたときは取り直さない
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            err = str(e)
        time.sleep(5)
    return f"失敗: {err}", None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYYMMDD（省略時は日本時間の今日と、直近のまだ無い日）")
    ap.add_argument("--days", type=int, default=3, help="さかのぼる日数（既定 3）")
    a = ap.parse_args()
    today = datetime.now(JST).strftime("%Y%m%d")
    if a.date:
        days = [a.date]
    else:
        days = [(datetime.now(JST) - timedelta(days=i)).strftime("%Y%m%d") for i in range(a.days + 1)]
    bad = 0
    first = True
    for ymd in days:
        path = HERE / f"k{ymd[2:]}.lzh"
        must = bool(a.date) or ymd == today
        if path.exists() and not must:
            continue
        if not first:
            time.sleep(2)
        first = False
        state, body = fetch(ymd)
        if state != "ok":
            print(f"{ymd}: {state}")
            if must:
                bad += 1
            continue
        if path.exists() and path.read_bytes() == body:
            print(f"{ymd}: 変化なし（{len(body)} バイト）")
            continue
        was = path.exists()
        path.write_bytes(body)
        print(f"{ymd}: {'置き換えました' if was else '取りました'}（{len(body)} バイト）→ kfile/{path.name}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
