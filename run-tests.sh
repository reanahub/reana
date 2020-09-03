#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# Quit on errors
set -o errexit

# Quit on unbound symbols
set -o nounset

check_black() {
    echo '==> [INFO] Checking Black compliance...'
    black --check .
}

pydocstyle reana
check_black
check-manifest
sphinx-build -qnNW docs docs/_build/html
python setup.py test
sphinx-build -qnNW -b doctest docs docs/_build/doctest
helm lint helm/reana
echo '==> [INFO] All tests passed! ✅'
