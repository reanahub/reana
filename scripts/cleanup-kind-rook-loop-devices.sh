#!/bin/sh
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

set -eu

STATE_HOME="${XDG_STATE_HOME:-${HOME:-.}/.local/state}"
STATE_FILE="${1:-${REANA_DEV_CEPHFS_STATE_FILE:-${STATE_HOME}/reana-dev/kind-cephfs.state}}"
NODE_CONTAINER="kind-control-plane"
NODE_IMAGE=""
BASE_DIR="/var/lib/rook-dev"
if [ -f "${STATE_FILE}" ]; then
    persisted_node_container="$(awk -F '\t' '$1 == "node_container" { print $2; exit }' "${STATE_FILE}")"
    persisted_node_image="$(awk -F '\t' '$1 == "node_image" { print $2; exit }' "${STATE_FILE}")"
    persisted_base_dir="$(awk -F '\t' '$1 == "base_dir" { print $2; exit }' "${STATE_FILE}")"
    NODE_CONTAINER="${persisted_node_container:-${NODE_CONTAINER}}"
    NODE_IMAGE="${persisted_node_image:-${NODE_IMAGE}}"
    BASE_DIR="${persisted_base_dir:-${BASE_DIR}}"
fi
MAP_FILE="${BASE_DIR}/device-map.txt"

echo "Cleaning loop-backed raw devices owned by ${NODE_CONTAINER}..."

if docker inspect "${NODE_CONTAINER}" >/dev/null 2>&1; then
    docker start "${NODE_CONTAINER}" >/dev/null 2>&1 || true
    docker exec "${NODE_CONTAINER}" sh -lc "
set -eu
map='${MAP_FILE}'
cleanup_image() {
    expected_dev=\"\$1\"
    img=\"\$2\"
    current=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
    if [ -n \"\${current}\" ]; then
        if [ -n \"\${expected_dev}\" ] && [ \"\${current}\" != \"\${expected_dev}\" ]; then
            echo \"Owned image \${img} moved from \${expected_dev} to \${current}\"
        fi
        losetup -d \"\${current}\"
        echo \"Detached \${current} from \${img}\"
    fi
    rm -f \"\${img}\"
}
if [ -f \"\${map}\" ]; then
    while read -r dev img; do
        [ -n \"\${dev}\" ] || continue
        cleanup_image \"\${dev}\" \"\${img}\"
    done < \"\${map}\"
    rm -f \"\${map}\"
fi
# Always reconcile owned backing images, including surplus images omitted by
# a map written by an older or interrupted setup run.
for img in '${BASE_DIR}'/osd-*.img; do
    [ -e \"\${img}\" ] || continue
    dev=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
    cleanup_image \"\${dev}\" \"\${img}\"
done
rmdir '${BASE_DIR}' 2>/dev/null || true
"
    rm -f "${STATE_FILE}"
    exit 0
fi

if [ ! -f "${STATE_FILE}" ] || [ -z "${NODE_IMAGE}" ]; then
    echo "Node container ${NODE_CONTAINER} is unavailable and no complete lifecycle state was found at ${STATE_FILE}." >&2
    exit 1
fi

# Loop mappings live in the Docker VM kernel. If the Kind node was already
# removed, use its locally cached image as a short-lived privileged recovery
# container and detach only devices whose backing file still matches our state.
cleanup_failed=false
tab="$(printf '\t')"
while IFS="${tab}" read -r key dev img; do
    [ "${key}" = "device" ] || continue
    if ! docker run --rm --privileged --entrypoint /bin/sh "${NODE_IMAGE}" -c '
        set -eu
        recorded_dev="$1"
        expected_img="$2"
        dev="$(
            losetup -l -n -O NAME,BACK-FILE |
                while read -r candidate backing _; do
                    case "${backing}" in
                    *"${expected_img}")
                        printf "%s" "${candidate}"
                        break
                        ;;
                    esac
                done
        )"
        [ -n "${dev}" ] || exit 0
        backing="$(losetup -n -O BACK-FILE "${dev}")"
        case "${backing}" in
        *"${expected_img}"* | *"/$(basename "${expected_img}")"*)
            if [ "${dev}" != "${recorded_dev}" ]; then
                echo "Owned image ${expected_img} moved from ${recorded_dev} to ${dev}"
            fi
            losetup -d "${dev}"
            echo "Detached ${dev} from ${backing}"
            ;;
        *)
            echo "Refusing to detach ${dev}; current backing file is ${backing}, expected ${expected_img}" >&2
            exit 1
            ;;
        esac
    ' cleanup "${dev}" "${img}"; then
        cleanup_failed=true
    fi
done <"${STATE_FILE}"

if [ "${cleanup_failed}" = "true" ]; then
    echo "One or more owned loop mappings could not be recovered; retaining ${STATE_FILE}." >&2
    exit 1
fi

rm -f "${STATE_FILE}"
