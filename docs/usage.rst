Usage
=====

Create a Kubernetes cluster
---------------------------

Run OpenStack magnum docker client:

::

$ docker login gitlab-registry.cern.ch
$ sudo docker run -it gitlab-registry.cern.ch/cloud/ciadm /bin/bash

Once this is done, follow the `Cloud
Docs <http://clouddocs.web.cern.ch/clouddocs/containers/quickstart.html#create-a-cluster>`__
to create a Kubernetes cluster.

Download the code
-----------------
Get git repo.

``git clone --recursive https://github.com/focilo/focilo.git``

And change Kubernetes service account token in step-broker node.
::

    $ kubectl get secrets
    NAME                  TYPE                                  DATA      AGE
    default-token-XXXXX   kubernetes.io/service-account-token   3         13d
    $ sed 's/default-token-02p0z/default-token-XXXXX/' -i kubernetes-cluster/deployments/cap-system/step-broker-rc.yaml

Create the Kubernetes resources using manifest files
----------------------------------------------------

-  Cap system instances:

   ``kubectl create -f kubernetes-cluster/deployments/cap-system``

-  Yadage workers (currently only one):

   ``kubectl create -f kubernetes-cluster/deployments/yadage-workers/``

-  Fibonacci worker (Since Yadage workers are not launching jobs yet, add a fibonacci worker to see how it works).

   ``kubectl create -f kubernetes-cluster/deployments/fibonacci-workers/alice-worker-rc.yaml``

-  Services:

   ``kubectl create -f kubernetes-cluster/services/``

-  Secrets:

   ``kubectl create -f kubernetes-cluster/secrets/``

Get the Workflow Controller (web node) ip address and port
----------------------------------------------------------
::

    $ kubectl describe services workflow-execution-cont | grep NodePort
    NodePort:                  http                    32313/TCP
    $ kubectl get pods | grep workflow-execution-controller | cut -d" " -f 1 | xargs kubectl describe pod | grep 'Node:'
    Node:        192.168.99.100,192.168.99.100

So this web server container can be accesses through ``192.168.99.100:32313``.

``sed 's/137.138.7.46:32331/192.168.99.100:32313/' -i workflow-execution-controller/cli-client/cli.py``

Launch jobs against the API
---------------------------

Launch fibonacci workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~

Enter the ``tests`` directory and call cli.py (requires ``click`` and
``requests`` packages) with the following parameters (you can do this
out of the OpenStack client it is just a call to the public API):

``python cli.py fibonacci -f fib_file -e alice``

Once you run the command you should start seeing that Kubernetes has
launched some jobs.

::

    kubectl get jobs --all-namespaces

    NAMESPACE NAME DESIRED SUCCESSFUL AGE default
    bdfdbb1d-e832-46e3-9bf6-6e1ab8d57624-0 1 0 1m default
    bdfdbb1d-e832-46e3-9bf6-6e1ab8d57624-1 1 0 1m default
    bdfdbb1d-e832-46e3-9bf6-6e1ab8d57624-2 1 0 1m default
    bdfdbb1d-e832-46e3-9bf6-6e1ab8d57624-3 1 0 1m default
    bdfdbb1d-e832-46e3-9bf6-6e1ab8d57624-4 1 0 1m

For checking the results you can connect to node the``\ storage-admin\`
node which is hosting all the nodes:

::

    $ kubectl exec -ti storage-admin bash
    ~ cd /mnt/ceph/alice
    ~ ls -lrt``

An example could be:
::

    /bdfdbb1d-e832-46e3-9bf6-6e1ab8d57624/0/input.dat
    /bdfdbb1d-e832-46e3-9bf6-6e1ab8d57624/0/output.dat

Where you can have a look on the input and output data for the step 0 of
the workflow bdfdbb1d-e832-46e3-9bf6-6e1ab8d57624.

Launch Yadage workflows
~~~~~~~~~~~~~~~~~~~~~~~

Enter the ``tests`` directory and call cli.py (requires ``click`` and
``requests`` packages) with the following parameters (you can do this
out of the OpenStack client it is just a call to the public API):

``python cli.py yadage --experiment cms --toplevel some-text --workflow some-text --parameters '{"par1" : "val1"}'``

::

    $ kubectl get pods | grep cms-yadage-workflow-controller | cut -d" " -f1 | xargs kubectl logs
    [2016-11-18 09:40:41,251: INFO/MainProcess] Received task: tasks.run_yadage_workflow[dddde31a-ce2f-46f8-b4dc-46a8a1e4f5f9]
    [2016-11-18 09:40:41,256: WARNING/Worker-1] some-text
    [2016-11-18 09:40:41,256: WARNING/Worker-1] some-text
    [2016-11-18 09:40:41,256: WARNING/Worker-1] {"par1" : "val1"}
    [2016-11-18 09:40:41,259: INFO/MainProcess] Task tasks.run_yadage_workflow[dddde31a-ce2f-46f8-b4dc-46a8a1e4f5f9] succeeded in 0.00235133804381s: None
