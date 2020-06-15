#!/bin/bash

instance_name=$1

# Get REANA Server pod name
REANA_SERVER=$(kubectl get pod -l "app=$instance_name-server" | grep Running | awk '{print $1}')

# Initialise DB
kubectl exec "$REANA_SERVER" -- ./scripts/setup

# Create admin user
admin_access_token=$(kubectl exec "$REANA_SERVER" -- \
                     flask reana-admin create-admin-user admin@reana.org)

# Add token to secrets
kubectl create secret generic "$instance_name"-admin-access-token \
      --from-literal=ADMIN_ACCESS_TOKEN="$admin_access_token"
