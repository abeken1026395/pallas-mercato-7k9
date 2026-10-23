import sys,glob
from PIL import Image, ImageDraw
fs=sys.argv[2:]; out=sys.argv[1]
W=300; ims=[Image.open(f).convert("RGB") for f in fs]; ims=[i.resize((W,int(i.height*W/i.width))) for i in ims]
H=max(i.height for i in ims)+16
S=Image.new("RGB",(len(ims)*(W+6),H),"white"); d=ImageDraw.Draw(S)
for k,(f,i) in enumerate(zip(fs,ims)): S.paste(i,(k*(W+6),16)); d.text((k*(W+6),2),f.split('/')[-1],fill="black")
S.save(out)
