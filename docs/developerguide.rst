.. _developerguide:

Developer guide
===============

This developer guide is meant for software developers who would like to
understand REANA source code and contribute to it.

Local development workflow
--------------------------

REANA cluster is composed of several micro-services with multiple independent
source code repositories. ``reana-dev`` is a helper development script that
facilitates working with multiple repositories for local development and
integration testing purposes.

.. click:: reana.cli:cli
   :prog: reana-dev

You can use ``--help`` option to see the detailed help for each command.

Debugging
---------

In order to debug a REANA component, you first have to install REANA cluster in
the development mode (see
`reana-cluster documentation <http://reana-cluster.readthedocs.io/en/latest/developerguide.html#deploying-latest-master-branch-versions>`_).
Once you have done this, you have to build the image of the component you are
working on in development mode and we restart the corresponding pod:

.. code-block:: console

   $ cd src/reana-server
   $ reana-dev docker-build -t latest -c . -b DEBUG=true
   $ reana-dev kubectl-delete-pod -c .

Let us now introduce `wdb` breakpoint as the first instruction of the
first instruction of the `get_workflows()` function located in
`reana_server/rest/workflows.py`:

.. image:: /_static/setting-the-breakpoint.png

We can check that the code has been in fact updated and make a request to the
component:

.. code-block:: console

   $ kubectl logs --selector=app="server"

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
