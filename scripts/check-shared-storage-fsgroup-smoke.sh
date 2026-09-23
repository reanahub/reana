#!/bin/sh
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

set -eu

usage() {
    cat <<EOF
Usage: $0 [--namespace NAMESPACE] [--delete-on-success] [--hold-seconds N] [WORKFLOW_NAME]

Run the non-root shared-storage smoke workflow twice against the same REANA
workspace. While each run is alive, assert the batch and user-job pod security
contexts, runtime identity, workspace ownership, and group-write behaviour.
Then verify that the restarted run can reuse and modify the first run's files.

Environment:
- REANA_SERVER_URL or an existing reana-client configuration
- REANA_ACCESS_TOKEN if the client is not already authenticated
- REANA_CLIENT_BIN to override the reana-client executable
- EXPECTED_RUNTIME_UID [default: 1000]
- EXPECTED_RUNTIME_GID [default: 0]
- EXPECTED_FS_GROUP [default: EXPECTED_RUNTIME_GID]
- SMOKE_RUN_TIMEOUT_SECONDS [default: 300]

Options:
- --namespace NAMESPACE  Runtime Kubernetes namespace used by REANA
                        [default: REANA_RUNTIME_KUBERNETES_NAMESPACE or default]
- --delete-on-success   Delete the smoke workflow after a successful run
- --hold-seconds N      Seconds each user job remains alive for inspection
                        [default: 60; minimum: 30]

If WORKFLOW_NAME is omitted, a unique one is generated automatically.
EOF
}

NAMESPACE="${REANA_RUNTIME_KUBERNETES_NAMESPACE:-default}"
DELETE_ON_SUCCESS=false
HOLD_SECONDS=60
WORKFLOW_NAME=""
EXPECTED_RUNTIME_UID="${EXPECTED_RUNTIME_UID:-1000}"
EXPECTED_RUNTIME_GID="${EXPECTED_RUNTIME_GID:-0}"
EXPECTED_FS_GROUP="${EXPECTED_FS_GROUP:-${EXPECTED_RUNTIME_GID}}"
RUN_TIMEOUT_SECONDS="${SMOKE_RUN_TIMEOUT_SECONDS:-300}"

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
    --delete-on-success)
        DELETE_ON_SUCCESS=true
        shift
        ;;
    --hold-seconds)
        [ $# -ge 2 ] || {
            echo "Error: --hold-seconds requires a value" >&2
            exit 1
        }
        HOLD_SECONDS="$2"
        shift 2
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

case "${HOLD_SECONDS}" in
'' | *[!0-9]*)
    echo "Error: --hold-seconds must be an integer" >&2
    exit 1
    ;;
esac
if [ "${HOLD_SECONDS}" -lt 30 ]; then
    echo "Error: --hold-seconds must be at least 30 for live pod inspection" >&2
    exit 1
fi

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)"
WORKFLOW_DIR="${REPO_ROOT}/etc/workspace-persistence-smoke"
TMP_DIR="$(mktemp -d)"
FIRST_DOWNLOAD_DIR="${TMP_DIR}/first"
SECOND_DOWNLOAD_DIR="${TMP_DIR}/second"
BEFORE_RESTART_JSON="${TMP_DIR}/before-restart.json"

# shellcheck disable=SC2329
cleanup() {
    rm -rf "${TMP_DIR}"
}

trap cleanup EXIT

if [ -z "${WORKFLOW_NAME}" ]; then
    WORKFLOW_NAME="nonroot-fsgroup-smoke-$(date +%Y%m%d%H%M%S)"
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

