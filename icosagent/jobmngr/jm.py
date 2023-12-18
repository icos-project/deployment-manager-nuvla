from http import HTTPStatus
import os
import requests

from icosagent.authmngr.authmngr import AuthManager
from icosagent.config.config import JobManagerConf as JMConfig
from icosagent.log import get_logger

log = get_logger('job-manager')


class JobManagerProxy:

    DEPLOYMENT_URI = 'jobmanager'
    DEPLOYMENT_JOBS_URI = os.path.join(DEPLOYMENT_URI, 'jobs')

    def __init__(self, config: JMConfig, auth_mngr: AuthManager):
        self.url = config.url
        self.auth_mngr = auth_mngr
        self.token = None

    def _cond_authn(self):
        if not self.token:
            log.info('Authenticating with ICOS.')
            self.token = self.auth_mngr.get_token()

    def _is_need_reauthn(self, resp: requests.Response) -> bool:
        if resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            log.warning('Need to re-authenticate with ICOS.')
            self.token = None
            return True
        return False

    def deployments_to_launch(self) -> list:
        depl_jobs_url = os.path.join(self.url, self.DEPLOYMENT_JOBS_URI)
        try:
            for _ in range(2):  # retry logic for re-authentication
                self._cond_authn()
                headers = {'Authorization': f'Bearer {self.token}'}
                log.info('Getting deployments from JM...')
                resp = requests.get(depl_jobs_url, headers=headers)

                if self._is_need_reauthn(resp):
                    continue
                resp.raise_for_status()
                return resp.json()

        except requests.exceptions.RequestException as ex:
            log.exception(ex)

        return []

    def delete_job(self, job_id):
        depl_job_url = os.path.join(self.url, self.DEPLOYMENT_JOBS_URI, job_id)
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

    def lock_job(self, job_id):
        data = {'ID': job_id, 'uuid': job_id, 'locker': True, 'state': 3}
        self._put_job(job_id, data, 'Lock')

    def unlock_job(self, job_id):
        data = {'ID': job_id, 'uuid': job_id, 'locker': False, 'state': 3}
        self._put_job(job_id, data, 'Unlock')

    def _put_job(self, job_id: str, data: dict, action: str):
        depl_job_url = os.path.join(self.url, self.DEPLOYMENT_JOBS_URI, job_id)
        try:
            for _ in range(2):  # retry logic for re-authentication
                if not self.token:
                    log.info('Authenticating with ICOS.')
                    self.token = self.auth_mngr.get_token()
                headers = {'Authorization': f'Bearer {self.token}'}
                log.info(f'{action} job {job_id}...')
                resp = requests.put(depl_job_url, json=data, headers=headers)

                if resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
                    log.warning('Re-authenticating with ICOS.')
                    self.token = None
                    continue
                resp.raise_for_status()
                return resp.json()

        except requests.exceptions.RequestException as ex:
            log.exception(ex)
