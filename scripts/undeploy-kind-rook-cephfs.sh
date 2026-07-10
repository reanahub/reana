#!/bin/sh

set -eu

ROOK_VERSION="${ROOK_VERSION:-v1.19.6}"
ROOK_NAMESPACE="rook-ceph"
SMOKE_NAMESPACE="rook-cephfs-smoke"

wait_until_deleted() {
    namespace="$1"
    resource="$2"
    timeout_seconds="$3"

    for _ in $(seq 1 "${timeout_seconds}"); do
        if ! kubectl -n "${namespace}" get "${resource}" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    return 1
}

kubectl delete pod rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true
kubectl delete pvc rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true
kubectl delete namespace "${SMOKE_NAMESPACE}" --ignore-not-found --wait=false >/dev/null 2>&1 || true

kubectl delete storageclass rook-cephfs --ignore-not-found
kubectl delete cephfilesystem reanafs -n "${ROOK_NAMESPACE}" --ignore-not-found || true
kubectl delete cephblockpool builtin-mgr -n "${ROOK_NAMESPACE}" --ignore-not-found || true
kubectl delete cephcluster rook-ceph -n "${ROOK_NAMESPACE}" --ignore-not-found || true

if ! wait_until_deleted "${ROOK_NAMESPACE}" "cephcluster/rook-ceph" 300; then
    echo "CephCluster rook-ceph is still deleting after 300 seconds; continuing with operator teardown." >&2
fi

kubectl delete -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/csi-operator.yaml" --ignore-not-found >/dev/null 2>&1 || true
kubectl delete -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/operator.yaml" --ignore-not-found >/dev/null 2>&1 || true
kubectl delete -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/common.yaml" --ignore-not-found >/dev/null 2>&1 || true
kubectl delete -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/crds.yaml" --ignore-not-found >/dev/null 2>&1 || true

kubectl delete namespace "${ROOK_NAMESPACE}" --ignore-not-found --wait=false
