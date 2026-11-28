// 買い続け試算: レースの月ファイル data/races/YYYY-MM.json を読む。
// 期間に入る月だけを並列で取り、取ったものはメモリに置いて2回目からは取り直さない。
// 「選手の1着流し」は選手の組ファイル data/players/NN.json だけを読む（loadPlayer。下のほう）。

const BASE = 'data/races/';

// ---------- 公開用の読み方（2026/11/26）----------
// 公開するデータは data_guard.py と同じ置き換えをした JSON の文字列（"…"）になっている。
// make_page.py が公開用の CONF（window.KT_CONF）に guard:1 と、ファイルごとの版 ver:{'data/races/2026-01.json':'…'} を入れる。
// guard のときは文字列を __dz（ページに入る data_guard.JS_DECODER）で戻してから JSON.parse する。手元版（guard なし）はそのまま読む。
function conf() {
  return (typeof globalThis !== 'undefined' && globalThis.KT_CONF) || {};
}
/** 版つきの URL（公開用。キャッシュで前の日のデータが出ないように） */
export function dataUrl(path) {
  const v = conf().ver && conf().ver[path];
  return v ? `${path}?v=${v}` : path;
}
/** 取ったファイルの中身（文字列）→ データ。guard なら置き換えを戻してから */
export function parseData(text, c = conf()) {
  if (!c.guard) return JSON.parse(text);
  const dz = globalThis.__dz;
  if (typeof dz !== 'function') throw new Error('データを戻す処理がありません');
  return JSON.parse(dz(JSON.parse(text)));
}
/** path のデータを取って読む（players.json 用。page.js から） */
export async function fetchData(path) {
  const res = await fetch(dataUrl(path));
  if (!res.ok) throw new Error(`${path} を読めませんでした（${res.status}）`);
  return parseData(await res.text());
}
const cache = new Map(); // 'YYYY-MM' -> Promise<race[]>

/** 計測用（最後の loadRaces の 取得・JSON.parse の時間 ms と月の数）。画面には出さない。 */
export const lastStats = { months: 0, fetched: 0, fetchMs: 0, parseMs: 0, expandMs: 0, totalMs: 0 };

// 月ファイルの軽い形（build_races.py の pack_month）を Task 1 のレースの形に戻す。
//   {v:1, ym, venues, grades, bets, races:[[日, 場の番号, R, グレードの番号|null, [[waku,toban,course,rank,refund01],…], [券種ごとの [組番,円,…]], void01], …]}
//   → {date, venue, rno, grade, boats:[{waku,toban,course,rank,refund}], pay:{tansho:[["1",130]],…}, void}
//   組番は艇番を並べた整数（124）→ 連単・単勝・複勝は "1-2-4"、連複は "1=2=4"。名前は入っていない（players.json）。
// 配列（前の形）はそのまま返す。
const SEP = { tansho: '-', fukusho: '-', nirentan: '-', nirenpuku: '=', sanrentan: '-', sanrenpuku: '=' };
const keyCache = { '-': new Map(), '=': new Map() }; // 区切り → (組番の整数 → 文字列)。同じ組番の文字列を使い回す
function keyStr(sep, n) {
  const cache = keyCache[sep];
  let s = cache.get(n);
  if (s === undefined) {
    s = String(n).split('').join(sep);
    cache.set(n, s);
  }
  return s;
}
export function expandMonth(obj) {
  if (Array.isArray(obj)) return obj;
  if (!obj || obj.v !== 1) throw new Error('月ファイルの形が分かりません');
  const { ym, venues, grades, bets } = obj;
  const seps = bets.map((b) => SEP[b] || '-');
  const days = [];
  for (let d = 1; d <= 31; d++) days.push(`${ym}-${String(d).padStart(2, '0')}`);
  const src = obj.races;
  const out = new Array(src.length);
  for (let i = 0; i < src.length; i++) {
    const [d, v, rno, g, bs, pay, vd] = src[i];
    const boats = new Array(bs.length);
    for (let j = 0; j < bs.length; j++) {
      const b = bs[j];
      boats[j] = { waku: b[0], toban: b[1], course: b[2], rank: b[3], refund: b[4] === 1 };
    }
    const p = {};
    for (let k = 0; k < bets.length; k++) {
      const flat = pay[k] || [];
      const arr = new Array(flat.length / 2);
      for (let m = 0; m < flat.length; m += 2) arr[m / 2] = [keyStr(seps[k], flat[m]), flat[m + 1]];
      p[bets[k]] = arr;
    }
    out[i] = { date: days[d - 1], venue: venues[v], rno, grade: g === null ? null : grades[g], boats, pay: p, void: vd === 1 };
  }
  return out;
}

