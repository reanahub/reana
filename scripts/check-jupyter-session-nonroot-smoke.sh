#!/bin/sh

set -eu

usage() {
    cat <<EOF
Usage: $0 [--namespace NAMESPACE] [--image IMAGE] [--delete-on-success] [WORKFLOW_NAME]

Create a temporary REANA workflow, materialise files in its real shared
workspace, open a real Jupyter interactive session on top of that workflow,
and verify that the recommended image:
- starts under uid 1000 / gid 0 with supplementary group 100
- serves the Jupyter HTTP endpoint
- can read and append to files created by the batch run
- can still write to /home/jovyan
- can read mounted and environment-provided REANA user secrets

Environment:
- REANA_SERVER_URL or an existing reana-client configuration
- REANA_ACCESS_TOKEN if the client is not already authenticated
- REANA_CLIENT_BIN to override the reana-client executable

Options:
- --namespace NAMESPACE  Runtime Kubernetes namespace used by REANA
                        [default: REANA_RUNTIME_KUBERNETES_NAMESPACE or default]
- --image IMAGE         Jupyter image to test
                        [default: quay.io/jupyter/scipy-notebook:notebook-7.2.2]
- --delete-on-success  Delete the temporary smoke workflow after success
EOF
}

NAMESPACE="${REANA_RUNTIME_KUBERNETES_NAMESPACE:-default}"
IMAGE="quay.io/jupyter/scipy-notebook:notebook-7.2.2"
DELETE_ON_SUCCESS=false
WORKFLOW_NAME=""

while [ $# -gt 0 ]; do
    case "$1" in
    --namespace)
        [ $# -ge 2 ] || {
            echo "Error: --namespace requires a value" >&2
            exit 1
        }
        NAMESPACE="$2"
        shift 2
        ;;
    --image)
        [ $# -ge 2 ] || {
            echo "Error: --image requires a value" >&2
            exit 1
        }
        IMAGE="$2"
        shift 2
        ;;
    --delete-on-success)
        DELETE_ON_SUCCESS=true
        shift
        ;;
    -h | --help)
        usage
        exit 0
        ;;
    -*)
        echo "Error: unknown option '$1'" >&2
        usage >&2
        exit 1
        ;;
    *)
        [ -z "${WORKFLOW_NAME}" ] || {
            echo "Error: workflow name already specified as '${WORKFLOW_NAME}'" >&2
            exit 1
        }
        WORKFLOW_NAME="$1"
        shift
        ;;
    esac
done

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)"
WORKFLOW_DIR="${REPO_ROOT}/etc/nonroot-smoke"
TMP_DIR="$(mktemp -d)"
FIRST_DOWNLOAD_DIR="${TMP_DIR}/first"
SECOND_DOWNLOAD_DIR="${TMP_DIR}/second"
POD_JSON_FILE="${TMP_DIR}/session-pod.json"
STAMP="$(date +%Y%m%d%H%M%S)"
ENV_SECRET_NAME="JUPYTER_SMOKE_ENV_${STAMP}"
ENV_SECRET_VALUE="smoke-env-${STAMP}"
FILE_SECRET_NAME="jupyter-smoke-file-${STAMP}.txt"
FILE_SECRET_VALUE="smoke-file-${STAMP}"
FILE_SECRET_PATH="${TMP_DIR}/${FILE_SECRET_NAME}"
SESSION_POD_NAME=""
SESSION_OPENED=false

if [ -z "${WORKFLOW_NAME}" ]; then
    WORKFLOW_NAME="nonroot-jupyter-session-smoke-${STAMP}"
fi

if [ -n "${REANA_CLIENT_BIN:-}" ]; then
    CLIENT_BIN="${REANA_CLIENT_BIN}"
elif command -v reana-client >/dev/null 2>&1; then
    CLIENT_BIN="$(command -v reana-client)"
elif [ -x "${REPO_ROOT}/../reana-venv/bin/reana-client" ]; then
    CLIENT_BIN="${REPO_ROOT}/../reana-venv/bin/reana-client"
else
    echo "Error: could not find reana-client; set REANA_CLIENT_BIN or activate the REANA virtualenv" >&2
    exit 1
fi

client() {
    "${CLIENT_BIN}" "$@"
}

assert_file_equals() {
    expected_file="$1"
    actual_file="$2"
    description="$3"
    if ! diff -u "${expected_file}" "${actual_file}"; then
        echo "Error: ${description} did not match the expected contents" >&2
        exit 1
    fi
}

create_expected_file() {
    output_path="$1"
    shift
    printf '%s' "$1" >"${output_path}"
}

wait_for_session_metadata() {
    for _ in $(seq 1 30); do
        session_metadata_json="$(client list --sessions -w "${WORKFLOW_NAME}" --json)"
        if printf '%s' "${session_metadata_json}" | python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data else 1)'; then
            printf '%s' "${session_metadata_json}"
            return 0
        fi
        sleep 2
    done
    echo "Error: interactive session metadata did not appear for workflow ${WORKFLOW_NAME}" >&2
    exit 1
}

