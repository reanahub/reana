#!/bin/sh

set -eu

NODE_CONTAINER="${1:-kind-control-plane}"
DEVICE_COUNT="${DEVICE_COUNT:-3}"
BASE_DIR="${BASE_DIR:-/var/lib/rook-dev}"

echo "Cleaning loop-backed raw devices from ${NODE_CONTAINER}..."

docker exec "${NODE_CONTAINER}" sh -lc "
set -eu
for i in \$(seq 0 $((DEVICE_COUNT - 1))); do
    img='${BASE_DIR}/osd-'\${i}'.img'
    dev='/dev/loop'\${i}
    current=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
    if [ -n \"\${current}\" ]; then
        losetup -d \"\${current}\" || true
        echo \"Detached \${current} from \${img}\"
    elif losetup \"\${dev}\" >/dev/null 2>&1; then
        attached=\$(losetup \"\${dev}\" | sed -n 's/.*(\\(.*\\)).*/\\1/p' || true)
        if [ -n \"\${attached}\" ]; then
            echo \"Leaving \${dev} attached to unrelated backing file \${attached}\"
        fi
    fi
    rm -f \"\${img}\"
done
rmdir '${BASE_DIR}' 2>/dev/null || true
"