/** from〜to（YYYY-MM-DD）に入る月の一覧 ['YYYY-MM', ...] */
export function monthsBetween(from, to) {
  const out = [];
  let y = Number(from.slice(0, 4));
  let m = Number(from.slice(5, 7));
  const ey = Number(to.slice(0, 4));
  const em = Number(to.slice(5, 7));
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    m += 1;
    if (m > 12) { m = 1; y += 1; }
  }
  return out;
}

function loadMonth(ym) {
  if (!cache.has(ym)) {
    const p = (async () => {
      const t0 = performance.now();
      const res = await fetch(dataUrl(`${BASE}${ym}.json`));
      if (!res.ok) throw new Error(`${ym} のデータを読めませんでした（${res.status}）`);
      const text = await res.text();
      const t1 = performance.now();
      const data = parseData(text);
      const t2 = performance.now();
      const races = expandMonth(data);
      const t3 = performance.now();
      lastStats.fetchMs += t1 - t0;
      lastStats.parseMs += t2 - t1;
      lastStats.expandMs += t3 - t2;
      lastStats.fetched += 1;
      return races;
    })();
    p.catch(() => cache.delete(ym)); // 失敗した月は次に取り直す
    cache.set(ym, p);
  }
  return cache.get(ym);
}

/**
 * from〜to（YYYY-MM-DD・両端を含む）のレースを返す。
 * opt.months: 実在する月の一覧（あれば、無い月は取りに行かない）
 * opt.onProgress(done, total): 1か月読めるごとに呼ぶ
 */
export async function loadRaces(from, to, opt = {}) {
  const t0 = performance.now();
  Object.assign(lastStats, { months: 0, fetched: 0, fetchMs: 0, parseMs: 0, expandMs: 0, totalMs: 0 });
  let months = monthsBetween(from, to);
  if (opt.months) {
    const have = new Set(opt.months);
    months = months.filter((m) => have.has(m));
  }
  lastStats.months = months.length;
  let done = 0;
  if (opt.onProgress) opt.onProgress(0, months.length);
  const parts = await Promise.all(months.map((ym) => loadMonth(ym).then((d) => {
    done += 1;
    if (opt.onProgress) opt.onProgress(done, months.length);
    return d;
  })));
  // 期間の内側の月はそのまま、両端の月だけ日付で絞る
  const fm = from.slice(0, 7), tm = to.slice(0, 7);
  const out = [];
  parts.forEach((arr, k) => {
    const ym = months[k];
    const edge = ym === fm || ym === tm;
    for (let i = 0; i < arr.length; i++) {
      const r = arr[i];
      if (!edge || (r.date >= from && r.date <= to)) out.push(r);
    }
  });
  lastStats.totalMs = performance.now() - t0;
  return out;
}

// ---------- 選手の組ファイル data/players/NN.json（2026/11/26。「選手の1着流し」は選手の分だけ読む） ----------
// NN＝登録番号 % 64。形は build_races.py の pack_players。
//   {v:1, group, groups:64, d0:'YYYY-MM-DD', venues, grades, players:{'登録番号':[行…]}}
//   行 = [日(d0 からの日数), 場の番号, R, グレードの番号|null, 枠, コース|null, 印(1=返還 2=不成立), 返還でない艇(艇番のビット), 単勝, 複勝, 2連単, 3連単]
// 戻したレースは filterRaces（期間・場・グレード・選手・コース）と evalPlayerNagashi のためだけの形:
//   boats＝その選手の艇（着は null）＋返還でない他の艇（艇番だけ分かる仮の艇。toban 0）
//   pay＝単勝・複勝はその選手の艇番、2連単・3連単は「その艇番-*」の1組に合計の払戻。載っていない券種は []。連複は []
// 出目指定には使わない（月ファイルを使う）。
const PBASE = 'data/players/';
const PGROUPS = 64;
const groupCache = new Map(); // 組の番号 -> Promise<組ファイル>
const playerCache = new Map(); // 登録番号 -> race[]

