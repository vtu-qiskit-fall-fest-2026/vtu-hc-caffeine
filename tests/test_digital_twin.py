import unittest

from config import SimulationConfig
from q_netops.engine.digital_twin import NetworkSnapshot, score_route
from q_netops.engine.memory import MemorySlot
from q_netops.engine.network import Network


class DigitalTwinTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig()
        self.network = Network.demo(memory_capacity=2)
        self.path = [self.network.links[0], self.network.links[1],
                     self.network.links[2], self.network.links[3]]

    def test_snapshot_records_live_memory_without_sharing_it(self):
        bank = self.network.nodes["R1"].memory
        bank.allocate(MemorySlot("held", "L1", 0.0, .95, .05))
        live_slot_ids = set(bank.slots)

        snapshot = NetworkSnapshot.capture(self.network, .012)

        self.assertEqual(snapshot.captured_at_s, .012)
        self.assertEqual(snapshot.available_slots["R1"], 1)
        self.assertEqual(set(bank.slots), live_slot_ids)
        self.assertIsNot(snapshot, self.network.nodes["R1"].memory)

    def test_twin_scoring_does_not_mutate_live_resources(self):
        before = {node: tuple(sorted(item.memory.slots))
                  for node, item in self.network.nodes.items()}
        snapshot = NetworkSnapshot.capture(self.network, 0.0)

        result = score_route(snapshot, self.path, "A", self.config,
                             lambda edge, _config: .8, .01)

        after = {node: tuple(sorted(item.memory.slots))
                 for node, item in self.network.nodes.items()}
        self.assertEqual(before, after)
        self.assertEqual(result["links"], ["L1", "L2", "L3", "L4"])
        self.assertGreaterEqual(result["modeled_failure_risk"], 0.0)
        self.assertLessEqual(result["modeled_failure_risk"], 1.0)
        self.assertIn("fidelity", result["constraints"])

    def test_candidate_is_marked_infeasible_when_memory_is_full(self):
        for node in self.network.nodes.values():
            for index in range(node.memory.capacity):
                node.memory.allocate(MemorySlot(
                    f"{node.node_id}-{index}", "L1", 0.0, .95, .05))
        snapshot = NetworkSnapshot.capture(self.network, 0.0)

        result = score_route(snapshot, self.path, "A", self.config,
                             lambda edge, _config: .9, .01)

        self.assertFalse(result["feasible"])
        self.assertFalse(result["constraints"]["memory"])

    def test_route_weights_are_normalized_for_objective(self):
        snapshot = NetworkSnapshot.capture(self.network, 0.0)
        baseline = score_route(snapshot, self.path, "A", self.config,
                               lambda edge, _config: .8, .01)
        reliability_only = SimulationConfig(
            route_weight_reliability=1.0, route_weight_fidelity=0.0,
            route_weight_latency=0.0, route_weight_resources=0.0,
            route_weight_recovery=0.0)
        tuned = score_route(snapshot, self.path, "A", reliability_only,
                            lambda edge, _config: .8, .01)
        self.assertNotEqual(baseline["objective_score"], tuned["objective_score"])

    def test_request_risk_uses_end_to_end_rollout_delivery(self):
        snapshot = NetworkSnapshot.capture(self.network, 0.0)
        result = score_route(snapshot, self.path, "A", self.config,
                             lambda edge, _config: .8, .01,
                             forecast={"delivery_rate": .25})
        self.assertAlmostEqual(result["modeled_failure_risk"], .75)
        self.assertAlmostEqual(result["forecast_delivery_rate"], .25)
        self.assertNotEqual(result["single_attempt_failure_risk"], .75)


if __name__ == "__main__":
    unittest.main()
