rho = [0.5,0.5];

p = [0.15, 0.85];
q = 2*rho - p;

%p1_list = [max([0, 2*rho(1)-1]):  0.001: min([1, 2*rho(1)])];
%p2_list = [max([0, 2*rho(2)-1]):  0.001: min([1, 2*rho(2)])];

p1_list = [0.01:  0.001: 0.99];
p2_list = 1 - p1_list;

q1_list = [0.01:  0.001: 0.99];
q2_list = 1 - q1_list;

L = zeros( length(p1_list), length(p2_list) );


for i = 1: length(p1_list)
    for j = 1: length(q1_list)
        p1 = p1_list(i);
        p2 = p2_list(i);
        q1 = q1_list(j);
        q2 = q2_list(j);        
  
        L(i,j) = 2* (p(1)*p(2) + q(1)*q(2)) * log( 0.5* p1*p2 + 0.5* q1*q2 ) + ...
                    (p(1)*p(1) + q(1)*q(1)) * log( 0.5* p1*p1 + 0.5* q1*q1 ) + ...
                    (p(2)*p(2) + q(2)*q(2)) * log( 0.5* p2*p2 + 0.5* q2*q2 );
        L(i,j) = 0.5* L(i,j);
    end
end

[X,Y] = meshgrid(p1_list,q1_list);

s = surf(X,Y, -L,'FaceAlpha',0.6)
s.EdgeColor = 'none';
rotate3d on
grid off
axis off

zlim([1,1.5])

colormap(winter)
%colormap(flipud(winter))
