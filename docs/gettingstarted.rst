.. _gettingstarted:

Getting started
===============

Get started with the REANA reusable analysis platform by exploring the following
three steps.

Step One: Structure your analysis
---------------------------------

Structure your research data analysis repository into input "data" and
"parameters", runtime "code", computing "environments", and computational
"workflows", following the model of the :ref:`fourquestions`. Create
``reana.yaml`` describing your structure:

.. code-block:: yaml

    version: 0.4.0
    inputs:
      files:
        - code/mycode.py
        - data/mydata.csv
      parameters:
        myparameter: myvalue
    workflow:
      type: cwl
      file: workflow/myworkflow.cwl
    outputs:
      files:
        - results/myplot.png

See and run some :ref:`examples`.

Step Two: Install REANA cluster
-------------------------------

You can use an existing REANA cloud deployment (if you have access to one) by
setting the ``REANA_SERVER_URL`` environment variable and providing a valid
token:

.. code-block:: console

   $ export REANA_SERVER_URL=https://reana.cern.ch/
   $ export REANA_ACCESS_TOKEN=XXXXXXX

You can also easily deploy your own REANA cloud instance by using the
``reana-cluster`` command line utility (see `prerequisites
<https://reana-cluster.readthedocs.io/en/latest/userguide.html#prerequisites>`_):

.. code-block:: console

   $ # install kubectl 1.14.0 and minikube 1.0.0
   $ sudo dpkg -i kubectl*.deb minikube*.deb
   $ minikube start --feature-gates="TTLAfterFinished=true"
   $ # create new virtual environment
   $ virtualenv ~/.virtualenvs/myreana
   $ source ~/.virtualenvs/myreana/bin/activate
   $ # install reana-cluster utility
   $ pip install reana-cluster
   $ # deploy helm inside the cluster
   $ helm init
   $ # deploy new cluster and check progress
   $ reana-cluster init --traefik
   $ reana-cluster status
   $ # set environment variables for reana-client
   $ eval $(reana-cluster env --incude-admin-token) # since you are admin

See `REANA-Cluster's Getting started guide
<http://reana-cluster.readthedocs.io/en/latest/gettingstarted.html>`_ for more
information.

Step Three: Run REANA client
----------------------------

You can run your analysis on the REANA cloud by using the ``reana-client``
command line client:

.. code-block:: console

   $ # create new virtual environment
   $ virtualenv ~/.virtualenvs/myreana
   $ source ~/.virtualenvs/myreana/bin/activate
   $ # install REANA client
   $ pip install reana-client
   $ # create new workflow
   $ reana-client create -n my-analysis
   $ export REANA_WORKON=my-analysis
   $ # upload input code and data to the workspace
   $ reana-client upload
   $ # start computational workflow
   $ reana-client start
   $ # check its progress
   $ reana-client status
   $ # list workspace files
   $ reana-client ls
   $ # download output results
   $ reana-client download

See `REANA-Client's Getting started guide
<http://reana-client.readthedocs.io/en/latest/gettingstarted.html>`_ for more
information.

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
