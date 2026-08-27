# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for auth-related Helm rendering."""

import base64
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CHART = REPO_ROOT / "helm" / "reana"
VALUES_DEV = REPO_ROOT / "helm" / "configurations" / "values-dev.yaml"
VALUES_CERN = REPO_ROOT / "helm" / "configurations" / "values-cern.yaml"
VALUES_EOSC = REPO_ROOT / "helm" / "configurations" / "values-eosc.yaml"
VALUES_ESCAPE = REPO_ROOT / "helm" / "configurations" / "values-escape.yaml"
CREATE_ADMIN_SCRIPT = REPO_ROOT / "scripts" / "create-admin-user.sh"
AUTHENTICATED_TEST_SCRIPTS = (
    REPO_ROOT / "scripts" / "test-spec-validation-storage.sh",
    REPO_ROOT / "scripts" / "test-spec-validator-network-policy.sh",
)


def _helm_template(*extra_args):
    if shutil.which("helm") is None:
        pytest.skip("helm is not installed")
    result = subprocess.run(
        ["helm", "template", "reana", str(CHART), *extra_args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _helm_major_version():
    """Return Helm's major version number, or None when helm is unavailable."""
    if shutil.which("helm") is None:
        return None
    result = subprocess.run(
        ["helm", "version", "--template", "{{.Version}}"],
        capture_output=True,
        text=True,
    )
    match = re.search(r"v?(\d+)\.", result.stdout)
    return int(match.group(1)) if match else None


def _helm_install_dry_run(*extra_args):
    """Render a dry-run install, including the chart's installation notes.

    Rendering NOTES without a reachable cluster needs ``--dry-run=client``,
    which only Helm 4 honours (Helm 3 still contacts the cluster and fails). The
    CI ``python-tests`` job pins Helm 4 for this reason; a local Helm 3 skips
    with a clear reason rather than failing on cluster reachability. ``lint-helm``
    keeps covering Helm 3 through chart-testing.
    """
    major = _helm_major_version()
    if major is None:
        pytest.skip("helm is not installed")
    if major < 4:
        pytest.skip(
            "rendering chart NOTES without a cluster requires Helm 4 "
            "(`helm install --dry-run=client`); the CI python-tests job pins it"
        )
    result = subprocess.run(
        [
            "helm",
            "install",
            "reana-auth-test",
            str(CHART),
            "--dry-run=client",
            "--debug",
            *extra_args,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Surface stderr so the decisive Helm error is visible in CI instead of
        # a bare non-zero exit from ``check=True``.
        raise AssertionError(
            "helm install --dry-run=client failed "
            f"(exit {result.returncode}).\n--- stderr ---\n{result.stderr}\n"
            f"--- stdout ---\n{result.stdout}"
        )
    return result.stdout + result.stderr


def _rendered_resource(rendered, kind, name):
    """Return one named resource from a multi-document Helm render."""
    return next(
        resource
        for resource in yaml.safe_load_all(rendered)
        if resource
        and resource.get("kind") == kind
        and resource.get("metadata", {}).get("name") == name
    )


def _container_environment(deployment, container_name):
    """Return a container's rendered environment as a name-keyed mapping."""
    containers = deployment["spec"]["template"]["spec"]["containers"]
    container = next(item for item in containers if item["name"] == container_name)
    return {item["name"]: item for item in container["env"]}


def test_default_chart_does_not_enable_auth_or_bundled_keycloak():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "keycloak.enabled=false",
    )

    assert "REANA_AUTH_ISSUER" not in rendered
    assert "REANA_AUTH_WEB_CLIENT_SECRET" not in rendered
    assert "name: reana-auth-secrets" not in rendered
    assert "name: reana-keycloak" not in rendered


def test_local_keycloak_auth_uses_secret_backed_reana_auth():
    rendered = _helm_template("-f", str(VALUES_DEV))
    server = _rendered_resource(rendered, "Deployment", "reana-server")
    environment = _container_environment(server, "rest-api")
    network_policy = _rendered_resource(rendered, "NetworkPolicy", "reana-keycloak")

    assert "REANA_AUTH_ISSUER" in rendered
    assert "https://localhost:30443/keycloak/realms/reana" in rendered
    assert environment["REANA_AUTH_BACKCHANNEL_BASE_URL"]["value"] == (
        "http://reana-keycloak:8080/keycloak/realms/reana"
    )
    assert environment["REANA_AUTH_BACKCHANNEL_ALLOW_HTTP"]["value"] == "true"
    assert environment["PROXYFIX_CONFIG"]["value"] == '{"x_for":1,"x_proto":1}'
    assert environment["REANA_AUTH_OPENID_CONFIG_URL"]["value"] == (
        "http://reana-keycloak:8080/keycloak/realms/reana/"
        ".well-known/openid-configuration"
    )
    assert environment["REANA_AUTH_AUTHORIZATION_URL"]["value"] == (
        "https://localhost:30443/keycloak/realms/reana/" "protocol/openid-connect/auth"
    )
    assert environment["REANA_AUTH_END_SESSION_URL"]["value"] == (
        "https://localhost:30443/keycloak/realms/reana/"
        "protocol/openid-connect/logout"
    )
    allowed_sources = network_policy["spec"]["ingress"][0]["from"]
    assert {"podSelector": {"matchLabels": {"app": "reana-server"}}} in (
        allowed_sources
    )
    assert {
        "podSelector": {"matchLabels": {"app.kubernetes.io/name": "traefik"}}
    } in allowed_sources
    assert {
        "namespaceSelector": {
            "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
        },
        "podSelector": {"matchLabels": {"app.kubernetes.io/name": "traefik"}},
    } in allowed_sources
    assert "name: reana-auth-secrets" in rendered
    assert "key: REANA_AUTH_WEB_CLIENT_SECRET" in rendered
    assert "name: reana-keycloak" in rendered
    assert "jane@example.org" not in rendered
    assert 'value: "admin"' not in rendered
    assert "LOGIN_PROVIDERS" not in rendered
    assert "CERN_CONSUMER" not in rendered
    assert "EOSC_CONSUMER" not in rendered


def test_bundled_keycloak_honours_non_default_scopes_and_session_ttl():
    """auth.scopes/auth.sessionTtl are not external-issuer-only settings.

    Both used to be wired into only the external-issuer branch of the
    auth env-var block, so a deployer overriding either under bundled
    Keycloak -- e.g. shortening sessionTtl as a security control -- had
    it silently ignored; reana-server fell back to its own Python
    defaults instead.
    """
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "auth.scopes=openid profile",
        "--set",
        "auth.sessionTtl=60",
    )
    server = _rendered_resource(rendered, "Deployment", "reana-server")
    environment = _container_environment(server, "rest-api")

    assert environment["REANA_AUTH_SCOPES"]["value"] == "openid profile"
    assert environment["REANA_AUTH_SESSION_TTL"]["value"] == "60"


def test_bundled_keycloak_http_backchannel_requires_explicit_opt_in():
    """Enabling bundled HTTP without the explicit risk choice fails rendering."""
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        _helm_template(
            "-f",
            str(VALUES_DEV),
            "--set",
            "keycloak.backchannel_allow_http=false",
        )

    assert "keycloak.backchannel_allow_http=true explicitly" in (exc_info.value.stderr)


def test_external_http_backchannel_requires_base_and_explicit_opt_in():
    """External-mode Helm values fail before creating an unsafe deployment."""
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        _helm_template(
            "-f",
            str(VALUES_DEV),
            "-f",
            str(VALUES_CERN),
            "--set",
            "auth.backchannelAllowHttp=true",
        )
    assert "requires auth.backchannelBaseUrl" in exc_info.value.stderr

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        _helm_template(
            "-f",
            str(VALUES_DEV),
            "-f",
            str(VALUES_CERN),
            "--set",
            "auth.backchannelBaseUrl=http://keycloak.internal/realms/reana",
        )
    assert "requires auth.backchannelAllowHttp=true" in exc_info.value.stderr


def test_external_https_backchannel_renders_without_insecure_opt_in():
    """A production-style HTTPS backchannel remains the secure default."""
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_CERN),
        "--set",
        "auth.backchannelBaseUrl=https://keycloak.internal/realms/reana",
        "--set",
        "auth.caBundle=/etc/reana/idp-ca.pem",
        "--set",
        "auth.audience=test-audience",
    )
    server = _rendered_resource(rendered, "Deployment", "reana-server")
    environment = _container_environment(server, "rest-api")

    assert environment["REANA_AUTH_BACKCHANNEL_BASE_URL"]["value"] == (
        "https://keycloak.internal/realms/reana"
    )
    assert environment["REANA_AUTH_BACKCHANNEL_ALLOW_HTTP"]["value"] == "false"
    assert environment["REANA_AUTH_CA_BUNDLE"]["value"] == ("/etc/reana/idp-ca.pem")