export function playerGroup(toban) {
  return Number(toban) % PGROUPS;
}

function dayStrings(d0, n) {
  const [y, m, d] = d0.split('-').map(Number);
  const out = new Array(n + 1);
  const p = (x) => String(x).padStart(2, '0');
  for (let i = 0; i <= n; i++) {
    const t = new Date(Date.UTC(y, m - 1, d + i));
    out[i] = `${t.getUTCFullYear()}-${p(t.getUTCMonth() + 1)}-${p(t.getUTCDate())}`;
  }
  return out;
}

/** 組ファイルの1選手分の行 → レースの形（filterRaces・evalPlayerNagashi 用） */
export function expandPlayer(obj, toban) {
  if (!obj || obj.v !== 1) throw new Error('選手のファイルの形が分かりません');
  const rows = (obj.players && obj.players[String(Number(toban))]) || [];
  const tb = Number(toban);
  let maxDay = 0;
  for (const r of rows) if (r[0] > maxDay) maxDay = r[0];
  const days = dayStrings(obj.d0, maxDay);
  const out = new Array(rows.length);
  for (let i = 0; i < rows.length; i++) {
    const [d, v, rno, g, waku, course, flags, alive, tan, fuku, n2, n3] = rows[i];
    const boats = [{ waku, toban: tb, course, rank: null, refund: (flags & 1) === 1 }];
    for (let w = 1; w <= 6; w++) {
      if (w !== waku && (alive & (1 << (w - 1)))) boats.push({ waku: w, toban: 0, course: null, rank: null, refund: false });
    }
    const ws = String(waku);
    out[i] = {
      date: days[d], venue: obj.venues[v], rno, grade: g === null ? null : obj.grades[g], boats,
      pay: {
        tansho: tan === null ? [] : [[ws, tan]],
        fukusho: fuku === null ? [] : [[ws, fuku]],
        nirentan: n2 === null ? [] : [[`${ws}-*`, n2]],
        nirenpuku: [],
        sanrentan: n3 === null ? [] : [[`${ws}-*-*`, n3]],
        sanrenpuku: [],
      },
      void: (flags & 2) === 2,
    };
  }
  return out;
}

function loadGroup(g) {
  if (!groupCache.has(g)) {
    const p = (async () => {
      const t0 = performance.now();
      const res = await fetch(dataUrl(`${PBASE}${String(g).padStart(2, '0')}.json`));
      if (!res.ok) throw new Error(`選手のデータを読めませんでした（${res.status}）`);
      const text = await res.text();
      const t1 = performance.now();
      const data = parseData(text);
      lastStats.fetchMs += t1 - t0;
      lastStats.parseMs += performance.now() - t1;
      lastStats.fetched += 1;
      return data;
    })();
    p.catch(() => groupCache.delete(g));
    groupCache.set(g, p);
  }
  return groupCache.get(g);
}

/** 選手が出た全レース（全期間・レースの順）。組ファイルはメモリに置き、2回目からは取り直さない */
export async function loadPlayer(toban) {
  const t0 = performance.now();
  Object.assign(lastStats, { months: 0, fetched: 0, fetchMs: 0, parseMs: 0, expandMs: 0, totalMs: 0 });
  const tb = Number(toban);
  if (!playerCache.has(tb)) {
    const data = await loadGroup(playerGroup(tb));
    const t1 = performance.now();
    if (!playerCache.has(tb)) playerCache.set(tb, expandPlayer(data, tb));
    lastStats.expandMs += performance.now() - t1;
  }
  lastStats.totalMs = performance.now() - t0;
  return playerCache.get(tb);
}
