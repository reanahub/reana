.. _gitlab:

GitLab integration
==================

Improve your experience using REANA by using the GitLab integration.
There are two solutions to integrate REANA and GitLab. The first one uses
`GitLab CI/CD <https://gitlab.cern.ch/help/ci/README.md>`_, GitLab's built-in Continuous Integration, Continuous Deployment, Continuous Delivery toolset.
While the second is a GitLab application that can be authorized to execute your GitLab projects on REANA.
This document will give an overview of both integration solutions and provide a tutorial on how to configure them.

The GitLab CI/CD solution
-------------------------

This solution connects REANA to the existing GitLab CI/CD toolset.
Most of the configuration is takes place on the `.gitlab-ci.yml` file, a `file <https://gitlab.cern.ch/help/ci/yaml/README.md>`_
that defines the steps to be executed by the GitLab CI/CD runner.
Another important configuration step is the definition of the REANA `environment variables on GitLab <https://gitlab.cern.ch/help/ci/variables/README#variables>`_.
This variables will allow the GitLab CI/CD runner to authorize its access to a REANA cluster and run the analysis there.


**Setting the environment variables**

The CI environment variables have to be set via the GitLab web interface.
After the users have selected the project which will execute on REANA,
they need to select the options `Settings > CI/CD` on the project's sidebar panel.

.. image:: /_static/gitlab-ci-cd-variables.png

Then, expand the **Variables** section to add the new environment variables.

.. image:: /_static/gitlab-ci-cd-variables2.png

There are two variables to add to this section. The `REANA_SERVER_URL` and the `REANA_ACCESS_TOKEN`.
The former is the URL of the REANA cluster which will run the analysis and the latter is the user's
access token to that cluster.

.. image:: /_static/gitlab-ci-cd-variables3.png

After adding the variables' key and values the user should save them by clicking on the `Save variables` button.

**Configuring the .gitlab-ci.yml file**

The GitLab CI/CD runner needs to have instructions on how to execute the project.
That's where the `.gitlab-ci.yml` file comes in. It describes the steps necessary to execute your analysis on REANA from a client machine,
on this case the client machine is the GitLab CI/CD runner.

The `.gitlab-ci.yml` file must be on the project's root.

.. image:: /_static/gitlab-ci-cd-yaml.png

The main parameters of the GitLab CI/CD YAML file are **image**, **script**, and the section **artifacts**.
  - The `image` parameter specifies the docker image required to run the script.
  - The `script` parameter describes the commands that the pipeline should execute.
  - The `artifacts` section tells GitLab what it should do with the output files.

.. image:: /_static/gitlab-ci-cd-yaml2.png

**Example**

.. code-block:: yaml

  reana:
    image: "python:3"
    script:
        # install reana-client
        - pip install reana-client

        # create the workflow
        - reana-client create -n $CI_PROJECT_NAME

        # export workflow name
        - export REANA_WORKON=$CI_PROJECT_NAME

        # upload analysis' code and input files
        - reana-client upload <code_path> <data_path>

        # execute the workflow
        - reana-client start --follow

        # download output files
        - reana-client download <output_files_path>

        artifacts:
            paths:
                - <output_files_path>
            expire_in: <expiration_period>
            when: on_success

In the example above the user names the pipeline "reana" and tells GitLab CI that it should run on a Python 3 container.
As for the script, it begins by installing `reana-client <https://reana-client.readthedocs.io>`_,
then it creates a new workflow with the same name as the GitLab project name.
It exports an environment variable to let REANA know the workflow's name. Then, it uploads the code and data necessary to the workflow execution.
**Here, it is important to point out that the paths used in this command are relative to the GitLab project structure**.

After the code and data have been uploaded the workflow can be started. Note that the start command contains the flag **\-\-follow**.
This is a crucial addition as it makes the client, and the GitLab CI/CD runner, follow the workflow execution until it finishes.
The last script command downloads the outputs from the analysis into the GitLab CI/CD runner.

**Artifacts**

The artifacts section deals with the execution output files. It specifies the path of the newly downloaded output files
and defines for how long those files should be kept on the GitLab CI/CD runner. However, via the GitLab interface,
the user can browse the artifacts and decide whether to download them or keep them available for longer.

.. image:: /_static/gitlab-ci-cd-artifacts.png

The REANA client, which is executing inside the GitLab CI/CD runner, also logs the job execution and
outputs the file download URLs after the job is finished. This is yet another option to retrieve the analysis artifacts.


The REANA application solution
------------------------------