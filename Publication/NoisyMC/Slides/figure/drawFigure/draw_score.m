n = 80;
score = abs(randn(n,1));

score = sort(score,'descend');
m = 50;
stem(1: m, score(1:m),'filled','linewidth',2)

%axis off


