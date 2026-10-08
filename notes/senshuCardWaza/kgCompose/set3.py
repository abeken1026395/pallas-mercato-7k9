from comp import *
D={}
roof=T('宇',268); rb_=bb(roof)
X0,X1=rb_[0]+20,rb_[2]-20
D['實']=U(roof,fit(G('貫'),(X0,300,X1,995)))
nya=big(R('弥',gapx('弥',200,450)))
D['寳']=U(roof,fitb(G('王'),(X0,300,470,590)),fitb(nya,(530,300,X1,590)),fit(G('貝'),(X0,625,X1,995)))
# 榮
D['榮']=U(fit(B('栄',150),(0,330,1000,995)),fitb(G('火'),(20,0,480,300)),fitb(G('火'),(520,0,980,300)))
# 凜
x=gapx('凛',200,420); rt=R('凛',x)
nogi=L('利',gapx('利',300,600))
D['凜']=U(L('凛',x),clip(rt,(-100,-100,1100,530)),fit(nogi,bb(clip(rt,(-100,545,1100,1100)))))
# 將
x=gapx('将',200,420); D['將']=U(fit(mirror(G('片')),bb(L('将',x))),R('将',x))
# 淺・澁
x=gapx('沢',200,420); rb=bb(R('沢',x))
ge=big(R('戦',gapx('戦',300,520)))
D['淺']=U(L('沢',x),fit(ge,(rb[0]+40,rb[1],rb[2]-20,rb[1]+(rb[3]-rb[1])*0.45-10)),fit(ge,(rb[0],rb[1]+(rb[3]-rb[1])*0.45+10,rb[2],rb[3])))
st=big(T('歩',gapy('歩',300,560))); m=rb[1]+(rb[3]-rb[1])*0.48; c=(rb[0]+rb[2])/2
D['澁']=U(L('沢',x),fit(st,(rb[0],rb[1],rb[2],m-15)),fit(mirror(st),(rb[0],m+15,c-15,rb[3])),fit(st,(c+15,m+15,rb[2],rb[3])))
# 齊・齋
hi_=big(R('化',gapx('化',200,450)))
T_=30
def sei(src,y):
    top=T(src,y); b=bb(top)
    return U(B(src,y),fit(top,(210,b[1],790,b[3])),fitb(G('刀'),(0,170,190,y-10)),fitb(hi_,(810,170,1000,y-10)))
D['齊']=sei('斉',470)
D['齋']=sei('斎',440)
# 來
g=G('木'); top=clip(g,(-100,-100,1100,380)); legs=clip(g,(-100,380,1100,1100)); lb=bb(legs)
nt=600
D['來']=U(top,fit(legs,(lb[0],nt,lb[2],lb[3]),lb),box(380,370,620,nt+40),fitb(G('人'),(40,420,350,nt+80)),fitb(G('人'),(650,420,960,nt+80)))
