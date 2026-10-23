(() => {
  const KP = window.__KP;
  const STATE = /^(ug|kata)|^(on|active|sel|selected|cur|current|is-active|open|closed|show|shown|hidden|hide|is-open|expanded|done|now|today|soon|live|fin)$/;
  const vis0 = e => e.getClientRects().length > 0 && !(e.closest('details:not([open])') && !(() => { const d = e.closest('details:not([open])'); const s = d.querySelector(':scope>summary'); return s && s.contains(e); })());
  const PNUM = /^[¥￥+\-−]?\d[\d,]*(?:\.\d+)?\s*(?:%|％|円|倍|回|位|本|件|走|勝|機|人|R|秒|号機|日|節|pt)?$/;
  const numeric = e => { if (!Array.prototype.some.call(e.childNodes, n => n.nodeType === 3 && n.nodeValue.trim())) return false; const t = (e.textContent || '').trim(); return t.length <= 14 && PNUM.test(t) && /\d/.test(t); };
  const part = e => { let s = e.tagName.toLowerCase(); if (s.indexOf(':') >= 0) return null; for (const c of e.classList) { if (!STATE.test(c) && /^[A-Za-z_][\w-]*$/.test(c)) s += '.' + c; } if (e.id && /^[A-Za-z][\w-]*$/.test(e.id) && !/\d{3}/.test(e.id)) s += '#' + e.id; if (numeric(e)) s += '.kataN'; return s; };
  const nth = e => { let k = 1; for (let x = e.previousElementSibling; x; x = x.previousElementSibling) if (x.tagName === e.tagName) k++; return k; };
  const part2 = e => { const s = part(e); if (!s) return null; if (s.replace('.kataN','').indexOf('.') >= 0 || s.indexOf('#') >= 0 || !e.parentElement) return s; let same = 0; for (const x of e.parentElement.children) if (x.tagName === e.tagName) same++; return same > 1 && same <= 8 ? s + ':nth-of-type(' + nth(e) + ')' : s; };
  const sig2 = (e, d) => { let s = part2(e); if (!s) return null; let p = e.parentElement; for (let i = 0; i < d; i++) { if (!p || p === document.documentElement) return null; const q = part2(p); if (!q) return null; s = q + '>' + s; p = p.parentElement; } return s; };
  const part3 = e => { let s = part(e); if (!s) return null; if (s.replace('.kataN','').indexOf('.') >= 0 || s.indexOf('#') >= 0) return s;
    const st = e.getAttribute('data-ko'); if (!st) return s;
    return s.replace(/^[a-z0-9]+/, t => t + '[data-ko="' + st + '"]'); };
  for (const e of document.body.querySelectorAll('*')) { if (e.classList.length || e.id) continue; const st = window.__ko0 && window.__ko0.has(e) ? window.__ko0.get(e) : e.getAttribute('style'); if (st && st.indexOf('"') < 0 && st.length <= 300) e.setAttribute('data-ko', st); }
  const sig3 = (e, d) => { let s = part3(e); if (!s) return null; let p = e.parentElement; for (let i = 0; i < d; i++) { if (!p || p === document.documentElement) return null; const q = part3(p); if (!q) return null; s = q + '>' + s; p = p.parentElement; } return s; };
  const sig = (e, d) => { let s = part(e); if (!s) return null; let p = e.parentElement; for (let i = 0; i < d; i++) { if (!p || p === document.documentElement) return null; const q = part(p); if (!q) return null; s = q + '>' + s; p = p.parentElement; } return s; };
  for (const e of document.body.querySelectorAll('*')) if (numeric(e)) e.classList.add('kataN');
  const paint = new Map();
  const vis = e => vis0(e) || ((paint.get(e) || {}).display === 'none' && e.parentElement && vis0(e.parentElement));
  const all = [...document.body.querySelectorAll('*')];
  for (const e of all) {
    const m = KP && KP.get(e.style); const o = {};
    if (m) for (let i = 0; i < e.style.length; i++) { const n = e.style[i]; if (e.style.getPropertyPriority(n) === 'important') o[n] = e.style.getPropertyValue(n); }
    for (const c of ['kataNum', 'kataNoBefore', 'kataNoAfter', 'kataTitle']) if (e.classList.contains(c)) o['@' + c] = '1';
    if (e.hasAttribute('data-kskip')) o['@kskip'] = '1';
    // 23) の飾りの細い帯（::before / ::after）は、第5版が見落とした分も、ここで同じ条件で拾う
    if (!e.closest('.kataNote,svg,canvas,script,style,.kataTitle,[data-kata-skip],[data-kskip]') && e.getClientRects().length) for (const ps of ['before', 'after']) {
      const q = getComputedStyle(e, '::' + ps); if (q.content === 'none' || q.content === 'normal') continue;
      const m = q.backgroundColor.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/); const a = m ? (m[4] == null ? 1 : +m[4]) : 0;
      const w = parseFloat(q.width), h = parseFloat(q.height);
      if (w > 0 && w <= 6 && h >= 14 && a > 0.3) o[ps === 'before' ? '@kataNoBefore' : '@kataNoAfter'] = '1';
    }
    if (Object.keys(o).length) paint.set(e, o);
  }
  const cache = new Map();
  let MAJ = 1; // 1＝全部一致を求める。0.8＝8割一致でよい（全部一致の規則が作れなかった部品だけ、あとで）
  function consistent(sel) {
    const ck = MAJ + '|' + sel;
    if (cache.has(ck)) return cache.get(ck);
    let ms; try { ms = [...document.querySelectorAll(sel)].filter(vis); } catch (x) { cache.set(ck, null); return null; }
    // 8割以上が同じ値なら、その値を規則にする（第5版でも、開いていた1つだけ塗り漏れていた、のような偶然の差を吸収する）。
    // 少ないとき（5個未満）と、状態で色が変わる部品（data-kskip）を含むときは全部一致を求める
    let res = null;
    if (ms.length) {
      const cnt = new Map(); let ks = false;
      for (const x of ms) { const o = paint.get(x) || {}; if (x.hasAttribute('data-kskip')) ks = true; for (const k in o) { const key = k + '\u0000' + o[k]; cnt.set(key, (cnt.get(key) || 0) + 1); } }
      res = {};
      const kc = new Map(); for (const [key, c] of cnt) { const k = key.split('\u0000')[0]; kc.set(k, (kc.get(k) || 0) + c); }
      // 全部一致（MAJ=1）か、半分以上が同じ値で塗られ、別の値で塗られた部品が無いとき（残りは第5版の塗り漏れとみなす）。状態で色が変わる部品が混じるときと5個未満は全部一致
      for (const [key, c] of cnt) { const [k, v] = key.split('\u0000'); const strictAll = MAJ >= 1 || ms.length < 5 || (ks && k !== '@kskip'); if (strictAll ? c >= ms.length : (c >= ms.length * 0.5 && kc.get(k) === c)) res[k] = v; } // 第5版の塗り漏れ（同じ部品の一部だけ塗られていない）は、そろえて塗る側に寄せる
      if (!Object.keys(res).length) res = null;
    }
    cache.set(ck, res); return res;
  }
  if (window.__CAND) { // 別の状態（タブ）で作った規則を、この状態でも確かめる。合わない規則は捨てる
    const rej = [];
    for (const [sel, o] of Object.entries(window.__CAND)) {
      let ms; try { ms = [...document.querySelectorAll(sel)].filter(vis); } catch (x) { continue; }
      if (!ms.length) continue;
      let ks = ms.some(x => x.hasAttribute('data-kskip'));
      for (const [k, vv] of Object.entries(o)) {
        const v = vv[0], strict = vv[1];
        // 最初の状態で作った規則（strict=0）：別の値で塗られた部品が2割を超えたら捨てる（塗られていない部品は数えない。第5版は状態によって塗り漏れがあった）。
        // ほかの状態でだけ作れた規則（strict=1）：塗られていない部品も外れとして数える（推しの金の地が、ほかの状態の部品に付かないように）
        const bad = ms.filter(x => { const w = (paint.get(x) || {})[k]; return strict ? w !== v : (w !== undefined && w !== v); }).length;
        if (bad > (ks ? 0 : ms.length * 0.2)) rej.push([sel, k]);
      }
    }
    return { rej };
  }
  const rules = {}; let pairs = 0, cov = 0; const miss = [];
  const left = new Map();
  for (const [e, o] of paint) {
    if (!vis(e)) continue;
    const need = new Set(Object.keys(o)); pairs += need.size;
    for (const [fn, dmax] of [[sig, 4], [sig2, 6], [sig3, 5]]) for (let d = 0; d <= dmax && need.size; d++) {
      const s = fn(e, d); if (!s) break;
      const c = consistent(s); if (!c) continue;
      for (const k of [...need]) if (c[k] === o[k]) { (rules[s] = rules[s] || {})[k] = o[k]; need.delete(k); cov++; }
    }
    if (need.size) left.set(e, need);
  }
  MAJ = 0.8;
  for (const [e, need] of left) {
    const o = paint.get(e);
    for (const [fn, dmax] of [[sig, 4], [sig2, 6], [sig3, 5]]) for (let d = dmax; d >= 0 && need.size; d--) { // 8割一致は、狭い（深い）形から試す
      const s = fn(e, d); if (!s) continue;
      if (d < 2 && /^[a-z0-9]+(\.kataN)?$/.test(s.split('>').pop())) continue; // 半分一致で、ただの div や li のような広い形は使わない
      const c = consistent(s); if (!c) continue;
      for (const k of [...need]) if (c[k] === o[k]) { (rules[s] = rules[s] || {})[k] = o[k]; need.delete(k); cov++; }
    }
    if (need.size && miss.length < 40) miss.push(sig(e, 2) + ' || ' + sig3(e, 1) + ' n3=' + (()=>{try{const s3=sig3(e,1);const ms=[...document.querySelectorAll(s3)];return ms.length+'/'+ms.filter(vis).length+'/'+ms.filter(x=>(paint.get(x)||{})[[...need][0]]===o[[...need][0]]).length}catch(x){return 'E'}})() + ' :: ' + [...need].map(k => k + '=' + o[k]).join('; ') + ' :: n=' + (()=>{try{return document.querySelectorAll(sig(e,2)).length}catch(x){return -1}})());
  }
  // 塗られていない見える要素が、作った規則に当たってしまう件数（誤爆）
  return { pairs, cov, rules, els: all.length, miss };
})()
