from http import HTTPStatus
import os
import requests

from icosagent.authmngr.authmngr import AuthManager
from icosagent.config.config import JobManagerConf as JMConfig
from icosagent.log import get_logger

log = get_logger('job-manager')


class JobManagerProxy:

    JOB_CREATED = 1
    JOB_PROCESSING = 2
    JOB_COMPLETED = 3
    JOB_DEGRADED = 4

    JM_URI = 'jobmanager'
    JOBS_URI = os.path.join(JM_URI, 'jobs')
    JOBS_URI_NUVLA = os.path.join(JOBS_URI, 'executable/orchestrator/nuvla')

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
        depl_jobs_url_nuvla = os.path.join(self.url, self.JOBS_URI_NUVLA)
        try:
            for _ in range(2):  # retry logic for re-authentication
                self._cond_authn()
                headers = {'Authorization': f'Bearer {self.token}'}
                log.info('Getting deployments from JM...')
                resp = requests.get(depl_jobs_url_nuvla, headers=headers)

                if self._is_need_reauthn(resp):
                    continue
                resp.raise_for_status()
                return resp.json()

        except requests.exceptions.RequestException as ex:
            log.exception(ex)

        return []

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

    def mark_job_as_completed(self, job_id):
        data = {'ID': job_id, 'uuid': job_id,
                'locker': True, 'state': self.JOB_COMPLETED}
        self._put_job(job_id, data, 'Mark as completed')

    def lock_job(self, job_id):
        data = {'ID': job_id, 'uuid': job_id,
                'locker': True, 'state': self.JOB_PROCESSING}
        self._put_job(job_id, data, 'Lock')

    def unlock_job(self, job_id):
        data = {'ID': job_id, 'uuid': job_id,
                'locker': False, 'state': self.JOB_CREATED}
        self._put_job(job_id, data, 'Unlock')

    def _put_job(self, job_id: str, data: dict, action: str):
        depl_job_url = os.path.join(self.url, self.JOBS_URI, job_id)
        try:
            for _ in range(2):  # retry logic for re-authentication
                if not self.token:
                    log.info('Authenticating with ICOS.')
                    self.token = self.auth_mngr.get_token()
                headers = {'Authorization': f'Bearer {self.token}'}
                log.info(f'{action} job {job_id}')
                resp = requests.put(depl_job_url, json=data, headers=headers)

                if resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
                    log.warning('Re-authenticating with ICOS.')
                    self.token = None
                    continue
                resp.raise_for_status()
                return resp.json()

        except requests.exceptions.RequestException as ex:
            log.exception(ex)
