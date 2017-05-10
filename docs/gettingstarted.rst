.. _gettingstarted:

Getting started
===============

About
-----

This tutorial explains how to install a local REANA cloud to get started with
REANA development.

Install minikube
----------------

REANA cloud uses `Kubernetes <https://kubernetes.io/>`_ container orchestration
system. The best way to try it out locally is to set up `Minikube
<https://kubernetes.io/docs/getting-started-guides/minikube/>`_. How to do this
depends on your operating system. For example, on Arch Linux, you can install
the following packages:

- `virtualbox <https://www.archlinux.org/packages/community/x86_64/virtualbox/>`_
- `virtualbox-guest-iso <https://www.archlinux.org/packages/community/x86_64/virtualbox-guest-iso/>`_
- `virtualbox-host-modules-arch <https://www.archlinux.org/packages/community/x86_64/virtualbox-host-modules-arch/>`_
- `docker <https://www.archlinux.org/packages/community/x86_64/docker/>`_
- `minikube (AUR) <https://aur.archlinux.org/packages/minikube/>`_
- `kubectl-bin (AUR) <https://aur.archlinux.org/packages/kubectl-bin/>`_

Here is one example of supported versions:

.. code-block:: console

   $ pacman -Q | grep -iE '(docker|virtualbox|kube)'
   docker 1:17.05.0-1
   kubectl-bin 1.5.4-1
   minikube 0.17.1-1
   virtualbox 5.1.22-2
   virtualbox-guest-iso 5.1.22-1
   virtualbox-host-modules-arch 5.1.22-2

Start minikube
--------------

Once minikube is installed, you should start the Minikube VM:

.. code-block:: console

   $ minikube start

and instruct your shell to use Minikube's Docker connection:

.. code-block:: console

   $ eval "$(minikube docker-env)"

Install REANA
-------------

Install REANA system sources in a fresh Python virtual environment:

.. code-block:: console

   $ mkvirtualenv reana
   $ pip install 'git+https://github.com/reanahub/reana.git@master#egg=reana'

Initialise REANA cloud
----------------------

You can now initialise REANA cloud on the local minikube cluster:

.. code-block:: console

   $ reana init

This will take several minutes to create the pods and download REANA compontent
images. Once it finishes, we can check the REANA cluster pods:

.. code-block:: console

   $ kubectl get pods
   NAME                                   READY     STATUS    RESTARTS   AGE
   job-controller-3834756890-xsw1x        1/1       Running   0          48s
   message-broker-1410199975-4fkgm        1/1       Running   0          48s
   storage-admin                          1/1       Running   0          47s
   workflow-controller-2689978795-lj59n   1/1       Running   0          47s
   workflow-monitor-1639319062-2hdt7      1/1       Running   0          47s
   yadage-alice-worker-2356735553-kg9m4   1/1       Running   0          47s
   yadage-atlas-worker-1840967394-pcvfx   1/1       Running   0          47s
   yadage-cms-worker-945219876-140gq      1/1       Running   0          47s
   yadage-lhcb-worker-1129769854-75m90    1/1       Running   0          47s
   zeromq-msg-proxy-1617754619-7v7jl      1/1       Running   0          47s

Finally, we can test whether the REANA components are ready:

.. code-block:: console

   # check workflows:
   $ curl "http://$(reana get reana-workflow-controller)/workflows"
   {
     "workflows": {}
   }
   # check jobs:
   $ curl "http://$(reana get reana-job-controller)/jobs"
   {
     "jobs": {}
   }
   # check monitor UI:
   $ firefox "http://$(reana get reana-workflow-monitor)/helloworld"

Run "hello world" example application
-------------------------------------

You can now submit a simple `"hello world" example application
<https://github.com/reanahub/reana-demo-helloworld>`_ to run on your local REANA
cloud:

.. code-block:: console

   $ reana run reanahub/reana-demo-helloworld

Let us verify whether it worked:

.. code-block:: console

   $ minikube ssh
   minikube> find /reana/atlas/ -name greetings.txt
   /reana/atlas/a624f984-7d1d-4932-860a-fb4873af9563/yadage/helloworld/greetings.txt
   minikube> cat /reana/atlas/a624f984-7d1d-4932-860a-fb4873af9563/yadage/helloworld/greetings.txt
   minikube> Hello JohnDoe!

Run "word population" example analysis
--------------------------------------

You can now submit a `"world population" example analysis
<https://github.com/reanahub/reana-demo-worldpopulation>`_ to run on your local
REANA cloud:

.. code-block:: console

   $ reana run reanahub/reana-demo-worldpopulation

Let us verify whether it worked:

.. code-block:: console

   $ minikube ssh
   minikube> find /reana/atlas/ -name world_population_analysis.html
   /reana/atlas/8a73eea9-7cd7-42a0-91fd-fb3fb3c42a85/yadage/worldpopulation/world_population_analysis.html

Washing our bowl
----------------

If you want to bring down the REANA cluster after the testing is over, as well
as delete the minikube virtual machine, we can do:

.. code-block:: console

   $ reana down
   $ minikube delete
