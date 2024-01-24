[keycloak]
url = {{ tpl .Values.icos.iam.authUrl . | quote }}
client_id = {{ tpl .Values.icos.iam.clientId . | quote }}
client_secret = {{ tpl .Values.icos.iam.clientSecret . | quote }}
grant_type = client_credentials

[jm]
url = {{ tpl .Values.icos.jobManager.url . | quote }}

[nuvla]
url = {{ tpl .Values.nuvla.url . | quote }}
api_key = {{ tpl .Values.nuvla.apiKey . | quote }}
api_secret = {{ tpl .Values.nuvla.apiSecret . | quote }}
debug = {{ tpl .Values.nuvla.debug . | quote }}
