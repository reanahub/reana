#!/usr/bin/env python3
"""End-to-end smoke test for local REANA OIDC authentication and workflows.

The test is intentionally aimed at the bundled development Keycloak and a
disposable local cluster. It creates two temporary identities, drives the real
browser BFF login flow, runs the Hello World workflow through reana-client,
checks recent auth hardening, and removes the identities and workflow again.
"""

import argparse
import html.parser
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urljoin

import requests
import urllib3

ROOT = Path(__file__).resolve().parents[2]
TERMINAL_WORKFLOW_STATES = {"finished", "failed", "stopped", "deleted"}


class LoginFormParser(html.parser.HTMLParser):
    """Extract the Keycloak password form action."""

    def __init__(self):
        super().__init__()
        self.action = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.action = values.get("action")


class E2E:
    """Stateful runner with cleanup for disposable cluster resources."""

    def __init__(self, args):
        self.args = args
        self.client_path = args.reana_client
        self.demo_dir = args.demo_dir
        self.server_url = args.server_url.rstrip("/")
        self.keycloak_deployment = f"deployment/{args.release}-keycloak"
        self.server_deployment = f"deployment/{args.release}-server"
        suffix = secrets.token_hex(4)
        self.primary_email = f"reana-e2e-primary-{suffix}@example.org"
        self.denied_email = f"reana-e2e-denied-{suffix}@example.org"
        self.password = secrets.token_urlsafe(18)
        self.workflow = None
        self.workflow_uuid = None
        self.access_token = None
        self.user_ids = []
        self.runtime_namespace = args.namespace
        self.realm = None
        self.required_role = None

    def log(self, message):
        print(f"\n==> {message}", flush=True)

    def run(self, command, *, cwd=None, env=None, check=True, sensitive=False):
        if not sensitive:
            print("  $ " + " ".join(map(str, command)), flush=True)
        result = subprocess.run(
            list(map(str, command)),
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
        )
        if check and result.returncode:
            # A sensitive command's argument vector (e.g. `kcadm
            # set-password --new-password <secret>`) must stay out of the
            # failure message too, not just the pre-execution echo above --
            # a caller passing sensitive=True is asking for the whole
            # command to be redacted, not merely its happy-path logging.
            command_description = (
                "<redacted sensitive command>"
                if sensitive
                else " ".join(map(str, command))
            )
            raise RuntimeError(
                f"Command failed ({result.returncode}): {command_description}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def kubectl(self, *args, check=True, sensitive=False):
        return self.run(
            ["kubectl", "-n", self.args.namespace, *args],
            check=check,
            sensitive=sensitive,
        )

    def server_admin(self, *args, check=True):
        return self.kubectl(
            "exec",
            self.server_deployment,
            "-c",
            "rest-api",
            "--",
            "flask",
            "reana-admin",
            *args,
            check=check,
        )

    def kcadm(self, *args, check=True, sensitive=False):
        return self.kubectl(
            "exec",
            self.keycloak_deployment,
            "--",
            "/opt/keycloak/bin/kcadm.sh",
            *args,
            check=check,
            sensitive=sensitive,
        )

    def configure_kcadm(self):
        """Authenticate kcadm using credentials already in the target pod."""
        relative_path = self.pod_env(
            self.keycloak_deployment, "KC_HTTP_RELATIVE_PATH"
        ).rstrip("/")
        command = (
            'KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" "$1" config '
            'credentials --server "$2" --realm master --user '
            '"$KC_BOOTSTRAP_ADMIN_USERNAME"'
        )
        self.kubectl(
            "exec",
            self.keycloak_deployment,
            "--",
            "sh",
            "-c",
            command,
            "_",
            "/opt/keycloak/bin/kcadm.sh",
            f"http://localhost:8080{relative_path}",
            sensitive=True,
        )

    def pod_env(self, deployment, name, container=None):
        command = ["exec", deployment]
        if container:
            command += ["-c", container]
        command += ["--", "printenv", name]
        return self.kubectl(*command).stdout.strip()

    def create_keycloak_user(self, email, with_role):
        result = self.kcadm(
            "create",
            "users",
            "-r",
            self.realm,
            "-i",
            "-s",
            f"username={email}",
            "-s",
            f"email={email}",
            "-s",
            "enabled=true",
            "-s",
            "emailVerified=true",
            "-s",
            "firstName=REANA",
            "-s",
            "lastName=E2E",
        )
        user_id = result.stdout.strip()
        if not user_id:
            raise RuntimeError(f"Keycloak did not return an id for {email}")
        self.user_ids.append(user_id)
        self.kcadm(
            "set-password",
            "-r",
            self.realm,
            "--userid",
            user_id,
            "--new-password",
            self.password,
            sensitive=True,
        )
        if with_role:
            self.add_role(user_id)
        return user_id

    def add_role(self, user_id):
        self.kcadm(
            "add-roles",
            "-r",
            self.realm,
            "--uid",
            user_id,
            "--rolename",
            self.required_role,
            "--rolename",
            "offline_access",
        )

    def remove_role(self, user_id):
        self.kcadm(
            "remove-roles",
            "-r",
            self.realm,
            "--uid",
            user_id,
            "--rolename",
            self.required_role,
        )

    def browser_login(self, email):
        """Drive REANA BFF -> Keycloak -> REANA callback with real redirects."""
        session = requests.Session()
        response = session.get(
            f"{self.server_url}/api/login",
            params={"next": "/"},
            verify=False,
            timeout=30,
        )
        response.raise_for_status()
        parser = LoginFormParser()
        parser.feed(response.text)
        if not parser.action:
            raise RuntimeError(
                f"Could not find Keycloak login form at {response.url}: "
                f"{response.text[:500]}"
            )
        response = session.post(
            urljoin(response.url, parser.action),
            data={
                "username": email,
                "password": self.password,
                "credentialId": "",
            },
            verify=False,
            timeout=30,
        )
        response.raise_for_status()
        token = next(
            (cookie.value for cookie in session.cookies if cookie.name == "reana_at"),
            None,
        )
        if not token:
            raise RuntimeError(
                f"BFF login did not set reana_at; final URL was {response.url}"
            )
        return session, token

    def api(self, path, *, session=None, token=None, expected=200):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = (session or requests).get(
            f"{self.server_url}{path}",
            headers=headers,
            verify=False,
            timeout=30,
        )
        if response.status_code != expected:
            raise RuntimeError(
                f"GET {path}: expected {expected}, got {response.status_code}: "
                f"{response.text[:1000]}"
            )
        return response

    def client(self, *args, check=True, cwd=None):
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": os.pathsep.join(
                    [str(ROOT / "reana-client"), str(ROOT / "reana-commons")]
                ),
                "REANA_SERVER_URL": self.server_url,
                "REANA_ACCESS_TOKEN": self.access_token,
                "REANA_INSECURE": "true",
            }
        )
        return self.run(
            [self.client_path, *args],
            cwd=cwd or self.demo_dir,
            env=env,
            check=check,
        )

    def operational_script(self, script_name, *args):
        """Run an authenticated operational probe with the current OIDC token."""
        env = os.environ.copy()
        env.update(
            {
                "REANA_SERVER_URL": self.server_url,
                "REANA_ACCESS_TOKEN": self.access_token,
            }
        )
        return self.run([ROOT / "reana" / "scripts" / script_name, *args], env=env)

    @staticmethod
    def parse_status(output):
        payload = json.loads(output)
        if not payload:
            raise RuntimeError("Empty workflow status response")
        return payload[0]

    def wait_for_workflow(self, wanted=None, timeout=600):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.client("status", "-w", self.workflow, "--json")
            status = self.parse_status(result.stdout)["status"]
            print(f"  workflow status: {status}", flush=True)
            if wanted and status == wanted:
                return status
            if status in TERMINAL_WORKFLOW_STATES:
                return status
            time.sleep(3)
        raise RuntimeError(f"Workflow did not reach a terminal state in {timeout}s")

    def newest_run_batch_pod(self, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.run(
                [
                    "kubectl",
                    "-n",
                    self.runtime_namespace,
                    "get",
                    "pods",
                    "-l",
                    f"reana-run-batch-workflow-uuid={self.workflow_uuid}",
                    "-o",
                    "json",
                ]
            )
            pods = json.loads(result.stdout).get("items", [])
            active = [
                pod
                for pod in pods
                if pod.get("status", {}).get("phase") == "Running"
                and pod.get("status", {}).get("podIP")
                and any(
                    status.get("name") == "job-controller"
                    and status.get("state", {}).get("running")
                    for status in pod.get("status", {}).get("containerStatuses", [])
                )
            ]
            if active:
                return max(
                    active,
                    key=lambda pod: pod["metadata"].get("creationTimestamp", ""),
                )
            time.sleep(2)
        raise RuntimeError("No active run-batch pod appeared")

    def assert_sidecar_is_not_cross_pod_reachable(self):
        pod = self.newest_run_batch_pod()
        pod_ip = pod.get("status", {}).get("podIP")
        if not pod_ip:
            raise RuntimeError("Run-batch pod has no pod IP")
        probe = (
            "import socket,sys; s=socket.socket(); s.settimeout(2); "
            "\ntry: s.connect((sys.argv[1],5000))"
            "\nexcept OSError: sys.exit(0)"
            "\nelse: s.close(); sys.exit(1)"
        )
        result = self.kubectl(
            "exec",
            self.server_deployment,
            "-c",
            "rest-api",
            "--",
            "python3",
            "-c",
            probe,
            pod_ip,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                "Job-controller port 5000 was reachable from another pod; "
                "the listener is not effectively loopback-only."
            )

    def assert_user_exists(self, email, expected):
        result = self.server_admin("user-list", "--email", email, "--json")
        users = json.loads(result.stdout or "[]")
        found = any(user.get("email") == email for user in users)
        if found != expected:
            raise RuntimeError(
                f"Expected REANA user {email} existence={expected}, got {found}"
            )

    def run_all(self):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.log("Checking cluster and public API basics")
        self.kubectl(
            "wait", "--for=condition=Available", "deployment", "--all", "--timeout=10m"
        )
        self.api("/api/ping")
        self.api("/api/you", expected=401)
        metadata = self.api("/api/.well-known/openid-configuration").json()
        for field in ("issuer", "authorization_endpoint", "token_endpoint"):
            if not metadata.get(field):
                raise RuntimeError(f"OIDC relay omitted {field}")

        self.log("Creating disposable Keycloak identities")
        self.configure_kcadm()
        self.realm = self.pod_env(self.keycloak_deployment, "REANA_KEYCLOAK_REALM")
        self.required_role = self.pod_env(
            self.keycloak_deployment, "REANA_KEYCLOAK_REQUIRED_ROLE"
        )
        self.runtime_namespace = self.pod_env(
            self.server_deployment,
            "REANA_RUNTIME_KUBERNETES_NAMESPACE",
            container="rest-api",
        )
        primary_id = self.create_keycloak_user(self.primary_email, with_role=True)
        denied_id = self.create_keycloak_user(self.denied_email, with_role=False)

        self.log("Checking role-first provisioning and normal BFF login")
        denied_session, _ = self.browser_login(self.denied_email)
        denied = self.api("/api/you", session=denied_session, expected=403).json()
        if denied.get("code") != "access_not_granted":
            raise RuntimeError(f"Unexpected denied-user response: {denied}")
        self.assert_user_exists(self.denied_email, expected=False)
        self.add_role(denied_id)
        allowed_session, _ = self.browser_login(self.denied_email)
        self.api("/api/you", session=allowed_session)
        self.assert_user_exists(self.denied_email, expected=True)

        primary_session, self.access_token = self.browser_login(self.primary_email)
        identity = self.api("/api/you", session=primary_session).json()
        if identity.get("email") != self.primary_email:
            raise RuntimeError(f"BFF identity mismatch: {identity}")
        self.api("/api/info", session=primary_session)

        self.log("Checking webhook authorization status contract")
        webhook = self.api("/api/gitlab/webhook-token", session=primary_session).json()
        required_fields = {
            "configured",
            "expired",
            "expires_at",
            "max_lifetime_seconds",
        }
        if not required_fields.issubset(webhook):
            raise RuntimeError(f"Incomplete webhook status: {webhook}")

        self.log("Checking bearer-only operational validation scripts")
        self.operational_script(
            "test-spec-validation-storage.sh", self.args.namespace, self.args.release
        )
        self.operational_script(
            "test-spec-validator-network-policy.sh",
            self.args.namespace,
            self.args.release,
            "true",
        )

        self.log("Creating, uploading, and starting a real workflow")
        workflow_base = f"auth-e2e-{int(time.time())}"
        created = self.client("create", "-w", workflow_base)
        self.workflow = created.stdout.strip().splitlines()[-1]
        if not re.fullmatch(rf"{re.escape(workflow_base)}\.\d+", self.workflow):
            raise RuntimeError(f"Could not parse workflow name: {created.stdout}")
        workflow_status = self.parse_status(
            self.client("status", "-w", self.workflow, "--json", "--verbose").stdout
        )
        self.workflow_uuid = workflow_status.get("id")
        if not self.workflow_uuid:
            raise RuntimeError(f"Workflow status omitted its UUID: {workflow_status}")
        self.client("upload", "-w", self.workflow)
        self.client("start", "-w", self.workflow, "-p", "sleeptime=1")

        self.log("Checking that job-controller is unreachable from another pod")
        self.assert_sidecar_is_not_cross_pod_reachable()

        self.log("Waiting for workflow output")
        status = self.wait_for_workflow()
        if status != "finished":
            logs = self.client("logs", "-w", self.workflow, check=False).stdout
            raise RuntimeError(f"Workflow ended as {status}. Logs:\n{logs}")
        with tempfile.TemporaryDirectory(prefix="reana-auth-e2e-") as output_dir:
            self.client(
                "download",
                "-w",
                self.workflow,
                "-o",
                output_dir,
                "results/greetings.txt",
            )
            greetings = Path(output_dir, "results", "greetings.txt").read_text()
            if greetings != "Hello Jane Doe!\nHello Joe Bloggs!\n":
                raise RuntimeError(f"Unexpected workflow output: {greetings!r}")

        self.log("Checking reserved interactive-session secret failure is controlled")
        self.client("secrets-add", "--env", "NOTEBOOK_ARGS=attacker-controlled")
        opened = self.client("open", "-w", self.workflow, "jupyter", check=False)
        combined = opened.stdout + opened.stderr
        if opened.returncode == 0 or "NOTEBOOK_ARGS" not in combined:
            raise RuntimeError(
                "Reserved NOTEBOOK_ARGS did not produce the expected controlled error:\n"
                + combined
            )
        self.client("secrets-delete", "NOTEBOOK_ARGS")

        self.log("Checking stateless JWT and role revocation semantics")
        self.remove_role(primary_id)
        old_token_identity = self.api("/api/you", token=self.access_token).json()
        if old_token_identity.get("email") != self.primary_email:
            raise RuntimeError("Existing JWT stopped working before its issuer expiry")
        revoked_role_session, _ = self.browser_login(self.primary_email)
        self.api("/api/you", session=revoked_role_session, expected=403)
        revoked = self.server_admin("revoke-identity", "--email", self.primary_email)
        if not re.search(r"Deleted [1-9]\d* browser session", revoked.stdout):
            raise RuntimeError(
                f"Revocation did not delete a BFF session:\n{revoked.stdout}"
            )
        self.add_role(primary_id)
        restored_session, _ = self.browser_login(self.primary_email)
        self.api("/api/you", session=restored_session)

        self.log("End-to-end auth and workflow checks passed")

    def cleanup(self):
        errors = []
        if self.workflow and self.access_token:
            try:
                self.client(
                    "delete",
                    "-w",
                    self.workflow,
                    "--include-workspace",
                    check=False,
                )
            except Exception as error:  # noqa: BLE001 - best-effort cleanup
                errors.append(str(error))
        if not self.args.keep_users and self.realm:
            for user_id in reversed(self.user_ids):
                try:
                    self.kcadm(
                        "delete", "users", user_id, "-r", self.realm, check=False
                    )
                except Exception as error:  # noqa: BLE001 - best-effort cleanup
                    errors.append(str(error))
        if errors:
            print("Cleanup warnings:\n" + "\n".join(errors), file=sys.stderr)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-url", default="https://localhost:30443", help="Public REANA URL"
    )
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--release", default="reana", help="Helm resource prefix")
    parser.add_argument(
        "--keep-users", action="store_true", help="Keep disposable Keycloak users"
    )
    parser.add_argument(
        "--reana-client",
        default=None,
        help=(
            "Path to the reana-client executable to drive. Defaults to "
            "whatever `reana-client` resolves to on PATH, so any correctly "
            "activated virtualenv works -- no fixed checkout layout is "
            "assumed."
        ),
    )
    parser.add_argument(
        "--demo-dir",
        default=None,
        help=(
            "Path to a reana-demo-helloworld checkout to run reana-client "
            "commands from. Defaults to a `reana-demo-helloworld` directory "
            "next to this script's own repository checkout."
        ),
    )
    args = parser.parse_args()

    if args.reana_client is None:
        resolved = shutil.which("reana-client")
        if resolved is None:
            parser.error(
                "reana-client is not on PATH and --reana-client was not "
                "given; activate the virtualenv it's installed in, or pass "
                "--reana-client explicitly."
            )
        args.reana_client = Path(resolved).resolve()
    else:
        # Resolved to an absolute path now, while it's still relative to
        # this process's own cwd: every reana-client subprocess this script
        # spawns runs with cwd=args.demo_dir instead, so an explicit
        # relative path (e.g. --reana-client ./bin/reana-client) would
        # otherwise pass this validation but then resolve against the demo
        # checkout instead of the directory the script was launched from.
        args.reana_client = Path(args.reana_client).resolve()
        if not args.reana_client.is_file():
            parser.error(f"--reana-client does not exist: {args.reana_client}")

    if args.demo_dir is None:
        args.demo_dir = ROOT / "reana-demo-helloworld"
    else:
        args.demo_dir = Path(args.demo_dir).resolve()
    if not args.demo_dir.is_dir():
        parser.error(
            f"--demo-dir does not exist or is not a directory: {args.demo_dir}"
        )
    if not (args.demo_dir / "reana.yaml").is_file():
        parser.error(
            "--demo-dir is not a REANA demo checkout (missing reana.yaml): "
            f"{args.demo_dir}"
        )

    return args


def main():
    args = parse_args()
    runner = E2E(args)
    try:
        runner.run_all()
    finally:
        runner.cleanup()


if __name__ == "__main__":
    main()
