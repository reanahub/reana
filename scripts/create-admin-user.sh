#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# Read inputs: instance name, admin user email, admin user password
instance_name=$1
if [ -z "$instance_name" ]; then
    echo 'Instance name missing.'
    exit 1
fi
admin_email=$2
if [ -z "$admin_email" ]; then
    echo 'Admin user email address missing.'
    exit 1
fi
admin_password=$3
if [ -z "$admin_password" ]; then
    echo 'Admin user password missing.'
    exit 1
fi

# Wait for database to be ready
while [ "0" -ne "$(kubectl exec deployment/reana-db -- pg_isready -U reana -h 127.0.0.1 -p 5432 &> /dev/null && echo $? || echo 1)" ]
do
    echo "Waiting for deployment/reana-db to be ready..."
    sleep 5
done

# Initialise database
kubectl exec deployment/reana-server -c rest-api -- ./scripts/create-database.sh

# Create admin user
if ! admin_access_token=$(kubectl exec deployment/reana-server -c rest-api -- \
    flask reana-admin create-admin-user --email "$admin_email" --password "$admin_password")
then
    # Output failures
    echo "$admin_access_token"
    exit 1
fi

# Add token to secrets
kubectl create secret generic "$instance_name"-admin-access-token \
      --from-literal=ADMIN_ACCESS_TOKEN="$admin_access_token"
