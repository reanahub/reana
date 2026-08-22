#!/bin/sh

set -eu

ROOK_VERSION="${ROOK_VERSION:-v1.19.6}"
ROOK_NAMESPACE="rook-ceph"
NODE_NAME="${NODE_NAME:-$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')}"
NODE_CONTAINER="${NODE_CONTAINER:-${NODE_NAME}}"
ENABLE_RBD_CSI="${ENABLE_RBD_CSI:-false}"
FORCE_CEPHFS_KERNEL_CLIENT="${FORCE_CEPHFS_KERNEL_CLIENT:-false}"
CEPHFS_ATTACH_REQUIRED="${CEPHFS_ATTACH_REQUIRED:-false}"
BASE_DIR="${BASE_DIR:-/var/lib/rook-dev}"
MAP_FILE="${BASE_DIR}/device-map.txt"
SMOKE_NAMESPACE="rook-cephfs-smoke"
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)"
MANIFEST_DIR="${REPO_ROOT}/etc/rook-cephfs-kind"
TMP_DIR="$(mktemp -d)"
DEVICE_MAP_COPY="${TMP_DIR}/device-map.txt"
CLUSTER_MANIFEST="${TMP_DIR}/cluster.yaml"
FILESYSTEM_MANIFEST="${TMP_DIR}/filesystem.yaml"
STORAGECLASS_MANIFEST="${TMP_DIR}/storageclass.yaml"
TEST_PVC_MANIFEST="${TMP_DIR}/test-pvc.yaml"
TEST_POD_MANIFEST="${TMP_DIR}/test-pod.yaml"

cleanup() {
    kubectl delete pod rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true
    kubectl delete pvc rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true
    rm -rf "${TMP_DIR}"
}

dump_diagnostics() {
    echo
    echo "Rook pods:"
    kubectl -n "${ROOK_NAMESPACE}" get pods || true
    echo
    echo "CephCluster:"
    kubectl -n "${ROOK_NAMESPACE}" describe cephcluster rook-ceph || true
    echo
    echo "CephFilesystem:"
    kubectl -n "${ROOK_NAMESPACE}" describe cephfilesystem reanafs || true
    echo
    echo "Smoke PVC:"
    kubectl -n "${SMOKE_NAMESPACE}" describe pvc rook-cephfs-smoke || true
    echo
    echo "Smoke pod:"
    kubectl -n "${SMOKE_NAMESPACE}" describe pod rook-cephfs-smoke || true
}

fail() {
    echo "$1" >&2
    dump_diagnostics
    exit 1
}

wait_for_jsonpath_value() {
    namespace="$1"
    resource="$2"
    jsonpath="$3"
    expected="$4"
    description="$5"
    timeout_seconds="$6"
    sleep_seconds="$7"
    attempts=$((timeout_seconds / sleep_seconds))

    echo "Waiting for ${description}..."
    for _ in $(seq 1 "${attempts}"); do
        value="$(kubectl -n "${namespace}" get "${resource}" -o "jsonpath=${jsonpath}" 2>/dev/null || true)"
        if [ "${value}" = "${expected}" ]; then
            echo "${description}: ${value}"
            return 0
        fi
        [ -n "${value}" ] && echo "Current ${description}: ${value}"
        sleep "${sleep_seconds}"
    done

    return 1
}

render_manifest() {
    input_file="$1"
    output_file="$2"
    sed -e "s/__ROOK_NAMESPACE__/${ROOK_NAMESPACE}/g" \
        -e "s/__SMOKE_NAMESPACE__/${SMOKE_NAMESPACE}/g" \
        "${input_file}" >"${output_file}"
}

render_cluster_manifest() {
    awk \
        -v rook_namespace="${ROOK_NAMESPACE}" \
        -v node_name="${NODE_NAME}" \
        -v device_map="${DEVICE_MAP_COPY}" '
        /__DEVICE_ENTRIES__/ {
            while ((getline line < device_map) > 0) {
                if (line == "") {
                    continue
                }
                split(line, fields, " ")
                printf "          - name: %s\n", fields[1]
            }
            close(device_map)
            next
        }
        {
            gsub("__ROOK_NAMESPACE__", rook_namespace)
            gsub("__NODE_NAME__", node_name)
            print
        }
    ' "${MANIFEST_DIR}/cluster.yaml.in" >"${CLUSTER_MANIFEST}"
}

trap cleanup EXIT

if ! kubectl get node "${NODE_NAME}" >/dev/null 2>&1; then
    echo "Kubernetes node '${NODE_NAME}' not found" >&2
    exit 1
