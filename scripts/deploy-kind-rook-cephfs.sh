#!/bin/sh
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

set -eu

CHECK_ONLY=false
if [ "${1:-}" = "--check-only" ]; then
    CHECK_ONLY=true
    shift
fi

STATE_HOME="${XDG_STATE_HOME:-${HOME:-.}/.local/state}"
STATE_FILE="${1:-${REANA_DEV_CEPHFS_STATE_FILE:-${STATE_HOME}/reana-dev/kind-cephfs.state}}"
ROOK_VERSION="${ROOK_VERSION:-v1.19.6}"
ROOK_NAMESPACE="rook-ceph"
KIND_CEPHFS_NODE_LABEL="reana.io/infrastructure-storage=cephfs"
persisted_node_name=""
persisted_node_container=""
persisted_base_dir=""
if [ -f "${STATE_FILE}" ]; then
    persisted_node_name="$(awk -F '\t' '$1 == "node_name" { print $2; exit }' "${STATE_FILE}")"
    persisted_node_container="$(awk -F '\t' '$1 == "node_container" { print $2; exit }' "${STATE_FILE}")"
    persisted_base_dir="$(awk -F '\t' '$1 == "base_dir" { print $2; exit }' "${STATE_FILE}")"
fi
NODE_NAME="${NODE_NAME:-${persisted_node_name:-$(kubectl get nodes -l "${KIND_CEPHFS_NODE_LABEL}" -o jsonpath='{.items[0].metadata.name}')}}"
NODE_CONTAINER="${NODE_CONTAINER:-${persisted_node_container:-kind-control-plane}}"
ENABLE_RBD_CSI="${ENABLE_RBD_CSI:-false}"
FORCE_CEPHFS_KERNEL_CLIENT="${FORCE_CEPHFS_KERNEL_CLIENT:-false}"
CEPHFS_ATTACH_REQUIRED="${CEPHFS_ATTACH_REQUIRED:-false}"
BASE_DIR="${BASE_DIR:-${persisted_base_dir:-/var/lib/rook-dev}}"
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

# shellcheck disable=SC2329
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