wait_for_session_pod_name() {
    workflow_id="$1"
    label_selector="reana_workflow_mode=session,reana-run-session-workflow-uuid=${workflow_id}"
    for _ in $(seq 1 60); do
        pod_name="$(kubectl get pods -n "${NAMESPACE}" -l "${label_selector}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
        if [ -n "${pod_name}" ]; then
            printf '%s' "${pod_name}"
            return 0
        fi
        sleep 2
    done
    echo "Error: interactive session pod did not appear for workflow ${WORKFLOW_NAME}" >&2
    exit 1
}

cleanup() {
    if [ "${SESSION_OPENED}" = "true" ]; then
        client close -w "${WORKFLOW_NAME}" >/dev/null 2>&1 || true
    fi
    client secrets-delete "${ENV_SECRET_NAME}" "${FILE_SECRET_NAME}" >/dev/null 2>&1 || true
    rm -rf "${TMP_DIR}"
}

trap cleanup EXIT

printf '%s\n' "${FILE_SECRET_VALUE}" >"${FILE_SECRET_PATH}"

echo "Using reana-client: ${CLIENT_BIN}"
echo "Workflow smoke source: ${WORKFLOW_DIR}"
echo "Runtime namespace: ${NAMESPACE}"

echo "Uploading temporary REANA user secrets..."
client secrets-add --env "${ENV_SECRET_NAME}=${ENV_SECRET_VALUE}" --file "${FILE_SECRET_PATH}" >/dev/null

echo "Creating workflow ${WORKFLOW_NAME}..."
(
    cd "${WORKFLOW_DIR}"
    client create -n "${WORKFLOW_NAME}" -f reana.yaml >/dev/null
    client upload -w "${WORKFLOW_NAME}" >/dev/null
)

echo "Running the batch smoke once to materialise workspace files..."
client start -w "${WORKFLOW_NAME}" -p "hold_seconds=0" --follow

mkdir -p "${FIRST_DOWNLOAD_DIR}"
client download -w "${WORKFLOW_NAME}" -o "${FIRST_DOWNLOAD_DIR}" >/dev/null
expected_first="${TMP_DIR}/expected-first-persist.txt"
create_expected_file "${expected_first}" "first
"
assert_file_equals \
    "${expected_first}" \
    "${FIRST_DOWNLOAD_DIR}/results/persist.txt" \
    "batch-run persist.txt"

echo "Opening a real Jupyter interactive session for workflow ${WORKFLOW_NAME}..."
client open -w "${WORKFLOW_NAME}" jupyter --image "${IMAGE}" >/dev/null
SESSION_OPENED=true

session_metadata_json="$(wait_for_session_metadata)"
WORKFLOW_ID="$(printf '%s' "${session_metadata_json}" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data[0]["id"])')"
SESSION_URI="$(printf '%s' "${session_metadata_json}" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data[0]["session_uri"])')"
SESSION_POD_NAME="$(wait_for_session_pod_name "${WORKFLOW_ID}")"

echo "Waiting for the Jupyter session pod ${SESSION_POD_NAME} to become ready..."
if ! kubectl wait --for=condition=Ready "pod/${SESSION_POD_NAME}" -n "${NAMESPACE}" --timeout=300s; then
    echo "Interactive session pod failed to become ready. Dumping diagnostics..." >&2
    kubectl describe pod "${SESSION_POD_NAME}" -n "${NAMESPACE}" || true
    kubectl logs "${SESSION_POD_NAME}" -n "${NAMESPACE}" || true
    exit 1
fi

kubectl get pod "${SESSION_POD_NAME}" -n "${NAMESPACE}" -o json >"${POD_JSON_FILE}"

SESSION_BASE_URL="$(python3 -c 'import json,sys
pod = json.load(open(sys.argv[1]))
for arg in pod["spec"]["containers"][0].get("args", []):
    if arg.startswith("--NotebookApp.base_url="):
        print(arg.split("=", 1)[1].strip(chr(39)))
        break
else:
    raise SystemExit("missing NotebookApp.base_url")
' "${POD_JSON_FILE}")"
SESSION_TOKEN="$(python3 -c 'import json,sys
pod = json.load(open(sys.argv[1]))
for arg in pod["spec"]["containers"][0].get("args", []):
    if arg.startswith("--NotebookApp.token="):
        print(arg.split("=", 1)[1].strip(chr(39)))
        break
else:
    raise SystemExit("missing NotebookApp.token")
' "${POD_JSON_FILE}")"
NOTEBOOK_DIR="$(python3 -c 'import json,sys
pod = json.load(open(sys.argv[1]))
for arg in pod["spec"]["containers"][0].get("args", []):
    if arg.startswith("--notebook-dir="):
        print(arg.split("=", 1)[1].strip(chr(39)))
        break
else:
    raise SystemExit("missing notebook-dir")
' "${POD_JSON_FILE}")"
FILE_SECRET_MOUNT_PATH="$(python3 -c 'import json,sys
pod = json.load(open(sys.argv[1]))
secret_file_name = sys.argv[2]
volumes = {volume["name"]: volume for volume in pod["spec"].get("volumes", [])}
for mount in pod["spec"]["containers"][0].get("volumeMounts", []):
    volume = volumes.get(mount["name"], {})
    items = volume.get("secret", {}).get("items", [])
    if any(item.get("path") == secret_file_name for item in items):
        print(mount["mountPath"])
        break
