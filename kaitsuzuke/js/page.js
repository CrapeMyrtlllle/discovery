// 買い続け試算の画面。条件の入力 → 期間の月を読む（選手の1着流しは選手の組ファイルだけ。loader.js）→ 計算（calc.js）→ 結果表・累計収支グラフ・結果カード。
// グラフは手書きの SVG、結果カードは canvas に描いて PNG で保存する（外部のライブラリは使わない）。
import { filterRaces, parseCombos, evalPlayerNagashi, evalCombos, summarize, cumulative, validateAmount } from './calc.js?v=021287adc4';
import { loadRaces, loadPlayer, lastStats, fetchData } from './loader.js?v=021287adc4';

const CONF = window.KT_CONF || {};
const VENUES = ['桐生', '戸田', '江戸川', '平和島', '多摩川', '浜名湖', '蒲郡', '常滑', '津', '三国', 'びわこ', '住之江',
  '尼崎', '鳴門', '丸亀', '児島', '宮島', '徳山', '下関', '若松', '芦屋', '福岡', '唐津', '大村'];
const GRADES = ['SG', 'G1', 'G2', 'G3', '一般'];
const BET_NAME = { tansho: '単勝', fukusho: '複勝', nirentan: '2連単', nirenpuku: '2連複', sanrentan: '3連単', sanrenpuku: '3連複' };
const NAGASHI = [
  { key: 'tansho', label: '単勝' },
  { key: 'fukusho', label: '複勝' },
  { key: 'nirentan', label: '2連単 1着流し' },
  { key: 'sanrentan', label: '3連単 1着流し' },
];
// 系列の色（固定の順。dataviz の検証済み：明るい地・暗い地とも CVD の差 8 以上。色だけに頼らず線の端に名前を付ける）
const COLORS_LIGHT = ['#3977B8', '#eb6834', '#1baf7a', '#eda100'];
const COLORS_DARK = ['#5A93D0', '#d95926', '#199e70', '#c98500'];
const REF_MIN = 30; // これ未満の走数は「参考値」

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const yen = (n) => `${Math.round(n).toLocaleString('ja-JP')}円`;
const signed = (n) => (n > 0 ? '+' : n < 0 ? '−' : '±') + Math.abs(Math.round(n)).toLocaleString('ja-JP') + '円';
const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);
const squeeze = (s) => String(s || '').replace(/[\s　]+/g, '');
const dark = () => document.documentElement.dataset.theme === 'dark';
const colors = () => (dark() ? COLORS_DARK : COLORS_LIGHT);
const nextFrame = () => new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));
const mobile = () => window.matchMedia('(max-width: 600px)').matches; // テンプレートの @media (max-width: 600px) と同じ

// runMsg に出す文。from は出したところ（'amount'＝金額の欄の入力中の確かめ）。金額が直ったときは金額の文だけ消す
function setMsg(cls, text, from = '') {
  const m = $('runMsg');
  m.className = cls;
  m.textContent = text;
  m.dataset.from = from;
}

const state = { players: [], player: null, last: null, running: 0 };
window.__kt = { timings: [] }; // 計測用（画面には出さない）

// ---------- 入力欄 ----------
function initPills() {
  $('grades').innerHTML = GRADES.map((g) => `<label class="pill"><input type="checkbox" value="${g}"><span>${g}</span></label>`).join('');
  $('venues').innerHTML = VENUES.map((v) => `<label class="pill"><input type="checkbox" value="${v}"><span>${v}</span></label>`).join('');
  $('vClear').addEventListener('click', () => { $('venues').querySelectorAll('input').forEach((i) => { i.checked = false; }); });
}
const checked = (id) => [...$(id).querySelectorAll('input:checked')].map((i) => i.value);

