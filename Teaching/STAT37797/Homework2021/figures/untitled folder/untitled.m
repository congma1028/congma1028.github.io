x=-10:0.001:10;
y=zeros(1,length(x));
for i=1:length(x)
    y(i)=exp(-(x(i))^2);
end
close all; plot(x,y,'linewidth',1.5); hold on;
xlabel('f(t)','Interpreter','Tex'); hold on;
axis([-7,7,-0,1.1]);set(gca,'XtickLabel',[],'YtickLabel',[]);

x=-10:0.001:10;
y=zeros(1,length(x));
for i=1:length(x)
    y(i)=exp(-(x(i))^2/11);
end
figure(2)
plot(x,y,'linewidth',1.5); hold on;
xlabel('F(\omega)','Interpreter','Tex'); hold on;
axis([-7,7,-0,1.1]); set(gca,'XtickLabel',[],'YtickLabel',[]);

x=-10:0.001:20;
y=zeros(1,length(x));
for i=1:length(x)
    y(i)=exp(-(x(i))^2);
end
figure(3)
plot(x,y,'linewidth',1.5); hold on;
axis([-5,15,-0,1.1]);set(gca,'XtickLabel',[],'YtickLabel',[]);

x=-10:0.001:20;
y=zeros(1,length(x));
for i=1:length(x)
    y(i)=exp(-(x(i))^2)+exp(-(x(i)-10)^2);
end
figure(4)
plot(x,y,'linewidth',1.5); hold on;
axis([-5,15,-0,1.1]);set(gca,'XtickLabel',[],'YtickLabel',[]);