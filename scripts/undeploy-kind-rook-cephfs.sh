#!/bin/sh
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

set -eu

STATE_HOME="${XDG_STATE_HOME:-${HOME:-.}/.local/state}"
STATE_FILE="${1:-${REANA_DEV_CEPHFS_STATE_FILE:-${STATE_HOME}/reana-dev/kind-cephfs.state}}"
ROOK_VERSION="${ROOK_VERSION:-v1.19.6}"
ROOK_NAMESPACE="rook-ceph"
SMOKE_NAMESPACE="rook-cephfs-smoke"
NODE_CONTAINER="kind-control-plane"
if [ -f "${STATE_FILE}" ]; then
    persisted_node_container="$(awk -F '\t' '$1 == "node_container" { print $2; exit }' "${STATE_FILE}")"
    NODE_CONTAINER="${persisted_node_container:-${NODE_CONTAINER}}"
fi

kube() {
    kubectl --request-timeout=10s "$@"
}

wait_until_deleted() {
    namespace="$1"
    resource="$2"
    timeout_seconds="$3"

    for _ in $(seq 1 "${timeout_seconds}"); do
        if [ -n "${namespace}" ]; then
            exists="$(kube -n "${namespace}" get "${resource}" -o name 2>/dev/null || true)"
        else
            exists="$(kube get "${resource}" -o name 2>/dev/null || true)"
        fi
        [ -z "${exists}" ] && return 0
        sleep 1
    done
    return 1
}

dump_diagnostics() {
    echo "Rook teardown diagnostics:" >&2
    kube -n "${ROOK_NAMESPACE}" get cephcluster,cephfilesystem,cephblockpool,pods 2>/dev/null || true
    kube get pvc -A -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,STORAGECLASS:.spec.storageClassName,PHASE:.status.phase' 2>/dev/null || true
}

if ! kube get namespace "${ROOK_NAMESPACE}" >/dev/null 2>&1; then
    if kube get namespace default >/dev/null 2>&1; then
        echo "Rook namespace ${ROOK_NAMESPACE} is already absent."
        exit 0
    fi
    echo "Rook namespace ${ROOK_NAMESPACE} is unavailable; skipping Kubernetes teardown." >&2
    exit 1
fi

kube delete pod rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
kube delete pvc rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
kube delete namespace "${SMOKE_NAMESPACE}" --ignore-not-found --wait=false >/dev/null 2>&1 || true

# Helm uninstall runs before this helper. Refuse to remove Rook while any other
# claim still consumes the local CephFS StorageClass.
for _ in $(seq 1 120); do
    remaining_claims="$(
        kube get pvc -A \
            -o jsonpath='{range .items[?(@.spec.storageClassName=="rook-cephfs")]}{.metadata.namespace}{"/"}{.metadata.name}{"\n"}{end}' \
            2>/dev/null || true
    )"
    [ -z "${remaining_claims}" ] && break
    echo "Waiting for CephFS consumers to be removed: ${remaining_claims}" >&2
    sleep 1
done
if [ -n "${remaining_claims}" ]; then
    echo "CephFS claims are still in use; refusing to remove Rook resources." >&2
    dump_diagnostics
    exit 1
fi

kube delete storageclass rook-cephfs --ignore-not-found --wait=false
kube delete cephfilesystem reanafs -n "${ROOK_NAMESPACE}" --ignore-not-found --wait=false
kube delete cephblockpool builtin-mgr -n "${ROOK_NAMESPACE}" --ignore-not-found --wait=false

if ! wait_until_deleted "${ROOK_NAMESPACE}" "cephfilesystem/reanafs" 300; then
    echo "CephFilesystem reanafs did not finish deleting within 300 seconds." >&2
    dump_diagnostics
    exit 1
fi

if kube get cephcluster rook-ceph -n "${ROOK_NAMESPACE}" >/dev/null 2>&1; then
    kube patch cephcluster rook-ceph -n "${ROOK_NAMESPACE}" --type merge \
        -p '{"spec":{"cleanupPolicy":{"confirmation":"yes-really-destroy-data"}}}'
    kube delete cephcluster rook-ceph -n "${ROOK_NAMESPACE}" --wait=false
fi

if ! wait_until_deleted "${ROOK_NAMESPACE}" "cephcluster/rook-ceph" 300; then
    echo "CephCluster rook-ceph did not finish deleting within 300 seconds." >&2
    dump_diagnostics
    exit 1
fi

cleanup_jobs="$(kube -n "${ROOK_NAMESPACE}" get jobs -l app=rook-ceph-cleanup -o name 2>/dev/null || true)"
if [ -n "${cleanup_jobs}" ]; then
    if ! kube -n "${ROOK_NAMESPACE}" wait --for=condition=complete job \
        -l app=rook-ceph-cleanup --timeout=300s; then
        echo "Rook host cleanup jobs did not complete within 300 seconds." >&2
        dump_diagnostics
        exit 1
    fi
fi

for resource in \
    operatorconfigs.csi.ceph.io \
    drivers.csi.ceph.io \
    clientprofiles.csi.ceph.io \
    clientprofilemappings.csi.ceph.io \
    cephconnections.csi.ceph.io; do
    kube delete "${resource}" --all -n "${ROOK_NAMESPACE}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
done

kube delete -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/csi-operator.yaml" --ignore-not-found --wait=false >/dev/null 2>&1 || true
kube delete -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/operator.yaml" --ignore-not-found --wait=false >/dev/null 2>&1 || true
kube delete -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/common.yaml" --ignore-not-found --wait=false >/dev/null 2>&1 || true
kube delete -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/crds.yaml" --ignore-not-found --wait=false >/dev/null 2>&1 || true
kube delete namespace "${ROOK_NAMESPACE}" --ignore-not-found --wait=false

# cleanupPolicy normally removes this path; clear it explicitly as a bounded
# local-development fallback before the node container is deleted.
docker start "${NODE_CONTAINER}" >/dev/null 2>&1 || true
docker exec "${NODE_CONTAINER}" sh -lc 'rm -rf /var/lib/rook'

if ! wait_until_deleted "" "namespace/${ROOK_NAMESPACE}" 120; then
    echo "Namespace ${ROOK_NAMESPACE} is still terminating after 120 seconds." >&2
    dump_diagnostics
    exit 1
fi
