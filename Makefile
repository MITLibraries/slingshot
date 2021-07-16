.PHONY: clean install dist test tests update publish promote
SHELL=/bin/bash
ECR_REGISTRY=672626379771.dkr.ecr.us-east-1.amazonaws.com
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)


help: ## Print this message
	@awk 'BEGIN { FS = ":.*##"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*##/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)


clean: ## Remove build artifacts
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	find . -name '__pycache__' -print0 | xargs -0 rm -rf
	rm -rf .coverage .tox *.egg-info .eggs build dist

install: ## Install project and dev depenedencies
	pipenv install --dev

dist: ## Build docker container
	docker build -t $(ECR_REGISTRY)/slingshot-stage:latest \
		-t $(ECR_REGISTRY)/slingshot-stage:`git describe --always` \
		-t slingshot .

test: ## Run tests
	tox

tests: test

update: ## Update all Python dependencies
	pipenv clean
	pipenv update --dev

publish: ## Push and tag the latest image (use `make dist && make publish`)
	aws ecr get-login-password | docker login --password-stdin --username AWS $(ECR_REGISTRY)
	docker push $(ECR_REGISTRY)/slingshot-stage:latest
	docker push $(ECR_REGISTRY)/slingshot-stage:`git describe --always`

promote: ## Promote the current staging build to production
	aws ecr get-login-password | docker login --password-stdin --username AWS $(ECR_REGISTRY)
	docker pull $(ECR_REGISTRY)/slingshot-stage:latest
	docker tag $(ECR_REGISTRY)/slingshot-stage:latest $(ECR_REGISTRY)/slingshot-prod:latest
	docker tag $(ECR_REGISTRY)/slingshot-stage:latest $(ECR_REGISTRY)/slingshot-prod:$(DATETIME)
	docker push $(ECR_REGISTRY)/slingshot-prod:latest
	docker push $(ECR_REGISTRY)/slingshot-prod:$(DATETIME)
