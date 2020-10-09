# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev` related utils."""

import datetime
import importlib.util
import json
import os
import subprocess
import sys

import click
import semver
import yaml
from packaging.version import InvalidVersion, Version

from reana.config import (
    COMPONENTS_USING_SHARED_MODULE_COMMONS,
    COMPONENTS_USING_SHARED_MODULE_DB,
    HELM_VERSION_FILE,
    JAVASCRIPT_VERSION_FILE,
    OPENAPI_VERSION_FILE,
    PYTHON_VERSION_FILE,
    REPO_LIST_ALL,
    REPO_LIST_CLIENT,
    REPO_LIST_CLUSTER,
    REPO_LIST_DEMO,
    CLUSTER_DEPLOYMENT_MODES,
)

INSTANCE_NAME = os.path.basename(os.environ["VIRTUAL_ENV"])


def shorten_component_name(component):
    """Return canonical short version of the component name.

    Example: reana-workflow-controller -> r-w-controller

    :param component: standard component name
    :type component: str

    :return: short component name
    :rtype: str
    """
    short_name = ""
    parts = component.split("-")
    for part in parts[:-1]:
        short_name += part[0] + "-"
    short_name += parts[-1]
    return short_name


def find_standard_component_name(component_name):
    """Return standard component name corresponding to the component name.

    Note this is an idempotent operation, if ``component_name`` is already
    standard it will return it as it is.

    Example: r-w-controller -> reana-workflow-controller
             reana-ui       -> reana-ui

    :param component_name: component name
    :type component: str

    :return: standard component name
    :rtype: str

    :raise: exception in case more than one is found
    """

    def _is_standard_name(component_name):
        """Detect whether the provided component name is already standard."""
        prefixes = component_name.split("-")[:-1]
        return all([len(n) > 1 for n in prefixes])

    if _is_standard_name(component_name):
        standard_component_name = component_name
    else:
        output = []
        for component in REPO_LIST_ALL:
            component_short_name = shorten_component_name(component)
            if component_short_name == component_name:
                output.append(component)
        if len(output) == 1:
            standard_component_name = output[0]
        else:
            raise Exception(
                "Component name {0} cannot be uniquely "
                "mapped.".format(component_name)
            )

    return standard_component_name


def find_reana_srcdir():
    """Find directory where REANA sources are checked out.

    Try to go up from the current directory until you find the first parent
    directory where REANA cluster repositories are checked out.

    :return: source code directory for given component
    :rtype: str

    :raise: exception in case it is not found
    """
    # first, try current working directory:
    srcdir = os.getcwd()
    if os.path.exists(srcdir + os.sep + "reana" + os.sep + ".git" + os.sep + "config"):
        return srcdir
    # second, try from the parent of git toplevel:
    toplevel = (
        subprocess.check_output("git rev-parse --show-toplevel", shell=True)
        .decode()
        .rstrip("\r\n")
    )
    srcdir = toplevel.rsplit(os.sep, 1)[0]
    if os.path.exists(srcdir + os.sep + "reana" + os.sep + ".git" + os.sep + "config"):
        return srcdir
    # fail if not found
    raise Exception(
        "Cannot find REANA component source directory " "in {0}.".format(srcdir)
    )


def get_srcdir(component=""):
    """Return source code directory of the given REANA component.

    :param component: standard component name
    :type component: str

    :return: source code directory for given component
    :rtype: str
    """
    reana_srcdir = find_reana_srcdir()
    if component:
        return reana_srcdir + os.sep + component
    else:
        return reana_srcdir


def get_current_branch(srcdir):
    """Return current Git branch name checked out in the given directory.

    :param srcdir: source code directory
    :type srcdir: str

    :return: checkout out branch in the component source code directory
    :rtype: str
    """
    os.chdir(srcdir)
    return (
        subprocess.check_output(
            'git branch 2>/dev/null | grep "^*" | colrm 1 2', shell=True
        )
        .decode()
        .rstrip("\r\n")
    )


