r"""
各場の公式サイトから選手コメントと記者情報を取る（2026/11/20 追加）。
  選手コメント（選手本人の言葉）：鳴門・下関・芦屋・徳山・三国・常滑・蒲郡・若松・浜名湖・尼崎・大村・唐津・児島・福岡・津・宮島
  記者情報（記者が書いた足・気配の評価）：江戸川・常滑・蒲郡・浜名湖・尼崎・大村・平和島・桐生・戸田
選手コメントと記者情報は混ぜない（2026/11/20 ユーザーの指示）。置き場所・ファイル名・最後の列名を分け、どちらも「区分」の列を持つ。
  選手コメントの区分：前日（前日の走りや前検についての言葉）・当日（常滑の「直前」＝特訓後・レース後、蒲郡の「当日」）
    鳴門・下関・芦屋は1日1つで、区分はすべて「前日」として入れている。若松はタグ「前日」がサイトに付いている。
  記者情報の区分：特注情報（江戸川）・記者・記者の目（常滑・尼崎）・目展示評価・耳より情報（蒲郡）・当日（浜名湖）・M評価（大村）・前日気配・おかぺん評価（平和島）・記者コメント（桐生）・記者寸評（戸田）
取りに行くのは場ごとに「進行中の節＋過去4節」の範囲（2026/11/20 ユーザーの指示）。取った日のファイルは古くなっても消さずに全部残す
（2026/11/21 ユーザーの指示。DELETE_OLD = False。平和島・児島などは過去の分を取り直せないため）。

場ごとの取り方（SITES の type）:
  - jlc（鳴門 14・下関 19・芦屋 21・徳山 18・三国 10・津 09）：同じ作りのサイトで、出走表などのタブを次のURLから読み込んでいる（HTML・UTF-8）。
      https://<サイト>/sp/ajax/ajax_yosou.php?targetday=YYYYMMDD&race=R&req=<syussou|cyokuzen>&run=<タブ>
      場ごとの違い（req・タブ番号・コメントの列・列の見出し）は SITES に書く。
      鳴門 www.n14.jp：「選手コメント」タブ run=2。コメントは col4。級別/登録番号は com-toban に「A1/5054」。
        11/19 1R の6艇はボートレース日和のコメントと一字一句同じ。2023/12 の日付でも取れる。
      芦屋 www.boatrace-ashiya.com：「モーター・選手コメント」タブ run=1。コメントは col5（col4 はモーター番号）。
        級別は col-kyu_A2 のクラス、登録番号は com-toban。2025 以前の日付は空の返事だった（開催日かは未確認）。
      下関 www.boatrace-shimonoseki.jp：「直前情報」（req=cyokuzen）の「選手コメント」タブ run=4。見出しは「前日コメント」で
        コメントは col3（col4 は過去コメントの小窓なので取らない）。級別/登録番号は com-toban に「B1 /5020」。
      徳山 www.boatrace-tokuyama.jp：出走表の「選手コメント」タブ run=3。コメントは col3（zComment の欄だけ）。
        級別/登録番号は com-toban に「A2/4738」。コメントの無い艇は「※コメントなし」なので取らない。10/3 の日付でも取れる。
      三国 www.boatrace-mikuni.jp：出走表の「選手ｺﾒﾝﾄ」タブ run=2。コメントは col3。欄の中の「過去コメント」の小窓とボタンは取り除く。
        級別/登録番号は com-toban に「A1</span>/4809」。10/16 の日付でも取れる。
      津 www.boatrace-tsu.com：芦屋と同じ作り（page=yosou-yosou）。出走表の「選手コメント」タブ run=1、コメントは col3（z_comment）。
        登録番号は「4610/東京/36/A1」の形で com-toban が無いので、番組表CSVから枠番で付ける（fetch_jlc）。11/3 の日付でも取れる。
        mbrace の番組表TXTが 11/19〜21 をどれも「第１日」と書いていて、節の区切りが1日ずつに分かれる（取りに行く範囲が短くなる）。
      同じ表の上の「コメント」（記者予想の文）は取らない。1日2走でも同じ文（鳴門 678件・芦屋 584件・下関 528件で確認）。
  - tokoname（常滑 08 www.boatrace-tokoname.jp）：jlc と同じ作りで syussou run=2「選手コメント」。1艇にタグ付きの文が並ぶ：
      前日・直前（選手）、記者（記者）。直前の文に「（記者の目）…」が続くことがあり、そこから後ろは記者情報「記者の目」に分ける。
      履歴の小窓（コメント履歴）は取らない。表に登録番号が無いので番組表CSVから枠番で付ける（選手名が合うときだけ）。
      ボートレース日和の常滑は【直前】【記者】をつないだ文（11/16・11/18 で確認）。
  - wakamatsu（若松 20 www.wmb.jp）：jlc と同じ作りで syussou run=1「モーター・ボート・選手コメント」。常滑と同じタグ付きの欄
      （タグは「前日」と、10/13〜18 の節では「直前」も。記者のタグは 10/5〜11/17 で無かった）。タグの扱いは常滑と同じ（tag_rows）。級別は col-kyu、登録番号は canter_toban。
      最終日（11/18）はコメント欄が空で、1R が空の日は「なし」とする。
  - 浜名湖 06 www.boatrace-hamanako.jp も type=wakamatsu（同じタブ run=1）。タグとコメントが <td> の中、登録番号は「B1</span>/ 4197」の形。
      タグ「前日」は選手の言葉、「当日」は記者が展示・特訓を見て書いた文（「バックでは○○より少し伸びる」など）なので記者情報。
      9/30〜11/4 の各日、全艇に前日・当日が1つずつ。
  - amagasaki（尼崎 13 www.boatrace-amagasaki.jp）：jlc と同じ作りで syussou run=1「モーター・ボート・選手コメント」。
      タグは comment_tag_zenjitsu（前日＝選手）・comment_tag_toujitsu（当日）。当日の文は「（記者の目）…」なら記者、
      「（特訓後）…」「（１走後）…」なら選手のその日の言葉なので、常滑の「直前」と同じ扱い（parse_amagasaki）。
      当日の文はサイトに直近の節の分しか残らない（11/20 に見たとき 11/12〜 だけ）ので、毎日取らないと失う。
  - omura（大村 24 omurakyotei.jp）：/yosou/sp/syussou/?day=YYYYMMDD&race=RR の「選手コメント・モーター評価」の表。
      ふつうの文＝選手の言葉（前日）、赤字の「(当日気配)」＝その日の選手の言葉（「レース後「…」」。見出しと末尾の時刻は外す）、
      M評価(記者)＝点数と出足・伸足・回足の記号（記者情報「M評価」）。登録番号は「過去のコメント」のリンク past.php?num= から。
      10/15 の日付でも当日気配まで残っている。
  - karatsu（唐津 23 www.boatrace-karatsu.jp）：/sp/index.php?page=raceinfo-racers_comment&day=YYYYMMDD の「全選手コメント」（1日1ページ）。
      zComment＝前日、cComment＝直前（末尾の「（12：27現在）」は外す）。どちらも選手の言葉。レースと枠は番組表CSVから登録番号で付ける。
      同じ欄のモーター評価（出足・伸び足の記号の画像・素性）は記号の意味が分からないので取らない。10/8 の日付でも取れる。
  - heiwajima（平和島 04 www.heiwajima.gr.jp）：予想のページ /asp/kyogi/04/sp/syusso01RR.htm の「記者予想」の表の
      「前日気配･短評」（記者の短評。日和の平和島の「コメント」と同じ文）。URL に日付が無く、その日の分しか見られないので、
      今日と前日だけ見に行き、1R の6人の登録番号が番組表CSVのその日の1Rと合うときだけ保存する。過去の節の分は取れない。
      同じページの「おかぺんモーター評価」（評価 SS〜E・出足・伸び・短評。モーターごとで更新日時つき）も記者情報「おかぺん評価」として取る
      （2026/11/21 ユーザーの指示で採用。文の末尾に「（2026/11/16 15:04 更新）」のようにページの更新日時を付ける）。
      ライブレポート（www.boatrace-livereport.com/heiwajima の「気配・直前情報」）は採用しない（11/21 ユーザーの指示）。
  - kojima（児島 16 www.kojimaboat.jp）：予想のページ /asp/kyogi/16/pc/syusso01RR.htm の表（table_yoso4）の最後の列「選手コメント」。
      平和島と同じく URL に日付が無くその日の分しか見られないので、今日と前日だけ見に行き、1R の登録番号が番組表と合うときだけ保存。
      区分は「前日」とする（2026/8/10 の保存記録の文は「初日と変わらず足は悪くない」など前日までの走りについての言葉）。
      同じ表のモーター評価（出足・伸び足）は記号が画像のクラス番号でしか無いので取らない。表の上の記者の一言（advice）は取らない。
      2026/11/21 は開催が無く、開催中のページではまだ確かめていない（保存記録のページで読み取りを確認）。
  - fukuoka（福岡 22 www.boatrace-fukuoka.com）：/sp/ajax/ajax_syussou.php?targetday=YYYYMMDD&race=R の「選手コメント」の表の col4。
      級別は A1 だけ <span> 付き。col5 の過去コメントの小窓と、ページの上の「予想コメント」（レースごとの記者の文）は取らない。
      10/12 の日付でも取れる。
  - 丸亀 15 www.marugameboat.jp：日和には丸亀のコメントがあるが、公式サイトの見られるページでは見つからなかった（11/21）。
      ユーザーの指示で「無い」とみなす（2026/11/21）。
  - miyajima（宮島 17 www.boatrace-miyajima.com）：HTML の出走表や PDF には無く、トップページの「選手コメント」タブにある。
      中身は race_common/require/kaisai_reload.php に POST（race=R・date=YYYYMMDD）した返事を「####」で分けた28番目。
      日付を指定できるので過去の日も取れる（9/20 で確認）。2026/11/21 ユーザーの指摘で見つけた（最初は「無い」と誤って報告した）。
  - びわこ 11 www.boatrace-biwako.jp：/sp/index.php?page=yosou-syussou&day=日付&race=R にあるのはレースごとの記者予想の「コメント」（サンスポ記者）だけで、
      艇ごとの選手コメント・記者の文は無い（2026/11/21 確認）。
  - 住之江 12 www.boatrace-suminoe.jp：/asp/kyogi/12/sp/ の記者予想（前日・直前）の「コメント」はレースごとの文だけ。艇ごとの選手コメントは無い。
      直前のページ（yoso05RR）に艇ごとの「展示評価」（5段階）の欄があるが、11/21 朝は空で中身は未確認。取っていない。
  - kiryu（桐生 01 www.kiryu-kyotei.com）：/sp/ajax/ajax_syussou.php?day=YYYYMMDD&race=R の「モーター素性・記者コメント」の表の col5。
      記者が書いた艇ごとの文なので記者情報「記者コメント」。モーター素性（記号の画像）と履歴の小窓は取らない。11/5 の日付でも取れる。
  - 多摩川 05 www.boatrace-tamagawa.com：jlc と同じ作りだが、あるのはレースごとの「予想コメント」（記者）だけで、艇ごとの文は無い（11/21 確認）。
  - gamagori（蒲郡 07 www.gamagori-kyotei.com）：PC版の「ピットの声」のコメントは日ごとの JS
      /asp/gamagori/kyogi/kyogihtml/js/comment<日付>07.js に登録番号ごとに入っている（1日1ファイル）。
      funcBeforeComment＝前日、funcToDayComment＝当日（日和の蒲郡のコメントと同じ文。11/13 1R で確認）。
      funcToDayNewComment（1人に最大4つ・タイプの番号つき）はタイプの意味が分からないので取らない。
      レースと枠は番組表CSVから付ける。記者情報はスマホ版の予想のページ
      /asp/gamagori/sp/kyogi/kyogihtml/recomend/recomend<日付>07<RR>.htm の「目展示評価」と「耳より情報」で、
      艇番の画像（taka_NS.png）のあとの文をその艇のものとする（最初の画像より前の前置きの文は取らない）。
  - edogawa（江戸川 03 www.boatrace-edogawa.com）：選手コメントの欄が無い。出走表のページ
      /sp/index.php?page=yosou-syussou&day=YYYYMMDD&race=R の「前日予想」の表の「特注情報」（江戸川番記者）を取る。
      日和の江戸川の「コメント」はこの特注情報と同じ文（11/18 1R の6艇で確認）。開催のない日は「本場非開催」で空。
  - toda（戸田 02 www.boatrace-toda.jp）：トップページの出走表の「記者寸評」。racer_comment.js が /xml/kaisai/YYYYMMDD/race_table_comment_RR.xml を読む
      （枠番・登録番号・文）。記者の文なので記者情報「記者寸評」。開催日の朝10時ごろ出る。過去の日も取れる（11/1 で確認）。
      最初は「公式サイトにレースごとのページが無い」と誤って報告した（2026/11/21 ユーザーの指示で調べ直して見つけた）。
  - 公式の速報サイトにはコメントのファイルが無い（403）。ほかの場は場ごとに出どころを調べて SITES・FETCH に足す。

使い方の決まり（作業場のルール）:
  - タスク BoatraceComment（毎日 1:00・6:00・10:05・15:15・21:35）が動かす。10:05 は戸田の記者寸評（朝10時ごろ出る）のため（11/21 追加）。1R に間に合うよう夜1時に取り、出ていない場は朝6時に取り直す
    （2026/11/21 ユーザーの指示）。15:15・21:35 は当日の文（尼崎・大村・唐津・常滑など）と、その日の分しか見られない平和島・児島のため。
  - ボートレース日和は利用規約（第5条）で自動取得・スクレイピングを禁止しているので、日和からは取らない（2026/11/21 確認）。
  - note 記事には選手コメントを引用も言い換えもしない（CLAUDE.md）。ここで集めるのは自分の分析用。
  - 番組表ページ（today/・make_today_racers.py）のスマホのモーターのタブに「最新コメント」として出す（2026/11/21 ユーザーの指示）。
    選手コメントが無い場は記者の文を「（記者：区分）」と補足して出す。ほかの公開ページに出すときはユーザーに確かめる。

節の区切りは fetch_oriten_bc.py の meetings() と同じ（番組表CSVの1Rの日次「第1日」・タイトルが変わったとき）。

保存先: 選手コメント\<場名>\comment_<場コード>_YYYYMMDD.csv（1日1ファイル）と まとめ.csv（残している日をつないだもの）
  列: 日付・場コード・場名・レース・枠・級別・登録番号・選手名・区分・コメント
記者情報は 記者情報\<場名>\kisha_<場コード>_YYYYMMDD.csv と まとめ.csv。列の最後が「記者情報」
  区分の列は 11/20 に足した（それまでに取った鳴門・下関・芦屋は「前日」、江戸川は「特注情報」を入れ直した）。

使い方:
  python fetch_comment.py                 全場：取りに行く範囲のうち未取得の日を取り、まとめを作り直す（古い日は消さない）
  python fetch_comment.py 20261119        指定日の全場だけ取る（消さない）
  python fetch_comment.py show            場ごとに残す節と日を表示するだけ
  オプション --jo 01,02,03,04,06,07,08,09,10,13,14,16,17,18,19,20,21,22,23,24  --force（取得済みでも取り直す）  --wait 2（1回の読み込みごとの待ち秒）
当日の分は、コメントが出そろっていないことがあるので、実行のたびに取り直す。
"""
import csv
import html
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests

