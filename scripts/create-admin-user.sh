#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020, 2024, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

set -e

# Read inputs: kubernetes namespace, instance name, admin user email,
# admin user password for bundled Keycloak, optional Helm resource prefix.
if [ "$#" -ne 4 ] && [ "$#" -ne 5 ]; then
    echo "Error: Invalid number of parameters."
    echo "Usage: $0 <kubernetes_namespace> <instance_name> <admin_email> <admin_password> [resource_prefix]"
    echo "Example: $0 reana reana john.doe@example.org mysecretpassword reana"
    exit 1
fi
kubernetes_namespace=$1
instance_name=$2
admin_email=$3
admin_password=$4
resource_prefix=${5:-$instance_name}

# Wait for database to be ready
while [ "0" -ne "$(kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-db" -- pg_isready -U reana -h 127.0.0.1 -p 5432 &>/dev/null && echo $? || echo 1)" ]; do
    echo "Waiting for deployment/${resource_prefix}-db to be ready..."
    sleep 5
done

# Initialise database
kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-server" -c rest-api -- ./scripts/create-database.sh

# Create and link a user in bundled Keycloak when it is deployed.
if kubectl -n "${kubernetes_namespace}" get "deployment/${resource_prefix}-keycloak" &>/dev/null; then
    keycloak_admin_user=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
            printenv KC_BOOTSTRAP_ADMIN_USERNAME
    )
    # The admin password itself is read directly from KC_BOOTSTRAP_ADMIN_PASSWORD
    # inside the remote kcadm.sh invocation below, not round-tripped through a
    # local variable here.
    keycloak_relative_path=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
            printenv KC_HTTP_RELATIVE_PATH
    )
    keycloak_realm=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
            printenv REANA_KEYCLOAK_REALM
    )
    keycloak_required_role=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
            printenv REANA_KEYCLOAK_REQUIRED_ROLE
    )
    keycloak_server_url="http://localhost:8080${keycloak_relative_path:-/keycloak}"
    keycloak_cmd="/opt/keycloak/bin/kcadm.sh"

    # KC_CLI_PASSWORD is read by kcadm.sh in place of --password/--new-password
    # when those flags are omitted, so the admin password never appears in
    # this container's argv (visible via `ps`/`/proc/<pid>/cmdline` to
    # anything with exec/process-list access, independent of any Secret
    # RBAC). It is set here from KC_BOOTSTRAP_ADMIN_PASSWORD, which is
    # already present in the target container's own environment (set by its
    # Deployment spec) -- referencing it inside the single-quoted remote
    # script expands it in the remote shell, never touching this script's
    # own argv or the `kubectl exec` command line either.
    # shellcheck disable=SC2016 # intentional: expands in the remote shell, not here.
    kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
        sh -c 'KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" "$1" config credentials --server "$2" --realm master --user "$3"' \
        _ "${keycloak_cmd}" "${keycloak_server_url}" "${keycloak_admin_user}"

    keycloak_user_id=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
            "${keycloak_cmd}" get users -r "${keycloak_realm}" \
            -q "username=${admin_email}" -q exact=true \
            --fields id --format csv --noquotes
    )
    if [ -z "${keycloak_user_id}" ]; then
        keycloak_user_id=$(
            kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
                "${keycloak_cmd}" create users -r "${keycloak_realm}" -i \
                -s "username=${admin_email}" \
                -s "email=${admin_email}" \
                -s enabled=true \
                -s emailVerified=true
        )
    fi

    # Known limitation, verified empirically rather than assumed: unlike
    # `config credentials`, kcadm.sh's `set-password` requires a real Java
    # Console for its interactive password prompt and rejects a plain
    # `kubectl exec -i` stdin pipe ("Console is not active, but password is
    # required"), and this kubectl version has no `exec --env` to inject
    # KC_CLI_PASSWORD without an argv. admin_password is operator-supplied
    # (this script's own $4), not already present in the target container's
    # environment the way KC_BOOTSTRAP_ADMIN_PASSWORD is above, so there is
    # no available mechanism here that avoids it appearing in this
    # container's argv. Writing it to a temp file first would trade this
    # exposure for a filesystem one without a clear improvement.
    kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
        "${keycloak_cmd}" set-password -r "${keycloak_realm}" \
        --userid "${keycloak_user_id}" --new-password "${admin_password}"
    kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
        "${keycloak_cmd}" add-roles -r "${keycloak_realm}" --uid "${keycloak_user_id}" \
        --rolename "${keycloak_required_role}" \
        --rolename reana:admin \
        --rolename offline_access

    auth_issuer=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-server" -c rest-api -- \
            printenv REANA_AUTH_ISSUER
    )
    kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-server" -c rest-api -- \
        flask reana-admin create-admin-user \
        --email "${admin_email}" \
        --idp-issuer "${auth_issuer}" \
        --idp-subject "${keycloak_user_id}"
    setup_result="Database initialised and bundled-Keycloak administrator created."
else
    echo "Bundled Keycloak is not deployed; skipping automatic administrator creation."
    echo "Before the administrator's first REANA login, obtain their issuer and subject from the external identity provider and run:"
    printf '  kubectl -n %s exec deployment/%s-server -c rest-api -- \\\n' \
        "${kubernetes_namespace}" "${resource_prefix}"
    echo "    flask reana-admin create-admin-user --email ${admin_email} --idp-issuer <issuer> --idp-subject <subject>"
    setup_result="Database initialised; external-issuer administrator creation was skipped."
fi

# Success!
echo "Success! ${setup_result}"
echo "You may now set the following environment variables:"
echo ""
echo "  $ export REANA_SERVER_URL=https://localhost:30443  # or use your URL"
echo ""
echo "Run 'reana-client login' before using the command line client."
echo "Please see http://docs.reana.io/getting-started/ on how to run your first REANA example."