function addMonths(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setMonth(d.getMonth() + n);
  d.setDate(d.getDate() + 1);
  const p = (x) => String(x).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function initRange() {
  const min = CONF.min, max = CONF.max;
  for (const el of [$('dFrom'), $('dTo')]) { el.min = min; el.max = max; }
  const setRange = (k) => {
    $('dTo').value = max;
    $('dFrom').value = k === 'all' ? min : (addMonths(max, -Number(k)) < min ? min : addMonths(max, -Number(k)));
  };
  setRange('all');
  document.querySelectorAll('[data-range]').forEach((b) => b.addEventListener('click', () => setRange(b.dataset.range)));
  $('rangeNote').textContent = `データは ${fmtDate(min)}〜${fmtDate(max)}`;
}
const fmtDate = (s) => (s ? `${Number(s.slice(0, 4))}/${Number(s.slice(5, 7))}/${Number(s.slice(8, 10))}` : '');

async function initPlayers() {
  try {
    const arr = await fetchData('data/races/players.json');
    state.players = arr.map((p) => ({ toban: Number(p.toban), name: p.name, key: squeeze(p.name) }));
  } catch (e) {
    $('pRes').innerHTML = '<span class="err">選手の一覧を読めませんでした。登録番号で入れてください。</span>';
  }
}
function searchPlayers(q) {
  const s = squeeze(String(q).normalize('NFKC'));
  if (!s) return [];
  if (/^\d+$/.test(s)) {
    const hit = state.players.filter((p) => String(p.toban).startsWith(s));
    if (hit.length === 0 && s.length === 4) return [{ toban: Number(s), name: '（一覧にない登録番号）', key: '', unknown: true }];
    return hit.slice(0, 20);
  }
  return state.players.filter((p) => p.key.includes(s)).slice(0, 20);
}
function renderPlayer() {
  const body = $('pBody');
  const p = state.player;
  if (p) {
    body.innerHTML = `<span class="chosen"><span class="tb">${p.toban}</span>${esc(p.name)}<button type="button" id="pClear" aria-label="選手を外す" title="選手を外す">✕</button></span>`;
    $('pClear').addEventListener('click', () => { state.player = null; renderPlayer(); });
  } else {
    body.innerHTML = '<input class="in" type="search" id="pq" placeholder="名前か登録番号で探す" autocomplete="off" aria-label="選手を探す"><div id="pRes"></div>';
    bindSearch();
  }
  const has = !!p;
  $('course').disabled = !has;
  if (!has) $('course').value = '';
  $('courseNote').hidden = has;
  $('mNagashi').disabled = !has;
  if (!has && $('mNagashi').checked) $('mCombo').checked = true;
  $('modeNote').textContent = has
    ? '「選手の1着流し」は単勝・複勝・2連単（1着固定の流し）・3連単（1着固定の流し）を並べて出します。「出目指定」はこの選手が出たレースだけで数えます'
    : '「選手の1着流し」は選手を選ぶと選べます。単勝・複勝・2連単（1着固定の流し）・3連単（1着固定の流し）を並べて出します';
  updateMode();
}
function bindSearch() {
  const q = $('pq');
  q.addEventListener('input', () => {
    const hits = searchPlayers(q.value);
    $('pRes').innerHTML = hits.map((p, i) => `<button type="button" data-i="${i}"><span class="tb">${p.toban}</span>${esc(p.name)}</button>`).join('')
      + (q.value.trim() && hits.length === 0 ? '<span class="muted sm">見つかりません</span>' : '');
    $('pRes').querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      state.player = hits[Number(b.dataset.i)];
      renderPlayer();
    }));
  });
}
function mode() { return $('mNagashi').checked ? 'nagashi' : 'combo'; }
function updateMode() { $('comboRow').hidden = mode() !== 'combo'; }

function comboPreview() {
  const text = $('combos').value;
  const msg = $('comboMsg');
  if (!text.trim()) { msg.textContent = ''; msg.className = 'note'; return null; }
  const r = parseCombos(text, $('betType').value);
  if (!r.ok) { msg.textContent = r.message; msg.className = 'note err'; return r; }
  const list = r.combos.length > 20 ? `${r.combos.slice(0, 20).join('、')} ほか${r.combos.length - 20}点` : r.combos.join('、');
  msg.className = 'note';
  msg.textContent = `${BET_NAME[$('betType').value]} ${r.combos.length}点：${list}`
    + (r.duplicates > 0 ? `（同じ出目が重なっていた分 ${r.duplicates}点を除いて、${r.combos.length}点にまとめました）` : '');
  return r;
}

// ---------- 計算 ----------
function readConditions() {
  const amountRaw = $('amount').value;
  const va = validateAmount(String(amountRaw).normalize('NFKC'));
  if (!va.ok) return { error: va.message, from: 'amount' }; // 金額の欄を直したら消す
  const amount = Number(String(amountRaw).normalize('NFKC').trim());
  const from = $('dFrom').value, to = $('dTo').value;
  if (!from || !to) return { error: '期間を入れてください。' };
  if (from > to) return { error: '期間のはじめが、おわりより後になっています。' };
  const m = mode();
  const c = {
    amount, from, to, mode: m,
    toban: state.player ? state.player.toban : null,
    playerName: state.player && !state.player.unknown ? state.player.name : '',
    course: state.player && $('course').value ? Number($('course').value) : null,
    grades: checked('grades'), venues: checked('venues'),
  };
  if (m === 'nagashi' && !c.toban) return { error: '「選手の1着流し」は選手を選んでください。' };
  if (m === 'combo') {
    const r = parseCombos($('combos').value, $('betType').value);
    if (!r.ok) return { error: r.message };
    c.betType = $('betType').value;
    c.combos = r.combos;
    c.duplicates = r.duplicates;
  }
  return { c };
}

