/* サイト共通の枠（プロ化3・2026-11-07 けん「本番に反映してくれ」・第2弾「本番へ」・第3弾 全ページへ・第4弾 細部・第5弾 動き・第6弾 素人感の掃除）。トップと同じ上の帯（ロゴ・データ攻め・選手検索）と下の5つのタブを、どのページにも出す。
   置き場所：assets/siteFrame.js。読み込む側は <script src="（ルートからの相対）assets/siteFrame.js" defer></script>。
   ルートはこのファイル自身の場所から割り出す（ページの深さに関係なく正しいリンクになる）。
   トップ（index.html）は自前の帯とタブを持つので何もしない。 */
(function(){
  // 本文を出す（kata.css とページの頭で、枠が付くまで隠している）。枠を付け、文字の大きさをそろえ終えてから出す（出した後にずれないように。2026-11-09）
  function dzfOk(){
    // 題字の印（kata.js が DOMContentLoaded で付ける）が出す前に付いていないと、出した後に題字の大きさが変わってずれる。h1 があれば先に付けておく
    try { if (!document.querySelector(".kataTitle")) { var h = document.querySelector("h1"); if (h && !h.closest(".kataNote")) h.classList.add("kataTitle"); } } catch (e) {}
    document.documentElement.classList.add("dzf-ok");
  }
  // 取れなかったときの表示（全ページ共通の文言。見た目は kata.css の .dzf-st）。圏外なら「通信が切れています」
  window.dzfErrHtml = function(){ var off = navigator.onLine === false; return '<div class="dzf-st" role="alert"><p>' + (off ? "通信が切れています。つながったら、もう一度読み込んでください。" : "データを読み込めませんでした。通信の良いところで、もう一度読み込んでください。") + '</p><button type="button" class="dzf-re" onclick="location.reload()">もう一度読み込む</button></div>'; };
  // 隠したまま1回描かせて（このとき最終の並びが決まる）から出す。描く前に出すと、出した瞬間に並びが変わったと数えられてずれる。rAF が止まる裏のタブでは時間で出す
  function dzfOkSoon(){ try { requestAnimationFrame(function(){ requestAnimationFrame(dzfOk); }); } catch (e) {} setTimeout(dzfOk, 120); }
  if (window.__dzFrame) { dzfOkSoon(); return; } window.__dzFrame = 1;
  var me = document.currentScript || document.querySelector('script[src*="assets/siteFrame.js"]');
  function go(){ try { run(me); } finally { dzfOkSoon(); } }
  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", go); } else { go(); }
  function run(me){
  var ROOT = me ? me.src.replace(/assets\/siteFrame\.js.*$/, "") : (location.origin + "/");
  var here = location.href.split(/[?#]/)[0];
  if (here === ROOT || here === ROOT + "index.html" || document.querySelector("header.bar .brand")) return;
  var vm = document.querySelector('meta[name="viewport"]'); if (vm && !/viewport-fit/.test(vm.content)) vm.content += ", viewport-fit=cover";
  // iPhone は16px未満の入力欄を押すと画面ごと拡大してずれる。iPhone だけ自動の拡大を止める（iOS は指での拡大を止めない。Android には付けない）
  if (vm && /iP(hone|ad|od)/.test(navigator.userAgent) && !/maximum-scale/.test(vm.content)) vm.content += ", maximum-scale=1";
  // 動き 第2版（ugoki）を読んでいないページ（場の朝刊・整備・検証の一部）にも読み込む（2026-11-07 けん「2」）
  if (!document.querySelector('script[src*="assets/ugoki.js"]')) {
    var uc = document.createElement("link"); uc.rel = "stylesheet"; uc.href = ROOT + "assets/ugoki.css?v=a0c08edf"; document.head.appendChild(uc);
    var uj = document.createElement("script"); uj.src = ROOT + "assets/ugoki.js?v=e40e8a0a"; document.body.appendChild(uj);
  }
  var LOGO = "M 548 730 C 540 734, 525 741, 515 745 C 401 796, 280 883, 194 974 C 170 1000, 124 1058, 113 1076 C 65 1155, 45 1218, 50 1272 C 57 1336, 109 1382, 193 1400 C 218 1405, 227 1405, 242 1403 C 247 1402, 262 1400, 276 1398 C 326 1391, 348 1386, 390 1373 C 428 1361, 431 1359, 433 1353 C 434 1348, 432 1347, 419 1344 C 373 1335, 328 1310, 309 1283 C 295 1264, 280 1223, 278 1202 C 276 1175, 282 1130, 293 1101 C 309 1056, 337 1005, 364 969 C 407 915, 452 870, 521 815 C 559 783, 603 755, 678 715 C 721 691, 724 690, 727 686 C 730 680, 727 676, 720 676 C 708 676, 666 687, 635 697 C 626 700, 611 705, 602 708 C 583 714, 567 721, 548 730 M 1306 815 C 1221 826, 1174 916, 1216 989 C 1221 996, 1221 999, 1222 1005 C 1223 1014, 1222 1013, 1258 1043 C 1294 1073, 1298 1075, 1308 1074 C 1314 1074, 1380 1063, 1398 1059 C 1411 1056, 1415 1042, 1405 1035 C 1404 1034, 1384 1024, 1362 1012 C 1339 1000, 1319 989, 1318 987 C 1312 982, 1313 979, 1323 960 C 1340 927, 1342 924, 1350 925 C 1352 926, 1369 935, 1389 945 C 1428 966, 1432 967, 1439 964 C 1455 955, 1448 904, 1426 871 C 1401 833, 1350 809, 1306 815 M 1062 906 C 1036 907, 998 916, 970 927 C 916 949, 878 975, 832 1020 C 807 1045, 791 1067, 770 1099 C 757 1121, 737 1159, 736 1166 C 734 1174, 740 1181, 748 1181 C 752 1181, 839 1164, 878 1155 C 892 1152, 918 1146, 934 1143 C 965 1137, 973 1135, 1048 1122 C 1072 1118, 1104 1112, 1119 1109 C 1134 1106, 1159 1102, 1175 1099 C 1207 1094, 1211 1093, 1214 1088 C 1220 1079, 1217 1074, 1198 1058 C 1178 1042, 1171 1032, 1169 1016 C 1167 1007, 1166 1002, 1161 987 C 1154 969, 1152 957, 1151 938 C 1151 923, 1150 921, 1148 918 C 1141 909, 1106 904, 1062 906 M 1898 1068 C 1892 1068, 1879 1069, 1870 1070 C 1861 1071, 1846 1072, 1836 1073 C 1826 1074, 1809 1076, 1797 1077 C 1719 1084, 1472 1120, 1365 1140 C 1350 1143, 1320 1148, 1298 1152 C 1276 1156, 1250 1161, 1240 1162 C 1231 1164, 1206 1169, 1186 1172 C 1167 1175, 1139 1180, 1124 1183 C 1109 1186, 1077 1192, 1052 1196 C 959 1213, 954 1214, 908 1224 C 893 1227, 853 1236, 819 1243 C 692 1268, 542 1304, 523 1314 C 496 1328, 504 1349, 539 1359 C 570 1368, 583 1369, 678 1370 C 763 1370, 777 1370, 812 1366 C 821 1365, 837 1364, 846 1363 C 856 1362, 865 1362, 868 1361 C 917 1355, 959 1351, 977 1349 C 989 1348, 1006 1346, 1016 1345 C 1026 1344, 1042 1343, 1052 1342 C 1061 1341, 1078 1340, 1089 1339 C 1133 1335, 1247 1334, 1282 1337 C 1289 1338, 1309 1340, 1325 1341 C 1390 1347, 1464 1363, 1534 1385 C 1579 1399, 1588 1401, 1603 1397 C 1621 1393, 1626 1389, 1681 1342 C 1707 1320, 1819 1227, 1850 1201 C 1912 1151, 1949 1120, 1956 1112 C 1969 1096, 1969 1083, 1955 1072 C 1947 1066, 1928 1064, 1898 1068 M 540 1151 C 531 1154, 517 1167, 515 1175 C 515 1177, 513 1203, 511 1232 C 508 1282, 508 1284, 510 1287 C 513 1295, 521 1297, 534 1293 C 537 1292, 559 1286, 581 1281 C 624 1270, 626 1269, 629 1263 C 632 1258, 632 1259, 623 1208 C 614 1159, 614 1156, 608 1152 C 604 1150, 547 1149, 540 1151 M 1132 1401 C 1073 1404, 968 1424, 902 1445 C 867 1455, 733 1493, 714 1498 C 676 1508, 630 1515, 596 1518 C 586 1519, 567 1521, 554 1523 C 525 1526, 464 1527, 442 1524 C 346 1513, 307 1504, 238 1479 C 195 1464, 192 1463, 185 1467 C 182 1469, 179 1474, 179 1478 C 179 1493, 239 1539, 297 1568 C 364 1602, 413 1616, 498 1626 C 617 1640, 734 1621, 898 1560 C 1002 1521, 1080 1498, 1142 1487 C 1199 1477, 1221 1476, 1306 1476 C 1382 1477, 1401 1478, 1461 1489 C 1486 1494, 1491 1493, 1495 1485 C 1501 1473, 1491 1466, 1445 1448 C 1389 1426, 1341 1414, 1269 1405 C 1239 1400, 1167 1398, 1132 1401";
  var css = ":root{--dzf-bar:#0e1d30;--dzf-line:rgba(255,255,255,.09);--dzf-tx:#eef3f8;--dzf-dim:#a3b4c6}"
  + ".dzf-bar{position:relative;z-index:60;background:var(--dzf-bar);border-bottom:1px solid var(--dzf-line);margin:0 0 4px}"
  + ".dzf-in{max-width:600px;height:52px;margin:0 auto;display:flex;align-items:center;padding:0 16px;box-sizing:border-box}"
  + ".dzf-brand{display:flex;align-items:center;gap:9px;text-decoration:none!important;color:var(--dzf-tx)!important;border:0!important;background:none!important;padding:0!important;margin:0!important}"
  + ".dzf-brand svg{height:30px;width:auto;display:block}"
  + ".dzf-wm{display:flex;flex-direction:column;gap:4px;line-height:1}"
  + ".dzf-wm b{font:400 19px/1 'Dela Gothic One',sans-serif!important;letter-spacing:.04em;color:var(--dzf-tx)!important;white-space:nowrap}"
  + ".dzf-wm i{font:400 9px/1 'Dela Gothic One',sans-serif!important;font-style:normal!important;letter-spacing:.42em;color:var(--dzf-dim)!important;white-space:nowrap}"
  + ".dzf-sp{flex:1}"
  + ".dzf-sr{display:flex;align-items:center;justify-content:center;width:44px;height:44px;margin-right:-10px;border:0!important;background:none!important}"
  + ".dzf-sr svg,.dzf-tb svg,.dzf-sh svg{fill:none;stroke-linecap:round;stroke-linejoin:round}"
  + ".dzf-sr svg{width:22px;height:22px;stroke:#dfe7ef;stroke-width:1.6}"
  + ".dzf-waku{display:flex;height:3px}.dzf-waku i{flex:1}"
  + ".dzf-waku i:nth-child(1){background:#f4f4f4}.dzf-waku i:nth-child(2){background:#000}.dzf-waku i:nth-child(3){background:#e2313a}.dzf-waku i:nth-child(4){background:#2b6fdc}.dzf-waku i:nth-child(5){background:#f2d02e}.dzf-waku i:nth-child(6){background:#2fa04f}"
  + ".dzf-tb{position:fixed;left:0;right:0;bottom:0;z-index:60;background:var(--dzf-bar);border-top:1px solid var(--dzf-line);padding-bottom:env(safe-area-inset-bottom)}"
  + ".dzf-tbi{max-width:600px;margin:0 auto;display:grid;grid-template-columns:repeat(5,1fr);height:58px}"
  + ".dzf-tb a,.dzf-tb button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;background:none!important;border:0!important;margin:0!important;padding:0!important;font:600 11px/1 -apple-system,'Hiragino Sans','Noto Sans JP',sans-serif!important;color:var(--dzf-dim)!important;text-decoration:none!important;cursor:pointer;border-radius:0!important}"
  + ".dzf-tb .on{color:var(--dzf-tx)!important}"
  + ".dzf-tb svg{width:24px;height:24px;stroke:currentColor;stroke-width:1.5}"
  + ".dzf-sh{position:fixed;left:0;right:0;bottom:calc(58px + env(safe-area-inset-bottom));z-index:59;background:var(--dzf-bar);border-top:1px solid var(--dzf-line);max-height:calc(100vh - 136px - env(safe-area-inset-bottom));max-height:calc(100dvh - 136px - env(safe-area-inset-bottom));overflow-y:auto;overscroll-behavior:contain}"
  + ".dzf-sh[hidden]{display:none}"
  + ".dzf-sh{opacity:0;transform:translateY(10px);transition:opacity .16s ease-out,transform .16s ease-out}.dzf-sh.in{opacity:1;transform:none}@media (prefers-reduced-motion:reduce){.dzf-sh{transition:none}}"
  + ".dzf-shi{max-width:600px;margin:0 auto;display:grid;grid-template-columns:repeat(2,1fr)}"
  + ".dzf-sh a{display:flex;align-items:center;height:52px;padding:0 18px;border-bottom:1px solid var(--dzf-line);font:600 15px/1 -apple-system,'Hiragino Sans','Noto Sans JP',sans-serif!important;color:var(--dzf-tx)!important;text-decoration:none!important;background:none!important;border-radius:0!important}"
  + ".dzf-sh a:nth-of-type(odd){border-right:1px solid var(--dzf-line)}"
  + ".dzf-sh a.full{grid-column:1/-1;border-right:0}.dzf-sh .sh2{grid-column:1/-1;padding:12px 18px 4px;font-size:11px;color:var(--dzf-dim);border-bottom:1px solid var(--dzf-line)}"
  + "body{padding-bottom:calc(66px + env(safe-area-inset-bottom))!important}"
  + "body>a.siteback,body>a.sitelink,body>.siteback,body>.sitelink{display:none!important}"
  /* ページの頭の型（大見出し → 1行の説明 → 小さい字の更新・出典）と「このページの見方」の形。全ページで同じにする */
  + ".kataTitle{font-size:24px!important;margin-top:18px!important;line-height:1.3!important}header .reader-line,header .lead1,header>.lead{font-size:14px!important;line-height:1.75!important;color:#c3d0dd!important;margin-top:4px!important}header .reader-line b{font-weight:700;color:#eef3f8}header .sub,header .date{font-size:12px!important;color:#8fa3b8!important;margin-top:6px!important;letter-spacing:.02em}header details.pageHow{margin-top:10px;border-top:1px solid rgba(255,255,255,.09);border-bottom:1px solid rgba(255,255,255,.09)}header details.pageHow summary{min-height:44px;display:flex;align-items:center;font-size:13px;font-weight:700;color:#c3d0dd;cursor:pointer;padding:0;list-style:none}header details.pageHow summary::after{content:\"＋\";margin-left:auto;color:#8fa3b8}header details.pageHow[open] summary::after{content:\"－\"}header details.pageHow .lead{font-size:13px!important;color:#a3b4c6!important;margin:0 0 10px!important}.rpay{white-space:nowrap}.wrap>header,body>header{padding-top:0!important;margin-top:0!important}.kataTitle{margin-top:16px!important}header details.howto{margin-top:10px!important;border:0!important;border-top:1px solid rgba(255,255,255,.09)!important;border-bottom:1px solid rgba(255,255,255,.09)!important;background:none!important;padding:0!important}header details.howto>summary{min-height:44px;display:flex!important;align-items:center;font-size:13px!important;font-weight:700;color:#c3d0dd!important;padding:0!important;list-style:none}header details.howto>summary::-webkit-details-marker{display:none}header details.howto>summary::after{content:\"＋\";margin-left:auto;color:#8fa3b8}header details.howto[open]>summary::after{content:\"－\"}"
  /* 表の作法（プロ化3 第2弾・2026-11-07 けん「本番へ」）：枠番の札はトップの6色・四角、級別はA1赤・A2橙・B1青・B2灰、選んでいるタブは白地に紺、表の見出しは小さく薄く下に1本線、表の中のリンクは下線なし */
  + ".ns-lane,.lane-num,.badge.b1,.badge.b2,.badge.b3,.badge.b4,.badge.b5,.badge.b6,.wk{border-radius:0!important;border:0!important;font-weight:800!important}.lane-num.l1,.ns-lane.l1,.badge.b1,.wk1{background:#f4f4f4!important;color:#0b1726!important}.lane-num.l2,.ns-lane.l2,.badge.b2,.wk2{background:#000!important;color:#fff!important;box-shadow:inset 0 0 0 1px #7d8da0!important}.lane-num.l3,.ns-lane.l3,.badge.b3,.wk3{background:#d82a33!important;color:#fff!important}.lane-num.l4,.ns-lane.l4,.badge.b4,.wk4{background:#2b6fdc!important;color:#fff!important}.lane-num.l5,.ns-lane.l5,.badge.b5,.wk5{background:#f2d02e!important;color:#0b1726!important}.lane-num.l6,.ns-lane.l6,.badge.b6,.wk6{background:#1f8540!important;color:#fff!important}.klass,.lv{border-radius:0!important;font-size:11px!important;font-weight:800!important;line-height:1!important;padding:3px 4px!important;min-width:0!important;height:auto!important;display:inline-block!important}.k-A1,.lvA1{background:#c8323a!important;color:#fff!important}.k-A2,.lvA2{background:#d9772e!important;color:#0b1726!important}.k-B1,.lvB1{background:#2b6fdc!important;color:#fff!important}.k-B2,.lvB2{background:#5c6773!important;color:#fff!important}.navtab.on,.sortbtn.on,.dsw-btn.on,.tabs .tab.on{background:#eef3f8!important;color:#0b1726!important;border-color:#eef3f8!important;border-radius:0!important}.navtab,.sortbtn,.dsw-btn,.tabs .tab{border-radius:0!important}.wrap th,#out th,body th{font-size:12px!important;font-weight:600!important;color:#8fa3b8!important;letter-spacing:.04em;border-bottom:1px solid rgba(255,255,255,.12)!important;background:none!important}td a,.nm a{text-decoration:none!important}"
  /* 第4弾（2026-11-07 けん「a」）：角は四角（10/23）・選んでいる札は白地に紺・英字の小見出しは出さない */
  + "button:not(.dzf-tb button),.chip,.chipbtn,.it,span.p,details.fold,figure.chart,p.lead,.wrap img,.lead,.note1,.yomi,.curvefig,.scalefig,.gapfig,.card,.wrap details,section.watch,span.bar,span.track,.histfig,.wfig{border-radius:0!important}html body .chip.on,html body .chipbtn.on,.chipbtn[aria-pressed=\"true\"],.tab[aria-selected=\"true\"],button.tab.on{background:#eef3f8!important;color:#0b1726!important;border-color:#eef3f8!important}header .eyebrow,#hero h1>small{display:none!important}";
  // 共通の型（kata.css）を読まないページは、地の紺・書体・題字だけそろえる。場の朝刊は新聞の色を残す（けん「a」）
  if (!document.querySelector('link[href*="kata/kata.css"]') && !/\/choukan\//.test(location.pathname)) css += "html{background:#0d1c2f!important}body{background:transparent!important;font-family:-apple-system,'Hiragino Sans','Noto Sans JP',sans-serif!important}h1{font-family:'Dela Gothic One',-apple-system,sans-serif!important;font-weight:400!important;color:#f2f2f0!important;-webkit-text-fill-color:#f2f2f0!important;padding-bottom:10px!important;border-bottom:1px solid rgba(212,176,106,.6)!important;margin-bottom:12px!important;background:none!important;letter-spacing:.02em}";
  /* 第6弾（2026-11-07 けん「進めて」）：札の形を1つに・見立ての文を本文の強さに・出走表のボタンを同じ線に・空の案内枠を出さない */
  css += ":root body .nichi,:root body .kikaku,:root body .badge:not(.b1):not(.b2):not(.b3):not(.b4):not(.b5):not(.b6),:root body .soon-badge,:root body .bunrui,:root body .rmitate .lbl,:root body .fortune-tag{background:none!important;border:1px solid rgba(255,255,255,.2)!important;color:#c3d0dd!important;font-size:11.5px!important;font-weight:600!important;padding:2px 6px!important;border-radius:0!important;letter-spacing:.02em}:root body .bunrui.b-are{border-color:rgba(242,177,85,.65)!important;color:#f2b155!important}:root body .bunrui.b-kata{border-color:rgba(92,200,176,.6)!important;color:#5cc8b0!important}:root body .rmitate{font-size:14px!important;line-height:1.75!important;color:#d5dee8!important;font-weight:400!important}:root body a.harvest-link,:root body button.harvest-x,:root body button.harvest-all{background:none!important;border:1px solid rgba(255,255,255,.28)!important;color:#eef3f8!important;border-radius:0!important;font-weight:600!important}:root body .a2hs:empty{display:none!important}:root body .watchbtn,:root body a.offlink,:root body a.chip-link{background:none!important;border:1px solid rgba(255,255,255,.28)!important;color:#eef3f8!important;border-radius:0!important;font-weight:600!important}:root body .watchbtn.on{background:#eef3f8!important;color:#0b1726!important;border-color:#eef3f8!important}";
  /* 第7弾（2026-11-08 けん「まとめて改善しよう」）：プロとの差を実測で潰す。
     ・iPhone で入力欄を押したときの画面ごとの拡大を止める（指での拡大はそのまま使える）
     ・小さい押し場所は、見た目を変えずに押せる範囲を広げる（44px 目安）
     ・白い文字の札で読みにくい色（赤4.4・緑3.4・橙3.2）を、同じ色味のまま読める濃さに
     ・「その他」は後ろを暗くし、後ろのページを動かさない。閉じたら元の位置のまま */
  css += "button[title=\"推しフォロー\"],button[title=\"この場をフォロー\"],a.xs,a.jump{position:relative}"
    + "button[title=\"推しフォロー\"]::after,button[title=\"この場をフォロー\"]::after,a.xs::after,a.jump::after{content:\"\";position:absolute;left:-10px;right:-10px;top:-12px;bottom:-12px}"
    + ".gr.gA1{background:#c8323a!important;color:#fff!important}.gr.gA2{background:#d9772e!important;color:#0b1726!important}"
    + ".c.C3{background:#d82a33!important}.c.C6{background:#1f8540!important}.jimoto{background:#2b6fdc!important}"
    + ".dzf-bd{position:fixed;left:0;right:0;top:0;bottom:0;z-index:58;background:rgba(4,10,18,.6)}.dzf-bd[hidden]{display:none}"
    + ".dzf-tb .dzf-op{color:var(--dzf-tx)!important}"
    + ".dzf-bar{padding-top:env(safe-area-inset-top)}"
    + "@media (prefers-reduced-motion:reduce){.dzf-sh{transition:none!important;transform:none!important}}";
  /* 第13弾（2026-11-08 けん「全部色がおかしい」）：ページ側の型（kata/*.css）の色が枠に漏れないよう、枠の色をいちばん強い指定で固定する。:is(#dzfZ,…) は指定を強くするためだけのもの（#dzfZ という要素は無い） */
  css += ".dzf-bar:is(#dzfZ,.dzf-bar),.dzf-tb:is(#dzfZ,.dzf-tb),.dzf-sh:is(#dzfZ,.dzf-sh){background:var(--dzf-bar)!important}"
    + ".dzf-tb:is(#dzfZ,.dzf-tb) a,.dzf-tb:is(#dzfZ,.dzf-tb) button{color:var(--dzf-dim)!important;-webkit-text-fill-color:currentColor!important;background:none!important;border:0!important;text-shadow:none!important;box-shadow:none!important;opacity:1!important}"
    + ".dzf-tb:is(#dzfZ,.dzf-tb) .on,.dzf-tb:is(#dzfZ,.dzf-tb) .dzf-op{color:var(--dzf-tx)!important}"
    + ".dzf-sh:is(#dzfZ,.dzf-sh) a{color:var(--dzf-tx)!important;-webkit-text-fill-color:currentColor!important;background:none!important;border:0!important;border-bottom:1px solid var(--dzf-line)!important;text-shadow:none!important;box-shadow:none!important;opacity:1!important}"
    + ".dzf-sh:is(#dzfZ,.dzf-sh) a:nth-of-type(odd){border-right:1px solid var(--dzf-line)!important}.dzf-sh:is(#dzfZ,.dzf-sh) a.full{border-right:0!important}"
    + ".dzf-sh:is(#dzfZ,.dzf-sh) .sh2{color:var(--dzf-dim)!important;-webkit-text-fill-color:currentColor!important;background:none!important}"
    + ".dzf-bar:is(#dzfZ,.dzf-bar) a{-webkit-text-fill-color:currentColor!important;text-shadow:none!important;box-shadow:none!important}.dzf-bar:is(#dzfZ,.dzf-bar) .dzf-brand{color:var(--dzf-tx)!important;background:none!important;border:0!important}.dzf-bar:is(#dzfZ,.dzf-bar) .dzf-wm b{color:var(--dzf-tx)!important}.dzf-bar:is(#dzfZ,.dzf-bar) .dzf-wm i{color:var(--dzf-dim)!important}.dzf-bar:is(#dzfZ,.dzf-bar) .dzf-sr{background:none!important;border:0!important}";
  var st = document.createElement("style"); st.id = "dzfCss"; st.textContent = css; document.head.appendChild(st);
  // 押したときの反応（2026-11-09）：指が触れたら札・ボタン・リンクを少し薄くして「押せた」と分かるようにする。
  // 0.05秒待ってから薄くするので、スクロールのつもりで触れただけのときはちらつかない。iPhone は touchstart の受け手が無いと :active が効かないので空の受け手を置く
  st.appendChild(document.createTextNode("a[href]:active,button:not(:disabled):active,summary:active,[role=button]:active,[role=tab]:active,label[for]:active{opacity:.6;transition:opacity 0s linear .05s}.dzf-tb:is(#dzfZ,.dzf-tb) a:active,.dzf-tb:is(#dzfZ,.dzf-tb) button:active,.dzf-sh:is(#dzfZ,.dzf-sh) a:active{opacity:.6!important;transition:opacity 0s linear .05s}"));
  try { document.addEventListener("touchstart", function(){}, { passive: true }); } catch (e) {}
  // 改行の位置（2026-11-09）：見出しや札は行の長さをそろえて折り、本文は最後の行に1、2文字だけ残らないように折る（対応していない端末では今までどおり）。検証のページは本文に触らない
  if (!/\/kensho\//.test(location.pathname)) st.appendChild(document.createTextNode("h1,h2,h3,h4,h5,summary,button,th,dt,label,.kataTitle{text-wrap:balance}p,li,dd,td,div,blockquote,figcaption,span{text-wrap:pretty}"));
  if (!document.querySelector('link[href*="Dela+Gothic+One"]')) {
    var lf = document.createElement("link"); lf.rel = "stylesheet"; lf.href = "https://fonts.googleapis.com/css2?family=Dela+Gothic+One&display=swap"; document.head.appendChild(lf);
  }
  var I = {
    top:'<svg viewBox="0 0 24 24"><path d="M3.5 11L12 4l8.5 7"/><path d="M6 9.5V20h12V9.5"/></svg>',
    racers:'<svg viewBox="0 0 24 24"><rect x="3.5" y="4" width="17" height="16"/><path d="M3.5 9.3h17M3.5 14.6h17M8 4v16"/></svg>',
    highlights:'<svg viewBox="0 0 24 24"><path d="M5 21V3.5"/><path d="M5 4.5c3-1.6 5.5 1.6 8.5 0s4.5-.6 5.5 0v7.5c-1-.6-2.5-1.6-5.5 0S8 10.4 5 12"/></svg>',
    results:'<svg viewBox="0 0 24 24"><path d="M5 21V3.5"/><rect x="5" y="4" width="14" height="9"/><path d="M5 7h14M5 10h14M8.5 4v9M12 4v9M15.5 4v9"/></svg>',
    more:'<svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'
  };
  var path = here.slice(ROOT.length);
  var cur = /^racers\//.test(path) ? "racers" : /^highlights\//.test(path) ? "highlights" : /^results\//.test(path) ? "results" : "more";
  var bar = document.createElement("div"); bar.className = "dzf-bar";
  bar.innerHTML = '<div class="dzf-in"><a class="dzf-brand" href="' + ROOT + '" aria-label="データ攻め トップ"><svg viewBox="49 676 1917 955" aria-hidden="true"><path fill="#e9b45a" fill-rule="evenodd" d="' + LOGO + '"/></svg><span class="dzf-wm"><b>データ攻め</b><i>DATA ZEME</i></span></a><span class="dzf-sp"></span><a class="dzf-sr" href="' + ROOT + 'players/" aria-label="選手を探す"><svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5l5 5"/></svg></a></div><div class="dzf-waku" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>';
  document.body.insertBefore(bar, document.body.firstChild);
  // 題字の頭の「BOATRACE」を外す（題字の印が後から付くページがあるので、読み込み後にもう一度）
  var cutBR = function(){ Array.prototype.forEach.call(document.querySelectorAll(".kataTitle,h1"), function(h){ var w = document.createTreeWalker(h, NodeFilter.SHOW_TEXT, null), n; while ((n = w.nextNode())) { if (/^\s*BOATRACE\s+/.test(n.nodeValue)) { n.nodeValue = n.nodeValue.replace(/^\s*BOATRACE\s+/, ""); break; } } }); };
  // 画面より広い表は、表だけ横に送れるようにする（ページ全体が横に動かないように）
  var wideTable = function(){ Array.prototype.forEach.call(document.querySelectorAll("table"), function(t){ var p = t.parentElement; if (!p || p.classList.contains("dzf-scroll") || t.closest(".dzf-scroll")) return; if (t.getBoundingClientRect().right > document.documentElement.clientWidth + 1) { var w = document.createElement("div"); w.className = "dzf-scroll"; w.style.cssText = "overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch;max-width:100%"; p.insertBefore(w, t); w.appendChild(t); } }); };
  // 全角の英数字（公式データのまま「ＢＯＡＴＲＡＣＥ」「５日目」など）を半角にそろえる。入力欄・書式つきの中身は触らない
  var Z = /[\uFF10-\uFF19\uFF21-\uFF3A\uFF41-\uFF5A]/;
  var han = function(root){ if (!root || !root.nodeType) return; var w = document.createTreeWalker(root.nodeType === 3 ? root.parentNode || document.body : root, NodeFilter.SHOW_TEXT, { acceptNode: function(n){ var p = n.parentNode; if (!p || /^(SCRIPT|STYLE|TEXTAREA|INPUT|CODE|PRE)$/.test(p.nodeName) || p.isContentEditable) return 2; return Z.test(n.nodeValue) ? 1 : 2; } }), n, a = []; while ((n = w.nextNode())) a.push(n); a.forEach(function(n){ n.nodeValue = n.nodeValue.replace(/[\uFF10-\uFF19\uFF21-\uFF3A\uFF41-\uFF5A]/g, function(c){ return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); }); }); };
  // 文字の大きさを5段（12・14・16・20・24px）にそろえる（2026-11-08 けん「はい次」・プロ化 第8弾）。
  // 26px以上（題字・大きな数字）はそのまま。共通の枠（dzf-）と data-kata-skip（二つ名など）は触らない。px 以外の指定（em・clamp など）も触らない
  // 検証（/kensho/）の記事は検証の型の決まりで組んでいるので、ここでは大きさを変えない
  var snapOff = /\/kensho\//.test(location.pathname);
  var snapFs = function(px){ return px >= 26 ? px : px < 13 ? 12 : px < 15 ? 14 : px < 18 ? 16 : px < 22 ? 20 : 24; };
  var snapDecl = function(sty){ var m = /^([\d.]+)px$/.exec((sty.getPropertyValue("font-size") || "").trim()); if (!m) return; var px = +m[1], v = snapFs(px); if (v !== px) sty.setProperty("font-size", v + "px", sty.getPropertyPriority("font-size")); };
  var snapRules = function(rules){ for (var i = 0; i < rules.length; i++) { var r = rules[i]; if (r.cssRules && !r.style) { snapRules(r.cssRules); continue; } if (r.style && r.selectorText && !/dzf-|data-kata-skip/.test(r.selectorText) && r.style.fontSize) snapDecl(r.style); } };
  var snapSheets = function(){ if (snapOff) return; Array.prototype.forEach.call(document.styleSheets, function(sh){ if (sh.ownerNode && sh.ownerNode.id === "dzfCss") return; if (sh.dzfSnap) return; try { snapRules(sh.cssRules); sh.dzfSnap = 1; } catch (e) {} }); };
  var snapInline = function(root){ if (snapOff) return; if (!root || root.nodeType !== 1) return; var a = Array.prototype.slice.call(root.querySelectorAll('[style*="font-size"]')); if (root.matches('[style*="font-size"]')) a.push(root); a.forEach(function(el){ if (el.closest("[data-kata-skip],.dzf-bar,.dzf-tb,.dzf-sh")) return; snapDecl(el.style); }); };
  // em・% などで決まっていて段から外れた文字は、見えている大きさを段にそろえて上書きする（読んでから書く。2回目で入れ子も追いつく）
  var snapEls = function(root){ if (snapOff) return; if (!root || root.nodeType !== 1) return; var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: function(n){ return n.nodeValue.trim() ? 1 : 2; } }), n, seen = [], todo = []; while ((n = w.nextNode())) { var el = n.parentElement; if (!el || el.dzfFs || seen.indexOf(el) >= 0 || /clamp|calc|vw|min\(|max\(/.test(el.style.fontSize) || /^(SCRIPT|STYLE)$/.test(el.nodeName) || el.closest("[data-kata-skip],.dzf-bar,.dzf-tb,.dzf-sh")) continue; seen.push(el); } seen.forEach(function(el){ var px = parseFloat(getComputedStyle(el).fontSize), v = snapFs(px); if (Math.abs(v - px) > 0.25) todo.push([el, v]); }); todo.forEach(function(t){ t[0].style.setProperty("font-size", t[1] + "px", "important"); t[0].dzfFs = 1; }); };
  snapSheets(); snapInline(document.body);
  var hanQ = [], hanT = 0;
  try { new MutationObserver(function(ms){ ms.forEach(function(m){ for (var k = 0; k < m.addedNodes.length; k++) hanQ.push(m.addedNodes[k]); if (m.type === "characterData") hanQ.push(m.target); }); /* 描く前に直す（120ms 待ってから直すと、いったん描いた文字が後から大きさを変えて画面がずれるため。2026-11-09） */ var q = hanQ; hanQ = []; q.forEach(function(x){ if (x.isConnected) { han(x); snapInline(x); snapEls(x); if (/^(STYLE|LINK)$/.test(x.nodeName)) snapSheets(); } }); }).observe(document.body, { childList: true, subtree: true, characterData: true }); } catch (e) {}
  han(document.body);
  var onLoad = function(){ snapSheets(); snapInline(document.body); snapEls(document.body); cutBR(); wideTable(); setTimeout(function(){ snapSheets(); snapInline(document.body); snapEls(document.body); cutBR(); wideTable(); }, 1500); setTimeout(function(){ snapSheets(); snapEls(document.body); }, 4000); };
  cutBR(); if (document.readyState === "complete") onLoad(); else window.addEventListener("load", onLoad);
  // 押す場所を指の大きさ（44px）まで広げる（見た目は変えない。透明の ::after で当たりだけ広げる。2026-11-09）
  // 隣の押せる部品と当たりが重ならない分だけ広げる。::after を自分で使っている部品・入力欄・文中のリンクは触らない
  var HIT = 44, hitT = 0, HSEL = 'a[href],button,summary,[role="button"],[role="tab"]';
  st.appendChild(document.createTextNode('.dzf-hit::after{content:"";position:absolute;left:calc(var(--dzf-hx,0px)*-1);right:calc(var(--dzf-hx,0px)*-1);top:calc(var(--dzf-hy,0px)*-1);bottom:calc(var(--dzf-hy,0px)*-1)}.dzf-hitR{position:relative}select,input[type=search],input[type=text],input:not([type]){min-height:44px}'));
  function hitPass(){
    hitT = 0;
    var els = Array.prototype.filter.call(document.querySelectorAll(HSEL), function(e){ return !e.closest(".dzf-bar,.dzf-tb,.dzf-sh,.dzf-bd") && !(e.tagName === "A" && e.closest("p,li") && getComputedStyle(e).display === "inline"); });
    var R = els.map(function(e){ return e.getBoundingClientRect(); });
    els.forEach(function(e, i){
      var r = R[i]; if (!r.width || !r.height) return;
      var needY = Math.max(0, (HIT - r.height) / 2), needX = Math.max(0, (HIT - r.width) / 2);
      if (!needY && !needX) { if (e.classList.contains("dzf-hit")) e.classList.remove("dzf-hit"); return; }
      if (!e.classList.contains("dzf-hit")) { var af = getComputedStyle(e, "::after").content; if (af && af !== "none" && af !== "normal") return; }
      // 隣と重ならない幅に抑える（間の半分まで）
      for (var j = 0; j < R.length; j++) { if (j === i) continue; var o = R[j]; if (!o.width) continue;
        if (o.left < r.right && o.right > r.left) { if (o.bottom <= r.top) needY = Math.min(needY, (r.top - o.bottom) / 2); else if (o.top >= r.bottom) needY = Math.min(needY, (o.top - r.bottom) / 2); }
        if (o.top < r.bottom && o.bottom > r.top) { if (o.right <= r.left) needX = Math.min(needX, (r.left - o.right) / 2); else if (o.left >= r.right) needX = Math.min(needX, (o.left - r.right) / 2); }
      }
      if (needY < 1 && needX < 1) return;
      if (getComputedStyle(e).position === "static") {
        var abs = Array.prototype.some.call(e.querySelectorAll("*"), function(c){ var p = getComputedStyle(c).position; return p === "absolute" || p === "fixed"; });
        if (abs) return; e.classList.add("dzf-hitR");
      }
      e.style.setProperty("--dzf-hy", Math.floor(needY) + "px"); e.style.setProperty("--dzf-hx", Math.floor(needX) + "px"); e.classList.add("dzf-hit");
    });
  }
  function hitSoon(){ if (!hitT) hitT = setTimeout(hitPass, 300); }
  try { new MutationObserver(function(ms){ for (var k = 0; k < ms.length; k++) if (ms[k].addedNodes.length) { hitSoon(); return; } }).observe(document.body, { childList: true, subtree: true }); } catch (e) {}
  document.addEventListener("click", hitSoon, true); window.addEventListener("resize", hitSoon); window.addEventListener("load", hitSoon); hitSoon();
  // 本文の余白を打ち消して、帯を画面の端から端まで出す（ページごとに body の余白が違うため）
  var bs = getComputedStyle(document.body), px = function(k){ return (parseFloat(bs["padding" + k]) || 0) + (parseFloat(bs["margin" + k]) || 0); };
  bar.style.margin = "-" + px("Top") + "px -" + px("Right") + "px 4px -" + px("Left") + "px";
  // ページに残っている「← データ攻め トップ」と、トップへ戻るだけの「データ攻め」のリンクは、上の帯と重なるので隠す
  Array.prototype.forEach.call(document.querySelectorAll("a"), function(a){
    if (a.closest(".dzf-bar,.dzf-tb,.dzf-sh")) return;
    var tx = (a.textContent || "").trim();
    if (/^\u2190\s*データ攻め/.test(tx) || (tx === "データ攻め" && a.href.split(/[?#]/)[0] === ROOT)) a.style.display = "none";
  });
  var L = [["motor/","モーター"],["players/","選手図鑑"],["stadium/","24場"],["kensho/","検証"],["updates/","更新履歴"],["torisetsu/","トリセツ"],0,["payouts/","万舟のツボ"],["motor-maintenance/","モーター整備"],["players/card.html","選手カード"],["note/","観戦ノート"],["ichimark/","1マークの見立て"],["glossary/","用語辞典"],["fan/","場の文化"],["announcers/","実況アナ図鑑"],["uranai/","選手占い"]];
  var sh = document.createElement("div"); sh.className = "dzf-sh"; sh.id = "dzfSheet"; sh.hidden = true;
  sh.innerHTML = '<div class="dzf-shi">' + L.map(function(x){ return x ? '<a href="' + ROOT + x[0] + '">' + x[1] + '</a>' : '<div class="sh2">ほかのページ</div>'; }).join("") + '<a href="https://note.com/abeken2000" target="_blank" rel="noopener">有料note（外部）</a><a class="full" href="' + ROOT + 'hikae/">フォローの控え（機種変更・アイコンの置き直し）</a></div>';
  var tb = document.createElement("nav"); tb.className = "dzf-tb"; tb.setAttribute("aria-label", "ページ");
  function t(k, h, n){ return '<a href="' + ROOT + h + '"' + (cur === k ? ' class="on" aria-current="page"' : '') + '>' + I[k] + n + '</a>'; }
  tb.innerHTML = '<div class="dzf-tbi">' + t("top", "", "トップ") + t("racers", "racers/", "出走表") + t("highlights", "highlights/", "見どころ") + t("results", "results/", "結果") + '<button type="button" id="dzfMore" aria-expanded="false" aria-controls="dzfSheet"' + (cur === "more" ? ' class="on"' : '') + '>' + I.more + 'その他</button></div>';
  document.body.appendChild(sh); document.body.appendChild(tb);
  // 見どころ・結果の小さな丸と、開いたことの記録（assets/shinchaku.js・2026-11-10）
  var scn = document.createElement("script"); scn.src = ROOT + "assets/shinchaku.js?v=2"; scn.defer = true; document.body.appendChild(scn);
  var mb = document.getElementById("dzfMore");
  var bd = document.createElement("div"); bd.className = "dzf-bd"; bd.hidden = true; document.body.appendChild(bd);
  var keepY = 0, bs = document.body.style;
  function lock(){ keepY = window.scrollY; bs.position = "fixed"; bs.top = -keepY + "px"; bs.left = "0"; bs.right = "0"; bs.width = "100%"; }
  function unlock(){ bs.position = ""; bs.top = ""; bs.left = ""; bs.right = ""; bs.width = ""; window.scrollTo(0, keepY); }
  // 「その他」を開いたら履歴に1つ積む。戻る操作（戻るボタン・端からのスワイプ）では前のページへ戻らず、メニューだけ閉じる（2026-11-09）
  function shState(){ try { return !!(history.state && history.state.dzfSh); } catch (e) { return false; } }
  function openSh(){ try { if (!shState()) { var st = {}; if (history.state && typeof history.state === "object") for (var k in history.state) st[k] = history.state[k]; st.dzfSh = 1; history.pushState(st, ""); } } catch (e) {} sh.hidden = false; bd.hidden = false; mb.setAttribute("aria-expanded", "true"); mb.classList.add("dzf-op"); lock(); sh.classList.remove("in"); void sh.offsetWidth; sh.classList.add("in"); }
  function closeSh(fromPop){ if (sh.hidden) return; sh.hidden = true; bd.hidden = true; sh.classList.remove("in"); mb.setAttribute("aria-expanded", "false"); mb.classList.remove("dzf-op"); unlock(); if (fromPop !== true && shState()) { try { history.back(); } catch (e) {} } }
  mb.addEventListener("click", function(){ if (sh.hidden) openSh(); else closeSh(); });
  bd.addEventListener("click", closeSh);
  window.addEventListener("popstate", function(){ if (!sh.hidden) closeSh(true); });
  // メニューの中のリンクは、積んだ1つを置き換えて進む（戻ったときに、閉じたメニューの分だけ余計に戻らずに済むように）
  sh.addEventListener("click", function(e){ var a = e.target.closest && e.target.closest("a[href]"); if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || a.target === "_blank" || !shState()) return; e.preventDefault(); closeSh(true); location.replace(a.href); });
  document.addEventListener("keydown", function(e){ if (e.key === "Escape") closeSh(); });
  window.addEventListener("pageshow", function(e){ if (e.persisted) closeSh(true); });
  }
})();
