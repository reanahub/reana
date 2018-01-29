.. _userguide:

User guide
==========

This user guide is meant for researchers who would like to structure their data
analysis and run them on REANA cloud.

REANA file
----------

It is advised to structure your analysis code using the "inputs", "code",
"outputs", "environments", "workflows" strategy mentioned in :ref:`concepts`.

REANA client
------------

REANA is coming with a convenience ``reana-client`` script that you can install
using ``pip``, for example:

.. code-block:: console

   $ mkvirtualenv reana-client -p /usr/bin/python2.7
   $ pip install reana-client

You can run ``reana-client --help`` to obtain help.

There are several convenient environment variables you can set when working with
``reana-client``:

- ``REANA_SERVER_URL`` Permits to specify to which REANA cloud instance the
  client should connect. For example:

.. code-block:: console

   $ export REANA_SERVER_URL=http://reana.cern.ch

- ``REANA_WORKON`` Permits to specify a concrete workflow ID run for the given
  analysis. (As an alternative to specifying ``--workflow`` in commands.) For
  example:

.. code-block:: console

   $ export REANA_WORKON="57c917c8-d979-481e-ae4c-8d8b9ffb2d10"

The typical usage scenario of ``reana-client`` goes as follows:

.. code-block:: console

   $ reana-client ping
   $ reana-client workflow create
   $ reana-client code upload mycode.py
   $ reana-client inputs upload myinput.csv
   $ reana-client workflow start
   $ reana-client workflow status
   $ reana-client outputs list
   $ reana-client outputs download myresults.png

For more information, please see `reana-client documentation
<https://reana-client.readthedocs.io/>`_.

Examples
--------

There are several REANA-compatible research data analysis examples that
illustrate how to structure the research data analysis and run it on REANA
cloud. Please see :ref:`examples`.

Next steps
----------

For more information, please see `reana-client documentation
<https://reana-client.readthedocs.io/>`_.