async function evalInChunks(races, fn, runId) {
  const out = [];
  const CHUNK = 5000; // スマホでも1回の処理が長くならないように区切る
  for (let i = 0; i < races.length; i += CHUNK) {
    const end = Math.min(races.length, i + CHUNK);
    for (let j = i; j < end; j++) out.push(fn(races[j]));
    if (end < races.length) {
      await nextFrame();
      if (runId !== state.running) return null;
    }
  }
  return out;
}

// 結果の欄を隠し、古い結果で画像を保存できないようにする
function clearResult() {
  state.last = null;
  state.cardDone = false;
  $('resBox').hidden = true;
  $('resBody').innerHTML = '';
  $('chartBox').hidden = true;
  $('cardBox').hidden = true;
  $('chartWrap').innerHTML = '';
  const cv = $('cardCanvas');
  cv.getContext('2d').clearRect(0, 0, cv.width, cv.height);
  unfold(false);
}

// ---------- スマホ: 結果が出たら条件を1行に畳み、結果まで送る（PC は今のまま） ----------
function summaryText(c) {
  const who = c.toban ? (c.playerName ? `${c.playerName}（${c.toban}）` : `${c.toban}`) : '選手指定なし';
  const parts = [who];
  if (c.toban && c.course) parts.push(`${c.course}コース`);
  if (c.grades.length) parts.push(c.grades.join('・'));
  parts.push(c.venues.length ? c.venues.join('・') : '全場');
  parts.push(`${fmtDate(c.from)}〜${fmtDate(c.to)}`);
  parts.push(c.mode === 'nagashi' ? '1着流し' : `${BET_NAME[c.betType]} ${c.combos.length}点`);
  parts.push(`1点${c.amount.toLocaleString('ja-JP')}円`);
  return parts.join('・');
}
function fold(c) {
  const t = summaryText(c);
  $('formSumText').textContent = t;
  $('formSumText').title = t;
  $('formSum').hidden = false;
  $('formBox').classList.add('folded');
  $('main').classList.add('nogo');
  $('unfoldBtn').setAttribute('aria-expanded', 'false');
}
function unfold(scroll) {
  const box = $('formBox');
  if (!box.classList.contains('folded')) return;
  box.classList.remove('folded');
  $('main').classList.remove('nogo');
  $('formSum').hidden = true;
  $('unfoldBtn').setAttribute('aria-expanded', 'true');
  if (scroll) box.scrollIntoView({ block: 'start' });
}
function afterResult(c) {
  if (!mobile()) return;
  fold(c);
  $('resBox').scrollIntoView({ block: 'start', behavior: 'smooth' });
}
async function run() {
  const { c, error, from } = readConditions();
  const msg = $('runMsg');
  if (error) { setMsg('err', error, from || ''); clearResult(); return; }
  const runId = ++state.running;
  const btn = $('runBtn');
  btn.disabled = true;
  setMsg('busy', '読み込み中…');
  const t0 = performance.now();
  try {
    // 選手の1着流しは、その選手の組ファイル（data/players/NN.json）だけ読む。期間・場・グレード・コースは下の filterRaces で絞る
    const races = c.mode === 'nagashi'
      ? await loadPlayer(c.toban)
      : await loadRaces(c.from, c.to, {
        months: CONF.months,
        onProgress: (d, n) => { if (runId === state.running) msg.textContent = `読み込み中（${d}/${n}か月）…`; },
      });
    if (runId !== state.running) return;
    const t1 = performance.now();
    msg.textContent = `計算中（${races.length.toLocaleString('ja-JP')}レース）…`;
    await nextFrame();
    const target = filterRaces(races, { toban: c.toban, course: c.course, grades: c.grades, venues: c.venues, from: c.from, to: c.to });
    let res;
    if (c.mode === 'nagashi') {
      const per = await evalInChunks(target, (r) => {
        const e = evalPlayerNagashi(r, c.toban);
        return e ? { date: r.date, e } : null;
      }, runId);
      if (!per) return;
      const valid = per.filter(Boolean);
      res = {
        target: target.length,
        rows: NAGASHI.map((b, i) => {
          const results = valid.map((x) => ({ date: x.date, points: x.e[b.key].points, payout: x.e[b.key].payout }));
          return { key: b.key, label: b.label, color: i, results, points: pointsLabel(results) };
        }),
      };
      for (const row of res.rows) { // 券種ごとに区切って集計（画面を固めない）
        await nextFrame();
        if (runId !== state.running) return;
        row.sum = summarize(row.results, c.amount);
        row.cum = cumulative(row.results, c.amount);
        delete row.results;
      }
    } else {
      const per = await evalInChunks(target, (r) => {
        const e = evalCombos(r, c.betType, c.combos);
        return e ? { date: r.date, points: e.points, payout: e.payout } : null;
      }, runId);
      if (!per) return;
      const results = per; // null（不成立）は summarize・cumulative が数えない
      await nextFrame();
      if (runId !== state.running) return;
      res = {
        target: target.length,
        rows: [{ key: c.betType, label: `${BET_NAME[c.betType]} ${c.combos.length}点`, color: 0,
          sum: summarize(results, c.amount), cum: cumulative(results, c.amount), points: '' }],
      };
    }
    const t2 = performance.now();
    state.last = { c, res };
    state.cardDone = false;
    await render(c, res);
    const t3 = performance.now();
    // 結果カードは画面に近づいたとき（または「画像を保存」を押したとき）に描く。結果の表とグラフを先に見せる
    if (cardObserver && !$('cardBox').hidden) { cardObserver.unobserve($('cardBox')); cardObserver.observe($('cardBox')); }
    else if (!cardObserver) ensureCard();
    window.__kt.timings.push({ load: t1 - t0, calc: t2 - t1, render: t3 - t2, total: t3 - t0, races: races.length,
      target: target.length, parseMs: lastStats.parseMs, expandMs: lastStats.expandMs, fetched: lastStats.fetched, months: lastStats.months });
    setMsg('muted sm', c.mode === 'nagashi'
      ? `この選手が出た${races.length.toLocaleString('ja-JP')}レースから計算しました`
      : `${races.length.toLocaleString('ja-JP')}レースから計算しました`);
    afterResult(c);
  } catch (e) {
    if (runId === state.running) { setMsg('err', `読み込めませんでした：${e.message}`); clearResult(); }
  } finally {
    if (runId === state.running) btn.disabled = false;
  }
}

