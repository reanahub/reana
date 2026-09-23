#!/bin/sh
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

set -eu

NODE_CONTAINER="${1:-kind-control-plane}"
NODE_NAME="${2:-${NODE_CONTAINER}}"
STATE_HOME="${XDG_STATE_HOME:-${HOME:-.}/.local/state}"
STATE_FILE="${3:-${REANA_DEV_CEPHFS_STATE_FILE:-${STATE_HOME}/reana-dev/kind-cephfs.state}}"
DEVICE_COUNT="${DEVICE_COUNT:-3}"
DEVICE_SIZE="${DEVICE_SIZE:-6G}"
BASE_DIR="${BASE_DIR:-/var/lib/rook-dev}"
MAP_FILE="${BASE_DIR}/device-map.txt"

case "${DEVICE_COUNT}" in
'' | *[!0-9]* | 0)
    echo "DEVICE_COUNT must be at least 1" >&2
    exit 1
    ;;
esac

echo "Provisioning ${DEVICE_COUNT} loop-backed raw devices in ${NODE_CONTAINER}..."

docker exec "${NODE_CONTAINER}" sh -lc "
set -eu
mkdir -p '${BASE_DIR}' /run/udev/data
map='${MAP_FILE}'
new_map=\"\${map}.new\"
: > \"\${new_map}\"
pgrep -af systemd-udevd >/dev/null 2>&1 || /lib/systemd/systemd-udevd --daemon
for i in \$(seq 0 $((DEVICE_COUNT - 1))); do
    img='${BASE_DIR}/osd-'\${i}'.img'
    current=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
    if [ -n \"\${current}\" ]; then
        dev=\"\${current}\"
        echo \"Reusing \${dev} -> \${img}\"
    else
        if [ ! -f \"\${img}\" ]; then
            truncate -s '${DEVICE_SIZE}' \"\${img}\"
        fi
        dev=\$(losetup --find --show \"\${img}\")
        echo \"Attached \${dev} -> \${img}\"
    fi
    [ -b \"\${dev}\" ] || {
        echo \"Expected block device \${dev} does not exist\" >&2
        exit 1
    }
    printf '%s %s\n' \"\${dev}\" \"\${img}\" >> \"\${new_map}\"
    major_minor=\$(cat \"/sys/block/\${dev##*/}/dev\")
    major=\${major_minor%%:*}
    minor=\${major_minor##*:}
    udev=\"/run/udev/data/b\${major}:\${minor}\"
    for _ in \$(seq 1 10); do
        [ -f \"\${udev}\" ] && break
        sleep 1
    done
    if [ ! -f \"\${udev}\" ]; then
        echo \"Missing udev metadata for \${dev} after attach; will synthesize it later\"
    fi
done

# Reconcile devices from earlier runs that are no longer requested.
for img in '${BASE_DIR}'/osd-*.img; do
    [ -e \"\${img}\" ] || continue
    if awk -v image=\"\${img}\" '\$2 == image { found = 1 } END { exit !found }' \"\${new_map}\"; then
        continue
    fi
    current=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
    if [ -n \"\${current}\" ]; then
        losetup -d \"\${current}\"
        echo \"Detached surplus mapping \${current} -> \${img}\"
    fi
    rm -f \"\${img}\"
done
mv \"\${new_map}\" \"\${map}\"

for sysdev in /sys/block/* /sys/block/*/*; do
    [ -e \"\${sysdev}\" ] || continue
    [ -f \"\${sysdev}/dev\" ] || continue
    name=\$(basename \"\${sysdev}\")
    devfile=\"\${sysdev}/dev\"
    major_minor=\$(cat \"\${devfile}\")
    major=\${major_minor%%:*}
    minor=\${major_minor##*:}
    udev=\"/run/udev/data/b\${major}:\${minor}\"
    if [ -f \"\${udev}\" ]; then
        continue
    fi
    dev=\"/dev/\${name}\"
    udevadm info --query=all --name \"\${dev}\" | sed -n '/^[SIEGQV]:/p' > \"\${udev}\" || true
    if [ ! -s \"\${udev}\" ]; then
        diskseq=\$(cat \"\${sysdev}/diskseq\" 2>/dev/null || echo 0)
        {
            printf 'S:disk/by-diskseq/%s\n' \"\${diskseq}\"
            printf 'I:%s\n' \"\${diskseq}\"
            printf 'G:systemd\n'
            printf 'Q:systemd\n'
            printf 'V:1\n'
            printf 'E:DEVNAME=%s\n' \"\${dev}\"
            printf 'E:DEVTYPE=disk\n'
            printf 'E:DISKSEQ=%s\n' \"\${diskseq}\"
            printf 'E:MAJOR=%s\n' \"\${major}\"
            printf 'E:MINOR=%s\n' \"\${minor}\"
            printf 'E:SUBSYSTEM=block\n'
        } > \"\${udev}\"
    fi
    echo \"Synthesized udev metadata for /dev/\${name}\"
done

echo
echo \"Owned loop device mappings:\"
cat \"\${map}\"
echo
losetup -a | grep '${BASE_DIR}' || true
"

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

echo "Recorded CephFS lifecycle state in ${STATE_FILE}."
