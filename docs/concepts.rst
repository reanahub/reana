.. _concepts:

Concepts
========

Reusable analyses
-----------------

The revalidation, reinterpretation and reuse of research data analyses requires
having access not only to the original experimental datasets and the analysis
software, but also to the operating system environment and the computational
workflow steps which were used by the researcher to produce the original
scientific results in the first place.

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

   - simple linear commands
   - complex workflows
   - local or remote workflow step execution

Analysis structure
------------------

It is advised to structure your analysis code using the "inputs", "code",
"outputs", "environments", "workflows" strategy. For example:

.. code-block:: console

   $ ls -l .
   inputs/mydata.csv
   code/mycode.py
   environments/myubuntu/Dockerfile
   workflow/myworkflow.cwl
   outputs/myresult1.png
   outputs/myresult2.png

This is not mandatory, but we believe that it (i) helps to think about writing
analysis code in a reusable-friendly manner, as well as (ii) simplifies working
with REANA platform as well.

REANA file
----------

The analysis structured in the above manner can be described by means of a YAML
file that specifies information about analysis inputs, code, environments,
workflow and the desired outputs. Here is one example:

.. code-block:: yaml

    version: 0.1.0
    metadata:
      authors:
      - John Doe <john.doe@example.org>
      - Jane Doe <ane.doe@example.org>
      title: My analysis
      date: 18 January 2017
      repository: https://github.com/johndoe/myanalysis
    code:
      files:
      - code/mycode.py
    inputs:
      files:
        - inputs/mydata.csv
      parameters:
        myparameter1: myvalue1
        myparameter2: myvalue2
        inputfile: inputs/mydata.csv
        mycode: code/mycode.py
    outputs:
      files:
      - outputs/myresult1.png
      - outputs/myresult2.png
    environments:
      - type: docker
        image: johndoe/myubuntu:1.1
    workflow:
      type: cwl
      file: workflow/myworkflow.cwl

REANA platform
--------------

Users can use ``reana-client`` command line client that talks to
``reana-server`` REST API sending commands to REANA cloud. The REANA cloud can
be deployed using ``reana-cluster`` command line client. The REANA cluster
consists of several micro-service components that manage and run user-supplied
computational workflows. Together, the (local) REANA client and (remote) REANA
cluster constitute the REANA reusable analysis platform.
