# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2018 CERN.
#
# REANA is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# REANA is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# REANA; if not, write to the Free Software Foundation, Inc., 59 Temple Place,
# Suite 330, Boston, MA 02111-1307, USA.
#
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization or
# submit itself to any jurisdiction.

"""Helper scripts for REANA developers. Run `reana --help` for help."""

import os
import subprocess
import sys

import click

SRCDIR = os.environ.get('REANA_SRCDIR')

GITHUB_USER = os.environ.get('REANA_GITHUB_USER')

REPO_LIST_ALL = [
    'reana',
    'reana-client',
    'reana-cluster',
    'reana-commons',
    'reana-demo-alice-lego-train-test-run',
    'reana-demo-atlas-recast',
    'reana-demo-bsm-search',
    'reana-demo-helloworld',
    'reana-demo-lhcb-d2pimumu',
    'reana-demo-root6-roofit',
    'reana-demo-worldpopulation',
    'reana-env-aliphysics',
    'reana-env-jupyter',
    'reana-env-root6',
    'reana-job-controller',
    'reana-message-broker',
    'reana-server',
    'reana-ui',
    'reana-workflow-commons',
    'reana-workflow-controller',
    'reana-workflow-engine-cwl',
    'reana-workflow-engine-serial',
    'reana-workflow-engine-yadage',
    'reana-workflow-monitor',
    'reana.io',
]


REPO_LIST_CLUSTER = [
    'reana-commons',
    'reana-job-controller',
    'reana-message-broker',
    'reana-server',
    'reana-workflow-commons',
    'reana-workflow-controller',
    'reana-workflow-engine-cwl',
    'reana-workflow-engine-serial',
    'reana-workflow-engine-yadage',
    'reana-workflow-monitor',
]


@click.group()
def cli():  # noqa: D301
    """Run REANA development and integration commands.

    How to configure your environment:

    .. code-block:: console

        \b
        $ export REANA_SRCDIR=~/project/reana/src
        $ export REANA_GITHUB_USER=tiborsimko

    How to prepare your environment:

    .. code-block:: console

        \b
        $ # prepare directoru that will hold sources
        $ mkdir $REANA_SRCDIR && cd $REANA_SRCDIR
        $ # install reana developer helper script
        $ mkvirtualenv reana
        $ pip install git+git://github.com/reanahub/reana.git#egg=reana
        $ # run ssh-agent locally to simplify GitHub interaction
        $ eval "$(ssh-agent -s)"
        $ ssh-add ~/.ssh/id_rsa

    How to fork and clone all REANA repositories:

    .. code-block:: console

        \b
        $ reana git-fork -c ALL
        $ eval "$(reana git-fork -c ALL)"
        $ reana git-clone -c ALL

    How to compile and deploy latest ``master`` REANA cluster:

    .. code-block:: console

        \b
        $ minikube start --kubernetes-version="v1.9.4" --vm-driver=kvm2
        $ eval $(minikube docker-env)
        $ reana docker-build
        $ reana docker-images
        $ pip install reana-cluster
        $ reana-cluster -f reana-cluster-latest.yaml init
        $ # we now have REANA cluster running "master" versions of components

    How to test multiple component branches:

    .. code-block:: console

        \b
        $ reana git-checkout -b reana-job-controller 82
        $ reana git-checkout -b reana-workflow-controller 112
        $ reana git-status
        $ reana docker-build
        $ kubectl delete pod job-controller-65f87df9df-ht459
        $ kubectl delete pod workflow-controller-76d7b87887-2b64n
        $ kubectl get pods
        $ # we can now try to run an example

    How to release and push cluster component images:

    .. code-block:: console

        \b
        $ reana git-clean
        $ reana docker-build --no-cache
        $ # we should now run one more test with non-cached ``latest``
        $ # once it works, we can tag and push
        $ reana docker-build -t 0.3.0.dev20180625
        $ reana docker-push -t 0.3.0.dev20180625
        $ # we should now make PR for ``reana-cluster.yaml`` to use given tag
    """
    pass


def get_srcdir(component=''):
    """Return source code directory for the given component."""
    if not SRCDIR:
        click.echo('Please set environment variable REANA_SRCDIR'
                   ' to the directory that will contain'
                   ' REANA source code repositories.')
        click.echo('Example:'
                   ' $ export REANA_SRCDIR=~/private/project/reana/src')
        sys.exit(1)
    if component:
        return SRCDIR + os.sep + component
    else:
        return SRCDIR


