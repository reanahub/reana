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
    assert environment["REANA_AUTH_OPENID_CONFIG_URL"]["value"] == (
        "http://reana-keycloak:8080/keycloak/realms/reana/"
        ".well-known/openid-configuration"
    )
    assert environment["REANA_AUTH_AUTHORIZATION_URL"]["value"] == (
        "https://localhost:30443/keycloak/realms/reana/"
        "protocol/openid-connect/auth"
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
        "podSelector": {
            "matchLabels": {"app.kubernetes.io/name": "traefik"}
        }
    } in allowed_sources
    assert "name: reana-auth-secrets" in rendered
    assert "key: REANA_AUTH_WEB_CLIENT_SECRET" in rendered
    assert "name: reana-keycloak" in rendered
    assert "jane@example.org" not in rendered
    assert 'value: "admin"' not in rendered
    assert "LOGIN_PROVIDERS" not in rendered
    assert "CERN_CONSUMER" not in rendered
    assert "EOSC_CONSUMER" not in rendered


def test_bundled_keycloak_http_backchannel_requires_explicit_opt_in():
    """Enabling bundled HTTP without the explicit risk choice fails rendering."""
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        _helm_template(
            "-f",
            str(VALUES_DEV),
            "--set",
            "keycloak.backchannel_allow_http=false",
        )

    assert "keycloak.backchannel_allow_http=true explicitly" in (
        exc_info.value.stderr
    )


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
    )
    server = _rendered_resource(rendered, "Deployment", "reana-server")
    environment = _container_environment(server, "rest-api")

    assert environment["REANA_AUTH_BACKCHANNEL_BASE_URL"]["value"] == (
        "https://keycloak.internal/realms/reana"
    )
    assert environment["REANA_AUTH_BACKCHANNEL_ALLOW_HTTP"]["value"] == "false"
    assert environment["REANA_AUTH_CA_BUNDLE"]["value"] == (
        "/etc/reana/idp-ca.pem"
    )


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
        "secrets.auth.REANA_AUTH_WEB_CLIENT_SECRET=custom-web-secret",
    )

    realm_secret = _rendered_resource(rendered, "Secret", "reana-keycloak-realm")
    realm = json.loads(realm_secret["stringData"]["reana-realm.json"])
    web_client, cli_client = realm["clients"]
    keycloak = _rendered_resource(rendered, "Deployment", "reana-keycloak")
    environment = _container_environment(keycloak, "keycloak")

    assert realm["realm"] == "custom-realm"
    assert web_client["clientId"] == "custom-web"
    assert cli_client["clientId"] == "custom-cli"
    assert web_client["secret"] == "custom-web-secret"
    assert web_client["redirectUris"] == [
        "https://reana.example.org/api/oauth/callback"
    ]
    for client in realm["clients"]:
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


def test_cern_profile_renders_without_bundled_keycloak():
    rendered = _helm_template("-f", str(VALUES_DEV), "-f", str(VALUES_CERN))

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
    )

    assert 'value: "https://iam.local"' in rendered
    assert 'value: "reana"' in rendered
    assert "https://iam.local/" not in rendered
    assert "REANA_AUTH_ROLE_SOURCES" not in rendered
    assert "REANA_GROUP_BACKEND" not in rendered
    assert 'value: "seeded-reana-client-id"' in rendered
    assert "REANA_AUTH_WEB_CLIENT_SECRET" in rendered
    assert (
        base64.b64encode(b"seeded-reana-client-secret").decode("ascii") in rendered
    )


def test_external_jwt_without_bff_does_not_require_web_client_secret():
    rendered = _helm_template(
        "-f",
        str(VALUES_DEV),
        "-f",
        str(VALUES_CERN),
        "--set",
        "auth.bffEnabled=false",
    )

    assert "https://auth.cern.ch/auth/realms/cern" in rendered
    assert "REANA_AUTH_WEB_CLIENT_SECRET" not in rendered
    assert "name: reana-auth-secrets" not in rendered


def test_auth_profiles_render_jwt_only_configuration():
    cern_rendered = _helm_template("-f", str(VALUES_DEV), "-f", str(VALUES_CERN))
    eosc_rendered = _helm_template("-f", str(VALUES_DEV), "-f", str(VALUES_EOSC))

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
    assert '--password "${admin_password}"' not in script
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