def test_reana_server_readiness_probe_checks_process_readiness():
    """A dependency outage must not withdraw the otherwise usable whole API."""
    rendered = _helm_template("-f", str(VALUES_DEV))
    server = _rendered_resource(rendered, "Deployment", "reana-server")
    container = next(
        item
        for item in server["spec"]["template"]["spec"]["containers"]
        if item["name"] == "rest-api"
    )

    probe = container["readinessProbe"]
    assert probe["httpGet"]["path"] == "/api/ping"
    assert probe["httpGet"]["port"] == 5000


def test_job_controller_http_listener_is_pod_local():
    """Only the trusted sidecar in the same pod may call job-controller HTTP."""
    rendered = _helm_template("-f", str(VALUES_DEV))
    config = _rendered_resource(
        rendered, "ConfigMap", "uwsgi-config-reana-job-controller"
    )
    assert "http = 127.0.0.1:5000" in config["data"]["uwsgi.ini"]
    assert "http = 0.0.0.0:5000" not in config["data"]["uwsgi.ini"]


@pytest.mark.parametrize("hostport", (443, 30443))
def test_reana_server_receives_public_hostport(hostport):
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        f"reana_hostport={hostport}",
    )

    server = _rendered_resource(rendered, "Deployment", "reana-server")
    environment = _container_environment(server, "rest-api")

    assert environment["REANA_HOSTPORT"]["value"] == str(hostport)


