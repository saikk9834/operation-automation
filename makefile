install:
	pip install --upgrade pip &&\
	pip install -r requirements.txt

format:
	black *.py

lint:
	pylint --disable=R,C,W0718,E1101,W0612 *.py

test:
	#test

deploy:
	#deploy

all: install format lint test deploy 