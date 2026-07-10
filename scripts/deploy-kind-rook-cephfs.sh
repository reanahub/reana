#!/bin/sh

set -eu

ROOK_VERSION="${ROOK_VERSION:-v1.19.6}"
ROOK_NAMESPACE="${ROOK_NAMESPACE:-rook-ceph}"
NODE_NAME="${NODE_NAME:-$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')}"
ENABLE_RBD_CSI="${ENABLE_RBD_CSI:-false}"
FORCE_CEPHFS_KERNEL_CLIENT="${FORCE_CEPHFS_KERNEL_CLIENT:-false}"
CEPHFS_ATTACH_REQUIRED="${CEPHFS_ATTACH_REQUIRED:-false}"
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)"
MANIFEST_DIR="${REPO_ROOT}/etc/rook-cephfs-kind"
TMP_DIR="$(mktemp -d)"
CLUSTER_MANIFEST="${TMP_DIR}/cluster.yaml"

cleanup() {
    rm -rf "${TMP_DIR}"
}

trap cleanup EXIT

if ! kubectl get node "${NODE_NAME}" >/dev/null 2>&1; then
    echo "Kubernetes node '${NODE_NAME}' not found" >&2
    exit 1
fi

echo "Deploying Rook ${ROOK_VERSION} in namespace ${ROOK_NAMESPACE} for node ${NODE_NAME}..."

kubectl create namespace "${ROOK_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/crds.yaml"
kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/common.yaml"
kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/operator.yaml"
kubectl -n "${ROOK_NAMESPACE}" patch configmap rook-ceph-operator-config \
    --type merge \
    -p "{\"data\":{\"ROOK_CEPH_ALLOW_LOOP_DEVICES\":\"true\",\"ROOK_CSI_ENABLE_RBD\":\"${ENABLE_RBD_CSI}\",\"CSI_ENABLE_RBD_SNAPSHOTTER\":\"${ENABLE_RBD_CSI}\",\"CSI_FORCE_CEPHFS_KERNEL_CLIENT\":\"${FORCE_CEPHFS_KERNEL_CLIENT}\",\"CSI_CEPHFS_ATTACH_REQUIRED\":\"${CEPHFS_ATTACH_REQUIRED}\"}}"
kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/csi-operator.yaml"
kubectl -n "${ROOK_NAMESPACE}" rollout status deployment/rook-ceph-operator --timeout=10m

sed "s/__NODE_NAME__/${NODE_NAME}/g" "${MANIFEST_DIR}/cluster.yaml.in" >"${CLUSTER_MANIFEST}"
kubectl apply -f "${CLUSTER_MANIFEST}"

echo "Waiting for CephCluster status to appear..."
for _ in $(seq 1 120); do
    state="$(kubectl -n "${ROOK_NAMESPACE}" get cephcluster rook-ceph -o jsonpath='{.status.state}' 2>/dev/null || true)"
    if [ -n "${state}" ]; then
        echo "CephCluster state: ${state}"
        break
    fi
    sleep 5
done

kubectl apply -f "${MANIFEST_DIR}/filesystem.yaml"
kubectl apply -f "${MANIFEST_DIR}/storageclass.yaml"

echo
echo "Current rook-ceph pods:"
kubectl -n "${ROOK_NAMESPACE}" get pods
echo
echo "CephCluster summary:"
kubectl -n "${ROOK_NAMESPACE}" get cephcluster rook-ceph -o wide || true
echo
echo "CephFilesystem summary:"
kubectl -n "${ROOK_NAMESPACE}" get cephfilesystem reanafs -o wide || true
echo
echo "Storage classes:"
kubectl get storageclass
