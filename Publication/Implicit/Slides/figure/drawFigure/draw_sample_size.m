delta_list = 0.15:0.001:0.7;
n = 1000; 
sample_size = zeros( size(delta_list) );
sample_size_jang = n^2* sqrt(log(n)/n)* ones( size(delta_list) );


for i = 1: length(delta_list)
   delta = delta_list(i);
   sample_size(i) = n* log(n) / (delta^2);
   
   sample_size_jang(i) = max([sample_size(i), sample_size_jang(i)]);
end

plot(delta_list, sample_size, 'linewidth',3);
hold on



plot(delta_list, sample_size_jang, 'linewidth',3);



h_legend = legend(' ', ...
                  ' ')
set(h_legend,'FontSize',20);  
%set(h_legend, 'Position', [0.4,0.15,0.3,0.3])
legend boxoff

axis off