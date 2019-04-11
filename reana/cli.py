# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2018, 2019 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Helper scripts for REANA developers. Run `reana-dev --help` for help."""

import os
import subprocess
import sys

import click

REPO_LIST_DEMO = [
    'reana-demo-atlas-recast',
    'reana-demo-bsm-search',
    'reana-demo-helloworld',
    'reana-demo-root6-roofit',
    'reana-demo-worldpopulation',
]

REPO_LIST_ALL = [
    'reana',
    'reana-client',
    'reana-cluster',
    'reana-commons',
    'reana-db',
    'reana-demo-alice-lego-train-test-run',
    'reana-demo-cms-h4l',
    'reana-demo-lhcb-d2pimumu',
    'reana-env-aliphysics',
    'reana-env-jupyter',
    'reana-env-root6',
    'reana-job-controller',
    'pytest-reana',
    'reana-message-broker',
    'reana-server',
    'reana-ui',
    'reana-workflow-controller',
    'reana-workflow-engine-cwl',
    'reana-workflow-engine-serial',
    'reana-workflow-engine-yadage',
    'reana-workflow-monitor',
    'reana.io',
] + REPO_LIST_DEMO

REPO_LIST_CLIENT = [
    # shared utils
    'pytest-reana',
    'reana-commons',
    # client
    'reana-client',
]

REPO_LIST_CLUSTER = [
    # shared utils
    'pytest-reana',
    'reana-commons',
    'reana-db',
    # cluster components
    'reana-job-controller',
    'reana-message-broker',
    'reana-server',
    'reana-workflow-controller',
    'reana-workflow-engine-cwl',
    'reana-workflow-engine-serial',
    'reana-workflow-engine-yadage',
]

REPO_LIST_CLUSTER_CLI = [
    'reana-commons',
    'reana-cluster',
]

WORKFLOW_ENGINE_LIST_ALL = [
    'cwl',
    'serial',
    'yadage'
]

COMPONENT_PODS = {
    'reana-workflow-engine-cwl': 'cwl-default-worker',
    'reana-db': 'db',
    'reana-job-controller': 'job-controller',
    'reana-message-broker': 'message-broker',
    'reana-workflow-engine-serial': 'serial-default-worker',
    'reana-server': 'server',
    'reana-workflow-controller': 'workflow-controller',
    'reana-workflow-engine-yadage': 'yadage-default-worker',
}

EXAMPLE_OUTPUTS = {
    'reana-demo-helloworld': ('greetings.txt',),
    'reana-demo-bsm-search': ('prefit.pdf', 'postfit.pdf'),
    'reana-demo-alice-lego-train-test-run': ('plot.pdf',),
    'reana-demo-atlas-recast': ('pre.png', 'limit.png', 'limit_data.json'),
    '*': ('plot.png',)
}

COMPONENTS_USING_SHARED_MODULE_COMMONS = [
    'reana-job-controller',
    'reana-server',
    'reana-workflow-controller',
    'reana-workflow-engine-cwl',
    'reana-workflow-engine-serial',
    'reana-workflow-engine-yadage',
]

COMPONENTS_USING_SHARED_MODULE_DB = [
    'reana-job-controller',
    'reana-server',
    'reana-workflow-controller',
]


