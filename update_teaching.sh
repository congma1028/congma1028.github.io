cp -R ~/Dropbox/UChicago/Courses/STAT37797/Lectures2021 Teaching/STAT37797/
cp -R ~/Dropbox/UChicago/Courses/STAT37797/Homework2021 Teaching/STAT37797/
cd Teaching/STAT37797
python3 ../../jemdoc.py index.jemdoc
python3 ../../jemdoc.py syllabus.jemdoc
python3 ../../jemdoc.py course_info.jemdoc
python3 ../../jemdoc.py homework.jemdoc
python3 ../../jemdoc.py lectures.jemdoc
python3 ../../jemdoc.py reference.jemdoc
python3 ../../jemdoc.py project.jemdoc

# rsync -rvz www/*.html www/jemdoc.css yc5@nobel.princeton.edu:public_html/ele520_math_data/
  