def test_bundled_keycloak_realm_tracks_chart_values_and_uses_secrets():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "reana_hostname=reana.example.org",
        "--set",
        "reana_hostport=443",
        "--set",
        "keycloak.realm=custom-realm",
        "--set",
        "keycloak.audience=custom-audience",
        "--set",
        "keycloak.cli_client_id=custom-cli",
        "--set",
        "keycloak.web_client_id=custom-web",
        "--set",
        "keycloak.roles_claim=custom_roles",
        "--set",
        "keycloak.required_role=reana:member",
        "--set",
        "secrets.auth.REANA_AUTH_WEB_CLIENT_SECRET=custom-web-secret",
    )

    realm_secret = _rendered_resource(rendered, "Secret", "reana-keycloak-realm")
    realm = json.loads(realm_secret["stringData"]["reana-realm.json"])
    web_client, cli_client = realm["clients"]
    keycloak = _rendered_resource(rendered, "Deployment", "reana-keycloak")
    reconciler = _rendered_resource(rendered, "Job", "reana-keycloak-realm-reconciler")
    environment = _container_environment(keycloak, "keycloak")

    assert realm["realm"] == "custom-realm"
    assert realm["sslRequired"] == "external"
    assert keycloak["spec"]["template"]["spec"]["containers"][0]["args"][0] == ("start")
    assert web_client["clientId"] == "custom-web"
    assert web_client["serviceAccountsEnabled"] is True
    assert cli_client["clientId"] == "custom-cli"
    assert "users" not in realm
    assert "groups" not in realm
    assert web_client["secret"] == "custom-web-secret"
    assert {role["name"] for role in realm["roles"]["realm"]} >= {
        "reana:member",
        "reana:admin",
        "offline_access",
    }
    assert web_client["redirectUris"] == [
        "https://reana.example.org/api/oauth/callback"
    ]
    assert web_client["attributes"]["post.logout.redirect.uris"] == (
        "https://reana.example.org"
    )
    for client in realm["clients"]:
        roles_mapper = next(
            mapper
            for mapper in client["protocolMappers"]
            if mapper["name"] == "custom_roles"
        )
        assert roles_mapper["config"]["claim.name"] == "custom_roles"
        audience_mapper = next(
            mapper
            for mapper in client["protocolMappers"]
            if mapper["name"] == "reana-audience"
        )
        assert audience_mapper["config"]["included.custom.audience"] == (
            "custom-audience"
        )
    for variable in ("KC_BOOTSTRAP_ADMIN_USERNAME", "KC_BOOTSTRAP_ADMIN_PASSWORD"):
        assert environment[variable]["valueFrom"]["secretKeyRef"]["name"] == (
            "reana-keycloak-bootstrap"
        )
    assert keycloak["spec"]["template"]["spec"]["volumes"] == [
        {"name": "realm", "secret": {"secretName": "reana-keycloak-realm"}}
    ]
    assert environment["REANA_KEYCLOAK_REQUIRED_ROLE"]["value"] == ("reana:member")
    assert environment["REANA_KEYCLOAK_ROLES_CLAIM"]["value"] == ("custom_roles")
    assert reconciler["metadata"]["annotations"]["helm.sh/hook"] == (
        "post-install,post-upgrade"
    )
    reconcile_script = reconciler["spec"]["template"]["spec"]["containers"][0]["args"][
        0
    ]
    assert "create partialImport" in reconcile_script
    assert "ifResourceExists=OVERWRITE" in reconcile_script
    assert "get group-by-path/local" in reconcile_script
    assert "get group-by-path/local/atlas" in reconcile_script
    assert "create groups" in reconcile_script
    assert '"groups/${local_group_id}/children"' in reconcile_script
    assert "add-roles" in reconcile_script
    assert '"service-account-${KEYCLOAK_WEB_CLIENT_ID}"' in reconcile_script
    assert "serviceAccountsEnabled=false" in reconcile_script
    assert "serviceAccountsEnabled=true" in reconcile_script
    for role in ("query-groups", "view-users"):
        assert f"--rolename {role}" in reconcile_script
    assert "--rolename view-groups" not in reconcile_script
    assert "get roles/offline_access" in reconcile_script
    assert '"roles/default-roles-${KEYCLOAK_REALM}/composites"' in reconcile_script
    assert "printf '[%s]'" in reconcile_script
    assert not re.search(
        r"get roles/offline_access.*?--fields.*?--compressed",
        reconcile_script,
        re.DOTALL,
    )
    reconciler_environment = {
        item["name"]: item
        for item in reconciler["spec"]["template"]["spec"]["containers"][0]["env"]
    }
    assert "--password" not in reconcile_script
    assert "KC_CLI_PASSWORD" in reconciler_environment
    assert reconciler_environment["KEYCLOAK_WEB_CLIENT_ID"]["value"] == "custom-web"
    assert reconciler_environment["KC_CLI_PASSWORD"]["valueFrom"]["secretKeyRef"] == {
        "name": "reana-keycloak-bootstrap",
        "key": "password",
    }
    assert "KEYCLOAK_ADMIN_PASSWORD" not in reconciler_environment


def test_bundled_keycloak_resources_are_configurable():
    """Keycloak's resources have a non-empty default and accept overrides.

    Unlike every other component in this chart, Keycloak's resources were
    previously hardcoded in the template with no values.yaml override and no
    limits -- an operator sizing a production node pool had no way to set
    them.
    """
    default_rendered = _helm_template("-f", str(VALUES_DEV))
    default_keycloak = _rendered_resource(
        default_rendered, "Deployment", "reana-keycloak"
    )
    default_resources = default_keycloak["spec"]["template"]["spec"]["containers"][0][
        "resources"
    ]
    assert default_resources == {"requests": {"cpu": "250m", "memory": "768Mi"}}

    overridden = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "keycloak.resources.requests.cpu=1",
        "--set",
        "keycloak.resources.requests.memory=2Gi",
        "--set",
        "keycloak.resources.limits.memory=4Gi",
    )
    keycloak = _rendered_resource(overridden, "Deployment", "reana-keycloak")
    resources = keycloak["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert resources == {
        "requests": {"cpu": 1, "memory": "2Gi"},
        "limits": {"memory": "4Gi"},
    }


def test_deployment_manager_role_can_delete_secrets():
    """RBAC must allow deleting the Secret it also creates.

    reana-workflow-controller's partial-creation cleanup path
    (delete_k8s_objects_if_exist -> delete_namespaced_secret) deletes the
    per-session notebook-token Secret when interactive-session creation
    fails partway. Without this verb that cleanup 403s and the Secret --
    holding a live credential -- is orphaned instead of removed.
    """
    rendered = _helm_template("-f", str(VALUES_DEV))
    role = _rendered_resource(rendered, "ClusterRole", "reana-deployment-manager")
    secrets_rules = [
        rule
        for rule in role["rules"]
        if "" in rule["apiGroups"] and "secrets" in rule["resources"]
    ]
    assert secrets_rules, "no rule grants access to secrets"
    assert any("delete" in rule["verbs"] for rule in secrets_rules)


def test_runtime_service_account_is_always_created():
    """The runtime ServiceAccount must exist even in single-namespace mode.

    PR976-17: previously it was only rendered when ``namespace_runtime``
    differed from the release namespace, so single-namespace deployments (the
    common case) had no distinct runtime identity for the batch pod to use.
    """
    rendered = _helm_template("-f", str(VALUES_DEV))
    account = _rendered_resource(rendered, "ServiceAccount", "reana-runtime")
    assert account["metadata"].get("namespace") in (None, "default")


def test_runtime_service_account_is_not_bound_to_deployment_manager():
    """The runtime ServiceAccount must not inherit the controller's own role.

    PR976-17: the batch pod that executes user-submitted workflow/job code
    must not carry the same cluster-wide privileges (including secret
    delete) as the infrastructure ServiceAccount reana-workflow-controller
    itself runs as.
    """
    rendered = _helm_template("-f", str(VALUES_DEV))
    binding = _rendered_resource(
        rendered, "ClusterRoleBinding", "reana-manage-deployments"
    )
    runtime_subjects = [
        subject for subject in binding["subjects"] if subject["name"] == "reana-runtime"
    ]
    assert not runtime_subjects, "runtime SA must not be bound to deployment-manager"


