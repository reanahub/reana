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

    version: 0.3.0
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
   $ mkvirtualenv reana-client
   $ pip install reana-client

You can run ``reana-client --help`` to obtain help.

There are several convenient environment variables you can set when working with
``reana-client``:

- ``REANA_SERVER_URL`` Permits to specify to which REANA cloud instance the
  client should connect. For example:

.. code-block:: console

   $ export REANA_SERVER_URL=http://reana.cern.ch

- ``REANA_ACCESS_TOKEN`` Identifies the current user when performing
  protected actions.

.. code-block:: console

   $ export REANA_ACCESS_TOKEN=XXXXXXX

- ``REANA_WORKON`` Permits to specify a concrete workflow run for the given
  analysis. (As an alternative to specifying ``--workflow`` name in commands.)
  For example:

.. code-block:: console

   $ export REANA_WORKON=myanalysis.17

The typical usage scenario of ``reana-client`` goes as follows:

.. code-block:: console

   $ # create new workflow
   $ export REANA_WORKON=$(reana-client create)
   $ # upload runtime code and inputs
   $ reana-client upload
   $ # start workflow and check progress
   $ reana-client start
   $ reana-client status
   $ # list files
   $ reana-client list
   $ # download outputs
   $ reana-client download myplot.png

For more information, please see `REANA-Client's Getting started guide
<http://reana-client.readthedocs.io/en/latest/gettingstarted.html>`_.

.. _examples:

Examples
--------

This section lists several REANA-compatible research data analysis examples that
illustrate how to a typical research data analysis can be packaged in a
REANA-compatible manner to facilitate its future reuse.

- `reana-demo-helloworld <https://github.com/reanahub/reana-demo-helloworld/blob/master/README.rst>`_ - a simple "hello world" example
- `reana-demo-worldpopulation <https://github.com/reanahub/reana-demo-worldpopulation/>`_ - a parametrised Jupyter notebook example
- `reana-demo-root6-roofit <https://github.com/reanahub/reana-demo-root6-roofit/>`_ - a simplified ROOT RooFit physics analysis example
- `reana-demo-alice-lego-train-test-run <https://github.com/reanahub/reana-demo-alice-lego-train-test-run/blob/master/README.rst>`_ - ALICE experiment analysis train test run and validation
- `reana-demo-atlas-recast <https://github.com/reanahub/reana-demo-atlas-recast/blob/master/README.rst>`_ - ATLAS collaboration production software stack example recasting an analysis
- `reana-demo-bsm-search <https://github.com/reanahub/reana-demo-bsm-search/blob/master/README.rst>`_ - a typical BSM search example with complex particle physics workflows
- `reana-demo-cms-h4l <https://github.com/reanahub/reana-demo-cms-h4l/blob/master/README.rst>`_ - CMS Higgs-to-four-leptons open data analysis example
- `reana-demo-lhcb-d2pimumu <https://github.com/reanahub/reana-demo-lhcb-d2pimumu/blob/master/README.rst>`_ - LHCb rare charm decay search example

Next steps
----------

For more information, you can explore `REANA-Client documentation
<https://reana-client.readthedocs.io/>`_.