def get_current_branch(srcdir):
    """Return current Git branch name checked out in the given directory."""
    os.chdir(srcdir)
    return subprocess.getoutput('git branch 2>/dev/null | '
                                'grep "^*" | colrm 1 2')


def select_components(components):
    """Return expanded and simplified component list based on input values.

    The input value is list. Each item may be containing (name, 'CLUSTER',
    'ALL') where name is a component name, 'CLUSTER' will expand to cover all
    REANA cluster components, 'ALL' will expand to include all REANA
    repositories.
    """
    output = set([])
    for component in components:
        if component == 'ALL':
            for repo in REPO_LIST_ALL:
                output.add(repo)
        elif component == 'CLUSTER':
            for repo in REPO_LIST_CLUSTER:
                output.add(repo)
        else:
            output.add(component)
    return list(output)


def is_component_dockerised(component):
    """Return whether the component contains Dockerfile.

    Useful to skip some docker-related commands for those components that are
    not concerned, such as building Docker images for `reana-cluster` that does
    not provide any.
    """
    if os.path.exists(get_srcdir(component) + os.sep + 'Dockerfile'):
        return True
    return False


def shorten_component_name(component):
    """Return shorter version of the component name.

    Example: reana-job-controller -> r-j-controller
    """
    short_name = ''
    parts = component.split('-')
    for part in parts[:-1]:
        short_name += part[0] + '-'
    short_name += parts[-1]
    return short_name


def run_command(cmd, component=''):
    """Run given command in the given component source directory.

    Exit in case of troubles.
    """
    click.secho('[{0}] {1}'.format(component, cmd), bold=True)
    if component:
        os.chdir(get_srcdir(component))
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as err:
        sys.exit(err.cmd)


def display_message(msg, component=''):
    """Display message in a similar style as run_command()."""
    click.secho('[{0}] {1}'.format(component, msg), bold=True)


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
              help='Which components? [name|CLUSTER|ALL]')
@click.option('--browser', '-b', default='firefox',
              help='Which browser to use? [firefox]')
@cli.command(name='git-fork')
def git_fork(component, browser):
    """Display commands to fork REANA source code repositories on GitHub.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    components = select_components(component)
    if components:
        click.echo('# Fork REANA repositories on GitHub using your browser.')
        click.echo('# Run the following eval and then complete the fork'
                   ' process in your browser.')
        click.echo('#')
        click.echo('# eval "$(reana git-fork -b {0} {1})"'.format(
            browser,
            "".join([" -c {0}".format(c) for c in component])))
    for component in components:
        cmd = '{0} https://github.com/reanahub/{1}/fork;'.format(browser,
                                                                 component)
        click.echo(cmd)
    click.echo('echo "Please continue the fork process in the opened'
               ' browser windows."')


@click.option('--user', '-u', default=GITHUB_USER,
              help='GitHub user name [{0}]'.format(GITHUB_USER))
@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER|ALL]')
@cli.command(name='git-clone')
def git_clone(user, component):
    """Clone REANA source repositories from GitHub.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]

    """
    if not GITHUB_USER:
        click.echo('Please set environment variable REANA_GITHUB_USER to your'
                   ' GitHub user name.')
        click.echo('Example: $ export REANA_GITHUB_USER=tiborsimko')
        sys.exit(1)
    components = select_components(component)
    for component in components:
        os.chdir(get_srcdir())
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
              help='Which components? [name|CLUSTER|ALL]')
@cli.command(name='git-status')
def git_status(component):
    """Report status of REANA source repositories.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    components = select_components(component)
    for component in components:
        branch = get_current_branch(get_srcdir(component))
        click.secho('- {0}'.format(component), nl=False, bold=True)
        if branch == 'master':
            click.secho(' @ {0}'.format(branch))
        else:
            click.secho(' @ {0}'.format(branch), fg='red')


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER|ALL]')
@cli.command(name='git-clean')
def git_clean(component):
    """Clean REANA source repository code tree.

    Removes pyc, eggs, _build and other leftover friends.
    Less aggressive then "git clean -x".

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    components = select_components(component)
    for component in components:
        for cmd in [
            'find . -name "*.pyc" -delete',
            'find . -type d -name "*.egg-info" -exec rm -rf {} \\;',
            'find . -type d -name ".eggs" -exec rm -rf {} \\;',
            'find . -type d -name __pycache__ -delete',
            'find docs -type d -name "_build" -exec rm -rf {} \\;'
        ]:
            run_command(cmd, component)


@click.option('--branch', '-b', nargs=2, multiple=True,
              help='Which PR? [number component]')
@click.option('--fetch', is_flag=True, default=False)
@cli.command(name='git-checkout')
def git_checkout(branch, fetch):
    """Check out local branch corresponding to a component pull request.

    For example, ``-b reana-job-controler 82`` will create a local branch
    called ``pr-82`` in the reana-job-component source code directory.

    The options can be repetitive to check out several pull requests in several
    repositories at the same time.

    The option ``--fetch`` fetches upstream first.
    """
    for cpr in branch:
        component, pull_request = cpr
        if fetch:
            cmd = 'git fetch upstream'
            run_command(cmd, component)
        cmd = 'git checkout -b pr-{0} upstream/pr/{0}'.format(pull_request)
        run_command(cmd, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER|ALL]')
@cli.command(name='git-fetch')
def git_fetch(component):
    """Fetch REANA upstream source code repositories without upgrade.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    for component in select_components(component):
        cmd = 'git fetch upstream'
        run_command(cmd, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER|ALL]')
