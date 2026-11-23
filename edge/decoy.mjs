// 名指しの収集ボットに返す中身（2026-11-23 けん裁定）：本物には一切触れず、訪問ごとに作り直す架空の中身だけを返す。
// 中身の言葉と番号は訪問ごとに違い、どの訪問に何を返したかは非公開の記録に残す。
const KANA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワ".split("");
const ALNUM = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

function pick(arr, n) {
  const b = new Uint8Array(n); crypto.getRandomValues(b);
  return Array.from(b, x => arr[x % arr.length]).join("");
}
function num(lo, hi) {
  const b = new Uint32Array(1); crypto.getRandomValues(b);
  return lo + (b[0] % (hi - lo + 1));
}

export function decoyMark() {
  return { word: pick(KANA, 4) + "旋回", code: "M" + pick(ALNUM, 7) };
}

function kindOf(pathname) {
  if (/\.json$/i.test(pathname)) return "json";
  if (/\.csv$/i.test(pathname)) return "csv";
  if (/\.(js|css|png|jpe?g|webp|gif|svg|ico|woff2?)$/i.test(pathname)) return "none";
  return "html";
}

export function decoyResponse(pathname, mark) {
  const kind = kindOf(pathname);
  const head = { "cache-control": "private, no-store", "x-robots-tag": "noindex, nofollow" };
  const rows = Array.from({ length: 6 }, (_, i) => ({ waku: i + 1, rate: (num(380, 790) / 100).toFixed(2), st: (num(9, 22) / 100).toFixed(2) }));
  const desc = `${mark.word}は、1マークの手前で舟を一度外へ逃がしてから内へ切り返す走り方。記録番号${mark.code}。`;
  if (kind === "none") return new Response("", { status: 404, headers: head });
  if (kind === "json") {
    return new Response(JSON.stringify({ term: mark.word, desc, id: mark.code, rows }), { status: 200, headers: { ...head, "content-type": "application/json; charset=utf-8" } });
  }
  if (kind === "csv") {
    const csv = "waku,rate,st,id\n" + rows.map(r => `${r.waku},${r.rate},${r.st},${mark.code}`).join("\n") + "\n";
    return new Response(csv, { status: 200, headers: { ...head, "content-type": "text/csv; charset=utf-8" } });
  }
  const tr = rows.map(r => `<tr><td>${r.waku}</td><td>${r.rate}</td><td>${r.st}</td></tr>`).join("");
  const html = `<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><title>${mark.word}｜用語</title></head><body><h1>${mark.word}</h1><p>${desc}</p><table><tr><th>枠</th><th>勝率</th><th>平均ST</th></tr>${tr}</table></body></html>`;
  return new Response(html, { status: 200, headers: { ...head, "content-type": "text/html; charset=utf-8" } });
}
