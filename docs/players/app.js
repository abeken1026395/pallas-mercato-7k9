// 自動生成ファイル。手で編集しないこと。正本は scripts/players/app.jsx
const {
  useState,
  useMemo,
  useEffect
} = React;
/* ===== 選手データの取得 =====
   以前は index.html に全選手ぶんの選手データを静的埋め込みしていた。
   埋め込みをやめ、一覧・検索・ソートに要る core だけを先に取り、詳細パネル／
   支部傾向タブで初めて要る detail は後から取る。値は racerStats.json と同一で、
   表示される数字は埋め込み時代と1つも変わらない（期首時点の固定値）。
   取得パスは同ファイル内の既存 fetch（racerKimarite.csv / profileLite.json /
   ../data/playerMonthly.json / ../data/e30PlayerStats.json）と同じ作法にそろえる。
   docs/players/ からの相対パス・クエリ無し・r.ok を見て json() する。 */
const CORE_URL = "../data/racerStatsCore.json";
const DETAIL_URL = "../data/racerStatsDetail.json";
/* detail は「詳細を開く」「支部傾向タブ」の両方から要求される。連打やタブ往復で
   何度も取りに行かないよう、Promise をモジュールに1本だけ持って共有する。
   失敗したときは握った Promise を捨てて、次の操作でやり直せるようにする。 */
let DETAIL_P = null;
function loadDetail() {
  if (!DETAIL_P) {
    DETAIL_P = fetch(DETAIL_URL).then(r => r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))).then(j => {
      const m = j && j.players;
      if (!m) throw new Error("players が無い");
      return m;
    }).catch(e => {
      DETAIL_P = null;
      throw e;
    });
  }
  return DETAIL_P;
}
/* ===== 推しフォロー（出走表 template_racers.html と共有。キー br_oshi ／ 形式 [{toban,name}] ／ toban は文字列） ===== */
function lsGet(k, d) {
  try {
    var v = localStorage.getItem(k);
    return v ? JSON.parse(v) : d;
  } catch (e) {
    return d;
  }
}
function lsSet(k, v) {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch (e) {}
}
function loadOshi() {
  var a = lsGet("br_oshi", []);
  return Array.isArray(a) ? a : [];
}
function hasOshi(list, toban) {
  return list.some(function (o) {
    return o && String(o.toban) === String(toban);
  });
}
function nextOshi(list, toban, name) {
  if (hasOshi(list, toban)) return list.filter(function (o) {
    return o && String(o.toban) !== String(toban);
  });
  return [{
    toban: String(toban),
    name: name || ""
  }].concat(list); /* 出走表と同じ先頭追加 */
}
// 級別バッジ色（旧版踏襲: A1=赤系で目立たせる）
const RANK_BADGE = {
  "A1": "#e5484d",
  "A2": "#4593e5",
  "B1": "#7d8da0",
  "B2": "#5a6878"
};
const RANK_LINE = {
  "A1": "#e5484d",
  "A2": "#4593e5",
  "B1": "#7d8da0",
  "B2": "#3a4550"
};