from fetch_oriten_bc import JO_NAME, _same_name, meetings, timetable  # 場名・節の区切り・番組表は同じものを使う

BASE_DIR = Path(__file__).resolve().parent.parent  # このファイル(自動化スクリプト\)の1つ上＝作業場のフォルダ
LOG = BASE_DIR / "logs" / "comment.log"
KEEP_PAST = 4  # 取りに行く過去の節の数（進行中の節は別に。まだ取っていない日をこの範囲で探す）
# 古い日のファイルを消すか。2026/11/21 ユーザーの指示で消さずに全部残す（平和島・児島などは過去の分を取り直せないため）
DELETE_OLD = False
WAIT = 2.0
# 選手コメント（選手本人の言葉）と記者情報（記者が書いた気配の評価）は混ぜない。置き場所・ファイル名・列名を分ける。
# 区分：選手コメントは「前日」「当日」（常滑の直前・蒲郡の当日）。記者情報は場ごとの欄の名前（特注情報・記者・記者の目・目展示評価・耳より情報）
KINDS = {
    "comment": {"root": BASE_DIR / "選手コメント", "prefix": "comment", "col": "コメント"},
    "kisha": {"root": BASE_DIR / "記者情報", "prefix": "kisha", "col": "記者情報"},
}
BASE_COLS = ["日付", "場コード", "場名", "レース", "枠", "級別", "登録番号", "選手名", "区分"]
# type: jlc＝鳴門・下関・芦屋の作り（ajax_yosou.php の表に選手コメント）／edogawa／tokoname／gamagori
SITES = {
    "01": {"type": "kiryu", "kinds": ("kisha",), "host": "https://www.kiryu-kyotei.com"},
    "02": {"type": "toda", "kinds": ("kisha",), "host": "https://www.boatrace-toda.jp"},
    "03": {"type": "edogawa", "kinds": ("kisha",), "host": "https://www.boatrace-edogawa.com", "head": "特注情報</th>"},
    "07": {"type": "gamagori", "kinds": ("comment", "kisha"), "host": "https://www.gamagori-kyotei.com"},
    "08": {"type": "tokoname", "kinds": ("comment", "kisha"), "host": "https://www.boatrace-tokoname.jp"},
    "13": {"type": "amagasaki", "kinds": ("comment", "kisha"), "host": "https://www.boatrace-amagasaki.jp"},
    "09": {"type": "jlc", "kinds": ("comment",), "host": "https://www.boatrace-tsu.com", "req": "syussou", "run": 1, "col": "col3", "head": "選手コメント</th>"},
    "10": {"type": "jlc", "kinds": ("comment",), "host": "https://www.boatrace-mikuni.jp", "req": "syussou", "run": 2, "col": "col3", "head": "選手コメント</th>"},
    "14": {"type": "jlc", "kinds": ("comment",), "host": "https://www.n14.jp", "req": "syussou", "run": 2, "col": "col4", "head": "選手コメント</th>"},
    "16": {"type": "kojima", "kinds": ("comment",), "host": "https://www.kojimaboat.jp"},
    "17": {"type": "miyajima", "kinds": ("comment",), "host": "https://www.boatrace-miyajima.com"},
    "18": {"type": "jlc", "kinds": ("comment",), "host": "https://www.boatrace-tokuyama.jp", "req": "syussou", "run": 3, "col": "col3", "head": "選手コメント</th>"},
    "19": {"type": "jlc", "kinds": ("comment",), "host": "https://www.boatrace-shimonoseki.jp", "req": "cyokuzen", "run": 4, "col": "col3", "head": "前日コメント</th>"},
    "04": {"type": "heiwajima", "kinds": ("kisha",), "host": "https://www.heiwajima.gr.jp"},
    "06": {"type": "wakamatsu", "kinds": ("comment", "kisha"), "host": "https://www.boatrace-hamanako.jp"},
    "20": {"type": "wakamatsu", "kinds": ("comment", "kisha"), "host": "https://www.wmb.jp"},
    "22": {"type": "fukuoka", "kinds": ("comment",), "host": "https://www.boatrace-fukuoka.com"},
    "23": {"type": "karatsu", "kinds": ("comment", "kisha"), "host": "https://www.boatrace-karatsu.jp"},
    "24": {"type": "omura", "kinds": ("comment", "kisha"), "host": "https://omurakyotei.jp"},
    "21": {"type": "jlc", "kinds": ("comment",), "host": "https://www.boatrace-ashiya.com", "req": "syussou", "run": 1, "col": "col5", "head": "選手コメント</th>"},
}
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (comment data collector)", "X-Requested-With": "XMLHttpRequest"})


