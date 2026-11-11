/* 月ごとのまとめの共有画像（再訪設計書 段階3・2026-11-11）。
   選手カードの保存用画像（players/card.html の drawStory）と同じ描き方：1080×1350、漆黒の配色、見出しと数字はキルゴU（作者 名残雪 様）を
   図形にした players/card/kgOutline.json で描く。描画の部品（sc で始まる関数）は card.html から写したもの。
   画像は端末の中だけで作る。サーバーには送らない */
(function(){
"use strict";
let K=null;const SC={P2:{}};
const SC_UI="'Hiragino Sans','Hiragino Kaku Gothic ProN','Noto Sans JP','Noto Sans CJK JP','Yu Gothic',Meiryo,sans-serif";
function scPal(kuro){
  return kuro?{WATER:"#141212",SUB:"#9c948a",INK:"#ece6da",ACC:"#d9b44a",ONACC:"#141212",YU:"#dcb84f",MARK:"#d8342c",HWG:"rgba(217,180,74,.10)",NAME:"#e8322a",LN:"rgba(236,230,218,.16)",OFF:"rgba(236,230,218,.08)",TC:{5:"#fffaf0",4:"#cfc7ba",3:"#a39b90",2:"#7a736b",1:"#4d4844"}}
             :{WATER:"#0b4a50",SUB:"#a6cdd0",INK:"#f3fafa",ACC:"#ffd23f",ONACC:"#121212",YU:"#ffd23f",HWG:"rgba(255,210,63,.086)",NAME:"#ff2a2a",LN:"rgba(255,255,255,.18)",OFF:"rgba(255,255,255,.1)",TC:{5:"#ffffff",4:"#c4e8ea",3:"#8fc4c8",2:"#5ea6ac",1:"#3d777c"}};
}

function scTxt(c,s,x,y,px,fill,an="la",bold=true){
  c.font=`${bold?700:400} ${px}px ${SC_UI}`;c.fillStyle=fill;c.textBaseline="top";
  c.textAlign=an[0]==="r"?"right":an[0]==="m"?"center":"left";
  c.fillText(s,x,y+px*0.06);c.textAlign="left";
}
function scKgW(s,px,ls=0){let x=0,n=0;for(const ch of s){const g=K.g[ch];x+=(g?g[0]:(ch===" "?300:1000))*px/1000;n++;}return x+ls*Math.max(0,n-1);}
/* anchor: la=左上(アセンダ) / ra=右上 / mm=中央 / ms=中央・ベースライン */
function scKg(c,s,x,y,px,fill,o={}){
  const ls=o.ls||0,w=scKgW(s,px,ls),an=o.anchor||"la";
  let x0=an[0]==="r"?x-w:an[0]==="m"?x-w/2:x;
  let y0=an[1]==="m"?y-0.6*px:an[1]==="s"?y-0.859*px:y;
  const sc=px/1000;
  const draw=(mode)=>{let xx=x0;for(const ch of s){const g=scGlyph(ch);
      c.save();c.translate(xx,y0);c.scale(sc,sc);
      if(g){if(mode==="s")c.stroke(g[1]);else c.fill(g[1]);}
      else if(ch!==" "){c.font="900 1000px "+SC_UI;c.textBaseline="alphabetic";c.textAlign="left";if(mode==="s")c.strokeText(ch,0,859);else c.fillText(ch,0,859);}
      c.restore();xx+=(g?g[0]:(ch===" "?300:1000))*sc+ls;}};
  if(o.stroke){c.save();c.strokeStyle=o.sf||"#fff";c.lineJoin="round";c.lineWidth=o.stroke*2/sc;draw("s");c.restore();}
  c.fillStyle=fill;draw("f");
  return w;
}
function scFit(s,max,start,min=24){let z=start;while(scKgW(s,z)>max&&z>min)z-=2;return z;}
function scMark(c,y,col="#ffd23f"){c.fillStyle=col;c.beginPath();c.moveTo(40,y+12);c.lineTo(52,y+12);c.lineTo(46,y+50);c.lineTo(34,y+50);c.fill();}
function scLine(c,x1,y1,x2,y2,col,lw=2){c.strokeStyle=col;c.lineWidth=lw;c.beginPath();c.moveTo(x1,y1);c.lineTo(x2,y2);c.stroke();}
function scTw(c,s,px){c.font=`700 ${px}px ${SC_UI}`;return c.measureText(s).width;}
function scGlyph(ch){if(!SC.P2[ch]){const g=K.g[ch];SC.P2[ch]=(g&&g[1])?[g[0],new Path2D(g[1])]:null;}return SC.P2[ch];}
function yen(n){return Math.round(n).toLocaleString();}
/* R：自分の記録で数えた月の数字（note/index.html の repStats）。返すのは canvas */
function draw(R){
  const pal=scPal(true),INK=pal.INK,SUB=pal.SUB,LN=pal.LN;
  const cv=document.createElement("canvas");cv.width=1080;cv.height=1350;const c=cv.getContext("2d");
  c.fillStyle=pal.WATER;c.fillRect(0,0,1080,1350);
  scTxt(c,"自分の記録",40,48,26,SUB);scTxt(c,R.range,1040,48,26,SUB,"ra");
  const hd=R.m+"月のまとめ";scKg(c,hd,40,96,scFit(hd,1000,120),INK);
  c.fillStyle=pal.MARK;c.beginPath();c.moveTo(46,252);c.lineTo(1040,252);c.lineTo(1034,240);c.lineTo(52,240);c.fill();
  let y=300;
  scMark(c,y,pal.MARK);scTxt(c,"予想の傾向",62,y+14,26,SUB);
  if(R.title){scKg(c,R.title,62,y+56,132,pal.ACC);}
  else if(R.rank!=null){scKg(c,"平均"+R.rank.toFixed(1)+"番人気",62,y+80,96,INK);}
  else scTxt(c,"人気の分かるレースがまだありません",62,y+100,36,SUB);
  /* 同じ数字を2回出さない：称号があるときだけ平均人気を説明の行に書く */
  scTxt(c,R.rank==null?(R.nOrd?"人気は翌日の昼過ぎに入ります":"着順のある買い目（単勝・2連単・3連単）が無い月です"):R.title?"1着に選んだ艇の人気 平均"+R.rank.toFixed(1)+"番人気":"1着に選んだ艇の人気の平均",62,y+204,30,INK);
  scTxt(c,R.title?"人気の分かる"+R.nRank+"レース":(R.nOrd?"人気の分かる"+R.nRank+"レース・称号は20レースから":""),62,y+246,24,SUB);
  y+=290;scLine(c,40,y,1040,y,LN);
  const cols=[["記録したレース",String(R.n),"レース",""],["的中",String(R.hit),"レース",R.judged+"レース中"],["回収率",R.roi!=null?String(R.roi):"—",R.roi!=null?"%":"",R.roi!=null?"金額の分かる"+R.nA+"レース":"金額の分かるレースなし"]];
  cols.forEach((k,i)=>{const x=40+i*340;if(i)scLine(c,x-10,y+20,x-10,y+210,LN);
    scTxt(c,k[0],x+8,y+26,24,SUB);const w=scKg(c,k[1],x+8,y+70,104,INK);if(k[2])scTxt(c,k[2],x+16+w,y+130,28,SUB);if(k[3])scFitTxt0(c,k[3],x+8,y+184,22,SUB,320);});
  y+=220;scLine(c,40,y,1040,y,LN);
  scTxt(c,R.roiAll!=null?"通算の回収率 "+R.roiAll+"%（金額の分かる"+R.nAAll+"レース）":"通算の回収率 —（金額の分かるレースなし）",40,y+18,26,INK);
  y+=64;scLine(c,40,y,1040,y,LN);
  y+=20;scMark(c,y,pal.MARK);scTxt(c,"場ごと（金額の分かるレースが5以上の場だけ）",62,y+14,26,SUB);y+=70;
  if(!R.venues.length){scTxt(c,"5レース以上の場はありません",40,y+10,30,SUB);}
  R.venues.forEach(v=>{
    scTxt(c,v.label,40,y,24,SUB);scKg(c,v.name,40,y+34,64,INK);scKg(c,v.roi+"%",1040,y+34,64,INK,{anchor:"ra"});scTxt(c,v.n+"レース",1040,y+100,22,SUB,"ra");
    y+=130;scLine(c,40,y-6,1040,y-6,"rgba(255,255,255,.094)");});
  scTxt(c,"本人がこの端末に残した記録から作成。"+R.m+"月の数字と通算を並べています。",40,1262,22,SUB);
  scTxt(c,"データ攻め",1040,1296,26,INK,"ra");
  return cv;
}
function scFitTxt0(c,s,x,y,px,fill,max){let z=px;while(z>14&&scTw(c,s,z)>max)z-=1;scTxt(c,s,x,y,z,fill);}
let KP=null;
function loadK(url){ if(!KP) KP=fetch(url).then(r=>{if(!r.ok)throw 0;return r.json();}).then(k=>{K=k;return k;}).catch(e=>{KP=null;throw e;}); return KP; }
/* 画像の Blob を返す。書体が読めないときは失敗にする（ゴシック体だけの画像は出さない） */
window.dzTsuki={make:function(R,kgUrl){return loadK(kgUrl).then(()=>new Promise((ok,ng)=>{const cv=draw(R);cv.toBlob(b=>b?ok(b):ng(0),"image/png");}));}};
})();
