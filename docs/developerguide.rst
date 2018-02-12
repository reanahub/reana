.. _developerguide:

Developer guide
===============

This developer guide is meant for software developers who would like to
understand REANA source code and contribute to it.

Debugging
---------

In order to debug a REANA component, you first have to install REANA cluster in
the development mode (see
`reana-cluster documentation <http://reana-cluster.readthedocs.io/en/latest/developerguide.html#deploying-latest-master-branch-versions>`_).
Once you have done this, you have to build the image of the component you are
working on in development mode and we restart the corresponding pod:

.. code-block:: console

   $ cd src/reana-server
   $ # if we are not connected to the minikube docker daemon we should do it
   $ eval "$(minikube docker-env)"
   $ docker build . --build-arg DEBUG=true -t reanahub/reana-server:latest
   $ kubectl delete pod --selector=app="server"

Let us now introduce `wdb` breakpoint as the first instruction of the
first instruction of the `get_analyses()` function located in
`reana_server/rest/analyses.py`:

.. image:: /_static/setting-the-breakpoint.png

We can check that the code has been in fact updated and make a request to the
component:

.. code-block:: console

   $ kubectl logs --selector=app="server"

    * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
    * Restarting with stat
    * Debugger is active!
    * Debugger PIN: 310-304-952
   172.17.0.1 - - [15/Feb/2018 12:43:49] "GET /api/ping HTTP/1.1" 200 -
    * Detected change in '/code/reana_server/rest/analyses.py', reloading
    * Restarting with stat
    * Debugger is active!
    * Debugger PIN: 310-304-952
   $ curl "192.168.99.100:30659/api/analyses?organization=default&user=00000000-0000-0000-0000-000000000000"

After doing that we can go to the `wdb` dashboard (you can get ``wdb`` address
using `reana-cluster get wdb <http://reana-cluster.readthedocs.io/en/latest/cliapi.html#reana-cluster-get>`_).

.. image:: /_static/wdb-active-sessions.png

And finally select the debugging session.

.. image:: /_static/wdb-debugging-ui.png


**Limitations**

It is not possible to get live code updates in workflow engine components since
celery option `--autoreload` doesn't work and it is deprecated. To debug
`celery` right now:

* Set breakpoint: ``import wdb; wdb.set_trace()``
* Kill the workflow engine container: ``kubectl delete pod cwl-default-worker-2461563162-r4hgg``