else:
    raise SystemExit("missing file secret mount")
' "${POD_JSON_FILE}" "${FILE_SECRET_NAME}")"

echo "Checking runtime identity..."
id_output="$(kubectl exec "${SESSION_POD_NAME}" -n "${NAMESPACE}" -- id)"
case "${id_output}" in
*"uid=1000(jovyan) gid=0(root)"*"100(users)"*)
    printf '%s\n' "${id_output}"
    ;;
*)
    echo "Unexpected container identity: ${id_output}" >&2
    exit 1
    ;;
esac

echo "Checking notebook HTTP endpoint..."
http_status="$(
    kubectl exec "${SESSION_POD_NAME}" -n "${NAMESPACE}" -- \
        python3 -c 'import sys, urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8888{}{}token={}".format(sys.argv[1], "/api?" if not sys.argv[1].endswith("/") else "api?", sys.argv[2])).status)' "${SESSION_BASE_URL}" "${SESSION_TOKEN}"
)"
[ "${http_status}" = "200" ] || {
    echo "Unexpected notebook HTTP status: ${http_status}" >&2
    exit 1
}

echo "Checking workspace wiring..."
# shellcheck disable=SC2016
workspace_path="$(kubectl exec "${SESSION_POD_NAME}" -n "${NAMESPACE}" -- sh -lc 'printf %s "$REANA_WORKSPACE"')"
[ "${workspace_path}" = "${NOTEBOOK_DIR}" ] || {
    echo "Unexpected notebook workspace path: REANA_WORKSPACE=${workspace_path}, notebook-dir=${NOTEBOOK_DIR}" >&2
    exit 1
}
[ "${SESSION_URI}" = "${SESSION_BASE_URL}" ] || {
    echo "Unexpected session URI: list=${SESSION_URI}, pod=${SESSION_BASE_URL}" >&2
    exit 1
}

echo "Checking REANA user secrets..."
kubectl exec "${SESSION_POD_NAME}" -n "${NAMESPACE}" -- \
    python3 -c 'import os, sys; value = os.environ.get(sys.argv[1]); assert value == sys.argv[2], value' "${ENV_SECRET_NAME}" "${ENV_SECRET_VALUE}"
kubectl exec "${SESSION_POD_NAME}" -n "${NAMESPACE}" -- \
    sh -lc "test -f \"${FILE_SECRET_MOUNT_PATH}/${FILE_SECRET_NAME}\" && grep -qx '${FILE_SECRET_VALUE}' \"${FILE_SECRET_MOUNT_PATH}/${FILE_SECRET_NAME}\""

echo "Checking workspace visibility and writes..."
# shellcheck disable=SC2016
kubectl exec "${SESSION_POD_NAME}" -n "${NAMESPACE}" -- \
    sh -lc 'test -f "$REANA_WORKSPACE/results/persist.txt" && grep -qx "first" "$REANA_WORKSPACE/results/persist.txt"'
# shellcheck disable=SC2016
kubectl exec "${SESSION_POD_NAME}" -n "${NAMESPACE}" -- \
    sh -lc 'printf "session\n" >>"$REANA_WORKSPACE/results/persist.txt" && tail -n 1 "$REANA_WORKSPACE/results/persist.txt" | grep -qx "session"'

echo "Checking /home/jovyan writes..."
home_probe="$(
    kubectl exec "${SESSION_POD_NAME}" -n "${NAMESPACE}" -- \
        python3 -c 'from pathlib import Path; probe = Path("/home/jovyan/codex-home-write-test.txt"); probe.write_text("ok"); print(probe.read_text())'
)"
[ "${home_probe}" = "ok" ] || {
    echo "Unexpected /home/jovyan probe output: ${home_probe}" >&2
    exit 1
}

echo "Closing the interactive session before verifying user-visible downloads..."
client close -w "${WORKFLOW_NAME}" >/dev/null
SESSION_OPENED=false

mkdir -p "${SECOND_DOWNLOAD_DIR}"
client download -w "${WORKFLOW_NAME}" -o "${SECOND_DOWNLOAD_DIR}" >/dev/null
expected_second="${TMP_DIR}/expected-second-persist.txt"
create_expected_file "${expected_second}" "first
session
"
assert_file_equals \
    "${expected_second}" \
    "${SECOND_DOWNLOAD_DIR}/results/persist.txt" \
    "session-updated persist.txt"

echo "Jupyter non-root smoke passed for image ${IMAGE}."
echo "The real interactive-session pod could read and extend files from the real REANA workspace."

if [ "${DELETE_ON_SUCCESS}" = "true" ]; then
    echo "Deleting workflow ${WORKFLOW_NAME}..."
    client delete -w "${WORKFLOW_NAME}" --include-all-runs --include-workspace || true
else
    echo "Workflow retained for inspection: ${WORKFLOW_NAME}"
    echo "Cleanup command: ${CLIENT_BIN} delete -w ${WORKFLOW_NAME} --include-all-runs --include-workspace"
fi
