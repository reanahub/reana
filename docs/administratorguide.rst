.. _administratorguide:

Administrator guide
===================

This administrator guide is meant for people who would like to deploy and manage
REANA clusters.

Local deployment using Minikube
-------------------------------

REANA cloud uses `Kubernetes <https://kubernetes.io/>`_ container orchestration
system. The best way to try it out locally is to set up `Minikube
<https://kubernetes.io/docs/getting-started-guides/minikube/>`_ (minikube version 0.23.0 is
known to work the best).

The minikube can be started as follows:

.. code-block:: console

   $ minikube start --kubernetes-version="v1.6.4"

REANA cluster can be easily deployed by means of the ``reana-cluster`` helper
script. The typical usage scenario goes as follows:

.. code-block:: console

   $ mkvirtualenv reana-cluster
   $ pip install reana-cluster
   $ reana-cluster init
   $ # wait several minutes...
   $ reana-cluster status

For more information, please see `reana-cluster documentation
<https://reana-cluster.readthedocs.io/>`_.

Next steps
----------

For more information, please see `reana-cluster documentation
<https://reana-cluster.readthedocs.io/>`_.
