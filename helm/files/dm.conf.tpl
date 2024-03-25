[keycloak]
url = {{ tpl .Values.icos.iam.authUrl . }}
client_id = {{ tpl .Values.icos.iam.clientId . }}
client_secret = {{ tpl .Values.icos.iam.clientSecret . }}
grant_type = client_credentials

[jm]
url = {{ tpl .Values.icos.jobManager.url . }}

[nuvla]
url = {{ tpl .Values.nuvla.url . }}
api_key = {{ tpl .Values.nuvla.apiKey . }}
api_secret = {{ tpl .Values.nuvla.apiSecret . }}
debug = {{ tpl .Values.nuvla.debug . }}
