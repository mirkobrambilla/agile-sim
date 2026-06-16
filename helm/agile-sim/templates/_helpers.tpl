{{- define "agile-sim.fullname" -}}
{{- .Release.Name -}}
{{- end -}}

{{- define "agile-sim.labels" -}}
app.kubernetes.io/name: {{ include "agile-sim.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "agile-sim.selectorLabels" -}}
app.kubernetes.io/name: {{ include "agile-sim.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "agile-sim.pvcName" -}}
{{- if .Values.persistence.existingClaim -}}
{{ .Values.persistence.existingClaim }}
{{- else -}}
{{ include "agile-sim.fullname" . }}-data
{{- end -}}
{{- end -}}

{{- define "agile-sim.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{ .Values.secrets.existingSecret }}
{{- else -}}
{{ include "agile-sim.fullname" . }}-secrets
{{- end -}}
{{- end -}}
