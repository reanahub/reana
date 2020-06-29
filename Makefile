# This file is part of REANA.
# Copyright (C) 2019 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# configuration options that may be passed as environment variables:
BUILD_TYPE ?= dev
DEMO ?= DEMO
GITHUB_USER ?= anonymous
INSTANCE_NAME ?= reana
MINIKUBE_CPUS ?= 2
MINIKUBE_DISKSIZE ?= 40g
MINIKUBE_DRIVER ?= virtualbox
MINIKUBE_MEMORY ?= 3072
MINIKUBE_KUBERNETES ?= v1.16.3
TIMECHECK ?= 5
TIMEOUT ?= 300

# bash shell is necessary
SHELL = /usr/bin/env bash

# let's detect where we are and whether minikube and kubectl are available:
HAS_KUBECTL := $(shell command -v kubectl 2> /dev/null)
HAS_MINIKUBE := $(shell command -v minikube 2> /dev/null)
DEBUG := $(shell grep -q 'debug.enabled=true' <(echo ${CLUSTER_FLAGS}) && echo 1 || echo 0)
PWD := $(shell pwd)
REANA_CODE_DIR=$(shell cd ..; pwd)
TRUNC_INSTANCE_NAME=$(shell echo ${INSTANCE_NAME} | head -c 10 | xargs echo)
VALUES_YAML_PATH := $(shell test "${BUILD_TYPE}" = "dev" && echo helm/configurations/values-dev.yaml || echo helm/reana/values.yaml)

all: help

help:
	@echo 'Description:'
	@echo
	@echo '  This Makefile facilitates building and testing REANA on a local Minikube cluster.'
	@echo '  Useful for personal development and CI testing scenarios.'
	@echo
	@echo 'Available commands:'
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?# .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?# "}; {printf "  \033[36m%-17s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo 'Configuration options:'
	@echo
	@echo '  BUILD_TYPE              Is it a dev build or a release build? [default=dev]'
	@echo '  BUILD_ARGUMENTS         Space separated list of build arguments. [e.g. "COMPUTE_BACKENDS=htcondorcern" no build arguments are passed by default]'
	@echo '  CLUSTER_FLAGS           Which values need to be passed to Helm? [e.g. "debug.enabled=true,components.reana_ui.enabled=true"; no flags are passed by default]'
	@echo '  DEMO                    Which demo example to run? [e.g. "reana-demo-helloworld"; default is several]'
	@echo '  EXCLUDE_COMPONENTS      Which REANA components should be excluded from the build? [e.g. reana-ui,reana-message-broker]'
	@echo '  GITHUB_USER             Which GitHub user account to use for cloning for Minikube? [default=anonymous]'
	@echo '  INSTANCE_NAME           Which name/prefix to use for your REANA instance? [default=reana]'
	@echo '  MINIKUBE_CPUS           How many CPUs to allocate for Minikube? [default=2]'
	@echo '  MINIKUBE_DISKSIZE       How much disk size to allocate for Minikube? [default=40g]'
	@echo '  MINIKUBE_DRIVER         Which vm driver to use for Minikube? [default=virtualbox]'
	@echo '  MINIKUBE_MEMORY         How much memory to allocate for Minikube? [default=3072]'
	@echo '  MINIKUBE_KUBERNETES     Which Kubernetes version to use with Minikube? [default=v1.16.3]'
	@echo '  TIMECHECK               Checking frequency in seconds when bringing cluster up and down? [default=5]'
	@echo '  TIMEOUT                 Maximum timeout to wait when bringing cluster up and down? [default=300]'
	@echo '  SERVER_URL              Setting a customized REANA Server hostname? [e.g. "https://example.org"; default is Minikube IP]'
	@echo
	@echo 'Examples:'
	@echo
	@echo '  # Example 1: set up personal development environment'
	@echo '  $$ GITHUB_USER=johndoe make setup clone prefetch'
	@echo
	@echo '  # Example 2: build and deploy REANA in production mode'
	@echo '  $$ make build deploy'
	@echo
	@echo '  # Example 3: build REANA except REANA-UI and REANA-Message-Broker'
	@echo '  $$ EXCLUDE_COMPONENTS=r-ui,r-m-broker make build'
	@echo
	@echo '  # Example 4: build and deploy REANA in development mode (with live code changes and debugging)'
	@echo '  $$ CLUSTER_FLAGS=debug.enabled=true make build deploy'
	@echo
	@echo '  # Example 5: build and deploy REANA with a custom hostname including REANA-UI'
	@echo '  $$ CLUSTER_FLAGS=components.reana_ui.enabled=true SERVER_URL=https://example.org make build deploy'
	@echo
	@echo '  # Example 6: run one small demo example to verify the build'
	@echo '  $$ DEMO=reana-demo-helloworld make example'
	@echo
	@echo '  # Example 7: run several small examples to verify the build'
	@echo '  $$ make example'
	@echo
	@echo '  # Example 8: perform full CI build-and-test cycle'
	@echo '  $$ make ci'
	@echo
	@echo '  # Example 9: perform full CI build-and-test cycle for a given release before publishing'
	@echo '  $$ GITHUB_USER=reanahub BUILD_TYPE=release make ci'
	@echo '  $$ # If everything goes well you can publish all the images to DockerHub'
	@echo '  $$ reana-dev docker-push -t auto -u reanahub'
	@echo
	@echo '  # Example 10: perform full CI build-and-test cycle in an independent cluster'
	@echo '  $$ mkdir /tmp/nightly && cd /tmp/nightly'
	@echo '  $$ git clone https://github.com/reanahub/reana && cd reana'
	@echo '  $$ INSTANCE_NAME=nightly make ci'
	@echo '  $$ INSTANCE_NAME=nightly make teardown'
	@echo '  $$ cd /tmp && rm -rf /tmp/nightly'

