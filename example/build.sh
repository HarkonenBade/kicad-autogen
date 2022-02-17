#! /bin/bash

if [ ! -d venv ]; then
	python3 -m venv venv;
	. ./venv/bin/activate;
	pip install -r requirements.txt;
fi

. ./venv/bin/activate
for f in ./*.yaml; do
	build_lib.py $f;
done
