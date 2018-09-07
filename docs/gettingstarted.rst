.. _gettingstarted:

Getting started
===============

Get started with the REANA reusable analysis platform by exploring the following
three steps.

Step One: Structure your analysis
---------------------------------

Structure your research data analysis repository into "inputs", "code",
"environments", "workflows" directories, following up the model of the
:ref:`fourquestions`. Create ``reana.yaml`` describing your structure:

.. code-block:: yaml

    version: 0.2.0
    code:
      files:
      - code/mycode.py
    inputs:
      files:
        - inputs/mydata.csv
      parameters:
        myparameter: myvalue
    environments:
      - type: docker
        image: johndoe/mypython:1.0
    workflow:
      type: cwl
      file: workflow/myworkflow.cwl
    outputs:
      files:
      - outputs/myplot.png

(see :ref:`examples`)

Step Two: Install REANA cluster
-------------------------------

You can use an existing REANA cloud deployment (if you have access to one) by
setting the ``REANA_SERVER_URL`` environment variable:

.. code-block:: console

   $ export REANA_SERVER_URL=https://reana.cern.ch/

You can also easily deploy your own REANA cloud instance by using the
``reana-cluster`` command line utility:

.. code-block:: console

   $ # install kubectl 1.11.2 and minikube 0.28.2
   $ sudo dpkg -i kubectl*.deb minikube*.deb
   $ minikube start --kubernetes-version="v1.11.2"
   $ # install reana-cluster utility
   $ mkvirtualenv reana-cluster
   $ pip install reana-cluster
   $ # deploy new cluster and check progress
   $ reana-cluster init
   $ reana-cluster status
   $ # set environment variables for reana-client
   $ eval $(reana-cluster env)

(see `REANA-Cluster's Getting started guide
<http://reana-cluster.readthedocs.io/en/latest/gettingstarted.html>`_)

Step Three: Run REANA client
----------------------------

You can run your analysis on the REANA cloud by using the ``reana-client``
command line client:

.. code-block:: console

   $ # install reana-client
   $ mkvirtualenv reana-client -p /usr/bin/python2.7
   $ pip install reana-client
   $ reana-client ping
   $ # create new workflow
   $ export REANA_WORKON=$(reana-client workflow create)
   $ # upload runtime code and inputs
   $ reana-client code upload ./code/*
   $ reana-client inputs upload ./inputs/*
   $ # start workflow and check progress
   $ reana-client workflow start
   $ reana-client workflow status
   $ # download outputs
   $ reana-client outputs list
   $ reana-client outputs download myplot.png

(see `REANA-Client's Getting started guide
<http://reana-client.readthedocs.io/en/latest/gettingstarted.html>`_)

Next steps
----------

For more information, please see:

- Are you a researcher who would like to run a reusable analysis on REANA cloud?
  You can install and use `reana-client <https://reana-client.readthedocs.io/>`_
  utility that provides interface to both local and remote REANA cloud
  installations. For more information, please see the :ref:`userguide`. You may
  also be interested in checking out some existing :ref:`examples`.

- Are you an administrator who would like to deploy and manage REANA cloud?
  You can start by deploying REANA locally on your laptop using `reana-cluster
  <https://reana-cluster.readthedocs.io/>`_ utility that uses Kubernetes and
  Minikube. For more information, please see the :ref:`administratorguide`.

- Are you a software developer who would like to contribute to REANA? You may be
  interested in trying out REANA both from the user point of view and the
  administrator point of view first. Follow by reading the :ref:`developerguide`
  afterwards.