def columns(k):
    return BASE_COLS + [KINDS[k]["col"]]


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    if sys.stdout is not None:
        print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def get(jo, url, params=None, label=""):
    """本文（UTF-8）。403/404 は空。通信の失敗は3回まで取り直す"""
    host = SITES[jo]["host"]
    for attempt in range(3):
        try:
            r = SESSION.get(url, params=params, timeout=20, headers={"Referer": host + "/"})
            time.sleep(WAIT)
            if r.status_code in (403, 404):
                return ""
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except requests.RequestException as e:
            log(f"{JO_NAME[jo]} {label} 取得失敗({attempt + 1}回目): {e}")
            time.sleep(10)
    raise RuntimeError(f"{JO_NAME[jo]} {label} が取れない")


def _text(s):
    s = re.sub(r"<br\s*/?>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).replace("\u3000", " ").strip()


def _name(s):
    return re.sub(r"\s+", "", _text(s))


def _meta(jo, day, race, waku, name):
    """番組表CSVから (級別, 登録番号, 選手名)。選手名が分かっているときは合うときだけ"""
    b = timetable(day).get((jo, race), {}).get(str(waku))
    if not b or (name and not _same_name(name, b[2])):
        return "", "", name
    return b[1], b[0], name or re.sub(r"\s+", "", b[2])


def _row(day, jo, race, waku, kyu, no, nm, kind, kubun, text):
    return {"日付": day, "場コード": jo, "場名": JO_NAME[jo], "レース": race, "枠": waku, "級別": kyu,
            "登録番号": no, "選手名": nm, "区分": kubun, "kind": kind, "本文": text}


# ---- 鳴門・下関・芦屋 -------------------------------------------------------
def parse(text, col, head="選手コメント</th>"):
    """選手コメントの表 → [(枠, 級別, 登録番号, 選手名, コメント)]。表が無ければ []"""
    i = text.find(head)
    if i < 0:
        return []
    # 三国はコメントの欄の中に「過去コメント」の小窓（中に表）がある。小窓とボタンを取り除く
    # （下関の小窓も同じ形。小窓の中の表を先に消すと、ここが次の表まで消しすぎるので、小窓から先に取り除く）
    rest = re.sub(r"<div class='js-lightbox-target'.*?</table>\s*</div>\s*</div>", "", text[i:], flags=re.S)
    rest = re.sub(r"<div class='comment_history'>.*?</div>", "", rest, flags=re.S)
    # 下関はコメント履歴の小窓の中にも表があるので、先に取り除いてから表の終わりを探す（残っていれば）
    rest = re.sub(r"<table class='par-table01 history'>.*?</table>", "", rest, flags=re.S)
    j = rest.find("</table>")
    table = rest[:j if j > 0 else None]
    parts = re.split(r"<td class='col\d waku[^']*'[^>]*>\s*(\d)\s*</td>", table)
    out = []
    for k in range(1, len(parts) - 1, 2):
        waku, chunk = int(parts[k]), parts[k + 1]
        com = re.search(rf"<td class='{col}'[^>]*>(.*?)</td>", chunk, re.S)
        if not com:
            continue
        toban = re.search(r"class='com-toban[^']*'>(.*?)</li>", chunk, re.S)  # 下関は級別が <span> の中
        tb = re.sub(r"\s+", "", _text(toban.group(1))) if toban else ""
        kyu, no = ("", tb)
        if "/" in tb:
            kyu, no = [x.strip() for x in tb.split("/", 1)]
        if not kyu:
            m = re.search(r"col-kyu_([AB][12])", chunk)
            kyu = m.group(1) if m else ""
        name = re.search(r"class='com-rname'>(.*?)</li>", chunk, re.S)
        out.append((waku, kyu, no, _name(name.group(1)) if name else "", _text(com.group(1))))
    return out


def ajax_yosou(jo, day, race, req, run):
    return get(jo, SITES[jo]["host"] + "/sp/ajax/ajax_yosou.php",
               {"targetday": day, "race": race, "req": req, "run": run}, f"{day} {race}R")


def fetch_jlc(jo, day):
    s = SITES[jo]
    rows = []
    for race in range(1, 13):
        boats = parse(ajax_yosou(jo, day, race, s["req"], s["run"]), s["col"], s["head"])
        if not boats and race == 1:
            return []  # 開催なし・まだ出ていない
        for waku, kyu, no, nm, com in boats:
            if not no:  # 津は登録番号が「4610/東京/36/A1」の形で com-toban が無い。番組表CSVから付ける
                kyu2, no, nm = _meta(jo, day, race, waku, nm)
                kyu = kyu or kyu2
            if com and com != "※コメントなし":  # 徳山はコメントの無い艇に「※コメントなし」と出る
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "comment", "前日", com))
    return rows


