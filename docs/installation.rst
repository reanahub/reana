Installation
===============

.. note::

   In order to instantiate the REANA system a :doc:`backend <backends>` should
   be up and running.

We start by creating a fresh new Python virtual environment which will handle
our `REANA` cluster instantiation:

.. code-block:: console

   $ mkvirtualenv reana

Update ``pip``, ``setuptools`` and ``wheel``:

.. code-block:: console

   $ pip install --upgrade pip setuptools wheel

Install ``reana`` package:

.. code-block:: console

   $ pip install \
        -e 'git+https://github.com/reanahub/reana.git@master#egg=reana'

Start the REANA cluster:

.. code-block:: console

   $ reana init

Once the script finishes, we should use the backend specific command to check
if the components have been created. For instance, when using `Kubernetes` we would
run ``kubectl get pods`` until we get an output as follows:

.. code-block:: console

   $ kubectl get pods
   job-controller-1390584237-0lt03        1/1       Running            0          1m
   message-broker-1410199975-7c5v7        1/1       Running            0          1m
   storage-admin                          1/1       Running            0          1m
   workflow-controller-2689978795-5kzgt   1/1       Running            0          1m
   workflow-monitor-1639319062-q7v8z      1/1       Running            0          1m
   yadage-alice-worker-1624764635-x8z71   1/1       Running            0          1m
   yadage-atlas-worker-2909073811-t9qv3   1/1       Running            0          1m
   yadage-cms-worker-209120003-js5cv      1/1       Running            0          1m
   yadage-lhcb-worker-4061719987-6gpbn    1/1       Running            0          1m
   zeromq-msg-proxy-1617754619-68p7v      1/1       Running            0          1m

Finally, we will be able to check whether the components are actually working:

.. code-block:: console

   $ curl "http://$(reana get reana-workflow-controller)/workflows"
   {
     "workflows": {}
   }
   $ firefox "http://$(reana get reana-workflow-monitor)/helloworld"
   $ curl "http://$(reana get reana-job-controller)/jobs"
   {
     "jobs": {}
   }
