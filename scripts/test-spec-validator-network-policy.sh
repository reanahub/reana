#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

set -euo pipefail

usage() {
    cat <<EOF
Usage: $0 [namespace] [instance-name] [expect-public-egress]

Verify live CNI enforcement of the specification-validator NetworkPolicy.

Arguments:
  namespace             Kubernetes namespace. [default: default]
  instance-name         REANA Helm release name. [default: reana]
  expect-public-egress  Whether public egress should work: true or false.
                        [default: true]

Environment variables:
  REANA_SERVER_URL
      Public REANA URL used to trigger policy reconciliation.
      [default: https://localhost:30443]
  REANA_ACCESS_TOKEN
      Access token used for validation. When unset, read it from the
      <instance-name>-admin-access-token Kubernetes Secret.
  REANA_WORKFLOW_VALIDATOR_IMAGE
      Image used by the probe pod.
      [default: docker.io/reanahub/reana-workflow-validator]
  REANA_NETWORK_POLICY_TEST_IMAGE_PULL_POLICY
      Probe image pull policy. [default: IfNotPresent]
  REANA_NETWORK_POLICY_TEST_PUBLIC_HOST
      Public IP tested for egress. [default: 1.1.1.1]
  REANA_NETWORK_POLICY_TEST_PUBLIC_PORT
      Public TCP port tested for egress. [default: 443]
  REANA_NETWORK_POLICY_TEST_NODE_PORT
      Resident-node TCP port reported for information. [default: 10250]
  REANA_NETWORK_POLICY_TEST_TIMEOUT
      Maximum number of seconds to wait for the probe. [default: 60]
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

if [ "$#" -gt 3 ]; then
    usage >&2
    exit 2
fi

kubernetes_namespace=${1:-default}
instance_name=${2:-reana}
expect_public_egress=${3:-true}
server_url=${REANA_SERVER_URL:-https://localhost:30443}
validator_image=${REANA_WORKFLOW_VALIDATOR_IMAGE:-docker.io/reanahub/reana-workflow-validator}
image_pull_policy=${REANA_NETWORK_POLICY_TEST_IMAGE_PULL_POLICY:-IfNotPresent}
public_host=${REANA_NETWORK_POLICY_TEST_PUBLIC_HOST:-1.1.1.1}
public_port=${REANA_NETWORK_POLICY_TEST_PUBLIC_PORT:-443}
node_port=${REANA_NETWORK_POLICY_TEST_NODE_PORT:-10250}
timeout_seconds=${REANA_NETWORK_POLICY_TEST_TIMEOUT:-60}

case "${expect_public_egress}" in
true | false) ;;
*)
    echo "Error: expect-public-egress must be 'true' or 'false'." >&2
    exit 2
    ;;
esac

case "${timeout_seconds}" in
'' | *[!0-9]*)
    echo "Error: REANA_NETWORK_POLICY_TEST_TIMEOUT must be an integer." >&2
    exit 2
    ;;
esac

for required_command in kubectl curl base64 grep; do
    if ! command -v "${required_command}" >/dev/null 2>&1; then
        echo "Error: required command '${required_command}' was not found." >&2
        exit 2
    fi
done

policy_name="${instance_name}-spec-validator-egress"
service_name="${instance_name}-server"
admin_secret_name="${instance_name}-admin-access-token"
probe_pod_name="${instance_name}-spec-validator-network-test"
temporary_directory=$(mktemp -d)

# Invoked indirectly by the EXIT trap below.
# shellcheck disable=SC2329
cleanup() {
    kubectl -n "${kubernetes_namespace}" delete pod "${probe_pod_name}" \
        --ignore-not-found=true --wait=false >/dev/null 2>&1 || true
    rm -rf "${temporary_directory}"
}
trap cleanup EXIT

echo "Preparing validator NetworkPolicy in namespace '${kubernetes_namespace}'..."

access_token=${REANA_ACCESS_TOKEN:-}
if [ -z "${access_token}" ]; then
    encoded_access_token=$(kubectl -n "${kubernetes_namespace}" get secret \
        "${admin_secret_name}" -o jsonpath='{.data.ADMIN_ACCESS_TOKEN}')
    access_token=$(printf '%s' "${encoded_access_token}" | base64 --decode)
fi

cat >"${temporary_directory}/reana.yaml" <<'EOF'
version: 0.9.0
workflow:
  type: snakemake
  file: Snakefile
EOF

cat >"${temporary_directory}/Snakefile" <<'EOF'
rule all:
    shell:
        "true"
EOF

validation_status=$(curl --silent --show-error --insecure \
    --output "${temporary_directory}/validation-response.json" \
    --write-out '%{http_code}' \
    --form "reana.yaml=@${temporary_directory}/reana.yaml;filename=reana.yaml" \
    --form "Snakefile=@${temporary_directory}/Snakefile;filename=Snakefile" \
    "${server_url%/}/api/workflows/validate?access_token=${access_token}")

if [ "${validation_status}" != "200" ] ||
    ! grep -Eq '"valid"[[:space:]]*:[[:space:]]*true' \
        "${temporary_directory}/validation-response.json"; then
    echo "Error: could not reconcile the validator policy through validation." >&2
    echo "HTTP status: ${validation_status}" >&2
    cat "${temporary_directory}/validation-response.json" >&2
    exit 1
fi

if ! kubectl -n "${kubernetes_namespace}" get networkpolicy \
    "${policy_name}" >/dev/null; then
    echo "Error: NetworkPolicy '${policy_name}' was not created." >&2
    exit 1
