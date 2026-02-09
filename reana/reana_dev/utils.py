# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2023, 2024, 2025, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev` related utils."""

import datetime
import functools
import importlib.util
import json
import os
import re
import subprocess
import sys
from concurrent import futures
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import click
import semver
import yaml
from packaging.version import InvalidVersion, Version

from reana.config import (
    CLUSTER_DEPLOYMENT_MODES,
    COMPONENTS_USING_SHARED_MODULE_COMMONS,
    COMPONENTS_USING_SHARED_MODULE_DB,
    DOCKER_VERSION_FILE,
    GIT_DEFAULT_BASE_BRANCH,
    HELM_VERSION_FILE,
    JAVASCRIPT_VERSION_FILE,
    OPENAPI_VERSION_FILE,
    PYTHON_DOCKER_IMAGE,
    PYTHON_REQUIREMENTS_FILE,
    PYTHON_VERSION_FILE,
    REPO_LIST_ALL,
    REPO_LIST_CLIENT,
    REPO_LIST_CLUSTER,
    REPO_LIST_CLUSTER_INFRASTRUCTURE,
    REPO_LIST_CLUSTER_RUNTIME_BATCH,
    REPO_LIST_DEMO_RUNNABLE,
    REPO_LIST_PYTHON_FIRST,
)


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


def find_component_directory_from_current_dir():
    """Find the component root directory by walking up until .git is found.

    Starting from the current directory, walk up the directory tree until
    a .git directory is found. This allows detection of the component name
    even when in nested subdirectories.

    :return: component root directory (the directory containing .git)
    :rtype: str

    :raise: exception in case .git directory is not found
    """
    current = os.getcwd()
    while current != os.path.dirname(current):  # Stop at filesystem root
        if os.path.exists(os.path.join(current, ".git")):
            return current
        current = os.path.dirname(current)

    raise Exception("Cannot find .git directory starting from {0}.".format(os.getcwd()))


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
    try:
        toplevel = (
            subprocess.check_output("git rev-parse --show-toplevel", shell=True)
            .decode()
            .rstrip("\r\n")
        )
        srcdir = toplevel.rsplit(os.sep, 1)[0]
        if os.path.exists(
            srcdir + os.sep + "reana" + os.sep + ".git" + os.sep + "config"
        ):
            return srcdir
    except subprocess.CalledProcessError:
        pass
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
            for repo in REPO_LIST_DEMO_RUNNABLE:
                output.add(repo)
        elif component == "CLIENT":
            for repo in REPO_LIST_CLIENT:
                output.add(repo)
        elif component == "CLUSTER":
            for repo in REPO_LIST_CLUSTER:
                output.add(repo)
        elif component == "CLUSTER-INFRASTRUCTURE":
            for repo in REPO_LIST_CLUSTER_INFRASTRUCTURE:
                output.add(repo)
        elif component == "CLUSTER-RUNTIMEBATCH":
            for repo in REPO_LIST_CLUSTER_RUNTIME_BATCH:
                output.add(repo)
        elif component == ".":
            # Find the git root directory to get the actual component name
            component_dir = find_component_directory_from_current_dir()
            component_name = os.path.basename(component_dir)
            output.add(component_name)
        elif component in REPO_LIST_ALL:
            output.add(component)
        elif component in short_component_names:
            component_standard_name = find_standard_component_name(component)
            output.add(component_standard_name)
        else:
            display_message("Ignoring unknown component {0}.".format(component))

    if exclude_components:
        output = exclude_components_from_selection(output, exclude_components)

    return sorted(output)


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


def run_command(
    cmd: str,
    component: str = "",
    display: bool = True,
    return_output: bool = False,
    directory: str = None,
    dry_run: bool = False,
    exit_on_error: bool = True,
) -> Optional[str]:
    """Run given command in the given component source directory.

    Exit in case of troubles.

    :param cmd: shell command to run
    :param component: standard component name
    :param display: should we display command to run?
    :param return_output: shall the output of the command be returned?
    :param directory: directory where to run the command
    :param dry_run: should we only show the command without executing it?
    :type cmd: str
    :type component: str
    :type display: bool
    :type return_output: bool
    :type directory: str
    :type dry_run: bool
    """
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if display:
        click.secho("[{0}] ".format(now), bold=True, nl=False, fg="green")
        click.secho("{0}: ".format(component), bold=True, nl=False, fg="yellow")
        click.secho("{0}".format(cmd), bold=True)
    if dry_run:
        return
    if component and directory:
        os.chdir(os.path.join(directory, component))
    elif component:
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
        if exit_on_error:
            sys.exit(err.returncode)
        else:
            raise