def select_components(components, exclude_components=None):
    """Return expanded and unified component name list based on input values.

    :param components: A list of component name that may consist of:
                          * (1) standard component names such as
                                'reana-workflow-controller';
                          * (2) short component name such as 'r-w-controller';
                          * (3) special value '.' indicating component of the
                                current working directory;
                          * (4) special value 'CLUSTER' that will expand to
                                cover all REANA cluster components;
                          * (5) special value 'CLIENT' that will expand to
                                cover all REANA client components;
                          * (6) special value 'DEMO' that will expand
                                to include several runable REANA demo examples;
                          * (7) special value 'ALL' that will expand to include
                                all REANA repositories.
    :param exclude_components: A list of components to exclude.
    :type components: list
    :type exclude_components: list

    :return: Unique standard component names.
    :rtype: list

    """
    short_component_names = [shorten_component_name(name) for name in REPO_LIST_ALL]
    output = set([])
    for component in components:
        if component == "ALL":
            for repo in REPO_LIST_ALL:
                output.add(repo)
        elif component == "DEMO":
            for repo in REPO_LIST_DEMO:
                output.add(repo)
        elif component == "CLIENT":
            for repo in REPO_LIST_CLIENT:
                output.add(repo)
        elif component == "CLUSTER":
            for repo in REPO_LIST_CLUSTER:
                output.add(repo)
        elif component == ".":
            cwd = os.path.basename(os.getcwd())
            output.add(cwd)
        elif component in REPO_LIST_ALL:
            output.add(component)
        elif component in short_component_names:
            component_standard_name = find_standard_component_name(component)
            output.add(component_standard_name)
        else:
            display_message("Ignoring unknown component {0}.".format(component))

    if exclude_components:
        output = exclude_components_from_selection(output, exclude_components)

    return list(output)


def exclude_components_from_selection(selection, exclude_components):
    """Exclude list of components from list of selections.

    :param selection: List of selected components in standard naming form.
    :param exclude_components: List of components to exclude, either in short
        or standard naming form.
    :type selection: set
    :type exclude_components: list

    :return: Set of selected components without ``exclude_components``, all in
        standard naming form.
    :rtype: set
    """
    standard_named_exclude_components = [
        find_standard_component_name(c) for c in exclude_components
    ]
    non_existing_exclude_components = set(standard_named_exclude_components).difference(
        selection
    )
    if non_existing_exclude_components:
        display_message(
            "Unknown component(s) to exclude: {}".format(
                non_existing_exclude_components
            )
        )
        sys.exit(1)

    click.secho(
        "Excluding component(s) {}".format(standard_named_exclude_components),
        fg="yellow",
    )
    return selection.difference(standard_named_exclude_components)


def is_component_dockerised(component):
    """Return whether the component contains Dockerfile.

    Useful to skip some docker-related commands for those components that are
    not concerned, such as building Docker images for `reana-commons` that does
    not provide any.

    :param component: standard component name
    :type component: str

    :return: True/False whether the component is dockerisable
    :rtype: bool
    """
    if os.path.exists(get_srcdir(component) + os.sep + "Dockerfile"):
        return True
    return False


def is_component_runnable_example(component):
    """Return whether the component contains reana.yaml.

    Useful for safety check when using some run-example commands for those
    components that are not REANA examples.

    :param component: standard component name
    :type component: str

    :return: True/False whether the component is a REANA example
    :rtype: bool

    """
    if os.path.exists(get_srcdir(component) + os.sep + "reana.yaml"):
        return True
    return False


def run_command(cmd, component="", display=True, return_output=False):
    """Run given command in the given component source directory.

    Exit in case of troubles.

    :param cmd: shell command to run
    :param component: standard component name
    :param display: should we display command to run?
    :param return_output: shall the output of the command be returned?
    :type cmd: str
    :type component: str
    :type display: bool
    :type return_output: bool
    """
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if display:
        click.secho("[{0}] ".format(now), bold=True, nl=False, fg="green")
        click.secho("{0}: ".format(component), bold=True, nl=False, fg="yellow")
        click.secho("{0}".format(cmd), bold=True)
    if component:
        os.chdir(get_srcdir(component))
    try:
        if return_output:
            result = subprocess.check_output(cmd, shell=True)
            return result.decode().rstrip("\r\n")
        else:
            subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as err:
        if display:
            click.secho("[{0}] ".format(now), bold=True, nl=False, fg="green")
            click.secho("{0}: ".format(component), bold=True, nl=False, fg="yellow")
            click.secho("{0}".format(err), bold=True, fg="red")
        sys.exit(err.returncode)


def display_message(msg, component=""):
    """Display message in a similar style as run_command().

    :param msg: message to display
    :param component: standard component name
    :type msg: str
    :type component: str
    """
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    click.secho("[{0}] ".format(now), bold=True, nl=False, fg="green")
    click.secho("{0}: ".format(component), bold=True, nl=False, fg="yellow")
    click.secho("{0}".format(msg), bold=True)