@click.group()
def cli():  # noqa: D301
    """Run REANA development and integration commands.

    How to prepare your environment:

    .. code-block:: console

        \b
        $ # prepare directory that will hold sources
        $ mkdir -p ~/project/reana/src
        $ cd ~/project/reana/src
        $ # create new virtual environment
        $ virtualenv ~/.virtualenvs/myreana
        $ source ~/.virtualenvs/myreana/bin/activate
        $ # install reana-dev developer helper script
        $ pip install git+git://github.com/reanahub/reana.git#egg=reana
        $ # run ssh-agent locally to simplify GitHub interaction
        $ eval "$(ssh-agent -s)"
        $ ssh-add ~/.ssh/id_rsa

    How to fork and clone all REANA repositories:

    .. code-block:: console

        \b
        $ reana-dev git-fork -c ALL
        $ eval "$(reana-dev git-fork -c ALL)"
        $ reana-dev git-clone -c ALL -u tiborsimko

    How to install latest ``master`` REANA cluster and client CLI scripts:

    .. code-block:: console

        \b
        $ reana-dev install-client
        $ reana-dev install-cluster

    How to compile and deploy latest ``master`` REANA cluster:

    .. code-block:: console

        \b
        $ # install minikube and set docker environment
        $ minikube start --vm-driver=kvm2 \\
                         --feature-gates="TTLAfterFinished=true"
        $ eval $(minikube docker-env)
        # deploy helm inside the Cluster
        $ helm init
        $ # option (a): cluster in production-like mode
        $ reana-dev docker-build -t latest
        $ reana-cluster -f reana-cluster-latest.yaml init --traefik
        $ # option (b): cluster in developer-like debug-friendly mode
        $ reana-dev docker-build -t latest -b DEBUG=true
        $ reana-cluster -f reana-cluster-dev.yaml init --traefik

    How to set up your shell environment variables:

    .. code-block:: console

        \b
        $ eval $(reana-dev setup-environment)

    How to run full REANA example using a given workflow engine:

    .. code-block:: console

        \b
        $ reana-dev run-example -c reana-demo-root6-roofit -w serial -s 10

    How to test one component pull request:

    .. code-block:: console

        \b
        $ cd reana-job-controller
        $ reana-dev git-checkout -b . 72 --fetch
        $ reana-dev docker-build -t latest -c .
        $ reana-dev kubectl-delete-pod -c .

    How to test multiple component branches:

    .. code-block:: console

        \b
        $ reana-dev git-checkout -b reana-job-controller 72
        $ reana-dev git-checkout -b reana-workflow-controller 98
        $ reana-dev git-status
        $ reana-dev docker-build -t latest
        $ reana-dev kubectl-delete-pod -c reana-job-controller
        $ reana-dev kubectl-delete-pod -c reana-workflow-controller

    How to test multiple component branches with commits to shared modules:

    .. code-block:: console

        \b
        $ reana-dev git-checkout -b reana-commons 72
        $ reana-dev git-checkout -b reana-db 73
        $ reana-dev git-checkout -b reana-workflow-controller 98
        $ reana-dev git-checkout -b reana-server 112
        $ reana-dev git-submodule --update
        $ reana-dev install-client
        $ reana-dev install-cluster
        $ reana-dev docker-build -t latest
        $ reana-cluster -f reana-cluster-latest.yaml down
        $ minikube ssh 'sudo rm -rf /var/reana'
        $ reana-cluster -f reana-cluster-latest.yaml init --traefik
        $ eval $(reana-dev setup-environment)
        $ reana-dev run-example -c r-d-helloworld -s 20
        $ reana-dev git-submodule --delete
        $ reana-dev git-status -s

    How to release and push cluster component images:

    .. code-block:: console

        \b
        $ reana-dev git-clean
        $ reana-dev docker-build -t latest --no-cache
        $ # we should now run one more test with non-cached ``latest``
        $ # once it works, we can tag and push
        $ reana-dev docker-build -t 0.3.0.dev20180625
        $ reana-dev docker-push -t 0.3.0.dev20180625
        $ # we should now make PR for ``reana-cluster.yaml`` to use given tag

    """
    pass


def shorten_component_name(component):
    """Return canonical short version of the component name.

    Example: reana-job-controller -> r-j-controller

    :param component: standard component name
    :type component: str

    :return: short component name
    :rtype: str
    """
    short_name = ''
    parts = component.split('-')
    for part in parts[:-1]:
        short_name += part[0] + '-'
    short_name += parts[-1]
    return short_name


def find_standard_component_name(short_component_name):
    """Return standard component name corresponding to the short name.

    Example: r-j-controller -> reana-job-controller

    :param short_component_name: short component name
    :type component: str

    :return: standard component name
    :rtype: str

    :raise: exception in case more than one is found
    """
    output = []
    for component in REPO_LIST_ALL:
        component_short_name = shorten_component_name(component)
        if component_short_name == short_component_name:
            output.append(component)
    if len(output) == 1:
        return output[0]
    raise Exception('Component name {0} cannot be uniquely mapped.'.format(
        'short_component_name'))


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
    if os.path.exists(srcdir + os.sep + 'reana' + os.sep + '.git' +
                      os.sep + 'config'):
        return srcdir
    # second, try from the parent of git toplevel:
    toplevel = subprocess.check_output(
        'git rev-parse --show-toplevel', shell=True).decode().rstrip('\r\n')
    srcdir = toplevel.rsplit(os.sep, 1)[0]
    if os.path.exists(srcdir + os.sep + 'reana' + os.sep + '.git' +
                      os.sep + 'config'):
        return srcdir
    # fail if not found
    raise Exception('Cannot find REANA component source directory '
                    'in {1}.'.format(srcdir))


