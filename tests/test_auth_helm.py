# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for auth-related Helm rendering."""

import shutil
import subprocess
from pathlib import Path

import pytest


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

    assert "REANA_AUTH_ISSUER" in rendered
    assert "https://localhost:30443/keycloak/realms/reana" in rendered
    assert "name: reana-auth-secrets" in rendered
    assert "key: REANA_AUTH_WEB_CLIENT_SECRET" in rendered
    assert "name: reana-keycloak" in rendered
    assert "jane@example.org" not in rendered
    assert 'value: "admin"' not in rendered
    assert "LOGIN_PROVIDERS" not in rendered
    assert "CERN_CONSUMER" not in rendered
    assert "EOSC_CONSUMER" not in rendered


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
        "secrets.auth.REANA_AUTH_WEB_CLIENT_SECRET=reana-server-secret",
    )

    assert 'value: "https://iam.local"' in rendered
    assert 'value: "reana"' in rendered
    assert "https://iam.local/" not in rendered
    assert "REANA_AUTH_ROLE_SOURCES" not in rendered
    assert "REANA_GROUP_BACKEND" not in rendered


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
