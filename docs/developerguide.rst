.. _developerguide:

Developer guide
===============

This developer guide is meant for software developers who would like to
understand REANA source code and contribute to it.


Local development workflow
--------------------------

REANA cluster is composed of several micro-services with multiple independent
source code repositories.

The main source code repository contains a ``Makefile`` which allows you to
quickly clone all the necessary repositories and kick-start your REANA platform
developments locally.

You can simply type ``make`` to see the available options and usage scenarios.

.. program-output:: cd .. && make help
   :shell:

In addition, REANA comes with a ``reana-dev`` helper development script that
simplifies working with multiple repositories during local development and
integration testing. You can use ``--help`` option to see the detailed usage
instructions.

.. click:: reana.cli:cli
   :prog: reana-dev

Debugging
---------

In order to debug a REANA component, you first have to mount REANA's source
code into Minikube's `/code` directory and then build and re-deploy in
development mode:

.. code-block:: console

   $ minikube mount $(pwd)/..:/code
   $ CLUSTER_CONFIG=dev make build deploy

Let us now introduce `wdb` breakpoint as the first instruction of the
first instruction of the `get_workflows()` function located in
`reana_server/rest/workflows.py`:

.. image:: /_static/setting-the-breakpoint.png

We can check that the code has been in fact updated and make a request to the
component:

.. code-block:: console

   $ kubectl logs --selector=app="server" -c server

   DB Created.
    * Serving Flask app "/code/reana_server/app.py" (lazy loading)
    * Environment: production
    WARNING: Do not use the development server in a production environment.
    Use a production WSGI server instead.
    * Debug mode: on
    * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
    * Restarting with stat
    * Debugger is active!
    * Debugger PIN: 221-564-335

   $ curl $REANA_SERVER_URL/api/workflows?access_token=$REANA_ACCESS_TOKEN

After doing that we can go to the `wdb` dashboard:

.. code-block:: console

   $ firefox http://`minikube ip`:31984


.. image:: /_static/wdb-active-sessions.png

And finally select the debugging session.

.. image:: /_static/wdb-debugging-ui.png

Port forwarding
---------------

If you ever need to access one specific microservice via HTTP there is a Kubernetes
command that can help. The ``port-forward`` command connects a local port on the
machine to a port on a Kubernetes pod. It directs the traffic reaching the local
port to the pod port through an HTTP connection. Example:

.. code-block:: console

    $ kubectl port-forward --address 0.0.0.0 <pod_name> <local_port>:<pod_port>

The ``--address`` flag defines the local IP address to listen on. Using ``0.0.0.0``
makes the connection listen to all local IP addresses.