def get_srcdir(component=''):
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
    return subprocess.check_output(
        'git branch 2>/dev/null | grep "^*" | colrm 1 2',
        shell=True).decode().rstrip('\r\n')


def get_current_commit(srcdir):
    """Return information about git commit checked out in the given directory.

    :param srcdir: source code directory
    :type srcdir: str

    :return: commit information composed of brief SHA1 and subject
    :rtype: str
    """
    os.chdir(srcdir)
    return subprocess.check_output(
        'git log --pretty=format:"%h %s" -n 1',
        shell=True).decode().rstrip('\r\n')


def select_components(components):
    """Return expanded and unified component name list based on input values.

    :param components: A list of component name that may consist of:
                          * (1) standard component names such as
                                'reana-job-controller';
                          * (2) short component name such as 'r-j-controller';
                          * (3) special value '.' indicating component of the
                                current working directory;
                          * (4) special value 'CLUSTER' that will expand to
                                cover all REANA cluster components;
                          * (5) special value 'CLIENT' that will expand to
                                cover all REANA client components;
                          * (6) special value 'ALL' that will expand to include
                                all REANA repositories.
                          * (7) special value 'DEMO' that will expand
                                to include all REANA repository examples.
    :type components: list

    :return: Unique standard component names.
    :rtype: list

    """
    short_component_names = [shorten_component_name(name)
                             for name in REPO_LIST_ALL]
    output = set([])
    for component in components:
        if component == 'ALL':
            for repo in REPO_LIST_ALL:
                output.add(repo)
        elif component == 'DEMO':
            for repo in REPO_LIST_DEMO:
                output.add(repo)
        elif component == 'CLIENT':
            for repo in REPO_LIST_CLIENT:
                output.add(repo)
        elif component == 'CLUSTER':
            for repo in REPO_LIST_CLUSTER:
                output.add(repo)
        elif component == '.':
            cwd = os.path.basename(os.getcwd())
            output.add(cwd)
        elif component in REPO_LIST_ALL:
            output.add(component)
        elif component in short_component_names:
            component_standard_name = find_standard_component_name(component)
            output.add(component_standard_name)
        else:
            display_message('Ignoring unknown component {0}.'.format(
                component))
    return list(output)


def select_workflow_engines(workflow_engines):
    """Return known workflow engine names that REANA supports.

    :param workflow_engines: A list of workflow engine names such as 'cwl'.
    :type components: list

    :return: Unique workflow engine names.
    :rtype: list

    """
    output = set([])
    for workflow_engine in workflow_engines:
        if workflow_engine in WORKFLOW_ENGINE_LIST_ALL:
            output.add(workflow_engine)
        else:
            display_message('Ignoring unknown workflow engine {0}.'.format(
                workflow_engine))
    return list(output)


def is_component_dockerised(component):
    """Return whether the component contains Dockerfile.

    Useful to skip some docker-related commands for those components that are
    not concerned, such as building Docker images for `reana-cluster` that does
    not provide any.

    :param component: standard component name
    :type component: str

    :return: True/False whether the component is dockerisable
    :rtype: bool
    """
    if os.path.exists(get_srcdir(component) + os.sep + 'Dockerfile'):
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
    if os.path.exists(get_srcdir(component) + os.sep + 'reana.yaml'):
        return True
    return False


def construct_workflow_name(example, workflow_engine):
    """Construct suitable workflow name for given REANA example.

    :param example: REANA example (e.g. reana-demo-root6-roofit)
    :param workflow_engine: workflow engine to use (cwl, serial, yadage)
    :type example: str
    :type workflow_engine: str
    """
    output = '{0}.{1}'.format(example.replace('reana-demo-', ''),
                              workflow_engine)
    return output


