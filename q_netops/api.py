"""Small local API for Q-NetOps demo integrations."""
import importlib
import config as config_module
from fastapi import FastAPI
from pydantic import BaseModel, Field

from .assistant import answer_question
from .deployments import CORRIDORS
from .engine.simulator import run_benchmark
from .metrics.evaluator import summarize

app = FastAPI(title="Q-NetOps API", version="0.2.0", description="Local quantum-network control simulation API")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    context: dict = Field(default_factory=dict)


class SimulationRequest(BaseModel):
    requests: int = Field(default=20, ge=1, le=100)
    seed: int = Field(default=7, ge=0, le=999999)
    target_fidelity: float = Field(default=0.70, ge=0.25, le=1.0)
    noise_scale: float = Field(default=1.0, ge=0, le=3.0)
    traffic_load: float = Field(default=0.25, ge=0, le=0.8)
    memory_slots: int = Field(default=6, ge=1, le=20)
    fault_link: str | None = Field(default=None, pattern=r"^L[1-8]$")
    failure_severity: float = Field(default=0.0, ge=0.0, le=1.0)
    deadline_ms: int = Field(default=100, ge=20, le=250)
    max_retries: int = Field(default=12, ge=1, le=30)
    route_weight_reliability: float = Field(default=0.30, ge=0.0, le=1.0)
    route_weight_fidelity: float = Field(default=0.28, ge=0.0, le=1.0)
    route_weight_latency: float = Field(default=0.16, ge=0.0, le=1.0)
    route_weight_resources: float = Field(default=0.14, ge=0.0, le=1.0)
    route_weight_recovery: float = Field(default=0.12, ge=0.0, le=1.0)


class SimulationResponse(BaseModel):
    scenario: str
    requests_per_policy: int
    seed: int
    policies: list[dict]
    request_outcomes: list[dict]
    injected_fault: dict
    notice: str


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "q-netops-local-simulation"}


@app.get("/api/corridors")
def corridors():
    return {"notice": "Illustrative deployment concepts; not live quantum infrastructure.", "corridors": CORRIDORS}


@app.post("/api/chat")
def chat(payload: ChatRequest):
    return {"answer": answer_question(payload.message, payload.context), "mode": "local-contextual-assistant"}


@app.post("/api/simulate", response_model=SimulationResponse)
def simulate(payload: SimulationRequest):
    simulation_config_type = importlib.reload(config_module).SimulationConfig
    config = simulation_config_type(
        request_count=payload.requests, seed=payload.seed,
        target_fidelity=payload.target_fidelity, noise_scale=payload.noise_scale,
        traffic_load=payload.traffic_load, memory_slots_per_node=payload.memory_slots,
        degraded_link_id=payload.fault_link, failure_severity=payload.failure_severity,
        request_deadline_s=payload.deadline_ms / 1000,
        max_retries=payload.max_retries,
        route_weight_reliability=payload.route_weight_reliability,
        route_weight_fidelity=payload.route_weight_fidelity,
        route_weight_latency=payload.route_weight_latency,
        route_weight_resources=payload.route_weight_resources,
        route_weight_recovery=payload.route_weight_recovery,
    )
    rows = run_benchmark(config)
    frame = summarize(rows)
    policies = []
    for row in frame.to_dict(orient="records"):
        policies.append({key: (None if value != value else value) for key, value in row.items()})
    return {"scenario": "custom local simulation", "requests_per_policy": payload.requests,
            "seed": payload.seed, "policies": policies,
            "request_outcomes": rows,
            "injected_fault": {"link": payload.fault_link, "success_probability_reduction": payload.failure_severity},
            "notice": "Simulation output; no live repeater network or ocean route is connected."}
