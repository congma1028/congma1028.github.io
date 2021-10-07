clear
clc
close all

n = 1000;
theta = linspace(0, pi / 2, n);

figure
hold on
plot(theta, sin(theta))
plot(theta, 2 * sin(theta / 2))
plot(theta, sqrt(2) * sin(theta))
axis([0 pi / 2 0 sqrt(2)])
legend({'$$\sin\theta$$', '$$2\sin({\theta}/{2})$$', '$$\sqrt{2}\sin\theta$$'},'interpreter','latex', 'FontSize',15, 'Location', 'southeast')