def run_command(cmd, component='', display=True, return_output=False):
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
    if display:
        click.secho('[{0}] {1}'.format(component, cmd), bold=True)
    if component:
        os.chdir(get_srcdir(component))
    try:
        if return_output:
            result = subprocess.check_output(cmd, shell=True)
            return result.decode().rstrip('\r\n')
        else:
            subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as err:
        if display:
            click.secho('[{0}] {1}'.format(component, err), bold=True)
        sys.exit(err.returncode)


def display_message(msg, component=''):
    """Display message in a similar style as run_command().

    :param msg: message to display
    :param component: standard component name
    :type msg: str
    :type component: str
    """
    click.secho('[{0}] {1}'.format(component, msg), bold=True)


def get_default_output_for_example(example):
    """Return default output file name for given example.

    :param example: name of the component
    :return: Tuple with output file name(s)
    """
    try:
        output = EXAMPLE_OUTPUTS[example]
    except KeyError:
        output = EXAMPLE_OUTPUTS['*']
    return output


def get_current_version(component, dirty=False):
    """Return the current version of a component.

    :param component: standard component name
    :param dirty: wheter the ``dirty`` flag is used when calling
        ``git describe``
    :type component: str
    :type dirty: bool
    """
    cmd = 'git describe'
    if dirty:
        cmd += ' --dirty'
    tag = run_command(cmd, component, return_output=True)
    # Remove starting `v` we use for Python/Git versioning
    return tag[1:]


@cli.command()
def version():
    """Return REANA version."""
    from reana.version import __version__
    click.echo(__version__)


@cli.command()
def help():
    """Display usage help tips and tricks."""
    click.echo(cli.__doc__)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@click.option('--browser', '-b', default='firefox',
              help='Which browser to use? [firefox]')
@cli.command(name='git-fork')
def git_fork(component, browser):  # noqa: D301
    """Display commands to fork REANA source code repositories on GitHub.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param browser: The web browser to use. [default=firefox]
    :type component: str
    :type browser: str
    """
    components = select_components(component)
    if components:
        click.echo('# Fork REANA repositories on GitHub using your browser.')
        click.echo('# Run the following eval and then complete the fork'
                   ' process in your browser.')
        click.echo('#')
        click.echo('# eval "$(reana-dev git-fork -b {0} {1})"'.format(
            browser,
            "".join([" -c {0}".format(c) for c in component])))
    for component in components:
        cmd = '{0} https://github.com/reanahub/{1}/fork;'.format(browser,
                                                                 component)
        click.echo(cmd)
    click.echo('echo "Please continue the fork process in the opened'
               ' browser windows."')


@click.option('--user', '-u', default='anonymous',
              help='GitHub user name [anonymous]')
