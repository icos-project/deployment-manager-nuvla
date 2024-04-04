import json
import unittest

from icosagent.deploymngr.nuvla import DeploymentManagerNuvla


class TestDMNuvla(unittest.TestCase):

    def test_targets(self):
        assert [] == DeploymentManagerNuvla.nuvla_targets({})
        assert [] == DeploymentManagerNuvla.nuvla_targets({'targets': []})
        assert [] == DeploymentManagerNuvla.nuvla_targets({'targets': [{}]})
        assert [] == DeploymentManagerNuvla.nuvla_targets({'targets': [
            {'cluster_name': 'foo'}, {'cluster_name': 'bar'}]})
        assert len(DeploymentManagerNuvla.nuvla_targets({'targets': [
            {'cluster_name': 'nuvlabox/foo'},
            {'cluster_name': 'infrastructure-service/bar'}]})) == 2

    def test_merge_jobs(self):
        assert {} == DeploymentManagerNuvla._merge_jobs([])
        assert {'1': {'IDs': {'a'}, 'job': {'job_group_id': '1', 'manifest': 'a'}}} == \
               DeploymentManagerNuvla._merge_jobs([{'ID': 'a', 'job_group_id': '1', 'manifest': 'a'}])
        assert {'1': {'IDs': {'a'}, 'job': {'job_group_id': '1', 'manifest': 'a'}}} == \
               DeploymentManagerNuvla._merge_jobs([{'ID': 'a', 'job_group_id': '1', 'manifest': 'a'},
                                                   {'ID': 'a', 'job_group_id': '1', 'manifest': 'a'}])
        assert {'1': {'IDs': {'a', 'b'}, 'job': {'job_group_id': '1',
                                                 'manifest': f'a{DeploymentManagerNuvla.MANIFEST_SEPARATOR}b'}}} == \
               DeploymentManagerNuvla._merge_jobs([{'ID': 'a', 'job_group_id': '1', 'manifest': 'a'},
                                                   {'ID': 'b', 'job_group_id': '1', 'manifest': 'b'}])

        with open('jm-two-jobs.json') as fp:
            jobs = json.load(fp)
        merged = DeploymentManagerNuvla._merge_jobs(jobs)

        gid = 'cb05f5df-590c-4f23-87ea-57ef964c4fa5'
        assert gid in merged

        jids = {'1ea125ca-6887-4097-9124-593abb5188f9',
                '8fc23492-c8c3-4cf0-8c54-bb6feb298fe8'}
        assert jids == merged[gid]['IDs']
        assert 'ID' not in merged[gid]['job']
        assert 'kind: Pod' in merged[gid]['job']['manifest']
        assert 'kind: Service' in merged[gid]['job']['manifest']