# ---- 江戸川（記者の特注情報） ------------------------------------------------
def parse_kisha(text, jo, day, race, head):
    """江戸川の前日予想の表（印・枠・選手名・特注情報）→ [(枠, 級別, 登録番号, 選手名, 記者情報)]"""
    i = text.find(head)
    if i < 0:
        return []
    j = text.find("</table>", i)
    table = text[i:j if j > 0 else None]
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        waku = re.search(r"item-col2'>\s*(\d)\s*<", tr)
        name = re.search(r"item-col3'>(.*?)</td>", tr, re.S)
        info = re.search(r"<td class='item-col4'>(.*?)</td>", tr, re.S)
        if not (waku and info):
            continue
        w = int(waku.group(1))
        kyu, no, nm = _meta(jo, day, race, w, _name(name.group(1)) if name else "")
        out.append((w, kyu, no, nm, _text(info.group(1))))
    return out


def fetch_edogawa(jo, day):
    rows = []
    for race in range(1, 13):
        text = get(jo, SITES[jo]["host"] + "/sp/index.php", {"page": "yosou-syussou", "day": day, "race": race}, f"{day} {race}R")
        boats = parse_kisha(text, jo, day, race, SITES[jo]["head"])
        if not boats and race == 1:
            return []
        for waku, kyu, no, nm, info in boats:
            rows.append(_row(day, jo, race, waku, kyu, no, nm, "kisha", "特注情報", info))
    return rows


# ---- 常滑（前日・直前＝選手、記者・記者の目＝記者） ------------------------------
def parse_tokoname(text):
    """→ [(枠, 選手名, [(タグ, 文), …])]。履歴の小窓は除く"""
    i = text.find(">選手コメント</th>")
    if i < 0:
        return []
    rest = re.sub(r"<div class='js-lightbox-target'.*?</table>\s*</div>\s*</div>", "", text[i:], flags=re.S)
    j = rest.find("</table>")
    table = rest[:j if j > 0 else None]
    parts = re.split(r"<tr class='racer_com_name_block'><td class='[^']*col1'>\s*(\d)\s*</td><td class='[^']*col2'>(.*?)</td>", table)
    out = []
    for k in range(1, len(parts) - 2, 3):
        items = re.findall(r"col-comment_tag_[a-z]+'>(.*?)</span>.*?<div class='comment_text'>(.*?)</div>", parts[k + 2], re.S)
        out.append((int(parts[k]), _name(parts[k + 1]), [(_text(t), _text(c)) for t, c in items]))
    return out


def fetch_tokoname(jo, day):
    rows = []
    for race in range(1, 13):
        boats = parse_tokoname(ajax_yosou(jo, day, race, "syussou", 2))
        if not boats and race == 1:
            return []
        for waku, nm, items in boats:
            kyu, no, nm = _meta(jo, day, race, waku, nm)
            for tag, txt in items:
                rows += tag_rows(day, jo, race, waku, kyu, no, nm, tag, txt)
    return rows


def tag_rows(day, jo, race, waku, kyu, no, nm, tag, txt):
    """タグ付きの文（常滑・若松・浜名湖）→ 行。前日・直前＝選手コメント、記者・当日＝記者情報"""
    if not txt:
        return []
    if tag == "前日":
        return [_row(day, jo, race, waku, kyu, no, nm, "comment", "前日", txt)]
    if tag == "当日":
        # 浜名湖の「当日」は、記者が展示・特訓を見て書いた文（「バックでは○○より少し伸びる」「特訓には参加せず気配は不明」など。
        # 2026/11/20 に 10/10・10/30・11/2 の各艇で確認）なので記者情報に入れる
        return [_row(day, jo, race, waku, kyu, no, nm, "kisha", "当日", txt)]
    if tag == "直前":
        # 直前の文に「（記者の目）…」が続くことがある（常滑）。そこから後ろは記者の文
        player, _, eye = txt.partition("（記者の目）")
        out = []
        if player.strip():
            out.append(_row(day, jo, race, waku, kyu, no, nm, "comment", "当日", player.strip()))
        if eye.strip():
            out.append(_row(day, jo, race, waku, kyu, no, nm, "kisha", "記者の目", eye.strip()))
        return out
    if tag == "記者":
        return [_row(day, jo, race, waku, kyu, no, nm, "kisha", "記者", txt)]
    log(f"{JO_NAME[jo]} {day} {race}R 知らないタグ「{tag}」は取らない")
    return []


# ---- 若松（モーター・ボート・選手コメントのタブ。タグ付き） ------------------------
def parse_wakamatsu(text):
    """→ [(枠, 級別, 登録番号, 選手名, [(タグ, 文), …])]"""
    i = text.find("選手コメント</th>")
    if i < 0:
        return []
    # コメント欄の中にも小さな表があるので </table> では切らず、次のタブ（js-unit）の手前までを見る
    j = text.find('<div class="js-unit">', i)
    parts = re.split(r"<td class='col\d waku[^']*'[^>]*>\s*(\d)\s*</td>", text[i:j if j > 0 else None])
    out = []
    for k in range(1, len(parts) - 1, 2):
        chunk = parts[k + 1]
        kyu = re.search(r"col-kyu_([AB][12])", chunk)
        no = re.search(r"class='canter_toban'>\s*(\d+)\s*<", chunk)
        if not no:  # 浜名湖は「B1</span>/ 4197」の形
            no = re.search(r"class='com-toban'>.*?/\s*(\d{4})\s*</li>", chunk, re.S)
        name = re.search(r"class='com-rname'[^>]*>(.*?)</a>", chunk, re.S)
        # タグと文：若松は <div class='comment-table01 tag'>、浜名湖は <td class='comment-table01 tag'> の中
        items = re.findall(r"<(?:div|td) class='comment-table01 tag'>(.*?)</(?:div|td)>.*?"
                           r"<div class='comment_text'[^>]*>(.*?)</div>", chunk, re.S)
        out.append((int(parts[k]), kyu.group(1) if kyu else "", no.group(1) if no else "",
                    _name(name.group(1)) if name else "", [(_text(t), _text(c)) for t, c in items]))
    return out


