Backends
========

Kubernetes
----------

Local instance
``````````````
Creating a local cluster using `minikube` is a good way of trying REANA.
The `reana` CLI gives the option of installing and running it automatically:

.. code-block:: console

   $ reana install-minikube

Of course, the option of installing it manually using package managers or
following the `official documentation <https://kubernetes.io/docs/getting-started-guides/minikube/>`__
is always available.

Once `minikube` is installed and running it is important to rememeber that
for using `minikube`'s docker daemon the following command should be run:

.. code-block:: console

   $ eval "$(minikube docker-env)"

This is something important for local development so all changes made to
images are kept locally, avoiding network delays.

CERN OpenStack
``````````````
In order to create a Kubernetes cluster using OpenStack infrastructure,
we need to run the magnum command, which we can have available running
the magnum docker client:

.. code-block:: console

  $ docker login gitlab-registry.cern.ch
  $ sudo docker run -it gitlab-registry.cern.ch/cloud/ciadm /bin/bash

Or logging into `lxplus-cloud`:

.. code-block:: console

  $ ssh lxplus-cloud.cern.ch

Once we have it available we are ready to create the cluster:

.. code-block:: console

  $ magnum cluster-create --name reana-cluster --keypair-id reanakey \
                          --cluster-template kubernetes --node-count 2

Lastly, we must load the cluster configuration into the Kubernetes
client:

.. code-block:: console

  $ $(magnum cluster-config reana-cluster)

From now on, the ``reana`` CLI can be used.

For more information on Kubernetes/OpenStack, please see
`CERN Cloud Docs <http://clouddocs.web.cern.ch/clouddocs/containers/quickstart.html#create-a-cluster>`__.
