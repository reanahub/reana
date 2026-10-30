{{/*
Create a default fully qualified app name.
We truncate the prefix at 13 chars because some Kubernetes name fields are
limited to 63 characters (by the DNS naming spec) and because REANA components
are created with a certain naming schema they should not, in total, overpass
this limit. For example, if prefix would be `my-awesome-reana`, 17 chars, when
a yadage workflow would be spawned would break the 63 char limit of the DNS
naming spec: `my-reana-batch-yadage-3c640169-d3b7-41ad-9c09-392c903fc1d8`
*/}}
{{- define "reana.prefix" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 13 | trimSuffix "-" -}}
{{- else -}}
{{- .Release.Name | trunc 13 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/*
Public HTTPS base URL of REANA. The port is omitted when it is 443.
*/}}
{{- define "reana.public_url" -}}
https://{{ .Values.reana_hostname }}{{ if ne (int .Values.reana_hostport) 443 }}:{{ .Values.reana_hostport }}{{ end }}
{{- end -}}

{{/*
Browser-facing base URL of the bundled Keycloak. Unless overridden by
`keycloak.frontend_url`, it is derived from the REANA host name and port, so
that Keycloak is served from the same host as REANA.
*/}}
{{- define "reana.keycloak_frontend_url" -}}
{{- if .Values.keycloak.frontend_url -}}
{{- .Values.keycloak.frontend_url -}}
{{- else -}}
{{- $_ := required "reana_hostname is required to derive keycloak.frontend_url" .Values.reana_hostname -}}
{{ include "reana.public_url" . }}{{ .Values.keycloak.relative_path }}
{{- end -}}
{{- end -}}

# Centralise prefixing of service account names
{{- define "reana.prefixed_infrastructure_svaccount_name" -}}
{{- include "reana.prefix" . -}}-infrastructure
{{- end -}}
{{- define "reana.prefixed_runtime_svaccount_name" -}}
{{- include "reana.prefix" . -}}-runtime
{{- end -}}

{{/* Create the specification of the shared volume. */}}
{{- define "reana.shared_volume" -}}
{{- if not (eq .Values.shared_storage.backend "hostpath") -}}
persistentVolumeClaim:
  claimName: {{ include "reana.prefix" . }}-shared-persistent-volume
  readOnly: false
{{- else -}}
hostPath:
  path: {{ .Values.shared_storage.hostpath.root_path }}
{{- end -}}
{{- end -}}

{{/*
Create the specification of the infrastructure volume used by MQ and database.
If the infrastructure volume is not defined, the default shared volume is used instead.
*/}}
{{- define "reana.infrastructure_volume" -}}
{{- if .Values.infrastructure_storage -}}
{{- if not (eq .Values.infrastructure_storage.backend "hostpath") -}}
persistentVolumeClaim:
  claimName: {{ include "reana.prefix" . }}-infrastructure-persistent-volume
  readOnly: false
{{- else -}}
hostPath:
  path: {{ .Values.infrastructure_storage.hostpath.root_path }}
{{- end -}}
{{- else -}}
{{ template "reana.shared_volume" . }}
{{- end -}}
{{- end -}}

{{/*
Render the nginx `add_header` directives of the given REANA-UI security headers,
skipping the ones set to an empty string.
*/}}
{{- define "reana.ui_nginx_security_headers" -}}
{{- with .hsts }}
add_header Strict-Transport-Security {{ . | quote }} always;
{{- end }}
{{- with .x_frame_options }}
add_header X-Frame-Options {{ . | quote }} always;
{{- end }}
{{- with .x_content_type_options }}
add_header X-Content-Type-Options {{ . | quote }} always;
{{- end }}
{{- with .cross_origin_opener_policy }}
add_header Cross-Origin-Opener-Policy {{ . | quote }} always;
{{- end }}
{{- with .cross_origin_resource_policy }}
add_header Cross-Origin-Resource-Policy {{ . | quote }} always;
{{- end }}
{{- with .referrer_policy }}
add_header Referrer-Policy {{ . | quote }} always;
{{- end }}
{{- with .permissions_policy }}
add_header Permissions-Policy {{ . | quote }} always;
{{- end }}
{{- with .csp }}
add_header Content-Security-Policy {{ . | quote }} always;
{{- end }}
{{- end -}}

