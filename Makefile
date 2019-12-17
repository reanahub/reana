# This file is part of REANA.
# Copyright (C) 2019 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# configuration options that may be passed as environment variables:
DEMO ?= DEMO
GITHUB_USER ?= anonymous
MINIKUBE_CPUS ?= 2
MINIKUBE_DISKSIZE ?= 40g
MINIKUBE_DRIVER ?= virtualbox
MINIKUBE_MEMORY ?= 3072
MINIKUBE_PROFILE ?= minikube
MINIKUBE_KUBERNETES ?= v1.16.3
TIMECHECK ?= 5
TIMEOUT ?= 300
VENV_NAME ?= reana

# bash shell is necessary
SHELL = /usr/bin/env bash

# let's detect where we are and whether minikube and kubectl are available:
HAS_KUBECTL := $(shell command -v kubectl 2> /dev/null)
HAS_MINIKUBE := $(shell command -v minikube 2> /dev/null)
DEBUG := $(shell test "$$CLUSTER_CONFIG" = dev && echo 1 || echo 0)
SHOULD_MINIKUBE_MOUNT := $(shell [ "${DEBUG}" -gt 0 ] && [ -z "`ps -ef | grep -i '[m]inikube mount' 2> /dev/null`" ] && echo 1 || echo 0)
PWD := $(shell pwd)

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
	@echo '  CLUSTER_CONFIG      Which cluster configuration to use for Minikube? [e.g. "dev" for live coding and debugging; default is production]'
	@echo '  DEMO                Which demo example to run? [e.g. "reana-demo-helloworld"; default is several]'
	@echo '  GITHUB_USER         Which GitHub user account to use for cloning for Minikube? [default=anonymous]'
	@echo '  MINIKUBE_CPUS       How many CPUs to allocate for Minikube? [default=2]'
	@echo '  MINIKUBE_DISKSIZE   How much disk size to allocate for Minikube? [default=40g]'
	@echo '  MINIKUBE_DRIVER     Which vm driver to use for Minikube? [default=virtualbox]'
	@echo '  MINIKUBE_MEMORY     How much memory to allocate for Minikube? [default=3072]'
	@echo '  MINIKUBE_PROFILE    Which Minikube profile to use? [default=minikube]'
	@echo '  MINIKUBE_KUBERNETES Which Kubernetes version to use with Minikube? [default=v1.16.3]'
	@echo '  TIMECHECK           Checking frequency in seconds when bringing cluster up and down? [default=5]'
	@echo '  TIMEOUT             Maximum timeout to wait when bringing cluster up and down? [default=300]'
	@echo '  VENV_NAME           Which Python virtual environment name to use? [default=reana]'
	@echo '  SERVER_URL          Setting a customized REANA Server hostname? [e.g. "https://myreanaserver.com"; default is Minikube IP]'
	@echo '  CLUSTER_FLAGS       Which flags need to be passed to reana-cluster command? [e.g. "--loglevel --ui"; no flags are passed by default]'
	@echo
	@echo 'Examples:'
	@echo
	@echo '  # Example 1: set up personal development environment'
	@echo '  $$ GITHUB_USER=johndoe make setup clone prefetch'
	@echo
	@echo '  # Example 2: build and deploy REANA in production mode'
	@echo '  $$ make build deploy'
	@echo
	@echo '  # Example 3: build and deploy REANA in development mode (with live code changes and debugging)'
	@echo '  $$ minikube mount $$(pwd)/..:/code'
	@echo '  $$ CLUSTER_CONFIG=dev make build deploy'
	@echo
	@echo '  # Example 4: build and deploy REANA with a custom hostname including REANA-UI'
	@echo '  $$ CLUSTER_FLAGS=--ui SERVER_URL=https://reana-local.cern.ch make build deploy'
	@echo
	@echo '  # Example 5: run one small demo example to verify the build'
	@echo '  $$ DEMO=reana-demo-helloworld make example'
	@echo
	@echo '  # Example 6: run several small examples to verify the build'
	@echo '  $$ make example'
	@echo
	@echo '  # Example 7: perform full CI build-and-test cycle'
	@echo '  $$ make ci'
	@echo
	@echo '  # Example 8: perform full CI build-and-test cycle in an independent cluster'
	@echo '  $$ mkdir /tmp/nightlybuild && cd /tmp/nightlybuild'
	@echo '  $$ git clone https://github.com/reanahub/reana && cd reana'
	@echo '  $$ VENV_NAME=nightlybuild MINIKUBE_PROFILE=nightlybuild make ci'
	@echo '  $$ VENV_NAME=nightlybuild MINIKUBE_PROFILE=nightlybuild make teardown'
	@echo '  $$ cd /tmp && rm -rf /tmp/nightlybuild'

setup: # Prepare local host virtual environment and Minikube for REANA building and deployment.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make setup\033[0m"
ifndef HAS_KUBECTL
	$(error "Please install Kubectl v1.16.3 or higher")
endif
ifndef HAS_MINIKUBE
	$(error "Please install Minikube v1.5.2 or higher")
