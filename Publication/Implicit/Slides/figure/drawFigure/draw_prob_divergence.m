m = 50;

hFig = figure;

set(hFig, 'Position', [300 300 500 200])

P = exp(- [- floor(m/2) : floor(m/2) ].^2 / (m/4)^2 ) ;
P = P / sum(P);
stem(P, 'filled', 'linewidth', 0.3, 'MarkerSize', 8)
hold on;

P2 = circshift(P, [0,15])
stem(P2, 'filled', 'linewidth', 0.3, 'MarkerSize', 8)
axis off

hold on

for i = 1: length(P)
   hold on
   a = min([P(i), P2(i)]);
   b = max([P(i), P2(i)]);
   plot( [i, i], [a+0.001,b-0.001], 'Markersize', 10, 'Color', 'k', 'linewidth', 2 );
   hold on
end


%ylim([0,0.3])