def parse_amagasaki(text):
    """尼崎（モーター・ボート・選手コメントのタブ）→ parse_wakamatsu と同じ形。
    タグは comment_tag_zenjitsu（前日）・comment_tag_toujitsu（当日）。当日の文は「（記者の目）…」なら記者、
    「（特訓後）…」「（１走後）…」なら選手のその日の言葉なので、常滑の「直前」と同じ扱い（タグを「直前」にして tag_rows へ）。
    過去の日は当日の文が空（2026/11/20 に 10/14〜11/20 で確認）"""
    i = text.find("選手コメント</th>")
    if i < 0:
        return []
    rest = re.sub(r"<div class='js-lightbox-target'.*?</table>\s*</div>\s*</div>", "", text[i:], flags=re.S)  # 過去コメントの小窓
    j = rest.find('<div class="js-unit">')
    parts = re.split(r"<td class='col\d waku[^']*'[^>]*>\s*(\d)\s*</td>", rest[:j if j > 0 else None])
    tagname = {"zenjitsu": "前日", "toujitsu": "直前"}
    out = []
    for k in range(1, len(parts) - 1, 2):
        chunk = parts[k + 1]
        kyu = re.search(r"col-kyu_([AB][12])", chunk)
        no = re.search(r"class='com-toban'>.*?(\d{4})\s*</li>", chunk, re.S)
        name = re.search(r"class='com-rname'[^>]*>(.*?)</a>", chunk, re.S)
        items = re.findall(r"class='ico_comment_tag comment_tag_(\w+)'>.*?class='racer_comment'>(.*?)</span>", chunk, re.S)
        out.append((int(parts[k]), kyu.group(1) if kyu else "", no.group(1) if no else "",
                    _name(name.group(1)) if name else "", [(tagname.get(t, t), _text(c)) for t, c in items]))
    return out


def fetch_wakamatsu(jo, day):
    parser = parse_amagasaki if SITES[jo]["type"] == "amagasaki" else parse_wakamatsu
    rows = []
    for race in range(1, 13):
        boats = parser(ajax_yosou(jo, day, race, "syussou", 1))
        if race == 1 and not any(items for *_, items in boats if any(c for _, c in items)):
            return []  # 開催なし・まだ出ていない（最終日はコメント欄が空のことがある）
        for waku, kyu, no, nm, items in boats:
            for tag, txt in items:
                rows += tag_rows(day, jo, race, waku, kyu, no, nm, tag, txt)
    return rows


# ---- 大村（選手コメント・モーター評価の表） -----------------------------------------
def parse_omura(text):
    """大村 /yosou/sp/syussou/?day=日付&race=RR の「選手コメント・モーター評価」→
    [(枠, 登録番号, 選手名, 前日の文, 当日の文, M評価の文)]。
    ふつうの文＝選手の言葉（前日）。赤字の「(当日気配)」＝その日の選手の言葉（「レース後「…」」の形。見出しと末尾の時刻は外す）。
    M評価(記者)＝点数と出足・伸足・回足の記号（記者の評価）"""
    i = text.find('id="comment"')
    if i < 0:
        return []
    j = text.find("</table>", i)
    out = []
    for w, nm, pt, a, b, c, body in re.findall(
            r'<td class="waku(\d)"[^>]*>([^<]*)</td>\s*<td><strong>([^<]*)</strong></td>.*?'
            r'<td class="sp_hyoka">([^<]*)</td>\s*<td class="sp_hyoka">([^<]*)</td>\s*<td class="sp_hyoka">([^<]*)</td>.*?'
            r'<td colspan="6"[^>]*>(.*?)</td>', text[i:j if j > 0 else None], re.S):
        no = re.search(r"past\.php\?num=(\d+)", body)
        body = re.sub(r"<a [^>]*>.*?</a>", "", body, flags=re.S)
        zen, tou = [], []
        for part in re.split(r"<br\s*/?>", body):
            t = _text(part)
            if not t:
                continue
            if t.startswith("(当日気配)") or t.startswith("（当日気配）"):
                tou.append(re.sub(r"\s*\[\d{1,2}:\d{2}\]\s*$", "", t[6:]).strip())
            else:
                zen.append(t)
        marks = " ".join(f"{k}{v.strip()}" for k, v in (("出足", a), ("伸足", b), ("回足", c)) if v.strip())
        hyoka = " ".join(x for x in (pt.strip(), marks) if x)
        out.append((int(w), no.group(1) if no else "", _name(nm), " ".join(zen), " ".join(tou), hyoka))
    return out


def fetch_omura(jo, day):
    rows = []
    for race in range(1, 13):
        text = get(jo, f"{SITES[jo]['host']}/yosou/sp/syussou/", {"day": day, "race": f"{race:02d}"}, f"{day} {race}R")
        boats = parse_omura(text)
        if race == 1 and not any(z or t for _, _, _, z, t, _ in boats):
            return []  # 開催なし・まだ出ていない
        for waku, no, nm, zen, tou, hyoka in boats:
            kyu, no2, nm = _meta(jo, day, race, waku, nm)
            no = no or no2
            if zen:
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "comment", "前日", zen))
            if tou:
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "comment", "当日", tou))
            if hyoka:
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "kisha", "M評価", hyoka))
    return rows


# ---- 平和島（記者予想の「前日気配･短評」。日付の無いページ＝その日の分だけ） ----------------
def parse_heiwajima(text):
    """平和島 /asp/kyogi/04/sp/syusso01RR.htm の「記者予想」の表 → [(枠, 登録番号, 級別, 選手名, 前日気配･短評)]。
    短評は記者が書いた文（「押し感物足りず。出足○、伸び○」など）なので記者情報。
    同じページの「おかぺんモーター評価」（モーターごと・更新日つき）は日ごとの情報ではないので取らない"""
    i = text.find('id="yoso01"')
    if i < 0:
        return []
    j = text.find("</table>", i)
    out = []
    for tr in re.findall(r'<tr class="line_waku\d+">(.*?)</tr>', text[i:j if j > 0 else None], re.S):
        w = re.search(r'<td class="waku0?(\d)">', tr)
        no = re.search(r"toban=(\d+)", tr)
        name = re.search(r'target="_blank">(.*?)</a>', tr, re.S)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        kyu = re.search(r">\s*([AB][12])\s*<", tr)
        if not (w and no and tds):
            continue
        out.append((int(w.group(1)), no.group(1), kyu.group(1) if kyu else "", _name(name.group(1)) if name else "", _text(tds[-1])))
    return out


