import time
from typing import List, Union
from requests.exceptions import HTTPError

from nuvla.api import Api as Nuvla, NuvlaError
from nuvla.api.resources.base import ResourceBase
from nuvla.api.resources.credential import Credential
from nuvla.api.resources.infra_service import InfraService, \
    InfraServiceGroup, InfraServiceK8s, InfraServiceDocker
from nuvla.api.resources.module import Module, AppBuilderK8s, AppBuilderDocker
from nuvla.api.resources.deployment import Deployment
from nuvla.api.resources.user import User

from icosagent.jobmngr.jm import JobManagerProxy
from icosagent.config.config import NuvlaConf
from icosagent.log import get_logger

log = get_logger('dm-nuvla')

def infra_service_creds_by_ne_id(nuvla: Nuvla, ne_id: str,
                                 infra_service_type: str) -> List[dict]:
    infra_service_types = [infra_service_type]
    if infra_service_type == 'docker':
        infra_service_types.append('swarm')
    ne = NuvlaEdge(nuvla)
    ne_resource = ne.get_select(ne_id, ['coe-list'])
    coe_infra = {}
    for coe in ne_resource['coe-list']:
        if coe['coe-type'] in infra_service_types:
            coe_infra = coe
            break
    if not coe_infra:
        log.warning('No infra service found for NE: %s', ne_id)
        return []

    flt = f'parent="{coe_infra["id"]}" and method="infrastructure-service-{coe_infra["coe-type"]}"'
    resources = nuvla.search(Credential.resource, filter=flt,
                             select='id').resources
    return [x.data for x in resources]

def infra_service_creds_by_ne_id_old(nuvla: Nuvla, ne_id: str,
                                 infra_service_type: str) -> List[dict]:
    """Given NuvlaEdge ID `ne_id` and the infrastructure service type
    `infra_service_type` (e.g. 'kubernetes'), finds and returns the list of
    credentials corresponding to the first infrastructure service."""

    # Get infra service group that is defined on the NE.
    ne = NuvlaEdge(nuvla)
    ne_resource = ne.get_select(ne_id, [InfraServiceGroup.resource])
    infra_service_group = ne_resource[InfraServiceGroup.resource]

    # Find all ISes of the requested type ...
    flt = f'parent="{infra_service_group}" and subtype="{infra_service_type}"'
    resources = nuvla.search(InfraService.resource, filter=flt,
                             select='id').resources
    if not resources:
        log.warning('No infra services found for NE: %s', ne_id)
        return []
    # NB! We take the first one.
    infra_service_resource = resources[0].data['id']

    # Find all credentials of the IS
    flt = f'parent="{infra_service_resource}"'
    resources = nuvla.search(Credential.resource, filter=flt,
                             select='id').resources
    return [x.data for x in resources]


class NuvlaResourceBase(ResourceBase):
    def get_select(self, ne_id, select: Union[List, None]) -> dict:
        if not select:
            return self.get(ne_id)
        return self.nuvla.get(ne_id, select=','.join(select)).data


class NuvlaEdge(NuvlaResourceBase):
    resource = 'nuvlabox'


class NuvlaUser(User):

    def login_apikey(self, api_key, api_secret):
        response = self.nuvla.login_apikey(api_key, api_secret)
        try:
            response.raise_for_status()
        except HTTPError as e:
            try:
                json_msg = e.response.json()
                message = json_msg.get('message')
                if message is None:
                    error = json_msg.get('error')
                    message = error.get('code') + ' - ' + error.get('reason')
            except:
                try:
                    message = e.response.text
                except:
                    message = str(e)
            raise NuvlaError(message, response)

        return response.json().get('resource-id')


def nuvla_authn(config: NuvlaConf) -> Nuvla:
    if config.url:
        nuvla = Nuvla(endpoint=config.url, debug=config.debug, reauthenticate=True)
    else:
        nuvla = Nuvla(debug=config.debug, reauthenticate=True)

    user_api = NuvlaUser(nuvla)
    user_api.login_apikey(config.api_key, config.api_secret)

    return nuvla


class DeploymentFailedToStartError(Exception):
    pass


