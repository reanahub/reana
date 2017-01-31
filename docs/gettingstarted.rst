Getting started
===============

Create a Kubernetes cluster
---------------------------

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

It is at this point that we will have the `kubectl` command available
to manage our brand new cluster.

For more information on Kubernetes/OpenStack, please see
`CERN Cloud Docs <http://clouddocs.web.cern.ch/clouddocs/containers/quickstart.html#create-a-cluster>`__.

Create the Kubernetes resources using manifest files
----------------------------------------------------
- Clone `reana-resources-k8s <https://github.com/reanahub/reana-resources-k8s>`__:

  ``git clone https://github.com/reanahub/reana-resources-k8s.git``

- Change Kubernetes service account token in `reana-job-controller` node configuration file:

.. code-block:: console

     $ kubectl get secrets
     NAME                  TYPE                                  DATA      AGE
     default-token-XXXXX   kubernetes.io/service-account-token   3         13d
     $ sed 's/default-token-02p0z/default-token-XXXXX/' -i reana-resources-k8s/deployments/reana-system/job-controller.yaml

-  Create REANA system instances:

   ``kubectl create -f reana-resources-k8s/deployments/reana-system``

-  Yadage workers:

   ``kubectl create -f reana-resources-k8s/deployments/yadage-workers``

-  Services:

   ``kubectl create -f reana-resources-k8s/services/``

-  Secrets (you should provide your own CephFS secret):

   ``kubectl create -f reana-resources-k8s/secrets/``

Get the Workflow Controller ip address and port
-----------------------------------------------
.. code-block:: console

    $ kubectl describe services workflow-controller | grep NodePort
    NodePort:                  http                    32313/TCP
    $ kubectl get pods | grep workflow-controller | cut -d" " -f 1 | xargs kubectl describe pod | grep 'Node:'
    Node:        192.168.99.100,192.168.99.100

So the Workflow Controller component can be accessed through ``192.168.99.100:32313``.

Launch workflows
----------------

Launch Yadage workflows
~~~~~~~~~~~~~~~~~~~~~~~

FIXME

.. admonition:: CAVEAT LECTOR

   The "Getting started" guide will be expanded to cover how to launch workflows
   and jobs, how to monitor workflows, how to initialise the workflow work space
   and how to obtain the results back.