@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@cli.command(name='git-clone')
def git_clone(user, component):  # noqa: D301
    """Clone REANA source repositories from GitHub.

    If the ``user`` argument is provided, the ``origin`` will be cloned from
    the user repository on GitHub and the ``upstream`` will be set to
    ``reanahub`` organisation. Useful for setting up personal REANA development
    environment,

    If the ``user`` argument is not provided, the cloning will be done in
    anonymous manner from ``reanahub`` organisation. Also, the clone will be
    shallow to save disk space and CPU time. Useful for CI purposes.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param user: The GitHub user name. [default=anonymous]
    :type component: str
    :type user: str

    """
    components = select_components(component)
    for component in components:
        os.chdir(get_srcdir())
        if os.path.exists('{0}/.git/config'.format(component)):
            msg = 'Component seems already cloned. Skipping.'
            display_message(msg, component)
        elif user == 'anonymous':
            cmd = 'git clone https://github.com/reanahub/{0} --depth 1'.format(
                component)
            run_command(cmd)
        else:
            cmd = 'git clone git@github.com:{0}/{1}'.format(user, component)
            run_command(cmd)
            for cmd in [
                'git remote add upstream'
                    ' "git@github.com:reanahub/{0}"'.format(component),
                'git config --add remote.upstream.fetch'
                    ' "+refs/pull/*/head:refs/remotes/upstream/pr/*"',
            ]:
                run_command(cmd, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@click.option('--short', '-s', is_flag=True, default=False,
              help="Show git status short format details?")
@cli.command(name='git-status')
def git_status(component, short):  # noqa: D301
    """Report status of REANA source repositories.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param verbose: Show git status details? [default=False]
    :type component: str
    """
    components = select_components(component)
    for component in components:
        branch = get_current_branch(get_srcdir(component))
        commit = get_current_commit(get_srcdir(component))
        click.secho('- {0}'.format(component), nl=False, bold=True)
        if branch == 'master':
            click.secho(' @ {0} {1}'.format(branch, commit))
        else:
            click.secho(' @ {0} {1}'.format(branch, commit), fg='red')
        if short:
            cmd = 'git status --short'
            run_command(cmd, component, display=False)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@cli.command(name='git-clean')
def git_clean(component):  # noqa: D301
    """Clean REANA source repository code tree.

    Removes all non-source-controlled files in the component source code
    repository. Useful to run before building container images.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :type component: str
    """
    components = select_components(component)
    for component in components:
        for cmd in [
            'git clean -d -ff -x',
        ]:
            run_command(cmd, component)


@click.option('--update', is_flag=True,
              help='Update shared modules everywhere?', default=False)
@click.option('--status', is_flag=True,
              help='Show status of shared modules everywhere.', default=False)
@click.option('--delete', is_flag=True,
              help='Delete shared modules everywhere?', default=False)
@cli.command(name='git-submodule')
def git_submodule(update=False, status=False, delete=False):  # noqa: D301
    """Sync REANA shared modules across all the repositories.

    Take currently checked-out reana-commons and reana-db modules and sync them
    across REANA components. Useful for building container images with
    not-yet-released shared modules.

    The option ``--update`` propagates the shared modules across the code base
    as necessary. Useful before running local docker image building.

    The option ``--status`` shows the information about shared modules.

    The option ``--delete`` removes the shared modules from everywhere. Useful
    for clean up after testing.
    """
    if update:
        for component in COMPONENTS_USING_SHARED_MODULE_COMMONS:
            for cmd in [
                'rsync -az ../reana-commons modules',
            ]:
                run_command(cmd, component)
        for component in COMPONENTS_USING_SHARED_MODULE_DB:
            for cmd in [
                'rsync -az ../reana-db modules',
            ]:
                run_command(cmd, component)
    elif delete:
        for component in set(COMPONENTS_USING_SHARED_MODULE_COMMONS +
                             COMPONENTS_USING_SHARED_MODULE_DB):
            for cmd in [
                'rm -rf ./modules/',
            ]:
                run_command(cmd, component)
    elif status:
        for component in COMPONENTS_USING_SHARED_MODULE_COMMONS:
            for cmd in [
                'git status -s',
            ]:
                run_command(cmd, component)
        for component in COMPONENTS_USING_SHARED_MODULE_DB:
            for cmd in [
                    'git status -s',
            ]:
                run_command(cmd, component)
    else:
        click.echo('Unknown action. Please specify `--update`, `--status` '
                   ' or `--delete`. Exiting.')
        sys.exit(1)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@cli.command(name='git-branch')
def git_branch(component):  # noqa: D301
    """Display information about locally checked-out branches.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :type component: str
    """
    for component in select_components(component):
        cmd = 'git branch'
        run_command(cmd, component)


@click.option('--branch', '-b', nargs=2, multiple=True,
              help='Which PR? [number component]')
@click.option('--fetch', is_flag=True, default=False)
@cli.command(name='git-checkout')
def git_checkout(branch, fetch):  # noqa: D301
    """Check out local branch corresponding to a component pull request.

    The ``-b`` option can be repetitive to check out several pull requests in
    several repositories at the same time.

    \b
    :param branch: The option ``branch`` can be repeated. The value consist of
                   two strings specifying the component name and the pull
                   request number. For example, ``-b reana-job-controler 72``
                   will create a local branch called ``pr-72`` in the
                   reana-job-component source code directory.
    :param fetch: Should we fetch latest upstream first? [default=False]
    :type component: str
    :type fetch: bool
    """
    for cpr in branch:
        component, pull_request = cpr
        component = select_components([component, ])[0]
        if component in REPO_LIST_ALL:
            if fetch:
                cmd = 'git fetch upstream'
                run_command(cmd, component)
            cmd = 'git checkout -b pr-{0} upstream/pr/{0}'.format(pull_request)
            run_command(cmd, component)
        else:
            msg = 'Ignoring unknown component.'
            display_message(msg, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@cli.command(name='git-fetch')
def git_fetch(component):  # noqa: D301
    """Fetch REANA upstream source code repositories without upgrade.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :type component: str
    """
    for component in select_components(component):
        cmd = 'git fetch upstream'
        run_command(cmd, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@cli.command(name='git-upgrade')
def git_upgrade(component):  # noqa: D301
    """Upgrade REANA local source code repositories and push to GitHub origin.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :type component: str
    """
    for component in select_components(component):
        for cmd in ['git fetch upstream',
                    'git checkout master',
                    'git merge --ff-only upstream/master',
                    'git push origin master',
                    'git checkout -']:
            run_command(cmd, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@click.option('--number', '-n', default=6,
              help='Number of commits to output [6]')
@click.option('--all', is_flag=True, default=False,
              help="Show all references?")
@cli.command(name='git-log')
def git_log(component, number, all):  # noqa: D301
    """Show commit logs in given component repositories.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param number: The number of commits to output. [6]
    :param all: Show all references? [6]
    :type component: str
    :type number: int
    :type all: bool
    """
    for component in select_components(component):
        cmd = 'git log -n {0} --graph --decorate' \
              ' --pretty=format:"%C(blue)%d%Creset' \
              ' %C(yellow)%h%Creset %s, %C(bold green)%an%Creset,' \
              ' %C(green)%cd%Creset" --date=relative'.format(number)
        if all:
            cmd += ' --all'
        msg = cmd[0:cmd.find('--pretty')] + '...'
        display_message(msg, component)
        run_command(cmd, component, display=False)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@cli.command(name='git-diff')
def git_diff(component):  # noqa: D301
    """Diff checked-out REANA local source code repositories.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :type component: str
    """
    for component in select_components(component):
        for cmd in ['git diff master', ]:
            run_command(cmd, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER]')
@cli.command(name='git-push')
def git_push(component):  # noqa: D301
    """Push REANA local repositories to GitHub origin.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :type component: str
    """
    components = select_components(component)
    for component in components:
        for cmd in ['git push origin master']:
            run_command(cmd, component)


@click.option('--user', '-u', default='reanahub',
              help='DockerHub user name [reanahub]')
@click.option('--tag', '-t', default='',
              help='Image tag. Autogenerated by `git describe --dirty` if not '
                   'specified.')
@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER]')
@click.option('--build-arg', '-b', default='', multiple=True,
              help='Any build arguments? (e.g. `-b DEBUG=true`)')
@click.option('--no-cache', is_flag=True)
@click.option('-q', '--quiet', is_flag=True,
              help='Suppress the build output and print image ID on success')
@cli.command(name='docker-build')
def docker_build(user, tag, component, build_arg,
                 no_cache, quiet):  # noqa: D301
    """Build REANA component images.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker tag to use. Automatically filled with the output of
        `git describe --dirty` if not provided.
    :param build_arg: Optional docker build argument. (e.g. DEBUG=true)
    :param no_cache: Flag instructing to avoid using cache. [default=False]
    :type component: str
    :type user: str
    :type tag: str
    :type build_arg: str
    :type no_cache: bool
    :type quiet bool
    """
    components = select_components(component)
    static_tag = tag
    for component in components:
        if is_component_dockerised(component):
            cmd = 'docker build'
            if not static_tag:
                tag = get_current_version(component, dirty=True)
            for arg in build_arg:
                cmd += ' --build-arg {0}'.format(arg)
            if no_cache:
                cmd += ' --no-cache'
            if quiet:
                cmd += ' --quiet'
            cmd += ' -t {0}/{1}:{2} .'.format(user, component, tag)
            run_command(cmd, component)
        else:
            msg = 'Ignoring this component that does not contain' \
                  ' a Dockerfile.'
            display_message(msg, component)


@click.option('--user', '-u', default='reanahub',
              help='DockerHub user name [reanahub]')
@cli.command(name='docker-images')
def docker_images(user):  # noqa: D301
    """List REANA component images.

    :param user: DockerHub user name. [default=reanahub]
    :type user: str
    """
    cmd = 'docker images | grep {0}'.format(user)
    run_command(cmd)


@click.option('--user', '-u', default='reanahub',
              help='DockerHub user name [reanahub]')
@click.option('--tag', '-t', default='latest',
              help='Image tag [latest]')
@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER]')
@cli.command(name='docker-rmi')
def docker_rmi(user, tag, component):  # noqa: D301
    """Remove REANA component images.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker tag to use. [default=latest]
    :type component: str
    :type user: str
    :type tag: str
    """
    components = select_components(component)
    for component in components:
        if is_component_dockerised(component):
            cmd = 'docker rmi {0}/{1}:{2}'.format(user, component, tag)
            run_command(cmd, component)
        else:
            msg = 'Ignoring this component that does not contain' \
                  ' a Dockerfile.'
            display_message(msg, component)


@click.option('--user', '-u', default='reanahub',
              help='DockerHub user name [reanahub]')
@click.option('--tag', '-t', default='latest',
              help='Image tag [latest]')
@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER]')
@cli.command(name='docker-push')
def docker_push(user, tag, component):  # noqa: D301
    """Push REANA component images to DockerHub.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker tag to use. [default=latest]
    :type component: str
    :type user: str
    :type tag: str
    """
    components = select_components(component)
    for component in components:
        if is_component_dockerised(component):
            cmd = 'docker push {0}/{1}:{2}'.format(user, component, tag)
            run_command(cmd, component)
        else:
            msg = 'Ignoring this component that does not contain' \
                  ' a Dockerfile.'
            display_message(msg, component)


@click.option('--user', '-u', default='reanahub',
              help='DockerHub user name [reanahub]')
@click.option('--tag', '-t', default='latest',
              help='Image tag [latest]')
@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER]')
@cli.command(name='docker-pull')
def docker_pull(user, tag, component):  # noqa: D301
    """Pull REANA component images from DockerHub.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker tag to use. [default=latest]
    :type component: str
    :type user: str
    :type tag: str
    """
    components = select_components(component)
    for component in components:
        if is_component_dockerised(component):
            cmd = 'docker pull {0}/{1}:{2}'.format(user, component, tag)
            run_command(cmd, component)
        else:
            msg = 'Ignoring this component that does not contain' \
                  ' a Dockerfile.'
            display_message(msg, component)