fi

if ! docker exec "${NODE_CONTAINER}" sh -lc "test -s '${MAP_FILE}'"; then
    echo "Loop device map '${MAP_FILE}' not found in ${NODE_CONTAINER}. Run setup-kind-rook-loop-devices.sh first." >&2
    exit 1
fi

docker exec "${NODE_CONTAINER}" sh -lc "cat '${MAP_FILE}'" >"${DEVICE_MAP_COPY}"

echo "Deploying Rook ${ROOK_VERSION} in namespace ${ROOK_NAMESPACE} for node ${NODE_NAME}..."

render_cluster_manifest
render_manifest "${MANIFEST_DIR}/filesystem.yaml" "${FILESYSTEM_MANIFEST}"
render_manifest "${MANIFEST_DIR}/storageclass.yaml" "${STORAGECLASS_MANIFEST}"
render_manifest "${MANIFEST_DIR}/test-pvc.yaml" "${TEST_PVC_MANIFEST}"
render_manifest "${MANIFEST_DIR}/test-pod.yaml" "${TEST_POD_MANIFEST}"

kubectl create namespace "${ROOK_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/crds.yaml"
kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/common.yaml"
kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/operator.yaml"
kubectl -n "${ROOK_NAMESPACE}" patch configmap rook-ceph-operator-config \
    --type merge \
    -p "{\"data\":{\"ROOK_CEPH_ALLOW_LOOP_DEVICES\":\"true\",\"ROOK_CSI_ENABLE_RBD\":\"${ENABLE_RBD_CSI}\",\"CSI_ENABLE_RBD_SNAPSHOTTER\":\"${ENABLE_RBD_CSI}\",\"CSI_FORCE_CEPHFS_KERNEL_CLIENT\":\"${FORCE_CEPHFS_KERNEL_CLIENT}\",\"CSI_CEPHFS_ATTACH_REQUIRED\":\"${CEPHFS_ATTACH_REQUIRED}\"}}"
kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/csi-operator.yaml"
kubectl -n "${ROOK_NAMESPACE}" rollout status deployment/rook-ceph-operator --timeout=10m

kubectl apply -f "${CLUSTER_MANIFEST}"
wait_for_jsonpath_value \
    "${ROOK_NAMESPACE}" \
    "cephcluster/rook-ceph" \
    "{.status.state}" \
    "Ready" \
    "CephCluster state" \
    600 \
    5 || fail "CephCluster rook-ceph did not reach Ready within the timeout."

kubectl apply -f "${FILESYSTEM_MANIFEST}"
wait_for_jsonpath_value \
    "${ROOK_NAMESPACE}" \
    "cephfilesystem/reanafs" \
    "{.status.phase}" \
    "Ready" \
    "CephFilesystem phase" \
    600 \
    5 || fail "CephFilesystem reanafs did not reach Ready within the timeout."

kubectl apply -f "${STORAGECLASS_MANIFEST}"

kubectl create namespace "${SMOKE_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
kubectl delete pod rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true
kubectl delete pvc rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true
kubectl apply -f "${TEST_PVC_MANIFEST}"
kubectl apply -f "${TEST_POD_MANIFEST}"

wait_for_jsonpath_value \
    "${SMOKE_NAMESPACE}" \
    "pvc/rook-cephfs-smoke" \
    "{.status.phase}" \
    "Bound" \
    "smoke PVC phase" \
    300 \
    5 || fail "Smoke PVC did not become Bound."

if ! kubectl wait --for=condition=Ready pod/rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" --timeout=300s; then
    fail "Smoke pod did not become Ready."
fi

if ! kubectl exec rook-cephfs-smoke -n "${SMOKE_NAMESPACE}" -- sh -lc '
    set -eu
    printf "first\n" > /mnt/reanafs/probe.txt
    grep -qx "first" /mnt/reanafs/probe.txt
    printf "second\n" >> /mnt/reanafs/probe.txt
    tail -n 1 /mnt/reanafs/probe.txt | grep -qx "second"
'; then
    fail "CephFS smoke mount did not support the expected write/read cycle."
fi

echo
echo "Current rook-ceph pods:"
kubectl -n "${ROOK_NAMESPACE}" get pods
echo
echo "CephCluster summary:"
kubectl -n "${ROOK_NAMESPACE}" get cephcluster rook-ceph -o wide
echo
echo "CephFilesystem summary:"
kubectl -n "${ROOK_NAMESPACE}" get cephfilesystem reanafs -o wide
echo
echo "Storage classes:"
kubectl get storageclass
