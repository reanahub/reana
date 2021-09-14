# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for reana_dev/utils.py"""
import pytest


class TestTranslatePep440ToSemver2:
    @pytest.mark.parametrize(
        "original, expected",
        [("1.0.0.dev1", "1.0.0-dev.1"), ("0.8.0a2", "0.8.0-alpha.2")],
    )
    def test_pep440_to_semver2(self, original: str, expected: str):
        from reana.reana_dev.utils import translate_pep440_to_semver2

        assert translate_pep440_to_semver2(original) == expected

    @pytest.mark.parametrize(
        "original", ["0.8.0-alpha.2", "1.0.0-dev.1", "1.0.0-rc.1"],
    )
    def test_some_working_semver2_as_input(self, original: str):
        from reana.reana_dev.utils import translate_pep440_to_semver2

        assert translate_pep440_to_semver2(original) == original

    @pytest.mark.parametrize(
        "original", ["1.0.0-alpha.beta"],
    )
    def test_some_failing_semver2_as_input(self, original: str):
        from reana.reana_dev.utils import translate_pep440_to_semver2

        with pytest.raises(Exception):
            translate_pep440_to_semver2(original)


class TestParsePep440Version:
    @pytest.mark.parametrize(
        "original, expected",
        [("0.7.0-alpha.1", "0.7.0a1"), ("0.8.0-alpha.2", "0.8.0a2")],
    )
    def test_semver2_to_pep440(self, original: str, expected: str):
        """
        Underlying package.versioning.Version can handle SemVer2 format
        """
        from reana.reana_dev.utils import parse_pep440_version

        assert str(parse_pep440_version(original)) == expected
