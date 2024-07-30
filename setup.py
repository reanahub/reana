#
# This file is part of REANA.
# Copyright (C) 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""REANA - Reusable Analyses"""

from __future__ import absolute_import, print_function

import os
import re

from setuptools import find_packages, setup

readme = open("README.md").read()
history = open("CHANGELOG.md").read()

extras_require = {
    "docs": [
        "myst-parser",
        "Sphinx>=1.5.1",
    ],
    "tests": [
        "pytest-reana>=0.9.2,<0.10.0",
    ],
    "benchmark": [
        "pandas>=1.1.5",
        "matplotlib>=3.3.4",
    ],
}

extras_require["all"] = []
for key, reqs in extras_require.items():
    if ":" == key[0]:
        continue
    extras_require["all"].extend(reqs)


install_requires = [
    "click>=7",
    "colorama>=0.3.9",
    "PyYAML>=5.1,<7.0",
    "semver>=2.10.2,<3.0.0",
    "packaging>=20.4",
]

packages = find_packages()


# Get the version string. Cannot be done with import!
with open(os.path.join("reana", "version.py"), "rt") as f:
    version = re.search(r'__version__\s*=\s*"(?P<version>.*)"\n', f.read()).group(
        "version"
    )

setup(
    name="reana",
    version=version,
    description=__doc__,
    long_description=readme + "\n\n" + history,
    long_description_content_type="text/markdown",
    author="REANA",
    author_email="info@reana.io",
    url="http://www.reana.io/",
    packages=packages,
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "reana-dev = reana.reana_dev.cli:reana_dev",
            "reana-benchmark = reana.reana_benchmark.cli:reana_benchmark",
        ],
    },
    python_requires=">=3.8",
    extras_require=extras_require,
    install_requires=install_requires,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
