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

# Wait for DB to be ready
REANA_DB=$(kubectl get pod -l "app=$instance_name-db" | grep Running | awk '{print $1}')
echo $REANA_DB
while [ "0" -ne "$(kubectl exec "$REANA_DB" -- pg_isready -U reana -h 127.0.0.1 -p 5432 &> /dev/null && echo $? || echo 1)" ]
do
    echo "Waiting for REANA-DB to be ready."
    sleep 5;
done
echo "REANA-DB ready"

# Initialise DB
kubectl exec "$REANA_SERVER" -- ./scripts/setup

# Create admin user
admin_access_token=$(kubectl exec "$REANA_SERVER" -- \
                     flask reana-admin create-admin-user $email_address)

# Add token to secrets
kubectl create secret generic "$instance_name"-admin-access-token \
      --from-literal=ADMIN_ACCESS_TOKEN="$admin_access_token"
