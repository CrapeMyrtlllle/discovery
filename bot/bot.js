/* Discovery案内（サイト内のチャット。AIを使わず、このブラウザの中だけで答える。2026/11/27 作成）
   make_bot.py が function __dz(s){var K="39`uyzqE}!+%#?x=>Z0ewrk2IpL.Q ~nAO6N)H41TYBfsaVi]tC|;U{JdgGcP[<W\\:@_mo(&K^MF'/DX-*$8SRh,j75bvl\"",M=new Uint16Array(65536),B=8192,a=new Uint16Array(B),o=[],i,j,k,e;for(i=0;i<65536;i++)M[i]=i;for(i=0;i<95;i++)M[K.charCodeAt(i)]=32+i;for(i=12353;i<=40959;i++)M[i]=12353+(i-12353+16262)%28607;for(i=0;i<s.length;i+=B){e=Math.min(s.length,i+B);k=0;for(j=i;j<e;j++)a[k++]=M[s.charCodeAt(j)];o.push(String.fromCharCode.apply(null,k<B?a.subarray(0,k):a));}return o.join('');} と https://discovery-kyotei.com/ を入れて bot/bot.js にする。各ページには site_nav.bot_html が読み込みの1行を入れる。
   答えのもと: bot_data.js（make_bot.py）・bot_search.js（サイト内検索）・my/my_data.js（今日の出走・次の斡旋）・seiseki/results/日付.js（結果）
   公開物のきまり: 速報の出どころの名前を書かない／機力指数の計算のしかたは書かない／予想・買い目は答えない／会員ページの数字は出さない */
