{{/*
Expand the name of the chart.
*/}}
{{- define "aegis-trader.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "aegis-trader.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "aegis-trader.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "aegis-trader.labels" -}}
helm.sh/chart: {{ include "aegis-trader.chart" . }}
{{ include "aegis-trader.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "aegis-trader.selectorLabels" -}}
app.kubernetes.io/name: {{ include "aegis-trader.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "aegis-trader.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "aegis-trader.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get NATS service URL
*/}}
{{- define "aegis-trader.natsUrl" -}}
{{- $natsPort := 4222 }}
{{- if .Values.nats }}
  {{- if .Values.nats.nats }}
    {{- if .Values.nats.nats.service }}
      {{- if .Values.nats.nats.service.ports }}
        {{- if .Values.nats.nats.service.ports.client }}
          {{- $natsPort = .Values.nats.nats.service.ports.client.port | default 4222 }}
        {{- end }}
      {{- end }}
    {{- end }}
  {{- end }}
{{- end }}
{{- printf "nats://%s-nats:%v" .Release.Name (int $natsPort) }}
{{- end }}

{{/*
Get Monitor API service URL
*/}}
{{- define "aegis-trader.monitorApiUrl" -}}
{{- $apiPort := index .Values "monitor-api" "service" "port" | default 8100 }}
{{- printf "http://%s-monitor-api:%d" .Release.Name $apiPort }}
{{- end }}