.. _userguide:

User guide
==========

This user guide is meant for researchers who would like to structure their data
analysis and run them on REANA cloud.

Reusable analyses
-----------------

Making a research data analysis reproducible basically means to provide
structured "runnable recipes" addressing (1) where is the input data, (2) what
software was used to analyse the data, (3) which computing environments were
used to run the software and (4) which computational steps were taken to run the
analysis. This will permit to instantiate the analysis on the computational
cloud and run the analysis to obtain its (5) output results.

.. _fourquestions:

Four questions
--------------

REANA helps to make the research analysis reproducible by providing a structure
helping to answer the "Four Questions":

1. What is your input data?

   - input data files
   - input parameters
   - live database calls

2. Which code analyses it?

   - custom analysis code
   - analysis frameworks
   - Jupyter notebooks

3. What is your environment?

   - operating system
   - software packages and libraries
   - CPU and memory resources

4. Which steps did you take?

   - simple shell commands
   - complex computational workflows
   - local and/or remote task execution

Let us see step by step on how we could go about making an analysis reproducible
and run it on the REANA platform.

Structure your analysis
-----------------------

It is advised to structure your research data analysis sources to clearly
declare and separate your analysis inputs, code, and outputs. A simple
hypothetical example:

.. code-block:: console

    $ find .
    data/mydata.csv
    code/mycode.py
    docs/mynotes.txt
    results/myplot.png

Note how we put the input data file in the ``data`` directory, the runtime code
that analyses it in the ``code`` directory, the documentation in the ``docs``
directory, and the produced output plots in the ``results`` directory.

Note that this structure is fully optional and you can use any you prefer, or
simply store everything in the same working directory. You can also take
inspiration by looking at several real-life examples in the :ref:`examples`
section of the documentation.

Capture your workflows
----------------------

Now that we have structured our analysis data and code, we have to provide
recipe how to produce final plots.

**Simple analyses**

Let us assume that our analysis is run in two stages, firstly a data filtering
stage and secondly a data plotting stage. A hypothetical example:

.. code-block:: console

    $ python ./code/mycode.py \
        < ./data/mydata.csv > ./workspace/mydata.tmp
    $ python ./code/mycode.py --plot myparameter=myvalue \
        < ./workspace/mydata.tmp > ./results/myplot.png

Note how we call a given sequence of commands to produce our desired output
plots. In order to capture this sequence of commands in a "runnable" or
"actionable" manner, we can write a short shell script ``run.sh`` and make it
parametrisable:

.. code-block:: console

    $ ./run.sh --myparameter myvalue

In this case you will want to use the `Serial
<https://reana-workflow-engine-serial.readthedocs.io/>`_ workflow engine of
REANA. The engine permits to express the workflow as a sequence of commands:

.. code-block:: console

              START
               |
               |
               V
          +--------+
          | filter |  <-- mydata.csv
          +--------+
               |
               | mydata.tmp
               |
               V
          +--------+
          |  plot  |  <-- myparameter=myvalue
          +--------+
               |
               | plot.png
               V
              STOP

Note that you can run different commands in different computing environments,
but they must be run in a linear sequential manner.

The sequential workflow pattern will usually cover only simple computational
workflow needs.

**Complex analyses**

For advanced workflow needs we may want to run certain commands in parallel in a
sort of map-reduce fashion. There are `many workflow systems
<https://github.com/common-workflow-language/common-workflow-language/wiki/Existing-Workflow-systems>`_
that are dedicated to expressing complex computational schemata in a structured
manner. REANA supports several, such as `CWL <http://www.commonwl.org/>`_ and
`Yadage <https://github.com/yadage/yadage>`_.

The workflow systems enable to express the computational steps in the form of
`Directed Acyclic Graph (DAG)
<https://en.wikipedia.org/wiki/Directed_acyclic_graph>`_ permitting advanced
computational scenarios.

.. code-block:: console

                        START
                         |
                         |
                  +------+----------+
                 /       |           \
                /        V            \
          +--------+  +--------+  +--------+
          | filter |  | filter |  | filter |   <-- mydata
          +--------+  +--------+  +--------+
                  \       |       /
                   \      |      /
                    \     |     /
                     \    |    /
                      \   |   /
                       \  |  /
                        \ | /
                      +-------+
                      | merge |
                      +-------+
                          |
                          | mydata.tmp
                          |
                          V
                      +--------+
                      |  plot  |  <-- myparameter=myvalue
                      +--------+
                          |
                          | plot.png
                          V
                         STOP