@cli.command(name='git-upgrade')
def git_upgrade(component):
    """Upgrade REANA local source code repositories.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    for component in select_components(component):
        for cmd in ['git fetch upstream',
                    'git checkout master',
                    'git merge --ff-only upstream/master',
                    'git push origin master',
                    'git checkout -']:
            run_command(cmd, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER|ALL]')
@cli.command(name='git-diff')
def git_diff(component):
    """Diff checked-out REANA local source code repositories.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    for component in select_components(component):
        for cmd in ['git diff master', ]:
            run_command(cmd, component)


@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER]')
@cli.command(name='git-push')
def git_push(full, component):
    """Push REANA local repositories to GitHub origin.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    components = select_components(component)
    for component in components:
        for cmd in ['git push origin master']:
            run_command(cmd, component)


@click.option('--user', '-u', default='reanahub',
              help='DockerHub user name [reanahub]')
@click.option('--tag', '-t', default='latest',
              help='Image tag [latest]')
@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER]')
@click.option('--no-cache', is_flag=True)
@cli.command(name='docker-build')
def docker_build(user, tag, component, no_cache):
    """Build REANA component images.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    components = select_components(component)
    for component in components:
        if is_component_dockerised(component):
            if no_cache:
                cmd = 'docker build --no-cache -t {0}/{1}:{2} .'.format(
                    user, component, tag)
            else:
                cmd = 'docker build -t {0}/{1}:{2} .'.format(
                    user, component, tag)
            run_command(cmd, component)
        else:
            msg = 'Ignoring this component that does not contain' \
                  ' a Dockerfile.'
            display_message(msg, component)


@click.option('--user', '-u', default='reanahub',
              help='DockerHub user name [reanahub]')
@cli.command(name='docker-images')
def docker_images(user):
    """List REANA component images."""
    cmd = 'docker images | grep {0}'.format(user)
    run_command(cmd)


@click.option('--user', '-u', default='reanahub',
              help='DockerHub user name [reanahub]')
@click.option('--tag', '-t', default='latest',
              help='Image tag [latest]')
@click.option('--component', '-c', multiple=True, default=['CLUSTER'],
              help='Which components? [name|CLUSTER]')
@cli.command(name='docker-rmi')
def docker_rmi(user, tag, component):
    """Remove REANA component images.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
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
def docker_push(user, tag, component):
    """Push REANA component images to DockerHub.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
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
def docker_pull(user, tag, component):
    """Pull REANA component images from DockerHub.

    The option ``component`` can be repeated and the value can be a name such
    as 'reana-job-controller', or a special value 'CLUSTER' meaning all
    cluster-related components, or special value 'ALL' meaning all REANA
    repositories. [default=CLUSTER]
    """
    components = select_components(component)
    for component in components:
        if not is_component_dockerised(component):
            cmd = 'docker pull {0}/{1}:{2}'.format(user, component, tag)
            run_command(cmd, component)
        else:
            msg = 'Ignoring this component that does not contain' \
                  ' a Dockerfile.'
            display_message(msg, component)
