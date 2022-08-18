.PHONY: clean install dist test tests update publish promote
SHELL=/bin/bash
ECR_REGISTRY=672626379771.dkr.ecr.us-east-1.amazonaws.com
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)

### This is the Terraform-generated header for slingshot-dev ###
ECR_NAME_DEV:=slingshot-dev
ECR_URL_DEV:=222053980223.dkr.ecr.us-east-1.amazonaws.com/slingshot-dev
### End of Terraform-generated header ###

help: ## Print this message
	@awk 'BEGIN { FS = ":.*##"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*##/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)


### Terraform-generated Developer Deploy Commands for Dev environment ###
dist-dev: ## Build docker container (intended for developer-based manual build)
	docker build --platform linux/amd64 \
	    -t $(ECR_URL_DEV):latest \
		-t $(ECR_URL_DEV):`git describe --always` \
		-t $(ECR_NAME_DEV):latest .

publish-dev: dist-dev ## Build, tag and push (intended for developer-based manual publish)
	docker login -u AWS -p $$(aws ecr get-login-password --region us-east-1) $(ECR_URL_DEV)
	docker push $(ECR_URL_DEV):latest
	docker push $(ECR_URL_DEV):`git describe --always`

### Terraform-generated manual shortcuts for deploying to Stage ###
### This requires that ECR_NAME_STAGE & ECR_URL_STAGE environment variables are set locally
### by the developer and that the developer has authenticated to the correct AWS Account.
### The values for the environment variables can be found in the stage_build.yml caller workflow.
dist-stage: ## Only use in an emergency
	docker build --platform linux/amd64 \
	    -t $(ECR_URL_STAGE):latest \
		-t $(ECR_URL_STAGE):`git describe --always` \
		-t $(ECR_NAME_STAGE):latest .

publish-stage: ## Only use in an emergency
	docker login -u AWS -p $$(aws ecr get-login-password --region us-east-1) $(ECR_URL_STAGE)
	docker push $(ECR_URL_STAGE):latest
	docker push $(ECR_URL_STAGE):`git describe --always`

# Commands for legacy AWS
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
