#!/bin/sh

set -eu

STORAGE_CLASS="${1:-standard}"
NAMESPACE="${2:-default}"
PVC_NAME="cephfs-block-probe"
POD_NAME="cephfs-block-consumer"
TMP_DIR="$(mktemp -d)"
PVC_MANIFEST="${TMP_DIR}/pvc.yaml"
POD_MANIFEST="${TMP_DIR}/pod.yaml"

# shellcheck disable=SC2317
cleanup() {
    kubectl delete pod "${POD_NAME}" -n "${NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true
    kubectl delete pvc "${PVC_NAME}" -n "${NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true
    rm -rf "${TMP_DIR}"
}

trap cleanup EXIT

echo "Checking raw block support for storage class '${STORAGE_CLASS}' in namespace '${NAMESPACE}'..."

cat >"${PVC_MANIFEST}" <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${PVC_NAME}
  namespace: ${NAMESPACE}
spec:
  accessModes:
    - ReadWriteOnce
  volumeMode: Block
  resources:
    requests:
      storage: 1Gi
  storageClassName: ${STORAGE_CLASS}
EOF
kubectl apply --validate=false -f "${PVC_MANIFEST}"

cat >"${POD_MANIFEST}" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: ${POD_NAME}
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
    - name: consumer
      image: docker.io/library/busybox:1.36
      command:
        - sh
        - -c
        - sleep 600
      volumeDevices:
        - name: block
          devicePath: /dev/xvda
  volumes:
    - name: block
      persistentVolumeClaim:
        claimName: ${PVC_NAME}
EOF
kubectl apply --validate=false -f "${POD_MANIFEST}"

for _ in $(seq 1 60); do
    pvc_phase="$(kubectl get pvc "${PVC_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    pod_phase="$(kubectl get pod "${POD_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"

    if [ "${pvc_phase}" = "Bound" ] && [ "${pod_phase}" = "Running" ]; then
        if kubectl exec "${POD_NAME}" -n "${NAMESPACE}" -- sh -lc "test -b /dev/xvda"; then
            echo "Success: storage class '${STORAGE_CLASS}' can provision and attach raw block volumes."
            exit 0
        fi
    fi

    if [ "${pod_phase}" = "Failed" ] || [ "${pod_phase}" = "Succeeded" ]; then
        break
    fi
    sleep 2
done

echo "Failure: storage class '${STORAGE_CLASS}' did not provision and attach a raw block volume within the timeout."
echo "PVC phase: ${pvc_phase:-unknown}"
echo "Pod phase: ${pod_phase:-unknown}"
echo
echo "PVC description:"
kubectl describe pvc "${PVC_NAME}" -n "${NAMESPACE}"
echo
echo "Pod description:"
kubectl describe pod "${POD_NAME}" -n "${NAMESPACE}"
exit 1
