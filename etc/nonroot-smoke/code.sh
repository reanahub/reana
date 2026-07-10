#!/bin/bash

set -euo pipefail

mkdir -p results

if [[ -f results/persist.txt ]]; then
    printf 'second\n' >>results/persist.txt
    printf 'detected-existing-workspace\n' >results/proof.txt
else
    printf 'first\n' >results/persist.txt
    printf 'initialized-new-workspace\n' >results/proof.txt
fi

# Keep the user job alive long enough for live security-context inspection.
sleep "${SMOKE_HOLD_SECONDS:-60}"