// 流しの点数（返還があると減るので、いちばん多い点数を「◯点」、ほかがあれば「◯点など」）
function pointsLabel(results) {
  const cnt = new Map();
  for (const r of results) if (r.points > 0) cnt.set(r.points, (cnt.get(r.points) || 0) + 1);
  if (cnt.size === 0) return '';
  const top = [...cnt.entries()].sort((a, b) => b[1] - a[1])[0][0];
  return cnt.size > 1 ? `${top}点（返還で減るレースあり）` : `${top}点`;
}

// ---------- 結果表 ----------
function condParts(c) {
  const parts = [];
  parts.push(['選手', c.toban ? (c.playerName ? `${c.playerName}（${c.toban}）` : `${c.toban}`) : '指定なし']);
  if (c.toban) parts.push(['コース', c.course ? `${c.course}コース` : '指定なし']);
  parts.push(['グレード', c.grades.length ? c.grades.join('・') : 'すべて']);
  parts.push(['場', c.venues.length ? c.venues.join('・') : '全場']);
  parts.push(['期間', `${fmtDate(c.from)}〜${fmtDate(c.to)}`]);
  return parts;
}
function buyLabel(c) {
  if (c.mode === 'nagashi') return `${c.playerName || `登録番号${c.toban}`}の1着流し（単勝・複勝・2連単・3連単）`;
  const list = c.combos.length > 12 ? `${c.combos.slice(0, 12).join('、')} ほか${c.combos.length - 12}点` : c.combos.join('、');
  return `${BET_NAME[c.betType]} ${list}（${c.combos.length}点）`;
}
function countCell(n) {
  if (n < REF_MIN) return `<span class="ref">参考値（${n.toLocaleString('ja-JP')}走）</span>`;
  return `${n.toLocaleString('ja-JP')}走`;
}
// スマホの結果カード（券種ごとに1枚。PC は表。どちらを見せるかはテンプレートの CSS）
function resultCards(rows, multi, cs) {
  return '<div class="rcards">' + rows.map((r) => {
    const s = r.sum;
    const cls = s.profit > 0 ? 'plus' : s.profit < 0 ? 'minus' : '';
    const item = (k, v, w) => `<div${w ? ' class="w"' : ''}><dt>${k}</dt><dd>${v}</dd></div>`;
    return `<section class="rc" aria-label="${esc(r.label)}"><div class="rc-h">`
      + `<span>${multi ? `<span class="sw" data-c="${r.color}" style="background:${cs[r.color]}"></span>` : ''}${esc(r.label)}</span>`
      + `${r.points ? `<span class="pts">${esc(r.points)}</span>` : ''}<span class="rc-n">${countCell(s.count)}</span></div>`
      + `<div class="rc-big"><div><span class="k">回収率</span><span class="v">${pct(s.roi)}</span></div>`
      + `<div><span class="k">収支</span><span class="v pf ${cls}">${signed(s.profit)}</span></div></div>`
      + `<dl class="rc-s">${item('的中率', pct(s.hitRate))}${item('最高配当', s.maxPayout ? yen(s.maxPayout) : '—')}`
      + `${item('投資', yen(s.invest))}${item('払戻', yen(s.payout))}${item('最高配当除き回収率', pct(s.roiWithoutMax), true)}</dl></section>`;
  }).join('') + '</div>';
}
async function render(c, res) {
  $('resBox').hidden = false;
  $('condLine').innerHTML = condParts(c).map(([k, v]) => `${k} <b>${esc(v)}</b>`).join('　')
    + `<br>買い方 <b>${esc(buyLabel(c))}</b>　金額 <b>1点${c.amount.toLocaleString('ja-JP')}円</b>`;
  const cs = colors();
  const total = Math.max(...res.rows.map((r) => r.sum.count)); // 券種ごとに走数が違うので最大を「数えたレース」にする
  let html = '';
  if (total === 0) {
    html = '<p class="empty">該当レースがありません</p>';
  } else {
    const multi = res.rows.length > 1;
    html = `<div class="scroll rt-wrap"><table class="rt"><thead><tr><th>買い目</th><th>走数</th><th>投資</th><th>払戻</th><th>収支</th><th>回収率</th><th>的中率</th><th>最高配当</th><th>最高配当除き回収率</th></tr></thead><tbody>`
      + res.rows.map((r) => {
        const s = r.sum;
        const cls = s.profit > 0 ? 'plus' : s.profit < 0 ? 'minus' : '';
        return `<tr><td>${multi ? `<span class="sw" data-c="${r.color}" style="background:${cs[r.color]}"></span>` : ''}${esc(r.label)}${r.points ? `<span class="pts">${esc(r.points)}</span>` : ''}</td>`
          + `<td>${countCell(s.count)}</td><td>${yen(s.invest)}</td><td>${yen(s.payout)}</td><td class="${cls}">${signed(s.profit)}</td>`
          + `<td class="roi">${pct(s.roi)}</td><td>${pct(s.hitRate)}</td><td>${s.maxPayout ? yen(s.maxPayout) : '—'}</td><td>${pct(s.roiWithoutMax)}</td></tr>`;
      }).join('') + '</tbody></table></div>'
      + resultCards(res.rows, multi, cs);
  }
  const skipped = res.target - total;
  html += `<p class="counts">条件に合うレース ${res.target.toLocaleString('ja-JP')}　数えたレース ${total.toLocaleString('ja-JP')}`
    + (skipped > 0 ? `　数えなかったレース ${skipped.toLocaleString('ja-JP')}（返還・不成立など）` : '') + '</p>';
  if (c.mode === 'combo' && c.duplicates > 0) html += `<p class="counts">同じ出目が重なっていた分（${c.duplicates}点）を除いて、${c.combos.length}点で計算しました。</p>`;
  $('resBody').innerHTML = html;
  if (total === 0) {
    $('chartBox').hidden = true;
    $('cardBox').hidden = true;
  } else {
    $('chartBox').hidden = false;
    $('cardBox').hidden = false;
    await nextFrame(); // 表を先に見せてからグラフを描く
    const tch = performance.now();
    drawChart(res);
    window.__kt.chartMs = performance.now() - tch;
  }
}

