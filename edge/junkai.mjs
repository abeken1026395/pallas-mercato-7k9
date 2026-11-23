// 共通の小道具：接続元のまとめ方と、日本時間の日付。

export function ipKey(ip) {
  if (!ip) return "";
  if (ip.includes(":")) return ip.toLowerCase().split(":").slice(0, 4).join(":") + "::/64";
  return ip;
}

export function jstDay(now = Date.now()) {
  return new Date(now + 9 * 3600000).toISOString().slice(0, 10);
}