list_runs_json() {
    client list -w "${WORKFLOW_NAME}" --verbose --json
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

latest_run_metadata() {
    python3 -c '
import json, sys

items = json.load(sys.stdin)
if not items:
    raise SystemExit(1)
item = max(items, key=lambda row: tuple(int(part) for part in str(row["run_number"]).split(".")))
print("{}\t{}.{}".format(item["id"], item["name"], item["run_number"]))
'
}

wait_for_initial_run_metadata() {
    for _ in $(seq 1 30); do
        metadata="$(list_runs_json | latest_run_metadata 2>/dev/null || true)"
        [ -n "${metadata}" ] && {
            printf '%s' "${metadata}"
            return 0
        }
        sleep 2
    done
    echo "Error: could not obtain structured metadata for ${WORKFLOW_NAME}" >&2
    return 1
}

wait_for_restarted_run_metadata() {
    for _ in $(seq 1 60); do
        metadata="$(
            list_runs_json | python3 -c '
import json, sys

before = {item["id"] for item in json.load(open(sys.argv[1]))}
items = [item for item in json.load(sys.stdin) if item["id"] not in before]
if not items:
    raise SystemExit(1)
item = max(items, key=lambda row: tuple(int(part) for part in str(row["run_number"]).split(".")))
print("{}\t{}.{}".format(item["id"], item["name"], item["run_number"]))
' "${BEFORE_RESTART_JSON}" 2>/dev/null || true
        )"
        [ -n "${metadata}" ] && {
            printf '%s' "${metadata}"
            return 0
        }
        sleep 2
    done
    echo "Error: could not identify the restarted run from structured workflow data" >&2
    return 1
}

wait_for_pod() {
    label_selector="$1"
    description="$2"
    for _ in $(seq 1 90); do
        pod_name="$(kubectl get pods -n "${NAMESPACE}" -l "${label_selector}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
        if [ -n "${pod_name}" ]; then
            if kubectl wait --for=condition=Ready "pod/${pod_name}" -n "${NAMESPACE}" --timeout=10s >/dev/null 2>&1; then
                printf '%s' "${pod_name}"
                return 0
            fi
        fi
        sleep 2
    done
    echo "Error: ${description} did not become ready" >&2
    return 1
}

dump_run_diagnostics() {
    workflow_id="$1"
    echo "Batch pods:" >&2
    kubectl get pods -n "${NAMESPACE}" -l "reana-run-batch-workflow-uuid=${workflow_id}" -o wide >&2 || true
    echo "User job pods:" >&2
    kubectl get pods -n "${NAMESPACE}" -l "reana-run-job-workflow-uuid=${workflow_id}" -o wide >&2 || true
    kubectl get events -n "${NAMESPACE}" --sort-by=.lastTimestamp >&2 || true
}

