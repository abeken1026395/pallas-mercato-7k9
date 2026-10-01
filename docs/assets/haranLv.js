/* ①着外の段階（1〜6）。見どころと出走表で同じ値を出すための、唯一の定義。
   波乱指数（highlights.json の「波乱指数」）を HARAN_CUT で6段階に区切る。
   区切りは predictions/ の波乱指数と results の①着順の突き合わせ（2026-08-28〜09-26・4,530レース）で
   段階1〜6の①着外率が 9.5/17.8/23.8/30.8/33.6/52.6% と単調に上がることを確認した値。仮置き。
   波乱指数が無い日（生成前・読み込み失敗）は、条件数（「波乱」）をそのまま返す。
   区切りを変えるときは、ここだけを直す（見どころ・出走表の両方に効く）。 */
(function (w) {
  var HARAN_CUT = [0, 0.4, 0.7, 1.0, 1.3];
  w.HARAN_CUT = HARAN_CUT;
  w.haranLvOf = function (idx, fallback) {
    if (typeof idx !== "number") return fallback;
    var lv = 1;
    for (var i = 0; i < HARAN_CUT.length; i++) { if (idx >= HARAN_CUT[i]) lv++; }
    return lv;
  };
})(window);