def parse_heiwajima_okapen(text):
    """同じページの「おかぺんモーター評価」（id="yoso03"）→ {枠: 文}。2026/11/21 ユーザーの指示で採用。
    文は「評価B 出足○ 伸び▲ 短評…（2026/11/16 15:04 更新）」の形（評価は SS〜E、出足・伸びは ◉◎○▲△×。更新日時はページの表示）"""
    i = text.find('id="yoso03"')
    if i < 0:
        return {}
    j = text.find("</table>", i)
    upd = re.search(r"更新日時：\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})", text)
    when = f"（{upd.group(1)}/{int(upd.group(2))}/{int(upd.group(3))} {upd.group(4)} 更新）" if upd else ""
    out = {}
    for tr in re.findall(r'<tr class="line_waku\d+">(.*?)</tr>', text[i:j if j > 0 else None], re.S):
        w = re.search(r'<td class="waku0?(\d)">', tr)
        hy = re.search(r'<td class="col2[^"]*">(.*?)</td>', tr, re.S)
        de = re.search(r'<td class="col3">(.*?)</td>', tr, re.S)
        no = re.search(r'<td class="col4">(.*?)</td>', tr, re.S)
        tan = re.search(r'<td class="col5">(.*?)</td>', tr, re.S)
        if not w:
            continue
        parts = [f"評価{_text(hy.group(1))}" if hy and _text(hy.group(1)) else "",
                 f"出足{_text(de.group(1))}" if de and _text(de.group(1)) else "",
                 f"伸び{_text(no.group(1))}" if no and _text(no.group(1)) else "",
                 _text(tan.group(1)) if tan else ""]
        body = " ".join(p for p in parts if p)
        if body:
            out[int(w.group(1))] = body + when
    return out


def fetch_heiwajima(jo, day):
    """ページのURLに日付が無く、その日の分しか見られない。今日と前日だけ見に行き、
    1R の6人の登録番号が番組表CSVのその日の1Rと合うときだけ、その日の分として取る"""
    today = date.today()
    d = date(int(day[:4]), int(day[4:6]), int(day[6:]))
    if (today - d).days not in (0, 1):
        return []
    rows = []
    base = f"{SITES[jo]['host']}/asp/kyogi/04/sp"
    for race in range(1, 13):
        page = get(jo, f"{base}/syusso01{race:02d}.htm", label=f"{day} {race}R")
        boats = parse_heiwajima(page)
        okapen = parse_heiwajima_okapen(page)
        tt = timetable(day).get((jo, race), {})
        if race == 1:
            if not boats or sorted(b[1] for b in boats) != sorted(v[0] for v in tt.values()):
                return []  # その日のページではない（別の日・開催なし）
        for waku, no, kyu, nm, t in boats:
            if t:
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "kisha", "前日気配", t))
            if okapen.get(waku):
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "kisha", "おかぺん評価", okapen[waku]))
    return rows


# ---- 児島（予想のページの「選手コメント」。日付の無いページ＝その日の分だけ） ------------------
def parse_kojima(text):
    """児島 /asp/kyogi/16/pc/syusso01RR.htm の予想の表（table_yoso4）→ [(枠, 登録番号, 級別, 選手名, 選手コメント)]。
    選手コメントは表の最後の列（一人称の選手の言葉）。同じ表のモーター評価（出足・伸び足）は記号が画像のクラス番号でしか
    書かれていないので取らない。表の上に流れる記者の一言（advice）は艇ごとの文ではないので取らない"""
    i = text.find("table_yoso4")
    if i < 0:
        return []
    j = text.find("</table>", i)
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", text[i:j if j > 0 else None], re.S):
        w = re.search(r'<td class="waku0?(\d)">\s*\d\s*</td>', tr)
        no = re.search(r"toban=(\d+)", tr)
        name = re.search(r'target="_blank">(.*?)</a>', tr, re.S)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        kyu = re.search(r"<td>\s*([AB][12])\s*</td>", tr)
        if not (w and no and tds):
            continue
        out.append((int(w.group(1)), no.group(1), kyu.group(1) if kyu else "", _name(name.group(1)) if name else "", _text(tds[-1])))
    return out


def fetch_kojima(jo, day):
    """平和島と同じく URL に日付が無いので、今日と前日だけ見に行き、1R の登録番号が番組表と合うときだけ取る"""
    d = date(int(day[:4]), int(day[4:6]), int(day[6:]))
    if (date.today() - d).days not in (0, 1):
        return []
    rows = []
    for race in range(1, 13):
        boats = parse_kojima(get(jo, f"{SITES[jo]['host']}/asp/kyogi/16/pc/syusso01{race:02d}.htm", label=f"{day} {race}R"))
        if race == 1:
            tt = timetable(day).get((jo, race), {})
            if not boats or sorted(b[1] for b in boats) != sorted(v[0] for v in tt.values()):
                return []  # その日のページではない（別の日・開催なし）
        for waku, no, kyu, nm, t in boats:
            if t:
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "comment", "前日", t))
    return rows


# ---- 福岡（出走表の「選手コメント」。日付を指定できる） ------------------------------------
def parse_fukuoka(text):
    """福岡 /sp/ajax/ajax_syussou.php?targetday=日付&race=R の「選手コメント」の表 → [(枠, 登録番号, 級別, 選手名, コメント)]。
    コメントは col4（一人称の選手の言葉）。col5 の「過去コメント」の小窓は取らない。
    ページの上の「予想コメント」（レースごとの記者の文）は艇ごとではないので取らない"""
    i = text.find("選手コメント</th>")
    if i < 0:
        return []
    j = text.find("枠番別過去10走", i)
    out = []
    for w, kyu, nm, no, c in re.findall(
            r"item-body-waku'>(\d)</td>.*?<li class='com-subinfo'>(?:<span[^>]*>)?\s*([AB][12]).*?"
            r"<li class='com-rname[^']*'><span[^>]*>(.*?)</span></li>\s*<li class='com-subinfo'>(\d{4})/.*?"
            r"<td class='col4'>(.*?)</td>", text[i:j if j > 0 else None], re.S):
        out.append((int(w), no, kyu, _name(nm), _text(c)))
    return out


def fetch_fukuoka(jo, day):
    rows = []
    host = SITES[jo]["host"]
    for race in range(1, 13):
        text = get(jo, f"{host}/sp/ajax/ajax_syussou.php", {"targetday": day, "race": race}, f"{day} {race}R")
        boats = parse_fukuoka(text)
        if not any(c for *_, c in boats) and race == 1:
            return []  # 開催なし・まだ出ていない
        for waku, no, kyu, nm, c in boats:
            if c:
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "comment", "前日", c))
    return rows


# ---- 桐生（モーター素性の表の「記者コメント」。日付を指定できる） ---------------------------
def parse_kiryu(text):
    """桐生 /sp/ajax/ajax_syussou.php?day=日付&race=R の「モーター素性・記者コメント」の表 → [(枠, 選手名, 記者コメント)]。
    記者が書いた艇ごとの文（「１Ｒ比較断然伸び一撃…」など）なので記者情報。モーター素性（記号の画像）と履歴の小窓は取らない。
    選手名は履歴の小窓の見出し「○○選手の記者コメント履歴」から取る"""
    i = text.find("記者コメント</th>")
    if i < 0:
        return []
    j = text.find("</table>", text.find("</tbody>", i))
    out = []
    for tr in re.split(r"<tr class='(?:odd|even)'>", text[i:j if j > 0 else None])[1:]:
        w = re.search(r"im_color(\d) bodyh_01", tr)
        c = re.search(r"<td class='col5'>(.*?)</td>", tr, re.S)
        nm = re.search(r"comment_small-text'>(.*?)選手の記者コメント履歴", tr, re.S)
        if w and c:
            out.append((int(w.group(1)), _name(nm.group(1)) if nm else "", _text(c.group(1))))
    return out


