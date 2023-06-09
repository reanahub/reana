Changes
=======

Version 0.9.1 (UNRELEASED)
--------------------------

- Administrators:
    - Adds new configuration option ``interactive_sessions.maximum_inactivity_period`` to set a limit in days for the maximum inactivity period of interactive sessions after which they will be closed.
    - Adds new configuration option ``interactive_sessions.cronjob_schedule`` to set how often interactive session cleanup should be performed.
    - Adds support for Kubernetes clusters 1.26, 1.27.
    - Adds new configuration option ``ingress.extra`` to define extra Ingress resources, in order to support redirecting HTTP requests to HTTPS with traefik v2 version.
    - Adds new configuration option ``ingress.tls.hosts`` to define hosts that are present in the TLS certificate, in order to support cert-manager's automatic creation of certificates.
    - Adds new configuration option ``notifications.email_config.smtp_ssl`` to use SSL when connecting to the SMTP email server.
    - Adds new configuration option ``notifications.email_config.smtp_starttls`` to use the STARTTLS command to enable encryption after connecting to the SMTP email server.
    - Changes uWSGI configuration to add vacuuming of generated files and sockets.
    - Fixes uWSGI memory consumption on systems with very high allowed number of open files.
    - Fixes cronjob failures due to database connection issues when REANA is deployed with non-default namespace or prefix.
    - Fixes ``ingress.enabled`` option to correctly enable or disable the creation of Ingresses.
    - Adds new configuration options ``login`` and ``secrets.login`` for configuring Keycloak SSO login with third-party authentication services.
- Developers:
    - Fixes ``cluster-deploy`` and ``cluster-undeploy`` commands when using custom instance name or kubernetes namespace.

Version 0.9.0 (2023-01-26)
--------------------------

- Users:
    - Adds support for Rucio authentication for workflow jobs.
    - Adds support for Kerberos authentication for workflow orchestration.
    - Adds support for specifying ``slurm_partition`` and ``slurm_time`` for Slurm compute backend jobs.
    - Adds support for XRootD remote file locations in Snakemake workflow specification definitions.
    - Adds support for Python 3.11.
    - Adds Launch on REANA page allowing the submission of workflows via badge-clicking.
    - Adds notifications to inform users when critical levels of quota usage is reached.
    - Adds 404 Not Found error page.
    - Adds tab titles to all the pages.
    - Adds the ``REANA_WORKSPACE`` environment variable to jupyter notebooks and terminals.
    - Adds option to sort workflows by most disk and cpu quota usage to the workflow list endpoint.
    - Adds support for specifying and listing workspace file retention rules.
    - Adds support for ``.gitignore`` and ``.reanaignore`` to specify files that should not be uploaded to REANA.
    - Adds ``retention-rules-list`` command to list the retention rules of a workflow.
    - Changes REANA specification to allow specifying ``retention_days`` for the workflow.
    - Changes default Slurm partition to ``inf-short``.
    - Changes GitLab integration to also retrieve user's projects that are in groups and subgroups.
    - Changes the workflow-details page to show the logs of the workflow engine.
    - Changes the workflow-details page to show file sizes in a human-readable format.
    - Changes the workflow-details page to show the workspace's retention rules.
    - Changes the workflow-details page to show the duration of the workflow's jobs.
    - Changes the workflow-details page to display a label of the workflow launcher URL remote origin.
    - Changes the workflow-details page to periodically refresh the content of the page.
    - Changes the workflow-details page to refresh after the deletion of a workflow.
    - Changes the workflow-list page to add a way to hide deleted workflows.
    - Changes the workflow-list page to add new workflows sorting options by most used disk and cpu quota.
    - Changes the deletion of a workflow to always clean up the workspace and to update the user disk quota usage.
    - Changes the CWD of jupyter's terminals to the directory of the workflow's workspace.
    - Changes percentage ranges used to calculate the health status of user resource quota usage.
    - Changes ``create`` and ``restart`` commands to always upload the REANA specification file.
    - Changes ``delete`` command to always delete the workflow's workspace.
    - Changes ``delete_workflow`` Python API function to always delete the workflow's workspace.
    - Changes ``download`` command to add the possibility to write files to the standard output via ``-o -`` option.
    - Changes ``list`` command to hide deleted workflows by default.
    - Changes ``list`` command to allow displaying deleted workflows via ``--all`` and ``--show-deleted-runs`` options.
    - Changes ``list`` and ``status`` commands to allow displaying the duration of workflows with the ``--include-duration`` option.
    - Changes ``mv`` command to allow moving files while a workflow is running.
    - Changes ``upload`` command to prevent uploading symlinks.
    - Changes ``validation --environment`` command to use Docker registry v2 APIs to check that a Docker image exists in DockerHub.
    - Fixes ``list`` command to highlight the workflow specified in ``REANA_WORKON`` correctly.
    - Fixes ``secrets-delete`` command error message when deleting non existing secrets.
    - Fixes ``start`` command to report failed workflows as errors.
    - Fixes ``start`` and ``run`` commands to correctly follow the execution of the workflow until termination.
    - Fixes ``status`` command to respect output format provided by the ``--format`` option.
    - Fixes ``upload`` command to report when input directories are listed under the ``files`` section in the REANA specification file and vice versa.
    - Fixes ``validate --environment`` command to detect illegal whitespace characters in Docker image names.
    - Fixes Kerberos authentication for long-running workflows by renewing the Kerberos ticket periodically.
    - Fixes status reporting for failed CWL and Snakemake jobs that were incorrectly considered successful.
    - Fixes redirection chain for non-signed-in CERN SSO users to access the desired target page after sign-in.
    - Fixes the ordering by size of the files showed in the ``Workspace`` tab of the workflow-details page.
    - Fixes CERN OIDC authentication to possibly allow eduGAIN and social login users.
    - Fixes wrong numbering of restarted workflows by limiting the number of times a workflow can be restarted to nine.