def get_prefixed_component_name(component):
    """Get prefixed component name.

    :param component: String representing the component name.

    :return: Prefixed name.
    """
    return "-".join([INSTANCE_NAME, component])


def fetch_latest_pypi_version(package):
    """Fetch latest released version of a package."""
    import requests

    pypi_rc_info = requests.get("https://pypi.python.org/pypi/{}/json".format(package))
    return sorted(pypi_rc_info.json()["releases"].keys())[-1]


def is_last_commit_tagged(package):
    """Check whether the last commit of the module points at a tag."""
    tag = run_command("git tag --points-at", package, return_output=True)
    return bool(tag)


def is_feature_branch(component):
    """Check whether component current branch is different from master."""
    return get_current_branch(get_srcdir(component)) != "master"


def replace_string(
    file_=None, find=None, replace=None, line_selector_regex=None, component=None
):
    """Replace the old string with the new one in the specified file.

    :param file_: filename where the replacement takes place
                  (e.g. 'setup.py', 'requirements.txt')
    :param find: current string regex
    :param replace: new string regex
    :param line_selector_regex: grep expression to identify file line of the replacement
    :param component: standard component name where to run the command
    :type file_: str
    :type find: str
    :type replace: str
    :type line_selector_regex: str
    :type component: str
    """
    line = ""
    if line_selector_regex:
        line = run_command(
            f'cat {file_} | grep -n -e "{line_selector_regex}" | cut -f1 -d: ',
            return_output=True,
        )
        if not line:
            click.secho(
                f"[ERROR] Could not find `{line_selector_regex}` in {component}'s"
                f" `{file_}`. Please check `{file_}`.",
                err=True,
                fg="red",
            ),
            sys.exit(1)

    cmd = (
        f"sed -i.bk '{line}s/{find}/{replace}/' {file_} && [ -e {file_}.bk ]"
        f" && rm {file_}.bk"  # Compatibility with BSD sed
    )

    run_command(cmd, component)


def update_module_in_cluster_components(
    module,
    new_version,
    components_to_update=None,
    use_latest_known_tag=True,
    force_feature_branch=False,
):
    """Update the specified module version in all affected components."""
    updatable_components = {
        "reana-commons": COMPONENTS_USING_SHARED_MODULE_COMMONS + ["reana-client"],
        "reana-db": COMPONENTS_USING_SHARED_MODULE_DB,
    }[module]

    if components_to_update:
        components_to_update = set(components_to_update).intersection(
            set(updatable_components)
        )
    else:
        components_to_update = updatable_components

    if (
        components_to_update
        and not use_latest_known_tag
        and not is_last_commit_tagged(module)
    ):
        click.secho(
            f"[ERROR] Last commit of {module} does not point to a tag."
            " Use `--use-latest-known-tag` if you want to proceed using the latest"
            " known tag.",
            err=True,
            fg="red",
        ),
        sys.exit(1)

    for component in components_to_update:
        if force_feature_branch and not is_feature_branch(component):
            click.secho(
                f"[ERROR] Component {component} current branch is master."
                " Must be a feature branch.",
                err=True,
                fg="red",
            ),
            sys.exit(1)

        new_version_obj = Version(new_version)
        next_minor_version = ".".join(
            [
                str(new_version_obj.major),
                str(new_version_obj.minor + 1),
                str(new_version_obj.micro),
            ]
        )
        replace_string(
            file_="setup.py",
            find='>=.*,<.*[^",]',
            replace=f">={new_version},<{next_minor_version}",
            line_selector_regex=f"{module}.*>=",
            component=component,
        )
        if os.path.exists(get_srcdir(component) + os.sep + "requirements.txt"):
            replace_string(
                file_="requirements.txt",
                find="==.*#",
                replace=f"=={new_version}\t#",
                line_selector_regex=f"{module}.*==",
                component=component,
            )

    if components_to_update:
        click.secho(
            "✅ {module} updated to: {last_version}".format(
                module=module, last_version=new_version
            ),
            bold=True,
            fg="green",
        )


def get_component_version_files(component, abs_path=False):
    """Get a dictionary with all component's version files."""
    version_files = {}
    for file_ in [
        HELM_VERSION_FILE,
        OPENAPI_VERSION_FILE,
        JAVASCRIPT_VERSION_FILE,
        PYTHON_VERSION_FILE,
    ]:
        file_path = run_command(
            f"git ls-files | grep -w {file_} || true",
            component,
            display=False,
            return_output=True,
        )
        if file_path and abs_path:
            file_path = os.path.join(get_srcdir(component=component), file_path)

        version_files[file_] = file_path

    return version_files


