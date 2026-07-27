{{- define "rainbow-energy-publisher.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "rainbow-energy-publisher.fullname" -}}
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

{{- define "rainbow-energy-publisher.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "rainbow-energy-publisher.labels" -}}
helm.sh/chart: {{ include "rainbow-energy-publisher.chart" . }}
{{ include "rainbow-energy-publisher.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "rainbow-energy-publisher.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rainbow-energy-publisher.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "rainbow-energy-publisher.mqttSecretName" -}}
{{- if .Values.mqtt.existingSecret }}
{{- .Values.mqtt.existingSecret }}
{{- else if or .Values.mqtt.username .Values.mqtt.password }}
{{- include "rainbow-energy-publisher.fullname" . }}-mqtt
{{- else }}
{{- "" }}
{{- end }}
{{- end }}

{{/*
Image reference. Empty image.tag uses Chart.AppVersion (short SHA from CI;
"latest" in the local chart tree placeholder).
*/}}
{{- define "rainbow-energy-publisher.image" -}}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}
