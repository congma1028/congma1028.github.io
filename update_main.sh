python3 generate_jemdocs.py
python jemdoc.py -c my.conf index.jemdoc
python jemdoc.py -c my.conf paper.jemdoc
python jemdoc.py -c my.conf paper_topic.jemdoc
python jemdoc.py -c my.conf group.jemdoc
python jemdoc.py -c my.conf teaching.jemdoc
python jemdoc.py -c my.conf tutorial.jemdoc
python jemdoc.py -c my.conf talk.jemdoc
python3 generate_jemdocs.py --postprocess-html
# python2 jemdoc.py homework.jemdoc
# python2 jemdoc.py lectures.jemdoc
# python2 jemdoc.py reference.jemdoc
# python2 jemdoc.py project.jemdoc

perl -pi -e 's/target=&ldquo;_blank&rdquo;/target="_blank"/g; s/rel=&ldquo;noopener noreferrer&rdquo;/rel="noopener noreferrer"/g' index.html paper.html paper_topic.html group.html teaching.html tutorial.html talk.html

# rsync -rvz www/*.html www/jemdoc.css yc5@nobel.princeton.edu:public_html/ele520_math_data/
  