@cli.command(name='install-client')
def install_client():  # noqa: D301
    """Install latest REANA client Python package and its dependencies.

    \b
    :param upgrade: Should we upgrade? [default=True]
    :type fetch: bool
    """
    for component in REPO_LIST_CLIENT:
        for cmd in [
                'pip install . --upgrade',
        ]:
            run_command(cmd, component)


@cli.command(name='install-cluster')
def install_cluster():  # noqa: D301
    """Install latest REANA cluster Python package and its dependencies.

    \b
    :param upgrade: Should we upgrade if already installed? [default=True]
    :type fetch: bool
    """
    for component in REPO_LIST_CLUSTER_CLI:
        for cmd in [
                'pip install . --upgrade',
        ]:
            run_command(cmd, component)


@cli.command(name='setup-environment')
def setup_environment():  # noqa: D301
    """Display commands to set up shell environment for local cluster.

    Display commands how to set up REANA_SERVER_URL and REANA_ACCESS_TOKEN
    suitable for current local REANA cluster deployment. The output should be
    passed to eval.
    """
    print(subprocess.check_output(
        'reana-cluster env --include-admin-token',
        shell=True).decode().rstrip('\r\n'))


@click.option('--component', '-c', multiple=True,
              default=['reana-demo-root6-roofit'],
              help='Which examples to run? [reana-demo-root6-roofit]')