- Administrators:
    - Adds new configuration environment variable ``reana_server.environment.REANA_SCHEDULER_REQUEUE_COUNT`` to set workflow requeue count in case of scheduling errors or busy cluster situations.
    - Adds "infinity" option to ``REANA_SCHEDULER_REQUEUE_COUNT`` to disable requeue count.
    - Adds support for Kubernetes clusters 1.22, 1.23, 1.24, 1.25.
    - Adds new configuration option ``workspaces.retention_rules.maximum_period`` to set a default period for workspace retention rules.
    - Adds new configuration option ``workspaces.retention_rules.cronjob_schedule`` to set how often pending retention rules should be applied.
    - Adds configuration environment variable ``reana_server.environment.REANA_RATELIMIT_SLOW`` to limit API requests to some protected endpoints e.g launch workflow.
    - Adds configuration environment variable ``reana_server.environment.REANA_WORKFLOW_SCHEDULING_READINESS_CHECK_LEVEL`` to define checks that are performed to assess whether the cluster is ready to start new workflows.
    - Adds new configuration option `ingress.tls.self_signed_cert` to enable the generation of a self-signed TLS certificate.
    - Adds new configuration option `ingress.tls.secret_name` to specify the name of the Kubernetes secret containing the TLS certificate to be used.
    - Adds support for configuring an additional volume to be used by the database and the message broker.
    - Adds new configuration option `maintenance.enabled` to scale down the cluster for maintenance.
    - Adds support for Unicode characters inside email body.
    - Adds ``queue-consume`` command that can be used by REANA administrators to remove specific messages from the queue.
    - Adds ``retention-rules-apply`` command that can be used by REANA administrators to apply pending retention rules.
    - Adds ``retention-rules-extend`` command that can be used by REANA administrators to extend the duration of active retentions rules.
    - Adds ``check-workflows`` command that can be used by REANA administrators to check for out-of-sync workflows and interactive sessions.
    - Changes configuration option ``quota.workflow_termination_update_policy`` to deactivate workflow termination accounting by default.
    - Changes Helm template to use PostgreSQL 12.13 version.
    - Changes the base image for most of the components to Ubuntu 20.04 LTS and reduces final Docker image size by removing build-time dependencies.
    - Changes ``reana-auth-vomsproxy`` sidecar to the latest stable version to support client-side proxy file generation technique and ESCAPE VOMS.
    - Changes OAuth configuration to enable the new CERN SSO.
    - Changes job status consumer to improve logging for not-alive workflows.
    - Changes the deployment of interactive sessions to improve security by not automounting the Kubernetes service account token.
    - Changes the deployment of job-controller to avoid unnecessarily mounting the database's directory.
    - Changes the announcements to support limited HTML markup.
    - Changes REANA specification loading functionality to allow specifying different working directories.
    - Changes global setting of maximum number of parallel jobs to 300 for Snakemake workflow engine.
    - Fixes job status consumer by discarding invalid job IDs.
    - Fixes GitLab integration error reporting in case user exceeds CPU or Disk quota usage limits.
    - Fixes issue when irregular number formats are passed to ``REANA_SCHEDULER_REQUEUE_COUNT`` configuration environment variable.
    - Fixes quota updater to reduce memory usage.
    - Fixes conversion of possibly-negative resource usage values to human-readable formats.
    - Fixes disk quota updater to prevent setting negative disk quota usage values.
    - Removes support for Kubernetes version prior to 1.19.
