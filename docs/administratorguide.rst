.. _administratorguide:

Administrator guide
===================

This administrator guide is meant for people who would like to deploy and manage
REANA clusters. (The researchers are probably interested in reading the
:ref:`userguide` instead.)

Architecture
------------

REANA system is composed of multiple separated components that permit to define
and manage computing cloud resources that run computational workflows on the
cloud.

.. image:: /_static/reana-architecture.png

REANA uses the following technologies:

- `Python <https://www.python.org/>`_
- `Flask <http://flask.pocoo.org/>`_
- `Docker <https://www.docker.com/>`_
- `Kubernetes <https://kubernetes.io/>`_
- `RabbitMQ <http://www.rabbitmq.com/>`_
- `Yadage <https://github.com/diana-hep/yadage>`_
- `CWL <http://www.commonwl.org/>`_
- `EOS <https://github.com/cern-eos/eos>`_

Components
----------

REANA system is composed of multiple separated components that are developed
independently. The components are usually published as Python packages (user
client, administrator cluster management) or as Docker images (internal REANA
components).

reana-client
~~~~~~~~~~~~

REANA command line client for end users.

- source code: `<https://github.com/reanahub/reana-client>`_
- release notes: `<https://github.com/reanahub/reana-client/releases>`_
- known issues: `<https://github.com/reanahub/reana-client/issues>`_
- documentation: `<https://reana-client.readthedocs.io/>`_

reana-cluster
~~~~~~~~~~~~~

REANA component providing utilities to manage cluster instance.

- source code: `<https://github.com/reanahub/reana-cluster>`_
- release notes: `<https://github.com/reanahub/reana-cluster/releases>`_
- known issues: `<https://github.com/reanahub/reana-cluster/issues>`_
- documentation: `<https://reana-cluster.readthedocs.io/>`_

reana-commons
~~~~~~~~~~~~~

Shared utilities for REANA components.

- source code: `<https://github.com/reanahub/reana-commons>`_
- release notes: `<https://github.com/reanahub/reana-commons/releases>`_
- known issues: `<https://github.com/reanahub/reana-commons/issues>`_
- documentation: `<https://reana-commons.readthedocs.io/>`_

reana-db
~~~~~~~~

REANA component containing database models and utilities.

- source code: `<https://github.com/reanahub/reana-db>`_
- release notes: `<https://github.com/reanahub/reana-db/releases>`_
- known issues: `<https://github.com/reanahub/reana-db/issues>`_
- documentation: `<https://reana-db.readthedocs.io/>`_

reana-job-controller
~~~~~~~~~~~~~~~~~~~~

REANA component for running and managing jobs.

- source code: `<https://github.com/reanahub/reana-job-controller>`_
- release notes: `<https://github.com/reanahub/reana-job-controller/releases>`_
- known issues: `<https://github.com/reanahub/reana-job-controller/issues>`_
- documentation: `<https://reana-job-controller.readthedocs.io/>`_

reana-message-broker
~~~~~~~~~~~~~~~~~~~~

REANA component for messaging needs.

- source code: `<https://github.com/reanahub/reana-message-broker>`_
- release notes: `<https://github.com/reanahub/reana-message-broker/releases>`_
- known issues: `<https://github.com/reanahub/reana-message-broker/issues>`_
- documentation: `<https://reana-message-broker.readthedocs.io/>`_

pytest-reana
~~~~~~~~~~~~

Shared pytest fixtures and other common testing utilities.

- source code: `<https://github.com/reanahub/pytest-reana>`_
- release notes: `<https://github.com/reanahub/pytest-reana/releases>`_
- known issues: `<https://github.com/reanahub/pytest-reana/issues>`_
- documentation: `<https://pytest-reana.readthedocs.io/>`_

reana-server
~~~~~~~~~~~~

REANA component providing API server replying to client queries.

- source code: `<https://github.com/reanahub/reana-server>`_
- release notes: `<https://github.com/reanahub/reana-server/releases>`_
- known issues: `<https://github.com/reanahub/reana-server/issues>`_
- documentation: `<https://reana-server.readthedocs.io/>`_

reana-ui
~~~~~~~~

REANA UI frontend.

- source code: `<https://github.com/reanahub/reana-ui>`_
- release notes: `<https://github.com/reanahub/reana-ui/releases>`_
- known issues: `<https://github.com/reanahub/reana-ui/issues>`_
- documentation: `<https://reana-ui.readthedocs.io/>`_

reana-workflow-controller
~~~~~~~~~~~~~~~~~~~~~~~~~

REANA component for running and managing workflows.

- source code: `<https://github.com/reanahub/reana-workflow-controller>`_
- release notes: `<https://github.com/reanahub/reana-workflow-controller/releases>`_
- known issues: `<https://github.com/reanahub/reana-workflow-controller/issues>`_
- documentation: `<https://reana-workflow-controller.readthedocs.io/>`_

reana-workflow-engine-cwl
~~~~~~~~~~~~~~~~~~~~~~~~~

REANA component for running CWL types of workflows.

- source code: `<https://github.com/reanahub/reana-workflow-engine-cwl>`_
- release notes: `<https://github.com/reanahub/reana-workflow-engine-cwl/releases>`_
- known issues: `<https://github.com/reanahub/reana-workflow-engine-cwl/issues>`_
- documentation: `<https://reana-workflow-engine-cwl.readthedocs.io/>`_

reana-workflow-engine-serial
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REANA component for running simple sequential workflows.

- source code: `<https://github.com/reanahub/reana-workflow-engine-serial>`_
- release notes: `<https://github.com/reanahub/reana-workflow-engine-serial/releases>`_
- known issues: `<https://github.com/reanahub/reana-workflow-engine-serial/issues>`_
- documentation: `<https://reana-workflow-engine-serial.readthedocs.io/>`_

reana-workflow-engine-yadage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REANA component for running Yadage types of workflows.

- source code: `<https://github.com/reanahub/reana-workflow-engine-yadage>`_
- release notes: `<https://github.com/reanahub/reana-workflow-engine-yadage/releases>`_
- known issues: `<https://github.com/reanahub/reana-workflow-engine-yadage/issues>`_
- documentation: `<https://reana-workflow-engine-yadage.readthedocs.io/>`_

Deployment
----------

Local deployment using Minikube
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REANA cloud uses `Kubernetes <https://kubernetes.io/>`_ container orchestration
system. The best way to try it out locally is to set up `Minikube
<https://kubernetes.io/docs/getting-started-guides/minikube/>`_ (minikube
version 1.5.2 is known to work the best).

The minikube can be started as follows:

.. code-block:: console

   $ minikube start --feature-gates="TTLAfterFinished=true"

REANA cluster can be easily deployed by means of the ``reana-cluster`` helper
script. The typical usage scenario goes as follows:

.. code-block:: console

   $ # create new virtual environment
   $ virtualenv ~/.virtualenvs/myreana
   $ source ~/.virtualenvs/myreana/bin/activate
   $ # install reana-cluster utility
   $ pip install reana-cluster
   $ # deploy new cluster and check progress
   $ reana-cluster init
   $ reana-cluster status
   $ # set environment variables for reana-client
   $ eval $(reana-cluster env --include-admin-token) # since you are admin

For more information, please see `REANA-Cluster's Getting started guide
<http://reana-cluster.readthedocs.io/en/latest/gettingstarted.html>`_.

Next steps
----------

For more information, you can explore `REANA-Cluster documentation
<https://reana-cluster.readthedocs.io/>`_.
