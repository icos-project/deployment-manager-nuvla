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
