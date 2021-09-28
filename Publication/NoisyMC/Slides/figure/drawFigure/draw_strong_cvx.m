Xlist = - 4:0.01:4;
Ylist = - 4:0.01:4;

[X,Y] = meshgrid(Xlist, Ylist);
Z = 0.2*X.^2 + Y.^2;
Z2 = Z + Y.^2+ sin(X+Y);

s = surf(X,Y, Z,'FaceAlpha',0.6)
s.EdgeColor = 'none';
rotate3d on
grid on
zlim([0,2])
axis off

colormap summer

color_green = [0.2157    0.7541    0.7216];

%hold on


s = surf(X,Y, Z2,'FaceAlpha',0.6)
s.EdgeColor = 'none';
rotate3d on
grid on
zlim([0,2])
axis off

colormap summer

color_green = [0.2157    0.7541    0.7216];

hold on





