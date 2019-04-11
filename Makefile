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
TIME_SLEEP ?= 40
VENV_NAME ?= reana
DEMO ?= DEMO

# let's detect where we are and whether minikube and kubectl are available:
HAS_KUBECTL := $(shell command -v kubectl 2> /dev/null)
HAS_MINIKUBE := $(shell command -v minikube 2> /dev/null)
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
	@echo '  GITHUB_USER       Which GitHub user account to use for cloning? [default=anonymous]'
	@echo '  MINIKUBE_DRIVER   Which Minikube driver to use? [default=kvm2]'
	@echo '  MINIKUBE_PROFILE  Which Minikube profile to use? [default=minikube]'
	@echo '  TIME_SLEEP        How much time to sleep when bringing cluster up and down? [default=40]'
	@echo '  VENV_NAME         Which Python virtual environment name to use? [default=reana]'
	@echo
	@echo 'Examples:'
	@echo
	@echo '  # how to set up personal development environment:'
	@echo '  $$ GITHUB_USER=johndoe MINIKUBE_DRIVER=virtualbox make setup clone'
	@echo '  # how to build latest checked-out sources and run an example:'
	@echo '  $$ make ci'
	@echo
	@echo '  # how to run a specific example:'
	@echo '  $$ DEMO=reana-demo-helloworld make example'
	@echo '  # how to run all REANA examples:'
	@echo '  $$ make example'
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
	reana-dev docker-build -t latest && \
	reana-dev git-submodule --delete

deploy: # Deploy/redeploy previously built REANA cluster.
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	eval $$(minikube docker-env --profile ${MINIKUBE_PROFILE}) && \
	reana-cluster -f ${PWD}/../reana-cluster/reana_cluster/configurations/reana-cluster-latest.yaml down && \
	sleep ${TIME_SLEEP} && \
	minikube ssh --profile ${MINIKUBE_PROFILE} 'sudo rm -rf /var/reana' && \
	docker images | grep '<none>' | awk '{print $$3;}' | xargs -r docker rmi && \
	reana-cluster -f ${PWD}/../reana-cluster/reana_cluster/configurations/reana-cluster-latest.yaml init --traefik

example: # Run a REANA example. By default all REANA examples are executed.
	source ${HOME}/.virtualenvs/${VENV_NAME}/bin/activate && \
	eval $$(reana-dev setup-environment) && \
	reana-dev run-example -c ${DEMO} -s ${TIME_SLEEP}

ci: # Perform full Continuous Integration build and test cycle. [main function]
	make setup
	make clone
	make build
	make deploy
	sleep ${TIME_SLEEP}
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
