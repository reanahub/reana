# Publishing new versions of REANA

## 1. Clone the repository

```console
$ git clone https://github.com/reanahub/reana.git
$ cd reana/
```

## 2. Upgrade chart version

Upgrade the version in the `helm/reana/Chart.yaml` file:

```yaml
# Chart version.
version: 0.1.0
```

And create the new package:

```console
$ helm package helm/reana/* -d .deploy
```

:note: the `.deploy` folder will be created but not commited since it is part of the `.gitignore` file.

## 3. Upload the release to GitHub

The next step is to upload the release to GitHub, for that we will use the [chart-releaser](https://github.com/helm/chart-releaser) tool. You can use it via docker, by mounting the `reana` repository folder:

``` console
$ docker run -v /absolute/path/to/reana:/tmp/reana/ -it quay.io/helmpack/chart-releaser:v0.2.3 /bin/sh
```

Before proceeding we need to generate a new personal token with access to the repository (*repo* group). You can do so in [here](https://github.com/settings/tokens).

In the following examples, `cr` is the alias name of the command line tool `chart-releaser`.

```console
$ read -s GITHUB_TOKEN
$ cr upload -o reanahub -r reana -p .deploy -t  $GITHUB_TOKEN
```

:warning: the `.deploy` folder should only contain new releases, otherwise chart-releaser will try to push them all and will fail due to "already existing" versions.

And finally we should update the chart `index.yaml` file, that will be served to `helm`:

```console
$ cr index -i ./index.yaml -p .deploy/ -o reanahub -c https://github.com/reanahub/reana -r reana --token $GITHUB_TOKEN
$ git add index.yaml
$ git commit -m 'release: v0.1.0'
```

⚠️ The index.yaml file should be appended with the new versions, however chart-releaser overwrites it. There is an open issue to remedy that situation.