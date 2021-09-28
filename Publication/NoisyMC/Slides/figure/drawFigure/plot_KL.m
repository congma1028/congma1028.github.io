p_list = [0.001:0.001:0.9];
p0 = 0.35;

KL = p_list .* log(p_list / p0) + (1-p_list) .* log( (1-p_list) / (1-p0) );

plot(p_list, -KL, 'linewidth',4, 'color', [.5 .4 .7])

axis off
