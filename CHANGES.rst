Changes
=======

Version 0.7.4 (2021-07-07)
--------------------------

- Users:
    - Adds support for file listing wildcard matching patterns to ``ls`` command.
    - Adds support for directory download and wildcard matching patterns to ``download`` command.
    - Adds support for specifying ``kubernetes_memory_limit`` for Kubernetes compute backend jobs for CWL, Serial and Yadage workflows.
    - Changes ``list`` command to include deleted workflows by default.
    - Changes ``validate`` command to warn about incorrectly used workflow parameters for each step.
    - Changes ``validate`` command to display more granular workflow validation output.
    - Fixes workflow step job command formatting bug for CWL workflows on HTCondor compute backend.
    - Fixes ``validate`` command output for verifying environment image UID values.
    - Fixes ``upload_to_server()`` Python API function to silently skip uploading in case of none-like inputs.
    - Fixes ``validate`` command for environment image validation to not test repetitively the same image found in different steps.
- Administrators:
    - Adds support for Kubernetes 1.21.
    - Adds configuration environment variable to set default job memory limits for the Kubernetes compute backend (``REANA_KUBERNETES_JOBS_MEMORY_LIMIT``).
    - Adds configuration environment variable to set maximum custom memory limits that users can assign to their jobs for the Kubernetes compute backend (``REANA_KUBERNETES_JOBS_MAX_USER_MEMORY_LIMIT``).
    - Changes HTCondor compute backend to 8.9.11 and `myschedd` package and configuration to latest versions.
    - Fixes Kubernetes job log capture to include information about failures caused by external factors such as out-of-memory situations (`OOMKilled`).
- Developers:
    - Adds new functions to serialise/deserialise job commands between REANA components.
    - Changes client dependencies to unpin six so that client may be installed in more contexts.
    - Changes cluster dependencies to remove click and pins several dependencies.
    - Changes ``reana_ready()`` function location to REANA-Server.

Version 0.7.3 (2021-03-24)
--------------------------

- Users:
    - Adds ``reana-client validate`` options to detect possible issues with workflow input parameters and environment images.
    - Fixes problem with failed jobs being reported as still running in case of network problems.
    - Fixes job command encoding issues when dispatching jobs to HTCondor and Slurm backends.
- Administrators:
    - Adds new configuration to toggle Kubernetes user jobs clean up.
      (``REANA_RUNTIME_KUBERNETES_KEEP_ALIVE_JOBS_WITH_STATUSES`` in ``components.reana_workflow_controller.environment``)
    - Improves platform resilience.
- Developers:
    - Adds new command-line options to ``reana-dev run-example`` command allowing full parallel asynchronous execution of demo examples.
    - Adds default configuration for developer deployment mode to keep failed workflow and job pods for easier debugging.
    - Changes job status consumer communications to improve overall platform resilience.

Version 0.7.2 (2021-02-04)
--------------------------

- Administrators:
    - Adds support for deployments on Kubernetes 1.20 clusters.
    - Adds deployment option to disable user email confirmation step after sign-up.
      (``REANA_USER_EMAIL_CONFIRMATION`` in ``components.reana_server.environment``)
    - Adds deployment option to disable user sign-up feature completely.
      (``components.reana_ui.hide_signup``)
    - Adds deployment option to display CERN Privacy Notice for CERN deployments.
      (``components.reana_ui.cern_ropo``)
- Developers:
    - Adds support for Python 3.9.
    - Fixes minor code warnings.
    - Changes CI system to include Python flake8 and Dockerfile hadolint checkers.

Version 0.7.1 (2020-11-10)
--------------------------

- Users:
    - Adds support for specifying ``htcondor_max_runtime`` and ``htcondor_accounting_group`` for HTCondor compute backend jobs.
    - Fixes restarting of Yadage and CWL workflows.
    - Fixes REANA <-> GitLab synchronisation for projects having additional external webhooks.
    - Changes ``ping`` command output to include REANA client and server version information.
- Developers:
    - Fixes conflicting ``kombu`` installation requirements by requiring Celery version 4.
    - Changes ``/api/you`` endpoint to include REANA server version information.
    - Changes continuous integration platform from Travis CI to GitHub Actions.

Version 0.7.0 (2020-10-21)
--------------------------