@dataclass
class ExecutionProgress:
    """Progress of the parallel execution of multiple tasks."""

    cancelled: int = 0
    done: int = 0
    failed: int = 0
    remaining: int = 0
    total: int = 0


def execute_parallel(
    fn_calls: Sequence[Tuple[Callable, Tuple]],
    processes: Optional[int] = None,
    progress_callback: Optional[Callable] = None,
    progress_interval: float = 10,
):
    """Execute multiple functions in parallel.

    :param fn_calls: List of function calls to be executed.
        Each element is a tuple containing the function and its arguments.
    :param processes: Number of function calls to be executed in parallel.
    :param progress_callback: Function used to track the progress of the execution.
        It should accept a single argument of type `ExecutionProgress`.
    :param progress_interval: Time interval in seconds between calls to `progress_callback`.
    """
    if processes == 1:
        for fn, args in fn_calls:
            fn(*args)
        return

    with futures.ProcessPoolExecutor(max_workers=processes) as executor:
        pending = list(reversed(fn_calls))  # Tasks waiting to be submitted
        submitted = []  # Tasks already submitted
        done = []  # Tasks finished (or failed)
        failed = []  # Tasks failed

        timeout = progress_interval if progress_callback is not None else None
        while submitted or (pending and not failed):
            # If there are empty slots and no task has failed yet, submit some new tasks
            while not failed and pending and len(submitted) < processes:
                fn, args = pending.pop()
                submitted.append(executor.submit(fn, *args))

            # Wait for one task to finish (or for the timeout)
            w = futures.wait(submitted, timeout, futures.FIRST_COMPLETED)

            # Update list of submitted/done/failed tasks
            submitted = list(w.not_done)
            done.extend(w.done)
            failed.extend(t for t in w.done if t.exception() is not None)

            if progress_callback:
                status = ExecutionProgress(
                    total=len(fn_calls),
                    done=len(done),
                    failed=len(failed),
                    remaining=(
                        len(submitted) + len(pending) if not failed else len(submitted)
                    ),
                    cancelled=0 if not failed else len(pending),
                )
                progress_callback(status)

        for task in failed:
            # task.result() is called to propagate exceptions
            task.result()


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


def fetch_latest_pypi_version(package):
    """Fetch latest released version of a package."""
    import requests

    pypi_rc_info = requests.get("https://pypi.python.org/pypi/{}/json".format(package))
    return sorted(pypi_rc_info.json()["releases"].keys(), key=Version)[-1]


def is_last_commit_tagged(package):
    """Check whether the last commit of the module points at a tag."""
    tag = run_command("git tag --points-at", package, return_output=True)
    return bool(tag)


