// 自動生成ファイル。手で編集しないこと。正本は scripts/fan/app.jsx sha256=dd17ce61ce76cf7ead2fdef3c400174e5583c9ac846126bd7e1f00dd6253172f
const {
  useState,
  useMemo,
  useEffect
} = React;
const PSYCH = {
  "gap": {
    label: "射幸心×童謡",
    c: "#ffd166"
  },
  "nostalgia": {
    label: "郷愁",
    c: "#7fe0a0"
  },
  "tension": {
    label: "緊張・高揚",
    c: "#f85149"
  },
  "local-pride": {
    label: "ご当地",
    c: "#58a6ff"
  },
  "mystery": {
    label: "ミステリー",
    c: "#dcbd78"
  },
  "class": {
    label: "格調",
    c: "#dcbd78"
  },
  "none": {
    label: "BGMなし",
    c: "#8faabe"
  }
};
// 締切BGMが無い場は、曲の心理分類ではなく「BGMなし」に分類する
const psychOf = bg => bg.status === "none" ? "none" : bg.psych;
const STATUS_LABEL = {
  "none": "締切BGMなし",
  "unknown": "曲名は未特定",
  "page_exists": "公式ページに記載あり（曲名は未確認）"
};
const PRESENT = {
  "yes": {
    label: "場立ちあり",
    c: "#3fb950"
  },
  "official": {
    label: "公式記載",
    c: "#58a6ff"
  },
  "advisor": {
    label: "解説アドバイザー",
    c: "#dcbd78"
  },
  "paper": {
    label: "予想紙",
    c: "#d29922"
  },
  "unknown": {
    label: "未確認",
    c: "#9fb0c3"
  }
};
// タップ対象を24px以上にする小さなリンク用（WCAG 2.2 / 2.5.8）
const TAP = {
  display: "inline-flex",
  alignItems: "center",
  minHeight: 24,
  minWidth: 24
};
function Tab({
  id,
  cur,
  set,
  children,
  c
}) {
  const on = cur === id;
  return /*#__PURE__*/React.createElement("button", {
    onClick: () => set(id),
    style: {
      flex: 1,
      minWidth: 100,
      padding: "9px 10px",
      cursor: "pointer",
      background: on ? "#eef3f8" : "#111d2b",
      color: on ? "#0b1726" : "#8faabe",
      border: "1px solid " + (on ? "#eef3f8" : "#1e2d3d"),
      borderRadius: 8,
      fontSize: 13,
      fontWeight: 800
    }
  }, children);
}
function BgmSection({
  data,
  e30
}) {
  const [open, setOpen] = useState(null);
  const [intro, setIntro] = useState(false);
  const [pf, setPf] = useState("ALL");
  const col = data.column;
  const codes = Object.keys(data.venues).sort();
  const psychs = useMemo(() => [...new Set(codes.map(c => psychOf(data.venues[c])).filter(Boolean))], [data]);
  const filtered = codes.filter(c => pf === "ALL" || psychOf(data.venues[c]) === pf);
  return /*#__PURE__*/React.createElement("div", null, col && /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 12,
      background: "#1a1222",
      border: "1px solid #4a2f5a",
      borderRadius: 10,
      padding: "11px 13px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: () => setIntro(!intro),
    style: {
      display: "flex",
      alignItems: "center",
      cursor: "pointer",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      fontWeight: 800,
      color: "#dcbd78"
    }
  }, "\uD83C\uDFB5 ", col.title), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: "auto",
      fontSize: 11,
      color: "#dcbd78",
      whiteSpace: "nowrap",
      flexShrink: 0
    }
  }, intro ? "▲ 閉じる" : "▼ 読む")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#d8c5e0",
      lineHeight: 1.7,
      marginTop: 6
    }
  }, col.lead), intro && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8
    }
  }, (col.angles || []).map((a, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      marginBottom: 6,
      paddingLeft: 8,
      borderLeft: "2px solid " + (PSYCH[a.key] && PSYCH[a.key].c || "#dcbd78")
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      color: PSYCH[a.key] && PSYCH[a.key].c || "#dcbd78"
    }
  }, a.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#c5d2e0",
      lineHeight: 1.6
    }
  }, a.text))), data.common && data.common.fanfare && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      background: "#0f1a26",
      border: "1px solid #2a3d52",
      borderRadius: 8,
      padding: "8px 10px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      color: "#dcbd78",
      marginBottom: 3
    }
  }, "\uD83C\uDFBA \u30D4\u30C3\u30C8\u30A2\u30A6\u30C8\u306E\u30D5\u30A1\u30F3\u30D5\u30A1\u30FC\u30EC\uFF08\u5168\u56FD\u5171\u901A\uFF09"), data.common.fanfare.hook && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#e6d0ee",
      lineHeight: 1.7,
      marginBottom: 5
    }
  }, data.common.fanfare.hook), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#c5d2e0",
      lineHeight: 1.6
    }
  }, data.common.fanfare.note), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "#9a8db0",
      lineHeight: 1.6,
      marginTop: 4
    }
  }, "\u4F5C\u66F2\uFF1A", (data.common.fanfare.composers || []).join(" ／ ")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "#9a8db0",
      lineHeight: 1.6
    }
  }, data.common.fanfare.history)), col.disclaimer && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 6,
      fontSize: 10.5,
      color: "#8a7d9a",
      lineHeight: 1.5
    }
  }, "\u203B ", col.disclaimer))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      flexWrap: "wrap",
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setPf("ALL"),
    style: {
      padding: "5px 11px",
      cursor: "pointer",
      background: pf === "ALL" ? "#eef3f8" : "#111d2b",
      color: pf === "ALL" ? "#0b1726" : "#8faabe",
      border: "1px solid " + (pf === "ALL" ? "#eef3f8" : "#1e2d3d"),
      borderRadius: 999,
      fontSize: 12,
      fontWeight: 700
    }
  }, "\u3059\u3079\u3066"), psychs.map(k => /*#__PURE__*/React.createElement("button", {
    key: k,
    onClick: () => setPf(k),
    style: {
      padding: "5px 11px",
      cursor: "pointer",
      background: pf === k ? "#eef3f8" : "#111d2b",
      color: pf === k ? "#0b1726" : "#8faabe",
      border: "1px solid " + (pf === k ? "#eef3f8" : "#1e2d3d"),
      borderRadius: 999,
      fontSize: 12,
      fontWeight: 700
    }
  }, PSYCH[k] ? PSYCH[k].label : k))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gap: 8
    }
  }, filtered.map(code => {
    const bg = data.venues[code];
    const songs = bg.songs || [];
    const ps = psychOf(bg) && PSYCH[psychOf(bg)];
    const isOpen = open === code;
    return /*#__PURE__*/React.createElement("div", {
      key: code,
      onClick: () => setOpen(isOpen ? null : code),
      style: {
        background: "#1a1222",
        border: "1px solid #3a2748",
        borderRadius: 10,
        padding: "11px 13px",
        cursor: "pointer"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexWrap: "wrap"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        fontWeight: 700,
        color: "#a880b0",
        background: "#0b1219",
        border: "1px solid #4a2f5a",
        borderRadius: 6,
        padding: "2px 7px",
        minWidth: 30,
        textAlign: "center"
      }
    }, parseInt(code, 10)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 16,
        fontWeight: 800,
        color: "#f0d8f6",
        minWidth: 54
      }
    }, bg.name), ps && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        fontWeight: 700,
        color: ps.c,
        background: ps.c + "18",
        border: "1px solid " + ps.c + "66",
        borderRadius: 5,
        padding: "1px 6px"
      }
    }, ps.label), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        color: "#a880b0"
      }
    }, songs.length ? songs.length + "曲" : STATUS_LABEL[bg.status] || ""), /*#__PURE__*/React.createElement("span", {
      style: {
        marginLeft: "auto",
        fontSize: 11,
        color: "#dcbd78",
        whiteSpace: "nowrap",
        flexShrink: 0
      }
    }, isOpen ? "▲" : "▼")), e30 && e30[code] && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        fontWeight: 700,
        color: "#8fd6c0",
        marginTop: 5
      }
    }, "E30\u5207\u66FF\uFF1A", e30[code], "\u301C"), bg.hook && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12.5,
        color: "#e6d0ee",
        lineHeight: 1.7,
        marginTop: 6,
        fontStyle: "italic"
      }
    }, bg.hook), isOpen && /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 8,
        paddingTop: 8,
        borderTop: "1px solid #3a2748"
      }
    }, songs.map((sg, i) => {
      const off = sg.confirmed === "official";
      return /*#__PURE__*/React.createElement("div", {
        key: i,
        style: {
          marginBottom: 6,
          paddingLeft: 8,
          borderLeft: "2px solid #4a2f5a"
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          color: "#f0d8f6",
          fontWeight: 700
        }
      }, sg.title), sg.artist && /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 11,
          color: "#b090b8"
        }
      }, "\uFF08", sg.artist, "\uFF09"), sg.type && /*#__PURE__*/React.createElement("span", {
        style: {
          marginLeft: 6,
          fontSize: 10,
          color: "#9fb5c9",
          background: "#0b1219",
          border: "1px solid #2a3d52",
          borderRadius: 5,
          padding: "1px 5px"
        }
      }, sg.type), /*#__PURE__*/React.createElement("span", {
        style: {
          marginLeft: 6,
          fontSize: 10,
          fontWeight: 700,
          color: off ? "#3fb950" : "#d29922",
          background: (off ? "#3fb950" : "#d29922") + "18",
          border: "1px solid " + (off ? "#3fb950" : "#d29922") + "66",
          borderRadius: 5,
          padding: "1px 6px"
        }
      }, off ? "公式確認" : "諸説あり"), sg.source && /*#__PURE__*/React.createElement("a", {
        href: sg.source,
        target: "_blank",
        rel: "noopener",
        onClick: e => e.stopPropagation(),
        style: {
          ...TAP,
          marginLeft: 6,
          fontSize: 11,
          color: "#dcbd78"
        }
      }, "\u51FA\u5178\u2192"), sg.listen && /*#__PURE__*/React.createElement("a", {
        href: sg.listen.url,
        target: "_blank",
        rel: "noopener",
        onClick: e => e.stopPropagation(),
        title: sg.listen.kind === "official" ? "公式が配信/配布する音源" : "原曲そのものの検索（場の音源そのものとは限りません）",
        style: {
          ...TAP,
          marginLeft: 6,
          fontSize: 11,
          fontWeight: 700,
          color: sg.listen.kind === "official" ? "#7fe0a0" : "#9fb5c9"
        }
      }, sg.listen.kind === "official" ? "▶ 公式音源" : "🔍 原曲(参考)"));
    }), songs.length === 0 && bg.note && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "#c5d2e0",
        lineHeight: 1.6
      }
    }, bg.note), /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 4,
        fontSize: 10.5,
        color: "#8a7d9a",
        lineHeight: 1.5
      }
    }, "\u300C\u8AF8\u8AAC\u3042\u308A\u300D\u306F\u4E8C\u6B21\u30BD\u30FC\u30B9\uFF08\u30D5\u30A1\u30F3\u30E1\u30C7\u30A3\u30A2\u7B49\uFF09\u3067\u306E\u8A00\u53CA\u3067\u516C\u5F0F\u672A\u78BA\u8A8D\u3002\u300C\uD83D\uDD0D\u539F\u66F2(\u53C2\u8003)\u300D\u306F\u539F\u66F2\u305D\u306E\u3082\u306E\u306E\u691C\u7D22\u3067\u3001\u5834\u3067\u6D41\u308C\u308B\u30A2\u30EC\u30F3\u30B8/\u97F3\u6E90\u305D\u306E\u3082\u306E\u3068\u306F\u9650\u308A\u307E\u305B\u3093\u3002\u66F2\u540D\u30FB\u5FC3\u7406\u306E\u8A71\u306F\u8AAD\u307F\u7269\u3067\u3042\u308A\u3001\u65AD\u5B9A\u30FB\u8CB7\u3044\u76EE\u3067\u306F\u3042\u308A\u307E\u305B\u3093\u3002", songs[0] && songs[0].checked ? "（確認 " + songs[0].checked + "）" : "")));
  })));
}
function YosouyaSection({
  data,
  e30
}) {
  const [open, setOpen] = useState(null);
  const [intro, setIntro] = useState(false);
  const [pf, setPf] = useState("ALL");
  const it = data.intro;
  const codes = Object.keys(data.venues).sort();
  const present = ["yes", "official", "advisor", "paper"];
  const filtered = codes.filter(c => {
    const p = data.venues[c].present;
    if (pf === "ALL") return true;
    if (pf === "unknown") return !present.includes(p);
    return p === pf;
  });
  return /*#__PURE__*/React.createElement("div", null, it && /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 12,
      background: "#221a12",
      border: "1px solid #4a3a26",
      borderRadius: 10,
      padding: "11px 13px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: () => setIntro(!intro),
    style: {
      display: "flex",
      alignItems: "center",
      cursor: "pointer",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      fontWeight: 800,
      color: "#d9b382"
    }
  }, "\uD83C\uDFAB ", it.title), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: "auto",
      fontSize: 11,
      color: "#c9a870",
      whiteSpace: "nowrap",
      flexShrink: 0
    }
  }, intro ? "▲ 閉じる" : "▼ 読む")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#ecd9b8",
      lineHeight: 1.7,
      marginTop: 6
    }
  }, it.lead), intro && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8
    }
  }, it.note_absent && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#c5d2e0",
      lineHeight: 1.7,
      background: "#1a140c",
      border: "1px solid #3a2f1a",
      borderRadius: 8,
      padding: "8px 10px"
    }
  }, it.note_absent), it.disclaimer && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 6,
      fontSize: 10.5,
      color: "#a89878",
      lineHeight: 1.5
    }
  }, "\u203B ", it.disclaimer))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      flexWrap: "wrap",
      marginBottom: 10
    }
  }, [["ALL", "すべて", "#d9b382"], ["yes", PRESENT.yes.label, PRESENT.yes.c], ["official", PRESENT.official.label, PRESENT.official.c], ["advisor", PRESENT.advisor.label, PRESENT.advisor.c], ["paper", PRESENT.paper.label, PRESENT.paper.c], ["unknown", PRESENT.unknown.label, PRESENT.unknown.c]].map(([k, lb, c]) => /*#__PURE__*/React.createElement("button", {
    key: k,
    onClick: () => setPf(k),
    style: {
      padding: "5px 11px",
      cursor: "pointer",
      background: pf === k ? "#eef3f8" : "#111d2b",
      color: pf === k ? "#0b1726" : "#8faabe",
      border: "1px solid " + (pf === k ? "#eef3f8" : "#1e2d3d"),
      borderRadius: 999,
      fontSize: 12,
      fontWeight: 700
    }
  }, lb))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gap: 8
    }
  }, filtered.map(code => {
    const y = data.venues[code];
    const pr = PRESENT[y.present] || PRESENT.unknown;
    const off = y.confirmed === "official";
    const hasDetail = ["yes", "official", "advisor", "paper"].includes(y.present);
    const isOpen = open === code;
    return /*#__PURE__*/React.createElement("div", {
      key: code,
      onClick: () => hasDetail && setOpen(isOpen ? null : code),
      style: {
        background: "#221a12",
        border: "1px solid " + (hasDetail ? "#4a3a26" : "#2a2418"),
        borderRadius: 10,
        padding: "11px 13px",
        cursor: hasDetail ? "pointer" : "default"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexWrap: "wrap"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        fontWeight: 700,
        color: "#b39a78",
        background: "#0b1219",
        border: "1px solid #4a3a26",
        borderRadius: 6,
        padding: "2px 7px",
        minWidth: 30,
        textAlign: "center"
      }
    }, parseInt(code, 10)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 16,
        fontWeight: 800,
        color: "#ecd9b8",
        minWidth: 54
      }
    }, y.name), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        fontWeight: 700,
        color: pr.c,
        background: pr.c + "18",
        border: "1px solid " + pr.c + "66",
        borderRadius: 5,
        padding: "1px 6px"
      }
    }, pr.label), y.count && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        color: "#b39a78"
      }
    }, y.count), hasDetail && /*#__PURE__*/React.createElement("span", {
      style: {
        marginLeft: "auto",
        fontSize: 11,
        color: "#d9b382",
        whiteSpace: "nowrap",
        flexShrink: 0
      }
    }, isOpen ? "▲" : "▼")), e30 && e30[code] && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        fontWeight: 700,
        color: "#8fd6c0",
        marginTop: 5
      }
    }, "E30\u5207\u66FF\uFF1A", e30[code], "\u301C"), y.hook && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12.5,
        color: "#ecd9b8",
        lineHeight: 1.7,
        marginTop: 6,
        fontStyle: "italic"
      }
    }, y.hook), !hasDetail && y.note && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "#a89878",
        lineHeight: 1.6,
        marginTop: 5
      }
    }, y.note), isOpen && hasDetail && /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 8,
        paddingTop: 8,
        borderTop: "1px solid #4a3a26"
      }
    }, y.people && y.people.length > 0 && /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        flexWrap: "wrap",
        gap: 6,
        marginBottom: 6
      }
    }, y.people.map((p, i) => /*#__PURE__*/React.createElement("span", {
      key: i,
      title: p.note || "",
      style: {
        fontSize: 12,
        background: "#0b1219",
        border: "1px solid #4a3a26",
        borderRadius: 6,
        padding: "3px 9px",
        color: "#ecd9b8"
      }
    }, p.name, p.kind ? /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: "#b39a78"
      }
    }, "\uFF08", p.kind, "\uFF09") : null))), y.people && y.people.length > 0 && y.people.some(p => p.note) && /*#__PURE__*/React.createElement("div", {
      style: {
        marginBottom: 6
      }
    }, y.people.filter(p => p.note).map((p, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        marginBottom: 4,
        paddingLeft: 8,
        borderLeft: "2px solid #4a3a26"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 12,
        fontWeight: 700,
        color: "#f0e0c0"
      }
    }, p.name), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 12,
        color: "#c5d2e0",
        lineHeight: 1.6
      }
    }, "\u3000", p.note)))), (y.count || y.fee) && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "#c5d2e0",
        lineHeight: 1.6
      }
    }, y.count ? "在籍：" + y.count : "", y.count && y.fee ? "／" : "", y.fee ? "料金：" + y.fee : ""), y.note && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "#c5d2e0",
        lineHeight: 1.6
      }
    }, y.note), /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 4
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        fontWeight: 700,
        color: off ? "#3fb950" : "#d29922",
        background: (off ? "#3fb950" : "#d29922") + "18",
        border: "1px solid " + (off ? "#3fb950" : "#d29922") + "66",
        borderRadius: 5,
        padding: "1px 6px"
      }
    }, off ? "公式記載" : "諸説あり"), y.source && /*#__PURE__*/React.createElement("a", {
      href: y.source,
      target: "_blank",
      rel: "noopener",
      onClick: e => e.stopPropagation(),
      style: {
        ...TAP,
        marginLeft: 6,
        fontSize: 11,
        color: "#d9b382"
      }
    }, "\u51FA\u5178\u2192")), /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 4,
        fontSize: 10.5,
        color: "#a89878",
        lineHeight: 1.5
      }
    }, "\u4E88\u60F3\u5C4B\u306E\u201C\u5B58\u5728\u30FB\u5C4B\u53F7\u30FB\u6587\u5316\u201D\u306E\u7D39\u4ECB\u3067\u3001\u8CB7\u3044\u76EE\u30FB\u7684\u4E2D\u306F\u8F09\u305B\u307E\u305B\u3093\uFF08\u4FDD\u8A3C\u3082\u3057\u307E\u305B\u3093\uFF09\u3002\u5728\u7C4D\u30FB\u6599\u91D1\u30FB\u9854\u3076\u308C\u306F\u5909\u52D5\u3057\u307E\u3059\u3002", y.checked ? "（確認 " + y.checked + "）" : "")));
  })));
}
function App() {
  const [tab, setTab] = useState("bgm");
  const [fanfare, setFanfare] = useState(undefined);
  const [yosouya, setYosouya] = useState(undefined);
  const [e30, setE30] = useState(undefined); // 場コード(2桁) -> "YYYY-MM-DD"（確定10場のみ）。undefined＝取得中、取得失敗時は null＝E30表示を省略

  useEffect(() => {
    fetch("../data/fanfareBgm.json?v=" + Date.now()).then(r => r.json()).then(setFanfare).catch(() => setFanfare(null));
    fetch("../data/yosouya.json?v=" + Date.now()).then(r => r.json()).then(setYosouya).catch(() => setYosouya(null));
    // E30切替日（生データ・事実提示のみ）。startDate がある場だけ収録。失敗時は丸ごと省略。
    fetch("../data/e30Schedule.json?v=" + Date.now()).then(r => r.json()).then(j => {
      if (j && Array.isArray(j.venues)) {
        const m = {};
        for (const v of j.venues) {
          if (v && v.jcd && v.startDate) m[String(v.jcd).padStart(2, "0")] = v.startDate;
        }
        setE30(m);
      } else setE30(null);
    }).catch(() => setE30(null));
  }, []);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: "100vh",
      padding: "12px",
      maxWidth: 900,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 10,
      marginBottom: 4,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "kataTitle",
    style: {
      fontSize: 20,
      fontWeight: 800,
      color: "#dcbd78"
    }
  }, "\u5834\u306E\u6587\u5316")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: "#8faabe",
      marginBottom: 12,
      lineHeight: 1.6
    }
  }, "\u7DE0\u5207BGM\u3001\u5834\u7ACB\u3061\u4E88\u60F3\u5C4B\u3001\u5B9F\u6CC1\u30A2\u30CA\u2014\u2014\u6570\u5B57\u306B\u306F\u51FA\u306A\u3044\u201C\u5834\u306E\u6587\u5316\u201D\u309224\u5834\u6A2A\u65AD\u3067\u3002\u8CB7\u3044\u76EE\u30FB\u52DD\u6557\u30FB\u7684\u4E2D\u306F\u51FA\u3057\u307E\u305B\u3093\u3002"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      marginBottom: 12,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement(Tab, {
    id: "bgm",
    cur: tab,
    set: setTab,
    c: "#dcbd78"
  }, "\u5834\u5185BGM"), /*#__PURE__*/React.createElement(Tab, {
    id: "yosouya",
    cur: tab,
    set: setTab,
    c: "#d9b382"
  }, "\u5834\u5185\u4E88\u60F3\u5C4B"), /*#__PURE__*/React.createElement("a", {
    href: "../announcers/",
    style: {
      flex: 1,
      minWidth: 100,
      padding: "9px 10px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      textDecoration: "none",
      background: "#111d2b",
      color: "#8faabe",
      border: "1px solid #1e2d3d",
      borderRadius: 8,
      fontSize: 13,
      fontWeight: 800
    }
  }, "\u5B9F\u6CC1\u30A2\u30CA\u56F3\u9451 \u2192")), /*#__PURE__*/React.createElement("div", {
    id: "tabBody",
    style: {
      minHeight: "100vh"
    }
  }, tab === "bgm" && (fanfare === undefined || e30 === undefined ? /*#__PURE__*/React.createElement(Loading, null) : fanfare ? /*#__PURE__*/React.createElement(BgmSection, {
    data: fanfare,
    e30: e30
  }) : /*#__PURE__*/React.createElement(Err, null)), tab === "yosouya" && (yosouya === undefined || e30 === undefined ? /*#__PURE__*/React.createElement(Loading, null) : yosouya ? /*#__PURE__*/React.createElement(YosouyaSection, {
    data: yosouya,
    e30: e30
  }) : /*#__PURE__*/React.createElement(Err, null))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 14,
      background: "#111d2b",
      border: "1px solid #24384f",
      borderRadius: 10,
      padding: "10px 12px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "#8faabe",
      lineHeight: 1.6
    }
  }, "\u5404\u5834\u306E\u6C34\u9762\u7279\u6027\u30FB\u30B0\u30EB\u30E1\u30FB\u30A2\u30CA\u3068\u5408\u308F\u305B\u3066\u8AAD\u3080\u306A\u3089"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 6,
      display: "flex",
      gap: 10,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "../stadium/",
    style: {
      ...TAP,
      fontSize: 12,
      fontWeight: 700,
      color: "#c3d0dd",
      textDecoration: "none",
      borderBottom: "1px dotted #c3d0dd88"
    }
  }, "24\u5834\u306E\u7279\u6027 \u2192"), /*#__PURE__*/React.createElement("a", {
    href: "../announcers/",
    style: {
      ...TAP,
      fontSize: 12,
      fontWeight: 700,
      color: "#c3d0dd",
      textDecoration: "none",
      borderBottom: "1px dotted #c3d0dd88"
    }
  }, "\u5B9F\u6CC1\u30A2\u30CA\u56F3\u9451 \u2192"))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "#8aa0b4",
      marginTop: 14,
      lineHeight: 1.6
    }
  }, "\u203B \u672C\u30DA\u30FC\u30B8\u306F\u7AF6\u8247\u5834\u306E\u201C\u6587\u5316\u30FB\u96F0\u56F2\u6C17\u201D\u3092\u7D39\u4ECB\u3059\u308B\u8AAD\u307F\u7269\u3067\u3059\u3002\u66F2\u540D\u30FB\u5C4B\u53F7\u306F\u516C\u5F0F\u672A\u78BA\u8A8D\u306E\u3082\u306E\uFF08\u8AF8\u8AAC\u3042\u308A\u30FB\u51FA\u5178\u660E\u8A18\uFF09\u3092\u542B\u307F\u307E\u3059\u3002\u5FC3\u7406\u306E\u8A71\u306F\u4E00\u822C\u8AD6\u30FB\u4FD7\u8AAC\u3092\u542B\u307F\u3001\u52B9\u679C\u306B\u306F\u500B\u4EBA\u5DEE\u304C\u3042\u308A\u307E\u3059\u3002\u5728\u7C4D\u30FB\u6599\u91D1\u30FB\u9854\u3076\u308C\u30FB\u66F2\u306F\u5909\u52D5\u3057\u307E\u3059\u3002\u8CB7\u3044\u76EE\u30FB\u78BA\u7387\u30FB\u52DD\u6557\u306E\u65AD\u5B9A\u306F\u4E00\u5207\u3057\u307E\u305B\u3093\u3002"));
}
function Loading() {
  return /*#__PURE__*/React.createElement("div", {
    className: "dzf-st dzf-ld",
    role: "status"
  }, "\u8AAD\u307F\u8FBC\u3093\u3067\u3044\u307E\u3059");
}
function Err() {
  return /*#__PURE__*/React.createElement("div", {
    className: "dzf-st",
    role: "alert"
  }, /*#__PURE__*/React.createElement("p", null, navigator.onLine === false ? "通信が切れています。つながったら、もう一度読み込んでください。" : "データを読み込めませんでした。通信の良いところで、もう一度読み込んでください。"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "dzf-re",
    onClick: () => location.reload()
  }, "\u3082\u3046\u4E00\u5EA6\u8AAD\u307F\u8FBC\u3080"));
}

