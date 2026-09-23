#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

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