setup: # Prepare local host virtual environment and Minikube for REANA building and deployment.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make setup\033[0m"
ifndef HAS_KUBECTL
	$(error "Please install Kubectl v1.16.3 or higher")
endif
ifndef HAS_MINIKUBE
	$(error "Please install Minikube v1.5.2 or higher")
endif
	minikube status --profile ${INSTANCE_NAME} || minikube start --kubernetes-version=${MINIKUBE_KUBERNETES} --profile ${INSTANCE_NAME} --vm-driver ${MINIKUBE_DRIVER} --cpus ${MINIKUBE_CPUS} --memory ${MINIKUBE_MEMORY} --disk-size ${MINIKUBE_DISKSIZE} --feature-gates="TTLAfterFinished=true"
	test -e ${HOME}/.virtualenvs/${INSTANCE_NAME}/bin/activate || virtualenv ${HOME}/.virtualenvs/${INSTANCE_NAME}
ifeq ($(MINIKUBE_DRIVER),virtualbox)
	is_vbox_vm_configured=$(shell vboxmanage showvminfo ${INSTANCE_NAME} | grep -qw ${REANA_CODE_DIR} && vboxmanage showvminfo ${INSTANCE_NAME} | grep -qw "reana-https" && vboxmanage showvminfo ${INSTANCE_NAME} | grep -qw "reana-http" && echo 1 || echo 0) && \
	if [ $$is_vbox_vm_configured -eq 0 ]; then \
		echo "Configuring VirtualBox for REANA..."; \
		minikube stop --profile ${INSTANCE_NAME}; \
		(vboxmanage showvminfo ${INSTANCE_NAME} | grep -qw ${REANA_CODE_DIR} && echo "REANA code mount already configured in the minikube VM") || (vboxmanage sharedfolder add ${INSTANCE_NAME} --name code --hostpath ${REANA_CODE_DIR} --automount && echo "REANA code mount is now configured in the minikube VM"); \
		(vboxmanage showvminfo ${INSTANCE_NAME} | grep -qw "reana-https" && echo "REANA HTTPS port forwarding already configured in the minikube VM") || (vboxmanage modifyvm "${INSTANCE_NAME}" --natpf1 "reana-https,tcp,,443,,30443" && echo "REANA HTTPS port forwarding is now configured in the minikube VM"); \
		(vboxmanage showvminfo ${INSTANCE_NAME} | grep -qw "reana-http" && echo "REANA HTTP port forwarding already configured in the minikube VM") || (vboxmanage modifyvm "${INSTANCE_NAME}" --natpf1 "reana-http,tcp,,80,,30080" && echo "REANA HTTP port forwarding is now configured in the minikube VM"); \
		minikube start --kubernetes-version=${MINIKUBE_KUBERNETES} --profile ${INSTANCE_NAME} --vm-driver ${MINIKUBE_DRIVER} --cpus ${MINIKUBE_CPUS} --memory ${MINIKUBE_MEMORY} --disk-size ${MINIKUBE_DISKSIZE} --feature-gates="TTLAfterFinished=true"; \
	fi
endif

clone: # Clone REANA source code repositories locally.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make clone\033[0m"
	source ${HOME}/.virtualenvs/${INSTANCE_NAME}/bin/activate && \
	pip install . --upgrade && \
	reana-dev git-clone -c ALL -u ${GITHUB_USER}

build: # Build REANA client and cluster components.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make build\033[0m"
ifeq ($(BUILD_TYPE),release)
	make release-build
else ifeq ($(BUILD_TYPE),dev)
	make dev-build
else
	echo "Unknown build type $$BUILD_TYPE"
endif

