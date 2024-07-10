#!/usr/bin/env python3

import sys
import time

from icosagent.authmngr.authmngr import AuthManager
from icosagent.config.config import read_config, DMConfig
from icosagent.deploymngr.nuvla import nuvla_authn, Nuvla, \
    DeploymentManagerNuvla
from icosagent.jobmngr.jm import JobManagerProxy
from icosagent.log import get_logger

log = get_logger('main')

CONFIG_PATH = '/etc/icos/dm.conf'

SLEEP_SEC = 10


def sleep(sec=SLEEP_SEC):
    log.info(f'Sleeping {sec} sec...')
    time.sleep(sec)


def main():
    if len(sys.argv) > 1:
        conf_file = sys.argv[1]
    else:
        conf_file = CONFIG_PATH
    config: DMConfig = read_config(conf_file)

    auth_mngr = AuthManager(config.keycloak)
    jm = JobManagerProxy(config.jm, auth_mngr)

    nuvla_api: Nuvla = nuvla_authn(config.nuvla)
    dm = DeploymentManagerNuvla(nuvla_api)

    while True:
        try:
            log.info('Getting deployments to launch on Nuvla.')
            deployments = jm.deployments_to_launch()
            if not deployments:
                log.info('No deployments to launch on Nuvla.')
                sleep()
                continue
        except Exception:
            log.exception('Failed getting deployments to launch from ICOS JM.')
            sleep()
            continue

        try:
            log.info(f'Deploying {len(deployments)} deployments on Nuvla.')
            deployed = dm.deploy(deployments, jm)
            if deployed:
                log.info('Deployed on Nuvla: %s', deployed)
            else:
                log.info('Nothing was deployed on Nuvla.')
        except Exception:
            log.exception('Failed starting deployments on Nuvla.')

        sleep()


if __name__ == '__main__':
    main()
