// 見分けに使う材料は、Pages の秘密の環境変数 DZ_TRAP（JSON）にだけ置く。コードには書かない（2026-11-23 けん裁定）。
// 無い・壊れているときは、どの見分けも働かない（本物か関門に回る）。
let memoRaw = null, memoCfg = null;

export function trapCfg(env) {
  const raw = String((env && env.DZ_TRAP) || "");
  if (raw === memoRaw) return memoCfg;
  let o = {};
  try { o = JSON.parse(raw) || {}; } catch (e) { o = {}; }
  const list = v => (Array.isArray(v) ? v.map(x => String(x).toLowerCase()).filter(Boolean) : []);
  memoRaw = raw;
  memoCfg = {
    ai: list(o.ai),
    scr: list(o.scr),
    asn: Array.isArray(o.asn) ? o.asn.map(Number).filter(Boolean) : [],
    chk: typeof o.chk === "string" ? o.chk : "",
    kana: typeof o.kana === "string" && o.kana.length >= 8 ? o.kana : "",
    tail: Array.isArray(o.tail) && o.tail.length ? o.tail.map(String) : [""],
    pre: typeof o.pre === "string" ? o.pre : "",
  };
  return memoCfg;
}
