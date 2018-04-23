.. _userguide:

User guide
==========

This user guide is meant for researchers who would like to structure their data
analysis and run them on REANA cloud.

Reusable analyses
-----------------

The revalidation, reinterpretation and reuse of research data analyses requires
having access not only to the original experimental datasets and the analysis
software, but also to the operating system environment and the computational
workflow steps which were used by the researcher to produce the original
scientific results in the first place.

.. _fourquestions:

Four questions
--------------

REANA helps to make the research analysis reusable by providing a structure
helping to answer the "Four Questions":

1. What is your input data?

   - input files
   - input parameters
   - live database calls

2. What is your environment?

   - operating systems
   - software packages and libraries
   - CPU and memory resources

3. Which code analyses it?

   - analysis frameworks
   - custom analysis code
   - Jupyter notebooks

4. Which steps did you take?

   - simple shell commands
   - complex computational workflows
   - local or remote workflow step execution

Structure your analysis
-----------------------

It is advised to structure your research data analysis repository into "inputs",
"code", "environments", "workflows" directories, following up the model of the
:ref:`fourquestions`:

.. code-block:: console

   $ ls .
   code/mycode.py
   docs/mynotes.txt
   inputs/mydata.csv
   environments/mypython/Dockerfile
   workflow/myworkflow.cwl
   outputs/
   reana.yaml

The ``reana.yaml`` describing this structure look as follows:

.. code-block:: yaml

    version: 0.2.0
    code:
      files:
      - code/mycode.py
    inputs:
      files:
        - inputs/mydata.csv
      parameters:
        myparameter: myvalue
    environments:
      - type: docker
        image: johndoe/mypython:1.0
    workflow:
      type: cwl
      file: workflow/myworkflow.cwl
    outputs:
      files:
      - outputs/myplot.png

Note that this structure is fully optional and you can simply store everything
in the same working directory. You can see some real-life :ref:`examples` for
inspiration.

Use REANA client
----------------

REANA is coming with a convenience ``reana-client`` script that you can install
using ``pip``, for example:

.. code-block:: console

   $ # install reana-client
   $ mkvirtualenv reana-client -p /usr/bin/python2.7
   $ pip install reana-client

You can run ``reana-client --help`` to obtain help.

There are several convenient environment variables you can set when working with
``reana-client``:

- ``REANA_SERVER_URL`` Permits to specify to which REANA cloud instance the
  client should connect. For example:

.. code-block:: console

   $ export REANA_SERVER_URL=http://reana.cern.ch

- ``REANA_WORKON`` Permits to specify a concrete workflow run for the given
  analysis. (As an alternative to specifying ``--workflow`` name in commands.)
  For example:

.. code-block:: console

   $ export REANA_WORKON=myanalysis.17

The typical usage scenario of ``reana-client`` goes as follows:

.. code-block:: console

   $ # create new workflow
   $ export REANA_WORKON=$(reana-client workflow create)
   $ # upload runtime code and inputs
   $ reana-client code upload ./code/*
   $ reana-client inputs upload ./inputs/*
   $ # start workflow and check progress
   $ reana-client workflow start
   $ reana-client workflow status
   $ # download outputs
   $ reana-client outputs list
   $ reana-client outputs download myplot.png

For more information, please see `REANA-Client's Getting started guide
<http://reana-client.readthedocs.io/en/latest/gettingstarted.html>`_.

.. _examples:

Examples
--------

This section lists several REANA-compatible research data analysis examples that
illustrate how to a typical research data analysis can be packaged in a
REANA-compatible manner to be reusable even several years after original results
were published.

Hello world
~~~~~~~~~~~

A "hello world" application example that illustrates how a simple command can be
run on the REANA cloud.

- sources: `<https://github.com/reanahub/reana-demo-helloworld/>`_
- documentation: `<https://github.com/reanahub/reana-demo-helloworld/blob/master/README.rst>`_

Jupyter notebook
~~~~~~~~~~~~~~~~

A "world population" research data analysis example that illustrates how to
package an Jupyter Notebook type of analysis with a set of input and output
files.

- sources: `<https://github.com/reanahub/reana-demo-worldpopulation/>`_
- documentation: `<https://github.com/reanahub/reana-demo-worldpopulation/blob/master/README.rst>`_

ROOT and RooFit
~~~~~~~~~~~~~~~

A simplified particle physics analysis example using the `RooFit
<https://root.cern.ch/roofit>`_ package of the `ROOT <https://root.cern.ch/>`_
framework. The example mimics a typical particle physics analysis where the
signal and background data is processed and fitted against a model.

- sources: `<https://github.com/reanahub/reana-demo-root6-roofit/>`_
- documentation: `<https://github.com/reanahub/reana-demo-root6-roofit/blob/master/README.rst>`_

Next steps
----------

For more information, you can explore `REANA-Client documentation
<https://reana-client.readthedocs.io/>`_.