We pick for example the CWL standard to express our computational steps. We
store the workflow specification in the ``workflow`` directory:

.. code-block:: console

    $ find workflow
    workflow/myinput.yaml
    workflow/myworkflow.cwl
    workflow/step-filter.cwl
    workflow/step-plot.cwl

You will again be able to take inspiration from some real-life examples later in
the :ref:`examples` section of the documentation.


**To pick a workflow engine**

For simple needs, the ``Serial`` workflow engine is the quickest to start with.
For regular needs, ``CWL`` or ``Yadage`` would be more appropriate.

Note that the level of REANA platform support for a particular workflow engine
can differ:

    +----------------+---------------+---------------------+-------------+
    | Engine         | Parametrised? | Parallel execution? | Caching?    |
    +================+===============+=====================+=============+
    | CWL            |      yes      |         yes         |     no(1)   |
    +----------------+---------------+---------------------+-------------+
    | Serial         |      yes      |          no         |    yes      |
    +----------------+---------------+---------------------+-------------+
    | Yadage         |      yes      |         yes         |     no(1)   |
    +----------------+---------------+---------------------+-------------+

    (1) The vanilla workflow system may support the feature, but not when run
        via REANA environment.

**Develop workflow locally**

Now that we have declared our analysis input data and code, as well as captured
the computational steps in a structured manner, we can see whether our analysis
runs in the original computing environment. We can use the helper wrapper
scripts:

.. code-block:: console

    $ run.sh

or use workflow-specific commands, such as ``cwltool`` in case of CWL workflows:

.. code-block:: console

    $ cwltool --quiet --outdir="./results" \
         ./workflow/myworkflow.cwl ./workflow/myinput.yaml

This completes the first step in the parametrisation of our analysis in a
reproducible manner.

Containerise your environment
-----------------------------

Now that we have fully described our inputs and code and the steps to run the
analysis and produce our results, we need to make sure we shall be running the
commands in the same environment. Capturing the environment specifics is
essential to ensure reproducibility, for example the same version of Python we
are using and the same set of pre-installed libraries that are needed for our
analysis.

The environment is encapsulated by means of "containers" such as Docker or
Singularity.

**Using an existing environment**

Sometimes you can use an already-existing container environment prepared by
others. For example ``python:2.7`` for Python programs or
``clelange/cmssw:5_3_32`` for CMS Offline Software framework. In this case you
simply specify the container name and the version number in your workflow
specification and you are good to go. This is usually the case when your code
does not have to be compiled, for example Python scripts or ROOT macros.

Note also REANA offers a set of containers that can server as examples about how
to containerise popular analysis environments such as ROOT (see `reana-env-root6
<https://github.com/reanahub/reana-env-root6>`_), Jupyter (see
`reana-env-jupyter <https://github.com/reanahub/reana-env-jupyter>`_) or an
analysis framework such as AliPhysics (see `reana-env-aliphysics
<https://github.com/reanahub/reana-env-aliphysics>`_).

**Building your own environment**

Other times you may need to build your own container, for example to add a
certain library on top of Python 2.7. This is the most typical use case that
we'll address below.

This is usually the case when your code needs to be compiled, for example C++
analysis.

If you need to create your own environment, this can be achieved by means of
providing a particular ``Dockerfile``:

.. code-block:: console

    $ find environment
    environment/myenv/Dockerfile

    $ less environment/Dockerfile
    # Start from the Python 2.7 base image:
    FROM python:2.7

    # Install HFtools:
    RUN apt-get -y update && \
        apt-get -y install \
           python-pip \
           zip && \
        apt-get autoremove -y && \
        apt-get clean -y
    RUN pip install hftools

    # Mount our code:
    ADD code /code
    WORKDIR /code

You can build this customised analysis environment image and give it some name,
for example ``johndoe/myenv``:

.. code-block:: console

    $ docker build -f environment/myenv/Dockerfile -t johndoe/myenv .

and push the created image to the DockerHub image registry:

.. code-block:: console

    $ docker push johndoe/myenv

**Supporting arbitrary user IDs**

In the Docker container ecosystem, the processes run in the containers by
default use the ``root`` user identity. However, this may not be secure. If
you want to improve the security in your environment you can set up your own
user under which identity the processes will run.

In order for processes to run under any user identity and still be able to
write to shared workspaces, we use a GID=0 technique
`as used by OpenShift <https://docs.openshift.com/container-platform/3.11/creating_images/guidelines.html#openshift-specific-guidelines>`_:

