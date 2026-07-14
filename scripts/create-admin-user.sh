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
    keycloak_admin_password=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
            printenv KC_BOOTSTRAP_ADMIN_PASSWORD
    )
    keycloak_relative_path=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
            printenv KC_HTTP_RELATIVE_PATH
    )
    keycloak_realm=$(
        kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
            printenv REANA_KEYCLOAK_REALM
    )
    keycloak_server_url="http://localhost:8080${keycloak_relative_path:-/keycloak}"
    keycloak_cmd="/opt/keycloak/bin/kcadm.sh"

    kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
        "${keycloak_cmd}" config credentials \
            --server "${keycloak_server_url}" \
            --realm master \
            --user "${keycloak_admin_user}" \
            --password "${keycloak_admin_password}"

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

    kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
        "${keycloak_cmd}" set-password -r "${keycloak_realm}" \
            --userid "${keycloak_user_id}" --new-password "${admin_password}"
    kubectl -n "${kubernetes_namespace}" exec "deployment/${resource_prefix}-keycloak" -- \
        "${keycloak_cmd}" add-roles -r "${keycloak_realm}" --uid "${keycloak_user_id}" \
            --rolename reana:user \
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
else
    echo "Error: Bundled Keycloak is not deployed; the OIDC subject cannot be discovered automatically."
    echo "Create the administrator after obtaining their issuer and subject from the external identity provider:"
    printf '  kubectl -n %s exec deployment/%s-server -c rest-api -- \\\n' \
        "${kubernetes_namespace}" "${resource_prefix}"
    echo "    flask reana-admin create-admin-user --email ${admin_email} --idp-issuer <issuer> --idp-subject <subject>"
    exit 1
fi

# Success!
echo "Success! You may now set the following environment variables:"
echo ""
echo "  $ export REANA_SERVER_URL=https://localhost:30443  # or use your URL"
echo ""
echo "Run 'reana-client login' before using the command line client."
echo "Please see http://docs.reana.io/getting-started/ on how to run your first REANA example."