assert_run_security_context() {
    workflow_id="$1"
    batch_pod="$(wait_for_pod "reana-run-batch-workflow-uuid=${workflow_id}" "batch workflow pod")" || {
        dump_run_diagnostics "${workflow_id}"
        return 1
    }
    job_pod="$(wait_for_pod "reana-run-job-workflow-uuid=${workflow_id}" "user job pod")" || {
        dump_run_diagnostics "${workflow_id}"
        return 1
    }

    echo "Inspecting batch pod ${batch_pod} and user job pod ${job_pod}..."
    if ! kubectl get pod "${batch_pod}" -n "${NAMESPACE}" -o json | python3 -c '
import json, sys

pod = json.load(sys.stdin)
expected_uid, expected_gid, expected_fs_group = map(int, sys.argv[1:])
pod_context = pod["spec"].get("securityContext", {})
assert pod_context.get("fsGroup") == expected_fs_group, pod_context
containers = {item["name"]: item for item in pod["spec"]["containers"]}
for name in ("workflow-engine", "job-controller"):
    context = containers[name].get("securityContext", {})
    assert context.get("runAsUser") == expected_uid, (name, context)
    assert context.get("runAsGroup") == expected_gid, (name, context)
    assert context.get("runAsNonRoot") is True, (name, context)
' "${EXPECTED_RUNTIME_UID}" "${EXPECTED_RUNTIME_GID}" "${EXPECTED_FS_GROUP}"; then
        dump_run_diagnostics "${workflow_id}"
        return 1
    fi

    if ! kubectl get pod "${job_pod}" -n "${NAMESPACE}" -o json | python3 -c '
import json, sys

pod = json.load(sys.stdin)
expected_uid, expected_gid = map(int, sys.argv[1:])
pod_context = pod["spec"].get("securityContext", {})
assert pod_context.get("runAsUser") == expected_uid, pod_context
assert pod_context.get("runAsGroup") == expected_gid, pod_context
assert pod_context.get("runAsNonRoot") is True, pod_context
container_context = next(item for item in pod["spec"]["containers"] if item["name"] == "job").get("securityContext", {})
assert container_context.get("runAsNonRoot") is True, container_context
' "${EXPECTED_RUNTIME_UID}" "${EXPECTED_RUNTIME_GID}"; then
        dump_run_diagnostics "${workflow_id}"
        return 1
    fi

    runtime_uid="$(kubectl exec "${job_pod}" -n "${NAMESPACE}" -c job -- id -u)"
    runtime_gid="$(kubectl exec "${job_pod}" -n "${NAMESPACE}" -c job -- id -g)"
    runtime_groups="$(kubectl exec "${job_pod}" -n "${NAMESPACE}" -c job -- id -G)"
    [ "${runtime_uid}" = "${EXPECTED_RUNTIME_UID}" ] || {
        echo "Error: runtime UID is ${runtime_uid}, expected ${EXPECTED_RUNTIME_UID}" >&2
        return 1
    }
    [ "${runtime_gid}" = "${EXPECTED_RUNTIME_GID}" ] || {
        echo "Error: runtime GID is ${runtime_gid}, expected ${EXPECTED_RUNTIME_GID}" >&2
        return 1
    }
    case " ${runtime_groups} " in
    *" ${EXPECTED_FS_GROUP} "*) ;;
    *)
        echo "Error: runtime groups '${runtime_groups}' omit fsGroup ${EXPECTED_FS_GROUP}" >&2
        return 1
        ;;
    esac

    # shellcheck disable=SC2016
    workspace_stat="$(
        kubectl exec "${job_pod}" -n "${NAMESPACE}" -c job -- \
            bash -c 'workspace=$(readlink /proc/1/cwd); stat -c "%u %g %a" "${workspace}"'
    )"
    workspace_gid="$(printf '%s\n' "${workspace_stat}" | awk '{print $2}')"
    workspace_mode="$(printf '%s\n' "${workspace_stat}" | awk '{print $3}')"
    [ "${workspace_gid}" = "${EXPECTED_FS_GROUP}" ] || {
        echo "Error: workspace stat '${workspace_stat}' has unexpected group owner" >&2
        return 1
    }
    group_digit="$(printf '%s' "${workspace_mode}" | awk '{print substr($0, length($0) - 1, 1)}')"
    other_digit="$(printf '%s' "${workspace_mode}" | awk '{print substr($0, length($0), 1)}')"
    [ $((group_digit & 2)) -ne 0 ] || {
        echo "Error: workspace mode ${workspace_mode} is not group-writable" >&2
        return 1
    }
    [ $((other_digit & 2)) -eq 0 ] || {
        echo "Error: workspace mode ${workspace_mode} is world-writable" >&2
        return 1
    }

    # shellcheck disable=SC2016
    probe_gid="$(
        kubectl exec "${job_pod}" -n "${NAMESPACE}" -c job -- bash -c '
            set -eu
            workspace=$(readlink /proc/1/cwd)
            probe="${workspace}/.reana-fsgroup-write-probe"
            umask 0007
            printf "ok\n" >"${probe}"
            stat -c %g "${probe}"
            rm -f "${probe}"
        '
    )"
    [ "${probe_gid}" = "${EXPECTED_FS_GROUP}" ] || {
        echo "Error: group-write probe has GID ${probe_gid}, expected ${EXPECTED_FS_GROUP}" >&2
        return 1
    }

    echo "Runtime identity: uid=${runtime_uid} gid=${runtime_gid} groups=${runtime_groups}"
    echo "Workspace ownership and mode: ${workspace_stat}"
}

wait_for_run_completion() {
    run_reference="$1"
    workflow_id="$2"
    attempts=$((RUN_TIMEOUT_SECONDS / 2))

    for _ in $(seq 1 "${attempts}"); do
        status_json="$(client status -w "${run_reference}" --json)"
        status="$(printf '%s' "${status_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["status"])')"
        echo "${run_reference}: ${status}"
        case "${status}" in
        finished)
            return 0
            ;;
        failed | stopped | deleted)
            echo "Error: ${run_reference} ended with status ${status}" >&2
            dump_run_diagnostics "${workflow_id}"
            return 1
            ;;
        esac
        sleep 2
    done

    echo "Error: ${run_reference} did not finish within ${RUN_TIMEOUT_SECONDS} seconds" >&2
    client status -w "${run_reference}" --json >&2 || true
    dump_run_diagnostics "${workflow_id}"
    return 1
}

