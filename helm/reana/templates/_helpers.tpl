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
Resolve the Kubernetes concurrency limit, honouring the deprecated
REANA_MAX_CONCURRENT_BATCH_WORKFLOWS environment variable.

Precedence: explicit `concurrency_limits.kubernetes` > legacy
`environment.REANA_MAX_CONCURRENT_BATCH_WORKFLOWS` > built-in default of 30.
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