def test_runtime_worker_role_excludes_secret_delete_and_privileged_verbs():
    """The runtime-worker role must be minimal, not a copy of deployment-manager.

    Audited against reana-job-controller's actual Kubernetes API usage: it
    only creates/deletes Jobs, lists/watches Pods and reads Pod logs, and
    does one read-only fetch of the user's own secrets-store Secret.
    """
    rendered = _helm_template("-f", str(VALUES_DEV))
    role = _rendered_resource(rendered, "Role", "reana-runtime-worker")
    binding = _rendered_resource(rendered, "RoleBinding", "reana-runtime-worker")
    assert binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": "reana-runtime",
            "namespace": "default",
        }
    ]

    secrets_rules = [
        rule
        for rule in role["rules"]
        if "" in rule["apiGroups"] and "secrets" in rule["resources"]
    ]
    assert secrets_rules, "runtime worker must still read its own secrets store"
    for rule in secrets_rules:
        assert rule["verbs"] == [
            "get"
        ], "runtime worker must not list/create/update/delete secrets"

    forbidden_resources = {"storageclasses", "deployments", "services", "ingresses"}
    for rule in role["rules"]:
        assert not forbidden_resources & set(rule["resources"])


def test_runtime_worker_role_is_namespaced_to_namespace_runtime():
    """The runtime-worker Role/RoleBinding must live in the runtime namespace.

    PR976-18: this pair used to be a ClusterRole/ClusterRoleBinding, so its
    ``secrets: get`` rule -- however trimmed -- still let the runtime worker
    read any named Secret in any namespace in the cluster. Scoping it down to
    a namespaced Role confines that to the namespace the batch pod actually
    runs in, which in a split-topology deployment is ``namespace_runtime``,
    not ``Release.Namespace``.
    """
    rendered = _helm_template(
        "-f", str(VALUES_DEV), "--set", "namespace_runtime=reana-runtime"
    )
    role = _rendered_resource(rendered, "Role", "reana-runtime-worker")
    binding = _rendered_resource(rendered, "RoleBinding", "reana-runtime-worker")

    assert role["metadata"]["namespace"] == "reana-runtime"
    assert binding["metadata"]["namespace"] == "reana-runtime"


def test_bundled_keycloak_uses_an_isolated_database_on_bundled_postgres():
    rendered = _helm_template("-f", str(VALUES_DEV))
    keycloak = _rendered_resource(rendered, "Deployment", "reana-keycloak")
    database = _rendered_resource(rendered, "Deployment", "reana-db")
    environment = _container_environment(keycloak, "keycloak")
    database_secret = _rendered_resource(rendered, "Secret", "reana-keycloak-database")
    provisioner = keycloak["spec"]["template"]["spec"]["initContainers"][0]
    provisioner_environment = {item["name"]: item for item in provisioner["env"]}

    assert environment["KC_DB"]["value"] == "postgres"
    assert database["spec"]["strategy"] == {
        "type": "RollingUpdate",
        "rollingUpdate": {"maxSurge": 0, "maxUnavailable": 1},
    }
    assert database["spec"]["template"]["spec"]["containers"][0]["readinessProbe"][
        "exec"
    ]["command"][-1] == (
        'pg_isready --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"'
    )
    assert environment["KC_DB_URL_HOST"]["value"] == "reana-db"
    assert environment["KC_DB_URL_DATABASE"]["value"] == "keycloak"
    assert environment["KC_DB_USERNAME"]["value"] == "keycloak"
    assert environment["KCRAW_DB_PASSWORD"]["valueFrom"]["secretKeyRef"] == {
        "name": "reana-keycloak-database",
        "key": "password",
    }
    assert provisioner["name"] == "provision-keycloak-database"
    assert provisioner_environment["PGUSER"]["valueFrom"]["secretKeyRef"] == {
        "name": "reana-db-secrets",
        "key": "user",
    }
    assert provisioner_environment["KEYCLOAK_DB_PASSWORD"]["valueFrom"][
        "secretKeyRef"
    ] == {"name": "reana-keycloak-database", "key": "password"}
    assert (
        database_secret["metadata"]["annotations"]["helm.sh/resource-policy"] == "keep"
    )
    assert base64.b64decode(database_secret["data"]["password"]) == (
        b"reana-keycloak-db-password-for-development"
    )


def test_keycloak_database_provisioning_does_not_pass_password_via_cli_arg():
    """The Keycloak DB role's password must not appear in the initContainer's argv.

    A literal `--set=keycloak_password=...` on the psql command line is
    visible via `ps`/`/proc/<pid>/cmdline` to anything with exec/process-list
    access to the container, independent of any Kubernetes Secret RBAC.
    """
    rendered = _helm_template("-f", str(VALUES_DEV))
    keycloak = _rendered_resource(rendered, "Deployment", "reana-keycloak")
    provisioner = keycloak["spec"]["template"]["spec"]["initContainers"][0]
    script = provisioner["args"][0]

    assert "keycloak_password" not in script.split("<<'SQL'")[0]
    assert "\\set keycloak_password `printf '%s' \"$KEYCLOAK_DB_PASSWORD\"`" in script


def test_bootstrap_existing_secret_overrides_provisioning_credential():
    """An explicit bootstrap secret replaces the default app DB credential.

    By default the Keycloak DB provisioning initContainer reuses
    secrets.database.*, since that credential is already the bundled
    PostgreSQL superuser by construction. Operators who supply a narrower
    bootstrap credential must have it actually used, not silently ignored.
    """
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "keycloak.database.bootstrap_existing_secret=custom-bootstrap-secret",
    )
    keycloak = _rendered_resource(rendered, "Deployment", "reana-keycloak")
    provisioner = keycloak["spec"]["template"]["spec"]["initContainers"][0]
    provisioner_environment = {item["name"]: item for item in provisioner["env"]}

    assert provisioner_environment["PGUSER"]["valueFrom"]["secretKeyRef"] == {
        "name": "custom-bootstrap-secret",
        "key": "user",
    }
    assert provisioner_environment["PGPASSWORD"]["valueFrom"]["secretKeyRef"] == {
        "name": "custom-bootstrap-secret",
        "key": "password",
    }


