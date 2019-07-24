# This file is part of REANA.
# Copyright (C) 2019 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# configuration options that may be passed as environment variables:
GITHUB_USER ?= anonymous
MINIKUBE_DRIVER ?= kvm2
MINIKUBE_PROFILE ?= minikube
MINIKUBE_CPUS ?= 2
MINIKUBE_MEMORY ?= 3072
MINIKUBE_DISKSIZE ?= 40g
TIMECHECK ?= 5
TIMEOUT ?= 300
VENV_NAME ?= reana
DEMO ?= DEMO

# bash shell is necessary
SHELL = /usr/bin/env bash

# let's detect where we are and whether minikube and kubectl are available:
HAS_KUBECTL := $(shell command -v kubectl 2> /dev/null)
HAS_MINIKUBE := $(shell command -v minikube 2> /dev/null)
DEBUG := $(shell test "$$CLUSTER_CONFIG" = dev && echo 1 || echo 0)
SHOULD_MINIKUBE_MOUNT := $(shell [ "${DEBUG}" -gt 0 ] && [ -z "`ps -ef | grep -i '[m]inikube mount' 2> /dev/null`" ] && echo 1 || echo 0)
PWD := $(shell pwd)

define n


endef

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
	@echo '  GITHUB_USER       Which GitHub user account to use for cloning? [default=anonymous]'
	@echo '  MINIKUBE_DRIVER   Which Minikube driver to use? [default=kvm2]'
	@echo '  MINIKUBE_PROFILE  Which Minikube profile to use? [default=minikube]'
	@echo '  TIMECHECK         Checking frequency in seconds when bringing cluster up and down? [default=5]'
	@echo '  TIMEOUT           Maximum timeout to wait when bringing cluster up and down? [default=300]'
	@echo '  VENV_NAME         Which Python virtual environment name to use? [default=reana]'
	@echo '  DEMO              Which demo example to run? [e.g. reana-demo-helloworld; default=several runable examples]'
	@echo '  CLUSTER_CONFIG    REANA cluster environment mode. Use "dev" for live coding and debugging.'
	@echo
	@echo 'Examples:'
	@echo
	@echo '  # how to set up personal development environment:'
	@echo '  $$ GITHUB_USER=johndoe MINIKUBE_DRIVER=virtualbox make setup clone'
	@echo
	@echo '  # how to build and deploy REANA in production mode:'
	@echo '  $ make build'
	@echo '  $ make deploy'
	@echo
	@echo '  # how to deploy REANA in development mode, with application'
	@echo '  # autoreload on code changes and debugging capabilities:'
	@echo '  $$ minikube mount $$(pwd)/..:/code'
	@echo '  $$ cd reana-server && pip install -e . && cd ..  # workaround necessary for reanahub/reana-workflow-controller#64'
	@echo '  $$ CLUSTER_CONFIG=dev make build'
	@echo '  $$ CLUSTER_CONFIG=dev make deploy'
	@echo
	@echo '  # how to build latest checked-out sources and run one small demo example:'
	@echo '  $$ DEMO=reana-demo-helloworld make ci'
	@echo
	@echo '  # how to build latest checked-out sources and run several runable demo examples:'
	@echo '  $$ make ci'
	@echo
	@echo '  # how to perform an independent automated CI test run:'
	@echo '  $$ mkdir /tmp/nightlybuild && cd /tmp/nightlybuild'
	@echo '  $$ git clone https://github.com/reanahub/reana && cd reana'
	@echo '  $$ VENV_NAME=nightlybuild MINIKUBE_PROFILE=nightlybuild make ci'
	@echo '  $$ VENV_NAME=nightlybuild MINIKUBE_PROFILE=nightlybuild make teardown'
	@echo '  $$ cd /tmp && rm -rf /tmp/nightlybuild'

setup: # Prepare local host virtual environment and Minikube for REANA building and deployment.
ifndef HAS_KUBECTL
	$(error "Please install Kubectl v1.14.0 or higher")
endif
ifndef HAS_MINIKUBE
	$(error "Please install Minikube v1.0.0 or higher")
endif
	minikube status --profile ${MINIKUBE_PROFILE} || minikube start --profile ${MINIKUBE_PROFILE} --vm-driver ${MINIKUBE_DRIVER} --cpus ${MINIKUBE_CPUS} --memory ${MINIKUBE_MEMORY} --disk-size ${MINIKUBE_DISKSIZE} --feature-gates="TTLAfterFinished=true"
	helm init
	test -e ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate || virtualenv ${HOME}/.virtualenvs/${VENV_NAME}

clone: # Clone REANA source code repositories locally.
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	pip install . --upgrade && \
	reana-dev git-clone -c ALL -u ${GITHUB_USER}

build: # Build REANA client and cluster components.
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	eval $$(minikube docker-env --profile ${MINIKUBE_PROFILE})  && \
	pip install . --upgrade &&  \
	pip uninstall -y reana-commons reana-client reana-cluster reana-db pytest-reana && \
	reana-dev install-client && \
	reana-dev install-cluster && \
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
ifeq ($(SHOULD_MINIKUBE_MOUNT),1)
	$(error "$nIt seems you are not running 'minikube mount'.  Please run the following command in a different terminal:$n$n\
	    $$ minikube mount $$(pwd)/..:/code$n$nThis will enable the cluster pods to see the live edits that are necessary for debugging.")
endif
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	eval $$(minikube docker-env --profile ${MINIKUBE_PROFILE}) && \
	reana-cluster -f ${PWD}/../reana-cluster/reana_cluster/configurations/reana-cluster-minikube$(addprefix -, ${CLUSTER_CONFIG}).yaml down && \
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
	reana-cluster -f ${PWD}/../reana-cluster/reana_cluster/configurations/reana-cluster-minikube$(addprefix -, ${CLUSTER_CONFIG}).yaml init --traefik --generate-db-secrets && \
	waited=0 && while true; do \
		waited=$$(($$waited+${TIMECHECK})); \
		if [ $$waited -gt ${TIMEOUT} ];then \
			break; \
		elif [ $$(kubectl logs -l app=server -c server --tail=500 | grep -c '^Created 1st user') -eq 1 ]; then \
			break; \
		else \
			sleep ${TIMECHECK}; \
		fi;\
	done

example: # Run all or one particular demo example. By default all REANA examples are executed.
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	eval $$(reana-dev setup-environment) && \
	reana-dev run-example -c ${DEMO}

prefetch: # Prefetch interesting Docker images. Useful to speed things later.
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	eval $$(minikube docker-env --profile ${MINIKUBE_PROFILE}) && \
	reana-dev docker-pull -c ${DEMO}

ci: # Perform full Continuous Integration build and test cycle. [main function]
	make setup
	make clone
	make prefetch
	make build
	make deploy
	make example

teardown: # Destroy local host virtual environment and Minikube. All traces go.
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
