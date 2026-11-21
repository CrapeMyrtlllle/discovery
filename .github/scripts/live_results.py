r"""
当日の競走成績の速報を、ボートキャスト（race.boatcast.jp）から取って JSON にする

日中（パソコンが切れていても）GitHub Actions が15分おきに動かし、Discovery の Pages リポジトリの
live/ に置く。各ページ（番組表・Boat Board・タイムライン・AI予想・トップ）は開いたときにこれを読んで、
終わったレースの結果を上に重ねて表示する。夜の自前の競走成績（mbrace の K ファイル）は今までどおりで、
こちらは「その日の夜に正式な競走成績が入るまでの速報」。数字の定義は自前の競走成績CSVの列に合わせる。

使い方:
    python live_results.py --out <Pagesリポジトリの場所>            # 今日（日本時間）の分
    python live_results.py --out <場所> --date 20261118             # 日付を指定
    python live_results.py --check 20261118 --csv <results_YYYYMMDD.csv>   # 自前の競走成績CSVと突き合わせ

Python の標準の部品だけで動く（GitHub Actions で pip がいらないように）。

取る場所（race.boatcast.jp。1件ずつ順に、間を WAIT 秒あける）
  api_txt/getHoldingList2_日付.json … その日の開催場・各レースの締切・中止の状態
  m_txt/場/bc_rc1_日付_場.txt      … 場ごとに各レースの3連単・2連単（結果が出たレースだけ埋まる）
  txt/場/bc_rs1_日付_場_R.txt       … 着順・艇番・選手名・レースタイム・各艇のST・決まり手・進入・天候・風・波
  m_txt/場/bc_rs2_日付_場_R.txt     … 払戻（2連単・2連複・3連単・3連複・拡連複・単勝・複勝）と人気
  1回の実行で取るのは、場ごとの bc_rc1 と、新しく結果が出たレースの bc_rs1・bc_rs2 だけ

書き出し（--out の下）
  live/results_YYYYMMDD.json … {date, updated, venues: {場コード: {name, grade, title, day, nighter,
        deadlines[12], races: {R: レース}}}}
    レース = {status: "確定"|"中止"|"不成立", order: [[着, 艇番, 選手名, タイム], ...（着順の行の順）],
              st: {艇番: "0.15"|"F0.01"|"L"…}, course: [進入コース1〜6の艇番], kimarite, weather, wind_dir,
              wind (m), wave (cm), pay: {tan, fuku, 2t, 2f, kaku, 3t, 3f}, henkan: [返還艇]}
      pay の各券種 = [[組番, 払戻金(円・整数), 人気], ...]（同着で2つ以上のことがある。単勝・複勝は人気なし）
  live/latest.json … {date, updated, file}（各ページはまずこれを読む）

直前情報（2026/11/19 追加）
  hp_txt/場/bc_j_tkz_日付_場_R.txt … 展示タイム・体重・調整重量・チルト・スタート展示（進入とST）。1レース1件
  取るのは締切の PRE_BEFORE 分前から（結果が出るまで、そろうまで毎回）と、結果が出たのにまだ無いレース（1回）
  results_YYYYMMDD.json の pre: {場コード: {R: {ex, wt, adj, tilt, sst}}}（parse_tkz の説明）。結果の races とは別
  実行の間隔は GitHub Actions の設定（10分おき）。締切に間に合わないレースもある

オリジナル展示（2026/11/21 追加。ユーザーの指示「直前情報みたいに取って番組表に反映」「速報は当日分だけ」）
  txt/場/bc_oriten_日付_場_R.txt … 艇番・選手名・計測値。見出しの行に区間名（場ごとに違う。fetch_oriten_bc.py と同じ読み方）
  取るのは今日の分だけ。直前情報の展示タイムが入ったレースから（展示が終わってから出るため。むだに取りに行かない）、
  6艇そろうまで毎回。結果が出たのにまだ無いレースは1回だけ。江戸川はファイル自体が無いので取らない
  results_YYYYMMDD.json の ori: {場コード: {R: {c: [区間名…], v: {艇: [値…]}}}}。今日でない日のファイルからは消す
  場によって測る区間が違うので、場をまたいで比べない（順位も付けない）。正式な記録は夜の fetch_oriten_bc.py（オリ展\）
"""

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BC = "https://race.boatcast.jp"
UA = {"User-Agent": "Mozilla/5.0 (Discovery live results)", "Referer": BC + "/"}
WAIT = 0.7
JST = timezone(timedelta(hours=9))

