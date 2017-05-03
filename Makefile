.PHONY: all clean install release test tests update
SHELL=/bin/bash
RELEASE_TYPE=patch

all: test

clean:
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	find . -name '__pycache__' -print0 | xargs -0 rm -rf
	rm -rf .coverage .tox *.egg-info .eggs

install:
	pip install .

release:
	pipenv run bumpversion $(RELEASE_TYPE)
	@tput setaf 2
	@echo Built release for `git describe --tag`. Make sure to run:
	@echo "  $$ git push origin <branch> tag `git describe --tag`"
	@tput sgr0

test:
	tox

tests: test

update:
	pipenv update --dev
