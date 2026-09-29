# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2021, 2022, 2025, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for reana_dev/utils.py"""

import json
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


class TestBumpSemver2Version:
    @pytest.mark.parametrize(
        "original, expected",
        [
            ("0.0.0", "0.0.1"),
            ("0.0.1", "0.0.2"),
            ("0.1.0", "0.2.0"),
            ("1.0.0", "2.0.0"),
            ("0.95.0-alpha.1", "0.95.0-alpha.2"),
            ("0.0.0+build.1", "0.0.0+build.2"),
        ],
    )
    def test_automatic_bump(self, original: str, expected: str):
        """Test automatic bumps, including the all-zero initial version."""
        from reana.reana_dev.utils import bump_semver2_version

        assert bump_semver2_version(original) == expected


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


class TestGoComponentVersion:
    def test_version_read_from_annotated_line(self, tmp_path, monkeypatch):
        """Test that the Release Please annotation marks the version to read."""
        from reana.config import GO_VERSION_FILE
        from reana.reana_dev import utils

        version_file = tmp_path / "version.go"
        version_file.write_text(
            "package cmd\n\n"
            'const name = "reana-client-go"\n'
            'const version = "v0.95.0-alpha.1" // x-release-please-version\n'
        )
        monkeypatch.setattr(
            utils,
            "get_component_version_files",
            lambda component, abs_path=False: {GO_VERSION_FILE: str(version_file)},
        )

        assert (
            utils.get_current_component_version_from_source_files("reana-client-go")
            == "0.95.0-alpha.1"
        )

    def test_version_read_from_annotated_block(self, tmp_path, monkeypatch):
        """Test that the block annotation form is understood as well."""
        from reana.config import GO_VERSION_FILE
        from reana.reana_dev import utils

        version_file = tmp_path / "version.go"
        version_file.write_text(
            "package version\n\n"
            "// x-release-please-start-version\n"
            'var Version = "0.0.0"\n\n'
            "// x-release-please-end\n"
        )
        monkeypatch.setattr(
            utils,
            "get_component_version_files",
            lambda component, abs_path=False: {GO_VERSION_FILE: str(version_file)},
        )

        assert (
            utils.get_current_component_version_from_source_files(
                "reana-datastore-s3fs"
            )
            == "0.0.0"
        )

    def test_version_missing_without_annotation(self, tmp_path, monkeypatch):
        """Test that unannotated string constants are not mistaken for versions."""
        from reana.config import GO_VERSION_FILE
        from reana.reana_dev import utils

        version_file = tmp_path / "version.go"
        version_file.write_text('package cmd\n\nconst version = "v0.95.0-alpha.1"\n')
        monkeypatch.setattr(
            utils,
            "get_component_version_files",
            lambda component, abs_path=False: {GO_VERSION_FILE: str(version_file)},
        )

        assert (
            utils.get_current_component_version_from_source_files("reana-client-go")
            == ""
        )


class TestGetComponentGitTagName:
    @pytest.mark.parametrize(
        "include_v_in_tag, expected",
        [(True, "v0.95.0-alpha.1"), (False, "0.95.0-alpha.1")],
    )
    def test_prefix_follows_release_please_config(
        self, tmp_path, monkeypatch, include_v_in_tag: bool, expected: str
    ):
        """Test that the tag prefix honours the component's Release Please setting."""
        from reana.config import RELEASE_PLEASE_CONFIG_FILE
        from reana.reana_dev import utils

        (tmp_path / RELEASE_PLEASE_CONFIG_FILE).write_text(
            json.dumps({"include-v-in-tag": include_v_in_tag})
        )
        monkeypatch.setattr(utils, "get_srcdir", lambda component="": str(tmp_path))

        assert (
            utils.get_component_git_tag_name("reana-client-go", "0.95.0-alpha.1")
            == expected
        )

    def test_missing_config_keeps_bare_version(self, tmp_path, monkeypatch):
        """Test that components without a Release Please config tag bare versions."""
        from reana.reana_dev import utils

        monkeypatch.setattr(utils, "get_srcdir", lambda component="": str(tmp_path))

        assert (
            utils.get_component_git_tag_name("reana-demo-helloworld", "0.9.4")
            == "0.9.4"
        )

    def test_already_prefixed_version_is_kept(self, tmp_path, monkeypatch):
        """Test that an already prefixed version is not prefixed twice."""
        from reana.reana_dev import utils

        monkeypatch.setattr(utils, "get_srcdir", lambda component="": str(tmp_path))

        assert (
            utils.get_component_git_tag_name("reana-client-go", "v0.95.0-alpha.1")
            == "v0.95.0-alpha.1"
        )

    def test_unknown_version_has_no_tag_name(self):
        """Test that an undiscoverable version does not produce a tag name."""
        from reana.reana_dev import utils

        assert utils.get_component_git_tag_name("reana-client-go", "") == ""


class TestBumpComponentVersion:
    def test_zero_version_bumps_docker_and_go_files(self, tmp_path, monkeypatch):
        """Test that an automatic initial release preserves both version fields."""
        from reana.config import DOCKER_VERSION_FILE, GO_VERSION_FILE
        from reana.reana_dev import utils

        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text('LABEL org.opencontainers.image.version="0.0.0"\n')
        go_file = tmp_path / "internal" / "version" / "version.go"
        go_file.parent.mkdir(parents=True)
        go_file.write_text(
            "package version\n\n"
            "// x-release-please-start-version\n"
            'var Version = "0.0.0"\n'
            "// x-release-please-end\n"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(utils, "get_srcdir", lambda component="": str(tmp_path))
        monkeypatch.setattr(
            utils,
            "get_component_version_files",
            lambda component, abs_path=False: {
                DOCKER_VERSION_FILE: str(dockerfile),
                GO_VERSION_FILE: str(go_file),
            },
        )

        next_version, modified_files = utils.bump_component_version(
            "reana-datastore-s3fs"
        )

        assert next_version == "0.0.1"
        assert set(modified_files) == {str(dockerfile), str(go_file)}
        assert 'org.opencontainers.image.version="0.0.1"' in dockerfile.read_text()
        assert 'var Version = "0.0.1"' in go_file.read_text()

    def test_unparsable_version_file_rewrites_nothing(self, monkeypatch):
        """Test that an unreadable version file aborts before any file is written."""
        from reana.config import DOCKER_VERSION_FILE, GO_VERSION_FILE
        from reana.reana_dev import utils

        monkeypatch.setattr(
            utils,
            "get_component_version_files",
            lambda component, abs_path=False: {
                DOCKER_VERSION_FILE: "Dockerfile",
                GO_VERSION_FILE: "internal/version/version.go",
            },
        )
        monkeypatch.setattr(
            utils,
            "get_current_component_version_from_source_files",
            lambda component, version_file=None: (
                "0.0.0" if version_file == DOCKER_VERSION_FILE else ""
            ),
        )

        def fail_on_write(*args, **kwargs):
            raise AssertionError("no version file should have been rewritten")

        monkeypatch.setattr(utils, "replace_string", fail_on_write)

        with pytest.raises(Exception, match="Cannot detect the current version"):
            utils.bump_component_version("reana-datastore-s3fs", next_version="0.0.1")