JO_NAME = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖",
    "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島", "17": "宮島", "18": "徳山",
    "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}
# 自前の競走成績CSVのレースコードの英字 → 場コード（fetch_oriten_bc.py と同じ）
JO_ABBR = {
    "KRY": "01", "TDA": "02", "EDG": "03", "HWJ": "04", "TMG": "05", "HMN": "06", "GMG": "07",
    "TKN": "08", "TSU": "09", "MKN": "10", "BWK": "11", "SME": "12", "AMG": "13", "NRT": "14",
    "MRG": "15", "KJM": "16", "MYJ": "17", "TKY": "18", "SMS": "19", "WKM": "20", "ASY": "21",
    "FKO": "22", "KRT": "23", "OMR": "24",
}

# 天候の表記を自前の競走成績CSVに合わせる
WEATHER = {"晴れ": "晴", "くもり": "曇り", "曇": "曇り"}

_last = [0.0]
_count = [0]


def get(path):
    """本文（UTF-8）を返す。403/404（ファイルなし）は None。通信の失敗は3回まで取り直す"""
    for attempt in range(3):
        wait = WAIT - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        _count[0] += 1
        try:
            req = urllib.request.Request(BC + path, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", errors="replace")
            if body.lstrip().startswith("<!doctype") or body.lstrip().startswith("<html"):
                return None  # エラーページ
            return body
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            err = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            err = e
        print(f"  取得失敗({attempt + 1}回目) {path}: {err}", flush=True)
        time.sleep(5)
    return None


def nfkc(s):
    return unicodedata.normalize("NFKC", s or "").strip()


def yen(s):
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else None


def lines_of(text):
    L = [ln.rstrip("\r") for ln in (text or "").split("\n")]
    if L and L[0].startswith("data="):
        L = L[1:]
    return L


# ---------- 読み取り ----------

def parse_rc1(text):
    """→ {R: True}（結果の行が埋まっているレース）"""
    out = {}
    for ln in lines_of(text):
        f = ln.split("\t")
        m = re.match(r"(\d+)R$", f[0].strip()) if f else None
        if m and len(f) > 4 and any(x.strip() for x in f[1:5]):
            out[int(m.group(1))] = True
    return out


def parse_st(s):
    """".15" → "0.15"、"F.01" → "F0.01"、"L" → "L"、空 → "" """
    s = nfkc(s).replace(" ", "")
    if not s:
        return ""
    m = re.match(r"^([FL]?)(\d*)\.(\d+)$", s)
    if m:
        return f"{m.group(1)}{m.group(2) or '0'}.{m.group(3)}"
    return s


def parse_rs1(text):
    """着順・ST・決まり手・進入・天候。読めなければ None"""
    L = lines_of(text)
    if len(L) < 15:
        return None
    order = []
    for ln in L[1:7]:
        f = ln.split("\t")
        if len(f) < 3:
            return None
        order.append([nfkc(f[0]), int(nfkc(f[1])) if nfkc(f[1]).isdigit() else nfkc(f[1]),
                      f[2].strip(), nfkc(f[3]) if len(f) > 3 else ""])
    # ST の6行は進入の順（上から1コース）。1列目が艇番。11/18 の全120レースで自前の競走成績の進入コースと一致を確認
    st, kimarite, course = {}, "", []
    for ln in L[7:13]:
        f = ln.split("\t")
        if not f or not nfkc(f[0]).isdigit():
            continue
        course.append(int(nfkc(f[0])))
        st[nfkc(f[0])] = parse_st(f[1] if len(f) > 1 else "")
        if len(f) > 3 and nfkc(f[3]):
            kimarite = nfkc(f[3]).replace(" ", "")
    w = [nfkc(x) for x in L[14].split("\t")] if len(L) > 14 else []
    weather = (w[0] if len(w) > 0 else "").replace(" ", "")
    weather = WEATHER.get(weather, weather)
    wind = re.sub(r"[^\d.]", "", w[1]) if len(w) > 1 else ""
    wave = re.sub(r"[^\d.]", "", w[2]) if len(w) > 2 else ""
    wind_dir = (w[3] if len(w) > 3 else "").replace(" ", "")
    return {"status_rs1": nfkc(L[0]), "order": order, "st": st, "course": course, "kimarite": kimarite,
            "weather": weather, "wind": int(wind) if wind.isdigit() else wind,
            "wave": int(wave) if wave.isdigit() else wave, "wind_dir": wind_dir}


def parse_tkz(text):
    """直前情報（hp_txt/場/bc_j_tkz_日付_場_R.txt）。艇番の順に6行（選手名・展示タイム・?・調整重量(0.1kg)・体重・?・チルト…）と、
    最後の行にスタート展示（コースの順に 艇番・ST・F）。展示タイムは 11/18 徳山1R で自前の競走成績と一致を確認。
    体重は番組表の体重とほぼ一致（当日の計量）。調整重量は女子の 47kg に合わせた形で確認。チルトは照合先が無く未照合
    → {ex: {艇: "6.74"}, wt: {艇: 47.0}, adj: {艇: 1.5}, tilt: {艇: "-0.5"}, sst: [[艇, "0.05", "F"|""], ...（コースの順）]}"""
    L = [ln.rstrip("\r") for ln in lines_of(text)]
    rows = [ln.split("\t") for ln in L[1:7]] if len(L) >= 7 else []
    if len(rows) < 6:
        return None
    out = {"nm": {}, "ex": {}, "wt": {}, "adj": {}, "tilt": {}, "sst": []}
    for w, f in enumerate(rows, 1):
        k = str(w)
        nm = re.sub(r"[\s　]+", " ", (f[0] if f else "").strip())   # 「安井　　瑞紀」→「安井 瑞紀」
        if nm:
            out["nm"][k] = nm
        ex = nfkc(f[1]) if len(f) > 1 else ""
        if re.match(r"^\d\.\d\d$", ex):
            out["ex"][k] = ex
        wt = nfkc(f[4]) if len(f) > 4 else ""
        if re.match(r"^\d+(\.\d)?$", wt):
            out["wt"][k] = float(wt)
        adj = nfkc(f[3]) if len(f) > 3 else ""
        if adj.isdigit() and int(adj) > 0:
            out["adj"][k] = int(adj) / 10
        tl = nfkc(f[6]).replace(" ", "") if len(f) > 6 else ""
        if re.match(r"^[+-]?\d+(\.\d)?$", tl):
            out["tilt"][k] = tl
    last = [nfkc(x) for x in L[7].split("\t")] if len(L) > 7 else []
    for i in range(0, len(last) - 1, 3):   # 艇番・ST・F の3つずつ
        b, s = last[i], last[i + 1] if i + 1 < len(last) else ""
        if b.isdigit() and s:
            out["sst"].append([int(b), parse_st(s), (last[i + 2] if i + 2 < len(last) else "").strip()])
    return out if out["ex"] else None


SUI_WEATHER = {"1": "晴", "2": "曇り", "3": "雨", "4": "雪", "5": "台風", "6": "霧"}   # ボートキャストの番号（useWeather.js）→ 自前の競走成績の表記


ORI_KUKAN = {"一周": "一周", "半周ラップ": "半周", "半周": "半周", "まわり足": "まわり足", "周り足": "まわり足", "直線": "直線"}
NO_ORITEN = {"03"}   # 江戸川はオリ展のファイルが無い（fetch_oriten_bc.py と同じ）
TAB = chr(9)


def parse_oriten(text):
    """オリジナル展示（txt/場/bc_oriten_日付_場_R.txt）。3行目が見出し（区間名だけ）、4行目から1艇1行（艇番・選手名・区間ごとの値）。
    区間名は fetch_oriten_bc.py と同じ名前にそろえる（一周・半周・まわり足・直線。それ以外は見出しのまま）。
    「-」「.」だけの欄は空 → {c: [区間名…], v: {艇: [値…]}}。値が1つも無ければ None"""
    L = lines_of(text)
    if len(L) < 3:
        return None
    heads = [nfkc(h).replace(" ", "") for h in L[1].split(TAB)]
    cols = [ORI_KUKAN.get(h, h) for h in heads]
    out = {"c": cols, "v": {}}
    for ln in L[2:]:
        c = [x.strip() for x in ln.split(TAB)]
        if len(c) < 2 or not re.fullmatch(r"[1-6]", nfkc(c[0])):
            continue
        vals = [nfkc(x) for x in c[2:2 + len(cols)]]
        vals = ["" if (not x or set(x) <= set("-.")) else x for x in vals]
        if any(vals):
            out["v"][nfkc(c[0])] = vals
    keep = [i for i, h in enumerate(cols) if h and any(i < len(v) and v[i] for v in out["v"].values())]
    if not keep:
        return None
    out["c"] = [cols[i] for i in keep]
    out["v"] = {k: [v[i] if i < len(v) else "" for i in keep] for k, v in out["v"].items()}
    return out


def parse_sui(text):
    """水面気象（m_txt/場/bc_sui_日付_場.txt。場ごとにいちばん新しい観測）。例: 1816 1 6 西　　(向い風) 6 +11.0 +21.0 …
    → {time: "18:16", weather: "晴", wave: 6, wind_dir: "西", wind_type: "向い風", wind: 6, temp: 11.0, water: 21.0}
    11/19 丸亀 18:16 の観測で、公式の水面気象情報（ユーザーの画面）と全項目一致"""
    f = [x.strip() for x in lines_of(text)[0].split("\t")] if text and lines_of(text) else []
    if len(f) < 7 or not re.match(r"^\d{4}$", f[0]):
        return None
    num = lambda s: float(s.replace("+", "")) if re.match(r"^[+-]?\d+(\.\d+)?$", s or "") else None   # noqa: E731
    wd = f[3].replace("　", " ")
    m = re.match(r"^\s*([^(（\s]*)\s*[(（]?([^)）]*)[)）]?", wd)
    out = {"time": f"{f[0][:2]}:{f[0][2:]}", "weather": SUI_WEATHER.get(f[1], ""), "wave": num(f[2]),
           "wind_dir": (m.group(1) if m else "").strip(), "wind_type": (m.group(2) if m else "").strip(),
           "wind": num(f[4]), "temp": num(f[5]), "water": num(f[6])}
    for k in ("wave", "wind"):
        if out[k] is not None and out[k] == int(out[k]):
            out[k] = int(out[k])
    return out


def pre_complete(p):
    return bool(p and len(p.get("ex", {})) == 6 and len(p.get("sst", [])) == 6)


def blocks_of(text):
    """空行で区切ったかたまり（m_txt の bc_rs2）"""
    out, cur = [], []
    for ln in lines_of(text):
        if ln.strip():
            cur.append(ln.split("\t"))
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _combo(f, n, sep):
    boats = [nfkc(x) for x in f if nfkc(x).isdigit()][:n]
    return sep.join(boats)


def parse_rs2(text):
    """払戻。かたまりの順：状態＋2連単（同じかたまり）／2連複／3連単／3連複／拡連複（3行）／単勝／複勝"""
    B = blocks_of(text)
    if not B:
        return None
    head = [nfkc(x) for x in B[0][0]]
    status = head[0] if head else ""
    henkan = []
    rest = [B[0][1:]] + B[1:]
    pay = {"2t": [], "2f": [], "3t": [], "3f": [], "kaku": [], "tan": [], "fuku": []}

    def rows(block, n, sep):
        out = []
        for f in block:
            g = [x.strip() for x in f]
            # 例: 2 - 1 2,930 円 10 ／ 2 1 4 10,570 円 39 ／ 1 = 2 200 円 2
            nums = [x for x in g if x]
            if "円" not in nums:
                continue
            i = nums.index("円")
            combo = _combo(nums[:i - 1], n, sep)
            amount = yen(nums[i - 1])
            pop = yen(nums[i + 1]) if len(nums) > i + 1 else None
            if combo:
                out.append([combo, amount, pop])
        return out

    names = [("2t", 2, "-"), ("2f", 2, "="), ("3t", 3, "-"), ("3f", 3, "="), ("kaku", 2, "=")]
    k = 0
    for key, n, sep in names:
        if k >= len(rest):
            break
        pay[key] = rows(rest[k], n, sep)
        k += 1
    # 単勝・複勝: 「艇 金額 円」（人気なし）
    for key in ["tan", "fuku"]:
        if k >= len(rest):
            break
        out = []
        for f in rest[k]:
            nums = [x.strip() for x in f if x.strip()]
            if "円" in nums:
                i = nums.index("円")
                if i >= 2 and nfkc(nums[0]).isdigit():
                    out.append([nfkc(nums[0]), yen(nums[i - 1]), None])
        pay[key] = out
        k += 1
    return {"status_rs2": status, "henkan_flag": head[1] if len(head) > 1 else "", "pay": pay, "henkan": henkan}


# ---------- 1日分を作る ----------

def load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


PRE_BEFORE = 25   # 締切のこの分数前から、直前情報を取りに行く（展示は締切の十数分前に出る）


def fetch_pre(data, ymd, jo, ve, races, cancel):
    """直前情報を取る → 取ったレース数。取るのは (1) 締切 PRE_BEFORE 分前〜結果が出るまでで、まだそろっていないレース
    (2) 結果が出たのに直前情報が無いレース（1回だけ）。中止は取らない。日付が今日でないときは (2) だけ"""
    pre = data.setdefault("pre", {}).setdefault(jo, {})
    now = datetime.now(JST)
    today = now.strftime("%Y%m%d") == ymd
    dls = ve.get("deadlines") or []
    n = 0
    # 水面気象: 今日で、まだ結果の出ていない（中止でない）レースがある場だけ、毎回1件
    left = [r for r in range(1, 13) if not (races.get(str(r)) or {}).get("status")
            and not ((cancel[r - 1] if r - 1 < len(cancel) else "") and "中止" in cancel[r - 1])]
    if today and left:
        wx = parse_sui(get(f"/m_txt/{jo}/bc_sui_{ymd}_{jo}.txt"))
        n += 1
        if wx:
            ve["wx"] = wx
    for rno in range(1, 13):
        key = str(rno)
        c = cancel[rno - 1] if rno - 1 < len(cancel) else ""
        if (c and "中止" in c) or pre_complete(pre.get(key)):
            continue
        res = races.get(key)
        if res and res.get("status"):
            if key in pre or res.get("status") != "確定":
                continue   # 結果が出たあとは取り直さない（取れていた分はそのまま）
        else:
            dl = dls[rno - 1] if rno - 1 < len(dls) else ""
            if not today or not re.match(r"^\d\d:\d\d$", dl or ""):
                continue
            mins = (int(dl[:2]) * 60 + int(dl[3:])) - (now.hour * 60 + now.minute)
            if mins > PRE_BEFORE:
                continue
        p = parse_tkz(get(f"/hp_txt/{jo}/bc_j_tkz_{ymd}_{jo}_{rno:02d}.txt"))
        n += 1
        pre[key] = p or pre.get(key) or {}   # 取れなくても印を残す（結果が出たあとに取り直し続けないため）
    if today and jo not in NO_ORITEN:
        n += fetch_ori(data, ymd, jo, races, cancel)
    return n


def fetch_ori(data, ymd, jo, races, cancel):
    """オリジナル展示を取る（今日だけ）→ 取った件数。直前情報の展示タイムが入ったレースだけ、6艇そろうまで毎回。
    結果が出たあとは、まだ取っていないレースを1回だけ"""
    pre = (data.get("pre") or {}).get(jo) or {}
    ori = data.setdefault("ori", {}).setdefault(jo, {})
    n = 0
    for rno in range(1, 13):
        key = str(rno)
        c = cancel[rno - 1] if rno - 1 < len(cancel) else ""
        if (c and "中止" in c) or not (pre.get(key) or {}).get("ex"):
            continue
        o = ori.get(key) or {}
        if len(o.get("v", {})) >= 6:
            continue
        res = races.get(key)
        if res and res.get("status") and key in ori:
            continue   # 結果が出たあとは取り直さない
        got = parse_oriten(get(f"/txt/{jo}/bc_oriten_{ymd}_{jo}_{rno:02d}.txt"))
        n += 1
        ori[key] = got or o   # 取れなくても印を残す
    if not ori:
        data["ori"].pop(jo, None)
    if not data["ori"]:
        data.pop("ori")
    return n


def build(ymd, prev=None, max_new=400):
    hold = get(f"/api_txt/getHoldingList2_{ymd}.json")
    try:
        info = json.loads(hold)["return_info"] if hold else []
    except (ValueError, KeyError):
        info = []
    data = prev if (prev and prev.get("date") == ymd) else {"date": ymd, "venues": {}}
    venues = data.setdefault("venues", {})
    new = 0
    for v in info:
        jo = v.get("RaceStudiumNo", "").zfill(2)
        if jo not in JO_NAME:
            continue
        ve = venues.setdefault(jo, {"name": JO_NAME[jo], "races": {}})
        ve.update({"grade": v.get("RaceGrade", ""), "title": nfkc(v.get("HoldingTitle", "")),
                   "day": nfkc(v.get("DailyTitle", "")), "nighter": v.get("NighterFlag", "") == "Y",
                   "deadlines": v.get("DeadlineTimeAll", []), "cancel": v.get("CancelStatusAll", [])})
        races = ve.setdefault("races", {})
        rc1 = parse_rc1(get(f"/m_txt/{jo}/bc_rc1_{ymd}_{jo}.txt"))
        cancel = v.get("CancelStatusAll", []) or []
        for rno in range(1, 13):
            key = str(rno)
            c = cancel[rno - 1] if rno - 1 < len(cancel) else ""
            # 開催一覧で中止のレース（その場の開催の中止を含む）は取りに行かない。ボートキャストの払戻は「不成立・全艇返還」になる
            if c and "中止" in c:
                races[key] = {"status": "中止", "done": True}
                continue
            if not rc1.get(rno):
                continue
            if races.get(key, {}).get("status") in ("確定", "不成立", "中止") and races[key].get("done"):
                continue
            if new >= max_new:
                continue
            rs1 = parse_rs1(get(f"/txt/{jo}/bc_rs1_{ymd}_{jo}_{rno:02d}.txt"))
            rs2 = parse_rs2(get(f"/m_txt/{jo}/bc_rs2_{ymd}_{jo}_{rno:02d}.txt"))
            new += 1
            if not rs1 and not rs2:
                continue
            r = {}
            if rs1:
                r.update({k: rs1[k] for k in ["order", "st", "course", "kimarite", "weather", "wind_dir", "wind", "wave"]})
            if rs2:
                r["pay"] = rs2["pay"]
            st2 = rs2["status_rs2"] if rs2 else ""
            if st2 == "3":
                r["status"] = "中止"
            elif rs2 and not rs2["pay"]["3t"]:
                r["status"] = "不成立"
            else:
                r["status"] = "確定"
            # 返還艇: 着順の欄が数字でない艇（欠場・失格などの記号）のうち、欠場（返還）のもの
            r["henkan"] = [o[1] for o in r.get("order", []) if o[0] in ("欠", "K", "K0", "K1")]
            # 済み＝もう取り直さない。確定は着順と3連単がそろったとき（終わった直後は着順のファイルがまだ無いことがある）
            r["done"] = bool(r["status"] in ("中止", "不成立") or (rs1 and r["order"] and r.get("pay", {}).get("3t")))
            races[key] = r
        # 直前情報（展示タイム・体重・チルト・スタート展示）。結果（races）とは別の pre に置く
        new += fetch_pre(data, ymd, jo, ve, races, cancel)
    data["updated"] = datetime.now(JST).isoformat(timespec="seconds")
    return data, new


def write(out_dir, data):
    d = Path(out_dir) / "live"
    d.mkdir(parents=True, exist_ok=True)
    name = f"results_{data['date']}.json"
    today = datetime.now(JST).strftime("%Y%m%d")
    if data["date"] != today:
        data.pop("ori", None)   # オリ展の速報は当日分だけ
    (d / name).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (d / "latest.json").write_text(json.dumps({"date": data["date"], "updated": data["updated"], "file": name},
                                              ensure_ascii=False), encoding="utf-8")
    # 7日より古い速報は消す（正式な競走成績は夜にそろうので、速報は数日で足りる）
    limit = (datetime.strptime(data["date"], "%Y%m%d") - timedelta(days=7)).strftime("%Y%m%d")
    for p in d.glob("results_*.json"):
        m = re.match(r"results_(\d{8})\.json$", p.name)
        if m and m.group(1) < limit:
            p.unlink()
        elif m and m.group(1) != today and p.name != name:
            # オリ展の速報は当日分だけ（2026/11/21 ユーザーの指示）。前の日のファイルからは消す
            old = load_json(p)
            if old and "ori" in old:
                old.pop("ori")
                p.write_text(json.dumps(old, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return d / name


# ---------- 自前の競走成績CSVとの突き合わせ ----------

def check(ymd, csv_path, data=None):
    data = data or build(ymd)[0]
    rows = list(csv.DictReader(open(csv_path, encoding="cp932")))
    n = bad = 0
    diffs = {}

    def diff(kind, code, a, b):
        diffs.setdefault(kind, []).append(f"{code}: 速報={a} / CSV={b}")

    for row in rows:
        code = row["レースコード"]
        jo = JO_ABBR.get(code[8:11])
        rno = str(int(code[11:13]))
        r = data["venues"].get(jo, {}).get("races", {}).get(rno)
        if not r:
            diff("速報に無いレース", code, "-", row["決まり手"])
            continue
        n += 1
        before = sum(len(v) for v in diffs.values())
        # 着順（着の欄・艇番）とST・進入
        for i in range(1, 7):
            boat = row.get(f"{i}着_艇番", "").strip()
            if not boat:
                continue
            # 着の数字がある艇だけ並びを比べる（転覆・欠場などの艇の並びはCSVと速報で違う）
            o = r["order"][i - 1] if len(r.get("order", [])) >= i else None
            c_rank = nfkc(row.get(f"{i}着_着順", ""))
            if c_rank.isdigit() and (not o or str(o[1]) != str(int(boat)) or o[0] != str(int(c_rank))):
                diff("着順の艇番", code, o, f"{c_rank}着={boat}")
            if not c_rank.isdigit():
                ob = [x for x in r.get("order", []) if str(x[1]) == str(int(boat))]
                if not ob or ob[0][0].isdigit():
                    diff("着順の艇番", code, ob, f"{c_rank}={boat}")
            c_st = row.get(f"{i}着_スタートタイミング", "").strip()
            b_st = r.get("st", {}).get(str(int(boat)), "")
            if c_st not in ("", ".") and b_st.replace("F", "").replace("L", "") != c_st.replace("F", "").replace("L", ""):
                diff("ST", code, f"{boat}号艇 {b_st}", c_st)
            c_course = row.get(f"{i}着_進入コース", "").strip()
            if c_course.isdigit():
                bc = r.get("course", [])
                b_course = bc.index(int(boat)) + 1 if int(boat) in bc else None
                if b_course != int(c_course):
                    diff("進入コース", code, f"{boat}号艇 {b_course}", c_course)
        if nfkc(row["決まり手"]).replace(" ", "") != r.get("kimarite", ""):
            diff("決まり手", code, r.get("kimarite"), row["決まり手"])
        # 払戻
        pay = r.get("pay", {})
        for key, col in [("3t", "3連単"), ("3f", "3連複"), ("2t", "2連単"), ("2f", "2連複")]:
            c_combo = row[f"{col}_組番"].strip()
            if not c_combo:
                continue
            b = pay.get(key, [])
            c_amt, c_pop = yen(row[f"{col}_払戻金"]), yen(row[f"{col}_人気"])
            hit = [x for x in b if x[0].replace("=", "-") == c_combo.replace("=", "-")]
            if not hit or hit[0][1] != c_amt or hit[0][2] != c_pop:
                diff(col, code, b, f"{c_combo} {c_amt} {c_pop}")
        for j, col in enumerate(["拡連複_1-2着", "拡連複_1-3着", "拡連複_2-3着"]):
            c_combo = row[f"{col}_組番"].strip()
            if not c_combo:
                continue
            b = pay.get("kaku", [])
            hit = [x for x in b if x[0].replace("=", "-") == c_combo.replace("=", "-")]
            if not hit or hit[0][1] != yen(row[f"{col}_払戻金"]) or hit[0][2] != yen(row[f"{col}_人気"]):
                diff("拡連複", code, b, f"{c_combo} {row[f'{col}_払戻金']} {row[f'{col}_人気']}")
        if row["単勝_艇番"].strip():
            b = pay.get("tan", [])
            if not b or b[0][0] != str(int(row["単勝_艇番"])) or b[0][1] != yen(row["単勝_払戻金"]):
                diff("単勝", code, b, f"{row['単勝_艇番']} {row['単勝_払戻金']}")
        for j in (1, 2):
            boat = row[f"複勝_{j}着_艇番"].strip()
            if boat:
                b = [x for x in pay.get("fuku", []) if x[0] == str(int(boat))]
                if not b or b[0][1] != yen(row[f"複勝_{j}着_払戻金"]):
                    diff("複勝", code, pay.get("fuku"), f"{boat} {row[f'複勝_{j}着_払戻金']}")
        # 天候・風・波
        if nfkc(row["天候"]).replace(" ", "") != r.get("weather", ""):
            diff("天候", code, r.get("weather"), row["天候"])
        if str(row["風速(m)"]).strip() != str(r.get("wind", "")):
            diff("風速", code, r.get("wind"), row["風速(m)"])
        if str(row["波の高さ(cm)"]).strip() != str(r.get("wave", "")):
            diff("波高", code, r.get("wave"), row["波の高さ(cm)"])
        if sum(len(v) for v in diffs.values()) > before:
            bad += 1
    extra = sum(len(v["races"]) for v in data["venues"].values()) - n
    print(f"{ymd}: CSV {len(rows)} レース中 {n} レースを照合。違いのあったレース {bad}・速報だけにあるレース {extra}")
    for k, v in diffs.items():
        print(f"  [{k}] {len(v)} 件")
        for x in v[:5]:
            print("     ", x)
    return bad


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="Pages リポジトリの場所（live/ に書く）")
    ap.add_argument("--date", help="YYYYMMDD（省略時は日本時間の今日）")
    ap.add_argument("--check", metavar="YYYYMMDD", help="自前の競走成績CSVと突き合わせる日")
    ap.add_argument("--csv", help="--check で使う results_YYYYMMDD.csv")
    ap.add_argument("--save", help="--check で取った速報を書き出す場所（省略可）")
    a = ap.parse_args()
    t0 = time.time()
    if a.check:
        data, _ = build(a.check)
        if a.save:
            write(a.save, data)
        bad = check(a.check, a.csv, data)
        print(f"リクエスト {_count[0]} 件・{time.time() - t0:.0f} 秒")
        sys.exit(1 if bad else 0)
    ymd = a.date or datetime.now(JST).strftime("%Y%m%d")
    prev = load_json(Path(a.out) / "live" / f"results_{ymd}.json") if a.out else None
    before = json.dumps({k: v for k, v in (prev or {}).items() if k != "updated"}, ensure_ascii=False, sort_keys=True)
    data, new = build(ymd, json.loads(json.dumps(prev)) if prev else None)
    after = json.dumps({k: v for k, v in data.items() if k != "updated"}, ensure_ascii=False, sort_keys=True)
    if not data["venues"]:
        print(f"{ymd}: 開催の一覧が取れませんでした（開催なし・ボートキャストの不調）。書き出しません")
        return
    if before == after:
        print(f"{ymd}: 新しい結果なし（リクエスト {_count[0]} 件・{time.time() - t0:.0f} 秒）。書き出しません")
        return
    path = write(a.out, data) if a.out else None
    done = sum(1 for v in data["venues"].values() for r in v["races"].values() if r.get("status"))
    print(f"{ymd}: {len(data['venues'])} 場・結果 {done} レース（今回取得 {new}）・リクエスト {_count[0]} 件・"
          f"{time.time() - t0:.0f} 秒 → {path or '(書き出しなし)'}")


if __name__ == "__main__":
    main()
