from http import HTTPStatus
import os
import requests

from icosagent.authmngr.authmngr import AuthManager
from icosagent.config.config import JobManagerConf as JMConfig
from icosagent.log import get_logger

log = get_logger('job-manager')


class JobManagerProxy:

    JOB_STARTING = 'starting'
    JOB_DEPLOYED = 'deployed'
    JOB_STOPPING = 'stopping'
    JOB_STOPPED = 'stopped'
    JOB_DEGRADED = 'degraded'

    JM_URI = 'jobmanager'
    JOBS_URI = os.path.join(JM_URI, 'jobs')
    JOBS_URI_NUVLA = os.path.join(JOBS_URI, 'executable/nuvla')
    GROUPS_URI = os.path.join(JM_URI, 'groups')

    def __init__(self, config: JMConfig, auth_mngr: AuthManager):
        self.url = config.url
        self.agent_id = config.agent_id
        self.auth_mngr = auth_mngr
        self.token = None

    def _cond_authn(self):
        if not self.token:
            log.info('Authenticating with ICOS.')
            self.token = self.auth_mngr.get_token()

    def _is_need_reauthn(self, resp: requests.Response) -> bool:
        if resp.status_code == HTTPStatus.UNAUTHORIZED:
            log.warning('Need to re-authenticate with ICOS.')
            self.token = None
            return True
        return False

    def deployments_all(self) -> list:
        depl_jobs_url = os.path.join(self.url, self.JOBS_URI_NUVLA, self.agent_id)
        try:
            for _ in range(2):  # retry logic for re-authentication
                self._cond_authn()
                headers = {'Authorization': f'Bearer {self.token}'}
                log.info('Getting all deployments from JM...')
                resp = requests.get(depl_jobs_url, headers=headers)

                if self._is_need_reauthn(resp):
                    continue
                resp.raise_for_status()
                return resp.json()

        except requests.exceptions.RequestException as ex:
            log.exception(ex)

        return []

    @staticmethod
    def count_deployment_states(deployments: list) -> dict:
        states = {}
        for j in deployments:
            state = j['state']
            if state not in states:
                states[state] = 0
            states[state] += 1
        return states

    @classmethod
    def deployments_to_launch(cls, deployments: list) -> list:
        return list(filter(lambda j: j['state'] == cls.JOB_STARTING, deployments))

    @classmethod
    def deployments_to_stop(cls, deployments: list) -> list:
        return list(filter(lambda j: j['state'] == cls.JOB_STOPPING, deployments))

    def delete_job(self, job_id):
        depl_job_url = os.path.join(self.url, self.JOBS_URI, job_id)
        try:
            for _ in range(2):  # retry logic for re-authentication
                self._cond_authn()
                headers = {'Authorization': f'Bearer {self.token}'}
                log.info(f'Delete job {job_id}...')
                resp = requests.delete(depl_job_url, headers=headers)

                if self._is_need_reauthn(resp):
                    continue
                resp.raise_for_status()
                return resp.json()

        except requests.exceptions.RequestException as ex:
            log.exception(ex)

    def set_job_deployed(self, job: dict):
        job['state'] = self.JOB_DEPLOYED
        self._put_job(job['id'], job, 'Mark deployed')

    def set_job_stopped(self, job: dict):
        job['state'] = self.JOB_STOPPED
        self._put_job(job['id'], job, 'Mark stopped')

    def set_job_degraded(self, job: dict, error_msg: str):
        job['state'] = 'degraded'
        job['statusfeedback'] = error_msg
        self._put_job(job['id'], job, 'Mark degraded')

    def _put_job(self, job_id: str, data: dict, action: str):
        depl_job_url = os.path.join(self.url, self.JOBS_URI)
        try:
            for _ in range(2):  # retry logic for re-authentication
                if not self.token:
                    log.info('Authenticating with ICOS.')
                    self.token = self.auth_mngr.get_token()
                headers = {'Authorization': f'Bearer {self.token}'}
                log.info('%s job %s', action, job_id)
                params = {'id': job_id,
                          'orchestrator': 'nuvla'}
                resp = requests.put(depl_job_url, json=data, headers=headers,
                                    timeout=10, params=params)

                if resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
                    log.warning('Re-authenticating with ICOS.')
                    self.token = None
                    continue
                resp.raise_for_status()
                return resp.json()

        except requests.exceptions.RequestException as ex:
            log.exception(ex)

    def create_jobgroup(self, manifest: str):
        self._cond_authn()
        headers = {'Authorization': f'Bearer {self.token}'}
        groups_url = os.path.join(self.url, self.GROUPS_URI)
        resp = requests.post(groups_url, data=manifest, headers=headers, timeout=10)
        print(resp.status_code)
        if resp.status_code >= 400:
            log.error(f'Failed creating job group: {resp.text}')
        return resp.json()
