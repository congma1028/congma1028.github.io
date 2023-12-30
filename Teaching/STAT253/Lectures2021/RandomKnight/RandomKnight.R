KnightMoves = function(x0,y0){
  
rect(x0,y0,x0+1,y0+1,col=4)

if(x0-2>=0 & x0-2<=7 & y0-1>=0 & y0-1<=7){
  rect(x0-2,y0-1,x0-1,y0,  col=rgb(1,0,0,0.5))
  lines(x0+c(0.2,-1.5),y0+c(1/3,1/3),lwd=2)
  arrows(x0-2+0.5, y0+1/3,x0-2+0.5, y0-1+0.5,
         lwd=2, angle=15, length=0.05)
}

if(x0-2>=0 & x0-2<=7 & y0+1>=0 & y0+1<=7){
  rect(x0-2,y0+1,x0-1,y0+2,col=rgb(1,0,0,0.5))
  lines(x0+c(0.2,-1.5),y0+c(2/3,2/3),lwd=2)
  arrows(x0-2+0.5, y0+2/3,x0-2+0.5, y0+1+0.5,
         lwd=2, angle=15, length=0.05)
}

if(x0+2>=0 & x0+2<=7 & y0-1>=0 & y0-1<=7){
  rect(x0+2,y0-1,x0+3,y0  ,col=rgb(1,0,0,0.5))
  lines(x0+c(0.8, 2.5),y0+c(1/3,1/3),lwd=2)
  arrows(x0+2+0.5, y0+1/3,x0+2+0.5, y0-1+0.5,
         lwd=2, angle=15, length=0.05)
}

if(x0+2>=0 & x0+2<=7 & y0+1>=0 & y0+1<=7){
  rect(x0+2,y0+1,x0+3,y0+2,col=rgb(1,0,0,0.5))
  lines(x0+c(0.8, 2.5),y0+c(2/3,2/3),lwd=2)
  arrows(x0+2+0.5, y0+2/3,x0+2+0.5, y0+1+0.5,
         lwd=2, angle=15, length=0.05)
}

if(x0-1>=0 & x0-1<=7 & y0-2>=0 & y0-2<=7){
  rect(x0-1,y0-2,x0  ,y0-1,col=rgb(1,0,0,0.5))
  lines(x0+c(1/3,1/3),y0+c(0.2,-1.5),lwd=2)
  arrows(x0+1/3, y0-2+0.5, x0-1+0.5, y0-2+0.5,
         lwd=2, angle=15, length=0.05)
}

if(x0+1>=0 & x0+1<=7 & y0-2>=0 & y0-2<=7){
  rect(x0+1,y0-2,x0+2,y0-1,col=rgb(1,0,0,0.5))
  lines(x0+c(2/3,2/3),y0+c(0.2,-1.5),lwd=2)
  arrows(x0+2/3, y0-2+0.5, x0+1+0.5, y0-2+0.5,
         lwd=2, angle=15, length=0.05)
}

if(x0-1>=0 & x0-1<=7 & y0+2>=0 & y0+2<=7){
  rect(x0-1,y0+2,x0  ,y0+3,col=rgb(1,0,0,0.5))
  lines(x0+c(1/3,1/3),y0+c(0.8, 2.5),lwd=2)
  arrows(x0+1/3, y0+2+0.5, x0-1+0.5, y0+2+0.5,
         lwd=2, angle=15, length=0.05)
}

if(x0+1>=0 & x0+1<=7 & y0+2>=0 & y0+2<=7){
  rect(x0+1,y0+2,x0+2,y0+3,col=rgb(1,0,0,0.5))
  lines(x0+c(2/3,2/3),y0+c(0.8, 2.5),lwd=2)
  arrows(x0+2/3, y0+2+0.5, x0+1+0.5, y0+2+0.5,
         lwd=2, angle=15, length=0.05)
}
}

Chessboard = function(){
  plot(c(0,8), c(0,8), type="n", ann=F, axes = F)
  for(i in 0:8){
    lines(c(0,8),c(i,i))
    lines(c(i,i),c(0,8))
  }
}

pdf("KnightMoves_Border.pdf",width=2,height=2)
par(mai=c(0,0,0,0))
Chessboard()
KnightMoves(0,0)
KnightMoves(7,5)
dev.off()

pdf("KnightMoves_Border2.pdf",width=2,height=2)
par(mai=c(0,0,0,0))
Chessboard()
KnightMoves(4,0)
KnightMoves(1,7)
dev.off()

pdf("KnightMoves_Border3.pdf",width=2,height=2)
par(mai=c(0,0,0,0))
Chessboard()
KnightMoves(1,1)
KnightMoves(5,6)
dev.off()


pdf("KnightMove44.pdf",width=2,height=2)
par(mai=c(0,0,0,0))
Chessboard()
KnightMoves(4,4)
dev.off()

pdf("KnightMoves00.pdf",width=2,height=2)
par(mai=c(0,0,0,0))
Chessboard()
KnightMoves(0,0)
dev.off()

pdf("KnightMoves21.pdf",width=2,height=2)
par(mai=c(0,0,0,0))
Chessboard()
KnightMoves(2,1)
dev.off()