from django.test import SimpleTestCase


class PipelineFailureTest(SimpleTestCase):
    def test_blocage_du_deploiement(self):
        self.fail("ECHEC VOLONTAIRE : verifier que Jenkins bloque le deploiement")