fi

policy_selector=$(kubectl -n "${kubernetes_namespace}" get networkpolicy \
    "${policy_name}" -o jsonpath='{.spec.podSelector.matchLabels.app}')
if [ "${policy_selector}" != "reana-spec-validator" ]; then
    echo "Error: NetworkPolicy '${policy_name}' does not select validator pods." >&2
    exit 1
fi

cluster_service_ip=$(kubectl -n "${kubernetes_namespace}" get service \
    "${service_name}" -o jsonpath='{.spec.clusterIP}')
cluster_service_port=$(kubectl -n "${kubernetes_namespace}" get service \
    "${service_name}" -o jsonpath='{.spec.ports[0].port}')
cluster_pod_ip=$(kubectl -n "${kubernetes_namespace}" get pod \
    -l "app=${service_name}" -o jsonpath='{.items[0].status.podIP}')
cluster_pod_port=$(kubectl -n "${kubernetes_namespace}" get service \
    "${service_name}" -o jsonpath='{.spec.ports[0].targetPort}')

if [ -z "${cluster_pod_ip}" ]; then
    echo "Error: no backing pod was found for Service '${service_name}'." >&2
    exit 1
fi

kubectl -n "${kubernetes_namespace}" delete pod "${probe_pod_name}" \
    --ignore-not-found=true --wait=true >/dev/null

cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: ${probe_pod_name}
  namespace: ${kubernetes_namespace}
  labels:
    app: reana-spec-validator
spec:
  automountServiceAccountToken: false
  enableServiceLinks: false
  restartPolicy: Never
  containers:
    - name: probe
      image: ${validator_image}
      imagePullPolicy: ${image_pull_policy}
      command:
        - python3
        - -c
      args:
        - |
          import os
          import socket
          import sys

          def probe(name, host, port):
              try:
                  with socket.create_connection((host, int(port)), timeout=5):
                      reachable = True
                      detail = "connected"
              except Exception as error:
                  reachable = False
                  detail = type(error).__name__
              state = "reachable" if reachable else "blocked"
              print(f"RESULT {name} {state} {detail}", flush=True)
              return reachable

          cluster_reachable = probe(
              "cluster-service",
              os.environ["CLUSTER_SERVICE_IP"],
              os.environ["CLUSTER_SERVICE_PORT"],
          )
          cluster_pod_reachable = probe(
              "cluster-pod",
              os.environ["CLUSTER_POD_IP"],
              os.environ["CLUSTER_POD_PORT"],
          )
          public_reachable = probe(
              "public-internet",
              os.environ["PUBLIC_HOST"],
              os.environ["PUBLIC_PORT"],
          )
          probe(
              "resident-node",
              os.environ["NODE_IP"],
              os.environ["NODE_PORT"],
          )

          failures = []
          if cluster_reachable:
              failures.append("cluster-service traffic was not blocked")
          if cluster_pod_reachable:
              failures.append("cluster-pod traffic was not blocked")
          expect_public = os.environ["EXPECT_PUBLIC_EGRESS"] == "true"
          if public_reachable != expect_public:
              expected = "reachable" if expect_public else "blocked"
              failures.append(f"public internet was expected to be {expected}")

          if failures:
              print("FAIL " + "; ".join(failures), flush=True)
              sys.exit(1)
          print("PASS required egress behavior was enforced", flush=True)
      env:
        - name: CLUSTER_SERVICE_IP
          value: "${cluster_service_ip}"
        - name: CLUSTER_SERVICE_PORT
          value: "${cluster_service_port}"
        - name: CLUSTER_POD_IP
          value: "${cluster_pod_ip}"
        - name: CLUSTER_POD_PORT
          value: "${cluster_pod_port}"
        - name: PUBLIC_HOST
          value: "${public_host}"
        - name: PUBLIC_PORT
          value: "${public_port}"
        - name: NODE_IP
          valueFrom:
            fieldRef:
              fieldPath: status.hostIP
        - name: NODE_PORT
          value: "${node_port}"
        - name: EXPECT_PUBLIC_EGRESS
          value: "${expect_public_egress}"
      resources:
        requests:
          cpu: 50m
          memory: 64Mi
        limits:
          cpu: 250m
          memory: 128Mi
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop:
            - ALL
        readOnlyRootFilesystem: true
        runAsGroup: 0
        runAsNonRoot: true
        runAsUser: 1000
        seccompProfile:
          type: RuntimeDefault
EOF

deadline=$((SECONDS + timeout_seconds))
while [ "${SECONDS}" -lt "${deadline}" ]; do
    probe_phase=$(kubectl -n "${kubernetes_namespace}" get pod \
        "${probe_pod_name}" -o jsonpath='{.status.phase}')
    case "${probe_phase}" in
    Succeeded)
        kubectl -n "${kubernetes_namespace}" logs "${probe_pod_name}"
        echo "Success: validator NetworkPolicy behavior matches the deployment."
        exit 0
        ;;
    Failed)
        kubectl -n "${kubernetes_namespace}" logs "${probe_pod_name}" || true
        echo "Error: validator NetworkPolicy probe failed." >&2
        exit 1
        ;;
    esac
    sleep 1
done

kubectl -n "${kubernetes_namespace}" logs "${probe_pod_name}" || true
kubectl -n "${kubernetes_namespace}" describe pod "${probe_pod_name}" >&2 || true
echo "Error: validator NetworkPolicy probe timed out." >&2
exit 1