def is_feature_branch(component, base=GIT_DEFAULT_BASE_BRANCH):
    """Check whether component current branch is different from base branch."""
    return get_current_branch(get_srcdir(component)) != base


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
        "reana-commons": COMPONENTS_USING_SHARED_MODULE_COMMONS
        + ["reana-client", "reana-db"],
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
        next_minor_version = f"{new_version_obj.major}.{new_version_obj.minor + 1}.0"
        if os.path.exists(get_srcdir(component) + os.sep + "setup.py"):
            replace_string(
                file_="setup.py",
                find='>=.*,<.*[^",]',
                replace=f">={new_version},<{next_minor_version}",
                line_selector_regex=f"{module}.*>=",
                component=component,
            )
        if os.path.exists(get_srcdir(component) + os.sep + "pyproject.toml"):
            replace_string(
                file_="pyproject.toml",
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


def upgrade_requirements(component: str) -> bool:
    """Update the Python requirements file using pip-compile."""
    requirements_path = os.path.join(get_srcdir(component), PYTHON_REQUIREMENTS_FILE)
    if not os.path.exists(requirements_path):
        display_message(f"File {PYTHON_REQUIREMENTS_FILE} not found.", component)
        return False

    pip_compile_cmd = None
    with open(requirements_path) as requirements_file:
        # find pip-compile command contained in requirements.txt
        for line in requirements_file:
            stripped_line = line.lstrip("#").strip()
            if stripped_line.startswith("pip-compile"):
                pip_compile_cmd = stripped_line
                break

    if not pip_compile_cmd:
        display_message(
            f"File {PYTHON_REQUIREMENTS_FILE} does not contain a valid pip-compile command.",
            component,
        )
        return False

    executable, *options = pip_compile_cmd.split()
    if "annotation-style" not in pip_compile_cmd:
        options = ["--annotation-style=line"] + options
    options.append("-U")
    pip_compile_cmd = " ".join([executable] + options)

    docker_cmd = (
        f"docker run --rm -it -v {get_srcdir(component)}:/code:z {PYTHON_DOCKER_IMAGE} "
        f"bash -c 'cd /code && pip install --upgrade pip-tools pip && pip install \"setuptools<81\" && {pip_compile_cmd}'"
    )
    run_command(docker_cmd, component)
    return True


def get_component_version_files(component, abs_path=False) -> Dict[str, str]:
    """Get a dictionary with all component's version files."""
    version_files = {}
    for file_ in [
        DOCKER_VERSION_FILE,
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


def get_current_component_version_from_source_files(
    component: str, version_file: Optional[str] = None
) -> str:
    """Get component's current version.

    :param component: standard component name
    :param version_file: version file type e.g HELM_VERSION_FILE, etc.
    :type component: str
    :type version_file: str

    :return: version in SemVer2 or PEP440 format
    :rtype: str
    """
    all_version_files = get_component_version_files(component, abs_path=True)

    if version_file:
        all_version_files = {version_file: all_version_files[version_file]}

    version = ""
    if (
        all_version_files.get(DOCKER_VERSION_FILE)
        and component not in REPO_LIST_PYTHON_FIRST
    ):
        with open(all_version_files.get(DOCKER_VERSION_FILE)) as f:
            for line in f.readlines():
                match = re.match(
                    r'LABEL org.opencontainers.image.version="(.*?)"', line
                )
                if match:
                    version = match.groups(1)[0]
                    break

    elif all_version_files.get(HELM_VERSION_FILE):
        with open(all_version_files.get(HELM_VERSION_FILE)) as f:
            chart_yaml = yaml.safe_load(f.read())
            version = chart_yaml["version"]

    elif all_version_files.get(PYTHON_VERSION_FILE):
        spec = importlib.util.spec_from_file_location(
            component, all_version_files.get(PYTHON_VERSION_FILE)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        version = module.__version__

    elif all_version_files.get(JAVASCRIPT_VERSION_FILE):
        with open(all_version_files.get(JAVASCRIPT_VERSION_FILE)) as f:
            package_json = json.loads(f.read())
            version = package_json["version"]

    elif all_version_files.get(OPENAPI_VERSION_FILE):
        with open(all_version_files.get(OPENAPI_VERSION_FILE)) as f:
            openapi_json = json.loads(f.read())
            version = openapi_json.get("info", {}).get("version")

    return version


def bump_semver2_version(current_version: str, part=None) -> str:
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


def parse_pep440_version(version) -> Optional[Version]:
    """Determine whether the provided version is PEP440 compliant.

    :param version: String representation of a version.
    :type version: str
    """
    try:
        return Version(version)
    except InvalidVersion:
        return None


def bump_pep440_version(
    current_version: str,
    part=None,
    dev_version_prefix=None,
    post_version_prefix=None,
    pre_version_prefix=None,
) -> str:
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
        or (version.pre[0] if version.pre else False)
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
        next_version = Version(f"{version.major}.{version.minor}.{version.micro + 1}")
    elif (part and part == "minor") or (isinstance(version.minor, int) and not part):
        next_version = Version(f"{version.major}.{version.minor + 1}.0")
    elif (part and part == "major") or (isinstance(version.major, int) and not part):
        next_version = Version(f"{version.major + 1}.0.0")

    return str(next_version)


def translate_pep440_to_semver2(pep440_version: str) -> str:
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
        raise Exception(f"Version {pep440_version} is not a correct PEP440 version.")

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


def bump_component_version(
    component: str, next_version: Optional[str] = None
) -> (str, List[str]):
    """Bump to next component version.

    If next_version is set, it will be used for the component.
    If not, version will be bumped automatically from the current one.

    :param component: standard component name
    :param next_version: new version
    :type component: str
    :type next_version: str

    :return: next_version and list of modified version files
    :rtype: str, List[str]
    """
    version_files = get_component_version_files(component)

    updated_files = []
    next_version_per_file_type = {}

    # bump all version files
    for file_type, file_path in version_files.items():
        if not file_path:
            continue

        current_version = get_current_component_version_from_source_files(
            component, version_file=file_type
        )

        if file_type in [
            DOCKER_VERSION_FILE,
            HELM_VERSION_FILE,
            JAVASCRIPT_VERSION_FILE,
        ]:
            new_version = (
                translate_pep440_to_semver2(next_version)
                if next_version
                else bump_semver2_version(current_version)
            )
        elif file_type in [PYTHON_VERSION_FILE, OPENAPI_VERSION_FILE]:
            new_version = (
                str(parse_pep440_version(next_version))
                if next_version
                else bump_pep440_version(current_version)
            )
        else:
            raise Exception(f"Cannot bump the following {file_type} file")

        replace_string(
            file_=file_path,
            find=current_version,
            replace=new_version,
            component=component,
        )
        updated_files.append(file_path)
        next_version_per_file_type[file_type] = new_version

        if file_type == DOCKER_VERSION_FILE:
            today = datetime.date.today().isoformat()
            replace_string(
                file_=file_path,
                find='LABEL org.opencontainers.image.created=".*"',
                replace=f'LABEL org.opencontainers.image.created="{today}"',
                component=component,
            )

    # depending on a component, return proper component version
    if (
        DOCKER_VERSION_FILE in next_version_per_file_type.keys()
        and component not in REPO_LIST_PYTHON_FIRST
    ):
        return next_version_per_file_type[DOCKER_VERSION_FILE], updated_files
    elif HELM_VERSION_FILE in next_version_per_file_type.keys():
        return next_version_per_file_type[HELM_VERSION_FILE], updated_files
    elif JAVASCRIPT_VERSION_FILE in next_version_per_file_type:
        return next_version_per_file_type[JAVASCRIPT_VERSION_FILE], updated_files
    else:
        return next_version_per_file_type[PYTHON_VERSION_FILE], updated_files


def get_git_tag(component):
    """Return the current version of a component.

    :param component: standard component name
    :type component: str
    """
    cmd = "git describe --tags --abbrev=0"
    return run_command(cmd, component, return_output=True, display=False)


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


def click_add_git_base_branch_option(func):
    """Add `--base` git base branch option to click commands."""

    @click.option(
        "--base",
        default=GIT_DEFAULT_BASE_BRANCH,
        help="Against which git base branch are we working? [{}]".format(
            GIT_DEFAULT_BASE_BRANCH
        ),
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def validate_directory(ctx, param, target_directory):
    """Validate if directory is valid for first time cloning."""
    target_directory = os.path.realpath(target_directory)

    if not os.path.isdir(target_directory):
        message = "[ERROR] Directory {0} does not exist. Exiting.".format(
            target_directory
        )
        click.echo(click.style(message, fg="red"), err=True)
        ctx.exit(1)

    if len(os.listdir(target_directory)) != 0:
        message = "[ERROR] Directory {0} is not empty. Cloning aborted.".format(
            target_directory
        )
        click.echo(click.style(message, fg="red"), err=True)
        ctx.exit(1)
    return target_directory


def get_current_pr_number(component):
    """Get the PR number of the current branch."""
    try:
        output = run_command(
            "gh pr view --json number",
            component=component,
            display=False,
            return_output=True,
            exit_on_error=False,
        )
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            # no PR associated to the branch
            return None
        raise
    res = json.loads(output)
    return res["number"]


def get_next_available_issue_pr_number(component):
    """Get the next available number for issues/PRs."""
    last_used = 0
    for type_ in ("pr", "issue"):
        res = json.loads(
            run_command(
                f"gh {type_} list --state all --limit 1 --json number",
                component=component,
                display=False,
                return_output=True,
            )
        )
        if res:
            last_used = max(last_used, res[0]["number"])

    return last_used + 1


def get_commit_pr_suffix(component):
    """Get the commit message suffix containing the expected PR number."""
    current_pr = get_current_pr_number(component)
    if current_pr:
        return f" (#{current_pr})"

    pr_number_suffix = ""
    try:
        pr_number = get_next_available_issue_pr_number(component)
        pr_number_suffix = f" (#{pr_number})"
    except Exception as e:
        display_message(f"Could not find next available PR number: {e}", component)
    return pr_number_suffix


def print_colima_start_help():
    """Print information how to start Colima with K3s."""
    print("""
Please start a Colima VM with Kubernetes option and with appropriate
architecture, disk, memory, etc options for your laptop.

Here is an example for macOS:

$ colima start \\
    --activate \\
    --arch aarch64 \\
    --cpu 8 \\
    --disk 300 \\
    --kubernetes \\
    --memory 18 \\
    --mount-type virtiofs \\
    --profile default \\
    --verbose \\
    --vm-type vz \\
    --vz-rosetta

This script does not do this automatically. Exiting.""")
