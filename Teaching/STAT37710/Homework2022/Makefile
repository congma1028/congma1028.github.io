default: hw1.pdf hw1-solution.pdf hw2.pdf hw2-solution.pdf hw3.pdf hw3-solution.pdf

%.pdf: %.tex
	pdflatex $(basename $<)
	pdflatex $(basename $<)
	rm -f $(basename $<).aux
	rm -f $(basename $<).log

%-solution.pdf: %.tex
	sed -e 's/\\createHomework/\\createHomeworkSolutions/g' < $< > $(basename $<)-solution.tex
	pdflatex $(basename $<)-solution
	pdflatex $(basename $<)-solution
	rm -f $(basename $<)-solution.tex
	rm -f $(basename $<)-solution.aux
	rm -f $(basename $<)-solution.log