def fetch_kiryu(jo, day):
    rows = []
    host = SITES[jo]["host"]
    for race in range(1, 13):
        text = get(jo, f"{host}/sp/ajax/ajax_syussou.php", {"day": day, "race": race}, f"{day} {race}R")
        boats = parse_kiryu(text)
        if not any(c for *_, c in boats) and race == 1:
            return []  # 開催なし・まだ出ていない
        for waku, nm, c in boats:
            kyu, no, nm = _meta(jo, day, race, waku, nm)
            if c:
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "kisha", "記者コメント", c))
    return rows


# ---- 宮島（トップページが読み込む kaisai_reload.php の「選手コメント」） ----------------------------
def post(jo, url, data, label=""):
    """POST で読む（宮島）。403/404 は空。通信の失敗は3回まで取り直す"""
    host = SITES[jo]["host"]
    for attempt in range(3):
        try:
            r = SESSION.post(url, data=data, timeout=30, headers={"Referer": host + "/"})
            time.sleep(WAIT)
            if r.status_code in (403, 404):
                return ""
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except requests.RequestException as e:
            log(f"{JO_NAME[jo]} {label} 取得失敗({attempt + 1}回目): {e}")
            time.sleep(10)
    raise RuntimeError(f"{JO_NAME[jo]} {label} が取れない")


def parse_miyajima(text):
    """宮島 race_common/require/kaisai_reload.php（POST race・date）の返事を「####」で分けた28番目（dt[27]）が
    トップページの「選手コメント」タブ → [(枠, 登録番号, 級別, 選手名, コメント)]。末尾の「13:32更新」は外す。
    2・4号艇など色の濃い枠は class 名の後ろに「_white」が付く"""
    parts = text.split("####")
    if len(parts) < 28:
        return []
    out = []
    for tr in re.findall(r"<tr.*?</tr>", parts[27], re.S):
        w = re.search(r'class="wakuban(?:_white)?">\s*(\d)\s*<', tr)
        no = re.search(r"toban=(\d+)", tr)
        nm = re.search(r'class="player_name(?:_white)?">(.*?)</p>', tr, re.S)
        kyu = re.search(r'class="player_number(?:_white)?">\s*([AB][12])/', tr)
        c = re.search(r'class="table_txt_comment">(.*?)(?:<br\s*/?>|</p>)', tr, re.S)
        if w and no:
            out.append((int(w.group(1)), no.group(1), kyu.group(1) if kyu else "", _name(nm.group(1)) if nm else "",
                        _text(c.group(1)) if c else ""))
    return out


def fetch_miyajima(jo, day):
    """2026/11/21 追加（ユーザーの指摘で見つけた。HTML の出走表・PDF には無く、トップページのタブにだけある）。
    日付を指定できるので過去の日も取れる（9/20 で確認）。区分は「前日」とする（更新時刻の付く艇もあるが、いつの言葉かは分からない）"""
    rows = []
    url = f"{SITES[jo]['host']}/race_common/require/kaisai_reload.php"
    for race in range(1, 13):
        boats = parse_miyajima(post(jo, url, {"race": race, "date": day}, f"{day} {race}R"))
        if not any(c for *_, c in boats) and race == 1:
            return []  # 開催なし・まだ出ていない
        for waku, no, kyu, nm, c in boats:
            if c:
                rows.append(_row(day, jo, race, waku, kyu, no, nm, "comment", "前日", c))
    return rows


# ---- 戸田（トップページの出走表の「記者寸評」。日付とレースごとの XML） ------------------------------
def parse_toda(text):
    """戸田 /xml/kaisai/YYYYMMDD/race_table_comment_RR.xml → [(枠, 登録番号, 寸評)]"""
    out = []
    for rec in re.findall(r"<record>(.*?)</record>", text, re.S):
        w = re.search(r"<teiban>\s*(\d)\s*</teiban>", rec)
        no = re.search(r"<toban>\s*(\d+)\s*</toban>", rec)
        c = re.search(r"<comment>(.*?)</comment>", rec, re.S)
        if w:
            out.append((int(w.group(1)), no.group(1) if no else "", _text(c.group(1)) if c else ""))
    return out


def fetch_toda(jo, day):
    """2026/11/21 追加（ユーザーの指示で調べ直して見つけた）。トップページの racer_comment.js が読む XML。
    コードに「記者寸評の表示」とあり、記者の文なので記者情報「記者寸評」。開催日の朝10時ごろ出る（ページの案内）。
    日付を指定できるので過去の日も取れる（11/1 で確認）"""
    rows = []
    for race in range(1, 13):
        text = get(jo, f"{SITES[jo]['host']}/xml/kaisai/{day}/race_table_comment_{race:02d}.xml", label=f"{day} {race}R")
        boats = parse_toda(text)
        if not any(c for *_, c in boats) and race == 1:
            return []  # 開催なし・まだ出ていない
        for waku, no, c in boats:
            kyu, no2, nm = _meta(jo, day, race, waku, "")
            if c:
                rows.append(_row(day, jo, race, waku, kyu, no or no2, nm, "kisha", "記者寸評", c))
    return rows


# ---- 唐津（全選手コメント。1日1ページ） ---------------------------------------------
def parse_karatsu(text):
    """唐津 /sp/index.php?page=raceinfo-racers_comment&day=日付 → {登録番号: (級別, 選手名, 前日の文, 直前の文)}。
    zComment＝前日、cComment＝直前（末尾の「（12：27現在）」は外す）。どちらも選手の言葉。
    同じ欄のモーター評価（出足・伸び足の記号の画像・素性）は記号の意味が分からないので取らない"""
    out = {}
    for row in re.findall(r"<tr>\s*<td class='col1'>(.*?)</tr>", text, re.S):
        tk = re.search(r"class='toban-kyu[^']*'>\s*(\d{4})\s*/\s*([AB][12])\s*</span>\s*<br\s*/?>(.*?)</td>", row, re.S)
        if not tk:
            continue
        zen = re.search(r"<p class='zComment'>(.*?)</p>", row, re.S)
        cho = re.search(r"<p class='cComment[^']*'>(.*?)</p>", row, re.S)
        c = _text(cho.group(1)) if cho else ""
        c = re.sub(r"\s*[（(]\s*\d{1,2}\s*[：:]\s*\d{2}\s*現在\s*[）)]\s*$", "", c)
        out[tk.group(1)] = (tk.group(2), _name(tk.group(3)), _text(zen.group(1)) if zen else "", c)
    return out


def fetch_karatsu(jo, day):
    races = sorted(r for (j, r) in timetable(day) if j == jo)
    if not races:
        return []
    text = get(jo, f"{SITES[jo]['host']}/sp/index.php", {"page": "raceinfo-racers_comment", "day": day}, f"{day} 全選手コメント")
    com = parse_karatsu(text)
    if not any(z or c for _, _, z, c in com.values()):
        return []
    rows = []
    for race in races:
        for waku, (no, kyu, nm) in sorted(timetable(day)[(jo, race)].items(), key=lambda x: int(x[0])):
            if no not in com:
                continue
            kyu2, nm2, zen, cho = com[no]
            for tag, txt in (("前日", zen), ("直前", cho)):
                rows += tag_rows(day, jo, race, int(waku), kyu2 or kyu, no, nm2, tag, txt)
    return rows


# ---- 蒲郡（ピットの声＝日ごとの JS、目展示評価・耳より情報＝予想のページ） ----------
def parse_gamagori_js(text):
    """comment<日付>07.js → {"前日": {登録番号: 文}, "当日": {…}}。当日New は取らない（タイプの意味が分からないため）"""
    out = {"前日": {}, "当日": {}}
    for sec in text.split("function ")[1:]:
        key = "前日" if sec.startswith("funcBeforeComment") else "当日" if sec.startswith("funcToDayComment(") or sec.startswith("funcToDayComment ") else None
        if not key:
            continue
        for no, c in re.findall(r"strTouban === '(\d+)'\)\{\s*strComment = '((?:[^'\\]|\\.)*)';", sec):
            c = _text(c.replace("\\'", "'"))
            if c:
                out[key][no] = c
    return out