- Developers:
    - Adds OpenAPI specification support for ``launch`` endpoint that allows running workflows from remote sources.
    - Adds OpenAPI specification support for ``get_workflow_retention_rules`` endpoint that allows to retrieve the workspace file retention rules of a workflow.
    - Adds the remote origin of workflows submitted via Launch-on-REANA (``launcher_url``) to the workflow list endpoint.
    - Adds common utility functions for managing workspace files to ``reana-commons``.
    - Changes default consumer prefetch count to handle 10 messages instead of 200 in order to reduce the probability of 406 PRECONDITION errors on message acknowledgement.
    - Changes `git-upgrade-shared-modules` to generate the correct upper-bound in `setup.py`.
    - Changes REANA specification loading and validation functionalities by porting some of the logic to ``reana-commons``.
    - Changes OpenAPI specification to include missing response schema elements.
    - Changes the Kubernetes Python client to use the ``networking/v1`` API.
    - Changes the deployment of interactive sessions to use ``networking/v1`` Kubernetes API.
    - Changes to Flask v2.
    - Changes ``/api/info`` endpoint to also include the kubernetes maximum memory limit, the kubernetes default memory limit and the maximum workspace retention period.
    - Changes ``start_workflow`` endpoint to validate the REANA specification of the workflow.
    - Changes ``create_workflow`` endpoint to populate workspace retention rules for the workflow.
    - Changes ``start_workflow`` endpoint to disallow restarting a workflow when retention rules are pending.
    - Changes API rate limiter error messages to be more verbose.
    - Changes workflow scheduler to allow defining the checks needed to assess whether the cluster can start new workflows.
    - Changes workflow list endpoint to add the possibility to filter by workflow ID.
    - Changes the ``move_files`` endpoint to allow moving files while a workflow is running.
    - Changes the k8s specification of interactive sessions' pods to remove the environment variables used for service discovery.
    - Changes GitLab integration to use ``reana`` as pipeline name instead of ``default`` when setting status of a commit.
    - Changes the loading of Snakemake specifications to preserve the current working directory.
    - Changes the Invenio dependencies to the latest versions.
    - Fixes the submission of jobs by stripping potential leading and trailing whitespaces in Docker image names.
    - Fixes ``fetchWorkflow`` action to fetch a specific workflow instead of the entire user workflow list. (reana-ui)
    - Fixes the download of files by changing the default MIME type to ``application/octet-stream``.
    - Fixes the workflow list endpoint to correctly parse the boolean parameters ``include_progress``, ``include_workspace_size`` and ``include_retention_rules``.

Version 0.8.1 (2022-02-15)
--------------------------

- Users:
    - Adds support for specifying ``kubernetes_job_timeout`` for Kubernetes compute backend jobs.
    - Adds Kubernetes job memory limits validation before accepting workflows for execution.
    - Adds support for HTML preview of workspace files in the web user interface.
    - Adds an option to search for concrete file names in the workflow's workspace web user interface page.
    - Changes the Cluster Health web interface page to display the cluster status information based on resource availability rather than only usage.
    - Changes ``info`` command to include the list of supported compute backends.
    - Fixes workflow stuck in pending status due to early Yadage failures.
    - Fixes formatting of error messages and sets appropriate exit status codes.
- Administrators:
    - Adds new configuration option to set default job timeout value for the Kubernetes compute backend jobs (``kubernetes_jobs_timeout_limit``).
    - Adds new configuration option to set maximum job timeout that users can assign to their jobs for the Kubernetes compute backend (``kubernetes_jobs_max_user_timeout_limit``).
    - Adds new configuration option ``compute_backends`` to specify the supported list of compute backends for validation purposes.
    - Adds new configuration option ``reana_server.uwsgi.log_all`` to toggle the logging of all the HTTP requests.
    - Adds new configuration options ``reana_server.uwsgi.log_4xx`` and ``reana_server.uwsgi.log_5xx`` to only log HTTP error requests, i.e. HTTP requests with status code 4XX and 5XX. To make this configuration effective ``reana_server.uwsgi.log_all`` must be ``false``.
    - Adds new configuration options ``node_label_infrastructuremq`` and ``node_label_infrastructuredb`` to have the possibility to run the Message Broker and the Database pods in specific nodes.
    - Changes uWSGI configuration to log all HTTP requests in REANA-Server by default.
    - Changes ``quota.disk_update`` to ``quota.periodic_update_policy`` to also update the CPU quota. Keeps ``quota.disk_update`` for backward compatibility.
    - Changes the name of configuration option ``quota.termination_update_policy`` to ``quota.workflow_termination_update_policy``. Keeps ``quota.termination_update_policy`` for backward compatibility.