- Users:
    - Adds new ``restart`` command to restart previously run or failed workflows.
    - Adds option to ``logs`` command to filter job logs according to compute backend, docker image, job status and step name.
    - Adds option to specify operational options in the ``reana.yaml`` of the workflow.
    - Adds option to specify unpacked Docker images as workflow step requirement.
    - Adds option to specify Kubernetes UID for jobs.
    - Adds support for VOMS proxy as a new authentication method.
    - Adds support for pulling private Docker images.
    - Adds pagination on the workflow list and workflow detailed web interface pages.
    - Adds user profile page to the web interface.
    - Adds page refresh button to workflow detailed page.
    - Adds local user web forms for sign-in and sign-up functionalities for local deployments.
    - Fixes user experience by preventing dots as part of the workflow name to avoid confusion with restart runs.
    - Fixes workflow specification display to show runtime parameters.
    - Fixes file preview functionality experience to allow/disallow certain file formats.
    - Changes Yadage workflow engine to version 0.20.1.
    - Changes CERN HTCondor compute backend to use the new ``myschedd`` connection library.
    - Changes CERN Slurm compute backend to improve job status detection.
    - Changes documentation to move large parts to `docs.reana.io <http://docs.reana.io>`_.
    - Changes ``du`` command output format.
    - Changes ``logs`` command to enhance formatting using marks and colours.
    - Changes ``ping`` command to perform user access token validation.
    - Changes ``diff`` command to improve output formatting.
    - Changes defaults to accept both ``reana.yaml`` and ``reana.yml`` filenames.
    - Changes from Bravado to requests to improve download performance.
    - Changes file loading to optimise CLI performance.
- Administrators:
    - Adds Helm chart and switches to Helm-based deployment technique instead of using now-deprecated ``reana-cluster``.
    - Adds email notification service to inform administrators about system health.
    - Adds announcement configuration option to display any desired text on the web UI.
    - Adds pinning of all Python dependencies allowing to easily rebuild component images at later times.
    - Adds support for local user management and web forms for sign-in and sign-up functionalities.
    - Adds support for database upgrades using Alembic.
    - Changes installation procedures to move database initialisation and admin creation after Helm installation.
    - Changes service exposure to stop exposing unused Invenio-Accounts views.
    - Changes runtime job instantiation into the configured runtime namespace.
    - Changes CVMFS to be read-only mount.
- Developers:
    - Adds several new ``reana-dev`` commands to help with merging, releasing, unit testing.
    - Changes base image to use Python 3.8 for all REANA cluster components.
    - Changes pre-requisites to node version 12 and latest npm dependencies.
    - Changes back-end code formatting to respect ``black`` coding style.
    - Changes front-end code formatting to respect updated ``prettier`` version coding style.
    - Changes test strategy to start PostgreSQL DB container to run tests locally.
    - Changes auto-generated component documentation to single-page layout.

Version 0.6.1 (2020-06-09)
--------------------------

- Administrators:
    - Fixes installation troubles for REANA 0.6.x release series by pinning several dependencies.
    - Upgrades REANA-Commons package to latest Kubernetes Python client version.
    - Amends documentation for `minikube start` to include VirtualBox hypervisor explicitly.

Version 0.6.0 (2019-12-27)
--------------------------

- Users:
    - Adds support for HTCondor compute backend for all workflow engines (CWL, Serial, Yadage).
    - Adds support for Slurm compute backend for all workflow engines (CWL, Serial, Yadage).
    - Allows to run hybrid analysis pipelines where different parts of the workflow can run on different compute backends (HTCondor, Kubernetes, Slurm).
    - Adds support for Kerberos authentication mechanism for user workflows.
    - Introduces user secrets management commands ``secrets-add``, ``secrets-list`` and ``secrets-delete``.
    - Fixes ``upload`` command behaviour for uploading very large files.
    - Upgrades CWL workflow engine to 1.0.20191022103248.
    - Upgrades Yadage workflow engine to 0.20.0 with Packtivity 0.14.21.
    - Adds support for Python 3.8.
    - See additional changes in `reana-client 0.6.0 release notes <https://reana-client.readthedocs.io/en/latest/changes.html#version-0-6-0-2019-12-27>`_.