def parse_gamagori_eval(text):
    """予想のページ → [(区分, 枠, 文)]。艇番の画像（taka_NS.png）のあとの文をその艇のものとする"""
    out = []
    for div, kubun in (("hyoka", "目展示評価"), ("joho", "耳より情報")):
        m = re.search(rf'<div id="{div}">.*?<p>(.*?)</p>', text, re.S)
        if not m:
            continue
        parts = re.split(r"<img[^>]*taka_(\d)S\.png[^>]*>", m.group(1))
        for k in range(1, len(parts) - 1, 2):
            t = re.sub(r"\s+", " ", _text(re.sub(r"<br\s*/?>", " ", parts[k + 1])))  # 改行で言葉がくっつかないよう空白に
            if t:
                out.append((kubun, int(parts[k]), t))
    return out


def fetch_gamagori(jo, day):
    host = SITES[jo]["host"]
    js = get(jo, f"{host}/asp/gamagori/kyogi/kyogihtml/js/comment{day}{jo}.js", label=f"{day} コメントJS")
    races = sorted(r for (j, r) in timetable(day) if j == jo)
    if not js or not races:
        return []
    com = parse_gamagori_js(js)
    rows = []
    for race in races:
        for waku, (no, kyu, nm) in sorted(timetable(day)[(jo, race)].items(), key=lambda x: int(x[0])):
            for kubun in ("前日", "当日"):
                if com[kubun].get(no):
                    rows.append(_row(day, jo, race, int(waku), kyu, no, re.sub(r"\s+", "", nm), "comment", kubun, com[kubun][no]))
        page = get(jo, f"{host}/asp/gamagori/sp/kyogi/kyogihtml/recomend/recomend{day}{jo}{race:02d}.htm", label=f"{day} {race}R 予想")
        for kubun, waku, t in parse_gamagori_eval(page):
            kyu, no, nm = _meta(jo, day, race, waku, "")
            rows.append(_row(day, jo, race, waku, kyu, no, nm, "kisha", kubun, t))
    return rows


FETCH = {"jlc": fetch_jlc, "edogawa": fetch_edogawa, "tokoname": fetch_tokoname, "gamagori": fetch_gamagori, "wakamatsu": fetch_wakamatsu,
         "amagasaki": fetch_wakamatsu, "omura": fetch_omura, "karatsu": fetch_karatsu, "heiwajima": fetch_heiwajima,
         "kojima": fetch_kojima, "fukuoka": fetch_fukuoka, "kiryu": fetch_kiryu, "miyajima": fetch_miyajima, "toda": fetch_toda}


# ---- 保存 ------------------------------------------------------------------
def folder(jo, k):
    return KINDS[k]["root"] / JO_NAME[jo]


def day_path(jo, k, day):
    return folder(jo, k) / f"{KINDS[k]['prefix']}_{jo}_{day}.csv"


def save(jo, day, rows):
    for k in SITES[jo]["kinds"]:
        part = [r for r in rows if r["kind"] == k]
        if not part:
            continue
        folder(jo, k).mkdir(parents=True, exist_ok=True)
        col = KINDS[k]["col"]
        with open(day_path(jo, k, day), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns(k))
            w.writeheader()
            for r in part:
                w.writerow({**{c: r[c] for c in BASE_COLS}, col: r["本文"]})


def rebuild_summary(jo):
    for k in SITES[jo]["kinds"]:
        fd = folder(jo, k)
        if not fd.exists():
            continue
        files = sorted(fd.glob(f"{KINDS[k]['prefix']}_{jo}_*.csv"))
        with open(fd / "まとめ.csv", "w", encoding="utf-8-sig", newline="") as out:
            w = csv.DictWriter(out, fieldnames=columns(k))
            w.writeheader()
            for p in files:
                with open(p, encoding="utf-8-sig") as f:
                    w.writerows(csv.DictReader(f))
        log(f"{JO_NAME[jo]} {KINDS[k]['col']} まとめ.csv 作り直し（{len(files)}日分）")


def keep_groups(jo, mt, latest):
    """残す節（進行中の節＋過去 KEEP_PAST 節）"""
    groups = mt.get(jo, [])
    if not groups:
        return []
    ongoing = groups[-1][-1] >= latest
    return groups[-(KEEP_PAST + (1 if ongoing else 0)):]


def run(jo, day, force):
    today = date.today().strftime("%Y%m%d")
    if day > today:
        return False
    if not force and day < today and any(day_path(jo, k, day).exists() for k in SITES[jo]["kinds"]):
        return False
    rows = FETCH[SITES[jo]["type"]](jo, day)
    if not rows:
        log(f"{JO_NAME[jo]} {day} なし（開催なし・まだ出ていない）")
        return False
    save(jo, day, rows)
    for k in SITES[jo]["kinds"]:
        part = [r for r in rows if r["kind"] == k]
        if not part:
            log(f"{JO_NAME[jo]} {day} {KINDS[k]['col']} なし（この日はその欄が空）")
            continue
        kubun = {}
        for r in part:
            kubun[r["区分"]] = kubun.get(r["区分"], 0) + 1
        log(f"{JO_NAME[jo]} {day} {KINDS[k]['col']} 保存: {len({r['レース'] for r in part})}R {len(part)}件 {kubun}"
            f"（登録番号なし {sum(1 for r in part if not r['登録番号'])}件）")
    return True


def main(argv):
    global WAIT
    force = "--force" in argv
    jos = sorted(SITES)
    if "--jo" in argv:
        jos = [j.zfill(2) for j in argv[argv.index("--jo") + 1].split(",") if j.zfill(2) in SITES]
    if "--wait" in argv:
        WAIT = float(argv[argv.index("--wait") + 1])
    skip = {argv[argv.index(o) + 1] for o in ("--jo", "--wait") if o in argv}
    args = [a for a in argv if not a.startswith("--") and a not in skip]
    mode = args[0] if args else "auto"

    if mode not in ("auto", "show"):
        for jo in jos:
            if run(jo, mode, force):
                rebuild_summary(jo)
        return

    mt, latest = meetings()
    for jo in jos:
        groups = keep_groups(jo, mt, latest)
        if mode == "show":
            print(JO_NAME[jo], " / ".join(f"{g[0]}〜{g[-1]}({len(g)}日)" for g in groups))
            continue
        keep = [d for g in groups for d in g]
        changed = False
        for d in keep:
            try:
                changed |= run(jo, d, force)
            except RuntimeError as e:
                log(f"{JO_NAME[jo]} {d} 失敗: {e}")
        if keep and DELETE_OLD:
            keep_set = set(keep)
            for k in SITES[jo]["kinds"]:
                fd = folder(jo, k)
                if not fd.exists():
                    continue
                for fp in fd.glob(f"{KINDS[k]['prefix']}_{jo}_*.csv"):
                    if fp.stem[-8:] not in keep_set:
                        fp.unlink()
                        log(f"{JO_NAME[jo]} {fp.stem[-8:]} 古い節なので削除（{KINDS[k]['col']}）")
                        changed = True
        if changed or any(folder(jo, k).exists() and not (folder(jo, k) / "まとめ.csv").exists() for k in SITES[jo]["kinds"]):
            rebuild_summary(jo)


if __name__ == "__main__":
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main(sys.argv[1:])
    except Exception as e:
        log(f"エラーで終了: {type(e).__name__}: {e}")
        raise
