Changes
=======

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
