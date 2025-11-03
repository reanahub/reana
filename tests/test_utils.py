# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for reana_dev/utils.py"""
import os
import tempfile
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
        "original",
        ["0.8.0-alpha.2", "1.0.0-dev.1", "1.0.0-rc.1"],
    )
    def test_some_working_semver2_as_input(self, original: str):
        from reana.reana_dev.utils import translate_pep440_to_semver2

        assert translate_pep440_to_semver2(original) == original

    @pytest.mark.parametrize(
        "original",
        ["1.0.0-alpha.beta"],
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


class TestFindComponentDirectoryFromCurrentDir:
    def test_find_component_from_nested_directory(self):
        """Test that component is detected from nested subdirectories."""
        from reana.reana_dev.utils import find_component_directory_from_current_dir

        # Save current directory
        original_dir = os.getcwd()

        try:
            # Create a temporary directory structure: component/.git and component/tests/subdir
            with tempfile.TemporaryDirectory() as tmpdir:
                component_dir = os.path.join(tmpdir, "reana-server")
                git_dir = os.path.join(component_dir, ".git")
                tests_dir = os.path.join(component_dir, "tests")
                subdir = os.path.join(tests_dir, "subdir")

                os.makedirs(git_dir)
                os.makedirs(subdir)

                # Resolve symlinks for comparison (e.g., /var -> /private/var on macOS)
                component_dir_real = os.path.realpath(component_dir)

                # Test from component root
                os.chdir(component_dir)
                assert (
                    os.path.realpath(find_component_directory_from_current_dir())
                    == component_dir_real
                )

                # Test from nested tests directory
                os.chdir(tests_dir)
                assert (
                    os.path.realpath(find_component_directory_from_current_dir())
                    == component_dir_real
                )

                # Test from deeply nested subdirectory
                os.chdir(subdir)
                assert (
                    os.path.realpath(find_component_directory_from_current_dir())
                    == component_dir_real
                )

        finally:
            # Restore original directory
            os.chdir(original_dir)

    def test_find_component_fails_without_git(self):
        """Test that an exception is raised when no .git directory is found."""
        from reana.reana_dev.utils import find_component_directory_from_current_dir

        # Save current directory
        original_dir = os.getcwd()

        try:
            # Create a temporary directory without .git
            with tempfile.TemporaryDirectory() as tmpdir:
                no_git_dir = os.path.join(tmpdir, "no-git-component")
                os.makedirs(no_git_dir)
                os.chdir(no_git_dir)

                with pytest.raises(Exception, match="Cannot find .git directory"):
                    find_component_directory_from_current_dir()

        finally:
            # Restore original directory
            os.chdir(original_dir)