dev-build:
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make dev-build\033[0m"
	source ${HOME}/.virtualenvs/${INSTANCE_NAME}/bin/activate && \
	minikube docker-env --profile ${INSTANCE_NAME} > /dev/null && eval $$(minikube docker-env --profile ${INSTANCE_NAME}) && \
	pip install . --upgrade &&  \
	pip uninstall -y reana-commons reana-client reana-db pytest-reana && \
	reana-dev install-client && \
	if [ "${DEBUG}" -gt 0 ]; then \
		reana-dev python-install-eggs; \
	fi && \
	pip check && \
	reana-dev git-submodule --update && \
	reana-dev docker-build -b DEBUG=${DEBUG} $(addprefix --exclude-components , ${EXCLUDE_COMPONENTS})

release-build:
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make release-build\033[0m"
	source ${HOME}/.virtualenvs/${INSTANCE_NAME}/bin/activate && \
	minikube docker-env --profile ${INSTANCE_NAME} > /dev/null && eval $$(minikube docker-env --profile ${INSTANCE_NAME}) && \
	echo "Upgrading REANA to latest master ..." && \
	reana-dev git-upgrade -c CLUSTER && \
	echo "Cleaning components directories ..." && \
	reana-dev git-clean -c CLUSTER && \
	BUILT_IMAGES_FILE_PATH=$(shell echo /tmp/reana-images-`git describe --dirty`.txt) && \
	echo "Building images with no cache ..." && \
	reana-dev docker-build -c CLUSTER --no-cache \
		$(foreach argument, ${BUILD_ARGUMENTS}, -b ${argument}) \
		-u "${GITHUB_USER}" -t auto \
		--output-component-versions $$BUILT_IMAGES_FILE_PATH \
		$(addprefix --exclude-components , ${EXCLUDE_COMPONENTS}) && \
	echo "The following images have been built:" && \
	./scripts/update_images.sh $$BUILT_IMAGES_FILE_PATH && \
	rm $$BUILT_IMAGES_FILE_PATH

deploy: # Deploy/redeploy previously built REANA cluster.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make deploy\033[0m"
	source ${HOME}/.virtualenvs/${INSTANCE_NAME}/bin/activate && \
	minikube docker-env --profile ${INSTANCE_NAME} > /dev/null && eval $$(minikube docker-env --profile ${INSTANCE_NAME}) && \
	helm dep update helm/reana && (helm ls | grep -q ${TRUNC_INSTANCE_NAME} && helm uninstall ${TRUNC_INSTANCE_NAME}) && \
	kubectl get secrets -o custom-columns=":metadata.name" | grep ${TRUNC_INSTANCE_NAME} | xargs kubectl delete secret || \
	waited=0 && while true; do \
		waited=$$(($$waited+${TIMECHECK})); \
		if [ $$waited -gt ${TIMEOUT} ];then \
			break; \
		elif [ $$(kubectl get pods | wc -l) -eq 0 ]; then \
			break; \
		else \
			sleep ${TIMECHECK}; \
		fi;\
	done && \
	minikube ssh --profile ${INSTANCE_NAME} 'sudo rm -rf /var/reana' && \
	if [ $$(docker images | grep -c '<none>') -gt 0 ]; then \
		docker images | grep '<none>' | awk '{print $$3;}' | xargs docker rmi; \
	fi && \
	helm install ${TRUNC_INSTANCE_NAME} helm/reana $(addprefix --set , ${CLUSTER_FLAGS}) $(addprefix -f , ${VALUES_YAML_PATH}) --wait --namespace ${INSTANCE_NAME} --create-namespace && \
	kubectl config set-context --current --namespace=${INSTANCE_NAME} && \
	waited=0 && while true; do \
		waited=$$(($$waited+${TIMECHECK})); \
		if [ $$waited -gt ${TIMEOUT} ];then \
			break; \
		elif [ $$(kubectl logs -l app=${TRUNC_INSTANCE_NAME}-server -c rest-api --tail=1000 | grep -ce 'spawned uWSGI master process\|Serving Flask app') -eq 1 ]; then \
			break; \
		else \
			sleep ${TIMECHECK}; \
		fi;\
	done && \
	source ${PWD}/scripts/create-admin-user.sh ${TRUNC_INSTANCE_NAME} && \
	eval $$(reana-dev setup-environment $(addprefix --server-hostname , ${SERVER_URL}))

example: # Run one or several demo examples.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make example\033[0m"
	source ${HOME}/.virtualenvs/${INSTANCE_NAME}/bin/activate && \
	eval $$(reana-dev setup-environment $(addprefix --server-hostname , ${SERVER_URL})) && \
	reana-dev run-example -c ${DEMO}

prefetch: # Prefetch interesting Docker images. Useful to speed things later.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make prefetch\033[0m"
	source ${HOME}/.virtualenvs/${INSTANCE_NAME}/bin/activate && \
	minikube docker-env --profile ${INSTANCE_NAME} > /dev/null && eval $$(minikube docker-env --profile ${INSTANCE_NAME}) && \
	reana-dev docker-pull -c ${DEMO}

ci: # Perform full Continuous Integration build and test cycle. [main function]
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make ci\033[0m"
	make setup
	make clone
	make prefetch
	make build
	make deploy
	make example

teardown: # Destroy local host virtual environment and Minikube. All traces go.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make teardown\033[0m"
	minikube stop --profile ${INSTANCE_NAME}
	minikube delete --profile ${INSTANCE_NAME}
	rm -rf ${HOME}/.virtualenvs/${INSTANCE_NAME}
	@echo "You may also consider to run rm -rf ~/.minikube"

test: # Run unit tests on the REANA package.
	pydocstyle reana
	black --check .
	check-manifest --ignore ".travis-*"
	sphinx-build -qnNW docs docs/_build/html
	python setup.py test
	sphinx-build -qnNW -b doctest docs docs/_build/doctest
	helm lint helm/reana

# end of file