def test_bundled_keycloak_can_use_preprovisioned_external_postgres():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "keycloak.database.mode=external",
        "--set",
        "keycloak.database.host=postgres.identity.svc",
        "--set",
        "keycloak.database.port=5433",
        "--set",
        "keycloak.database.name=identity",
        "--set",
        "keycloak.database.username=identity_service",
        "--set",
        "keycloak.database.existing_secret=identity-database",
        "--set",
        "keycloak.database.password_key=database-password",
        "--set",
        "keycloak.database.tls_mode=verify-server",
    )
    keycloak = _rendered_resource(rendered, "Deployment", "reana-keycloak")
    environment = _container_environment(keycloak, "keycloak")
    resources = [resource for resource in yaml.safe_load_all(rendered) if resource]

    assert "initContainers" not in keycloak["spec"]["template"]["spec"]
    assert environment["KC_DB"]["value"] == "postgres"
    assert environment["KC_DB_URL_HOST"]["value"] == "postgres.identity.svc"
    assert environment["KC_DB_URL_PORT"]["value"] == "5433"
    assert environment["KC_DB_URL_DATABASE"]["value"] == "identity"
    assert environment["KC_DB_USERNAME"]["value"] == "identity_service"
    assert environment["KC_DB_TLS_MODE"]["value"] == "verify-server"
    assert environment["KCRAW_DB_PASSWORD"]["valueFrom"]["secretKeyRef"] == {
        "name": "identity-database",
        "key": "database-password",
    }
    assert not any(
        resource.get("kind") == "Secret"
        and resource.get("metadata", {}).get("name") == "reana-keycloak-database"
        for resource in resources
    )


def test_external_keycloak_database_can_mount_private_ca_secret():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "keycloak.database.mode=external",
        "--set",
        "keycloak.database.host=postgres.identity.svc",
        "--set",
        "keycloak.database.name=identity",
        "--set",
        "keycloak.database.username=identity_service",
        "--set",
        "keycloak.database.existing_secret=identity-database",
        "--set",
        "keycloak.database.tls_mode=verify-server",
        "--set",
        "keycloak.database.tls_truststore_existing_secret=identity-database-ca",
    )
    keycloak = _rendered_resource(rendered, "Deployment", "reana-keycloak")
    container = keycloak["spec"]["template"]["spec"]["containers"][0]
    environment = {item["name"]: item for item in container["env"]}

    assert environment["KC_DB_TLS_TRUST_STORE_FILE"]["value"] == (
        "/opt/keycloak/conf/database-ca.pem"
    )
    assert {
        "name": "database-truststore",
        "mountPath": "/opt/keycloak/conf/database-ca.pem",
        "subPath": "ca.crt",
        "readOnly": True,
    } in container["volumeMounts"]
    assert {
        "name": "database-truststore",
        "secret": {"secretName": "identity-database-ca"},
    } in keycloak["spec"]["template"]["spec"]["volumes"]


def test_notes_warn_about_unlinked_identities_on_upgrade():
    """Upgrading a pre-OIDC install must not silently lock out every user.

    Existing accounts have no idp_issuer/idp_subject until linked; NOTES.txt
    is the one place an upgrading operator reliably looks, so the warning
    and the concrete fix (manual linking or REANA_AUTH_EMAIL_LINKING_*) must
    render there, not only live in a docstring/plan document nobody reads
    before running `helm upgrade`.
    """
    notes = _helm_install_dry_run("-f", str(VALUES_DEV))

    assert "idp_issuer" in notes or "idp_subject" in notes
    assert "REANA_AUTH_EMAIL_LINKING_ENABLED" in notes
    assert "create-admin-user" in notes


def test_notes_warn_that_maintenance_mode_blocks_the_migration_command():
    """The migration command and maintenance mode must not be ordered wrong.

    `maintenance.enabled: true` scales `<release>-server` itself to zero
    replicas, so `kubectl exec deployment/<release>-server -- reana-db
    alembic upgrade` -- the command NOTES.txt tells an operator to run for
    exactly this maintenance-window scenario -- has no pod to reach if
    maintenance mode is already on. NOTES.txt must say so explicitly, not
    just print the two steps in an order that silently doesn't work.

    The Helm test release name "reana-auth-test" is 15 characters, longer
    than the 13-character prefix every real Deployment name is actually
    built from (`reana.prefix`, see _helpers.tpl); every resource name
    printed here must use that truncated prefix ("reana-auth-te"), not the
    raw, untruncated release name, or an operator following these exact
    commands would target a Deployment that does not exist.
    """
    notes = _helm_install_dry_run("-f", str(VALUES_DEV))

    assert "maintenance.enabled" in notes
    assert "zero replicas" in notes
    assert "patch service/reana-auth-te-server --type=merge" in notes
    assert '"app":"reana-auth-te-server-maintenance-migration"' in notes
    assert "scale deployment/reana-auth-te-server --replicas=1" in notes
    assert "scale deployment/reana-auth-te-server --replicas=0" in notes
    assert "wait --for=delete pod -l app=reana-auth-te-server --timeout=5m" in notes
    assert "reana-auth-test-server" not in notes
    # The bundled database is also scaled to zero by maintenance mode, and
    # must be scaled back up alongside the server for the migration to have
    # anything to connect to.
    assert "scale deployment/reana-auth-te-db --replicas=1" in notes
    assert "rollout status deployment/reana-auth-te-db --timeout=5m" in notes
    assert "scale deployment/reana-auth-te-pgbouncer --replicas=1" in notes
    assert "rollout status deployment/reana-auth-te-pgbouncer --timeout=5m" in notes
    assert "rollout status deployment/reana-auth-te-server --timeout=5m" in notes
    database_scale = notes.index("scale deployment/reana-auth-te-db")
    database_ready = notes.index("rollout status deployment/reana-auth-te-db")
    pool_scale = notes.index("scale deployment/reana-auth-te-pgbouncer")
    pool_ready = notes.index("rollout status deployment/reana-auth-te-pgbouncer")
    server_scale = notes.index("scale deployment/reana-auth-te-server")
    server_ready = notes.index("rollout status deployment/reana-auth-te-server")
    migration = notes.index("reana-db alembic upgrade", server_ready)
    server_stop = notes.index("scale deployment/reana-auth-te-server --replicas=0")
    pods_stopped = notes.index(
        "wait --for=delete pod -l app=reana-auth-te-server --timeout=5m"
    )
    pool_stop = notes.index(
        "scale deployment/reana-auth-te-pgbouncer --replicas=0", pods_stopped
    )
    database_stop = notes.index(
        "scale deployment/reana-auth-te-db --replicas=0", pool_stop
    )
    selector_restore = notes.index('"app":"reana-auth-te-server"', database_stop)
    service_gate = notes.index("patch service/reana-auth-te-server")
    assert (
        service_gate
        < database_scale
        < database_ready
        < pool_scale
        < pool_ready
        < server_scale
        < server_ready
        < migration
        < server_stop
        < pods_stopped
        < pool_stop
        < database_stop
        < selector_restore
    )
    assert "helm upgrade" not in notes


