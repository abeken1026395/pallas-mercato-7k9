/* 買い目の入力シート（2026-11-14 けん：見どころ・自分の記録から、場・日付・レースを選んで買い目を入れる。入力忘れを後から入れる）。
   出走表の「買い目を保存」と同じ形で、この端末の dz_bets に残す（{レースID:{v,j,h,r,d,b:[{t,k,ts,m?,s?,l?}],a,p,u}}）。
   締切後に入れた買い目には l:1 を付ける（画面には出さない・その分だけ消せる。締切前に保存した分は締切後は消せない）。
   場・日付・レースの一覧は ../racers/raceIndex.json（前日・当日・翌日）。
   使い方：dzKaime.open({j:"12", h:"20261114", r:5})。場の指定が無ければ直近に締切ったレースから。保存すると window に "dzbets" を送る。 */
(function () {
  if (window.dzKaime) return;
  var T = { "3t": ["3連単", 3, 1], "3f": ["3連複", 3, 0], "2t": ["2連単", 2, 1], "2f": ["2連複", 2, 0], "kk": ["拡連複", 2, 0], "tn": ["単勝", 1, 1], "fk": ["複勝", 1, 1] };
  var ORDER = ["3t", "3f", "2t", "2f", "kk", "tn", "fk"], POS = ["1着", "2着", "3着"];
  var LANE = { 1: ["#f4f4f4", "#0b1726"], 2: ["#000000", "#ffffff"], 3: ["#d82a33", "#ffffff"], 4: ["#2b6fdc", "#ffffff"], 5: ["#f2d02e", "#0b1726"], 6: ["#1f8540", "#ffffff"] };
  var IDX = null, IDXP = null, DLG = null;
  var S = { h: "", j: "", r: 0, t: "3t", m: "f", s: [[], [], []], msg: "", u: 100 };
  var UNITS = [100, 200, 500, 1000];

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function getO(k) { try { var v = JSON.parse(localStorage.getItem(k) || "{}"); return v && typeof v === "object" && !Array.isArray(v) ? v : {}; } catch (e) { return {}; } }
  function putO(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function ymd(off) { var n = new Date(Date.now() + 9 * 3600000 + (off || 0) * 86400000); return n.getUTCFullYear() + ("0" + (n.getUTCMonth() + 1)).slice(-2) + ("0" + n.getUTCDate()).slice(-2); }
  function dlMs(h, t) { var m = /^(\d{1,2}):(\d{2})$/.exec(t || ""); return m ? Date.UTC(+h.slice(0, 4), +h.slice(4, 6) - 1, +h.slice(6, 8), +m[1] - 9, +m[2]) : 0; }
  function rid() { return S.j + "_" + S.h + "_" + S.r; }
  function venue() { return IDX && IDX.days[S.h] && IDX.days[S.h][S.j] || null; }
  function dl() { var v = venue(); return v && v.r ? (v.r[String(S.r)] || "") : ""; }
  function closed() { var d = dlMs(S.h, dl()); return d ? Date.now() >= d : S.h < ymd(0); }
  function hasBox(t) { var d = T[t]; return !!(d && d[2] && d[1] > 1); }
  function rows() { return hasBox(S.t) && S.m === "b" ? 1 : T[S.t][1]; }
  function combos() {
    var d = T[S.t], c = d[1], out = [], s = S.s, num = function (a, b) { return a - b; }, i, j, k;
    var p = s[0].slice().sort(num);
    if (d[2] && c > 1 && S.m === "b") {
      for (i = 0; i < p.length; i++) for (j = 0; j < p.length; j++) { if (j === i) continue;
        if (c === 2) { out.push(p[i] + "-" + p[j]); continue; }
        for (k = 0; k < p.length; k++) if (k !== i && k !== j) out.push(p[i] + "-" + p[j] + "-" + p[k]); }
      return out;
    }
    if (d[2]) {
      var b = s[1].slice().sort(num), e = s[2].slice().sort(num);
      if (c === 1) return p.map(String);
      p.forEach(function (x) { b.forEach(function (y) { if (y === x) return;
        if (c === 2) { out.push(x + "-" + y); return; }
        e.forEach(function (z) { if (z !== x && z !== y) out.push(x + "-" + y + "-" + z); }); }); });
      return out;
    }
    for (i = 0; i < p.length; i++) for (j = i + 1; j < p.length; j++) {
      if (c === 2) { out.push(p[i] + "=" + p[j]); continue; }
      for (k = j + 1; k < p.length; k++) out.push(p[i] + "=" + p[j] + "=" + p[k]);
    }
    return out;
  }
  // 保存してある買い目を、出走表と同じ決まりで整える（形の違うものは捨てる）
  function cleanB(b) {
    return (Array.isArray(b) ? b : []).filter(function (x) { return x && typeof x === "object" && T[x.t] && Array.isArray(x.k); }).map(function (x) {
      var o = { t: x.t, k: x.k.filter(function (s) { return typeof s === "string" && /^[1-6]([-=][1-6]){0,2}$/.test(s); }), ts: +x.ts > 0 ? +x.ts : 0 };
      if (x.m === "b" && hasBox(x.t)) { o.m = "b"; o.s = (Array.isArray(x.s) ? x.s : []).filter(function (n) { return n >= 1 && n <= 6 && n === Math.floor(n); }); }
      if (x.l === 1) o.l = 1;
      if (okU(x.u)) o.u = x.u;
      return o;
    }).filter(function (o) { return o.k.length; });
  }
  function entryOf(e) {
    if (!e || typeof e !== "object" || Array.isArray(e)) return null;
    return { e: e, b: cleanB(e.b) };
  }
  function pvText(c) { return c.slice(0, 20).join("　") + (c.length > 20 ? "　ほか" + (c.length - 20) + "点" : ""); }
  function okU(n) { return typeof n === "number" && isFinite(n) && n >= 100 && n <= 1e7 && n % 100 === 0; }
  function yen(n) { return Number(n).toLocaleString("ja-JP") + "円"; }
  function nText(c) { if (!okU(S.u)) return "金額は100円単位で入れてください"; return c.length ? c.length + "点・" + yen(c.length * S.u) : "艇番を押して選ぶ"; }
  // 1点の金額（100円・200円・500円・1,000円か、ほかの金額）。最後に保存した金額を次も使う
  function amtHtml() {
    var cus = UNITS.indexOf(S.u) < 0;
    return '<div class="kz-amt"><span class="kz-ul" id="kzUl">1点の金額</span><div class="kz-us" role="group" aria-labelledby="kzUl">'
      + UNITS.map(function (n) { return '<button type="button" class="kz-u" data-kzu="' + n + '" aria-pressed="' + (n === S.u) + '">' + yen(n) + "</button>"; }).join("")
      + '</div><label class="kz-uo" for="kzU">ほかの金額<span class="kz-in"><input id="kzU" type="text" inputmode="numeric" autocomplete="off" maxlength="8" placeholder="100円単位" value="' + (cus ? S.u : "") + '"><span>円</span></span></label></div>';
  }
  function label(x) { return T[x.t][0] + (x.m === "b" ? "ボックス" : ""); }

  function loadIdx() {
    if (IDX) return Promise.resolve(IDX);
    if (IDXP) return IDXP;
    IDXP = fetch("/racers/raceIndex.json?_=" + ymd(0) + new Date().getUTCHours(), { cache: "no-store" }).then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (j) { if (!j || typeof j.days !== "object") throw 0; IDX = j; return j; })
      .catch(function (e) { IDXP = null; throw e; });
    return IDXP;
  }
  function days() { var y = ymd(-1); return Object.keys(IDX.days).filter(function (h) { return /^\d{8}$/.test(h) && h >= y; }).sort(); }
  function dayLabel(h) {
    var t = ymd(0), lab = h === t ? "本日" : h === ymd(-1) ? "前日" : h === ymd(1) ? "翌日" : "";
    return lab + " " + (+h.slice(4, 6)) + "/" + (+h.slice(6, 8));
  }
  function fix() {
    var ds = days();
    if (ds.indexOf(S.h) < 0) S.h = ds.indexOf(ymd(0)) >= 0 ? ymd(0) : (ds[0] || "");
    var vs = Object.keys(IDX.days[S.h] || {}).sort();
    if (vs.indexOf(S.j) < 0) S.j = vs[0] || "";
    var rs = Object.keys((venue() || {}).r || {}).map(Number).sort(function (a, b) { return a - b; });
    if (rs.indexOf(S.r) < 0) {
      var now = Date.now(), nx = rs.filter(function (r) { return dlMs(S.h, venue().r[String(r)]) > now; })[0];
      S.r = nx || rs[rs.length - 1] || 0;
    }
  }

  // 場の指定なしで開いたとき（自分の記録から）は、直近に締切ったレースを選んでおく（入れ忘れを入れるため）
  function pickRecent() {
    var now = Date.now(), best = 0;
    days().forEach(function (h) {
      Object.keys(IDX.days[h] || {}).forEach(function (j) {
        var r = (IDX.days[h][j] || {}).r || {};
        Object.keys(r).forEach(function (n) { var d = dlMs(h, r[n]); if (d && d <= now && d > best) { best = d; S.h = h; S.j = j; S.r = +n; } });
      });
    });
  }

  var CSS = ".kz{position:fixed;left:0;right:0;top:auto;bottom:0;margin:0 auto;width:100%;max-width:600px;max-height:92vh;padding:0;background:#13233a;color:#eef3f8;border:0;border-top:1px solid #2c3e55;border-radius:0;font-family:inherit}"
    + ".kz[open]{display:flex;flex-direction:column}.kz::backdrop{background:rgba(5,12,22,.72)}"
    + ".kz-h{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 8px 4px 16px;border-bottom:1px solid rgba(255,255,255,.09)}"
    + ".kz-h h2{font-size:16px;font-weight:700;margin:0;color:#eef3f8}"
    + ".kz-x{min-height:44px;min-width:64px;padding:0 8px;font-size:14px;color:#cdd7e0;background:none;border:0;cursor:pointer;font-family:inherit}"
    + ".kz-b{flex:1;overflow-y:auto;overscroll-behavior:contain;padding:16px}"
    + ".kz-sel{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:0 0 12px}"
    + ".kz-sel label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:#cdd7e0}"
    + ".kz-sel select{min-height:44px;padding:0 8px;font-size:16px;color:#eef3f8;background:#0b1726;border:1px solid #5c6f86;border-radius:0;font-family:inherit}"
    + ".kz-dl{font-size:13px;color:#cdd7e0;margin:0 0 12px}"
    + ".kz-ts{display:flex;flex-wrap:wrap;gap:4px;margin:0 0 12px}"
    + ".kz-t{min-height:44px;padding:0 12px;font-size:14px;font-weight:700;background:#13233a;color:#cdd7e0;border:1px solid #2c3e55;border-radius:0;cursor:pointer;font-family:inherit}"
    + ".kz-t[aria-pressed=true]{background:#eef3f8;color:#0b1726;border-color:#eef3f8}"
    + ".kz-row{display:grid;grid-template-columns:48px repeat(6,1fr);gap:4px;align-items:center;margin:0 0 4px}"
    + ".kz-pl{font-size:12px;color:#cdd7e0;white-space:nowrap}"
    + "@media (max-width:374px){.kz-sel{grid-template-columns:1fr 1fr}.kz-sel label:last-child{grid-column:1/-1}}"
    + "@media (max-width:374px){.kz-row{grid-template-columns:repeat(6,1fr)}.kz-pl{grid-column:1/-1}}"
    + ".kz-l{min-height:44px;font-size:16px;font-weight:700;background:#13233a;color:#cdd7e0;border:1px solid #2c3e55;border-radius:0;cursor:pointer;font-family:inherit}"
    + ".kz-l[aria-pressed=true]{background:var(--kc);color:var(--kt);border:2px solid #eef3f8}.kz-l:disabled{opacity:.3;cursor:default}"
    + ".kz-bx{display:inline-flex;align-items:center;gap:8px}.kz-bx::before{content:\"\";flex:none;width:14px;height:14px;border:2px solid currentColor;box-sizing:border-box}.kz-bx[aria-pressed=true]::before{background:#0b1726;box-shadow:inset 0 0 0 2px #eef3f8}"
    + ".kz-ft{position:sticky;bottom:-16px;z-index:1;margin:12px -16px 0;padding:8px 16px calc(12px + env(safe-area-inset-bottom));background:#13233a;border-top:1px solid #2c3e55}"
    + ".kz-amt{margin:12px 0 0}.kz-ul{display:block;font-size:12px;color:#cdd7e0;margin:0 0 4px}"
    + ".kz-us{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}"
    + ".kz-u{min-height:44px;padding:0 4px;font-size:14px;font-weight:700;background:#13233a;color:#cdd7e0;border:1px solid #2c3e55;border-radius:0;cursor:pointer;font-family:inherit;white-space:nowrap;font-variant-numeric:tabular-nums}"
    + ".kz-u[aria-pressed=true]{background:#eef3f8;color:#0b1726;border-color:#eef3f8}"
    + ".kz-uo{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0 0;font-size:13px;color:#cdd7e0}"
    + ".kz-in{display:flex;align-items:center;gap:6px}.kz-in input{width:8.5em;min-height:44px;padding:0 8px;font-size:16px;color:#eef3f8;background:#0b1726;border:1px solid #5c6f86;border-radius:0;font-family:inherit;text-align:right}"
    + ".kz-in input::placeholder{color:#8a9bb0}"
    + ".kz-pv{font-size:13px;color:#cdd7e0;line-height:1.5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}.kz-pv:empty{display:none}"
    + ".kz-fr{display:flex;align-items:center;gap:12px;margin:4px 0 0}.kz-n{flex:1;font-size:14px;color:#cdd7e0}"
    + ".kz-sv{min-height:44px;min-width:96px;padding:0 16px;font-size:16px;font-weight:700;background:#7fb4ff;color:#0b1726;border:0;border-radius:0;cursor:pointer;font-family:inherit}"
    + ".kz-sv:disabled{background:#2c3e55;color:#cdd7e0;cursor:default}"
    + ".kz-m{font-size:13px;color:#cdd7e0;margin:8px 0 0;line-height:1.6}"
    + ".kz-ls{list-style:none;margin:16px 0 0;padding:0;border-top:1px solid rgba(255,255,255,.09)}"
    + ".kz-ls li{display:grid;grid-template-columns:auto 1fr auto auto;gap:8px;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.09)}"
    + ".kz-st{font-size:12px;font-weight:700;color:#0b1726;background:#eef3f8;padding:3px 6px;white-space:nowrap}"
    + ".kz-k{font-size:14px;color:#eef3f8;line-height:1.5;overflow-wrap:anywhere}.kz-c{font-size:12px;color:#cdd7e0;white-space:nowrap;text-align:right;line-height:1.4;font-variant-numeric:tabular-nums}"
    + ".kz-d{min-height:44px;min-width:44px;font-size:12px;background:none;color:#cdd7e0;border:0;cursor:pointer;font-family:inherit}"
    + ".kz-open{display:flex;align-items:center;justify-content:center;width:100%;min-height:48px;margin:8px 0 0;padding:0 12px;font-size:14px;font-weight:700;color:#eef3f8;background:none;border:1px solid rgba(232,236,239,.32);border-radius:0;cursor:pointer;font-family:inherit}"
    + ".kz-go{display:flex;align-items:center;justify-content:space-between;min-height:44px;margin:12px 0 0;font-size:14px;color:#eef3f8;text-decoration:none;border-top:1px solid rgba(255,255,255,.09)}";

  function css() { if (!document.getElementById("kzCss")) { var st = document.createElement("style"); st.id = "kzCss"; st.textContent = CSS; document.head.appendChild(st); } }
  function ensure() {
    if (DLG) return DLG;
    css();
    DLG = document.createElement("dialog"); DLG.className = "kz"; DLG.setAttribute("aria-labelledby", "kzH");
    DLG.innerHTML = '<div class="kz-h"><h2 id="kzH">買い目を記録</h2><button type="button" class="kz-x" data-kz="x">閉じる</button></div><div class="kz-b" id="kzB"></div>';
    document.body.appendChild(DLG);
    DLG.addEventListener("click", onClick);
    DLG.addEventListener("change", onChange);
    DLG.addEventListener("input", function (ev) {
      if (ev.target.id !== "kzU") return;
      var v = ev.target.value.replace(/[^0-9]/g, "").slice(0, 8); if (v !== ev.target.value) ev.target.value = v;
      S.u = v === "" ? 100 : +v; sync();
    });
    DLG.addEventListener("click", function (ev) { if (ev.target === DLG) DLG.close(); });
    return DLG;
  }

  function draw() {
    var B = document.getElementById("kzB"); if (!B) return;
    if (!IDX) { B.innerHTML = '<p class="kz-m">' + (S.msg || "レースの一覧を読み込んでいます…") + "</p>"; return; }
    fix();
    var ds = days(), v = venue(), rs = Object.keys((v || {}).r || {}).map(Number).sort(function (a, b) { return a - b; });
    var h = '<div class="kz-sel">'
      + '<label>日付<select data-kz="h">' + ds.map(function (d) { return '<option value="' + d + '"' + (d === S.h ? " selected" : "") + ">" + esc(dayLabel(d)) + "</option>"; }).join("") + "</select></label>"
      + '<label>場<select data-kz="j">' + Object.keys(IDX.days[S.h] || {}).sort().map(function (j) { return '<option value="' + esc(j) + '"' + (j === S.j ? " selected" : "") + ">" + esc(IDX.days[S.h][j].n || j) + "</option>"; }).join("") + "</select></label>"
      + '<label>レース<select data-kz="r">' + rs.map(function (r) { return '<option value="' + r + '"' + (r === S.r ? " selected" : "") + ">" + r + "R " + esc(v.r[String(r)] || "") + "</option>"; }).join("") + "</select></label></div>";
    if (!v || !S.r) { B.innerHTML = h + '<p class="kz-m">この日の出走表がありません。</p>'; return; }
    var cl = closed();
    h += '<p class="kz-dl">' + esc((v.n || "") + " " + S.r + "R｜締切 " + (dl() || "—")) + (cl ? "（締切済み）" : "") + "</p>";
    h += '<div class="kz-ts">' + ORDER.map(function (k) { return '<button type="button" class="kz-t" data-kzt="' + k + '" aria-pressed="' + (k === S.t) + '">' + T[k][0] + "</button>"; }).join("") + "</div>";
    if (hasBox(S.t)) h += '<div class="kz-ts"><button type="button" class="kz-t kz-bx" data-kzm="1" aria-pressed="' + (S.m === "b") + '">ボックスで買う</button></div>';
    var n = rows(), i, ln;
    for (i = 0; i < n; i++) {
      var pl = n > 1 ? POS[i] : "選ぶ艇";
      h += '<div class="kz-row" role="group" aria-label="' + pl + '"><span class="kz-pl">' + pl + "</span>";
      for (ln = 1; ln <= 6; ln++) {
        var on = S.s[i].indexOf(ln) >= 0, c = LANE[ln];
        h += '<button type="button" class="kz-l" data-kzp="' + i + '" data-kzl="' + ln + '" aria-pressed="' + on + '" aria-label="' + (n > 1 ? pl + " " : "") + ln + '号艇" style="--kc:' + c[0] + ";--kt:" + c[1] + '">' + ln + "</button>";
      }
      h += "</div>";
    }
    h += amtHtml();
    var cmb = combos();
    h += '<div class="kz-ft"><div class="kz-pv" id="kzPv">' + esc(pvText(cmb)) + '</div><div class="kz-fr"><span class="kz-n" id="kzN" role="status">' + nText(cmb) + '</span><button type="button" class="kz-sv" data-kz="save"' + (cmb.length ? "" : " disabled") + ">保存</button></div></div>";
    if (S.msg) h += '<p class="kz-m" role="status">' + esc(S.msg) + "</p>";
    var en = entryOf(getO("dz_bets")[rid()]);
    if (en && en.b.length) {
      h += '<ul class="kz-ls" aria-label="このレースで保存した買い目">' + en.b.map(function (x, ix) {
        var can = !cl || x.l === 1;
        return '<li><span class="kz-st">' + esc(label(x)) + '</span><span class="kz-k">' + esc(x.m === "b" && Array.isArray(x.s) && x.s.length ? x.s.join("・") : x.k.join("　")) + '</span><span class="kz-c">' + x.k.length + "点" + (x.u ? "<br>" + esc(yen(x.k.length * x.u)) : "") + "</span>"
          + (can ? '<button type="button" class="kz-d" data-kzd="' + ix + '" aria-label="この買い目を消す">消す</button>' : "<span></span>") + "</li>";
      }).join("") + "</ul>";
      if (cl && en.b.some(function (x) { return x.l !== 1; })) h += '<p class="kz-m">締切前に保存した買い目は、締切後は消せません。</p>';
    }
    h += '<a class="kz-go" href="/racers/#v' + esc(S.j) + "r" + S.r + "d" + esc(S.h) + '"><span>このレースの出走表を開く</span><span aria-hidden="true">›</span></a>';
    B.innerHTML = h;
  }
  function sync() {
    var B = document.getElementById("kzB"); if (!B) return;
    Array.prototype.forEach.call(B.querySelectorAll("[data-kzl]"), function (el) {
      var i = +el.getAttribute("data-kzp"), ln = +el.getAttribute("data-kzl");
      el.setAttribute("aria-pressed", String(S.s[i].indexOf(ln) >= 0));
    });
    var cmb = combos();
    var pv = document.getElementById("kzPv"); if (pv) pv.textContent = pvText(cmb);
    var nn = document.getElementById("kzN"); if (nn) nn.textContent = nText(cmb);
    var sv = B.querySelector('[data-kz="save"]'); if (sv) sv.disabled = !cmb.length || !okU(S.u);
    Array.prototype.forEach.call(B.querySelectorAll("[data-kzu]"), function (el) { el.setAttribute("aria-pressed", String(+el.getAttribute("data-kzu") === S.u)); });
  }
  function save() {
    var cmb = combos(), v = venue(); if (!cmb.length || !v) return;
    var B = getO("dz_bets"), id = rid(), e = B[id] && typeof B[id] === "object" && !Array.isArray(B[id]) ? B[id] : { b: [], a: null, p: null };
    e.b = cleanB(e.b);
    e.v = v.n || ""; e.j = S.j; e.h = S.h; e.r = S.r; e.d = dl();
    var it = hasBox(S.t) && S.m === "b" ? { t: S.t, m: "b", s: S.s[0].slice().sort(function (a, b) { return a - b; }), k: cmb, ts: Date.now() } : { t: S.t, k: cmb, ts: Date.now() };
    if (closed()) it.l = 1;
    if (!okU(S.u)) return;
    it.u = S.u;
    // 合計の購入額を手で入れてあるレースは、この買い目の分を足す（自動の計算に任せているレースはそのまま）
    if (typeof e.a === "number" && isFinite(e.a)) e.a += cmb.length * S.u;
    e.b.push(it); B[id] = e;
    try { localStorage.setItem("dz_kaimeU", String(S.u)); } catch (x) {}
    if (!putO("dz_bets", B)) { S.msg = "保存できませんでした。端末の空き容量か、プライベートブラウズの設定を確かめてください。"; draw(); return; }
    var SK = getO("dz_skip"); if (SK[id]) { delete SK[id]; putO("dz_skip", SK); }
    S.s = [[], [], []]; S.msg = "保存しました。自分の記録の称号・傾向・収支に入ります。";
    draw(); fire();
  }
  function del(ix) {
    var B = getO("dz_bets"), id = rid(), e = B[id]; if (!e || typeof e !== "object") return;
    e.b = cleanB(e.b); if (!e.b[ix]) return;
    if (closed() && e.b[ix].l !== 1) return;
    if (e.b[ix].u && typeof e.a === "number" && isFinite(e.a)) e.a = Math.max(0, e.a - e.b[ix].k.length * e.b[ix].u);
    e.b.splice(ix, 1);
    if (!e.b.length && e.a == null && e.p == null) delete B[id]; else B[id] = e;
    putO("dz_bets", B); S.msg = ""; draw(); fire();
  }
  function fire() { try { window.dispatchEvent(new CustomEvent("dzbets")); } catch (e) {} }
  function onClick(ev) {
    var t = ev.target.closest ? ev.target.closest("button") : null; if (!t || !DLG.contains(t)) return;
    var a = t.getAttribute("data-kz");
    if (a === "x") { DLG.close(); return; }
    if (a === "save") { save(); return; }
    if (t.hasAttribute("data-kzt")) { var k = t.getAttribute("data-kzt"); if (k !== S.t) { S.t = k; S.s = [[], [], []]; S.msg = ""; draw(); } return; }
    if (t.hasAttribute("data-kzm")) { S.m = S.m === "b" ? "f" : "b"; S.s = [[], [], []]; S.msg = ""; draw(); return; }
    if (t.hasAttribute("data-kzl")) { var arr = S.s[+t.getAttribute("data-kzp")], ln = +t.getAttribute("data-kzl"), ix = arr.indexOf(ln); if (ix >= 0) arr.splice(ix, 1); else arr.push(ln); S.msg = ""; var m2 = DLG.querySelector(".kz-m[role=status]"); if (m2) m2.remove(); sync(); return; }
    if (t.hasAttribute("data-kzu")) { S.u = +t.getAttribute("data-kzu"); var ui = document.getElementById("kzU"); if (ui) ui.value = ""; sync(); return; }
    if (t.hasAttribute("data-kzd")) { del(+t.getAttribute("data-kzd")); return; }
  }
  function onChange(ev) {
    var a = ev.target.getAttribute && ev.target.getAttribute("data-kz"); if (!a) return;
    if (a === "h") { S.h = ev.target.value; S.j = ""; S.r = 0; }
    else if (a === "j") { S.j = ev.target.value; S.r = 0; }
    else if (a === "r") { S.r = +ev.target.value; }
    S.s = [[], [], []]; S.msg = ""; draw();
  }

  // ページに置いた <button class="kz-open" data-kzopen data-j data-h data-r> を押したら開く
  document.addEventListener("click", function (ev) {
    var b = ev.target && ev.target.closest ? ev.target.closest("[data-kzopen]") : null; if (!b) return;
    ev.preventDefault(); ev.stopPropagation();
    window.dzKaime.open({ j: b.getAttribute("data-j") || "", h: b.getAttribute("data-h") || "", r: b.getAttribute("data-r") || "" });
  }, true);
  if (document.head) css(); else document.addEventListener("DOMContentLoaded", css);

  window.dzKaime = {
    open: function (o) {
      o = o || {};
      ensure();
      if (/^\d{8}$/.test(o.h || "")) S.h = o.h;
      if (/^\d{2}$/.test(o.j || "")) S.j = o.j;
      S.r = +o.r >= 1 && +o.r <= 12 ? +o.r : 0;
      try { var lu = +localStorage.getItem("dz_kaimeU"); S.u = okU(lu) ? lu : 100; } catch (x) { S.u = 100; }
      var want = !/^\d{2}$/.test(o.j || "");
      S.s = [[], [], []]; S.msg = "";
      draw();
      try { DLG.showModal(); } catch (e) { DLG.setAttribute("open", ""); }
      loadIdx().then(function () { if (want) { pickRecent(); want = false; } S.msg = ""; draw(); }, function () { S.msg = "レースの一覧を読めませんでした。通信の良いところで開き直してください。"; draw(); });
    }
  };
})();