// ---------- 累計収支グラフ（SVG） ----------
function niceStep(range, n) {
  const raw = range / n;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const f = raw / mag;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag;
}
function shortYen(v) {
  const a = Math.abs(v);
  const s = v < 0 ? '−' : '';
  if (a >= 100000000) return `${s}${+(a / 100000000).toFixed(1)}億`;
  if (a >= 10000) return `${s}${+(a / 10000).toFixed(1)}万`;
  return `${s}${a.toLocaleString('ja-JP')}`;
}
// 点が多いときは区間ごとの最小・最大だけ残す（形は崩さない）
function thin(vals, maxPts) {
  const n = vals.length;
  if (n <= maxPts) return vals.map((v, i) => [i, v]);
  const out = [];
  const size = n / (maxPts / 2);
  for (let b = 0; b * size < n; b++) {
    const s = Math.floor(b * size), e = Math.min(n, Math.floor((b + 1) * size));
    let mi = s, ma = s;
    for (let i = s; i < e; i++) { if (vals[i] < vals[mi]) mi = i; if (vals[i] > vals[ma]) ma = i; }
    if (mi < ma) out.push([mi, vals[mi]], [ma, vals[ma]]); else if (mi > ma) out.push([ma, vals[ma]], [mi, vals[mi]]); else out.push([mi, vals[mi]]);
  }
  if (out[out.length - 1][0] !== n - 1) out.push([n - 1, vals[n - 1]]);
  return out;
}
function drawChart(res) {
  const wrap = $('chartWrap');
  const cs = colors();
  const series = res.rows.filter((r) => r.cum.profit.length > 0);
  // 画面の幅に合わせて描く（スマホで文字が縮まないように）
  state.chartW = wrap.clientWidth;
  const W = Math.max(300, Math.round(wrap.clientWidth || 760)), H = W < 600 ? 260 : 320;
  const L = 52, R = series.length > 1 ? 60 : 16, T = 14, B = 34;
  const pw = W - L - R, ph = H - T - B;
  let lo = 0, hi = 0, maxN = 1;
  for (const s of series) {
    for (const v of s.cum.profit) { if (v < lo) lo = v; if (v > hi) hi = v; }
    maxN = Math.max(maxN, s.cum.profit.length);
  }
  if (hi === lo) { hi += 1000; lo -= 1000; }
  const step = niceStep(hi - lo, 4);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  const x = (i, n) => L + (n <= 1 ? pw : (i / (n - 1)) * pw);
  const y = (v) => T + ((hi - v) / (hi - lo)) * ph;
  let g = '';
  for (let v = lo; v <= hi + step / 2; v += step) {
    g += `<line class="${v === 0 ? 'zero' : 'grid'}" x1="${L}" x2="${L + pw}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>`
      + `<text x="${L - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${shortYen(v)}</text>`;
  }
  const ref = series.reduce((a, s) => (s.cum.labels.length > a.cum.labels.length ? s : a), series[0]);
  const labs = ref.cum.labels;
  const ticks = labs.length > 1 ? [0, Math.floor((labs.length - 1) / 2), labs.length - 1] : [0];
  g += ticks.map((i, k) => `<text x="${x(i, labs.length).toFixed(1)}" y="${H - 12}" text-anchor="${k === 0 ? 'start' : k === ticks.length - 1 ? 'end' : 'middle'}">${fmtDate(labs[i])}</text>`).join('');
  let lines = '';
  const ends = [];
  for (const s of series) {
    const vals = s.cum.profit;
    const pts = thin(vals, 900).map(([i, v]) => `${x(i, vals.length).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
    lines += `<polyline points="${pts}" style="stroke:${cs[s.color]}"/>`;
    ends.push({ y: y(vals[vals.length - 1]), label: s.label.replace(' 1着流し', ''), color: cs[s.color] });
  }
  let endLabels = '';
  if (series.length > 1) { // 線の右端に名前（色だけに頼らない）。重なりは 14px ずつ離す
    ends.sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
    endLabels = ends.map((e) => `<text class="end" x="${L + pw + 6}" y="${(e.y + 4).toFixed(1)}">${esc(e.label)}</text>`).join('');
  }
  const legend = series.length > 1
    ? `<div class="legend">${series.map((s) => `<span><span class="sw" style="background:${cs[s.color]}"></span>${esc(s.label)}</span>`).join('')}</div>` : '';
  wrap.innerHTML = `${legend}<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="累計収支の推移（1走ごと）">${g}${lines}${endLabels}`
    + `<line class="cross" id="cross" x1="0" x2="0" y1="${T}" y2="${T + ph}" visibility="hidden"/>`
    + `<rect x="${L}" y="${T}" width="${pw}" height="${ph}" fill="transparent" id="hit"/></svg><div class="tip" id="tip" hidden></div>`;
  // ホバー：縦線とその走の累計
  const svg = wrap.querySelector('svg'), tip = $('tip'), cross = $('cross');
  const move = (ev) => {
    const rect = svg.getBoundingClientRect();
    const sx = ((ev.clientX - rect.left) / rect.width) * W;
    const f = Math.min(1, Math.max(0, (sx - L) / pw));
    const i = Math.round(f * (labs.length - 1));
    const cx = x(i, labs.length);
    cross.setAttribute('x1', cx); cross.setAttribute('x2', cx); cross.setAttribute('visibility', 'visible');
    tip.innerHTML = `<div class="h">${(i + 1).toLocaleString('ja-JP')}走目・${fmtDate(labs[i])}</div>`
      + series.map((s) => {
        const n = s.cum.profit.length;
        const v = s.cum.profit[Math.min(n - 1, Math.round(f * (n - 1)))];
        return `<div class="r"><span>${series.length > 1 ? `<span class="sw" style="background:${cs[s.color]}"></span>` : ''}${esc(s.label)}</span><b>${signed(v)}</b></div>`;
      }).join('');
    tip.hidden = false;
    const px = ((cx / W) * rect.width);
    const wrapW = wrap.clientWidth;
    const tw = tip.offsetWidth;
    tip.style.left = `${Math.max(0, Math.min(wrapW - tw, px + 12 > wrapW - tw ? px - tw - 12 : px + 12))}px`;
    tip.style.top = `${svg.offsetTop + 8}px`;
  };
  const hit = $('hit');
  hit.addEventListener('pointermove', move);
  hit.addEventListener('pointerdown', move);
  hit.addEventListener('pointerleave', () => { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); });
}

// 画面の幅が変わったとき・明るさ（ダーク）を切り替えたときにグラフ（と表・カードの色見本）を描き直す
function initRedraw() {
  let timer = 0;
  const redraw = () => {
    if (!state.last || $('chartBox').hidden) return;
    drawChart(state.last.res);
  };
  window.addEventListener('resize', () => {
    clearTimeout(timer);
    timer = setTimeout(() => { if ($('chartWrap').clientWidth !== state.chartW) redraw(); }, 150);
  });
  new MutationObserver(() => {
    if (!state.last) return;
    const cs = colors();
    $('resBody').querySelectorAll('.sw[data-c]').forEach((el) => { el.style.background = cs[Number(el.dataset.c)]; });
    redraw();
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
}

// ---------- 結果カード（canvas → PNG） ----------
const FONT = '"Noto Sans JP", "Yu Gothic UI", "Meiryo", system-ui, sans-serif';
function wrapText(ctx, text, maxW) {
  const out = [];
  let line = '';
  for (const ch of text) {
    if (ctx.measureText(line + ch).width > maxW && line) { out.push(line); line = ch; } else line += ch;
  }
  if (line) out.push(line);
  return out;
}
async function drawCard(c, res) {
  if (Math.max(...res.rows.map((r) => r.sum.count)) === 0) return;
  // 書体がまだ読めていなければ、いったん代わりの書体で描き、読めたら同じ結果のときだけ描き直す（待たせない）
  try {
    if (!document.fonts.check(`700 40px ${FONT}`)) {
      document.fonts.load(`700 40px ${FONT}`).then(() => {
        if (state.last && state.last.res === res && document.fonts.check(`700 40px ${FONT}`)) paintCard(c, res);
      }).catch(() => {});
    }
  } catch (e) { /* 書体の確認ができなくても描く */ }
  paintCard(c, res);
}
function paintCard(c, res) {
  const cv = $('cardCanvas');
  const W = 1080, P = 64, CW = W - P * 2;
  const ctx0 = cv.getContext('2d');
  // 1回目は高さを測るだけ
  ctx0.font = `500 30px ${FONT}`;
  const condLines = condParts(c).flatMap(([k, v]) => wrapText(ctx0, `${k}：${v}`, CW));
  const buyLines = wrapText(ctx0, `買い方：${buyLabel(c)}`, CW).concat(wrapText(ctx0, `金額：1点${c.amount.toLocaleString('ja-JP')}円`, CW));
  const multi = res.rows.length > 1;
  const rowH = multi ? 96 : 240;
  const H = 180 + (condLines.length + buyLines.length) * 46 + 40 + res.rows.length * rowH + 150;
  cv.width = W; cv.height = H;
  const ctx = cv.getContext('2d');
  // 画像はいつも明るい地（SNS に貼ったときに読みやすいように）
  const ink = '#182235', sub = '#56637A', meta = '#6E7A8E', line = '#E3E8EF', ok = '#21865A', er = '#D64B4B';
  ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#101D35'; ctx.fillRect(0, 0, W, 132);
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#6FA3DA'; ctx.font = `700 24px ${FONT}`; ctx.fillText('Discovery', P, 50);
  ctx.fillStyle = '#FFFFFF'; ctx.font = `700 46px ${FONT}`; ctx.fillText('買い続け試算', P, 106);
  let yy = 132 + 64;
  ctx.font = `500 30px ${FONT}`; ctx.fillStyle = sub;
  for (const l of condLines) { ctx.fillText(l, P, yy); yy += 46; }
  ctx.fillStyle = ink;
  for (const l of buyLines) { ctx.fillText(l, P, yy); yy += 46; }
  yy += 10;
  ctx.fillStyle = line; ctx.fillRect(P, yy, CW, 2); yy += 30;
  const cs = COLORS_LIGHT;
  for (const r of res.rows) {
    const s = r.sum;
    const pc = s.profit > 0 ? ok : s.profit < 0 ? er : ink;
    const cnt = s.count < REF_MIN ? `参考値（${s.count.toLocaleString('ja-JP')}走）` : `${s.count.toLocaleString('ja-JP')}走`;
    if (multi) {
      ctx.fillStyle = cs[r.color]; ctx.fillRect(P, yy + 12, 18, 18);
      ctx.fillStyle = ink; ctx.font = `700 32px ${FONT}`; ctx.fillText(r.label, P + 30, yy + 32);
      ctx.fillStyle = meta; ctx.font = `500 24px ${FONT}`; ctx.fillText(cnt, P + 30, yy + 70);
      ctx.textAlign = 'right';
      ctx.fillStyle = ink; ctx.font = `700 40px ${FONT}`; ctx.fillText(`回収率 ${pct(s.roi)}`, W - P, yy + 36);
      ctx.fillStyle = pc; ctx.font = `700 28px ${FONT}`; ctx.fillText(`収支 ${signed(s.profit)}`, W - P, yy + 74);
      ctx.textAlign = 'left';
      yy += rowH;
      ctx.fillStyle = line; ctx.fillRect(P, yy - 8, CW, 1);
    } else {
      ctx.fillStyle = sub; ctx.font = `500 28px ${FONT}`; ctx.fillText('回収率', P, yy + 30);
      ctx.fillStyle = ink; ctx.font = `700 96px ${FONT}`; ctx.fillText(pct(s.roi), P, yy + 126);
      ctx.fillStyle = sub; ctx.font = `500 28px ${FONT}`; ctx.fillText('収支', P + CW / 2, yy + 30);
      ctx.fillStyle = pc; ctx.font = `700 56px ${FONT}`; ctx.fillText(signed(s.profit), P + CW / 2, yy + 110);
      ctx.fillStyle = meta; ctx.font = `500 26px ${FONT}`;
      ctx.fillText(`${cnt}　投資 ${yen(s.invest)}　払戻 ${yen(s.payout)}`, P, yy + 190);
      yy += rowH;
    }
  }
  ctx.fillStyle = meta; ctx.font = `500 22px ${FONT}`;
  const foot = wrapText(ctx, '過去のレースで買い続けたときの試算です。払戻は元データにある分だけで計算しています。', CW);
  yy = H - 40 - (foot.length - 1) * 32;
  for (const l of foot) { ctx.fillText(l, P, yy); yy += 32; }
}
// 結果カードをまだ描いていなければ描く
let cardObserver = null;
async function ensureCard() {
  const last = state.last;
  if (!last || state.cardDone) return;
  state.cardDone = true;
  const t = performance.now();
  await drawCard(last.c, last.res);
  window.__kt.cardMs = performance.now() - t;
}
async function saveCard() {
  await ensureCard();
  const cv = $('cardCanvas');
  const d = new Date();
  const p = (x) => String(x).padStart(2, '0');
  const name = `kaitsuzuke_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}.png`;
  cv.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }, 'image/png');
}

// ---------- はじめ ----------
function init() {
  initPills();
  initRange();
  renderPlayer();
  document.querySelectorAll('input[name="mode"]').forEach((r) => r.addEventListener('change', updateMode));
  $('combos').addEventListener('input', comboPreview);
  $('betType').addEventListener('change', comboPreview);
  $('amount').addEventListener('input', () => {
    const v = validateAmount(String($('amount').value).normalize('NFKC'));
    const m = $('runMsg');
    if (!v.ok) setMsg('err', v.message, 'amount');
    else if (m.dataset.from === 'amount') setMsg('', ''); // 金額の文だけ消す（ほかのエラー・結果の文は残す）
  });
  $('runBtn').addEventListener('click', run);
  $('unfoldBtn').addEventListener('click', () => unfold(true));
  initRedraw();
  $('saveBtn').addEventListener('click', saveCard);
  if ('IntersectionObserver' in window) {
    cardObserver = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) ensureCard(); }, { rootMargin: '400px 0px' });
  }
  initPlayers();
}
init();