def test_notes_use_fullname_override_for_real_resource_names():
    """NOTES commands must use the same overridden prefix as chart resources."""
    notes = _helm_install_dry_run(
        "-f",
        str(VALUES_DEV),
        "--set",
        "fullnameOverride=custom-override-name",
    )

    assert "deployment/custom-overri-db" in notes
    assert "deployment/custom-overri-server" in notes
    assert "service/custom-overri-server" in notes
    assert "app=custom-overri-server" in notes
    assert "deployment/reana-auth-te-server" not in notes


def test_notes_external_database_recovery_restores_pool_then_server():
    """External databases are not scaled, but the chart's pool still is."""
    notes = _helm_install_dry_run(
        "-f",
        str(VALUES_DEV),
        "--set",
        "keycloak.enabled=false",
        "--set",
        "components.reana_db.enabled=false",
        "--set",
        "auth.issuer=https://identity.example.org/realms/reana",
    )

    assert "scale deployment/reana-auth-te-db" not in notes
    assert "rollout status deployment/reana-auth-te-db" not in notes
    assert "scale deployment/reana-auth-te-pgbouncer --replicas=1" in notes
    assert "rollout status deployment/reana-auth-te-pgbouncer --timeout=5m" in notes
    assert "scale deployment/reana-auth-te-server --replicas=1" in notes
    assert "rollout status deployment/reana-auth-te-server --timeout=5m" in notes
    assert notes.index(
        "rollout status deployment/reana-auth-te-pgbouncer"
    ) < notes.index("scale deployment/reana-auth-te-server")
    assert "scale deployment/reana-auth-te-pgbouncer --replicas=0" in notes
    assert '"app":"reana-auth-te-server"' in notes


def test_notes_without_pgbouncer_do_not_print_pool_commands():
    """Direct database connections do not require a nonexistent pool Deployment."""
    notes = _helm_install_dry_run(
        "-f",
        str(VALUES_DEV),
        "--set",
        "pgbouncer.enabled=false",
    )

    assert "deployment/reana-auth-te-pgbouncer" not in notes
    assert "rollout status deployment/reana-auth-te-db --timeout=5m" in notes
    assert "rollout status deployment/reana-auth-te-server --timeout=5m" in notes
    assert "scale deployment/reana-auth-te-db --replicas=0" in notes
    assert '"app":"reana-auth-te-server"' in notes


def test_ephemeral_keycloak_storage_requires_opt_in_and_emits_warning():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "keycloak.database.mode=ephemeral",
        "--set",
        "secrets.keycloak.database_password=",
    )
    keycloak = _rendered_resource(rendered, "Deployment", "reana-keycloak")
    environment = _container_environment(keycloak, "keycloak")
    resources = [resource for resource in yaml.safe_load_all(rendered) if resource]
    notes = _helm_install_dry_run(
        "-f",
        str(VALUES_DEV),
        "--set",
        "keycloak.database.mode=ephemeral",
        "--set",
        "secrets.keycloak.database_password=",
    )

    assert "initContainers" not in keycloak["spec"]["template"]["spec"]
    assert environment["KC_DB"]["value"] == "dev-file"
    assert "KCRAW_DB_PASSWORD" not in environment
    assert (
        keycloak["spec"]["template"]["metadata"]["annotations"][
            "reana.io/keycloak-storage-warning"
        ]
        == "ephemeral-development-storage-data-will-be-lost"
    )
    assert not any(
        resource.get("kind") == "Secret"
        and resource.get("metadata", {}).get("name") == "reana-keycloak-database"
        for resource in resources
    )
    assert "WARNING: bundled Keycloak is using ephemeral development storage" in (notes)


@pytest.mark.parametrize(
    ("settings", "error"),
    (
        (
            ("keycloak.database.mode=invalid",),
            "keycloak.database.mode must be one of bundled, external, or ephemeral",
        ),
        (
            (
                "keycloak.database.mode=bundled",
                "components.reana_db.enabled=false",
            ),
            "keycloak.database.mode=bundled requires components.reana_db.enabled=true",
        ),
        (
            (
                "keycloak.database.mode=external",
                "keycloak.database.host=",
            ),
            "keycloak.database.host must be set",
        ),
        (
            (
                "keycloak.database.mode=external",
                "keycloak.database.host=postgres.identity.svc",
            ),
            "external Keycloak PostgreSQL with tls_mode=disabled requires",
        ),
        (
            ("keycloak.database.tls_mode=invalid",),
            "keycloak.database.tls_mode must be disabled or verify-server",
        ),
        (
            ("keycloak.database.name=reana",),
            "keycloak.database.name must not collide",
        ),
        (
            ("keycloak.database.username=postgres",),
            "keycloak.database.username must be a dedicated role",
        ),
        (
            (
                "keycloak.database.tls_mode=disabled",
                "keycloak.database.tls_truststore_existing_secret=database-ca",
            ),
            "tls_truststore_existing_secret requires",
        ),
    ),
)
def test_keycloak_database_configuration_fails_closed(settings, error):
    args = ["-f", str(VALUES_DEV)]
    for setting in settings:
        args.extend(("--set", setting))

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        _helm_template(*args)

    assert error in exc_info.value.stderr