run_and_download() {
    run_label="$1"
    workflow_id="$2"
    run_reference="$3"
    download_dir="$4"

    echo "Starting ${run_label} run ${run_reference}..."
    client start -w "${run_reference}" -p "hold_seconds=${HOLD_SECONDS}"
    assert_run_security_context "${workflow_id}"
    wait_for_run_completion "${run_reference}" "${workflow_id}"
    mkdir -p "${download_dir}"
    client download -w "${run_reference}" -o "${download_dir}"
}

verify_first_run() {
    download_dir="$1"
    expected_persist="${TMP_DIR}/expected-first-persist.txt"
    expected_proof="${TMP_DIR}/expected-first-proof.txt"

    create_expected_file "${expected_persist}" "first
"
    create_expected_file "${expected_proof}" "initialized-new-workspace
"
    assert_file_equals "${expected_persist}" "${download_dir}/results/persist.txt" "first-run persist.txt"
    assert_file_equals "${expected_proof}" "${download_dir}/results/proof.txt" "first-run proof.txt"
}

verify_second_run() {
    download_dir="$1"
    expected_persist="${TMP_DIR}/expected-second-persist.txt"
    expected_proof="${TMP_DIR}/expected-second-proof.txt"

    create_expected_file "${expected_persist}" "first
second
"
    create_expected_file "${expected_proof}" "detected-existing-workspace
"
    assert_file_equals "${expected_persist}" "${download_dir}/results/persist.txt" "second-run persist.txt"
    assert_file_equals "${expected_proof}" "${download_dir}/results/proof.txt" "second-run proof.txt"
}

echo "Using reana-client: ${CLIENT_BIN}"
echo "Workflow smoke source: ${WORKFLOW_DIR}"
echo "Runtime namespace: ${NAMESPACE}"
echo "Hold seconds per run: ${HOLD_SECONDS}"

echo "Creating workflow ${WORKFLOW_NAME}..."
(
    cd "${WORKFLOW_DIR}"
    client create -n "${WORKFLOW_NAME}" -f reana.yaml
    client upload -w "${WORKFLOW_NAME}"
)

tab="$(printf '\t')"
initial_metadata="$(wait_for_initial_run_metadata)"
initial_workflow_id="${initial_metadata%%"${tab}"*}"
initial_run_reference="${initial_metadata#*"${tab}"}"
run_and_download "first" "${initial_workflow_id}" "${initial_run_reference}" "${FIRST_DOWNLOAD_DIR}"
verify_first_run "${FIRST_DOWNLOAD_DIR}"

list_runs_json >"${BEFORE_RESTART_JSON}"
echo "Restarting ${initial_run_reference} on the same workspace..."
client restart -w "${initial_run_reference}" -p "hold_seconds=${HOLD_SECONDS}"
restarted_metadata="$(wait_for_restarted_run_metadata)"
restarted_workflow_id="${restarted_metadata%%"${tab}"*}"
restarted_run_reference="${restarted_metadata#*"${tab}"}"
assert_run_security_context "${restarted_workflow_id}"
wait_for_run_completion "${restarted_run_reference}" "${restarted_workflow_id}"
mkdir -p "${SECOND_DOWNLOAD_DIR}"
client download -w "${restarted_run_reference}" -o "${SECOND_DOWNLOAD_DIR}"
verify_second_run "${SECOND_DOWNLOAD_DIR}"

echo
echo "Shared-storage fsGroup smoke passed for workflow ${WORKFLOW_NAME}."
echo "Both runs used the expected non-root identity and group-writable shared workspace."
echo
echo "Final outputs:"
cat "${SECOND_DOWNLOAD_DIR}/results/persist.txt"
echo

if [ "${DELETE_ON_SUCCESS}" = "true" ]; then
    echo "Deleting workflow ${WORKFLOW_NAME}..."
    client delete -w "${WORKFLOW_NAME}" --include-all-runs --include-workspace || true
else
    echo "Workflow retained for inspection: ${WORKFLOW_NAME}"
    echo "Cleanup command: ${CLIENT_BIN} delete -w ${WORKFLOW_NAME} --include-all-runs --include-workspace"
fi
