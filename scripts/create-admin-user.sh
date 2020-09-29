#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# Read inputs: kubernetes namespace, instance name, admin user email, admin user password
if [ "$#" -ne 4 ]; then
    echo "Error: Invalid number of parameters."
    echo "Usage: $0 <kubernetes_namespace> <instance_name> <admin_email> <admin_password>"
    echo "Example: $0 reana reana john.doe@example.org mysecretpassword"
    exit 1
fi
kubernetes_namespace=$1
instance_name=$2
admin_email=$3
admin_password=$4

# Wait for database to be ready
while [ "0" -ne "$(kubectl -n "${kubernetes_namespace}" exec "deployment/${instance_name}-db" -- pg_isready -U reana -h 127.0.0.1 -p 5432 &> /dev/null && echo $? || echo 1)" ]
do
    echo "Waiting for deployment/${instance_name}-db to be ready..."
    sleep 5
done

# Initialise database
kubectl -n "${kubernetes_namespace}" exec "deployment/${instance_name}-server" -c rest-api -- ./scripts/create-database.sh

# Create admin user
if ! admin_access_token=$(kubectl -n "${kubernetes_namespace}" exec "deployment/${instance_name}-server" -c rest-api -- \
    flask reana-admin create-admin-user --email "${admin_email}" --password "${admin_password}")
then
    # Output failures
    echo "${admin_access_token}"
    exit 1
fi

# Add token to secrets
kubectl -n "${kubernetes_namespace}" create secret generic "${instance_name}"-admin-access-token \
      --from-literal=ADMIN_ACCESS_TOKEN="${admin_access_token}"

# Success!
echo "Success! You may now set the following environment variables:"
echo ""
echo "  $ export REANA_SERVER_URL=https://localhost:30443  # or use your URL"
echo "  $ export REANA_ACCESS_TOKEN=${admin_access_token}"
echo ""
echo "Please see http://docs.reana.io/getting-started/ on how to run your first REANA example."