def test_bundled_keycloak_ingress_controller_peers_are_configurable():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set-json",
        'keycloak.network_policy.ingress_controller_peers=[{"namespaceSelector":'
        '{"matchLabels":{"kubernetes.io/metadata.name":"ingress-system"}},'
        '"podSelector":{"matchLabels":{"app":"custom-ingress"}}}]',
    )

    network_policy = _rendered_resource(rendered, "NetworkPolicy", "reana-keycloak")
    assert network_policy["spec"]["ingress"][0]["from"] == [
        {"podSelector": {"matchLabels": {"app": "reana-server"}}},
        {
            "namespaceSelector": {
                "matchLabels": {"kubernetes.io/metadata.name": "ingress-system"}
            },
            "podSelector": {"matchLabels": {"app": "custom-ingress"}},
        },
    ]


def test_interactive_session_ingress_gets_referrer_policy_middleware():
    """Interactive-session URLs carry a bearer secret; Referer must not leak it.

    The per-session notebook secret necessarily rides in the session URL's
    query string (Jupyter's own auth model), which this chart cannot
    change. Referrer-Policy: no-referrer closes the one sub-vector fully
    within the chart's control: a notebook page loading any cross-origin
    subresource must not send the full URL to that third party.
    """
    rendered = _helm_template("-f", str(VALUES_DEV))
    controller = _rendered_resource(rendered, "Deployment", "reana-workflow-controller")
    environment = _container_environment(controller, "rest-api")
    annotations = json.loads(environment["REANA_INGRESS_ANNOTATIONS"]["value"])

    assert annotations["traefik.ingress.kubernetes.io/router.middlewares"] == (
        "default-reana-session-headers@kubernetescrd"
    )
    # The main /api, /keycloak, / ingress is unrelated to session URLs and
    # must not pick up the session-only middleware.
    ingress = _rendered_resource(rendered, "Ingress", "reana-ingress")
    assert "router.middlewares" not in " ".join(
        ingress["metadata"].get("annotations", {}).keys()
    )

    middleware = _rendered_resource(rendered, "Middleware", "reana-session-headers")
    assert middleware["spec"]["headers"]["referrerPolicy"] == "no-referrer"


def test_session_headers_middleware_is_namespaced_to_namespace_runtime():
    """The session-headers Middleware and its CRD-reference annotation must agree.

    PR976-19: the Middleware object and the
    ``router.middlewares`` annotation that references it must live in --
    and point at -- the same namespace. Session and Dask-dashboard Ingresses
    are created by reana-workflow-controller in ``namespace_runtime``, so
    both the Middleware and the annotation must follow ``namespace_runtime``
    rather than ``Release.Namespace`` in a split-topology deployment.
    """
    rendered = _helm_template(
        "-f", str(VALUES_DEV), "--set", "namespace_runtime=reana-runtime"
    )
    middleware = _rendered_resource(rendered, "Middleware", "reana-session-headers")
    assert middleware["metadata"]["namespace"] == "reana-runtime"

    controller = _rendered_resource(rendered, "Deployment", "reana-workflow-controller")
    environment = _container_environment(controller, "rest-api")
    annotations = json.loads(environment["REANA_INGRESS_ANNOTATIONS"]["value"])
    assert annotations["traefik.ingress.kubernetes.io/router.middlewares"] == (
        "reana-runtime-reana-session-headers@kubernetescrd"
    )


def test_session_headers_middleware_appends_to_an_existing_middlewares_annotation():
    """A user-supplied router.middlewares annotation must be extended, not clobbered."""
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "ingress.annotations.traefik\\.ingress\\.kubernetes\\.io/router\\.middlewares="
        "default-custom@kubernetescrd",
    )
    controller = _rendered_resource(rendered, "Deployment", "reana-workflow-controller")
    environment = _container_environment(controller, "rest-api")
    annotations = json.loads(environment["REANA_INGRESS_ANNOTATIONS"]["value"])

    assert annotations["traefik.ingress.kubernetes.io/router.middlewares"] == (
        "default-custom@kubernetescrd,default-reana-session-headers@kubernetescrd"
    )


def test_session_headers_middleware_survives_a_null_ingress_annotations_override():
    """ingress.annotations: null (the standard Helm idiom for "no defaults") must render.

    Sprig's `deepCopy` panics on a nil input; ingress.annotations has a
    non-empty chart default, so this was only reachable by an operator
    override, not caught by any shipped values profile.
    """
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "--set",
        "ingress.annotations=null",
    )
    controller = _rendered_resource(rendered, "Deployment", "reana-workflow-controller")
    environment = _container_environment(controller, "rest-api")
    annotations = json.loads(environment["REANA_INGRESS_ANNOTATIONS"]["value"])

    assert annotations == {
        "traefik.ingress.kubernetes.io/router.middlewares": (
            "default-reana-session-headers@kubernetescrd"
        )
    }


def test_cern_profile_renders_without_bundled_keycloak():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_CERN),
        "--set",
        "auth.audience=reana",
    )

    assert "https://auth.cern.ch/auth/realms/cern" in rendered
    assert 'value: "reana"' in rendered
    assert "REANA_AUTH_ROLE_SOURCES" not in rendered
    assert "REANA_GROUP_BACKEND_CERN_CLIENT_SECRET" not in rendered
    assert "name: reana-keycloak" not in rendered
    assert "LOGIN_PROVIDERS" not in rendered


def test_escape_profile_renders_single_auth_block_without_group_backend():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_ESCAPE),
        "--set",
        "auth.clientId=seeded-reana-client-id",
        "--set",
        "auth.webClientId=seeded-reana-client-id",
        "--set",
        "secrets.auth.REANA_AUTH_WEB_CLIENT_SECRET=seeded-reana-client-secret",
        "--set",
        "auth.indigoIamGroupBackend.enabled=false",
    )

    assert 'value: "https://iam.local"' in rendered
    assert 'value: "reana"' in rendered
    assert "https://iam.local/" not in rendered
    assert "REANA_AUTH_ROLE_SOURCES" not in rendered
    assert "REANA_GROUP_BACKEND" not in rendered
    assert 'value: "seeded-reana-client-id"' in rendered
    assert "REANA_AUTH_WEB_CLIENT_SECRET" in rendered
    assert base64.b64encode(b"seeded-reana-client-secret").decode("ascii") in rendered


