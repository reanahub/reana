#!/bin/bash

# Two parameters: instance name and email address of the admin
instance_name=$1
if [ -z "$instance_name" ]; then
    instance_name=reana
fi
email_address=$2
if [ -z "$email_address" ]; then
    email_address=root@localhost
fi

# Get REANA Server pod name
REANA_SERVER=$(kubectl get pod -l "app=$instance_name-server" | grep Running | awk '{print $1}')

# Initialise DB
kubectl exec "$REANA_SERVER" -- ./scripts/setup

# Create admin user
admin_access_token=$(kubectl exec "$REANA_SERVER" -- \
                     flask reana-admin create-admin-user $email_address)

# Add token to secrets
kubectl create secret generic "$instance_name"-admin-access-token \
      --from-literal=ADMIN_ACCESS_TOKEN="$admin_access_token"
