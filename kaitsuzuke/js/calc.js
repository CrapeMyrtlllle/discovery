// 買い続け試算ツールの計算ロジック（DOM・fetch を使わない純粋関数。ブラウザと node の両方から import できる）

const BET_INFO = {
  sanrentan: { n: 3, ordered: true },
  sanrenpuku: { n: 3, ordered: false },
  nirentan: { n: 2, ordered: true },
  nirenpuku: { n: 2, ordered: false },
};

/** 期間・グレード・場・選手・コースで絞る。void のレースはここでは落とさない。 */
export function filterRaces(races, opt = {}) {
  const { toban, course, grades, venues, from, to } = opt;
  const hasToban = toban !== undefined && toban !== null && toban !== '';
  const hasCourse = course !== undefined && course !== null && course !== '';
  return races.filter((r) => {
    if (from && r.date < from) return false;
    if (to && r.date > to) return false;
    if (grades && grades.length > 0 && !grades.includes(r.grade)) return false;
    if (venues && venues.length > 0 && !venues.includes(r.venue)) return false;
    if (hasToban) {
      const b = r.boats.find((x) => Number(x.toban) === Number(toban));
      if (!b) return false;
      if (hasCourse && Number(b.course) !== Number(course)) return false;
    }
    return true;
  });
}

// 全角数字・全角ハイフン/イコール・全角空白などを半角に寄せる
function normalizeText(text) {
  return String(text)
    .normalize('NFKC')
    .replace(/[ー－−‐‑–—]/g, '-');
}

/** 買い目の文字列を点に分けて正規化する。 */
export function parseCombos(text, betType) {
  const info = BET_INFO[betType];
  if (!info) return { ok: false, message: '券種が不明です。' };
  const raw = normalizeText(text == null ? '' : text)
    .split(/[,，、\s]+/)
    .filter((s) => s !== '');
  if (raw.length === 0) return { ok: false, message: '買い目が入力されていません。' };

  const seen = new Set();
  const combos = [];
  let duplicates = 0;
  for (const token of raw) {
    const parts = token.split(/[-=]/);
    if (parts.length !== info.n) {
      return { ok: false, message: `「${token}」は艇番が${info.n}つではありません（${info.n}艇で書いてください）。` };
    }
    for (const p of parts) {
      if (!/^[1-6]$/.test(p)) {
        return { ok: false, message: `「${token}」に使えない艇番「${p}」があります（艇番は1〜6です）。` };
      }
    }
    if (new Set(parts).size !== parts.length) {
      return { ok: false, message: `「${token}」に同じ艇番が重なっています。` };
    }
    const nums = parts.map(Number);
    const key = info.ordered
      ? nums.join('-')
      : nums.slice().sort((a, b) => a - b).join('=');
    if (seen.has(key)) {
      duplicates += 1;
    } else {
      seen.add(key);
      combos.push(key);
    }
  }
  return { ok: true, combos, duplicates };
}

// pay[betType] のうち predicate(組番) に合う払戻の合計（100円あたり）
function sumPay(race, betType, predicate) {
  const arr = (race.pay && race.pay[betType]) || [];
  let sum = 0;
  for (const [key, yen] of arr) {
    if (predicate(String(key))) sum += yen;
  }
  return sum;
}

// その券種の払戻が1つでも載っているか（空・無しは不成立などで払戻が無い）
function hasPay(race, betType) {
  const arr = race.pay && race.pay[betType];
  return Array.isArray(arr) && arr.length > 0;
}

/** 選手の「頭固定・全流し」を1レースで評価する。返還・欠場・void は null。 */
export function evalPlayerNagashi(race, toban) {
  if (race.void) return null;
  const me = race.boats.find((b) => Number(b.toban) === Number(toban));
  if (!me || me.refund) return null;
  const n = race.boats.filter((b) => !b.refund).length;
  const w = String(me.waku);
  const head = (k) => k.split('-')[0] === w;
  // 払戻が載っていない券種（不成立・特払いなど）は、その券種だけ投資なし（points 0）にする
  const one = (betType, points, pred) => (hasPay(race, betType)
    ? { points, payout: sumPay(race, betType, pred) }
    : { points: 0, payout: 0 });
  return {
    tansho: one('tansho', 1, (k) => k === w),
    fukusho: one('fukusho', 1, (k) => k === w),
    nirentan: one('nirentan', n - 1, head),
    sanrentan: one('sanrentan', (n - 1) * (n - 2), head),
  };
}

/** 決まった買い目を1レースで評価する。void は null。返還・不在の艇を含む点は除く。 */
export function evalCombos(race, betType, combos) {
  if (race.void) return null;
  if (!hasPay(race, betType)) return { points: 0, payout: 0 };
  const sep = BET_INFO[betType] && BET_INFO[betType].ordered ? '-' : '=';
  const alive = new Set(race.boats.filter((b) => !b.refund).map((b) => String(b.waku)));
  const kept = new Set(combos.filter((c) => c.split(sep).every((w) => alive.has(w))));
  return {
    points: kept.size,
    payout: sumPay(race, betType, (k) => kept.has(k)),
  };
}

/** 結果配列（{date, points, payout}・払戻は100円あたり）を集計する。points 0 は数えない。 */
export function summarize(results, amount) {
  const rs = results.filter((r) => r && r.points > 0);
  const count = rs.length;
  const invest = rs.reduce((s, r) => s + r.points * amount, 0);
  const payout = rs.reduce((s, r) => s + Math.round((r.payout * amount) / 100), 0);
  const maxPayout = rs.reduce((m, r) => Math.max(m, Math.round((r.payout * amount) / 100)), 0);
  const hits = rs.filter((r) => r.payout > 0).length;
  return {
    count,
    invest,
    payout,
    profit: payout - invest,
    roi: count === 0 || invest === 0 ? null : payout / invest,
    hitRate: count === 0 ? null : hits / count,
    maxPayout,
    roiWithoutMax: count === 0 || invest === 0 ? null : (payout - maxPayout) / invest,
  };
}

/** 日付順の累計収支。points 0 は除く。同じ日は入力順。 */
export function cumulative(results, amount) {
  const rs = results
    .map((r, i) => ({ r, i }))
    .filter((x) => x.r && x.r.points > 0)
    .sort((a, b) => (a.r.date < b.r.date ? -1 : a.r.date > b.r.date ? 1 : a.i - b.i));
  const labels = [];
  const profit = [];
  let acc = 0;
  for (const { r } of rs) {
    acc += Math.round((r.payout * amount) / 100) - r.points * amount;
    labels.push(r.date);
    profit.push(acc);
  }
  return { labels, profit };
}

/** 1点あたりの金額の検証（100円以上・100円単位の整数）。 */
export function validateAmount(value) {
  const s = value == null ? '' : String(value).trim();
  if (!/^\d+$/.test(s)) return { ok: false, message: '金額は半角の整数で入力してください。' };
  const n = Number(s);
  if (n < 100) return { ok: false, message: '金額は100円以上で入力してください。' };
  if (n % 100 !== 0) return { ok: false, message: '金額は100円単位で入力してください。' };
  return { ok: true };
}