- Developers:
    - Adds workflow name validation to the ``create_workflow`` endpoint, restricting special characters like dots.
    - Changes ``/api/info`` endpoint to return a list of supported compute backends.
    - Changes ``/api/status`` endpoint to calculate the cluster health status based on the availability instead of the usage.
    - Changes the way of determining Snakemake job statuses, polling the Job Controller API instead of checking local files.

Version 0.8.0 (2021-11-30)
--------------------------

- Users:
    - Adds support for running and validating Snakemake workflows.
    - Adds support for ``outputs.directories`` in ``reana.yaml`` allowing to easily download output directories.
    - Adds new command ``quota-show`` to retrieve information about total CPU and Disk usage and quota limits.
    - Adds new command ``info`` that retrieves general information about the cluster, such as available workspace path settings.
    - Changes ``validate`` command to add the possibility to check the workflow against server capabilities such as desired workspace path via ``--server-capabilities`` option.
    - Changes ``list`` command to add the possibility to filter by workflow status and search by workflow name via ``--filter`` option.
    - Changes ``list`` command to add the possibility to filter and display all the runs of a given workflow via ``-w`` option.
    - Changes ``list`` command to stop including workflow progress and workspace size by default. Please use new options ``--include-progress`` and ``--include-workspace-size`` to show this information.
    - Changes ``list --sessions`` command to display the status of interactive sessions.
    - Changes ``logs`` command to display also the start and finish times of individual jobs.
    - Changes ``ls`` command to add the possibility to filter by file name, size and last-modified values via ``--filter`` option.
    - Changes ``du`` command to add the possibility filter by file name and size via ``--filter`` option.
    - Changes ``delete`` command to prevent hard-deletion of workflows.
    - Changes Yadage workflow specification loading to be done in ``reana-commons``.
    - Changes CWL workflow engine to ``cwltool`` version ``3.1.20210628163208``.
    - Removes support for Python 2.7. Please use Python 3.6 or higher from now on.
- Administrators:
    - Adds new configuration options ``node_label_runtimebatch``, ``node_label_runtimejobs``, ``node_label_runtimesessions`` allowing to set cluster node labels for splitting runtime workload into dedicated workflow batch nodes, workflow job nodes and interactive session nodes.
    - Adds new configuration option ``workspaces.paths`` allowing to set a dictionary of available workspace paths to pairs of ``cluster_node_path:cluster_pod_mountpath`` for mounting directories from cluster nodes.
    - Adds new configuration option ``quota.enabled`` to enable or disable CPU and Disk quota accounting for users.
    - Adds new configuration option ``quota.termination_update_policy`` to select the quota resources such as CPU and Disk for which the quota usage will be calculated immediately at the workflow termination time.
    - Adds new periodic cron job to update Disk quotas nightly. Useful if the ``quota.termination_update_policy`` does not include Disk quota resource.
    - Adds configuration environment variable ``reana_server.environment.REANA_WORKFLOW_SCHEDULING_POLICY`` allowing to set workflow scheduling policy (first-in first-out, user-balanced and workflow-complexity balanced).
    - Adds configuration environment variables ``reana_server.environment.REANA_RATELIMIT_GUEST_USER``, ``reana_server.environment.REANA_RATELIMIT_AUTHENTICATED_USER`` allowing to set REST API rate limit values.
    - Adds configuration environment variable ``reana_server.environment.REANA_SCHEDULER_REQUEUE_SLEEP`` to set a time to wait between processing queued workflows.
    - Adds configuration environment variable ``reana_workflow_controller.environment.REANA_JOB_STATUS_CONSUMER_PREFETCH_COUNT`` allowing to set a prefetch count for the job status consumer.
    - Adds support for Kubernetes 1.21 version clusters.
    - Adds default ``kubernetes_memory_limit`` value (4 GiB) that will be used for all user jobs unless they specify otherwise.
    - Changes Helm template to use PostgreSQL 12.8 version.
    - Changes Helm template for ``reana-db`` component to allow 300 maximum number of database connections by default.
    - Fixes email validation procedure during ``create-admin-user`` command to recognize more permissive email address formats.
- Developers:
    - Changes ``git-*`` commands to add the possibility of excluding certain components via the ``--exclude-components`` option.
    - Changes ``git-create-release-commit`` command to bump all version files in a component.
    - Changes ``git-log`` command to show diff patch or to pass any wanted argument.
    - Changes ``helm-upgrade-components`` command to also upgrade the image tags in ``prefetch-images.sh`` script.

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
