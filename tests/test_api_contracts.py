import unittest

from pydantic import ValidationError

from q_netops.api import SimulationRequest, app, health


class ApiContractTests(unittest.TestCase):
    def test_simulation_request_accepts_configurable_route_weights(self):
        request = SimulationRequest(requests=3, route_weight_fidelity=.5)
        self.assertEqual(request.requests, 3)
        self.assertEqual(request.route_weight_fidelity, .5)

    def test_simulation_request_rejects_invalid_route_weight(self):
        with self.assertRaises(ValidationError):
            SimulationRequest(route_weight_fidelity=2.0)

    def test_health_contract(self):
        self.assertEqual(health(), {"status": "ok", "service": "q-netops-local-simulation"})

    def test_simulation_contract_is_documented(self):
        schema = app.openapi()
        self.assertIn("/api/simulate", schema["paths"])
        self.assertIn("post", schema["paths"]["/api/simulate"])


if __name__ == "__main__":
    unittest.main()
