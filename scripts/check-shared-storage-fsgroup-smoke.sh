#!/bin/sh

set -eu

usage() {
    cat <<EOF
Usage: $0 [--delete-on-success] [--hold-seconds N] [WORKFLOW_NAME]

Run the non-root shared-storage smoke workflow twice against the same REANA
workspace and verify that the second run can reuse and modify the files created
by the first run.

Environment:
- REANA_SERVER_URL or an existing reana-client configuration
- REANA_ACCESS_TOKEN if the client is not already authenticated
- REANA_CLIENT_BIN to override the reana-client executable

Options:
- --delete-on-success  Delete the smoke workflow after a successful run
- --hold-seconds N     Workflow hold duration in seconds for each run
                       [default: 0 for this storage smoke]

If WORKFLOW_NAME is omitted, a unique one is generated automatically.
EOF
}

DELETE_ON_SUCCESS=false
HOLD_SECONDS=0
WORKFLOW_NAME=""

while [ $# -gt 0 ]; do
    case "$1" in
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

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)"
WORKFLOW_DIR="${REPO_ROOT}/etc/nonroot-smoke"
TMP_DIR="$(mktemp -d)"
FIRST_DOWNLOAD_DIR="${TMP_DIR}/first"
SECOND_DOWNLOAD_DIR="${TMP_DIR}/second"

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

run_smoke_once() {
    run_label="$1"
    download_dir="$2"

    echo "Starting ${run_label} run for workflow ${WORKFLOW_NAME}..."
    client start -w "${WORKFLOW_NAME}" -p "hold_seconds=${HOLD_SECONDS}" --follow

    mkdir -p "${download_dir}"
    client download -w "${WORKFLOW_NAME}" -o "${download_dir}"
}

wait_for_run_completion() {
    run_reference="$1"

    while true; do
        status_output="$(client status -w "${run_reference}")"
        printf '%s\n' "${status_output}"

        printf '%s\n' "${status_output}" | grep -q 'finished' && return 0
        if printf '%s\n' "${status_output}" | grep -Eq 'failed|stopped|deleted'; then
            echo "Error: ${run_reference} did not finish successfully" >&2
            return 1
        fi

        sleep 2
    done
}

restart_smoke_once() {
    run_label="$1"
    download_dir="$2"

    echo "Restarting ${run_label} run for workflow ${WORKFLOW_NAME}..."
    restart_output="$(
        client restart -w "${WORKFLOW_NAME}" -p "hold_seconds=${HOLD_SECONDS}"
    )"
    printf '%s\n' "${restart_output}"

    run_reference="$(
        printf '%s\n' "${restart_output}" |
            sed -n 's/.*SUCCESS: \([^[:space:]]*\) has been queued/\1/p' |
            tail -n 1
    )"
    [ -n "${run_reference}" ] || {
        echo "Error: could not determine restarted run reference" >&2
        exit 1
    }

    wait_for_run_completion "${run_reference}"

    mkdir -p "${download_dir}"
    client download -w "${WORKFLOW_NAME}" -o "${download_dir}"
}

verify_first_run() {
    download_dir="$1"
    expected_persist="${TMP_DIR}/expected-first-persist.txt"
    expected_proof="${TMP_DIR}/expected-first-proof.txt"

    create_expected_file "${expected_persist}" "first
"
    create_expected_file "${expected_proof}" "initialized-new-workspace
"

    assert_file_equals \
        "${expected_persist}" \
        "${download_dir}/results/persist.txt" \
        "first-run persist.txt"
    assert_file_equals \
        "${expected_proof}" \
        "${download_dir}/results/proof.txt" \
        "first-run proof.txt"
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

    assert_file_equals \
        "${expected_persist}" \
        "${download_dir}/results/persist.txt" \
        "second-run persist.txt"
    assert_file_equals \
        "${expected_proof}" \
        "${download_dir}/results/proof.txt" \
        "second-run proof.txt"
}

echo "Using reana-client: ${CLIENT_BIN}"
echo "Workflow smoke source: ${WORKFLOW_DIR}"
echo "Hold seconds per run: ${HOLD_SECONDS}"

echo "Creating workflow ${WORKFLOW_NAME}..."
(
    cd "${WORKFLOW_DIR}"
    client create -n "${WORKFLOW_NAME}" -f reana.yaml
    client upload -w "${WORKFLOW_NAME}"
)
run_smoke_once "first" "${FIRST_DOWNLOAD_DIR}"
verify_first_run "${FIRST_DOWNLOAD_DIR}"

restart_smoke_once "second" "${SECOND_DOWNLOAD_DIR}"
verify_second_run "${SECOND_DOWNLOAD_DIR}"

echo
echo "Shared-storage smoke passed for workflow ${WORKFLOW_NAME}."
echo "The same workspace was reused across runs and remained writable under the non-root setup."
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
