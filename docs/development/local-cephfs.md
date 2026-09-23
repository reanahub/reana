# Local Rook CephFS development

The local CephFS backend is intended for destructive REANA development and
validation on Kind. It is not supported with Colima/K3s. The lifecycle creates
loop-backed OSDs inside the Kind control-plane node and destroys all local Ceph
data during `cluster-delete`.

## Create and deploy

Create the Kind cluster and its Rook/CephFS storage substrate:

```console
$ reana-dev cluster-create --shared-storage-backend cephfs
```

The command labels the control-plane node as the Ceph and infrastructure data
owner, allocates loop devices, installs Rook in its documented order, waits for
CephFS readiness, and verifies an RWX mount with a write/read probe.

Deploy REANA using the local storage profile:

```console
$ reana-dev cluster-deploy \
    --shared-storage-backend cephfs \
    --admin-email admin@example.org \
    --admin-password admin
```

`cluster-deploy` reruns the RWX probe before invoking Helm. In development
modes, `values-dev.yaml` is the default base. Explicit `--values` files replace
that implicit base, and the selected CephFS overlay is always applied last. In
`releasehelm` mode only the chart defaults, explicit values, and the CephFS
overlay are used; the complete development profile is not restored.

The deploy preflight also validates the recorded loop mappings. If a Docker VM
restart detached them while preserving their backing images, it reattaches the
images, refreshes lifecycle state, and reconciles the CephCluster device list
before checking storage health.

For multi-node Kind clusters, CephFS provides the shared workflow workspace so
no `/var/reana` host mount is required. PostgreSQL and RabbitMQ keep their
separate hostPath data on the labelled control-plane node; the chart creates
that directory with `DirectoryOrCreate`.

## Validate user-visible storage

After deploying REANA and configuring `reana-client`, verify persistence,
non-root execution, fsGroup handling, and Jupyter visibility:

```console
$ scripts/check-shared-storage-fsgroup-smoke.sh --delete-on-success
$ scripts/check-jupyter-session-nonroot-smoke.sh --delete-on-success
```

The fsGroup probe inspects the live batch and user-job pods before checking
cross-run persistence. The Jupyter probe opens a real interactive session and
checks the actual workflow workspace and REANA user-secret mounts.

## Undeploy

Removing only the REANA release, while keeping the Rook substrate, also resets
the data roots owned by the deployment:

```console
$ reana-dev cluster-undeploy
```

The CephFS profile keeps PostgreSQL and RabbitMQ on their own
`/var/reana-infrastructure` hostPath, so undeploy clears both that root and the
shared `/var/reana` root. Without this, a redeploy would reuse the previous
database and report a broken admin-user setup as successful. The backend is
detected from lifecycle state; pass `--shared-storage-backend` to override it.

## Delete

Delete the cluster without repeating the backend option:

```console
$ reana-dev cluster-delete
```

The selected backend, Kind node/container identity, node image, backing files,
and loop mappings are recorded in
`${XDG_STATE_HOME:-$HOME/.local/state}/reana-dev/kind-cephfs.state`. Set
`REANA_DEV_STATE_DIR` to place this record elsewhere. The record lets
`cluster-delete` discover CephFS and recover owned loop mappings when the Kind
node container is already unavailable.

Deletion first removes the REANA Helm release, then follows the Rook teardown
order, cleans owned loop devices, deletes Kind, and finally handles requested
host-mount cleanup. Every phase is attempted even if an earlier phase fails; the
command reports all failed phases at the end. Use `--namespace` and
`--instance-name` when the REANA release does not use their defaults.