def test_external_jwt_without_bff_does_not_require_web_client_secret():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_CERN),
        "--set",
        "auth.bffEnabled=false",
        "--set",
        "auth.audience=reana",
    )

    assert "https://auth.cern.ch/auth/realms/cern" in rendered
    assert "REANA_AUTH_WEB_CLIENT_SECRET" not in rendered
    assert "name: reana-auth-secrets" not in rendered


@pytest.mark.parametrize(
    "value,error",
    (
        ("auth.clientId=", "auth.clientId must be set"),
        ("auth.webClientId=", "auth.webClientId must be set"),
        ("auth.audience=", "auth.audience must be set"),
    ),
)
def test_external_issuer_rejects_empty_token_contract_values(value, error):
    """Invalid external issuer settings must fail before deployment."""
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        _helm_template(
            "-f",
            str(VALUES_DEV),
            "-f",
            str(VALUES_CERN),
            "--set",
            "auth.audience=reana",
            "--set",
            value,
        )

    assert error in exc_info.value.stderr


def test_external_jwt_only_mode_allows_an_empty_web_client_id():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_CERN),
        "--set",
        "auth.bffEnabled=false",
        "--set",
        "auth.webClientId=",
        "--set",
        "auth.audience=reana",
    )

    server = _rendered_resource(rendered, "Deployment", "reana-server")
    environment = _container_environment(server, "rest-api")
    assert environment["REANA_AUTH_CLIENT_ID"]["value"] == "reana-cli"
    assert environment["REANA_AUTH_WEB_CLIENT_ID"]["value"] == ""


def test_auth_profiles_render_jwt_only_configuration():
    cern_rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_CERN),
        "--set",
        "auth.audience=reana",
    )
    eosc_rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_EOSC),
        "--set",
        "auth.bffEnabled=false",
        "--set",
        "auth.clientId=eosc-cli",
        "--set",
        "auth.audience=eosc-cli",
    )

    assert "core-proxy.sandbox.eosc-beyond.eu" in eosc_rendered
    assert 'value: "reana"' in eosc_rendered
    for rendered in (cern_rendered, eosc_rendered):
        assert "REANA_AUTH_TOKEN_VALIDATION" not in rendered
        assert "REANA_AUTH_INTROSPECTION" not in rendered
        assert "REANA_AUTH_EOSC_REQUIRED_ENTITLEMENT" not in rendered
        assert "REANA_AUTH_ROLE_SOURCES" not in rendered
        assert "entitlements" not in rendered
        assert "wlcg.groups" not in rendered


def test_bundled_keycloak_admin_is_linked_by_stable_subject():
    script = CREATE_ADMIN_SCRIPT.read_text()

    keycloak_user_creation = script.index('"${keycloak_cmd}" create users')
    reana_user_creation = script.index("flask reana-admin create-admin-user")
    assert keycloak_user_creation < reana_user_creation
    assert '--idp-issuer "${auth_issuer}"' in script
    assert '--idp-subject "${keycloak_user_id}"' in script
    assert '--rolename "${keycloak_required_role}"' in script
    assert "--rolename reana:user" not in script
    assert '--password "${admin_password}"' not in script
    assert "admin-access-token" not in script


@pytest.mark.parametrize("script_path", AUTHENTICATED_TEST_SCRIPTS)
def test_operational_scripts_use_only_bearer_authentication(script_path):
    """Operational probes must follow the OIDC-only server contract."""
    script = script_path.read_text()

    assert "Authorization: Bearer ${access_token}" in script
    assert "REANA_ACCESS_TOKEN is required" in script
    assert "?access_token=" not in script
    assert "&access_token=" not in script
    assert "ADMIN_ACCESS_TOKEN" not in script
    assert "admin-access-token" not in script


def test_external_issuer_admin_setup_is_a_successful_noop(tmp_path):
    """External issuer deployments must not fail while awaiting identity linking."""
    fake_kubectl = tmp_path / "kubectl"
    fake_kubectl.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  *"get deployment/reana-keycloak"*) exit 1 ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    fake_kubectl.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"

    result = subprocess.run(
        [str(CREATE_ADMIN_SCRIPT), "default", "reana", "admin@example.org", "pw"],
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0
    assert "skipping automatic administrator creation" in result.stdout
    assert "Before the administrator's first REANA login" in result.stdout
    assert "--idp-subject <subject>" in result.stdout


def test_cern_profile_can_enable_cern_group_backend():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_CERN),
        "--set",
        "auth.cernGroupBackend.enabled=true",
        "--set",
        "auth.webClientId=alex-test-groups",
        "--set",
        "auth.audience=reana",
    )

    assert "REANA_GROUP_BACKENDS" in rendered
    assert '\\"type\\":\\"cern\\"' in rendered
    assert '\\"provider\\":\\"cern\\"' in rendered
    assert '\\"client_id\\":\\"alex-test-groups\\"' in rendered
    assert '\\"client_secret_env\\":\\"REANA_AUTH_WEB_CLIENT_SECRET\\"' in rendered
    assert "REANA_GROUP_BACKEND_CERN_CLIENT_SECRET" not in rendered


def test_escape_profile_renders_indigo_iam_backend():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_ESCAPE),
        "--set",
        "auth.clientId=seeded-reana-client-id",
        "--set",
        "auth.webClientId=seeded-reana-client-id",
        "--set",
        "auth.indigoIamGroupBackend.clientId=seeded-scim-client-id",
        "--set",
        "secrets.auth.REANA_AUTH_WEB_CLIENT_SECRET=seeded-reana-client-secret",
        "--set",
        "secrets.auth.REANA_GROUP_BACKEND_INDIGO_IAM_CLIENT_SECRET=seeded-scim-secret",
    )

    assert "https://iam.local" in rendered
    assert "REANA_GROUP_BACKEND_INDIGO_IAM_CLIENT_SECRET" in rendered
    assert '\\"type\\":\\"indigo_iam\\"' in rendered
    assert '\\"provider\\":\\"escape\\"' in rendered
    assert '\\"base_url\\":\\"https://iam.local\\"' in rendered
    assert '\\"client_id\\":\\"seeded-scim-client-id\\"' in rendered
    assert "name: reana-keycloak" not in rendered