def get_current_component_version_from_source_files(component):
    """Get component's current version."""
    version_files = get_component_version_files(component, abs_path=True)
    version = ""
    if version_files.get(HELM_VERSION_FILE):
        with open(version_files.get(HELM_VERSION_FILE)) as f:
            chart_yaml = yaml.safe_load(f.read())
            version = chart_yaml["version"]

    elif version_files.get(PYTHON_VERSION_FILE):
        spec = importlib.util.spec_from_file_location(
            component, version_files.get(PYTHON_VERSION_FILE)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        version = module.__version__

    elif version_files.get(JAVASCRIPT_VERSION_FILE):
        with open(version_files.get(JAVASCRIPT_VERSION_FILE)) as f:
            package_json = json.loads(f.read())
            version = package_json["version"]

    return version


def bump_semver2_version(current_version, part=None, pre_version_prefix=None):
    """Bump a semver2 version string.

    :param current_version: current version to be bumped
    :type current_version: str

    :return: String representation of the next version
    :rtype: string
    """
    if not semver.VersionInfo.isvalid(current_version):
        click.echo(
            f"Current version {current_version} is not a valid semver2 version. Please amend it"
        )

    pre_version_prefix = pre_version_prefix or "alpha"
    parsed_current_version = semver.VersionInfo.parse(current_version)
    next_version = ""
    if parsed_current_version.build or part == "build":
        next_version = parsed_current_version.bump_build()
    elif parsed_current_version.prerelease or part == "prerelease":
        next_version = parsed_current_version.bump_prerelease("alpha")
    elif parsed_current_version.patch or part == "patch":
        next_version = parsed_current_version.next_version("patch")
    elif parsed_current_version.minor or part == "minor":
        next_version = parsed_current_version.next_version("minor")
    elif parsed_current_version.major or part == "major":
        next_version = parsed_current_version.next_version("major")

    return str(next_version)


def parse_pep440_version(version):
    """Determine whether the provided version is PEP440 compliant.

    :param version: String representation of a version.
    :type version: str
    """
    try:
        return Version(version)
    except InvalidVersion:
        return None


def bump_pep440_version(
    current_version,
    part=None,
    dev_version_prefix=None,
    post_version_prefix=None,
    pre_version_prefix=None,
):
    """Bump a PEP440 version string.

    :param current_version: current version to be bumped
    :param part: part of the PEP440 version to bump
        (one of: [major, minor, micro, dev, post, pre]).
    :type current_version: str
    :type part: str

    :return: String representation of the next version
    :rtype: string
    """

    def _bump_dev_post_pre(dev_post_pre_number):
        """Bump a dev/post/prerelease depending on its number/date based version."""
        try:
            dev_post_pre_string = str(dev_post_pre_number)
            default_date_format = "%Y%m%d"
            extended_date_format = default_date_format + "%H%M%S"

            today_ = datetime.datetime.today()
            next_prerelease_date = today_.strftime(default_date_format)
            prev_prerelease_date = datetime.datetime.strptime(
                dev_post_pre_string, default_date_format
            )
            if today_ < prev_prerelease_date:
                raise Exception(
                    "Current prerelease version is newer than today, please fix it."
                )
            if dev_post_pre_string == next_prerelease_date:
                next_prerelease_date = today_.strftime(extended_date_format)
            return next_prerelease_date
        except ValueError:
            return dev_post_pre_number + 1

    version = parse_pep440_version(current_version)
    if not version:
        click.echo(
            f"Current {current_version} is not a valid PEP440 version. Please amend it"
        )
        sys.exit(1)

    dev_post_pre_default_version_prefixes = {
        "dev": dev_version_prefix or "dev",
        "post": post_version_prefix or "post",
        "pre": pre_version_prefix or "a",
    }
    next_version = ""
    has_dev_post_pre = (
        ("dev" if version.dev else False)
        or ("post" if version.post else False)
        or version.pre[0]
    )
    if (part and part in dev_post_pre_default_version_prefixes.keys()) or (
        has_dev_post_pre and not part
    ):
        prefix_part = has_dev_post_pre or dev_post_pre_default_version_prefixes[part]
        version_part = version.dev or version.post or version.pre[1]
        version_part = _bump_dev_post_pre(version_part) if version_part else 1
        dev_post_pre_part = f"{prefix_part}{version_part}"
        next_version = Version(
            f"{version.major}.{version.minor}.{version.micro}{dev_post_pre_part}"
        )
    elif (part and part == "micro") or (isinstance(version.micro, int) and not part):
        next_version = Version(f"{version.major}.{version.minor}.{version.micro+1}")
    elif (part and part == "minor") or (isinstance(version.minor, int) and not part):
        next_version = Version(f"{version.major}.{version.minor+1}.0")
    elif (part and part == "major") or (isinstance(version.major, int) and not part):
        next_version = Version(f"{version.major+1}.0.0")

    return str(next_version)


def translate_pep440_to_semver2(pep440_version):
    """Translate a PEP440 compliant version to semver2."""
    prerelease_translation_dict = {
        "a": "alpha",
        "b": "beta",
        "dev": "dev",
        "post": "post",
        "rc": "rc",
    }
    parsed_pep440_version = parse_pep440_version(pep440_version)
    if not parsed_pep440_version:
        click.secho(f"Version {pep440_version} is not a correct PEP440 version.")
        sys.exit(1)
    dev_post_pre_semver2 = ""
    if parsed_pep440_version.is_devrelease:
        dev_post_pre_semver2 = f"dev.{parsed_pep440_version.dev}"
    elif parsed_pep440_version.is_postrelease:
        dev_post_pre_semver2 = f"post.{parsed_pep440_version.post}"
    elif parsed_pep440_version.is_prerelease:
        prefix = prerelease_translation_dict[parsed_pep440_version.pre[0]]
        number = parsed_pep440_version.pre[1]
        dev_post_pre_semver2 = f"{prefix}.{number}"

    semver2_version_string = f"{parsed_pep440_version.major}.{parsed_pep440_version.minor}.{parsed_pep440_version.micro}"
    if dev_post_pre_semver2:
        semver2_version_string += f"-{dev_post_pre_semver2}"
    if semver.VersionInfo.isvalid(semver2_version_string):
        return semver2_version_string
    else:
        click.secho(
            f"Something went wrong while translating {pep440_version} to semver2.",
            fg="red",
        )
        sys.exit(1)


def bump_component_version(component, current_version, next_version=None):
    """Bump to next component version."""
    try:
        version_files = get_component_version_files(component)
        files_to_update = []

        if version_files.get(HELM_VERSION_FILE):
            next_version = next_version or bump_semver2_version(current_version)
            files_to_update.append(version_files.get(HELM_VERSION_FILE))
        elif version_files.get(PYTHON_VERSION_FILE):
            next_version = next_version or bump_pep440_version(current_version)
            files_to_update.append(version_files.get(PYTHON_VERSION_FILE))
            if version_files.get(OPENAPI_VERSION_FILE):
                files_to_update.append(version_files.get(OPENAPI_VERSION_FILE))
        elif version_files.get(JAVASCRIPT_VERSION_FILE):
            next_version = next_version or bump_semver2_version(current_version)
            files_to_update.append(version_files.get(JAVASCRIPT_VERSION_FILE))

        for file_ in files_to_update:
            replace_string(
                file_=file_,
                find=current_version,
                replace=next_version,
                component=component,
            )

        return next_version, files_to_update
    except Exception as e:
        display_message(
            f"Something went wront while bumping the version: {e}", component
        )


def get_git_tag(component):
    """Return the current version of a component.

    :param component: standard component name
    :type component: str
    """
    cmd = "git describe --tags --abbrev=0"
    return run_command(cmd, component, return_output=True, display=True)


def validate_mode_option(ctx, param, value):
    """Validate mode option value."""
    if value not in CLUSTER_DEPLOYMENT_MODES:
        raise click.BadParameter(
            "Supported values are '{}'.".format("', '".join(CLUSTER_DEPLOYMENT_MODES))
        )
    return value


def get_docker_tag(component):
    """Return the current semver version of a component.

    :param component: standard component name
    :type component: str
    """
    tag = get_git_tag(component)

    if parse_pep440_version(tag):
        return translate_pep440_to_semver2(tag)
    elif semver.VersionInfo.isvalid(tag):
        return tag
    else:
        display_message(
            f"The component's latest tag ({tag}) is not a "
            "valid version (nor PEP440 nor semver2 compliant).",
            component,
        )
        sys.exit(1)
