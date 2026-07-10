#!/bin/sh

set -eu

ROOK_NAMESPACE="${ROOK_NAMESPACE:-rook-ceph}"

kubectl delete storageclass rook-cephfs --ignore-not-found
kubectl delete cephfilesystem reanafs -n "${ROOK_NAMESPACE}" --ignore-not-found
kubectl delete cephcluster rook-ceph -n "${ROOK_NAMESPACE}" --ignore-not-found
kubectl delete namespace "${ROOK_NAMESPACE}" --ignore-not-found --wait=false
