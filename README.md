[![image](docs/logo-reana.png)](http://docs.reana.io)

# REANA - Reusable Analyses

[![image](https://github.com/reanahub/reana/workflows/CI/badge.svg)](https://github.com/reanahub/reana/actions)
[![image](https://readthedocs.org/projects/reana/badge/?version=latest)](https://reana.readthedocs.io/en/latest/?badge=latest)
[![image](https://codecov.io/gh/reanahub/reana/branch/master/graph/badge.svg)](https://codecov.io/gh/reanahub/reana)
[![image](https://img.shields.io/badge/discourse-forum-blue.svg)](https://forum.reana.io)
[![image](https://img.shields.io/github/license/reanahub/reana.svg)](https://github.com/reanahub/reana/blob/master/LICENSE)
[![image](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## About

[REANA](http://www.reana.io) is a reusable and reproducible research data analysis
platform. It helps researchers to structure their input data, analysis code,
containerised environments and computational workflows so that the analysis can be
instantiated and run on remote compute clouds.

REANA was born to target the use case of particle physics analyses, but is applicable to
any scientific discipline. The system paves the way towards reusing and reinterpreting
preserved data analyses even several years after the original publication.

## Features

- structure research data analysis in reusable manner
- instantiate computational workflows on remote clouds
- rerun analyses with modified input data, parameters or code
- support for several compute clouds (Kubernetes/OpenStack)
- support for several workflow specifications (CWL, Serial, Yadage, Snakemake)
- support for several shared storage systems (Ceph)
- support for several container technologies (Docker)

## Getting started

You can
[install REANA locally](https://docs.reana.io/administration/deployment/deploying-locally/),
[deploy it at scale on premises](https://docs.reana.io/administration/deployment/deploying-at-scale/)
(in about 10 minutes) or use <https://reana.cern.ch>. Once the system is ready, you can
follow the guide to run
[your first example](https://docs.reana.io/getting-started/first-example/). For more in
depth information visit the [official REANA documentation](https://docs.reana.io/).

## Community

- Discuss [on Forum](https://forum.reana.io/)
- Chat on [Mattermost](https://mattermost.web.cern.ch/it-dep/channels/reana) or
  [Gitter](https://gitter.im/reanahub/reana)
- Follow us [on Twitter](https://twitter.com/reanahub)

## Useful links

- [REANA home page](http://www.reana.io/)
- [REANA documentation](http://docs.reana.io/)
- [REANA on DockerHub](https://hub.docker.com/u/reanahub/)