- UID: you can use any user ID you want;
- GID: your should add your user to group with GID=0 (the root group)

This will ensure the writable access to workspace directories managed by the
REANA platform.

For example, you can create the user ``johndoe`` with UID=501 and add the user
to GID=0 by adding the following commands at the end of the previous
``Dockerfile``:

.. code-block:: console

    # Setup user and permissions
    RUN adduser johndoe -u 501 --disabled-password --gecos ""
    RUN usermod -a -G 0 johndoe
    USER johndoe

**Testing the environment**

We now have a containerised image representing our computational environment
that we can use to run our analysis in another replicated environment.

We should test the containerised environment to ensure it works properly, for
example whether all the necessary libraries are present:

.. code-block:: console

    $ docker run -i -t --rm johndoe/myenv /bin/bash
    container> python -V
    Python 2.7.15
    container> python mycode.py < mydata.csv > /tmp/mydata.tmp

**Multiple environments**

Note that various steps of the analysis can run in various environments; the
data filtering step on a big cloud having data selection libraries installed,
the data plotting step in a local environment containing only the preferred
graphing system of choice. You can prepare several different environments for
your analysis if needed.

Write your ``reana.yaml``
-------------------------

We are now ready to tie all the above reproducible elements together. Our
analysis example becomes:

.. code-block:: console

    $ find .
    code/mycode.py
    data/mydata.csv
    docs/mynotes.txt
    environment/myenv/Dockerfile
    workflow/myinput.yaml
    workflow/myworkflow.cwl
    workflow/step-filtering.cwl
    workflow/step-plotting.cwl
    results/myplot.png

There is only thing that remains in order to make it runnable on the REANA
cloud; we need to capture the above structure by means of a ``reana.yaml`` file:

.. code-block:: yaml

    version: 0.4.0
    inputs:
      files:
        - code/mycode.py
        - data/mydata.csv
      parameters:
        myparameter: myvalue
    workflow:
      type: cwl
      file: workflow/myworkflow.cwl
    outputs:
      files:
        - results/myplot.png

This file is used by REANA to instantiate and run the analysis on the cloud.

Declare necessary resources
---------------------------

You can declare other additional runtime dependencies that your workflow needs
for successful operation, such as access to `CVMFS
<https://cernvm.cern.ch/portal/filesystem>`_. This is achieved by means of
providing a ``resources`` clause in ``reana.yaml``. For example:

.. code-block:: yaml

    workflow:
      type: serial
      resources:
        cvmfs:
          - fcc.cern.ch
      specification:
        steps:
          - environment: 'cern/slc6-base'
            commands:
            - ls -l /cvmfs/fcc.cern.ch/sw/views/releases/

Run your analysis on REANA cloud
--------------------------------

We can now download ``reana-client`` command-line utility, configure access to
the remote REANA cloud where we shall run the analysis, and launch it as
follows:

.. code-block:: console

    $ # create new virtual environment
    $ virtualenv ~/.virtualenvs/myreana
    $ source ~/.virtualenvs/myreana/bin/activate
    $ # install REANA client
    $ pip install reana-client
    $ # connect to some REANA cloud instance
    $ export REANA_SERVER_URL=https://reana.cern.ch/
    $ export REANA_ACCESS_TOKEN=XXXXXXX
    $ # create new workflow
    $ reana-client create -n my-analysis
    $ export REANA_WORKON=my-analysis
    $ # upload input code and data to the workspace
    $ reana-client upload ./code ./data
    $ # start computational workflow
    $ reana-client start
    $ # ... should be finished in about a minute
    $ reana-client status
    $ # list workspace files
    $ reana-client ls
    $ # download output results
    $ reana-client download results/plot.png

We are done! Our outputs plot should be located in the ``results`` directory.

Note that you can inspect your analysis workspace by opening `Jupyter notebook interactive sessions
<https://reana-client.readthedocs.io/en/latest/userguide.html#opening-interactive-sessions>`_.

For more information on how to use ``reana-client``, please see `REANA-Client's
Getting started guide
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
- `reana-demo-lhcb-d2pimumu <https://github.com/reanahub/reana-demo-lhcb-d2pimumu/blob/master/README.md>`_ - LHCb rare charm decay search example

Next steps
----------

For more information on how to use ``reana-client``, you can explore
`REANA-Client documentation <https://reana-client.readthedocs.io/>`_.