repair_device_map() {
    docker start "${NODE_CONTAINER}" >/dev/null 2>&1 || true
    docker exec "${NODE_CONTAINER}" sh -lc "
set -eu
map='${MAP_FILE}'
repaired=\"\${map}.repaired\"
: > \"\${repaired}\"
while read -r recorded_dev img; do
    [ -n \"\${recorded_dev}\" ] || continue
    if [ ! -f \"\${img}\" ]; then
        echo \"Backing image \${img} is missing\" >&2
        exit 1
    fi
    current=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
    if [ -z \"\${current}\" ]; then
        current=\$(losetup --find --show \"\${img}\")
        echo \"Reattached \${current} -> \${img}\"
    fi
    [ -b \"\${current}\" ] || {
        echo \"Mapped block device \${current} does not exist\" >&2
        exit 1
    }
    printf '%s %s\n' \"\${current}\" \"\${img}\" >> \"\${repaired}\"
done < \"\${map}\"
[ -s \"\${repaired}\" ] || {
    echo \"Device map \${map} contains no mappings\" >&2
    exit 1
}
mv \"\${repaired}\" \"\${map}\"
"
}

write_state() {
    state_dir="$(dirname "${STATE_FILE}")"
    mkdir -p "${state_dir}"
    state_tmp="$(mktemp "${STATE_FILE}.tmp.XXXXXX")"
    node_image="$(docker inspect --format '{{.Config.Image}}' "${NODE_CONTAINER}")"
    {
        printf 'backend\tcephfs\n'
        printf 'kubernetes\tkind\n'
        printf 'node_name\t%s\n' "${NODE_NAME}"
        printf 'node_container\t%s\n' "${NODE_CONTAINER}"
        printf 'node_image\t%s\n' "${node_image}"
        printf 'base_dir\t%s\n' "${BASE_DIR}"
        docker exec "${NODE_CONTAINER}" awk '{printf "device\t%s\t%s\n", $1, $2}' "${MAP_FILE}"
    } >"${state_tmp}"
    chmod 600 "${state_tmp}"
    mv "${state_tmp}" "${STATE_FILE}"
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
repair_device_map
docker exec "${NODE_CONTAINER}" sh -lc "cat '${MAP_FILE}'" >"${DEVICE_MAP_COPY}"
write_state
render_cluster_manifest

if [ "${CHECK_ONLY}" = "false" ]; then
    echo "Deploying Rook ${ROOK_VERSION} in namespace ${ROOK_NAMESPACE} for node ${NODE_NAME}..."
else
    echo "Repairing and checking the existing Rook/CephFS backend before REANA deployment..."
fi

render_manifest "${MANIFEST_DIR}/filesystem.yaml" "${FILESYSTEM_MANIFEST}"
render_manifest "${MANIFEST_DIR}/storageclass.yaml" "${STORAGECLASS_MANIFEST}"
render_manifest "${MANIFEST_DIR}/test-pvc.yaml" "${TEST_PVC_MANIFEST}"
render_manifest "${MANIFEST_DIR}/test-pod.yaml" "${TEST_POD_MANIFEST}"

if [ "${CHECK_ONLY}" = "true" ] && ! kubectl get storageclass rook-cephfs >/dev/null 2>&1; then
    fail "StorageClass rook-cephfs is not available."
fi

if [ "${CHECK_ONLY}" = "false" ]; then
    kubectl create namespace "${ROOK_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/crds.yaml"
    kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/common.yaml"
    kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/csi-operator.yaml"
    kubectl apply -f "https://raw.githubusercontent.com/rook/rook/${ROOK_VERSION}/deploy/examples/operator.yaml"
    kubectl -n "${ROOK_NAMESPACE}" patch configmap rook-ceph-operator-config \
        --type merge \
        -p "{\"data\":{\"ROOK_CEPH_ALLOW_LOOP_DEVICES\":\"true\",\"ROOK_CSI_ENABLE_RBD\":\"${ENABLE_RBD_CSI}\",\"CSI_ENABLE_RBD_SNAPSHOTTER\":\"${ENABLE_RBD_CSI}\",\"CSI_FORCE_CEPHFS_KERNEL_CLIENT\":\"${FORCE_CEPHFS_KERNEL_CLIENT}\",\"CSI_CEPHFS_ATTACH_REQUIRED\":\"${CEPHFS_ATTACH_REQUIRED}\"}}"
    kubectl -n "${ROOK_NAMESPACE}" rollout status deployment/rook-ceph-operator --timeout=10m
    kubectl apply -f "${CLUSTER_MANIFEST}"
else
    # Reconcile loop paths repaired after a Docker VM restart, but only when the
    # rendered manifest actually differs from the live object. An unconditional
    # apply bumps `.metadata.generation` on every preflight and makes Rook roll
    # the OSD deployments, which is slow and needlessly disruptive.
    if kubectl diff -f "${CLUSTER_MANIFEST}" >/dev/null 2>&1; then
        echo "CephCluster already matches the rendered device map; not re-applying."
    else
        echo "Rendered device map differs from the live CephCluster; re-applying."
        kubectl apply -f "${CLUSTER_MANIFEST}"
    fi
fi

# Readiness is reported by `.status.phase`. The `.status.state` field carries
# Rook's ClusterState enum (Creating/Created/Updating/Error) and never becomes
# "Ready", so waiting on it would always exhaust the timeout.
wait_for_jsonpath_value \
    "${ROOK_NAMESPACE}" \
    "cephcluster/rook-ceph" \
    "{.status.phase}" \
    "Ready" \
    "CephCluster phase" \
    600 \
    5 || fail "CephCluster rook-ceph did not reach Ready within the timeout."

if [ "${CHECK_ONLY}" = "false" ]; then
    kubectl apply -f "${FILESYSTEM_MANIFEST}"
fi
wait_for_jsonpath_value \
    "${ROOK_NAMESPACE}" \
    "cephfilesystem/reanafs" \
    "{.status.phase}" \
    "Ready" \
    "CephFilesystem phase" \
    600 \
    5 || fail "CephFilesystem reanafs did not reach Ready within the timeout."

if [ "${CHECK_ONLY}" = "false" ]; then
    kubectl apply -f "${STORAGECLASS_MANIFEST}"
fi
kubectl get storageclass rook-cephfs >/dev/null

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
