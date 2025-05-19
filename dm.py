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


def deploy(jm: JobManagerProxy, dm: DeploymentManagerNuvla, deployments: list):
    if not deployments:
        log.info('Nothing to deploy on Nuvla.')
        return
    try:
        log.info('Deploying %d deployments on Nuvla.', len(deployments))
        log.debug('Deployments: %s', deployments)
        deployed = dm.deploy(deployments, jm)
        if deployed:
            log.info('Deployed on Nuvla: %s', deployed)
        else:
            log.warning('Nothing was deployed on Nuvla.')
    except Exception:
        log.exception('Failed starting deployments on Nuvla.')


def stop(jm: JobManagerProxy, dm: DeploymentManagerNuvla, deployments: list):
    if not deployments:
        log.info('Nothing to stop on Nuvla.')
        return
    try:
        log.info('Stopping %d deployments on Nuvla.', len(deployments))
        log.debug('Stopping deployments: %s', deployments)
        dm.stop(deployments, jm)
    except Exception:
        log.exception('Failed stopping deployments on Nuvla.')


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
            log.info('Getting all deployments.')
            deployments = jm.deployments_all()
        except Exception:
            log.exception('Failed getting deployments from ICOS JM.')
            sleep()
            continue

        if not deployments:
            log.info('No deployments found.')
            sleep()
            continue

        log.debug('Found deployments: %s', deployments)
        log.info('Deployments: total %s; %s', len(deployments),
                 jm.count_deployment_states(deployments))

        dpl_launch = jm.deployments_to_launch(deployments)
        dpl_stop = jm.deployments_to_stop(deployments)
        log.info('Deployments: to launch %s, to stop %s',
                 len(dpl_launch), len(dpl_stop))

        try:
            deploy(jm, dm, dpl_launch)
            stop(jm, dm, dpl_stop)
        except Exception:
            log.exception('Failed deploying or stopping deployments.')

        sleep()


if __name__ == '__main__':
    log.debug('Starting DM...')
    log.warning('Starting DM...')
    main()
