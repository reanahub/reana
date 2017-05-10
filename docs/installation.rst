Installation
============

Installing REANA client
-----------------------

.. admonition:: Work-In-Progress

   **FIXME** The ``reana-client`` package is a not-yet-released work in
   progress. Until it is available, you can use ``reana run ...`` on the REANA
   server side, see the :ref:`gettingstarted` documentation.

If you are a researcher that is interested in running analyses on the REANA
cloud, all you need to install is the ``reana-client``:

.. code-block:: console

   $ pip install reana-client

You can select the REANA cloud instance where to run your analyses by setting
the ``REANA_SERVER_URL`` variable appropriately. For example:

.. code-block:: console

   $ export REANA_SERVER_URL=https://reana.cern.ch

You can then submit your job:

.. code-block:: console

   $ cd my-reseach-data-analysis
   $ reana-client run
   [INFO] Preparing to run analysis...
   [...]
   [INFO] Done. You can see the results in the `output/` directory.

Installing REANA cloud
----------------------

We start by creating a fresh new Python virtual environment which will handle
our REANA cluster sources:

.. code-block:: console

   $ mkvirtualenv reana

We install the ``reana`` package from PyPI or GitHub:

.. code-block:: console

   $ pip install \
        -e 'git+https://github.com/reanahub/reana.git@master#egg=reana'

Configuring cluster
-------------------

There are several options on how to prepare the REANA backend computing cluster.

Minikube
~~~~~~~~

If you would like to try REANA local cloud on your laptop, creating a local
cluster using `Minikube
<https://kubernetes.io/docs/getting-started-guides/minikube/>`_ is a good way to
proceed. Please follow the :ref:`gettingstarted` guide that provides a detailed
walk-through if you would like to go this way.

CERN OpenStack
~~~~~~~~~~~~~~

If you have access to the `CERN OpenStack cloud infrastructure
<http://clouddocs.web.cern.ch/clouddocs/containers/index.html>`_ you can proceed
as follows.

We need to run ``magnum`` client that we can run locally:

.. code-block:: console

   $ docker login gitlab-registry.cern.ch
   $ sudo docker run -it gitlab-registry.cern.ch/cloud/ciadm /bin/bash

or by logging into ``lxplus-cloud.cern.ch``:

.. code-block:: console

   $ ssh lxplus-cloud.cern.ch

where ``magnum`` client is also available.

We can create the REANA backend cluster in the following way:

.. code-block:: console

   $ magnum cluster-create \
                --name reana-cluster \
                --keypair-id reanakey \
                --cluster-template kubernetes \
                --node-count 2

After the cluster is created, you should load the cluster configuration into the
Kubernetes client:

.. code-block:: console

   $ $(magnum cluster-config reana-cluster)

Initialising cloud
------------------

The REANA system can now be deployed onto either local or remote computing
cluster. We continue by pulling REANA component images:

.. code-block:: console

   $ reana pull

and generating cluster infrastructure manifests for deployment:

.. code-block:: console

   $ reana prepare

that we deploy as follows:

.. code-block:: console

   $ reana deploy

We are done! Our REANA cloud instance is now up and running and ready to take
jobs.

You may want to follow by running some example applications as mentioned in the
:ref:`gettingstarted` guide.
