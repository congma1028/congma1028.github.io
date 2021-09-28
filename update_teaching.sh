cp -R ~/Dropbox/UChicago/Courses/STAT37797/Lectures2021 Teaching/STAT37797/
cd Teaching/STAT37797
python2 jemdoc.py index.jemdoc
python2 jemdoc.py syllabus.jemdoc
python2 jemdoc.py course_info.jemdoc
python2 jemdoc.py homework.jemdoc
python2 jemdoc.py lectures.jemdoc
python2 jemdoc.py reference.jemdoc
python2 jemdoc.py project.jemdoc

# rsync -rvz www/*.html www/jemdoc.css yc5@nobel.princeton.edu:public_html/ele520_math_data/
  