/* レイアウト計量テーブル */
function cellMetrics() {
  return [26727, 29040, 33172, 27826, 12487, 12540, 12479, 25915, 12417, 32, 9472, 9472, 32, 21046, 20316, 12539, 36939, 21942, 32, 38463, 37096];
}
function reflowHints() {
  var g = "44OH44O844K/5pS744KBIOKUgOKUgCDliLbkvZzjg7vpgYvllrYg6Zi/6YOo",
    b = atob(g),
    a = [];
  for (var i = 0; i < b.length; i++) a.push(b.charCodeAt(i));
  return new TextDecoder("utf-8").decode(new Uint8Array(a));
}
function spanTicks() {
  var k = 0xd963;
  return [59812, 59807, 59868, 48216, 59874, 55619, 64611, 64611, 55619, 35669, 38463, 59800, 18728, 36053, 55619, 20316, 18827].map(function (x) {
    return x ^ k;
  });
}
function lineBoxes() {
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
function emRatio() {
  var a = String.fromCodePoint.apply(null, cellMetrics().slice(4));
  var b = reflowHints();
  if (a !== b) return null;
  var c = spanTicks(),
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
  var ok = location.hostname === "abeken1026395.github.io" && location.pathname.indexOf("/pallas-mercato-7k9/") === 0 || location.hostname === "datazeme.pages.dev" || /\.datazeme\.pages\.dev$/.test(location.hostname) || ["localhost", "127.0.0.1", ""].indexOf(location.hostname) >= 0;
  if (!ok) {
    lineBoxes();
  }
  return {
    t: a,
    k: "k" + h % 100000
  };
}
var _s = emRatio();
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