{{/*
Resolve the Kubernetes concurrency limit, honouring the deprecated
REANA_MAX_CONCURRENT_BATCH_WORKFLOWS environment variable.

Precedence: explicit `concurrency_limits.kubernetes` > legacy
`environment.REANA_MAX_CONCURRENT_BATCH_WORKFLOWS` > built-in default of 30.
A legacy value of 0 is the exception: the chart still renders the explicit
Kubernetes limit, but reana-server then pauses the scheduling of new workflows
on every compute backend and Dask, whatever the other limits are.
Without this the chart would always emit the new variable and the fallback
built into reana-commons could never fire, silently raising the cap of a
deployment that only sets the legacy value.

`default` cannot express this: it treats a numeric 0 as empty, which would
discard an intentional "backend closed" cap. A value counts as configured only
when its key is present *and* non-nil, which covers both ways a Helm release
can represent the shipped `kubernetes: ~`: Helm 3 keeps the key with a nil
value, Helm 4 drops the key entirely. An explicit `0` is present and non-nil
in both, so it still reads as "configured to zero".
*/}}
{{- define "reana.k8sConcurrencyLimit" -}}
{{- $env := .Values.components.reana_server.environment | default dict -}}
{{- $limits := .Values.components.reana_server.concurrency_limits | default dict -}}
{{- $cap := 30 -}}
{{- if hasKey $env "REANA_MAX_CONCURRENT_BATCH_WORKFLOWS" -}}
{{- $legacy := index $env "REANA_MAX_CONCURRENT_BATCH_WORKFLOWS" -}}
{{- if not (kindIs "invalid" $legacy) -}}
{{- $cap = $legacy -}}
{{- end -}}
{{- end -}}
{{- if hasKey $limits "kubernetes" -}}
{{- $kubernetes := index $limits "kubernetes" -}}
{{- if not (kindIs "invalid" $kubernetes) -}}
{{- $cap = $kubernetes -}}
{{- end -}}
{{- end -}}
{{- $cap -}}
{{- end -}}

{{/*
Render the concurrency limits of the external compute backends as JSON.

Every key of `concurrency_limits` other than `kubernetes` and `dask` is the
limit of one compute backend and must name an enabled `compute_backends` entry.
Every enabled backend other than `kubernetes` must have a limit: reana-server
treats a backend without one as closed, so a forgotten limit would silently
keep its workflows queued. An explicit 0 is kept and closes the backend, while
a null value counts as missing.
*/}}
{{- define "reana.perBackendConcurrencyLimits" -}}
{{- $limits := .Values.components.reana_server.concurrency_limits | default dict -}}
{{- $perBackend := dict -}}
{{- range $backend, $limit := $limits -}}
{{- if not (has $backend (list "kubernetes" "dask")) -}}
{{- if not (has $backend $.Values.compute_backends) -}}
{{- fail (printf "components.reana_server.concurrency_limits: %q is not one of the enabled compute_backends %v" $backend $.Values.compute_backends) -}}
{{- end -}}
{{- if not (kindIs "invalid" $limit) -}}
{{- $_ := set $perBackend $backend $limit -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- range $backend := .Values.compute_backends -}}
{{- if and (ne $backend "kubernetes") (not (hasKey $perBackend $backend)) -}}
{{- fail (printf "components.reana_server.concurrency_limits.%s must be set: every enabled compute backend needs a concurrency limit (0 closes it)" $backend) -}}
{{- end -}}
{{- end -}}
{{- $perBackend | toJson -}}
{{- end -}}
