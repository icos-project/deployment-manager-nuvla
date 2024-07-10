import time
from typing import List, Union
from requests.exceptions import HTTPError

from nuvla.api import Api as Nuvla, NuvlaError
from nuvla.api.resources.base import ResourceBase
from nuvla.api.resources.credential import Credential
from nuvla.api.resources.infra_service import InfraService, \
    InfraServiceGroup, InfraServiceK8s
from nuvla.api.resources.module import Module, AppBuilderK8s
from nuvla.api.resources.deployment import Deployment
from nuvla.api.resources.user import User

from icosagent.jobmngr.jm import JobManagerProxy
from icosagent.config.config import NuvlaConf
from icosagent.log import get_logger

log = get_logger('dm-nuvla')


def infra_service_creds_by_ne_id(nuvla: Nuvla, ne_id: str,
                                 infra_service_type=InfraServiceK8s.subtype) -> List[dict]:
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
        nuvla = Nuvla(endpoint=config.url, debug=config.debug)
    else:
        nuvla = Nuvla(debug=config.debug)

    user_api = NuvlaUser(nuvla)
    user_api.login_apikey(config.api_key, config.api_secret)

    return nuvla


class DeploymentManagerNuvla:

    PARENT_PATH = 'icos/deploymentmanagement'
    AUTHOR = 'group/icos'

    def __init__(self, nuvla_api: Nuvla):
        self.nuvla = nuvla_api
        self.dpl_api = Deployment(self.nuvla)

    def create_app_k8s(self, manifest: str, app_name: str):
        app_name = f'{app_name} {int(time.time())}'
        module_api = Module(self.nuvla)
        app = AppBuilderK8s() \
            .name(app_name) \
            .description(app_name) \
            .author(self.AUTHOR) \
            .path(f'{self.PARENT_PATH}/{app_name.lower().replace(" ", "-")}') \
            .script(manifest) \
            .build()
        log.info(f'Create app {app}')

        return module_api.create(app, exist_ok=True)

    def launch(self, dpl_manifest: str, app_name: str, infra_cred_id: str) -> str:
        module_id = self.create_app_k8s(dpl_manifest, app_name)
        log.info('Created app %s', module_id)

        dpl = self.dpl_api.launch(module_id, infra_cred_id=infra_cred_id)
        log.info('Launched deployment %s', dpl.id)

        return dpl.id

    def wait_in_final_state(self, dpl_id: str):
        final = [Deployment.STATE_STARTED, Deployment.STATE_ERROR]
        while self.dpl_api.state(self.dpl_api.get(dpl_id)) not in final:
            time.sleep(5)

    def terminate(self, dpl_id: str):
        self.dpl_api.terminate(dpl_id)

    @staticmethod
    def is_target_nuvla(target: dict) -> bool:
        if 'cluster_name' not in target:
            return False
        return target['cluster_name'].startswith('nuvlabox/') or \
            target['cluster_name'].startswith('infrastructure-service/')

    @classmethod
    def nuvla_targets(cls, deployment: dict):
        return [t for t in deployment.get('targets', []) if cls.is_target_nuvla(t)]

    def deploy_CORRECT_VERSION(self, deployments: list, jm: JobManagerProxy) -> list:
        deployed_jobs = []
        for deployment in deployments:
            if deployment.get('orchestrator') != 'nuvla':
                continue
            # For IT-1 assuming deployment targets are IDs in the form
            # nuvlabox/<UUID>. Then, for each nuvlabox/<UUID> target we will have
            # to get the associated COE credential.
            targets = self.nuvla_targets(deployment)
            if not targets:
                continue

            manifest = deployment['manifest']
            job_id = deployment['ID']

            target_to_cred = self.creds_for_targets(
                [t['cluster_name'] for t in targets])

            app_name = deployment['job_group_name']

            for target, cred in target_to_cred.items():
                jm.lock_job(job_id)
                try:
                    depl_id = self.launch(manifest, app_name, cred)
                    log.info(f'Launched app on {target} with: {depl_id}')
                    deployed_jobs.append({'job': job_id,
                                          'target': target,
                                          'deployment': depl_id})
                    jm.mark_job_as_completed(job_id)
                except Exception:
                    log.exception(f'Failed launching deployment: {job_id}')
                    jm.unlock_job(job_id)

        return deployed_jobs

    def creds_for_targets(self, targets: List[str]):
        target_to_cred = {}
        for target in targets:
            creds = infra_service_creds_by_ne_id(self.nuvla, target)
            if not creds:
                log.error(
                    'Failed finding credentials for deployment target: %s',
                    target)
                break
            # FIXME: Find a way to select the right credential.
            target_to_cred[target] = creds[0]['id']

        return target_to_cred

    # FIXME: Remove all the code below after ICOS first review.

    MANIFEST_SEPARATOR = '\r\n---\r\n'

    @classmethod
    def _merge_jobs(cls, jobs: list):
        group_ids = set()
        for job in jobs:
            group_ids.add(job.get('job_group_id'))

        jobs_merged = {}
        for gid in group_ids:
            for job in jobs:
                if job.get('job_group_id') == gid:
                    if gid not in jobs_merged:
                        jobs_merged[gid] = {'IDs': {job['ID']},
                                            'job': job}
                        del jobs_merged[gid]['job']['ID']
                    elif job['ID'] not in jobs_merged[gid]['IDs']:
                        jobs_merged[gid]['IDs'].add(job['ID'])
                        jobs_merged[gid]['job']['manifest'] += \
                            cls.MANIFEST_SEPARATOR + job['manifest']
        return jobs_merged

    def deploy(self, deployments: list, jm: JobManagerProxy) -> list:
        deployed_jobs = []
        log.debug(f'Jobs: {deployments}')
        merged_jobs = self._merge_jobs(deployments)
        log.debug(f'Merged jobs: {merged_jobs}')
        for gid, mjob in merged_jobs.items():
            if mjob['job'].get('orchestrator') != 'nuvla':
                continue
            # For IT-1 assuming deployment targets are IDs in the form
            # nuvlabox/<UUID>. Then, for each nuvlabox/<UUID> target we will have
            # to get the associated COE credential.
            job = mjob['job']
            targets = self.nuvla_targets(job)
            if not targets:
                continue

            manifest = job['manifest']
            app_name = job['job_group_name']

            target_to_cred = self.creds_for_targets(
                [t['cluster_name'] for t in targets])

            for target, cred in target_to_cred.items():
                for job_id in mjob['IDs']:
                    jm.lock_job(job_id)
                try:
                    depl_id = self.launch(manifest, app_name, cred)
                    log.info(f'Launched app on {target} with: {depl_id}')
                    deployed_jobs.append({'job': gid,
                                          'target': target,
                                          'deployment': depl_id})
                    for job_id in mjob['IDs']:
                        jm.mark_job_as_completed(job_id)
                except Exception:
                    log.exception(f'Failed launching deployment: {gid}')
                    for job_id in mjob['IDs']:
                        jm.unlock_job(job_id)

        return deployed_jobs
