import json
import requests

from icosagent.config.config import KeycloakConf
from icosagent.log import get_logger


log = get_logger('authmngr')


class AuthManager:
    """Implements
    curl -iv -d 'client_id=ID' -d 'client_secret=SECRET' \
        -d 'grant_type=client_credentials' 'https://keycloak/path'
    """

    def __init__(self, config: KeycloakConf):
        self.url = config.url
        self.client_id = config.client_id
        self.client_secret = config.client_secret
        self.grant_type = 'client_credentials'

    def get_token(self):
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': self.grant_type
        }
        log.info('Getting token for %s of type %s from %s', self.client_id,
                 self.grant_type, self.url)
        res = requests.post(self.url, data=data)
        return json.loads(res.text)['access_token']