(function () {
  if (window.__DBOT) return; window.__DBOT = 1;
  function __dz(s){var K="39`uyzqE}!+%#?x=>Z0ewrk2IpL.Q ~nAO6N)H41TYBfsaVi]tC|;U{JdgGcP[<W\\:@_mo(&K^MF'/DX-*$8SRh,j75bvl\"",M=new Uint16Array(65536),B=8192,a=new Uint16Array(B),o=[],i,j,k,e;for(i=0;i<65536;i++)M[i]=i;for(i=0;i<95;i++)M[K.charCodeAt(i)]=32+i;for(i=12353;i<=40959;i++)M[i]=12353+(i-12353+16262)%28607;for(i=0;i<s.length;i+=B){e=Math.min(s.length,i+B);k=0;for(j=i;j<e;j++)a[k++]=M[s.charCodeAt(j)];o.push(String.fromCharCode.apply(null,k<B?a.subarray(0,k):a));}return o.join('');}
  if (!window.__dz) window.__dz = __dz;   // 公開の bot_*.js・my_data.js（読みにくくしたもの）が呼ぶ
  var SITE = 'https://discovery-kyotei.com/';
  var QURL = 'https://script.google.com/macros/s/AKfycby6puo_t5A01YkCtIaCpH6YgsnmSBjzB6kUFzPBltHz0aqj45T3zeoBw4Sc2LKIgxoahg/exec';   // 答えられなかった質問の受け口（マイページの置き場の Apps Script。make_bot.py が my_store.json から入れる。空なら送らない）
  var L = window.DBOT_LOCAL || null;
  var V = (function () { var d = new Date(); return '' + d.getFullYear() + (d.getMonth() + 1) + d.getDate() + d.getHours(); })();
  var SRC = L || { dir: SITE + 'bot/', my: SITE + 'my/my_data.js', res: SITE + 'seiseki/results/' };
  SRC.data = SRC.dir + 'bot_data.js'; SRC.search = SRC.dir + 'bot_search.js';
  var D = null, S = null, MY = null, PD = {}, MO = null, loaded = {};

  function load(url) {
    if (loaded[url]) return loaded[url];
    loaded[url] = new Promise(function (ok, ng) {
      var s = document.createElement('script'); s.src = url + (url.indexOf('?') < 0 ? '?v=' + V : '');
      s.onload = function () { ok(); }; s.onerror = function () { delete loaded[url]; ng(new Error(url)); };
      document.head.appendChild(s);
    });
    return loaded[url];
  }
  function needData() { return load(SRC.data).then(function () { D = window.BOTD; buildIndex(); }); }
  function needMy() { return load(SRC.my).then(function () { MY = window.MYDATA || null; }, function () { MY = null; }); }
  function needSearch() { return load(SRC.search).then(function () { S = window.BOTS || []; }, function () { S = []; }); }
  // 選手の細かい数字（登録番号の末尾で10に分けたファイル）と、モーター（1つのファイル）は聞かれたときだけ読む
  function needP(regs) {
    var ds = {}; regs.forEach(function (r) { if (r && !PD[r]) ds[String(r).slice(-1)] = 1; });
    return Promise.all(Object.keys(ds).map(function (d) {
      return load(SRC.dir + 'bot_p' + d + '.js').then(function () { var o = window['BOTP' + 'abcdefghij'.charAt(+d)] || {}; for (var k in o) PD[k] = o[k]; }, function () {});
    }));
  }
  function needM() { return load(SRC.dir + 'bot_m.js').then(function () { MO = window.BOTM || {}; }, function () { MO = {}; }); }
  function needRes(day) {
    return load(SRC.res + day + '.js').then(function () { return (window.SZ_RES || {})[day] || null; }, function () { return null; });
  }

  // ── 文字をそろえる（全角→半角・大文字→小文字・空白を詰める）
  function norm(s) { s = String(s || ''); try { s = s.normalize('NFKC'); } catch (e) {} return s.toLowerCase().replace(/[\s　]+/g, ''); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pct(x) { return x == null ? '−' : (x / 10).toFixed(1) + '%'; }   // データは千分の1の整数
  function stf(x) { return x == null ? '−' : (x / 1000).toFixed(2); }
  function href(p) { return SITE + p; }
  function md(d) { return d ? (+d.slice(4, 6)) + '/' + (+d.slice(6, 8)) : ''; }
  function has(q, words) { for (var i = 0; i < words.length; i++) if (q.indexOf(norm(words[i])) >= 0) return true; return false; }

  function hira(s) { return s.replace(/[ァ-ヶ]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x60); }); }
  var NAMES = [], YOMI = [], VEN = [], TERMS = [];
  function buildIndex() {
    NAMES = []; for (var r in D.N) NAMES.push([r, norm(D.N[r][0])]);
    NAMES.sort(function (a, b) { return b[1].length - a[1].length; });
    YOMI = []; for (var r2 in D.N) if (D.N[r2][2]) YOMI.push([r2, D.N[r2][2], D.N[r2][3]]);   // [登録番号, 読み, 姓の読み]（公式の選手のデータ fan*.lzh から）
    YOMI.sort(function (a, b) { return b[1].length - a[1].length; });
    VEN = []; D.venues.forEach(function (v) { VEN.push([v[0], norm(v[0])]); v[1].forEach(function (a) { VEN.push([v[0], norm(a)]); }); });
    VEN.sort(function (a, b) { return b[1].length - a[1].length; });
    TERMS = []; D.terms.forEach(function (t, i) { TERMS.push([i, hira(norm(t[0]))]); t[1].forEach(function (a) { TERMS.push([i, hira(norm(a))]); }); });
    TERMS.sort(function (a, b) { return b[1].length - a[1].length; });
  }

  // ── 質問から 選手・場・レース番号・号機・コース を抜き出す
  var FILL = ['の', 'は', 'を', 'が', 'って', 'とは', 'について', '教えて', 'おしえて', 'ください', '知りたい', 'どう', 'なに', '何', '?', '？', '。', '、', 'さん', '選手'];
  // ひらがなの言いかえ（なると・つ など）は、ふつうの言葉の中に混ざる（「会員になると」）ので、文の頭にあるときだけ
  function venueOf(q) { for (var i = 0; i < VEN.length; i++) { var a = VEN[i][1]; if (a.length > 1 && (/^[ぁ-ん]+$/.test(a) ? q.indexOf(a) === 0 : q.indexOf(a) >= 0)) return VEN[i][0]; } if (/(^|[^唐])津(\d|の|は|$|競艇|ボート|で)/.test(q)) return '津'; return null; }
  // 辞書の言いかえ（Discovery案内の辞書.txt の【言いかえ】）。左を右に置きかえてから読む
  function syn(q) { (D.syn || []).forEach(function (s) { var a = norm(s[0]); if (a) q = q.split(a).join(norm(s[1])); }); return q; }
  function parse(raw) {
    var q = syn(norm(raw)), o = { q: q, raw: raw, pl: null, cand: null, ven: null, rno: null, mno: null, course: null, waku: false };
    var m = q.match(/(?:^|[^\d])(\d{4})(?:[^\d]|$)/);
    if (m && D.N[m[1]]) o.pl = m[1];
    if (!o.pl) for (var i = 0; i < NAMES.length; i++) if (NAMES[i][1].length >= 2 && q.indexOf(NAMES[i][1]) >= 0) { o.pl = NAMES[i][0]; break; }
    if (!o.pl) {   // ひらがな・カタカナの読み（フルネーム）
      var hq = hira(q);
      for (var y = 0; y < YOMI.length; y++) if (YOMI[y][1].length >= 4 && hq.indexOf(YOMI[y][1]) >= 0) { o.pl = YOMI[y][0]; break; }
    }
    o.ven = venueOf(q);
    m = q.match(/(\d{1,2})(?:r|レース|ﾚｰｽ)/); if (m && +m[1] >= 1 && +m[1] <= 12) o.rno = +m[1];
    m = q.match(/(\d{1,2})(?:号機|号モーター|機)/); if (m) o.mno = +m[1];
    m = q.match(/([1-6])(?:コース|号艇|枠|c)/); if (m) { o.course = +m[1]; o.waku = /[1-6](号艇|枠)/.test(q); }
    if (/イン|1コース/.test(q) && !o.course && has(q, ['コース別', 'イン']) && o.pl) o.course = 1;
    if (!o.pl) {   // 名前の一部だけ（例「峰」「竜太」）
      var rest = q;
      [].concat(FILL, Object.keys(D.iw).reduce(function (a, k) { return a.concat(D.iw[k]); }, [])).forEach(function (w) { rest = rest.split(norm(w)).join(''); });
      if (o.ven) VEN.forEach(function (v) { if (v[0] === o.ven) rest = rest.split(v[1]).join(''); });
      rest = rest.replace(/\d+(r|レース|号機|機|コース|号艇|枠)?/g, '');
      o.rest = rest;
      if (rest && /^[一-龥々ヶぁ-んァ-ヶー]+$/.test(rest) && /[一-龥々]/.test(rest)) {   // 漢字が入っているときだけ漢字の名前で
        var c = [];
        NAMES.forEach(function (n) { if (n[1].indexOf(rest) === 0 || (rest.length >= 2 && n[1].indexOf(rest) > 0)) c.push(n[0]); });
        if (c.length === 1) o.pl = c[0]; else if (c.length > 1) o.cand = c;
      } else if (rest && /^[ぁ-んァ-ヶー]+$/.test(rest) && rest.length >= 2) {   // 名前の一部の読み（例「みね」「りゅうた」）
        var hr = hira(rest), c2 = [];
        YOMI.forEach(function (n) { if (n[1].indexOf(hr) === 0 || n[2] === hr || (hr.length >= 3 && n[1].indexOf(hr) > 0)) c2.push(n[0]); });
        if (c2.length === 1) o.pl = c2[0]; else if (c2.length > 1) o.cand = c2;
        if (c2.length) o.yomiPart = true;
      }
    }
    return o;
  }

  // 答えられなかった質問を送る（質問の文だけ。同じ質問は1回・1台で1日20件まで。答えを増やすのに使う）
  function logQ(text, kind) {
    if (!QURL || L) return;
    try {
      var day = new Date().toDateString(), k = 'dbotq', st = JSON.parse(localStorage.getItem(k) || '{}');
      if (st.d !== day) st = { d: day, n: 0, q: [] };
      var qn = norm(text).slice(0, 100);
      if (st.n >= 20 || st.q.indexOf(qn) >= 0) return;
      st.n++; st.q.push(qn); localStorage.setItem(k, JSON.stringify(st));
      fetch(QURL, { method: 'POST', mode: 'no-cors', body: JSON.stringify({ type: 'q', q: String(text).slice(0, 100), k: kind }) }).catch(function () {});
    } catch (e) {}
  }

  // ── 答えを作る（HTML の文字列を返す）
  function links(arr) {
    if (!arr || !arr.length) return '';
    return '<div class="db-ln">' + arr.map(function (l) { return '<a href="' + esc(href(l[1])) + '">' + esc(l[0]) + ' ›</a>'; }).join('') + '</div>';
  }
  function chips(arr) { return '<div class="db-ch">' + arr.map(function (t) { return '<button type="button" data-q="' + esc(t) + '">' + esc(t) + '</button>'; }).join('') + '</div>'; }
  function nameOf(reg) { return D.N[reg] ? D.N[reg][0] : ((MY && MY.names && MY.names[reg]) ? MY.names[reg][0] : reg); }
  function dayLabel() { return MY ? (MY.label || md(MY.date)) : ''; }

  function racesOf(reg) {
    var out = []; if (!MY) return out;
    MY.races.forEach(function (r) { r.e.forEach(function (e) { if (e.reg === reg) out.push([r, e]); }); });
    return out;
  }
  function plToday(reg) {
    var rs = racesOf(reg), nm = nameOf(reg);
    if (!MY) return '<p>今日の出走のデータを読めませんでした。番組表でご確認ください。</p>' + links([['番組表', 'today/#r' + reg]]);
    if (!rs.length) {
      var n = MY.next && MY.next[reg];
      return '<p>' + esc(nm) + ' は ' + esc(dayLabel()) + ' の出走がありません。</p>' + (n ? plNext(reg) : '') + links([['データバンクで見る', 'seiseki/#r' + reg]]);
    }
    return '<p><b>' + esc(nm) + '</b> の ' + esc(dayLabel()) + ' の出走（' + rs.length + 'レース）</p><table class="db-t"><tr><th>場</th><th>R</th><th>締切</th><th>枠</th><th>モーター</th></tr>' +
      rs.map(function (x) { return '<tr><td>' + esc(x[0].venue) + '</td><td>' + x[0].rno + 'R</td><td>' + esc(x[0].dl) + '</td><td>' + x[1].waku + '</td><td>' + esc(x[1].motor) + '号機</td></tr>'; }).join('') + '</table>' +
      links([['番組表で見る', 'today/#c' + rs[0][0].code], ['マイページでお気に入りに入れる', 'my/']]);
  }
  function plNext(reg) {
    var n = MY && MY.next && MY.next[reg], nm = nameOf(reg);
    if (!n) return '<p>' + esc(nm) + ' のこれからの斡旋（出場予定）は、いま入っていません。</p>' + links([['斡旋情報', 'assen/']]);
    return '<p><b>' + esc(nm) + '</b> の次の出場予定：<b>' + esc(n[0]) + '</b>　' + esc(md(n[1])) + '〜' + esc(md(n[2])) + (n[3] ? '（' + esc(n[3]) + '）' : '') + '</p>' + links([['斡旋情報', 'assen/']]);
  }
  function plStats(reg) {
    var p = PD[reg], a = p.all;
    return '<p><b>' + esc(p.nm) + '</b>（' + esc(reg) + '・' + esc(p.cls) + '）の成績　<span class="db-s">直近2年・' + a[0] + '走</span></p>' +
      '<table class="db-t"><tr><th>1着率</th><th>2連対率</th><th>3連対率</th><th>平均ST</th></tr><tr><td>' + pct(a[1]) + '</td><td>' + pct(a[2]) + '</td><td>' + pct(a[3]) + '</td><td>' + stf(a[4]) + '</td></tr></table>';
  }
  var AB1 = ['適性', 'ST', '差されにくさ', '捲られにくさ', '捲り差されにくさ', '入着力'], ABX = ['適性', 'ST', '差し', 'まくり', 'まくり差し', '入着力'];
  var KM = ['逃げ', '差し', 'まくり', 'まくり差し', '抜き', '恵まれ'];
  function plCourse(reg, course, waku) {
    var p = PD[reg], arr = waku ? p.wk : p.c, lab = waku ? '枠' : 'コース';
    var h = '<p><b>' + esc(p.nm) + '</b> の' + lab + '別の成績　<span class="db-s">直近2年' + (waku ? '' : '・進入したコース') + '</span></p><table class="db-t"><tr><th>' + lab + '</th><th>走数</th><th>1着率</th><th>2連対率</th><th>3連対率</th><th>平均ST</th></tr>';
    arr.forEach(function (s, i) {
      if (course && course !== i + 1) return;
      h += '<tr><td>' + (i + 1) + '</td><td>' + s[0] + '</td><td>' + pct(s[1]) + '</td><td>' + pct(s[2]) + '</td><td>' + pct(s[3]) + '</td><td>' + stf(s[4]) + '</td></tr>';
    });
    h += '</table>';
    if (course && !waku) {
      var k = p.km[course - 1];
      if (k && p.c[course - 1][0]) {
        var parts = []; k.forEach(function (v, i) { if (v) parts.push(KM[i] + ' ' + v); });
        if (parts.length) h += '<p class="db-s">' + course + 'コースの1着の決まり手：' + esc(parts.join('・')) + '</p>';
      }
      h += plAbility(reg, course);
    }
    if (arr.some(function (s) { return s[0] && s[0] < 10; })) h += '<p class="db-s">走数が少ない' + lab + 'は、数字が振れやすいので参考ていどに見てください。</p>';
    return h;
  }
  function plAbility(reg, only) {
    var p = PD[reg];
    var h = '<p><b>' + esc(p.nm) + '</b> の能力ランク　<span class="db-s">直近2年・全選手の中の順位（S〜F）</span></p><table class="db-t"><tr><th>コース</th><th>走数</th><th>適性</th><th>ST</th><th>差/守1</th><th>まくり/守2</th><th>まくり差し/守3</th></tr>';
    p.ab.forEach(function (a, i) {
      if (only && only !== i + 1) return;
      if (!a) { h += '<tr><td>' + (i + 1) + '</td><td>0</td><td colspan="5">−</td></tr>'; return; }
      h += '<tr><td>' + (i + 1) + '</td><td>' + a[0] + '</td>' + a.slice(1, 6).map(function (r) { return '<td class="rk rk-' + esc(String(r).replace('+', 'p')) + '">' + esc(r) + '</td>'; }).join('') + '</tr>';
    });
    h += '</table><p class="db-s">1コースの3つは守り（差されにくさ・捲られにくさ・捲り差されにくさ）。そのコースが10走未満は「−」。</p>';
    if (p.aa && !only) h += '<p>総合（全コース）：入着力 <b>' + esc(p.aa[1]) + '</b>・ST <b>' + esc(p.aa[2]) + '</b>・イン守り <b>' + esc(p.aa[6]) + '</b>（' + p.aa[0] + '走）</p>';
    return h;
  }
  function plCard(reg) {
    var h = plStats(reg), rs = racesOf(reg);
    if (rs.length) h += '<p>' + esc(dayLabel()) + '：' + rs.map(function (x) { return esc(x[0].venue) + ' ' + x[0].rno + 'R（' + x[1].waku + '枠・締切 ' + esc(x[0].dl) + '）'; }).join('、') + '</p>';
    else if (MY && MY.next && MY.next[reg]) { var n = MY.next[reg]; h += '<p>次の出場予定：' + esc(n[0]) + ' ' + esc(md(n[1])) + '〜' + esc(md(n[2])) + '</p>'; }
    var nm = PD[reg].nm;
    return h + links([['データバンクで見る', 'seiseki/#r' + reg]]) + chips([nm + ' のコース別成績', nm + ' の能力ランク', nm + ' の今日の出走', nm + ' の次の斡旋']);
  }
  function answerPlayer(o) { return needP([o.pl]).then(function () { return answerPlayer2(o); }); }
  function answerPlayer2(o) {
    var q = o.q, iw = D.iw;
    if (has(q, iw.assen) && !has(q, ['今日'])) return plNext(o.pl);
    if (has(q, iw.today)) return plToday(o.pl);
    if (!PD[o.pl]) return plToday(o.pl) + '<p class="db-s">この選手は直近2年の成績のデータがありません。</p>';
    if (has(q, iw.ability)) return plAbility(o.pl, o.course);
    if (o.course || has(q, iw.course)) return plCourse(o.pl, o.course, o.waku);
    if (has(q, iw.stats)) return plStats(o.pl) + links([['データバンクで見る', 'seiseki/#r' + o.pl]]);
    return plCard(o.pl);
  }

  // 場
  function venRaces(v) { return MY ? MY.races.filter(function (r) { return r.venue === v; }).sort(function (a, b) { return a.rno - b.rno; }) : []; }
  function venToday(v) {
    var rs = venRaces(v);
    if (!rs.length) {
      var m = D.VL[v];
      return '<p>' + esc(v) + ' は ' + esc(dayLabel()) + ' の開催がありません。</p>' + (m && m[0] ? '<p class="db-s">いちばん新しい節：' + esc(m[0]) + '（' + esc(m[1]) + '〜' + esc(m[2]) + '）</p>' : '') + links([['開催一覧', 'venues/'], ['斡旋情報（これからの節）', 'assen/']]);
    }
    return '<p><b>' + esc(v) + '</b> の ' + esc(dayLabel()) + ' のレース</p><table class="db-t"><tr><th>R</th><th>締切</th><th>レース名</th></tr>' +
      rs.map(function (r) { return '<tr><td><a href="' + esc(href('today/#c' + r.code)) + '">' + r.rno + 'R</a></td><td>' + esc(r.dl) + '</td><td>' + esc(r.name) + '</td></tr>'; }).join('') + '</table>' +
      links([['番組表で見る', 'today/#c' + rs[0].code], ['24場情報', 'seiseki/#v' + v]]);
  }
  function venRace(v, rno) {
    var r = venRaces(v).filter(function (x) { return x.rno === rno; })[0];
    if (r) return needP(r.e.map(function (e) { return e.reg; })).then(function () { return venRace2(v, rno, r); });
    return '<p>' + esc(v) + ' ' + rno + 'R は ' + esc(dayLabel()) + ' の番組表にありません。</p>' + chips([v + ' ' + rno + 'R の結果', v + ' の今日のレース']);
  }
  function venRace2(v, rno, r) {
    var h = '<p><b>' + esc(v) + ' ' + rno + 'R</b>　' + esc(r.name) + '　締切 ' + esc(r.dl) + '</p><table class="db-t"><tr><th>枠</th><th>選手</th><th>級</th><th>モーター</th><th>その枠の1着率</th></tr>';
    r.e.forEach(function (e) {
      var p = PD[e.reg], s = p && p.wk[e.waku - 1];
      h += '<tr><td class="wk wk' + e.waku + '">' + e.waku + '</td><td>' + esc(p ? p.nm : e.name) + '</td><td>' + esc(e.cls) + '</td><td>' + esc(e.motor) + '</td><td>' + (s && s[0] ? pct(s[1]) + '<span class="db-s">（' + s[0] + '走）</span>' : '−') + '</td></tr>';
    });
    return h + '</table><p class="db-s">1着率は直近2年のその枠の成績です。予想はしていません。</p>' + links([['番組表で見る', 'today/#c' + r.code], ['Boat Board（会員）', 'race/']]);
  }
  function venResult(v, rno, o) {
    var days = (D.resDays || []).slice().sort().reverse();
    var day = days[0];
    if (!day) return '<p>結果のデータがありません。</p>';
    return needRes(day).then(function (R) {
      var V0 = R && R[v];
      if (!V0) return '<p>' + esc(md(day)) + ' の ' + esc(v) + ' の結果はありません（開催が無かった日かもしれません）。</p>' + links([['レース結果', 'seiseki/?sn=result']]);
      var note = (MY && MY.date === day) ? '' : '<p class="db-s">結果は夜にまとめて入ります。いちばん新しい ' + esc(md(day)) + ' の結果です。</p>';
      var rows = V0.r.filter(function (x) { return !rno || x[0] === rno; });
      if (!rno) {
        return note + '<p><b>' + esc(md(day)) + ' ' + esc(v) + '</b>　' + esc(V0.t) + ' ' + esc(V0.d) + '</p><table class="db-t"><tr><th>R</th><th>3連単</th><th>払戻</th><th>決まり手</th></tr>' +
          rows.map(function (x) { var t = x[8] && x[8].t3; return '<tr><td>' + x[0] + 'R</td><td>' + esc(t ? t[0] : '−') + '</td><td>' + (t ? t[1].toLocaleString() + '円' : '−') + '</td><td>' + esc(x[7] || '') + '</td></tr>'; }).join('') +
          '</table>' + links([['レース結果', 'seiseki/#d' + day + '|' + v]]);
      }
      var x = rows[0];
      if (!x) return note + '<p>' + esc(md(day)) + ' の ' + esc(v) + ' ' + rno + 'R の結果はありません。</p>';
      var pay = x[8] || {}, h = note + '<p><b>' + esc(md(day)) + ' ' + esc(v) + ' ' + rno + 'R</b>　' + esc(x[1]) + '　決まり手：' + esc(x[7] || '−') + '</p>';
      h += '<table class="db-t"><tr><th>着</th><th>枠</th><th>選手</th><th>コース</th><th>ST</th></tr>' + x[9].map(function (e) { return '<tr><td>' + esc(e[0]) + '</td><td class="wk wk' + e[1] + '">' + e[1] + '</td><td>' + esc(String(e[3]).replace(/\s/g, '')) + '</td><td>' + esc(e[7]) + '</td><td>' + (e[8] == null || e[8] === '' ? '−' : (+e[8]).toFixed(2)) + '</td></tr>'; }).join('') + '</table>';
      var P2 = [['3連単', pay.t3], ['3連複', pay.f3], ['2連単', pay.t2], ['2連複', pay.f2], ['単勝', pay.tan]];
      h += '<table class="db-t"><tr><th>券種</th><th>組</th><th>払戻</th></tr>' + P2.filter(function (p) { return p[1]; }).map(function (p) { return '<tr><td>' + p[0] + '</td><td>' + esc(p[1][0]) + '</td><td>' + (+p[1][1]).toLocaleString() + '円' + (p[1][2] ? '<span class="db-s">（' + p[1][2] + '番人気）</span>' : '') + '</td></tr>'; }).join('') + '</table>';
      return h + links([['レース結果で見る', 'seiseki/#d' + day + '|' + v + '|' + rno]]);
    });
  }
  function venMotor(v, no) { return needM().then(function () { return venMotor2(v, no); }); }
  function venMotor2(v, no) {
    var m = MO[v], segs = m && m[String(no)];
    if (!segs) { var ks = Object.keys(m || {}).map(Number).sort(function (a, b) { return a - b; });
      return '<p>' + esc(v) + ' の ' + no + '号機のデータが見つかりませんでした。' + (ks.length ? esc(v) + ' のモーターは ' + ks[0] + '〜' + ks[ks.length - 1] + '号機です。' : '') + '</p>' + links([['モーター情報', 'seiseki/?sn=motor']]); }
    if (false) return '' + links([['モーター情報', 'seiseki/?sn=motor']]);
    var h = '<p><b>' + esc(v) + ' ' + no + '号機</b> の直近の節</p><table class="db-t"><tr><th>節</th><th>走数</th><th>2連対率</th><th>3連対率</th><th>乗った選手</th></tr>';
    segs.forEach(function (s) { h += '<tr><td>' + esc(s[0]) + '<span class="db-s">（' + esc(s[1]) + '）</span></td><td>' + s[2] + '</td><td>' + pct(s[3]) + '</td><td>' + pct(s[4]) + '</td><td>' + esc(s[5].join('・')) + '</td></tr>'; });
    h += '</table>';
    var today = venRaces(v).filter(function (r) { return r.e.some(function (e) { return +e.motor === no; }); });
    if (today.length) h += '<p>' + esc(dayLabel()) + '：' + today.map(function (r) { var e = r.e.filter(function (e) { return +e.motor === no; })[0]; return r.rno + 'R（' + esc(nameOf(e.reg)) + '）'; }).join('、') + '</p>';
    return h + links([['モーター情報で見る', 'seiseki/#m' + v + '|' + no], ['出場モーター', 'kmotors/']]);
  }
  function venInfo(v) {
    return needSearch().then(function () {
      var hit = S.filter(function (s) { return s[0].indexOf(v) >= 0 && s[0].indexOf('コラム') === 0; }).slice(0, 2);
      var h = '<p><b>' + esc(v) + '</b> の場の特徴は、データバンクの24場情報（コース別の成績・決まり手）と、コラムの24場ガイドで見られます。</p>';
      hit.forEach(function (s) { h += '<blockquote class="db-q"><b>' + esc(s[0].replace('コラム：', '')) + '</b><br>' + esc(s[1].slice(0, 160)) + '…</blockquote>'; });
      return h + links([['24場情報', 'seiseki/#v' + v]].concat(hit.length ? [['記事を読む', hit[0][2]]] : []));
    });
  }
  function answerVenue(o) {
    var q = o.q, iw = D.iw;
    if (o.mno) return venMotor(o.ven, o.mno);
    if (has(q, iw.result)) return venResult(o.ven, o.rno, o);
    if (o.rno) return venRace(o.ven, o.rno);
    if (has(q, iw.venueinfo) || has(q, ['1コース', 'イン', '強い', '荒れ'])) return venInfo(o.ven);
    return venToday(o.ven);
  }

  function kaisai() {
    if (!MY) return '<p>今日の開催のデータを読めませんでした。</p>' + links([['開催一覧', 'venues/']]);
    var by = {}; MY.races.forEach(function (r) { (by[r.venue] = by[r.venue] || []).push(r); });
    var vs = Object.keys(by).sort(function (a, b) { return by[a][0].jcd - by[b][0].jcd; });
    return '<p>' + esc(dayLabel()) + ' の開催（' + vs.length + '場）</p><table class="db-t"><tr><th>場</th><th>1R締切</th><th>最終R締切</th></tr>' +
      vs.map(function (v) { var rs = by[v].sort(function (a, b) { return a.rno - b.rno; }); return '<tr><td><a href="' + esc(href('today/#c' + rs[0].code)) + '">' + esc(v) + '</a></td><td>' + esc(rs[0].dl) + '</td><td>' + esc(rs[rs.length - 1].dl) + '</td></tr>'; }).join('') +
      '</table>' + links([['開催一覧', 'venues/']]);
  }
  function nextRaces() {
    if (!MY) return '<p>今日のレースのデータを読めませんでした。</p>';
    var now = new Date(), hm = ('0' + now.getHours()).slice(-2) + ':' + ('0' + now.getMinutes()).slice(-2);
    var td = '' + now.getFullYear() + ('0' + (now.getMonth() + 1)).slice(-2) + ('0' + now.getDate()).slice(-2);
    var rs = MY.races.slice();
    if (MY.date === td) rs = rs.filter(function (r) { return r.dl >= hm; });
    rs.sort(function (a, b) { return a.dl < b.dl ? -1 : a.dl > b.dl ? 1 : 0; });
    if (!rs.length) return '<p>今日のレースはすべて締め切りました。</p>' + links([['番組表（翌日分は夜に出ます）', 'today/']]);
    return '<p>' + (MY.date === td ? '次に締切のレース' : esc(dayLabel()) + ' の早い順') + '</p><table class="db-t"><tr><th>締切</th><th>場</th><th>R</th></tr>' +
      rs.slice(0, 6).map(function (r) { return '<tr><td>' + esc(r.dl) + '</td><td>' + esc(r.venue) + '</td><td><a href="' + esc(href('today/#c' + r.code)) + '">' + r.rno + 'R</a></td></tr>'; }).join('') + '</table>';
  }

  // よくある質問・用語・ページ
  function faqAns(f) { return '<p>' + esc(f.a) + '</p>' + links(f.l); }
  function faqScore(q) {
    var best = null, bs = 0;
    D.faq.forEach(function (f) { var s = 0; f.k.forEach(function (k) { if (q.indexOf(norm(k)) >= 0) s += norm(k).length >= 3 ? 2 : 1; }); if (s > bs) { bs = s; best = f; } });
    return [best, bs];
  }
  function termOf(q) { q = hira(q).replace(/(とは|ってなに|って何|ってなん|って|の意味|意味|はなに|は何|なに|何|\?)+$/, ''); for (var i = 0; i < TERMS.length; i++) if (q.indexOf(TERMS[i][1]) >= 0 && (TERMS[i][1].length > 1 || q === TERMS[i][1])) return D.terms[TERMS[i][0]]; return null; }
  function termAns(t) { return '<p><b>' + esc(t[0]) + '</b>：' + esc(t[2]) + '</p>'; }
  function pageOf(q) {
    var best = null, bs = 0;
    D.pages.forEach(function (p) { var s = 0; p[4].forEach(function (k) { if (q.indexOf(norm(k)) >= 0) s += norm(k).length; }); if (s > bs) { bs = s; best = p; } });
    return best;
  }
  function pageAns(p) { return '<p><b>' + esc(p[0]) + '</b>' + (p[2] ? '（会員）' : '') + '：' + esc(p[3]) + '</p>' + links([[p[0] + ' を開く', p[1]]]); }

  // サイト内検索（2文字ずつの重なりで近い文を探す）
  function grams(s) { var g = {}; for (var i = 0; i < s.length - 1; i++) g[s.substr(i, 2)] = 1; return g; }
  function search(q) {
    return needSearch().then(function () {
      var qq = q; FILL.forEach(function (w) { qq = qq.split(norm(w)).join(''); });
      var g = Object.keys(grams(qq)); if (!g.length) return null;
      var sc = S.map(function (s, i) { var t = norm(s[0] + s[1]), n = 0; g.forEach(function (x) { if (t.indexOf(x) >= 0) n++; }); return [n / g.length, i]; })
        .filter(function (x) { return x[0] >= 0.6; }).sort(function (a, b) { return b[0] - a[0]; });
      var seen = {}, out = [];
      sc.forEach(function (x) { var s = S[x[1]]; if (!seen[s[2]] && out.length < 3) { seen[s[2]] = 1; out.push(s); } });
      if (!out.length) return null;
      return '<p>サイトの中から近い説明を探しました。</p>' + out.map(function (s) { return '<blockquote class="db-q"><b>' + esc(s[0]) + '</b><br>' + esc(s[1].slice(0, 140)) + (s[1].length > 140 ? '…' : '') + '<br><a href="' + esc(href(s[2])) + '">開く ›</a></blockquote>'; }).join('');
    });
  }

  var EX = ['今日の開催', '次に締切のレース', '峰竜太の成績', '住之江 12R', '桐生の特徴', '3連単とは', '会員になると何が見られる？'];
  function answer(raw) {
    var o = parse(raw), q = o.q, iw = D.iw;
    if (!q) return help();
    var meaning = /とは|って何|ってなに|意味|って$|\?$/.test(q);
    if (o.yomiPart && (termOf(o.rest) || faqScore(o.rest)[1] >= 1 || pageOf(o.rest))) { o.pl = null; o.cand = null; }   // 「かど」などは用語を先に
    if (o.pl) return answerPlayer(o);
    if (o.cand) {
      if (o.cand.length > 12) return '<p>当てはまる選手が ' + o.cand.length + '人います。もう少し名前を入れてください（フルネームか登録番号）。</p>';
      return '<p>どの選手ですか？</p>' + chips(o.cand.map(function (r) { var sfx = o.rest ? q.split(o.rest).join('') : ''; return D.N[r][0] + (sfx ? ' ' + sfx : ''); }));
    }
    var t = termOf(q);
    if (t && meaning && !o.ven) return termAns(t);
    var f = faqScore(q);
    if (f[0] && f[1] >= 2 && !o.ven) { var p0 = pageOf(q); return faqAns(f[0]) + (p0 && !f[0].l.some(function (l) { return l[1] === p0[1]; }) && p0[4].some(function (k) { return norm(k).length >= 3 && q.indexOf(norm(k)) >= 0; }) ? pageAns(p0) : ''); }
    if (o.ven) return answerVenue(o);
    if (has(q, iw.next) || (has(q, iw.deadline) && q.length <= 8)) return nextRaces();
    if (has(q, ['今日の開催', '開催', 'やってる', 'どこでやって'])) return kaisai();
    var p = pageOf(q);
    if (f[0] && f[1] >= 1) return faqAns(f[0]) + (p && !f[0].l.some(function (l) { return l[1] === p[1]; }) ? pageAns(p) : '');
    if (t) return termAns(t) + (p ? pageAns(p) : '');
    if (p) return pageAns(p);
    return search(q).then(function (h) {
      logQ(raw, h ? 'search' : 'none');
      return h || ('<p>うまく読み取れませんでした。選手の名前（漢字・ひらがな）・場の名前・「住之江 12R」のように入れてみてください。</p>' + chips(EX));
    });
  }
  function help() {
    return '<p>Discovery のデータから、選手・場・レース・用語・サイトの使い方にお答えします。予想や買い目はお答えしていません。</p>' + chips(EX) +
      (QURL ? '<p class="db-s" style="margin-top:8px">答えられなかった質問は、答えを増やすために質問の文だけを記録します（お名前などは記録しません）。</p>' : '');
  }

  // 入れている途中の候補
  function suggest(raw) {
    var q = norm(raw), out = [];
    if (!q || !D) return out;
    var o = parse(raw);
    if (o.pl) { var nm = D.N[o.pl][0]; [' の成績', ' のコース別成績', ' の能力ランク', ' の今日の出走', ' の次の斡旋'].forEach(function (s) { out.push(nm + s); }); }
    else if (o.cand) o.cand.slice(0, 6).forEach(function (r) { out.push(D.N[r][0]); });
    if (o.ven && out.length < 6) {
      var v = o.ven;
      (o.rno ? [v + ' ' + o.rno + 'R', v + ' ' + o.rno + 'R の結果'] : [v + ' の今日のレース', v + ' 12R', v + ' の結果', v + ' の特徴']).forEach(function (s) { out.push(s); });
    }
    if (out.length < 6) D.faq.forEach(function (f) { if (out.length < 6 && f.k.some(function (k) { var nk = norm(k); return nk.indexOf(q) === 0 || (q.length >= 2 && q.indexOf(nk) >= 0); })) out.push(f.q); });
    if (out.length < 6) D.terms.forEach(function (t) { if (out.length < 6 && norm(t[0]).indexOf(q) === 0) out.push(t[0] + 'とは'); });
    return out.slice(0, 6);
  }

  // ── 画面
  var CSS = '.db-fab{position:fixed;right:16px;bottom:20px;z-index:9990;display:flex;align-items:center;gap:6px;padding:10px 14px;border:0;border-radius:999px;background:var(--ds-navy,#14284b);color:#fff;font:700 13px/1 "Noto Sans JP",sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.25);cursor:pointer}' +
    '.db-fab svg{width:18px;height:18px}' +
    '@media (max-width:899px){.db-fab{bottom:calc(76px + env(safe-area-inset-bottom));right:12px;padding:10px 12px}}' +
    '.db-pn{position:fixed;right:16px;bottom:20px;z-index:9991;width:380px;max-width:calc(100vw - 24px);height:min(620px,calc(100vh - 40px));display:flex;flex-direction:column;background:#fff;border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.3);font:14px/1.6 "Noto Sans JP",sans-serif;color:#1b2333;overflow:hidden}' +
    '@media (max-width:899px){.db-pn{left:0;right:0;bottom:0;width:auto;max-width:none;height:82vh;height:82dvh;border-radius:14px 14px 0 0}}' +
    '.db-pn[hidden]{display:none}.db-hd{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--ds-navy,#14284b);color:#fff;font-weight:700}' +
    '.db-hd small{font-weight:400;opacity:.8;margin-left:6px;font-size:11px}.db-hd button{background:none;border:0;color:#fff;font-size:20px;cursor:pointer;line-height:1}' +
    '.db-ms{flex:1;overflow:auto;padding:12px;background:#f4f6fa}.db-m{margin:0 0 10px;max-width:92%}.db-m p{margin:0 0 6px}' +
    '.db-u{margin-left:auto;background:var(--ds-navy,#14284b);color:#fff;padding:8px 12px;border-radius:12px 12px 2px 12px;width:fit-content}' +
    '.db-b{background:#fff;padding:10px 12px;border-radius:12px 12px 12px 2px;box-shadow:0 1px 2px rgba(0,0,0,.08)}' +
    '.db-t{border-collapse:collapse;width:100%;margin:4px 0 8px;font-size:12px}.db-t th,.db-t td{border-bottom:1px solid #e3e7ef;padding:4px 5px;text-align:left;white-space:nowrap}.db-t th{color:#5b6475;font-weight:500;background:#f7f8fb}' +
    '.db-b{overflow-x:auto}.db-s{color:#6b7385;font-size:11px}.db-ln{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.db-ln a{font-size:12px;color:var(--ds-navy,#14284b);font-weight:700;text-decoration:none;border:1px solid #cfd6e4;border-radius:999px;padding:3px 10px}' +
    '.db-ch{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.db-ch button{font:12px "Noto Sans JP",sans-serif;background:#eef2f9;border:1px solid #d5dcea;border-radius:999px;padding:4px 10px;cursor:pointer;color:#1b2333}' +
    '.db-q{margin:6px 0;padding:6px 10px;border-left:3px solid #cfd6e4;background:#f7f8fb;font-size:12px}.db-q a{color:var(--ds-navy,#14284b);font-weight:700}' +
    '.db-sg{display:flex;flex-wrap:wrap;gap:6px;padding:6px 10px 0;background:#fff}.db-sg:empty{display:none}.db-sg button{font:12px "Noto Sans JP",sans-serif;background:#fff;border:1px solid #cfd6e4;border-radius:999px;padding:3px 10px;cursor:pointer}' +
    '.db-in{display:flex;gap:6px;padding:8px 10px calc(8px + env(safe-area-inset-bottom));background:#fff;border-top:1px solid #e3e7ef}.db-in input{flex:1;min-width:0;font:16px "Noto Sans JP",sans-serif;padding:8px 10px;border:1px solid #cfd6e4;border-radius:8px}' +
    '.db-in button{border:0;border-radius:8px;background:var(--ds-navy,#14284b);color:#fff;font:700 13px "Noto Sans JP",sans-serif;padding:0 14px;cursor:pointer}' +
    '.db-in input{font-size:16px!important;touch-action:manipulation}' +
    // スマホは入力欄を見出しのすぐ下に出す（下だと見つけにくい・キーボードに隠れる）
    '@media (max-width:899px){.db-hd{order:0}.db-in{order:1;padding:10px;border-top:0;border-bottom:1px solid #e3e7ef;background:#eef2f9}.db-in input{padding:10px 12px;border:2px solid var(--ds-navy,#14284b)}.db-in button{padding:0 16px}' +
    '.db-sg{order:2;padding:8px 10px;background:#eef2f9;border-bottom:1px solid #e3e7ef}.db-ms{order:3}}' +
    '.wk{font-weight:700;text-align:center}.wk1{background:#fff}.wk2{background:#222;color:#fff}.wk3{background:#e33;color:#fff}.wk4{background:#2a6fdb;color:#fff}.wk5{background:#f2d230}.wk6{background:#2a9d4b;color:#fff}' +
    '.rk{font-weight:700;text-align:center}.rk-S,.rk-SS{color:#c0262d}.rk-Ap,.rk-A{color:#d4631a}.rk-E,.rk-F{color:#8a93a5}';
  var ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>';
  var pn, ms, inp, sg;
  function add(cls, html) { var d = document.createElement('div'); d.className = 'db-m ' + cls; d.innerHTML = html; ms.appendChild(d); ms.scrollTop = ms.scrollHeight; return d; }
  function send(text) {
    text = String(text || '').trim(); if (!text) return;
    add('db-u', esc(text)); inp.value = ''; sg.innerHTML = '';
    var d = add('db-b', '<span class="db-s">さがしています…</span>');
    Promise.all([needData(), needMy()]).then(function () { return answer(text); }).then(function (h) { d.innerHTML = h; ms.scrollTop = ms.scrollHeight; },
      function () { d.innerHTML = '<p>データを読めませんでした。通信をお確かめのうえ、もう一度お試しください。</p>'; });
  }
  function open() {
    if (!pn) {
      var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
      pn = document.createElement('div'); pn.className = 'db-pn'; pn.setAttribute('role', 'dialog'); pn.setAttribute('aria-label', 'Discovery案内');
      pn.innerHTML = '<div class="db-hd"><span>Discovery案内<small>データで答えます</small></span><button type="button" aria-label="閉じる">×</button></div>' +
        '<div class="db-ms"></div><div class="db-sg"></div><form class="db-in"><input type="text" enterkeyhint="send" placeholder="例：峰竜太の成績／住之江 12R／3連単とは" aria-label="質問"><button type="submit">送る</button></form>';
      document.body.appendChild(pn);
      ms = pn.querySelector('.db-ms'); inp = pn.querySelector('input'); sg = pn.querySelector('.db-sg');
      pn.querySelector('.db-hd button').addEventListener('click', function () { pn.hidden = true; fab.hidden = false; zoomLock(false); });
      pn.querySelector('form').addEventListener('submit', function (e) { e.preventDefault(); send(inp.value); });
      pn.addEventListener('click', function (e) { var b = e.target.closest('button[data-q]'); if (b) send(b.getAttribute('data-q')); });
      var tm; inp.addEventListener('input', function () { clearTimeout(tm); tm = setTimeout(function () { needData().then(function () { sg.innerHTML = suggest(inp.value).map(function (s) { return '<button type="button" data-q="' + esc(s) + '">' + esc(s) + '</button>'; }).join(''); }); }, 150); });
      add('db-b', help());
      needData(); needMy();
    }
    pn.hidden = false; fab.hidden = true; zoomLock(true); setTimeout(function () { inp.focus(); }, 50);
  }
  // 開いている間だけ、入力欄を押したときの自動の拡大を止める（閉じたら元に戻す）
  var vpOrig = null;
  function zoomLock(on) {
    var m = document.querySelector('meta[name="viewport"]');
    if (!m) { if (!on) return; m = document.createElement('meta'); m.name = 'viewport'; m.content = 'width=device-width, initial-scale=1'; document.head.appendChild(m); }
    if (on) { if (vpOrig === null) vpOrig = m.getAttribute('content') || ''; m.setAttribute('content', vpOrig.replace(/,?\s*maximum-scale=[^,]*/i, '') + ', maximum-scale=1'); }
    else if (vpOrig !== null) { m.setAttribute('content', vpOrig); vpOrig = null; }
  }
  var fab;
  function init() {
    if (document.querySelector('.db-fab')) return;
    var st = document.createElement('style'); st.textContent = CSS.split('.db-pn{')[0]; document.head.appendChild(st);
    fab = document.createElement('button'); fab.type = 'button'; fab.className = 'db-fab'; fab.innerHTML = ICON + '<span>案内</span>'; fab.setAttribute('aria-label', 'Discovery案内を開く');
    fab.addEventListener('click', open); document.body.appendChild(fab);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  window.DBOT = { answer: function (t) { return Promise.all([needData(), needMy()]).then(function () { return answer(t); }); }, suggest: function (t) { return needData().then(function () { return suggest(t); }); } };
})();
