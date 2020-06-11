# REANA: reproducible research data analysis platform.

## Chart Prefix

This Helm automatically prefixes all names using the release name to avoid collisions.

## Configuration

| Parameter                                                | Description                                                                          | Default value                                   |
|----------------------------------------------------------|--------------------------------------------------------------------------------------|-------------------------------------------------|
| `components.reana_db.enabled`                            | Instantiate a PostgreSQL database inside the cluster                                 | true                                            |
| `components.reana_job_controller.image`                  | [REANA-Job-Controller image](https://hub.docker.com/repository/docker/reanahub/reana-job-controller) to use  | `reanahub/reana-job-controller:<chart-release-verion>` |
| `components.reana_message_broker.image`                  | [REANA-Meessage-Broker image](https://hub.docker.com/repository/docker/reanahub/reana-message-broker) to use | `reanahub/reana-message-broker:<chart-release-verion>` |
| `components.reana_message_broker.imagePullPolicy`        | REANA-Message-Broker image pull policy                                               | IfNotPresent                                    |
| `components.reana_server.environment`                    | REANA-Server environment variables                                                   | {REANA_MAX_CONCURRENT_BATCH_WORKFLOWS: 30}      |
| `components.reana_server.image`                          | REANA-Server image to use                                                            | `reanahub/reana-server:<chart-release-verion>`  |
| `components.reana_server.imagePullPolicy`                | REANA-Server image pull policy                                                       | IfNotPresent                                    |
| `components.reana_ui.enabled`                            | Instantiate the [REANA-UI](https://github.com/reanahub/reana-ui)                     | false                                           |
| `components.reana_ui.image`                              | [REANA-UI image](https://hub.docker.com/repository/docker/reanahub/reana-ui) to use  | `reanahub/reana-ui:<chart-release-verion>`      |
| `components.reana_ui.imagePullPolicy`                    | REANA-UI image pull policy                                                           | IfNotPresent                                    |
| `components.reana_workflow_controller.environment`       | REANA-Workflow-Controller environment variables                                      | `{SHARED_VOLUME_PATH: /var/reana}`              |
| `components.reana_workflow_controller.image`             |                                                                                      | `reanahub/reana-workflow-controller:<chart-release-verion>` |
| `components.reana_workflow_controller.imagePullPolicy`   | REANA-Workflow-Controller image pull policy                                          | IfNotPresent                                    |
| `components.reana_workflow_engine_cwl.image`             | [REANA-Workflow-Engine-CWL](https://hub.docker.com/repository/docker/reanahub/reana-workflow-engine-cwl) image to use | `reanahub/reana-workflow-engine-cwl:<chart-release-verion>` |
| `components.reana_workflow_engine_serial.image`          | [REANA-Workflow-Engine-Serial](https://hub.docker.com/repository/docker/reanahub/reana-workflow-engine-serial) image to use | `reanahub/reana-workflow-engine-serial:<chart-release-verion>` |
| `components.reana_workflow_engine_yadage.image`          | [REANA-Workflow-Engine-Yadage](https://hub.docker.com/repository/docker/reanahub/reana-workflow-engine-yadage) image to use | `reanahub/reana-workflow-engine-yadage:<chart-release-verion>` |
| `db_env_config.REANA_DB_HOST`                            | Environment variable to connect to external databases                                | `<chart-release-name>-db`                       |
| `db_env_config.REANA_DB_NAME`                            | Environment variable to connect to external databases                                | reana                                           |
| `db_env_config.REANA_DB_PORT`                            | Environment variable to connect to external databases                                | "5432"                                          |
| `debug.enabled`                                          | Instantiate a [wdb](https://github.com/Kozea/wdb) remote debugger inside the cluster, accessible in port `31984` | false               |
| `eos.enabled`                                            | **[CERN only]** Enable EOS support inside the cluster                                | false                                           |
| `ingress.annotations.ingress.kubernetes.io/ssl-redirect` | Redirect all traffic to HTTPS                                                        | true                                            |
| `ingress.annotations.kubernetes.io/ingress.class`        | Type of ingress controller                                                           | traefik                                         |
| `ingress.annotations.traefik.frontend.entryPoints`       | Entrypoints allowed by the ingress controller                                        | "http,https"                                    |
| `ingress.enabled`                                        | Create an ingress resource to access the REANA instance from outside the cluster     | true                                            |
| `notifications.email_config.login`                       | Login for the sender email address                                                   | None                                            |
| `notifications.email_config.password`                    | Password for the sender email address                                                | None                                            |
| `notifications.email_config.receiver`                    | Email address which will be receiving the notifications                              | None                                            |
| `notifications.email_config.sender`                      | Email address which will be sending the notifications                                | None                                            |
| `notifications.email_config.smtp_server`                 | SMTP email server host                                                               | None                                            |
| `notifications.email_config.smtp_port`                   | SMTP email server port                                                               | None                                            |
| `notifications.enabled`                                  | Enable REANA system events notifications                                             | false                                           |
| `notifications.system_status`                            | Cronjob pattern representing how often the system status notification should be sent. Leave it empty to deactivate it | "0 0 * * *"                                     |
| `reana_url`                                              | REANA URL host                                                                       | None                                            |
| `default_runtime_namespace`                              | Namespace in which the REANA runtime pods (workflow engines, jobs etc...) will run   | None                                            |
| `secrets.cern.sso.CERN_CONSUMER_KEY`                     | CERN SSO consumer key                                                                | None                                            |
| `secrets.cern.sso.CERN_CONSUMER_SECRET`                  | **[Do not use in production, use secrets instead]** CERN SSO consumer secret         | None                                            |
| `secrets.database.pasword`                               | **[Do not use in production, use secrets instead]** PostgreSQL database password     | None                                            |
| `secrets.database.user`                                  | PostgreSQL database username                                                         | reana                                           |
| `secrets.gitlab.REANA_GITLAB_HOST`                       | Hostname of the GitLab instance                                                      | None                                            |
| `secrets.gitlab.REANA_GITLAB_OAUTH_APP_ID`               | GitLab OAuth application id                                                          | None                                            |
| `secrets.gitlab.REANA_GITLAB_OAUTH_APP_SECRET`           | **[Do not use in production, use secrets instead]** GitLab OAuth application secret  | None                                            |
| `secrets.reana.REANA_SECRET_KEY`                         | **[Do not use in production, use secrets instead]** REANA encryption secret key     | None                                            |
| `serviceAccount.create`                                  | Create a service account for the REANA system user                                   | true                                            |
| `serviceAccount.name`                                    | Service account name                                                                 | reana                                           |
| `shared_storage.access_modes`                            | Shared volume access mode                                                            | ReadWriteMany                                   |
| `shared_storage.backend`                                 | Shared volume storage backend                                                        | hostpath                                        |
| `shared_storage.cephfs.availability_zone`                | **[CERN only]** OpenStack Availability zone                                          | nova                                            |
| `shared_storage.cephfs.cephfs_os_share_access_id`        | **[CERN only]** CephFS share access ID                                               | None                                            |
| `shared_storage.cephfs.cephfs_os_share_id`               | **[CERN only]** CephFS share id                                                      | None                                            |
| `shared_storage.cephfs.os_secret_name`                   | **[CERN only]** Name of the Secret object containing OpenStack credentials           | os-trustee                                      |
| `shared_storage.cephfs.os_secret_namespace`              | **[CERN only]** Namespace of the OpenStack credentials Secret object                 | kube-system                                     |
| `shared_storage.cephfs.provisioner`                      | **[CERN only]** CephFS provisioner                                                   | manila-provisioner                              |
| `shared_storage.cephfs.type`                             | **[CERN only]** CephFS availability zone                                             | "Geneva CephFS Testing"                         |
| `shared_storage.volume_size`                             | Shared volume size                                                                   | 200                                             |
| `traefik.*`                                              | Pass any value from [Traefik Helm chart values](https://github.com/helm/charts/tree/master/stable/traefik#configuration) here, i.e. `traefik.rbac.enabled=true` | - |
| `traefik.enabled`                                        | Install Traefik in the cluster when installing REANA                                 | true                                            |
| `volume_paths.root_path`                                 | Path to the REANA directory inside the underlying storage volume                     | /var/reana                                      |
| `volume_paths.shared_volume_path`                        | Path inside the REANA components where the shared volume will be mounted             | /var/reana                                      |
