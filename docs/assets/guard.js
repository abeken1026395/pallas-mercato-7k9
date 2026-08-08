/* データ攻め コピー検知。判定式はこのファイルにのみ置く。URL変更時はここだけ直す。 */
(function () {
  var ok = ((location.hostname === "abeken1026395.github.io"
    && location.pathname.indexOf("/pallas-mercato-7k9/") === 0)
    || ["localhost", "127.0.0.1", ""].indexOf(location.hostname) >= 0);
  if (ok) return;
  var d = document.createElement("div");
  d.style.cssText = "position:relative;background:#b3261e;color:#fff;padding:12px 44px 12px 12px;font-size:13px;line-height:1.7;text-align:center";
  d.innerHTML = '<strong>このページは本物ではありません。</strong><br>「データ攻め」の無断複製です。 <a href="https://www.youtube.com/@abe-ken" target="_blank" rel="noopener" style="color:#ffd166;font-weight:700;text-decoration:underline">本物を見る（YouTube「あべけん」）</a>';
  var b = document.createElement("button");
  b.type = "button";
  b.setAttribute("aria-label", "閉じる");
  b.textContent = "\u00d7";
  b.style.cssText = "position:absolute;top:2px;right:2px;width:40px;height:40px;background:none;border:0;color:#fff;font-size:20px;line-height:40px;cursor:pointer";
  b.addEventListener("click", function () { d.parentNode.removeChild(d); });
  d.appendChild(b);
  document.body.insertBefore(d, document.body.firstChild);
})();