// 登番→選手 の逆引き（note内リンク・関係性表示に使う）
// core の到着後に fillNoMap で中身を入れる。renderNote / extractRelations /
// inverseRole / buildRelIndex はこのオブジェクトの参照を閉じ込めているので、
// 差し替えずに同じ入れ物へ詰めること（新しい {} を代入すると4関数が空を見る）。
// 参照するのは name / branch / rank / female だけで、いずれも core に入っている。
const NO_MAP = {};
function fillNoMap(list) {
  for (const k in NO_MAP) delete NO_MAP[k];
  list.forEach(p => {
    NO_MAP[p.no] = p;
  });
}
// note文中の「名前（登番）」を該当選手カードへのリンクに変換して描画。
// 登番で選手を確定し、直前の文字列がその選手名で終わっていれば名前だけをリンク化して
// 冗長な（登番）は落とす。名前が一致しなければ（登番）自体を小さなリンクにする。
function renderNote(text, jump) {
  if (!text) return null;
  const re = /[（(](\d{4})[）)]/g;
  const out = [];
  let last = 0,
    m,
    idx = 0;
  const linkStyle = {
    color: "#5ec8e6",
    cursor: "pointer",
    fontWeight: 700,
    borderBottom: "1px dotted #5ec8e688"
  };
  while (m = re.exec(text)) {
    const no = m[1],
      pl = NO_MAP[no];
    if (!pl) {
      continue;
    } // 現役に居ない登番（引退・誤記）は素通し
    const before = text.slice(last, m.index);
    const nm = pl.name,
      title = "→ " + nm + "（" + pl.branch + "・" + pl.rank + "）";
    const click = e => {
      e.stopPropagation();
      jump(no);
    };
    if (before.endsWith(nm)) {
      // 直前が選手名 → 名前だけリンク、（登番）は省略
      const pre = before.slice(0, before.length - nm.length);
      if (pre) out.push(pre);
      out.push(/*#__PURE__*/React.createElement("span", {
        key: "lk" + idx,
        onClick: click,
        title: title,
        style: linkStyle
      }, nm));
    } else {
      out.push(before);
      out.push(/*#__PURE__*/React.createElement("span", {
        key: "lk" + idx,
        onClick: click,
        title: title,
        style: {
          ...linkStyle,
          fontSize: 11
        }
      }, "\uFF08", nm, "\uFF09"));
    }
    last = re.lastIndex;
    idx++;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

// noteから師匠/弟子/家族/同期の関係を抽出→チップ表示用。
// ①名前（登番）の名前部分をマスク（名前に含まれる父/夫/兄等の誤検出を防ぐ）
// ②同一文内で「名前に最も近い役割語」で判定（師匠語と名前が離れても拾える）
function extractRelations(note) {
  if (!note) return [];
  const pink = "#ff9ec4";
  const re = /[（(](\d{4})[）)]/g;
  let m;
  const toks = [];
  const arr = note.split("");
  while (m = re.exec(note)) {
    const no = m[1],
      pl = NO_MAP[no];
    if (!pl) continue;
    const before = note.slice(0, m.index);
    if (before.endsWith(pl.name)) for (let i = m.index - pl.name.length; i < m.index; i++) arr[i] = "＊"; // 名前をマスク
    toks.push({
      at: m.index,
      no,
      pl
    });
  }
  const masked = arr.join("");
  const out = [];
  const seen = new Set();
  const push = (role, color, no, name) => {
    const key = role + no;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({
      role,
      color,
      no,
      name
    });
  };
  for (const t of toks) {
    // 後方文脈（名前の直後）を優先判定：「Xに師事/門下」「Xが師匠」→Xが師匠、「Xの師匠」「Xを弟子」→Xが弟子
    const af = masked.slice(t.at + 6, t.at + 16);
    if (/^に師事|^に弟子入り|^門下|^が師匠|^が師と|^に師事/.test(af)) {
      push("師匠", "#d2a8ff", t.no, t.pl.name);
      continue;
    }
    if (/^の師匠|^を弟子|^の弟子/.test(af)) {
      push("弟子", "#7ee787", t.no, t.pl.name);
      continue;
    }
    let bf = masked.slice(0, t.at);
    const sb = Math.max(bf.lastIndexOf("。"), bf.lastIndexOf("！"), bf.lastIndexOf("？"));
    if (sb >= 0) bf = bf.slice(sb + 1); // 同一文に限定
    const c = [];
    const put = (pos, role, color) => {
      if (pos >= 0) c.push({
        pos,
        role,
        color
      });
    };
    put(bf.lastIndexOf("弟子"), "弟子", "#7ee787");
    put(Math.max(bf.lastIndexOf("師匠"), bf.lastIndexOf("師事")), "師匠", "#d2a8ff");
    put(bf.lastIndexOf("同期"), "同期", "#8faabe");
    let jf = -1;
    {
      const fm = /従(兄弟|姉妹|兄|姉|弟|妹)/g;
      let mm;
      while (mm = fm.exec(bf)) jf = mm.index;
    }
    put(jf, "親戚", "#ffd166");
    for (const kw of ["息子", "娘", "姉", "妹", "父", "母", "夫", "妻", "兄"]) {
      const p = bf.lastIndexOf(kw);
      if (p >= 0 && !(jf >= 0 && p >= jf && p <= jf + 2)) put(p, kw, pink);
    }
    // 単独の「弟」（弟子・従弟・師弟を除外）
    for (let i = bf.length - 1; i >= 0; i--) {
      if (bf[i] === "弟" && bf[i + 1] !== "子" && bf[i - 1] !== "従" && bf[i - 1] !== "師" && !(jf >= 0 && i >= jf && i <= jf + 2)) {
        put(i, "弟", pink);
        break;
      }
    }
    if (!c.length) continue;
    c.sort((a, b) => b.pos - a.pos);
    const r = c[0];
    push(r.role, r.color, t.no, t.pl.name);
  }
  return out;
}

// 役割→色。家族系は桃色に集約
const ROLE_COLOR = {
  "師匠": "#d2a8ff",
  "弟子": "#7ee787",
  "同期": "#8faabe",
  "親戚": "#ffd166"
};
function roleColor(role) {
  return ROLE_COLOR[role] || "#ff9ec4";
}
// あるnote所有者(owner)の役割から見た、相手カードに出すべき逆方向の役割を返す
function inverseRole(role, ownerNo) {
  const fem = NO_MAP[ownerNo] && NO_MAP[ownerNo].female; // owner=相手から見た人物
  switch (role) {
    case "師匠":
      return "弟子";
    // owner の師匠 → 相手から見て owner は弟子
    case "弟子":
      return "師匠";
    case "兄":
    case "姉":
      return fem ? "妹" : "弟";
    // 相手が兄/姉 → owner は年下のきょうだい
    case "弟":
    case "妹":
      return fem ? "姉" : "兄";
    case "夫":
      return "妻";
    case "妻":
      return "夫";
    case "父":
    case "母":
      return fem ? "娘" : "息子";
    // 相手が親 → owner は子
    case "息子":
    case "娘":
      return fem ? "母" : "父";
    // 相手が子 → owner は親
    case "親戚":
      return "親戚";
    case "同期":
      return "同期";
    default:
      return null;
  }
}
// 全プロフィールのnoteから関係グラフを構築（自分の記載＋他人の記載の逆方向を統合）
function buildRelIndex(prof) {
  const idx = {};
  const add = (owner, role, no) => {
    if (!NO_MAP[no] || owner === no) return;
    const arr = idx[owner] || (idx[owner] = []);
    if (arr.some(r => r.role === role && r.no === no)) return;
    arr.push({
      role,
      color: roleColor(role),
      no,
      name: NO_MAP[no].name
    });
  };
  for (const owner in prof) {
    const note = prof[owner] && prof[owner].note;
    if (!note) continue;
    for (const e of extractRelations(note)) {
      add(owner, e.role, e.no);
      const inv = inverseRole(e.role, owner);
      if (inv) add(e.no, inv, owner);
    }
  }
  // 表示順: 師匠→弟子→家族→親戚→同期
  const ord = {
    "師匠": 0,
    "弟子": 1,
    "夫": 2,
    "妻": 2,
    "父": 2,
    "母": 2,
    "息子": 2,
    "娘": 2,
    "兄": 2,
    "弟": 2,
    "姉": 2,
    "妹": 2,
    "親戚": 3,
    "同期": 4
  };
  for (const k in idx) idx[k].sort((a, b) => (ord[a.role] ?? 9) - (ord[b.role] ?? 9));
  return idx;
}
const KIM = [["nige", "逃げ", "#ffd166"], ["makuri", "まくり", "#4593e5"], ["sashi", "差し", "#3fb950"], ["makurizashi", "まくり差し", "#d29922"], ["nuki", "抜き", "#8957e5"], ["megumare", "恵まれ", "#56607a"]];
/* ===== 級別の推移（公式番組表 Bファイル 由来） =====
   rankHistory.json は「級別が変わった日」だけを持つ差分形式。
   [[日付,級別],...] の並びは昇順で、先頭がその選手の初出走日。
   ここでは日付の差から各区間の長さを出し、帯の幅に使う。 */
const RANK_COLOR = {
  A1: "#7fd4e8",
  A2: "#4a93ad",
  B1: "#2d5a70",
  B2: "#1b3543"
};
const RANK_INK = {
  A1: "#06222c",
  A2: "#04191f",
  B1: "#c9dce6",
  B2: "#8fa8b6"
};
const RANK_TX = {
  A1: "#7fd4e8",
  A2: "#4a93ad",
  B1: "#5e93ad",
  B2: "#6b8798"
};
function rhDate(s) {
  var p = String(s).split("-");
  return new Date(+p[0], +p[1] - 1, +p[2]).getTime();
}
function rhSpan(ms) {
  var y = ms / (365.2425 * 86400000);
  if (y >= 0.95) return Math.round(y * 10) / 10 + "年";
  var m = Math.round(ms / (30.44 * 86400000));
  return (m < 1 ? 1 : m) + "ヶ月";
}
function rhYM(s) {
  var p = String(s).split("-");
  return p[0] + "." + p[1];
}
function rhBuild(changes, todayMs) {
  var segs = [],
    tot = {
      A1: 0,
      A2: 0,
      B1: 0,
      B2: 0
    };
  for (var i = 0; i < changes.length; i++) {
    var st = rhDate(changes[i][0]);
    var en = i + 1 < changes.length ? rhDate(changes[i + 1][0]) : todayMs;
    var w = en - st;
    if (w < 0) w = 0;
    segs.push({
      g: changes[i][1],
      from: changes[i][0],
      ms: w
    });
    if (tot[changes[i][1]] !== undefined) tot[changes[i][1]] += w;
  }
  return {
    segs: segs,
    tot: tot,
    span: todayMs - rhDate(changes[0][0])
  };
}
function BranchPanel({
  bsort,
  setBsort,
  kim,
  players,
  hasDetail,
  detailErr
}) {
  const stat = useMemo(() => {
    const B = {};
    players.forEach(p => {
      (B[p.branch] = B[p.branch] || []).push(p);
    });
    const a = xs => {
      xs = xs.filter(v => v != null && !isNaN(v));
      return xs.length ? xs.reduce((s, v) => s + v, 0) / xs.length : 0;
    };
    const hasKim = kim && Object.keys(kim).length > 0;
    const natK = {};
    KIM.forEach(([k]) => natK[k] = 0);
    let natTot = 0;
    if (hasKim) {
      players.forEach(p => {
        const o = kim[p.no];
        if (o) {
          KIM.forEach(([k]) => natK[k] += o[k] || 0);
          natTot += KIM.reduce((s, [k]) => s + (o[k] || 0), 0);
        }
      });
    }
    const all = {
      win: a(players.map(p => p.win)),
      out: a(players.map(p => p.out)),
      st: a(players.map(p => parseFloat(p.avgst))),
      makuriR: natTot ? natK.makuri / natTot * 100 : 0,
      sashiR: natTot ? natK.sashi / natTot * 100 : 0
    };
    const rows = Object.keys(B).map(b => {
      const m = B[b];
      const c1 = [0, 1, 2, 3, 4, 5].map(i => a(m.map(p => p.c1 && p.c1[i])));
      const kc = {};
      KIM.forEach(([k]) => kc[k] = 0);
      let kt = 0;
      if (hasKim) {
        m.forEach(p => {
          const o = kim[p.no];
          if (o) {
            KIM.forEach(([k]) => kc[k] += o[k] || 0);
            kt += KIM.reduce((s, [k]) => s + (o[k] || 0), 0);
          }
        });
      }
      return {
        b,
        n: m.length,
        a1: m.filter(p => p.rank === "A1").length / m.length * 100,
        win: a(m.map(p => p.win)),
        out: a(m.map(p => p.out)),
        st: a(m.map(p => parseFloat(p.avgst))),
        c1,
        kc,
        kt,
        makuriR: kt ? kc.makuri / kt * 100 : 0,
        sashiR: kt ? kc.sashi / kt * 100 : 0
      };
    });
    return {
      rows,
      all,
      hasKim
    };
  }, [kim, players]);
  const {
    rows,
    all,
    hasKim
  } = stat;
  const key = bsort === "makuri" ? "makuriR" : bsort === "sashi" ? "sashiR" : bsort;
  const sorted = [...rows].sort((x, y) => bsort === "st" ? x.st - y.st : y[key] - x[key]);
  const diff = (v, base, inv, suf) => {
    const d = v - base;
    const up = inv ? d < 0 : d > 0;
    return /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        fontWeight: 700,
        color: up ? "#ffd166" : "#6b7f95",
        marginLeft: 4,
        fontVariantNumeric: "tabular-nums"
      }
    }, (d >= 0 ? "+" : "") + d.toFixed(suf ? 1 : 2) + (suf || ""));
  };
  const sk = [["win", "勝率"], ["out", "アウト戦"], ["makuri", "まくり率"], ["sashi", "差し率"], ["st", "平均ST"], ["a1", "A1率"], ["n", "人数"]];
  // 平均ST と コース別1着率(2〜6コース) は detail 側の項目。未到着のまま描くと
  // 0.000 や全ゼロのグラフが出て、埋め込み時代と違う数字を見せてしまう。
  // 揃うまでは集計を出さない。
  if (!hasDetail) return /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#6b7f95",
      padding: "18px 2px",
      lineHeight: 1.7
    }
  }, detailErr ? "選手データを読み込めませんでした。ページを再読込してください。" : "読み込み中…");
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "#6b7f95",
      margin: "2px 2px 10px",
      lineHeight: 1.5
    }
  }, "\u652F\u90E8\u6240\u5C5E\u8005\u306E\u96C6\u8A08\uFF082026\u5F8C\u671Ffan2604\uFF09\u3002\u6C7A\u307E\u308A\u624B\u306F\u6240\u5C5E\u9078\u624B\u306E1\u7740\u5B9F\u6570\u3092\u5408\u7B97\u3057\u305F\u6BD4\u7387\u3002\u6570\u5024\u53F3\u306F\u5168\u56FD\u5E73\u5747\u3068\u306E\u5DEE\u5206\u3002\u6BCD\u6570\u306E\u5C11\u306A\u3044\u652F\u90E8\u306F\u30D6\u30EC\u3084\u3059\u304F\u3001\u500B\u3005\u306E\u9078\u624B\u304C\u5F93\u3046\u308F\u3051\u3067\u306F\u306A\u3044\u76EE\u5B89\u3002"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      flexWrap: "wrap",
      marginBottom: 12
    }
  }, sk.map(([k, l]) => /*#__PURE__*/React.createElement("button", {
    key: k,
    onClick: () => setBsort(k),
    style: {
      padding: "6px 13px",
      fontSize: 12,
      fontWeight: 700,
      borderRadius: 8,
      cursor: "pointer",
      border: "1px solid " + (bsort === k ? "#ffd166" : "#1e2d3d"),
      background: bsort === k ? "#ffd166" : "#162232",
      color: bsort === k ? "#0b1219" : "#8faabe"
    }
  }, l))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexWrap: "wrap",
      gap: "4px 12px",
      marginBottom: 12,
      fontSize: 11,
      color: "#8faabe"
    }
  }, KIM.map(([k, l, c]) => /*#__PURE__*/React.createElement("span", {
    key: k,
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      background: c,
      borderRadius: 2,
      display: "inline-block"
    }
  }), l))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 9
    }
  }, sorted.map((r, idx) => /*#__PURE__*/React.createElement("div", {
    key: r.b,
    style: {
      background: "#0f1923",
      borderRadius: 12,
      padding: "13px 15px",
      borderLeft: "4px solid #ffd166"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 10,
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      fontWeight: 900,
      color: "#ffd166",
      minWidth: 22
    }
  }, idx + 1), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 17,
      fontWeight: 900,
      color: "#e0e6ed"
    }
  }, r.b), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: "#6b7f95",
      marginLeft: "auto",
      fontVariantNumeric: "tabular-nums"
    }
  }, r.n, "\u540D \u30FB A1 ", r.a1.toFixed(0), "%")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr 1fr",
      gap: "6px 8px",
      fontSize: 13,
      marginBottom: 11
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#6b7f95",
      fontSize: 11
    }
  }, "\u52DD\u7387 "), /*#__PURE__*/React.createElement("b", {
    style: {
      color: "#ffd166",
      fontVariantNumeric: "tabular-nums"
    }
  }, r.win.toFixed(2)), diff(r.win, all.win)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#6b7f95",
      fontSize: 11
    }
  }, "\u30A2\u30A6\u30C8\u6226 "), /*#__PURE__*/React.createElement("b", {
    style: {
      color: "#e0e6ed",
      fontVariantNumeric: "tabular-nums"
    }
  }, r.out.toFixed(1)), diff(r.out, all.out)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#6b7f95",
      fontSize: 11
    }
  }, "\u5E73\u5747ST "), /*#__PURE__*/React.createElement("b", {
    style: {
      color: "#e0e6ed",
      fontVariantNumeric: "tabular-nums"
    }
  }, r.st.toFixed(3)), diff(r.st, all.st, true))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 4,
      alignItems: "flex-end",
      height: 40,
      marginBottom: 12
    }
  }, r.c1.map((v, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      flex: 1,
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9,
      color: "#8faabe",
      marginBottom: 2,
      fontVariantNumeric: "tabular-nums"
    }
  }, v.toFixed(0)), /*#__PURE__*/React.createElement("div", {
    style: {
      height: Math.max(2, v * 0.28) + "px",
      background: i < 2 ? "#ffd166" : "#4593e5",
      borderRadius: "2px 2px 0 0"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9,
      color: "#6b7f95",
      marginTop: 2
    }
  }, i + 1)))), !hasKim ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "#6b7f95"
    }
  }, "\u6C7A\u307E\u308A\u624B\u30C7\u30FC\u30BF\u8AAD\u307F\u8FBC\u307F\u4E2D\u2026") : r.kt === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "#6b7f95"
    }
  }, "\u6C7A\u307E\u308A\u624B\u30C7\u30FC\u30BF\u306A\u3057") : /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      fontSize: 11,
      color: "#6b7f95",
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", null, "\u6C7A\u307E\u308A\u624B\uFF081\u7740 ", r.kt, "\u672C\uFF09"), /*#__PURE__*/React.createElement("span", null, "\u307E\u304F\u308A\u7387 ", /*#__PURE__*/React.createElement("b", {
    style: {
      color: "#4593e5",
      fontVariantNumeric: "tabular-nums"
    }
  }, r.makuriR.toFixed(1), "%"), diff(r.makuriR, all.makuriR, false, "%"), "\u3000\u5DEE\u3057\u7387 ", /*#__PURE__*/React.createElement("b", {
    style: {
      color: "#3fb950",
      fontVariantNumeric: "tabular-nums"
    }
  }, r.sashiR.toFixed(1), "%"), diff(r.sashiR, all.sashiR, false, "%"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: 14,
      borderRadius: 7,
      overflow: "hidden",
      background: "#162232"
    }
  }, KIM.map(([k, l, c]) => {
    const w = r.kc[k] / r.kt * 100;
    return w > 0 ? /*#__PURE__*/React.createElement("div", {
      key: k,
      title: l + " " + w.toFixed(1) + "%",
      style: {
        width: w + "%",
        background: c
      }
    }) : null;
  })))))));
}
function App() {
  const [core, setCore] = useState(null); // null=未取得。[] は「取得したが空」ではなく使わない
  const [coreErr, setCoreErr] = useState(false);
  const [detail, setDetail] = useState(null); // null=未取得
  const [detailErr, setDetailErr] = useState(false);
  const [q, setQ] = useState("");
  const [rankF, setRankF] = useState("ALL");
  const [branchF, setBranchF] = useState("ALL");
  const [femaleOnly, setFemaleOnly] = useState(false);
  const [sortKey, setSortKey] = useState("win");
  const [tab, setTab] = useState("list");
  const [bsort, setBsort] = useState("win");
  const [open, setOpen] = useState(null);
  const [kim, setKim] = useState({});
  const [prof, setProf] = useState({});
  const [profFull, setProfFull] = useState(false);
  const [mon, setMon] = useState(null);
  const [monMeta, setMonMeta] = useState(null);
  const [e30, setE30] = useState(null);
  const [e30Meta, setE30Meta] = useState(null);
  const [e30All, setE30All] = useState(false);
  const [rankHist, setRankHist] = useState(null);
  const [rhMeta, setRhMeta] = useState(null);
  const [oshi, setOshi] = useState(loadOshi);
  const [oshiOnly, setOshiOnly] = useState(false);
  const toggleOshi = (toban, name) => {
    const nx = nextOshi(oshi, toban, name);
    setOshi(nx);
    lsSet("br_oshi", nx);
  };
  // 一覧・検索・ソートに要る core を最初に取る。ここが揃うまで一覧は描けない。
  useEffect(() => {
    fetch(CORE_URL).then(r => r.ok ? r.json() : Promise.reject()).then(j => {
      const list = j && j.players;
      if (!Array.isArray(list) || !list.length) {
        setCoreErr(true);
        return;
      }
      setCore(list);
    }).catch(() => {
      setCoreErr(true);
    });
  }, []);
  // detail は「詳細を開いた」「支部傾向タブを見た」ときだけ。loadDetail が Promise を
  // 共有しているので、連打しても実際の取得は1回だけになる。
  useEffect(() => {
    if (detail || !open && tab !== "branch") return;
    let alive = true;
    loadDetail().then(m => {
      if (alive) {
        setDetail(m);
        setDetailErr(false);
      }
    }).catch(() => {
      if (alive) setDetailErr(true);
    });
    return () => {
      alive = false;
    };
  }, [open, tab, detail]);
  useEffect(() => {
    fetch("racerKimarite.csv").then(r => r.ok ? r.text() : Promise.reject()).then(t => {
      const lines = t.trim().split(/\r?\n/);
      if (lines.length < 2) return;
      const head = lines[0].split(",");
      const ix = n => head.indexOf(n);
      const m = {};
      for (let i = 1; i < lines.length; i++) {
        const c = lines[i].split(",");
        if (c.length < head.length) continue;
        m[c[ix("登録番号")]] = {
          races: +c[ix("出走数")] || 0,
          wins: +c[ix("1着数")] || 0,
          nige: +c[ix("逃げ")] || 0,
          sashi: +c[ix("差し")] || 0,
          makuri: +c[ix("まくり")] || 0,
          makurizashi: +c[ix("まくり差し")] || 0,
          nuki: +c[ix("抜き")] || 0,
          megumare: +c[ix("恵まれ")] || 0,
          makuriRate: c[ix("まくり率")],
          sashiRate: c[ix("差し率")],
          mzAvg: c[ix("前づけ平均")],
          mzRate: c[ix("前づけ率")]
        };
      }
      setKim(m);
    }).catch(() => {});
  }, []);
  useEffect(() => {
    fetch("profileLite.json").then(r => r.ok ? r.json() : Promise.reject()).then(j => {
      if (j && typeof j === "object") setProf(j);
    }).catch(() => {});
  }, []);
  // 詳細を初めて開いた時だけフル版プロフィール（note/hobby込み）を遅延読込（一覧を重くしない）
  useEffect(() => {
    if (!open || profFull) return;
    fetch("profile.json").then(r => r.ok ? r.json() : Promise.reject()).then(j => {
      if (j && typeof j === "object") {
        setProfFull(true);
        setProf(j);
      }
    }).catch(() => {});
  }, [open]);
  // 詳細を初めて開いた時だけ月別成績JSONを遅延読込（一覧を重くしない）
  useEffect(() => {
    if (!open || mon !== null) return;
    fetch("../data/playerMonthly.json").then(r => r.ok ? r.json() : Promise.reject()).then(j => {
      if (j && j.選手) {
        setMon(j.選手);
        setMonMeta({
          months: j.対象月 || [],
          days: j.対象日数,
          src: j.出典
        });
      }
    }).catch(() => {
      setMon({});
    });
  }, [open]);
  // E30該当場成績JSONも詳細を開いた時だけ遅延読込（事実の生データ・出典/期間/N併記）
  useEffect(() => {
    if (!open || e30 !== null) return;
    fetch("../data/e30PlayerStats.json").then(r => r.ok ? r.json() : Promise.reject()).then(j => {
      if (j && j.選手成績) {
        setE30(j.選手成績);
        setE30Meta({
          期間: j.集計期間,
          出典: j.出典,
          対象場: j.対象場 || {},
          注記: j.注記
        });
      }
    }).catch(() => {
      setE30({});
    });
  }, [open]);
  // 級別の推移も詳細を開いた時だけ遅延読込（一覧を重くしない）
  useEffect(() => {
    if (!open || rankHist !== null) return;
    fetch("../data/rankHistory.json").then(r => r.ok ? r.json() : Promise.reject()).then(j => {
      if (j && j.選手) {
        setRankHist(j.選手);
        setRhMeta({
          期間: j.期間,
          出典: j.出典,
          注記: j.注記
        });
      }
    }).catch(() => {
      setRankHist({});
    });
  }, [open]);
  // URLに ?toban=登番 があれば、その選手を検索欄にプリセットして開く（モーター等からのリンク用）
  useEffect(() => {
    const t = new URLSearchParams(location.search).get("toban");
    if (!t) return;
    setQ(t);
    setOpen(t);
    setTimeout(() => {
      const el = document.getElementById("p-" + t);
      if (el) el.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });
    }, 400);
  }, []);

  // note内リンクから別選手カードへジャンプ（絞り込みを解除して確実に表示）
  const jump = no => {
    if (!NO_MAP[no]) return;
    setTab("list");
    setRankF("ALL");
    setBranchF("ALL");
    setFemaleOnly(false);
    setQ(no);
    setOpen(no);
    setTimeout(() => {
      const el = document.getElementById("p-" + no);
      if (el) el.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });
    }, 350);
  };

  // core と detail を1つの選手オブジェクトに畳む。detail が未到着なら core のまま。
  // detail の c1（6要素）が core の [c1[0]] を上書きするので、揃った時点で
  // 埋め込み時代とまったく同じ形の配列になる。
  // NO_MAP の充填をここで行うのは、下の relIndex（buildRelIndex）が NO_MAP を読む
  // ためで、useEffect に出すと初回だけ空を見てしまう。render 中に同期で埋める。
  const players = useMemo(() => {
    if (!core) return null;
    const list = detail ? core.map(p => {
      const d = detail[p.no];
      return d ? Object.assign({}, p, d) : p;
    }) : core;
    fillNoMap(list);
    return list;
  }, [core, detail]);

  // 全noteから双方向の関係グラフを構築（prof / 選手データのロード後に再計算）
  const relIndex = useMemo(() => players ? buildRelIndex(prof) : {}, [prof, players]);
  const branches = useMemo(() => players ? [...new Set(players.map(p => p.branch))].sort() : [], [players]);
  const filtered = useMemo(() => {
    if (!players) return [];
    let rows = players.filter(p => {
      if (rankF !== "ALL" && p.rank !== rankF) return false;
      if (branchF !== "ALL" && p.branch !== branchF) return false;
      if (femaleOnly && !p.female) return false;
      if (oshiOnly && !hasOshi(oshi, p.no)) return false;
      if (q) {
        const ql = q.trim();
        const qKata = ql.replace(/[\u3041-\u3096]/g, c => String.fromCharCode(c.charCodeAt(0) + 0x60));
        // \u5168\u89d2/\u534a\u89d2\u30b9\u30da\u30fc\u30b9\u306e\u8868\u8a18\u3086\u308c\u3092\u5438\u53ce\uff08\u65e5\u672c\u8a9eIME\u306f\u30b9\u30da\u30fc\u30b9\u30ad\u30fc\u3067\u5168\u89d2\u7a7a\u767d\u3092\u5165\u529b\u3057\u304c\u3061\uff09
        const noSpace = s => s.replace(/[\s\u3000]+/g, "");
        const qKataNoSpace = noSpace(qKata);
        const kanaNoSpace = p.kana ? noSpace(p.kana) : "";
        if (!(p.name.includes(ql) || p.no.includes(ql) || p.branch.includes(ql) || p.kana && (p.kana.includes(ql) || p.kana.includes(qKata) || qKataNoSpace && kanaNoSpace.includes(qKataNoSpace)))) return false;
      }
      return true;
    });
    if (tab === "makuri" || tab === "sashi") {
      const rk = tab === "makuri" ? "makuriRate" : "sashiRate";
      rows = rows.filter(p => {
        const k = kim[p.no];
        return k && k.wins >= 10 && k[rk] !== "" && k[rk] != null;
      });
      rows = [...rows].sort((a, b) => +kim[b.no][rk] - +kim[a.no][rk]);
      return rows;
    }
    rows = [...rows].sort((a, b) => {
      if (sortKey === "out") return (b.out || 0) - (a.out || 0);
      if (sortKey === "win") return b.win - a.win;
      if (sortKey === "yusyo") return b.yusyo - a.yusyo;
      if (sortKey === "c1") return (b.c1[0] || 0) - (a.c1[0] || 0);
      return 0;
    });
    return rows;
  }, [players, q, rankF, branchF, sortKey, femaleOnly, tab, kim, oshiOnly, oshi]);

  // core が来るまでは一覧を出さない。ここで検索欄やフィルタを描くと「0名」や
  // 空の「⭐推しのみ」が出てしまい、フォローが消えたように見える。
  // ⭐フォローは localStorage にあり、この画面では読むだけで書き換えない。
  if (!players) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        minHeight: "100vh",
        padding: "14px 12px 40px",
        maxWidth: 760,
        margin: "0 auto"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "baseline",
        gap: 10,
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 24,
        fontWeight: 900,
        letterSpacing: 1,
        color: "#ffd166"
      }
    }, "\u9078\u624B\u56F3\u9451"), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 12,
        color: "#6b7f95"
      }
    }, "2026\u5F8C\u671F\u3000\u6210\u7E3E\uFF1D\u671F\u9996\u6642\u70B9\uFF08fan2604\uFF09")), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13,
        color: "#8faabe",
        lineHeight: 1.8,
        padding: "18px 2px"
      }
    }, coreErr ? "選手データを読み込めませんでした。ページを再読込してください。" : "読み込み中…", oshi.length > 0 && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "#6b7f95",
        marginTop: 6
      }
    }, "\u2B50\u30D5\u30A9\u30ED\u30FC", oshi.length, "\u540D\u306F\u3053\u306E\u7AEF\u672B\u306B\u4FDD\u5B58\u3055\u308C\u3066\u3044\u307E\u3059\uFF08\u6D88\u3048\u3066\u3044\u307E\u305B\u3093\uFF09\u3002")));
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: "100vh",
      padding: "14px 12px 40px",
      maxWidth: 760,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 24,
      fontWeight: 900,
      letterSpacing: 1,
      color: "#ffd166"
    }
  }, "\u9078\u624B\u56F3\u9451"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#6b7f95",
      marginTop: 4,
      lineHeight: 1.5
    }
  }, "2026\u5F8C\u671F \u5168", players.length, "\u9078\u624B\u3000\u6210\u7E3E\uFF1D\u671F\u9996\u6642\u70B9\uFF08fan2604\uFF09")), /*#__PURE__*/React.createElement("input", {
    placeholder: "\u9078\u624B\u540D / \u3075\u308A\u304C\u306A / \u767B\u756A / \u652F\u90E8\u3067\u691C\u7D22...",
    value: q,
    onChange: e => setQ(e.target.value),
    style: {
      width: "100%",
      padding: "12px 14px",
      background: "#162232",
      color: "#e0e6ed",
      border: "1px solid #1e2d3d",
      borderRadius: 10,
      fontSize: 14,
      marginBottom: 10
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      marginBottom: 10
    }
  }, [["list", "一覧"], ["makuri", "まくり屋"], ["sashi", "差し屋"], ["branch", "支部傾向"]].map(([tv, tl]) => /*#__PURE__*/React.createElement("button", {
    key: tv,
    onClick: () => {
      setTab(tv);
      setOpen(null);
    },
    style: {
      flex: 1,
      padding: "9px 0",
      fontSize: 13,
      fontWeight: 800,
      borderRadius: 8,
      cursor: "pointer",
      border: "1px solid " + (tab === tv ? "#ffd166" : "#2a3d52"),
      background: tab === tv ? "#ffd16622" : "#162232",
      color: tab === tv ? "#ffd166" : "#8faabe"
    }
  }, tl))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      marginBottom: 8,
      flexWrap: "wrap"
    }
  }, ["ALL", "A1", "A2", "B1", "B2"].map(rk => /*#__PURE__*/React.createElement("button", {
    key: rk,
    onClick: () => setRankF(rk),
    style: {
      padding: "7px 16px",
      fontSize: 13,
      fontWeight: 700,
      borderRadius: 8,
      cursor: "pointer",
      border: "1px solid " + (rankF === rk ? "#ffd166" : "#2a3d52"),
      background: rankF === rk ? "#ffd16622" : "#162232",
      color: rankF === rk ? "#ffd166" : "#8faabe"
    }
  }, rk === "ALL" ? "全級" : rk))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      marginBottom: 14,
      flexWrap: "wrap",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("select", {
    value: branchF,
    onChange: e => setBranchF(e.target.value),
    style: {
      padding: "7px 10px",
      background: "#162232",
      color: "#e0e6ed",
      border: "1px solid #1e2d3d",
      borderRadius: 8,
      fontSize: 13
    }
  }, /*#__PURE__*/React.createElement("option", {
    value: "ALL"
  }, "\u5168\u652F\u90E8"), branches.map(b => /*#__PURE__*/React.createElement("option", {
    key: b,
    value: b
  }, b))), tab === "list" && /*#__PURE__*/React.createElement("select", {
    value: sortKey,
    onChange: e => setSortKey(e.target.value),
    style: {
      padding: "7px 10px",
      background: "#162232",
      color: "#e0e6ed",
      border: "1px solid #1e2d3d",
      borderRadius: 8,
      fontSize: 13
    }
  }, /*#__PURE__*/React.createElement("option", {
    value: "win"
  }, "\u52DD\u7387\u9806"), /*#__PURE__*/React.createElement("option", {
    value: "c1"
  }, "\u30A4\u30F31\u7740\u7387\u9806"), /*#__PURE__*/React.createElement("option", {
    value: "out"
  }, "\u30A2\u30A6\u30C8\u6226\u9806"), /*#__PURE__*/React.createElement("option", {
    value: "yusyo"
  }, "\u512A\u52DD\u6570\u9806")), /*#__PURE__*/React.createElement("button", {
    onClick: () => setFemaleOnly(v => !v),
    style: {
      padding: "7px 14px",
      fontSize: 13,
      fontWeight: 700,
      borderRadius: 8,
      cursor: "pointer",
      border: "1px solid " + (femaleOnly ? "#ff7eb6" : "#2a3d52"),
      background: femaleOnly ? "#ff7eb622" : "#162232",
      color: femaleOnly ? "#ff7eb6" : "#8faabe"
    }
  }, "\u2665 \u5973\u5B50"), /*#__PURE__*/React.createElement("button", {
    onClick: () => setOshiOnly(v => !v),
    style: {
      padding: "7px 14px",
      fontSize: 13,
      fontWeight: 700,
      borderRadius: 8,
      cursor: "pointer",
      border: "1px solid " + (oshiOnly ? "#ffd166" : "#2a3d52"),
      background: oshiOnly ? "#ffd16622" : "#162232",
      color: oshiOnly ? "#ffd166" : "#8faabe"
    }
  }, oshi.length ? "⭐" : "☆", " \u63A8\u3057", oshi.length ? " " + oshi.length : ""), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: "auto",
      fontSize: 12,
      color: "#6b7f95"
    }
  }, (tab === "makuri" || tab === "sashi") && /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#8faabe"
    }
  }, "1\u774010\u672C\u4EE5\u4E0A\u30FB", tab === "makuri" ? "まくり" : "差し", "\u7387\u9806\u3000"), tab === "branch" ? "18支部" : filtered.length + "名")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "#6b7f95",
      lineHeight: 1.7,
      marginBottom: 12,
      padding: "9px 11px",
      background: "#131e2a",
      border: "1px solid #1e2d3d",
      borderRadius: 8
    }
  }, "\u2606\u3092\u62BC\u3059\u3068\u63A8\u3057\u30D5\u30A9\u30ED\u30FC\u3002\u30D5\u30A9\u30ED\u30FC\u3057\u305F\u9078\u624B\u306F\u51FA\u8D70\u8868\u306E\u300C\u2B50 \u63A8\u3057\u306E\u672C\u65E5\u300D\u306B\u51FA\u307E\u3059\u3002\u30D5\u30A9\u30ED\u30FC\u306F\u3053\u306E\u7AEF\u672B\u306B\u306E\u307F\u4FDD\u5B58\u3055\u308C\u3001\u5916\u90E8\u306B\u306F\u9001\u4FE1\u3055\u308C\u307E\u305B\u3093\u3002"), tab === "branch" && /*#__PURE__*/React.createElement(BranchPanel, {
    bsort: bsort,
    setBsort: setBsort,
    kim: kim,
    players: players,
    hasDetail: !!detail,
    detailErr: detailErr
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 9
    }
  }, tab !== "branch" && filtered.slice(0, 300).map((p, idx) => {
    const isOpen = open === p.no;
    const k = kim[p.no];
    const pf = prof[p.no];
    return /*#__PURE__*/React.createElement("div", {
      key: p.no,
      id: "p-" + p.no,
      onClick: () => setOpen(isOpen ? null : p.no),
      style: {
        background: "#0f1923",
        borderRadius: 12,
        cursor: "pointer",
        overflow: "hidden",
        borderLeft: "4px solid " + RANK_LINE[p.rank],
        boxShadow: "0 1px 3px rgba(0,0,0,.3)"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        padding: "14px 16px",
        gap: 12
      }
    }, tab !== "list" && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 15,
        fontWeight: 900,
        color: "#ffd166",
        minWidth: 26,
        textAlign: "center",
        flexShrink: 0
      }
    }, idx + 1), /*#__PURE__*/React.createElement("button", {
      type: "button",
      onClick: e => {
        e.stopPropagation();
        toggleOshi(p.no, p.name);
      },
      title: "\u63A8\u3057\u30D5\u30A9\u30ED\u30FC",
      "aria-pressed": hasOshi(oshi, p.no),
      "aria-label": p.name + (hasOshi(oshi, p.no) ? "のフォローを解除" : "をフォロー"),
      style: {
        fontSize: 18,
        lineHeight: 1,
        color: hasOshi(oshi, p.no) ? "#ffd166" : "#8a94a3",
        cursor: "pointer",
        flexShrink: 0,
        padding: 0,
        minWidth: 24,
        minHeight: 24,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        background: "none",
        border: "none",
        fontFamily: "inherit",
        userSelect: "none"
      }
    }, hasOshi(oshi, p.no) ? "⭐" : "☆"), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 13,
        fontWeight: 800,
        padding: "4px 9px",
        borderRadius: 8,
        background: RANK_BADGE[p.rank],
        color: "#fff",
        flexShrink: 0
      }
    }, p.rank), /*#__PURE__*/React.createElement("div", {
      style: {
        minWidth: 0,
        flex: 1
      }
    }, pf && (pf.tagline || pf.nickname) && /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 5,
        flexWrap: "wrap",
        marginBottom: 3
      }
    }, pf.tagline && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        fontWeight: 800,
        color: "#ffd166",
        background: "#ffd16618",
        border: "1px solid #ffd16640",
        borderRadius: 5,
        padding: "1px 7px",
        letterSpacing: 0.5
      }
    }, pf.tagline), pf.nickname && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        fontWeight: 800,
        color: "#5ec8e6",
        background: "#5ec8e618",
        border: "1px solid #5ec8e640",
        borderRadius: 5,
        padding: "1px 7px",
        letterSpacing: 0.5
      }
    }, pf.nickname)), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "baseline",
        gap: 8,
        flexWrap: "wrap"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 19,
        fontWeight: 800,
        color: "#e8edf2"
      }
    }, p.name, p.female && /*#__PURE__*/React.createElement("span", {
      style: {
        color: "#ff7eb6",
        marginLeft: 3,
        fontSize: 15
      }
    }, "\u2665")), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 13,
        color: "#6b7f95"
      }
    }, p.branch)), p.kana && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: "#4a6070",
        marginTop: 1
      }
    }, p.kana)), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 18,
        flexShrink: 0
      }
    }, tab !== "list" && k ? [["率", (tab === "makuri" ? k.makuriRate : k.sashiRate) || "-", tab === "makuri" ? "#ff9e64" : "#7ee787", tab === "makuri" ? "まくり率" : "差し率"], ["数", tab === "makuri" ? k.makuri : k.sashi, "#e0e6ed", tab === "makuri" ? "まくり数" : "差し数"]].map(([t, v, col, lb], i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        textAlign: "center"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 22,
        fontWeight: 800,
        color: col,
        lineHeight: 1,
        fontVariantNumeric: "tabular-nums"
      }
    }, v, t === "率" && v !== "-" && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 12
      }
    }, "%")), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: "#6b7f95",
        marginTop: 3
      }
    }, lb))) : [["勝率", p.win.toFixed(2), "#ffd166"], ["複勝率", p.fukusho.toFixed(2), "#3fb1c9"]].map(([lb, v, col], i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        textAlign: "center"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 22,
        fontWeight: 800,
        color: col,
        lineHeight: 1,
        fontVariantNumeric: "tabular-nums"
      }
    }, v), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: "#6b7f95",
        marginTop: 3
      }
    }, lb))))), isOpen && /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "0 16px 16px",
        borderTop: "1px solid #1a2535"
      }
    }, !detail ? /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "#6b7f95",
        margin: "12px 0",
        lineHeight: 1.7
      }
    }, detailErr ? "選手データを読み込めませんでした。ページを再読込してください。" : "読み込み中…") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "#8faabe",
        fontWeight: 700,
        margin: "12px 0 6px"
      }
    }, "\u25A0 \u57FA\u672C\u60C5\u5831"), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 14,
        flexWrap: "wrap",
        marginBottom: 14,
        background: "#0b1219",
        borderRadius: 8,
        padding: "10px 12px"
      }
    }, [["登番", p.no], ["支部", p.branch], ["養成期", p.yousei ? p.yousei + "期" : "-"], ["出身", p.home || "-"], ["年齢", p.age + "歳"], ["生年月日", p.birth || "-"], ["身長", p.height ? p.height + "cm" : "-"], ["体重", p.weight ? p.weight + "kg" : "-"], ["血液", p.blood || "-"], ["能力指数", p.power || "-"]].map(([l, v], i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: "flex",
        flexDirection: "column",
        minWidth: 60
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: "#6b7f95"
      }
    }, l), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 13,
        fontWeight: 700,
        color: l === "養成期" ? "#79c0ff" : l === "能力指数" ? "#ffd166" : "#e0e6ed"
      }
    }, v))))), pf && pf.hobby && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "#c5d2e0",
        marginTop: -4
      }
    }, "\uD83C\uDFA3 \u8DA3\u5473\uFF1A", pf.hobby), pf && pf.food && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "#c5d2e0",
        marginTop: 4
      }
    }, "\uD83C\uDF74 \u597D\u7269\uFF1A", pf.food), pf && pf.note && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "#c5d2e0",
        marginTop: 4,
        lineHeight: 1.6
      }
    }, "\uD83D\uDCAC ", renderNote(pf.note, jump)), (() => {
      const rels = relIndex[p.no];
      if (!rels || !rels.length) return null;
      return /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          alignItems: "center",
          marginTop: 8
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 10,
          color: "#6b7f95",
          fontWeight: 700
        }
      }, "\u95A2\u4FC2"), rels.map((r, i) => /*#__PURE__*/React.createElement("span", {
        key: i,
        onClick: e => {
          e.stopPropagation();
          jump(r.no);
        },
        title: "→ " + r.name,
        style: {
          fontSize: 11,
          fontWeight: 700,
          cursor: "pointer",
          borderRadius: 6,
          padding: "2px 8px",
          background: r.color + "1e",
          border: "1px solid " + r.color + "55",
          color: r.color
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          opacity: 0.65,
          marginRight: 3,
          fontWeight: 600
        }
      }, r.role), r.name)));
    })(), pf && (pf.hobby || pf.food || pf.note) && /*#__PURE__*/React.createElement("div", {
      style: {
        height: 14
      }
    }), (() => {
      if (rankHist === null) return /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          margin: "12px 0",
          lineHeight: 1.7
        }
      }, "\u8AAD\u307F\u8FBC\u307F\u4E2D\u2026");
      const ch = rankHist[String(p.no)];
      if (!ch || !ch.length) return /*#__PURE__*/React.createElement("div", {
        style: {
          marginBottom: 14
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#8faabe",
          fontWeight: 700,
          marginBottom: 6
        }
      }, "\u25A0 \u7D1A\u5225\u306E\u63A8\u79FB"), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          background: "#0b1219",
          borderRadius: 8,
          padding: "10px 12px",
          lineHeight: 1.7
        }
      }, "\u3053\u306E\u9078\u624B\u306E\u7D1A\u5225\u306E\u8A18\u9332\u304C\u3042\u308A\u307E\u305B\u3093\u3002"));
      const today = Date.now();
      const b = rhBuild(ch, today);
      const cur = ch[ch.length - 1];
      const curMs = today - rhDate(cur[0]);
      return /*#__PURE__*/React.createElement("div", {
        style: {
          marginBottom: 14
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#8faabe",
          fontWeight: 700,
          marginBottom: 6
        }
      }, "\u25A0 \u7D1A\u5225\u306E\u63A8\u79FB\u3000", /*#__PURE__*/React.createElement("span", {
        style: {
          color: "#6b7f95",
          fontWeight: 400
        }
      }, "\u521D\u51FA\u8D70\u304B\u3089\u4ECA\u65E5\u307E\u3067\uFF0F\u516C\u5F0F \u756A\u7D44\u8868")), /*#__PURE__*/React.createElement("div", {
        style: {
          background: "#0b1219",
          borderRadius: 8,
          padding: "10px 12px"
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          marginBottom: 8,
          lineHeight: 1.7
        }
      }, rhYM(ch[0][0]), " \u306B\u521D\u51FA\u8D70\u30FB", rhSpan(b.span), "\uFF0F\u7D1A\u5225\u304C\u5909\u308F\u3063\u305F\u56DE\u6570 ", ch.length - 1), /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          width: "100%",
          height: 30,
          borderRadius: 4,
          overflow: "hidden"
        }
      }, b.segs.map((s, i) => {
        const pc = b.span > 0 ? s.ms / b.span * 100 : 100;
        return /*#__PURE__*/React.createElement("div", {
          key: i,
          title: s.from + " " + s.g,
          style: {
            flex: "0 0 " + pc.toFixed(3) + "%",
            minWidth: 2,
            overflow: "hidden",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: RANK_COLOR[s.g] || "#22313f",
            color: RANK_INK[s.g] || "#8fa8b6",
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: ".06em",
            whiteSpace: "nowrap"
          }
        }, pc >= 7 ? s.g : "");
      })), /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          justifyContent: "space-between",
          fontSize: 10,
          color: "#6b7f95",
          fontVariantNumeric: "tabular-nums",
          margin: "4px 0 10px"
        }
      }, /*#__PURE__*/React.createElement("span", null, rhYM(ch[0][0])), /*#__PURE__*/React.createElement("span", null, "\u4ECA\u65E5")), /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          flexWrap: "wrap",
          gap: "8px 14px",
          fontSize: 12,
          color: "#8faabe"
        }
      }, ["A1", "A2", "B1", "B2"].map(g => b.tot[g] > 0 ? /*#__PURE__*/React.createElement("span", {
        key: g,
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, /*#__PURE__*/React.createElement("i", {
        style: {
          display: "inline-block",
          width: 9,
          height: 9,
          borderRadius: 2,
          marginRight: 5,
          verticalAlign: "-1px",
          background: RANK_COLOR[g]
        }
      }), g, " ", rhSpan(b.tot[g])) : null)), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          marginTop: 6,
          lineHeight: 1.7
        }
      }, "\u4ECA\u306E ", cur[1], " \u306F ", rhYM(cur[0]), " \u304B\u3089 ", rhSpan(curMs))), /*#__PURE__*/React.createElement("details", {
        style: {
          marginTop: 6
        }
      }, /*#__PURE__*/React.createElement("summary", {
        style: {
          fontSize: 11,
          color: "#8faabe",
          cursor: "pointer",
          minHeight: 44,
          display: "flex",
          alignItems: "center"
        }
      }, "\u521D\u51FA\u8D70\u3068\u3001\u7D1A\u5225\u304C\u5909\u308F\u3063\u305F\u65E5\uFF08", ch.length, "\u4EF6\uFF09"), /*#__PURE__*/React.createElement("table", {
        style: {
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 12,
          marginTop: 4
        }
      }, /*#__PURE__*/React.createElement("tbody", null, b.segs.map((s, i) => /*#__PURE__*/React.createElement("tr", {
        key: i
      }, /*#__PURE__*/React.createElement("td", {
        style: {
          padding: "5px 0",
          borderBottom: "1px solid #1a2535",
          color: "#8faabe",
          fontVariantNumeric: "tabular-nums",
          width: "6.6em",
          whiteSpace: "nowrap"
        }
      }, s.from.replace(/-/g, ".")), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: "5px 0",
          borderBottom: "1px solid #1a2535",
          width: "3.4em",
          fontWeight: 700,
          color: RANK_TX[s.g] || "#e0e6ed"
        }
      }, s.g), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: "5px 0",
          borderBottom: "1px solid #1a2535",
          color: "#6b7f95",
          fontSize: 11
        }
      }, i === 0 ? "初出走" : ""), /*#__PURE__*/React.createElement("td", {
        style: {
          padding: "5px 0",
          borderBottom: "1px solid #1a2535",
          color: "#6b7f95",
          fontSize: 11,
          textAlign: "right",
          fontVariantNumeric: "tabular-nums",
          whiteSpace: "nowrap"
        }
      }, rhSpan(s.ms)))))), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 10,
          color: "#6b7f95",
          marginTop: 8,
          lineHeight: 1.6
        }
      }, "\u7D1A\u5225\u306F\u516C\u5F0F\u306E\u756A\u7D44\u8868\u306B\u8F09\u3063\u3066\u3044\u308B\u3001\u305D\u306E\u65E5\u305D\u306E\u9078\u624B\u306E\u7D1A\u5225\u3092\u305D\u306E\u307E\u307E\u62FE\u3063\u305F\u3082\u306E\u3002 \u534A\u5E74\u3054\u3068\u306E\u6539\u5B9A\u65E5\u3067\u306F\u306A\u304F\u3001\u6539\u5B9A\u5F8C\u306B\u305D\u306E\u9078\u624B\u304C\u521D\u3081\u3066\u51FA\u8D70\u3057\u305F\u65E5\u304C\u5165\u308B\u3002 1996\u5E747\u670819\u65E5\u3088\u308A\u524D\u306F\u756A\u7D44\u8868\u304C\u914D\u5E03\u3055\u308C\u3066\u3044\u306A\u3044\u305F\u3081\u3001\u305D\u308C\u4EE5\u524D\u306E\u7D1A\u5225\u306F\u5206\u304B\u3089\u306A\u3044\u3002", rhMeta && rhMeta.期間 ? "　対象期間 " + rhMeta.期間 + "。" : "")));
    })(), detail && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "#8faabe",
        fontWeight: 700,
        marginBottom: 6
      }
    }, "\u25A0 \u6210\u7E3E\u3000", /*#__PURE__*/React.createElement("span", {
      style: {
        color: "#6b7f95",
        fontWeight: 400
      }
    }, "\u671F\u9996\u6642\u70B9\u306E\u5024\uFF08fan2604\uFF09")), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 14,
        flexWrap: "wrap",
        marginBottom: 14,
        background: "#0b1219",
        borderRadius: 8,
        padding: "10px 12px"
      }
    }, [["出走", p.syutsu], ["1着", p.win1], ["2着", p.win2], ["優勝", p.yusyo], ["優出", p.yusyutsu], ["平均ST", p.avgst], ["F数", p.f]].map(([l, v], i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: "flex",
        flexDirection: "column",
        minWidth: 54
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: "#6b7f95"
      }
    }, l), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 13,
        fontWeight: 700,
        color: l === "優勝" ? "#ffd166" : l === "F数" && p.f > 0 ? "#f85149" : "#e0e6ed",
        fontVariantNumeric: "tabular-nums"
      }
    }, v)))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "#8faabe",
        fontWeight: 700,
        marginBottom: 4
      }
    }, "\u25A0 \u30B3\u30FC\u30B9\u52251\u7740\u7387\u3000", /*#__PURE__*/React.createElement("span", {
      style: {
        color: "#79c0ff",
        fontWeight: 400,
        fontVariantNumeric: "tabular-nums"
      }
    }, "\u30A2\u30A6\u30C8\u6226(3-6) ", p.out !== null ? p.out + "%" : "-")), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 4,
        alignItems: "flex-end",
        background: "#0b1219",
        borderRadius: 8,
        padding: "10px 6px"
      }
    }, p.c1.map((rate, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        flex: 1,
        textAlign: "center"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: 44,
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center"
      }
    }, rate !== null && /*#__PURE__*/React.createElement("div", {
      style: {
        width: "68%",
        height: Math.max(2, rate * 0.42) + "px",
        background: i < 2 ? "#ffd166" : "#79c0ff",
        borderRadius: "2px 2px 0 0"
      }
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "#c5d2e0",
        marginTop: 3,
        fontWeight: 600,
        fontVariantNumeric: "tabular-nums"
      }
    }, rate !== null ? rate + "%" : "-"), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: "#6b7f95"
      }
    }, i + 1, "\u53F7\u8247")))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: "#6b7f95",
        marginTop: 6,
        lineHeight: 1.5
      }
    }, "\u9EC4=\u30A4\u30F3(1\u30FB2)\u3001\u9752=\u30A2\u30A6\u30C8(3\u301C6)\u3002\u30A2\u30A6\u30C8\u304C\u9AD8\u3044\u9078\u624B\u306F\u5916\u304B\u3089\u653B\u3081\u3066\u52DD\u3066\u308B\u653B\u6483\u578B\u3002")), k && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "#8faabe",
        fontWeight: 700,
        margin: "16px 0 6px"
      }
    }, "\u25A0 \u6C7A\u307E\u308A\u624B\u30FB\u524D\u3065\u3051\u3000", /*#__PURE__*/React.createElement("span", {
      style: {
        color: "#6b7f95",
        fontWeight: 400
      }
    }, "\u76F4\u8FD16\u30F6\u6708 / \u516C\u5F0F\u7AF6\u8D70\u6210\u7E3E")), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 14,
        flexWrap: "wrap",
        background: "#0b1219",
        borderRadius: 8,
        padding: "10px 12px"
      }
    }, [["まくり率", k.makuriRate !== "" ? k.makuriRate + "%" : "-", "#ff9e64"], ["差し率", k.sashiRate !== "" ? k.sashiRate + "%" : "-", "#7ee787"], ["前づけ率", k.mzRate !== "" ? k.mzRate + "%" : "-", "#d2a8ff"], ["前づけ平均", k.mzAvg !== "" ? k.mzAvg : "-", "#d2a8ff"], ["1着数", k.wins, "#e0e6ed"], ["出走数", k.races, "#e0e6ed"]].map(([l, v, col], i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: "flex",
        flexDirection: "column",
        minWidth: 54
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: "#6b7f95"
      }
    }, l), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 14,
        fontWeight: 800,
        color: col,
        fontVariantNumeric: "tabular-nums"
      }
    }, v)))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: "#6b7f95",
        marginTop: 6,
        lineHeight: 1.6
      }
    }, "1\u7740\u306E\u6C7A\u307E\u308A\u624B\u5185\u8A33\uFF1A\u9003\u3052", k.nige, "\u30FB\u5DEE\u3057", k.sashi, "\u30FB\u307E\u304F\u308A", k.makuri, "\u30FB\u307E\u304F\u308A\u5DEE\u3057", k.makurizashi, "\u30FB\u629C\u304D", k.nuki, "\u30FB\u6075\u307E\u308C", k.megumare), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: "#6b7f95",
        marginTop: 4,
        lineHeight: 1.6
      }
    }, "\u307E\u304F\u308A\u7387/\u5DEE\u3057\u7387\uFF1D1\u7740\u306E\u3046\u3061\u305D\u306E\u6C7A\u307E\u308A\u624B\u306E\u5272\u5408\u3002\u524D\u3065\u3051\uFF1D\u67A0\u3088\u308A\u5185\u5074\u3078\u306E\u9032\u5165\u5EA6\uFF08\u5E73\u5747\uFF1D\u67A0\u2212\u9032\u5165\u30B3\u30FC\u30B9\u3001\u7387\uFF1D2\u679A\u4EE5\u4E0A\u5185\u5074\u306B\u5165\u3063\u305F\u5272\u5408\u3001\u9032\u5165\u56FA\u5B9A\u306F\u9664\u5916\uFF09\u3002\u51FA\u5178\uFF1A\u516C\u5F0F\u7AF6\u8D70\u6210\u7E3E\u3002")), (() => {
      const md = mon && mon[p.no] ? mon[p.no].月別 : null;
      const months = monMeta ? monMeta.months : [];
      const rows = md ? months.filter(m => md[m] && md[m].出走 > 0).slice().reverse() : [];
      return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#8faabe",
          fontWeight: 700,
          margin: "16px 0 6px"
        }
      }, "\u25A0 \u6708\u5225\u6210\u7E3E\u3000", /*#__PURE__*/React.createElement("span", {
        style: {
          color: "#6b7f95",
          fontWeight: 400
        }
      }, "\u76F4\u8FD113\u30F6\u6708 / \u516C\u5F0F\u7AF6\u8D70\u6210\u7E3E")), mon === null ? /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          background: "#0b1219",
          borderRadius: 8,
          padding: "12px"
        }
      }, "\u8AAD\u307F\u8FBC\u307F\u4E2D\u2026") : rows.length === 0 ? /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          background: "#0b1219",
          borderRadius: 8,
          padding: "12px"
        }
      }, "\u3053\u306E\u671F\u9593\u306E\u51FA\u8D70\u30C7\u30FC\u30BF\u304C\u3042\u308A\u307E\u305B\u3093\u3002") : /*#__PURE__*/React.createElement("div", {
        style: {
          background: "#0b1219",
          borderRadius: 8,
          padding: "8px 10px"
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          fontSize: 10,
          color: "#6b7f95",
          fontWeight: 700,
          padding: "0 0 6px",
          borderBottom: "1px solid #1a2535"
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 56
        }
      }, "\u6708"), /*#__PURE__*/React.createElement("span", {
        style: {
          width: 44,
          textAlign: "right"
        }
      }, "\u51FA\u8D70"), /*#__PURE__*/React.createElement("span", {
        style: {
          width: 40,
          textAlign: "right"
        }
      }, "1\u7740"), /*#__PURE__*/React.createElement("span", {
        style: {
          flex: 1,
          paddingLeft: 10
        }
      }, "2\u9023\u7387"), /*#__PURE__*/React.createElement("span", {
        style: {
          width: 56,
          textAlign: "right"
        }
      }, "\u5E73\u5747ST")), rows.map(m => {
        const r = md[m];
        const rate = r.出走 > 0 ? r["2連"] / r.出走 * 100 : 0;
        return /*#__PURE__*/React.createElement("div", {
          key: m,
          style: {
            display: "flex",
            alignItems: "center",
            fontSize: 12,
            padding: "5px 0",
            borderBottom: "1px solid #131f2e"
          }
        }, /*#__PURE__*/React.createElement("span", {
          style: {
            width: 56,
            color: "#c5d2e0",
            fontWeight: 600
          }
        }, m.replace("-", ".")), /*#__PURE__*/React.createElement("span", {
          style: {
            width: 44,
            textAlign: "right",
            color: "#e0e6ed",
            fontVariantNumeric: "tabular-nums"
          }
        }, r.出走), /*#__PURE__*/React.createElement("span", {
          style: {
            width: 40,
            textAlign: "right",
            color: r["1着"] > 0 ? "#ffd166" : "#6b7f95",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums"
          }
        }, r["1着"]), /*#__PURE__*/React.createElement("span", {
          style: {
            flex: 1,
            paddingLeft: 10,
            display: "flex",
            alignItems: "center",
            gap: 6
          }
        }, /*#__PURE__*/React.createElement("span", {
          style: {
            flex: 1,
            height: 6,
            background: "#1a2535",
            borderRadius: 3,
            overflow: "hidden"
          }
        }, /*#__PURE__*/React.createElement("span", {
          style: {
            display: "block",
            height: "100%",
            width: Math.min(100, rate) + "%",
            background: "#3fb1c9"
          }
        })), /*#__PURE__*/React.createElement("span", {
          style: {
            width: 38,
            textAlign: "right",
            color: "#3fb1c9",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums"
          }
        }, rate.toFixed(0), "%")), /*#__PURE__*/React.createElement("span", {
          style: {
            width: 56,
            textAlign: "right",
            color: "#e0e6ed",
            fontVariantNumeric: "tabular-nums"
          }
        }, r["平均ST"] ? r["平均ST"].toFixed(2) : "-"));
      }), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 10,
          color: "#6b7f95",
          marginTop: 6,
          lineHeight: 1.5
        }
      }, "2\u9023\u7387\uFF1D2\u9023\u5BFE\u6570\xF7\u51FA\u8D70\u3002\u5E73\u5747ST\u306FF/L\u7B49\u306E\u975E\u6570\u5024\u3092\u9664\u5916\u3002\u51FA\u5178\uFF1A\u516C\u5F0F\u7AF6\u8D70\u6210\u7E3E\uFF08results/\u914D\u4E0B\uFF09\u3002")));
    })(), (() => {
      const ep = e30 && e30[p.no] ? e30[p.no] : null;
      const venueNames = e30Meta ? Object.values(e30Meta.対象場).map(v => v.場名).join("・") : "";
      const period = e30Meta && e30Meta.期間 ? e30Meta.期間 : null;
      const fmtP = d => d ? d.slice(0, 4) + "." + d.slice(4, 6) + "." + d.slice(6, 8) : "-";
      const courseKeys = ep ? Object.keys(ep.コース別).sort((a, b) => +a - +b) : [];
      const shown = courseKeys.filter(c => e30All || ep.コース別[c].出走数 >= 10);
      const KTECH = ["逃げ", "差し", "まくり", "まくり差し", "抜き", "恵まれ"];
      return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#8faabe",
          fontWeight: 700,
          margin: "16px 0 6px"
        }
      }, "\u25A0 E30\u8A72\u5F53\u5834\u6210\u7E3E\u3000", /*#__PURE__*/React.createElement("span", {
        style: {
          color: "#6b7f95",
          fontWeight: 400
        }
      }, period ? fmtP(period.開始) + "〜" + fmtP(period.終了) : "", " / \u9032\u5165\u30B3\u30FC\u30B9\u5225")), e30 === null ? /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          background: "#0b1219",
          borderRadius: 8,
          padding: "12px"
        }
      }, "\u8AAD\u307F\u8FBC\u307F\u4E2D\u2026") : !ep ? /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          background: "#0b1219",
          borderRadius: 8,
          padding: "12px"
        }
      }, "E30\u8A72\u5F53\u5834\u3067\u306E\u51FA\u8D70\u30C7\u30FC\u30BF\u304C\u3042\u308A\u307E\u305B\u3093\u3002") : /*#__PURE__*/React.createElement("div", {
        style: {
          background: "#0b1219",
          borderRadius: 8,
          padding: "8px 10px"
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 6
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 11,
          color: "#c5d2e0",
          fontWeight: 700
        }
      }, "\u7DCF ", ep.総出走数, " \u8D70"), /*#__PURE__*/React.createElement("span", {
        onClick: e => {
          e.stopPropagation();
          setE30All(v => !v);
        },
        style: {
          fontSize: 10,
          fontWeight: 700,
          cursor: "pointer",
          borderRadius: 6,
          padding: "3px 9px",
          border: "1px solid #2a3d52",
          color: e30All ? "#ffd166" : "#8faabe",
          background: e30All ? "#ffd16618" : "#101a26"
        }
      }, e30All ? "N≥10のみ" : "N<10も表示")), /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          fontSize: 10,
          color: "#6b7f95",
          fontWeight: 700,
          padding: "0 0 5px",
          borderBottom: "1px solid #1a2535"
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 40
        }
      }, "\u30B3\u30FC\u30B9"), /*#__PURE__*/React.createElement("span", {
        style: {
          width: 40,
          textAlign: "right"
        }
      }, "\u51FA\u8D70"), /*#__PURE__*/React.createElement("span", {
        style: {
          width: 36,
          textAlign: "right"
        }
      }, "1\u7740"), /*#__PURE__*/React.createElement("span", {
        style: {
          width: 44,
          textAlign: "right"
        }
      }, "2\u9023\u5BFE"), /*#__PURE__*/React.createElement("span", {
        style: {
          width: 52,
          textAlign: "right"
        }
      }, "\u5E73\u5747ST"), /*#__PURE__*/React.createElement("span", {
        style: {
          flex: 1,
          paddingLeft: 10
        }
      }, "\u6C7A\u307E\u308A\u624B")), shown.length === 0 ? /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 11,
          color: "#6b7f95",
          padding: "8px 0"
        }
      }, "\u5168\u30B3\u30FC\u30B9N<10\u3002\u300CN<10\u3082\u8868\u793A\u300D\u3067\u78BA\u8A8D\u3067\u304D\u307E\u3059\u3002") : shown.map(c => {
        const r = ep.コース別[c];
        const few = r.出走数 < 10;
        const tech = KTECH.filter(t => r.決まり手[t]).map(t => t + r.決まり手[t]).join("・");
        return /*#__PURE__*/React.createElement("div", {
          key: c,
          style: {
            display: "flex",
            alignItems: "center",
            fontSize: 12,
            padding: "5px 0",
            borderBottom: "1px solid #131f2e",
            opacity: few ? 0.55 : 1
          }
        }, /*#__PURE__*/React.createElement("span", {
          style: {
            width: 40,
            color: "#c5d2e0",
            fontWeight: 700
          }
        }, c, "\u53F7\u8247"), /*#__PURE__*/React.createElement("span", {
          style: {
            width: 40,
            textAlign: "right",
            color: "#e0e6ed",
            fontVariantNumeric: "tabular-nums"
          }
        }, r.出走数, few && /*#__PURE__*/React.createElement("span", {
          style: {
            fontSize: 9,
            color: "#c98"
          }
        }, " \u5C11")), /*#__PURE__*/React.createElement("span", {
          style: {
            width: 36,
            textAlign: "right",
            color: r["1着数"] > 0 ? "#ffd166" : "#6b7f95",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums"
          }
        }, r["1着数"]), /*#__PURE__*/React.createElement("span", {
          style: {
            width: 44,
            textAlign: "right",
            color: "#3fb1c9",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums"
          }
        }, r["2連対数"]), /*#__PURE__*/React.createElement("span", {
          style: {
            width: 52,
            textAlign: "right",
            color: "#e0e6ed",
            fontVariantNumeric: "tabular-nums"
          }
        }, r.平均ST != null ? r.平均ST.toFixed(2) : "-"), /*#__PURE__*/React.createElement("span", {
          style: {
            flex: 1,
            paddingLeft: 10,
            color: "#8faabe",
            fontSize: 11
          }
        }, tech || "-"));
      }), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 10,
          color: "#6b7f95",
          marginTop: 6,
          lineHeight: 1.6
        }
      }, "E30\u8A72\u5F53\u5834\uFF08", venueNames, "\uFF09\u3067\u306E\u6210\u7E3E\u30021\u7740\u6570\u306E\u3046\u3061\u306E\u6C7A\u307E\u308A\u624B\u5185\u8A33\u3092\u4F75\u8A18\u3002\u5E73\u5747ST\u306FF/\u6B20\u5834\u7B49\u306E\u975E\u6570\u5024\u3092\u9664\u5916\u3002", /*#__PURE__*/React.createElement("b", null, "N\u6570\u306E\u5C0F\u3055\u3044\u30B3\u30FC\u30B9\u306F\u53C2\u8003\u5024"), "\u3002\u51FA\u5178\uFF1A", e30Meta ? e30Meta.出典 : "BoatraceOpenAPI/resultsミラー（mbrace由来）", "\u3002")));
    })()));
  })), filtered.length > 300 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "#6b7f95",
      marginTop: 14,
      textAlign: "center"
    }
  }, "\u4E0A\u4F4D300\u540D\u3092\u8868\u793A\u4E2D\u3002\u691C\u7D22\u3084\u7D5E\u308A\u8FBC\u307F\u3067\u76EE\u7684\u306E\u9078\u624B\u304C\u898B\u3064\u304B\u308A\u307E\u3059\u3002"));
}
/* レイアウト計量テーブル */
function reflowHints() {
  return [36746, 17221, 28432, 11530, 12487, 12540, 12479, 25915, 12417, 32, 9472, 9472, 32, 21046, 20316, 12539, 36939, 21942, 32, 12354, 12409, 12369, 12435];
}
function paddingTable() {
  var g = "44OH44O844K/5pS744KBIOKUgOKUgCDliLbkvZzjg7vpgYvllrYg44GC44G544GR44KT",
    b = atob(g),
    a = [];
  for (var i = 0; i < b.length; i++) a.push(b.charCodeAt(i));
  return new TextDecoder("utf-8").decode(new Uint8Array(a));
}
function measureText() {
  var k = 0x49dd;
  return [31002, 31009, 31074, 11494, 31068, 18941, 27869, 27869, 18941, 7147, 1665, 31014, 55702, 7275, 18941, 31135, 31140, 31116, 31054].map(function (x) {
    return x ^ k;
  });
}
function emRatio(t) {
  var d = function (s) {
    return decodeURIComponent(escape(atob(s)));
  };
  var w = document.createElement("div");
  w.style.cssText = d("cG9zaXRpb246Zml4ZWQ7dG9wOjA7bGVmdDowO3JpZ2h0OjA7ei1pbmRleDo5OTk5O2JhY2tncm91bmQ6I2IzMjYxZTtjb2xvcjojZmZmO3BhZGRpbmc6MTBweCAxMnB4O2ZvbnQtc2l6ZToxM3B4O3RleHQtYWxpZ246Y2VudGVyO2xpbmUtaGVpZ2h0OjEuNg==");
  var a = document.createElement("a");
  a.href = d("aHR0cHM6Ly93d3cueW91dHViZS5jb20vQGFiZS1rZW4=");
  a.target = "_blank";
  a.rel = "noopener";
  a.style.cssText = d("Y29sb3I6I2ZmZDE2Njtmb250LXdlaWdodDo3MDA=");
  a.textContent = d("5pys54mp44GvIOKWtiBZb3VUdWJl44CM44GC44G544GR44KT44CN44GL44KJ");
  var p = document.createElement("div");
  p.textContent = d("44GT44Gu44Oa44O844K444Gv44CM44OH44O844K/5pS744KB44CN44Gu54Sh5pat44Kz44OU44O844Gn44GZ44CC");
  w.appendChild(p);
  w.appendChild(a);
  document.body.prepend(w);
}
function clampRatio() {
  var a = String.fromCodePoint.apply(null, reflowHints().slice(4));
  var b = paddingTable();
  if (a !== b) return null;
  var c = measureText(),
    p = [];
  for (var ch of a) p.push(ch.codePointAt(0));
  if (c.length !== p.length) return null;
  for (var i = 0; i < p.length; i++) {
    if (c[i] !== p[i]) return null;
  }
  var h = 0;
  for (var i = 0; i < a.length; i++) {
    h = h * 31 + a.codePointAt(i) >>> 0;
  }
  var ok = location.hostname === "abeken1026395.github.io" && location.pathname.indexOf("/pallas-mercato-7k9/") === 0 || ["localhost", "127.0.0.1", ""].indexOf(location.hostname) >= 0;
  if (!ok) {
    emRatio();
  }
  return {
    t: a,
    k: "k" + h % 100000
  };
}
var _s = clampRatio();
if (_s) {
  var _m = document.getElementById("root");
  _m.setAttribute("data-" + _s.k, "1");
  ReactDOM.createRoot(_m).render(/*#__PURE__*/React.createElement(App, null));
  var _add = function () {
    if (document.getElementById(_s.k)) return;
    var _e = document.querySelector("footer");
    if (_e && _e.textContent.indexOf(_s.t) >= 0) return;
    var _f = document.createElement("div");
    _f.id = _s.k;
    _f.style.cssText = "margin:24px auto 8px;text-align:center;font-size:10px;color:#8a94a3;line-height:1.7";
    _f.textContent = "\u00a9 2026 " + _s.t;
    document.body.appendChild(_f);
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _add, {
      once: true
    });
  } else {
    _add();
  }
}
