#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

set -euo pipefail

usage() {
    cat <<EOF
Usage: $0 [namespace] [instance-name]

Exercise the validation-snapshot and later workspace-input contract against a
live REANA cluster.

Arguments:
  namespace      Kubernetes namespace. [default: default]
  instance-name  REANA Helm release name. [default: reana]

Environment variables:
  REANA_SERVER_URL
      Public REANA URL. [default: https://localhost:30443]
  REANA_ACCESS_TOKEN
      OIDC access token. Required.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi
if [ "$#" -gt 2 ]; then
    usage >&2
    exit 2
fi

server_url=${REANA_SERVER_URL:-https://localhost:30443}

access_token=${REANA_ACCESS_TOKEN:-}
if [ -z "${access_token}" ]; then
    echo "Error: REANA_ACCESS_TOKEN is required." >&2
    exit 2
fi

for required_command in cmp curl jq python3; do
    if ! command -v "${required_command}" >/dev/null 2>&1; then
        echo "Error: required command '${required_command}' was not found." >&2
        exit 2
    fi
done

temporary_directory=$(mktemp -d)
workflow_id=

# Invoked indirectly by the EXIT trap below.
# shellcheck disable=SC2329
cleanup() {
    if [ -n "${workflow_id}" ]; then
        curl --silent --insecure --request PUT \
            --header "Authorization: Bearer ${access_token}" \
            --header "Content-Type: application/json" \
            --data '{"all_runs":false,"workspace":true}' \
            "${server_url%/}/api/workflows/${workflow_id}/status?status=deleted" \
            >/dev/null 2>&1 || true
    fi
    rm -rf "${temporary_directory}"
}
trap cleanup EXIT

mkdir -p \
    "${temporary_directory}/source/code" \
    "${temporary_directory}/source/rules" \
    "${temporary_directory}/source/data"

cat >"${temporary_directory}/source/reana.yaml" <<'EOF'
version: 0.9.0
inputs:
  files:
    - data/input.txt
  parameters:
    greeting: hello
workflow:
  type: serial
  files:
    - code/helper.py
  directories:
    - rules
  specification:
    steps:
      - name: hello
        environment: docker.io/library/busybox
        commands:
          - echo "${greeting}"
EOF
printf '%s\n' 'print("helper")' >"${temporary_directory}/source/code/helper.py"
printf '%s\n' '# included workflow source' >"${temporary_directory}/source/rules/common.py"
printf '%s\n' 'dataset uploaded after create' >"${temporary_directory}/source/data/input.txt"

SOURCE_DIR="${temporary_directory}/source" python3 - <<'PY'
import os
import zipfile

source = os.environ["SOURCE_DIR"]
with zipfile.ZipFile(
    os.path.join(source, "validation-bundle.zip"),
    "w",
    compression=zipfile.ZIP_STORED,
    allowZip64=False,
) as archive:
    for name in ("reana.yaml", "code/helper.py", "rules/common.py"):
        archive.write(os.path.join(source, name), name)
PY

echo "Validating the declared workflow-definition snapshot..."
validation_status=$(curl --silent --show-error --insecure \
    --header "Authorization: Bearer ${access_token}" \
    --output "${temporary_directory}/validation.json" \
    --write-out '%{http_code}' \
    --form "bundle=@${temporary_directory}/source/validation-bundle.zip;filename=validation-bundle.zip" \
    "${server_url%/}/api/workflows/validate")
if [ "${validation_status}" != "200" ] ||
    [ "$(jq -r '.valid' "${temporary_directory}/validation.json")" != "true" ]; then
    echo "Error: valid snapshot was rejected (HTTP ${validation_status})." >&2
    cat "${temporary_directory}/validation.json" >&2
    exit 1
fi

echo "Creating a workflow from the same snapshot..."
workflow_name="storage-contract-$(date +%s)"
create_status=$(curl --silent --show-error --insecure \
    --header "Authorization: Bearer ${access_token}" \
    --output "${temporary_directory}/create.json" \
    --write-out '%{http_code}' \
    --form "bundle=@${temporary_directory}/source/validation-bundle.zip;filename=validation-bundle.zip" \
    "${server_url%/}/api/workflows?workflow_name=${workflow_name}")
if [ "${create_status}" != "201" ] && [ "${create_status}" != "200" ]; then
    echo "Error: workflow create failed (HTTP ${create_status})." >&2
    cat "${temporary_directory}/create.json" >&2
    exit 1
fi
workflow_id=$(jq -r '.workflow_id // empty' "${temporary_directory}/create.json")
if [ -z "${workflow_id}" ]; then
    echo "Error: create response did not contain workflow_id." >&2
    exit 1
fi

curl --silent --show-error --insecure \
    --header "Authorization: Bearer ${access_token}" \
    --output "${temporary_directory}/workspace-before.json" \
    "${server_url%/}/api/workflows/${workflow_id}/workspace"
if jq -e '.items[]? | select(.name == "data/input.txt")' \
    "${temporary_directory}/workspace-before.json" >/dev/null; then
    echo "Error: input dataset was present before the explicit upload." >&2
    exit 1
fi
for expected in reana.yaml code/helper.py rules/common.py; do
    if ! jq -e --arg name "${expected}" \
        '.items[]? | select(.name == $name)' \
        "${temporary_directory}/workspace-before.json" >/dev/null; then
        echo "Error: validation member '${expected}' is missing from workspace." >&2
        exit 1
    fi
done

echo "Uploading the declared input dataset after validation..."
upload_status=$(curl --silent --show-error --insecure \
    --header "Authorization: Bearer ${access_token}" \
    --header "Content-Type: application/octet-stream" \
    --output "${temporary_directory}/upload.json" \
    --write-out '%{http_code}' \
    --request POST \
    --data-binary "@${temporary_directory}/source/data/input.txt" \
    "${server_url%/}/api/workflows/${workflow_id}/workspace?file_name=data/input.txt")
if [ "${upload_status}" != "200" ]; then
    echo "Error: input upload failed (HTTP ${upload_status})." >&2
    cat "${temporary_directory}/upload.json" >&2
    exit 1
fi

echo "Verifying that the workspace upload preserved every byte..."
download_status=$(curl --silent --show-error --insecure \
    --header "Authorization: Bearer ${access_token}" \
    --output "${temporary_directory}/downloaded-input.txt" \
    --write-out '%{http_code}' \
    "${server_url%/}/api/workflows/${workflow_id}/workspace/data/input.txt")
if [ "${download_status}" != "200" ]; then
    echo "Error: input download failed (HTTP ${download_status})." >&2
    exit 1
fi
if ! cmp --silent \
    "${temporary_directory}/source/data/input.txt" \
    "${temporary_directory}/downloaded-input.txt"; then
    echo "Error: uploaded input differs from the downloaded workspace file." >&2
    exit 1
fi

echo "Checking malicious and compressed snapshots are rejected cleanly..."
SOURCE_DIR="${temporary_directory}/source" python3 - <<'PY'
import os
import zipfile

source = os.environ["SOURCE_DIR"]
with zipfile.ZipFile(os.path.join(source, "traversal.zip"), "w") as archive:
    archive.writestr("../escape", "escaped")
    archive.write(os.path.join(source, "reana.yaml"), "reana.yaml")
with zipfile.ZipFile(
    os.path.join(source, "compressed.zip"),
    "w",
    compression=zipfile.ZIP_DEFLATED,
) as archive:
    archive.write(os.path.join(source, "reana.yaml"), "reana.yaml")
PY

for archive in traversal compressed; do
    status=$(curl --silent --show-error --insecure \
        --header "Authorization: Bearer ${access_token}" \
        --output "${temporary_directory}/${archive}.json" \
        --write-out '%{http_code}' \
        --form "bundle=@${temporary_directory}/source/${archive}.zip;filename=${archive}.zip" \
        "${server_url%/}/api/workflows/validate")
    if [ "${status}" != "400" ]; then
        echo "Error: ${archive} snapshot returned HTTP ${status}, expected 400." >&2
        cat "${temporary_directory}/${archive}.json" >&2
        exit 1
    fi
done

echo "Validation storage contract passed for workflow ${workflow_id}."
