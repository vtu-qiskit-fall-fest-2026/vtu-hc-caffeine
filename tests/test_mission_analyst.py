import unittest

from config import SimulationConfig
from q_netops.assistant import answer_question
from q_netops.controllers.static import StaticController
from q_netops.engine.simulator import run_traffic_scenario
from q_netops.metrics.evaluator import summarize
from q_netops.mission_analyst import (
    answer_mission_question,
    build_mission_analysis,
    build_mission_report_text,
    mission_pdf_download,
)


class MissionAnalystTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(request_count=2, seed=23, request_deadline_s=.02)
        self.rows = [
            {"policy": "Q-NetOps adaptive", "request_id": 1, "delivered": True,
             "fidelity": .82, "latency_s": .012, "path": "A → R2 → B", "action": "CONNECT",
             "reason": "route score", "generation_attempts": 4, "wasted_attempts": 1,
             "memory_utilization": .25, "memory_blocked_ticks": 0, "local_repairs": 1,
             "preserved_segments": 1, "events": [{"kind": "route", "message": "route selected"},
                                                     {"kind": "route_repaired", "message": "kept one segment"},
                                                     {"kind": "delivered", "message": "delivered"}]},
            {"policy": "Q-NetOps adaptive", "request_id": 2, "delivered": False,
             "fidelity": .61, "latency_s": .02, "path": "A → R1 → B", "action": "RETRACT",
             "reason": "route score", "generation_attempts": 5, "wasted_attempts": 3,
             "memory_utilization": .4, "memory_blocked_ticks": 3, "local_repairs": 0,
             "preserved_segments": 0, "events": [{"kind": "deadline", "message": "Deadline reached; remaining pairs released"}]},
            {"policy": "Static Dijkstra", "request_id": 1, "delivered": False,
             "fidelity": .55, "latency_s": .02, "path": "A → R1 → B", "action": "RETRACT",
             "reason": "shortest path", "generation_attempts": 8, "wasted_attempts": 5,
             "memory_utilization": .5, "memory_blocked_ticks": 1, "local_repairs": 0,
             "preserved_segments": 0, "events": []},
            {"policy": "Static Dijkstra", "request_id": 2, "delivered": True,
             "fidelity": .75, "latency_s": .015, "path": "A → R1 → B", "action": "CONNECT",
             "reason": "shortest path", "generation_attempts": 4, "wasted_attempts": 2,
             "memory_utilization": .3, "memory_blocked_ticks": 0, "local_repairs": 0,
             "preserved_segments": 0, "events": []},
        ]
        self.analysis = build_mission_analysis(self.config, self.rows,
                                                summarize(self.rows).to_dict(orient="records"),
                                                "Test scenario", timestamp="2026-10-22T00:00:00+00:00")

    def test_actual_simulation_completes_and_records_events(self):
        config = SimulationConfig(request_count=1, seed=5, request_deadline_s=.01)
        results = run_traffic_scenario(StaticController(), config, requests=1)
        self.assertEqual(len(results), 1)
        self.assertIn("delivered", results[0])
        self.assertTrue(results[0]["events"])
        self.assertEqual(results[0]["events"][0]["kind"], "arrival")

    def test_analysis_uses_actual_delivery_denominator_and_terminal_event(self):
        self.assertEqual(self.analysis["metrics"]["qualified_deliveries"], 1)
        self.assertEqual(self.analysis["metrics"]["requests"], 2)
        self.assertAlmostEqual(self.analysis["metrics"]["qualified_delivery_rate"], .5)
        self.assertEqual(self.analysis["failed_requests"][0]["terminal_event"], "deadline")
        self.assertEqual(self.analysis["routes"][0], ("A → R2 → B", 1))

    def test_baseline_deltas_are_derived_from_evaluator_summary(self):
        comparison = self.analysis["comparisons"]["qualified_delivery_rate"]
        self.assertEqual(comparison["adaptive"], .5)
        self.assertEqual(comparison["static"], .5)
        self.assertEqual(comparison["delta_adaptive_minus_static"], 0)
        self.assertAlmostEqual(self.analysis["comparisons"]["mean_delivered_pair_fidelity"]["adaptive"], .82)

    def test_assistant_answers_from_current_mission_events_and_results(self):
        response = answer_question("Why did requests fail?", {"mission_analysis": self.analysis})
        self.assertIn("deadline", response)
        self.assertIn("Deadline reached", response)
        self.assertIn("simulation", answer_question("How did adaptive compare with static?", {"mission_analysis": self.analysis}).lower())

    def test_unavailable_provider_uses_deterministic_mission_answer(self):
        response = answer_question("Which routes did adaptive control choose?", {"mission_analysis": self.analysis})
        self.assertIn("A → R2 → B", response)
        self.assertIn("A → R1 → B", response)
        self.assertIsNotNone(answer_mission_question("what next experiment", self.analysis))

    def test_assistant_uses_only_the_selected_request_trace(self):
        response = answer_question("What happened in request 2?", {"mission_analysis": self.analysis})
        self.assertIn("Request 2", response)
        self.assertIn("deadline", response)
        self.assertIn("Deadline reached", response)
        self.assertNotIn("Request 1:", response)

    def test_report_contains_real_findings_and_disclaimers(self):
        report = "\n".join(build_mission_report_text(self.analysis))
        self.assertIn("Test scenario", report)
        self.assertIn("A → R2 → B", report)
        self.assertIn("Deadline reached", report)
        self.assertIn("not live quantum-network telemetry", report)

    def test_pdf_download_payload_is_valid_and_named(self):
        download = mission_pdf_download(self.analysis)
        self.assertEqual(download["mime"], "application/pdf")
        self.assertEqual(download["file_name"], "qnetops_mission_seed_23.pdf")
        self.assertTrue(download["data"].startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", download["data"])
        self.assertIn(b"Test scenario", download["data"])

    def test_missing_metrics_are_labeled_unavailable(self):
        analysis = build_mission_analysis({}, [], [], "Empty mission")
        self.assertIsNone(analysis["metrics"]["qualified_delivery_rate"])
        report = "\n".join(build_mission_report_text(analysis))
        self.assertIn("Qualified delivery: unavailable", report)
        self.assertIn("Unavailable", report)


if __name__ == "__main__":
    unittest.main()