@click.option('--workflow_engine', '-w', multiple=True,
              default=['cwl', 'serial', 'yadage'],
              help='Which workflow engine to run? [cwl,serial,yadage]')
@click.option('--file', '-f', multiple=True,
              help='Expected output file?')
@click.option('--sleep', '-s', default=60,
              help='How much seconds to wait for results? [60]')
@click.option('--parameter', '-p', 'parameters', multiple=True,
              help='Additional input parameters to override '
                   'original ones from reana.yaml. '
                   'E.g. -p myparam1=myval1 -p myparam2=myval2.')
@click.option('-o', '--option', 'options',
              multiple=True,
              help='Additional operatioal options for the workflow execution. '
                   'E.g. CACHE=off.')
@cli.command(name='run-example')
def run_example(component, workflow_engine,
                file, sleep, parameters, options):  # noqa: D301
    """Run given REANA example with given workflow engine.

    \b
    :param component: The option ``component`` can be repeated. The value is
                      the repository name of the example.
                      [default=reana-demo-root6-roofit]
    :param workflow_engine: The option ``workflow_engine`` can be repeated. The
                     value is the workflow engine to use to run the example.
                     [default=cwl,serial,yadage]
    :param file: The option ``file`` can be repeated. The value is the
                   expected output file the workflow should produce.
                     [default=plot.png]
    :param sleep: How much seconds to sleep in order to wait for workflow to be
                  finished before checking the results? [default=60]
    :param parameters: Additional input parameters to override original ones
                       from reana.yaml.
                       E.g. -p myparam1=myval1 -p myparam2=myval2.
    :param options: Additional operatioal options for the workflow execution.
                    E.g. CACHE=off.

    :type component: str
    :type workflow_engine: str
    :type sleep: int

    """
    components = select_components(component)
    workflow_engines = select_workflow_engines(workflow_engine)
    reana_yaml = {
        'cwl': 'reana-cwl.yaml',
        'serial': 'reana.yaml',
        'yadage': 'reana-yadage.yaml',
    }
    for component in components:
        for workflow_engine in workflow_engines:
            workflow_name = construct_workflow_name(component, workflow_engine)
            # check whether example contains recipe for given engine:
            if not os.path.exists(get_srcdir(component) + os.sep +
                                  reana_yaml[workflow_engine]):
                msg = 'Skipping example with workflow engine {0}.'.format(
                    workflow_engine)
                display_message(msg, component)
                continue
            # create workflow:
            for cmd in [
                'reana-client create -f {0} -n {1}'.format(
                    reana_yaml[workflow_engine], workflow_name),
            ]:
                run_command(cmd, component)
            # upload various inputs
            for inputdir in ['inputs', 'code', 'data']:
                if os.path.exists(get_srcdir(component) + os.sep + inputdir):
                    cmd = 'reana-client upload ./{0} -w {1}'.format(
                        inputdir, workflow_name)
                    run_command(cmd, component)
            # run workflow
            input_parameters = ' '.join(
                ['-p ' + parameter for parameter in parameters])
            operational_options = ' '.join(
                ['-o ' + option for option in options])
            for cmd in [
                'reana-client start -w {0} {1} {2}'.format(
                    workflow_name, input_parameters, operational_options),
                'sleep {0}'.format(sleep),
                'reana-client status -w {0}'.format(
                    workflow_name),
                'reana-client ls -w {0}'.format(
                    workflow_name),
            ]:
                run_command(cmd, component)
            # verify output file presence:
            output = file or get_default_output_for_example(component)
            for output_file in output:
                cmd = 'reana-client ls -w {0} | grep -q {1}'.format(
                    workflow_name, output_file)
                run_command(cmd, component)
    # report status; everything was OK
    run_command('echo OK', component)


@click.option('--component', '-c', multiple=True, default=['ALL'],
              help='Which components? [shortname|name|.|CLUSTER|ALL]')
@cli.command(name='kubectl-delete-pod')
def kubectl_delete_pod(component):  # noqa: D301
    """Delete REANA component's pod.

    If option ``component`` is not used, all pods will be deleted.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-job-controller';
                         * (2) short component name such as 'r-j-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'ALL' that will expand to include
                               all REANA repositories.
    :type component: str

    """
    if "ALL" in component:
        cmd = 'kubectl delete --all pods --wait=false'
        run_command(cmd)
    else:
        components = select_components(component)
        for component in components:
            if component in COMPONENT_PODS:
                cmd = 'kubectl delete pod --wait=false -l app={0}'.format(
                    COMPONENT_PODS[component])
                run_command(cmd, component)
