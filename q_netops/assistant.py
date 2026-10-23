"""Local, deterministic Q-NetOps help grounded in the active demo context."""
from .mission_analyst import answer_mission_question


def answer_question(message: str, context: dict | None = None) -> str:
    text = (message or "").strip().lower()
    context = context or {}
    policy = context.get("policy", "Q-NetOps adaptive")
    scenario = context.get("scenario", "the selected scenario")
    request = context.get("request", {})
    metrics = context.get("metrics", {})
    fault = context.get("fault", {})
    mission_answer = answer_mission_question(message, context.get("mission_analysis"))
    if mission_answer:
        return mission_answer
    delivery = metrics.get("delivery_rate")
    fidelity = metrics.get("mean_delivered_fidelity")

    if any(word in text for word in ("hello", "hi", "hey", "help")) and len(text.split()) <= 4:
        return ("Hi — I can help with the mission setup, route decisions, fidelity, latency, memory use, "
                "the policy comparison, IBM QPU validation, or what is and is not live. Ask a question, "
                "or open **Help & user guide** for the short walkthrough.")
    if any(phrase in text for phrase in ("manual", "user guide", "how to use", "how do i", "get started", "run a mission", "use this")):
        return ("**Quick start**\n\n"
                "1. In **Mission setup**, choose a stress scenario and set the target fidelity, traffic pressure, memory, retries, and deadline.\n"
                "2. Select **Run this mission**. The same seeded request stream is replayed across the policies.\n"
                "3. In **Network control**, choose a controller and request; step through the event trace to inspect attempts, swaps, and the final outcome.\n"
                "4. Open **Policy arena** to compare policies. Use **Physics & assumptions** to see the model limits.\n\n"
                "Use the Network control map selector to switch between the India & Indian Ocean geographic concepts and the Chennai simulation trace. Geographic corridors are illustrative, not connected quantum links.")
    if any(word in text for word in ("fault", "failure injection", "outage", "degrad")):
        if fault.get("link") and fault["link"] != "None":
            return (f"This mission applies a controlled **{fault['severity']}% success-probability reduction** to **{fault['link']}** in the synthetic Chennai graph. "
                    "The same fault setting is used for every policy. Inspect the red edge in the Chennai simulator map, the `fault_injected` event, and the policy comparison. This is a simulation control, not a live link outage.")
        return "No link fault is active. Choose L1–L8 and a reduction percentage in Mission setup, submit the mission, and replay the same seeded traffic across all policies. The injected fault only changes the synthetic Chennai simulation."
    if any(word in text for word in ("export", "download report", "mission report", "reproduc")):
        return "Open the Mission Analyst debrief and select **Generate PDF report**, then download the generated file. Policy arena also retains the detailed JSON export with the seed, settings, per-policy rows, and recorded event traces."
    if any(word in text for word in ("play", "pause", "auto-play", "autoplay")):
        return "In Network control, choose a policy and request, then select Play event trace. It advances through that request's recorded events; pause it or scrub the event slider at any time."
    if any(phrase in text for phrase in ("how it works", "how does", "algorithm", "controller work", "adaptive controller", "machine learning", "predictive")):
        return ("Q-NetOps is an **interpretable simulation controller**, not a trained machine-learning model. "
                "It evaluates candidate routes with 64 Monte Carlo forecasts using the simulator's link loss, noise, swap success, fidelity decay, deadline, and memory constraints. "
                "It ranks requests using deadline urgency, completed route segments, estimated fidelity, generation success probability, and memory headroom. "
                "After repeated link failures it can replan around the failed section while preserving completed segments and in-flight work on shared links. "
                "It tracks pair age and decayed fidelity, and refreshes a segment only when a forecast says the target can be recovered before the deadline. "
                "The event replay records repairs, refresh decisions, memory occupancy, and outcomes for inspection.")
    if any(word in text for word in ("latency", "time", "deadline", "slow")):
        return ("**Delivery time** is measured from request arrival to completion or its deadline. "
                "The simulation includes link-generation attempts, propagation, swap scheduling, and waiting for repeater memory. "
                "Compare the same request stream in Policy arena; lower latency alone does not mean a request met the fidelity target.")
    if any(word in text for word in ("memory", "slot", "occupancy", "waste", "decoherence")):
        return ("Each repeater has a finite number of memory slots. Stored pairs carry an age and decayed fidelity; expired pairs are released. "
                "Open **Resource & entanglement state** in Network control to inspect per-node occupied/free slots and the selected request's pair ages and fidelities. "
                "Q-NetOps can refresh one aging segment when the predicted fidelity gain justifies the extra generation time. "
                "Increase memory capacity in Mission setup to see how it changes results.")
    if any(word in text for word in ("repair", "preserve", "rebuild", "segment", "local recovery")):
        return ("After repeated heralded failures on a link, Q-NetOps can replan around that link. "
                "It keeps completed entangled pairs and in-flight generation on links shared by the old and new routes, releasing only resources tied to removed links. "
                "Inspect `route_repaired` events and the preserved-segment count in Network control. This behavior is evaluated in the synthetic Chennai simulation.")
    if any(word in text for word in ("success", "qualified", "delivery rate", "delivered pair")):
        return ("**Qualified delivery** is the fraction of requests that complete entanglement swapping before the deadline and meet the configured fidelity target. "
                "A delivered-pair fidelity average includes successfully delivered pairs only. These are simulator outputs, not field measurements.")
    if any(word in text for word in ("live", "real", "ocean", "pacific", "indian", "location", "map", "telemetry")):
        return "The controller's measured test network is a synthetic five-node graph in Chennai. The India-wide and Indian Ocean maps show illustrative planning corridors, not verified fiber routes, live links, deployed repeaters, or simulation telemetry. The Policy arena results still come from the Chennai simulation."
    if any(word in text for word in ("why", "reason", "decision", "route", "path")):
        if request:
            return (f"Request {request.get('request_id', '—')} used **{request.get('path', 'an unavailable route')}**. "
                    f"The recorded controller action is **{request.get('action', '—')}**: "
                    f"{request.get('reason', 'No decision rationale was recorded.')}")
        return f"The active controller is **{policy}** under **{scenario}**. Select a request in Network control to inspect its route, action, and recorded rationale."
    if any(word in text for word in ("fidelity", "threshold", "target", "quality")):
        if request:
            return (f"This request ended with fidelity **{request.get('fidelity', 0):.3f}** and "
                    f"{'met' if request.get('delivered') else 'did not meet'} the configured service target. "
                    "Fidelity here is calculated by the simulator's Werner-state decay and swapping model.")
        return "Fidelity is the simulated entangled-pair quality score. The required threshold is configured in Mission setup; a request counts as qualified delivery only when swapping succeeds and the result meets that threshold."
    if any(word in text for word in ("compare", "baseline", "performance", "delivery rate", "success rate")):
        if delivery is not None:
            return (f"In **{scenario}**, **{policy}** qualified {delivery:.1%} of requests. "
                    + (f"Mean fidelity among delivered pairs was {fidelity:.3f}. " if fidelity is not None else "")
                    + "Open Policy arena for side-by-side results. These are simulation results, not field measurements.")
        return "Open Policy arena to compare Static Dijkstra, Greedy link quality, and Q-NetOps adaptive under the same seeded request arrivals."
    if any(word in text for word in ("api", "backend", "endpoint", "server")):
        return "The local FastAPI backend exposes /api/health, /api/corridors, /api/chat, and /api/simulate. Start it separately with `uvicorn q_netops.api:app --host 127.0.0.1 --port 8000`."
    if any(word in text for word in ("ibm", "qpu", "hardware", "key")):
        return "The IBM hardware tab can run a Bell-state validation circuit on an IBM QPU when a local key is configured. That validates QPU execution; it does not provide repeater-network telemetry."
    return ("I can explain the selected request, fidelity threshold, controller comparison, ocean-corridor concepts, "
            "or the local API. Ask about one of those and I’ll use the active mission context where available.")
