#!/bin/sh

set -eu

NODE_CONTAINER="${1:-kind-control-plane}"
DEVICE_COUNT="${DEVICE_COUNT:-3}"
DEVICE_SIZE="${DEVICE_SIZE:-6G}"
BASE_DIR="${BASE_DIR:-/var/lib/rook-dev}"
MAP_FILE="${BASE_DIR}/device-map.txt"

if [ "${DEVICE_COUNT}" -lt 1 ]; then
    echo "DEVICE_COUNT must be at least 1" >&2
    exit 1
fi

echo "Provisioning ${DEVICE_COUNT} loop-backed raw devices in ${NODE_CONTAINER}..."

docker exec "${NODE_CONTAINER}" sh -lc "
set -eu
mkdir -p '${BASE_DIR}' /run/udev/data
map='${MAP_FILE}'
: > \"\${map}\"
pgrep -af systemd-udevd >/dev/null 2>&1 || /lib/systemd/systemd-udevd --daemon
for i in \$(seq 0 $((DEVICE_COUNT - 1))); do
    img='${BASE_DIR}/osd-'\${i}'.img'
    current=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
    if [ -n \"\${current}\" ]; then
        dev=\"\${current}\"
        echo \"Reusing \${dev} -> \${img}\"
    else
        rm -f \"\${img}\"
        truncate -s '${DEVICE_SIZE}' \"\${img}\"
        dev=\$(losetup --find --show \"\${img}\")
        echo \"Attached \${dev} -> \${img}\"
    fi
    printf '%s %s\n' \"\${dev}\" \"\${img}\" >> \"\${map}\"
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