endif
	minikube status --profile ${MINIKUBE_PROFILE} || minikube start --kubernetes-version=${MINIKUBE_KUBERNETES} --profile ${MINIKUBE_PROFILE} --vm-driver ${MINIKUBE_DRIVER} --cpus ${MINIKUBE_CPUS} --memory ${MINIKUBE_MEMORY} --disk-size ${MINIKUBE_DISKSIZE} --feature-gates="TTLAfterFinished=true"
	test -e ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate || virtualenv ${HOME}/.virtualenvs/${VENV_NAME}

clone: # Clone REANA source code repositories locally.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make clone\033[0m"
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	pip install . --upgrade && \
	reana-dev git-clone -c ALL -u ${GITHUB_USER}

build: # Build REANA client and cluster components.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make build\033[0m"
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	minikube docker-env --profile ${MINIKUBE_PROFILE} > /dev/null && eval $$(minikube docker-env --profile ${MINIKUBE_PROFILE}) && \
	pip install . --upgrade &&  \
	pip uninstall -y reana-commons reana-client reana-cluster reana-db pytest-reana && \
	reana-dev install-client && \
	reana-dev install-cluster && \
	if [ "${DEBUG}" -gt 0 ]; then \
		cd ${PWD}/../reana-server/ && \
		python setup.py bdist_egg && \
		cd -; \
	fi && \
	pip check && \
	reana-dev git-submodule --update && \
	reana-dev docker-build -b DEBUG=${DEBUG} && \
	reana-dev git-submodule --delete && \
	if [ "${DEBUG}" -gt 0 ]; then \
		echo "Please run minikube mount in a new terminal to have live code updates." && \
		echo "" && \
		echo "    $$ minikube mount $$(pwd)/..:/code" && \
		echo "" && \
		echo "For more information visit the documentation: https://reana-cluster.readthedocs.io/en/latest/developerguide.html#deploying-latest-master-branch-versions"; \
	fi

deploy: # Deploy/redeploy previously built REANA cluster.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make deploy\033[0m"
ifeq ($(SHOULD_MINIKUBE_MOUNT),1)
	$(error "$nIt seems you are not running 'minikube mount'.  Please run the following command in a different terminal:$n$n\
	    $$ minikube mount $$(pwd)/..:/code$n$nThis will enable the cluster pods to see the live edits that are necessary for debugging.")
endif
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	minikube docker-env --profile ${MINIKUBE_PROFILE} > /dev/null && eval $$(minikube docker-env --profile ${MINIKUBE_PROFILE}) && \
	reana-cluster -f ${PWD}/../reana-cluster/reana_cluster/configurations/reana-cluster-minikube$(addprefix -, ${CLUSTER_CONFIG}).yaml $(CLUSTER_FLAGS) down --delete-traefik --delete-secrets && \
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
	minikube ssh --profile ${MINIKUBE_PROFILE} 'sudo rm -rf /var/reana' && \
	if [ $$(docker images | grep -c '<none>') -gt 0 ]; then \
		docker images | grep '<none>' | awk '{print $$3;}' | xargs docker rmi; \
	fi && \
	reana-cluster -f ${PWD}/../reana-cluster/reana_cluster/configurations/reana-cluster-minikube$(addprefix -, ${CLUSTER_CONFIG}).yaml $(CLUSTER_FLAGS) init && \
	waited=0 && while true; do \
		waited=$$(($$waited+${TIMECHECK})); \
		if [ $$waited -gt ${TIMEOUT} ];then \
			break; \
		elif [ $$(kubectl logs -l app=server -c server --tail=500 | grep -ce 'spawned uWSGI master process\|Serving Flask app') -eq 1 ]; then \
			break; \
		else \
			sleep ${TIMECHECK}; \
		fi;\
	done && \
	eval $$(reana-dev setup-environment $(addprefix --server-hostname , ${SERVER_URL}))

example: # Run one or several demo examples.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make example\033[0m"
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	eval $$(reana-dev setup-environment $(addprefix --server-hostname , ${SERVER_URL})) && \
	reana-dev run-example -c ${DEMO}

prefetch: # Prefetch interesting Docker images. Useful to speed things later.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make prefetch\033[0m"
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	minikube docker-env --profile ${MINIKUBE_PROFILE} > /dev/null && eval $$(minikube docker-env --profile ${MINIKUBE_PROFILE}) && \
	reana-dev docker-pull -c ${DEMO}

ci: # Perform full Continuous Integration build and test cycle. [main function]
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make ci\033[0m"
	make setup
	make clone
	make prefetch
	make build
	make deploy
	sleep ${TIMECHECK} && sleep ${TIMECHECK} && sleep ${TIMECHECK} && sleep ${TIMECHECK}
	make example

teardown: # Destroy local host virtual environment and Minikube. All traces go.
	@echo -e "\033[1;32m[$$(date +%Y-%m-%dT%H:%M:%S)]\033[1;33m reana:\033[0m\033[1m make teardown\033[0m"
	minikube stop --profile ${MINIKUBE_PROFILE}
	minikube delete --profile ${MINIKUBE_PROFILE}
	rm -rf ${HOME}/.virtualenvs/${VENV_NAME}
	@echo "You may also consider to run rm -rf ~/.minikube"

test: # Run unit tests on the REANA package.
	pydocstyle reana
	isort -rc -c -df **/*.py
	check-manifest --ignore ".travis-*"
	sphinx-build -qnNW docs docs/_build/html
	python setup.py test
	sphinx-build -qnNW -b doctest docs docs/_build/doctest

# end of file