- Administrators:
    - Upgrades to Kubernetes 1.16 and moves Traefik installation to Helm 3.0.0.
    - Creates a new Kubernetes service account for REANA with appropriate permissions.
    - Makes database connection details configurable so that REANA can connect to databases external to the cluster.
    - Autogenerates deployment secrets if not provided by administrator at cluster creation time.
    - Adds an interactive mode on cluster initialisation to allow providing deployment secrets.
    - Adds CERN specific Kerberos configuration files and CERN EOS storage support.
    - See additional changes in `reana-cluster 0.6.0 release notes <https://reana-cluster.readthedocs.io/en/latest/changes.html#version-0-6-0-2019-12-27>`_.
- Developers:
    - Modifies the batch workflow runtime pod creation including an instance of job controller running alongside workflow engine using the sidecar pattern.
    - Adds generic job manager class and provides example classes for CERN HTCondor and CERN Slurm clusters.
    - Provides user secrets to the job container runtime tasks.
    - Adds sidecar container to the Kubernetes job pod if Kerberos authentication is required.
    - Refactors job monitoring using the singleton pattern.
    - Enriches ``make`` behaviour for developer-oriented installations with live code reload changes and debugging.
    - Enriches ``git-status`` component status reporting for developers.
    - See additional changes in `individual REANA 0.6.0 platform components <https://reana.readthedocs.io/en/latest/administratorguide.html#components>`_.

Version 0.5.0 (2019-04-24)
--------------------------

- Users:
    - Allows to explore workflow results by running interactive Jupyter notebook sessions on the workspace files.
    - Allows to declare computing resources needed for workflow runs, such as access to CVMFS repositories.
    - Improves ``reana-client`` command-line client with new options to stop workflows, diff workflows, move and remove files.
    - Upgrades CWL engine to 1.0.20181118133959.
    - See additional changes in `reana-client 0.5.0 release notes <https://reana-client.readthedocs.io/en/latest/changes.html#version-0-5-0-2019-04-24>`_.
- Administrators:
    - Upgrades to Kubernetes 1.14, Helm 2.13 and Minikube 1.0.
    - Separates cluster infrastructure pods from runtime workflow engine pods that will be created by workflow controller.
    - Introduces configurable CVMFS and CephFS shared volume mounts.
    - Adds support for optional HTTPS protocol termination.
    - Introduces incoming workflow queue for additional safety in case of user storms.
    - Makes infrastructure pods container image slimmer to reduce the memory footprint.
    - See additional changes in `reana-cluster 0.5.0 release notes <https://reana-cluster.readthedocs.io/en/latest/changes.html#version-0-5-0-2019-04-24>`_.
- Developers:
    - Enhances development process by using git-submodule-like behaviour for shared components.
    - Introduces simple Makefile for (fast) local testing and (slow) nightly building purposes.
    - Centralises logging level and common Celery tasks.
    - Adds helpers for test suite fixtures and improves code coverage.
    - See additional changes in `individual REANA 0.5.0 platform components <https://reana.readthedocs.io/en/latest/administratorguide.html#components>`_.

Version 0.4.0 (2018-11-07)
--------------------------

- Uses common OpenAPI client in communications between workflow engines and job
  controller.
- Improves AMQP re-connection handling.
- Enhances test suite and increases code coverage.
- Changes license to MIT.

Version 0.3.0 (2018-09-27)
--------------------------

- Introduces new Serial workflow engine for simple sequential workflow needs.
- Enhances progress reporting for CWL, Serial and Yadage workflow engines.
- Simplifies ``reana-client`` command set and usage scenarios.
- Introduces multi-user capabilities with mandatory access tokens.
- Adds support for multi-node clusters using shared CephFS volumes.
- Adds support for Kubernetes 1.11, Minikube 0.28.2.
- Upgrades CWL workflow engine to use latest ``cwltool`` version.
- Fixes several bugs such as binary file download with Python 3.

Version 0.2.0 (2018-04-23)
--------------------------

- Adds support for Common Workflow Language workflows.
- Adds support for persistent user-selected workflow names.
- Enables file and directory input uploading using absolute paths.
- Enriches ``reana-client`` and ``reana-cluster`` command set.
- Reduces verbosity level for commands and improves error messages.

Version 0.1.0 (2018-01-30)
--------------------------

- Initial public release.

.. admonition:: Please beware

   Please note that REANA is in an early alpha stage of its development. The
   developer preview releases are meant for early adopters and testers. Please
   don't rely on released versions for any production purposes yet.
