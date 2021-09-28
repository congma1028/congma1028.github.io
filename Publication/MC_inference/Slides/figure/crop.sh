#!/bin/sh

for filename in `ls *.png`
do
    convert $filename -trim $filename 
done 

