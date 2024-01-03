%.pdf:  %.tex
	pdflatex $(basename $<)
	pdflatex $(basename $<)
	rm -f $(basename $<).aux
	rm -f $(basename $<).log
	rm -f $(basename $<).toc
	rm -f $(basename $<).out
	rm -f $(basename $<).nav
	rm -f $(basename $<).snm
	mv $(basename $<).pdf ../$(basename $<).pdf

