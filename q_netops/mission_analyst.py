"""Grounded, deterministic mission debriefs and PDF export for Q-NetOps."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import math
import re
import textwrap
import unicodedata


def _number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def build_mission_analysis(config, results, summary, scenario="Mission", timestamp=None):
    """Summarize completed simulator rows without inventing missing metrics."""
    config_data = dict(config) if isinstance(config, dict) else dict(vars(config))
    rows = [dict(row) for row in results]
    policies = {str(row.get("policy")): dict(row) for row in summary}
    adaptive = policies.get("Q-NetOps adaptive", {})
    static = policies.get("Static Dijkstra", {})
    adaptive_rows = [row for row in rows if row.get("policy") == "Q-NetOps adaptive"]
    request_count = len(adaptive_rows)
    delivered = [row for row in adaptive_rows if bool(row.get("delivered"))]
    qualified_rate = len(delivered) / request_count if request_count else None

    routes = Counter(row.get("path") for row in adaptive_rows if row.get("path"))
    actions = Counter(row.get("action") for row in adaptive_rows if row.get("action"))
    rationales = Counter(row.get("reason") for row in adaptive_rows if row.get("reason"))
    event_counts = Counter(event.get("kind") for row in adaptive_rows
                           for event in (row.get("events") or []) if event.get("kind"))
    failed = []
    request_details = []
    for row in adaptive_rows:
        events = row.get("events") or []
        request_details.append({
            "request_id": row.get("request_id"), "path": row.get("path"),
            "action": row.get("action"), "delivered": bool(row.get("delivered")),
            "fidelity": _number(row.get("fidelity")),
            "latency_ms": 1000 * _number(row.get("latency_s")) if _number(row.get("latency_s")) is not None else None,
            "decision_rationale": row.get("reason"),
            "events": [{key: event.get(key) for key in ("time_ms", "kind", "message", "edge", "fidelity")}
                       for event in events],
        })
        if row.get("delivered"):
            continue
        terminal = next((event for event in reversed(events) if event.get("kind") in {
            "deadline", "swap_rejected", "reroute_failed", "request_failed", "expired"
        }), None)
        failed.append({
            "request_id": row.get("request_id"), "path": row.get("path"),
            "action": row.get("action"), "recorded_reason": row.get("reason"),
            "terminal_event": terminal.get("kind") if terminal else None,
            "terminal_message": terminal.get("message") if terminal else None,
            "fidelity": _number(row.get("fidelity")),
        })

    metrics = {
        "qualified_delivery_rate": qualified_rate,
        "qualified_deliveries": len(delivered),
        "requests": request_count,
        "qualified_delivery_definition": (
            "Delivered requests divided by adaptive-policy requests. In this simulator, delivered is set only after successful swapping, target-fidelity qualification, and completion before the request deadline."
        ),
        "mean_delivered_pair_fidelity": _number(adaptive.get("mean_delivered_fidelity")),
        "mean_request_latency_ms": (1000 * _number(adaptive.get("mean_latency_s"))
                                     if _number(adaptive.get("mean_latency_s")) is not None else None),
        "mean_memory_utilization": _number(adaptive.get("mean_memory_utilization")),
        "generation_attempts_per_request": _number(adaptive.get("mean_generation_attempts")),
        "wasted_attempts_per_request": _number(adaptive.get("mean_wasted_attempts")),
        "memory_blocked_ticks": sum(int(row.get("memory_blocked_ticks") or 0) for row in adaptive_rows),
        "local_repairs": sum(int(row.get("local_repairs") or 0) for row in adaptive_rows),
        "preserved_segments": sum(int(row.get("preserved_segments") or 0) for row in adaptive_rows),
    }
    comparisons = {}
    for key, label, multiplier in (
        ("success_rate", "qualified_delivery_rate", 1),
        ("mean_delivered_fidelity", "mean_delivered_pair_fidelity", 1),
        ("mean_latency_s", "mean_request_latency_ms", 1000),
        ("mean_memory_utilization", "mean_memory_utilization", 1),
        ("mean_wasted_attempts", "mean_wasted_attempts", 1),
    ):
        a, b = _number(adaptive.get(key)), _number(static.get(key))
        comparisons[label] = {"adaptive": a * multiplier if a is not None else None,
                              "static": b * multiplier if b is not None else None,
                              "delta_adaptive_minus_static": (a - b) * multiplier
                              if a is not None and b is not None else None}

    strengths, bottlenecks, recommendations = [], [], []
    delta = comparisons["qualified_delivery_rate"]["delta_adaptive_minus_static"]
    if delta is not None:
        if delta > 0:
            strengths.append(f"Adaptive qualified delivery exceeded Static Dijkstra by {delta:.1%} in this run.")
        elif delta < 0:
            bottlenecks.append(f"Adaptive qualified delivery was {abs(delta):.1%} below Static Dijkstra in this run.")
        else:
            strengths.append("Adaptive and Static Dijkstra had the same qualified delivery rate in this run.")
    if metrics["local_repairs"]:
        strengths.append(f"The adaptive controller recorded {metrics['local_repairs']} local route repair(s), preserving {metrics['preserved_segments']} segment(s).")
    if failed:
        reason_counts = Counter(item["terminal_event"] or "no terminal failure event recorded" for item in failed)
        bottlenecks.append("Adaptive requests not delivered: " + "; ".join(f"{name}: {count}" for name, count in reason_counts.items()) + ".")
        recommendations.append("Inspect the recorded failed-request events, then vary one relevant setting at a time (for example deadline, retry budget, or the injected-link severity) and compare the same seed.")
    if metrics["memory_blocked_ticks"]:
        bottlenecks.append(f"The event rows recorded {metrics['memory_blocked_ticks']} memory-blocked ticks across adaptive requests.")
        recommendations.append("Repeat with more repeater memory slots to measure whether contention limits qualified delivery.")
    if not recommendations:
        recommendations.append("Repeat the mission with a changed seed and one controlled parameter change to check whether the observed policy difference is robust.")
    if delta is not None and delta <= 0:
        recommendations.append("Compare route choices and recorded failures in Network control before adjusting the adaptive objective weights.")

    return {
        "title": f"{scenario} mission debrief", "generated_at": timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": scenario, "seed": config_data.get("seed"), "request_count": request_count,
        "configuration": config_data, "metrics": metrics, "comparisons": comparisons,
        "routes": routes.most_common(), "controller_actions": dict(actions),
        "decision_rationales": dict(rationales), "event_counts": dict(event_counts), "failed_requests": failed,
        "request_details": request_details,
        "strengths": strengths or ["No positive finding can be established from the available rows."],
        "bottlenecks": bottlenecks or ["No recorded bottleneck identified in the available adaptive event and metric data."],
        "recommendations": recommendations,
        "data_scope": "Completed synthetic Chennai simulator outcomes; not live network telemetry.",
        "event_trace_available": any(row.get("events") is not None for row in adaptive_rows),
        "limitations": ["Monte Carlo route forecasts and modeled risk are estimates, not measured outcomes.",
                        "Published BBM92 calibration, when selected, is static experimental input rather than live telemetry.",
                        "Failure causes are reported only when a corresponding terminal event was recorded; controller rationale is not treated as a failure cause."],
    }


def answer_mission_question(message, analysis):
    """Answer follow-ups from mission data; return None when not mission-specific."""
    if not analysis:
        return None
    text = (message or "").lower()
    metrics = analysis.get("metrics", {})
    requested_id = re.search(r"\brequest\s*#?\s*(\d+)\b", text)
    if requested_id and any(word in text for word in ("route", "path", "event", "decision", "why", "happen", "fidelity")):
        request_id = int(requested_id.group(1))
        row = next((item for item in analysis.get("request_details", []) if item.get("request_id") == request_id), None)
        if not row:
            return f"Request {request_id} is not present in the recorded adaptive mission results."
        fidelity = row.get("fidelity")
        lines = [f"Request {request_id}: route {row.get('path') or 'unavailable'}; action {row.get('action') or 'unavailable'}; "
                 f"{'delivered' if row.get('delivered') else 'not delivered'}; "
                 + (f"fidelity {fidelity:.3f}" if fidelity is not None else "fidelity unavailable")]
        if row.get("decision_rationale"):
            lines.append("Recorded controller rationale: " + str(row["decision_rationale"]))
        events = row.get("events", [])
        lines.append("Recorded events: " + ("; ".join(
            f"{event.get('time_ms', '?')} ms {event.get('kind')}: {event.get('message')}"
            for event in events[-10:]) if events else "no event trace available"))
        return "\n".join(lines)
    if any(word in text for word in ("fail", "failure", "unqualified", "why didn't", "not delivered")):
        failures = analysis.get("failed_requests", [])
        if not failures:
            return "No adaptive requests were unqualified in the recorded mission rows."
        known = [f"Request {item.get('request_id')}: {item['terminal_event']} — {item['terminal_message']}"
                 for item in failures if item.get("terminal_event") and item.get("terminal_message")]
        unknown = len(failures) - len(known)
        answer = "Recorded terminal failure events:\n" + "\n".join(known[:8]) if known else "No terminal failure reason was recorded for the unqualified adaptive requests."
        if unknown:
            answer += f"\n{unknown} additional unqualified request(s) have no recorded terminal failure event; their cause is unavailable."
        return answer
    if any(word in text for word in ("route", "path", "decision", "action")):
        routes = analysis.get("routes", [])
        actions = analysis.get("controller_actions", {})
        if not routes:
            return "No adaptive route data is available in this mission result."
        return ("Most common recorded adaptive routes: " + "; ".join(f"{path} ({count})" for path, count in routes[:5])
                + ". Recorded actions: " + (", ".join(f"{key} {value}" for key, value in actions.items()) or "unavailable") + ".")
    if any(word in text for word in ("baseline", "static", "compare", "comparison")):
        item = analysis.get("comparisons", {}).get("qualified_delivery_rate", {})
        if item.get("adaptive") is None or item.get("static") is None:
            return "The adaptive-versus-static qualified-delivery comparison is unavailable in this result."
        return (f"Qualified delivery was {item['adaptive']:.1%} for Q-NetOps adaptive and {item['static']:.1%} for Static Dijkstra "
                f"(adaptive minus static: {item['delta_adaptive_minus_static']:+.1%}). Same mission setup and seeded request stream; simulation results only.")
    if any(word in text for word in ("memory", "resource", "slot", "occupancy")):
        value = metrics.get("mean_memory_utilization")
        blocked = metrics.get("memory_blocked_ticks")
        return (f"Mean adaptive memory utilization was {value:.1%}." if value is not None else "Mean memory utilization is unavailable.") + (f" The recorded event rows show {blocked} memory-blocked ticks." if blocked is not None else " Memory-blocked tick data is unavailable.")
    if any(word in text for word in ("fidelity", "quality", "target")):
        value = metrics.get("mean_delivered_pair_fidelity")
        target = analysis.get("configuration", {}).get("target_fidelity")
        return (f"Mean fidelity among delivered adaptive pairs was {value:.3f}." if value is not None else "No delivered-pair fidelity average is available.") + (f" The configured target was {target:.3f}." if target is not None else " The configured target is unavailable.") + " This is not a hardware measurement."
    if any(word in text for word in ("recommend", "next experiment", "what next", "bottleneck", "strength")):
        return "Recommendations from this run:\n" + "\n".join(f"- {item}" for item in analysis.get("recommendations", []))
    if any(word in text for word in ("latency", "delivery time")):
        value = metrics.get("mean_request_latency_ms")
        return f"Mean adaptive request latency was {value:.1f} ms (all adaptive requests; delivered and unsuccessful outcomes)." if value is not None else "Mean request latency is unavailable in this result."
    return None


def build_mission_report_text(analysis):
    """Create readable, grounded report paragraphs shared with the PDF renderer."""
    m = analysis.get("metrics", {})
    cfg = analysis.get("configuration", {})
    lines = [analysis.get("title", "Q-NetOps Mission Report"),
             f"Generated: {analysis.get('generated_at', 'Unavailable')} | Scenario: {analysis.get('scenario', 'Unavailable')} | Seed: {analysis.get('seed', 'Unavailable')}",
             "", "EXECUTIVE SUMMARY"]
    rate = m.get("qualified_delivery_rate")
    lines.append(f"Qualified delivery: {rate:.1%} ({m.get('qualified_deliveries', 0)}/{m.get('requests', 0)} requests). {m.get('qualified_delivery_definition', '')}" if rate is not None else "Qualified delivery: unavailable.")
    lines.extend(["", "MISSION CONFIGURATION"])
    for key, value in cfg.items():
        lines.append(f"{key}: {value}")
    lines.extend(["", "KEY PERFORMANCE INDICATORS"])
    for label, value, fmt in (("Delivered-pair fidelity", m.get("mean_delivered_pair_fidelity"), ".3f"),
                              ("Mean request latency (ms)", m.get("mean_request_latency_ms"), ".2f"),
                              ("Mean memory utilization", m.get("mean_memory_utilization"), ".1%"),
                              ("Generation attempts/request", m.get("generation_attempts_per_request"), ".2f"),
                              ("Wasted attempts/request", m.get("wasted_attempts_per_request"), ".2f")):
        lines.append(f"{label}: {format(value, fmt) if value is not None else 'Unavailable'}")
    lines.extend(["", "ADAPTIVE VERSUS STATIC DIJKSTRA"])
    for label, row in analysis.get("comparisons", {}).items():
        lines.append(f"{label}: adaptive={row.get('adaptive')}; static={row.get('static')}; delta={row.get('delta_adaptive_minus_static')}")
    lines.extend(["", "ROUTES AND CONTROLLER DECISIONS"])
    lines.extend([f"{route}: {count} request(s)" for route, count in analysis.get("routes", [])] or ["Route data unavailable."])
    lines.append("Actions: " + (json.dumps(analysis.get("controller_actions", {}), sort_keys=True) or "Unavailable"))
    lines.append("Recorded decision rationales: " + (json.dumps(analysis.get("decision_rationales", {}), sort_keys=True) or "Unavailable"))
    lines.append("Recorded event counts: " + (json.dumps(analysis.get("event_counts", {}), sort_keys=True) or "Unavailable"))
    lines.extend(["", "UNQUALIFIED REQUESTS / FAILURE ANALYSIS"])
    failures = analysis.get("failed_requests", [])
    lines.extend([f"Request {row.get('request_id')}: {row.get('terminal_event') or 'terminal reason unavailable'} — {row.get('terminal_message') or 'No terminal failure event was recorded.'}" for row in failures] or ["No unqualified adaptive requests recorded."])
    lines.extend(["", "FINDINGS AND NEXT EXPERIMENTS"])
    for heading in ("strengths", "bottlenecks", "recommendations"):
        lines.append(heading.title() + ":")
        lines.extend(analysis.get(heading, []) or ["Unavailable."])
    lines.extend(["", "ASSUMPTIONS AND LIMITATIONS", analysis.get("data_scope", "Simulation-only data.")])
    lines.extend(analysis.get("limitations", []))
    lines.append("All controller results are synthetic simulation outputs, not live quantum-network telemetry or QPU repeater measurements.")
    return lines


def generate_mission_pdf(analysis):
    """Generate a dependency-free, standards-compliant text PDF on the backend."""
    lines = []
    for raw in build_mission_report_text(analysis):
        normalized = unicodedata.normalize("NFKD", str(raw)).encode("ascii", "replace").decode("ascii")
        lines.extend(textwrap.wrap(normalized, width=92, break_long_words=True) or [""])
    pages = [lines[i:i + 48] for i in range(0, len(lines), 48)] or [[]]
    objects = [b""]
    page_ids = []
    font_id = 3 + len(pages) * 2
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{3 + i*2} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    for index, page_lines in enumerate(pages):
        page_id, content_id = 3 + index*2, 4 + index*2
        page_ids.append(page_id)
        commands = ["BT", "48 752 Td"]
        for line_index, line in enumerate(page_lines):
            if line_index == 0 and index == 0:
                commands.extend(["/F2 18 Tf", "0.776 0.325 0.176 rg", "0 -4 Td"])
            elif line.isupper() and len(line) > 3:
                commands.extend(["/F2 11 Tf", "0.776 0.325 0.176 rg", "0 -3 Td"])
            else:
                commands.extend(["/F1 9 Tf", "0.161 0.157 0.141 rg"])
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.extend([f"({safe}) Tj", "0 -14 Td"])
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R /F2 {font_id + 1} 0 R >> >> /Contents {content_id} 0 R >>".encode())
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, obj in enumerate(objects[1:], start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def mission_pdf_download(analysis):
    """Return the payload metadata consumed by Streamlit's download control."""
    seed = analysis.get("seed", "unknown")
    return {"data": generate_mission_pdf(analysis),
            "file_name": f"qnetops_mission_seed_{seed}.pdf",
            "mime": "application/pdf"}