class DeploymentManagerNuvla:

    PARENT_PATH = 'icos/deploymentmanagement'
    AUTHOR = 'group/icos'

    def __init__(self, nuvla_api: Nuvla):
        self.nuvla = nuvla_api
        self.dpl_api = Deployment(self.nuvla)

    def create_app(self, manifest: str, app_name: str, app_type: str):
        if app_type == InfraServiceK8s.subtype:
            return self.create_app_k8s(manifest, app_name)
        elif app_type == InfraServiceDocker.subtype:
            return self.create_app_docker(manifest, app_name)
        else:
            raise ValueError(f'Unsupported app type: {app_type}')

    def _create_app(self, manifest: str, app_name: str, builder_class):
        # app_name = f'{app_name} {int(time.time())}'
        module_api = Module(self.nuvla)
        app = builder_class() \
            .name(app_name) \
            .description(app_name) \
            .author(self.AUTHOR) \
            .path(f'{self.PARENT_PATH}/{app_name.lower().replace(" ", "-")}') \
            .script(manifest) \
            .build()
        if builder_class == AppBuilderDocker:
            app['compatibility'] = 'swarm'
        log.info(f'Create app {app}')

        return module_api.create(app, exist_ok=True)

    def create_app_k8s(self, manifest: str, app_name: str):
        return self._create_app(manifest, app_name, AppBuilderK8s)

    def create_app_docker(self, manifest: str, app_name: str):
        return self._create_app(manifest, app_name, AppBuilderDocker)

    def launch(self, dpl_manifest: str, app_name: str, infra_cred_id: str) -> str:
        cred_subtype = self.nuvla.get(infra_cred_id).data.get('subtype')
        if not cred_subtype:
            raise ValueError(f'No subtype found for credential: {infra_cred_id}') 
        log.debug('Launching app with credential subtype: %s', cred_subtype)
        app_type = cred_subtype.split('-')[-1]
        log.debug('Launching app with type: %s', app_type)
        module_id = self.create_app(dpl_manifest, app_name, app_type)
        log.info('Created app %s', module_id)

        dpl = self.dpl_api.launch(module_id, infra_cred_id=infra_cred_id)
        log.info('Launched deployment %s', dpl.id)

        return dpl.id

    def wait_in_final_state(self, dpl_id: str) -> str:
        final = [Deployment.STATE_STARTED, Deployment.STATE_ERROR]
        log.debug('Waiting for deployment %s to reach final state...', dpl_id)
        while True:
            state = self.dpl_api.state(self.dpl_api.get(dpl_id))
            if state in final:
                return state
            time.sleep(5)

    def terminate(self, dpl_id: str):
        self.dpl_api.terminate(dpl_id)

    def _target_cluster(self, deployment: dict) -> str:
        target = deployment.get('clustername')
        if not target or target == 'unknown':
            return ''
        return target

    def _creds_for_target(self, target: str, coe_type: str):
        creds = infra_service_creds_by_ne_id(self.nuvla, target, coe_type)
        if not creds:
            log.error('Failed finding credentials for deployment target %s and COE type %s',
                      target, coe_type)
            return ''
        return creds[0]['id']

    def deploy(self, deployments: list, jm: JobManagerProxy) -> list:
        deployed_jobs = []
        for deployment in deployments:
            target = self._target_cluster(deployment)
            if not target:
                log.warning('No Nuvla target cluster found for job: %s', deployment)
                continue
            coe_type = deployment.get('type', 'unknown').lower()
            if coe_type == 'unknown':
                log.warning('No COE type defined for job: %s', deployment)
                continue
            log.debug('Deployment target: %s, COE type: %s', target, coe_type)
            try:
                creds = self._creds_for_target(target, coe_type)
                if not creds:
                    err_msg = f'Failed to find credential for target {target} and COE type {coe_type}'
                    log.error(err_msg)
                    continue
            except Exception as e:
                err_msg = f'Failed to get credentials for target {target}: {e}'
                jm.set_job_degraded(deployment, err_msg)
                log.error(err_msg)
                continue

            log.debug('Creds for target %s: %s', target, creds)

            app_name = f'{deployment["job_group_id"]}-{deployment["id"]}'

            job_id = deployment['id']
            try:
                depl_id = self.launch(deployment['manifests'], app_name, creds)
                state = self.wait_in_final_state(depl_id)
                if state == Deployment.STATE_ERROR:
                    err_msg = f'Deployment failed to start. Check deployment on Nuvla: {depl_id}'
                    log.error(err_msg)
                    jm.set_job_degraded(deployment, err_msg)
                else:
                    log.info('Launched app on %s with: %s', target, depl_id)
                    deployed_jobs.append({'job': job_id,
                                        'target': target,
                                        'deployment': depl_id})
                    jm.set_job_deployed(deployment)
            except Exception:
                log.exception('Failed launching deployment: %s', job_id)

        return deployed_jobs

    def stop(self, deployments: list, jm: JobManagerProxy):
        for deployment in deployments:
            module_name = f'{deployment["job_group_id"]}-{deployment["id"]}'
            log.debug('Looking for deployment with name: %s', module_name)
            res = self.nuvla.search(Deployment.resource, filter=f'module/name="{module_name}"')
            if not res.resources:
                msg = f'No deployment found on Nuvla for job: {deployment["id"]}'
                log.warning(msg)
                jm.set_job_degraded(deployment, msg)
                continue
            depl_id = res.resources[0].data['id']
            log.info('Stopping deployment %s', depl_id)
            try:
                self.terminate(depl_id)
                log.info('Terminated deployment %s', depl_id)
                jm.delete_job(deployment['id'])
            except Exception:
                log.exception('Failed terminating deployment: %s', depl_id)
