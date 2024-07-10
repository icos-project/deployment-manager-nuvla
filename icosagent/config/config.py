import configparser
import os.path


class KeycloakConf:
    url: str
    client_id: str
    client_secret: str
    grant_type: str = 'client_credentials'


class NuvlaConf:
    url = 'https://nuvla.io'
    api_key = ''
    api_secret = ''
    debug = False


class JobManagerConf:
    url: str


class DMConfig:
    keycloak: KeycloakConf
    nuvla: NuvlaConf
    jm: JobManagerConf


def keyclok_from_config(config: configparser.ConfigParser) -> KeycloakConf:
    keycloak = KeycloakConf()
    keycloak.url = config['keycloak']['url']
    keycloak.client_id = config['keycloak']['client_id']
    keycloak.client_secret = config['keycloak'].get('client_secret')
    keycloak.grant_type = config['keycloak'].get('grant_type',
                                                 'client_credentials')
    return keycloak


def nuvla_from_config(config: configparser.ConfigParser) -> NuvlaConf:
    nuvla = NuvlaConf()
    nuvla.url = config['nuvla'].get('url') or nuvla.url
    nuvla.api_key = config['nuvla']['api_key']
    nuvla.api_secret = config['nuvla']['api_secret']
    return nuvla


def jm_from_config(config: configparser.ConfigParser) -> JobManagerConf:
    jm = JobManagerConf()
    jm.url = config['jm']['url']
    return jm


def read_config(file_path) -> DMConfig:
    if not os.path.exists(file_path):
        raise Exception(f'Config file {file_path} not found.')
    config = configparser.ConfigParser()
    config.read(file_path)

    keycloak = keyclok_from_config(config)
    nuvla = nuvla_from_config(config)
    jm = jm_from_config(config)

    conf: DMConfig = DMConfig()
    conf.keycloak = keycloak
    conf.nuvla = nuvla
    conf.jm = jm

    return conf
