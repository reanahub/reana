#!/bin/sh

set -eu

NODE_CONTAINER="${1:-kind-control-plane}"
BASE_DIR="${BASE_DIR:-/var/lib/rook-dev}"
MAP_FILE="${BASE_DIR}/device-map.txt"

echo "Cleaning loop-backed raw devices from ${NODE_CONTAINER}..."

docker exec "${NODE_CONTAINER}" sh -lc "
set -eu
map='${MAP_FILE}'
cleanup_image() {
    dev=\"\$1\"
    img=\"\$2\"
    current=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
    if [ -n \"\${current}\" ] && { [ -z \"\${dev}\" ] || [ \"\${current}\" = \"\${dev}\" ]; }; then
        losetup -d \"\${current}\" || true
        echo \"Detached \${current} from \${img}\"
    elif [ -n \"\${current}\" ]; then
        echo \"Leaving \${current} attached to \${img}; expected \${dev}\" >&2
    fi
    rm -f \"\${img}\"
}
if [ -f \"\${map}\" ]; then
    while read -r dev img; do
        [ -n \"\${dev}\" ] || continue
        cleanup_image \"\${dev}\" \"\${img}\"
    done < \"\${map}\"
    rm -f \"\${map}\"
else
    for img in '${BASE_DIR}'/osd-*.img; do
        [ -e \"\${img}\" ] || continue
        dev=\$(losetup -j \"\${img}\" | cut -d: -f1 | head -n 1 || true)
        cleanup_image \"\${dev}\" \"\${img}\"
    done
fi
rmdir '${BASE_DIR}' 2>/dev/null || true
"
