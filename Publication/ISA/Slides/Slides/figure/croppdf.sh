#!/bin/sh

for filename in `ls *.pdf`
do
    pdfcrop --margin 5 $filename $filename 
done 

