.PHONY: clean install wheel test tests update
SHELL=/bin/bash


help: ## Print this message
	@awk 'BEGIN { FS = ":.*##"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*##/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)


clean: ## Remove build artifacts
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	find . -name '__pycache__' -print0 | xargs -0 rm -rf
	rm -rf .coverage .tox *.egg-info .eggs build dist

install: ## Install project and dev depenedencies
	pipenv install --dev

wheel: ## Build Python wheel
	pipenv run python setup.py bdist_wheel

test: ## Run tests
	tox

tests: test

update: ## Update all Python dependencies
	pipenv clean
	pipenv update --dev
