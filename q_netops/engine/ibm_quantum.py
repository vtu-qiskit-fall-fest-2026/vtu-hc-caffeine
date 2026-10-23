"""Optional IBM Quantum hardware connector. Credentials are supplied at runtime."""
from __future__ import annotations


def _service(api_key: str, instance: str | None = None):
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ImportError as exc:
        raise RuntimeError("IBM support is not installed. Install requirements.txt and restart Streamlit.") from exc

    options = {"token": api_key, "plans_preference": ["open"], "region": "us-east"}
    if instance:
        options["instance"] = instance
    return QiskitRuntimeService(**options)


def list_qpus(api_key: str, instance: str | None = None) -> list[dict[str, str]]:
    """Return operational, non-simulator backends with at least two qubits."""
    service = _service(api_key, instance)
    backends = service.backends(simulator=False, operational=True, min_num_qubits=2)
    return [{"name": backend.name, "qubits": str(backend.num_qubits)} for backend in backends]


def get_instance_usage(api_key: str, instance: str) -> dict:
    """Read current instance usage from the IBM Quantum REST API."""
    import requests

    token_response = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
        timeout=30,
    )
    token_response.raise_for_status()
    bearer = token_response.json()["access_token"]
    response = requests.get(
        "https://quantum.cloud.ibm.com/api/v1/instances/usage",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {bearer}",
            "Service-CRN": instance,
            "IBM-API-Version": "2026-04-15",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def run_bell_pair(api_key: str, backend_name: str, shots: int = 1024,
                  instance: str | None = None) -> dict:
    """Submit and collect a two-qubit Bell-state measurement on real hardware."""
    try:
        from qiskit import QuantumCircuit
        from qiskit.transpiler import generate_preset_pass_manager
        from qiskit_ibm_runtime import SamplerV2
    except ImportError as exc:
        raise RuntimeError("IBM support is not installed. Install requirements.txt and restart Streamlit.") from exc

    service = _service(api_key, instance)
    backend = service.backend(backend_name)
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure_all()
    isa_circuit = generate_preset_pass_manager(backend=backend, optimization_level=1).run(circuit)
    job = SamplerV2(backend).run([isa_circuit], shots=shots)
    result = job.result()
    counts = result[0].data.meas.get_counts()
    total = sum(counts.values())
    correlated = sum(count for bits, count in counts.items() if bits.replace(" ", "") in {"00", "11"})
    return {
        "backend": backend.name,
        "job_id": job.job_id(),
        "status": str(job.status()),
        "shots": total,
        "counts": counts,
        "correlated_fraction": correlated / total if total else 0.0,
    }


def run_bell_tomography(api_key: str, backend_name: str, shots: int = 256,
                        instance: str | None = None) -> dict:
    """Estimate |Phi+> fidelity from X, Y, and Z correlations on real hardware."""
    try:
        from qiskit import QuantumCircuit
        from qiskit.transpiler import generate_preset_pass_manager
        from qiskit_ibm_runtime import SamplerV2
    except ImportError as exc:
        raise RuntimeError("IBM support is not installed. Install requirements.txt and restart Streamlit.") from exc

    service = _service(api_key, instance)
    backend = service.backend(backend_name)
    circuits = []
    for basis in ("X", "Y", "Z"):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        if basis == "X":
            circuit.h([0, 1])
        elif basis == "Y":
            circuit.sdg([0, 1])
            circuit.h([0, 1])
        circuit.measure_all()
        circuit.name = f"bell_{basis.lower()}"
        circuits.append(circuit)

    isa_circuits = generate_preset_pass_manager(backend=backend, optimization_level=1).run(circuits)
    job = SamplerV2(backend).run(isa_circuits, shots=shots)
    results = job.result()
    correlations = {}
    counts_by_basis = {}
    for basis, pub_result in zip(("X", "Y", "Z"), results):
        counts = pub_result.data.meas.get_counts()
        n = sum(counts.values())
        parity_sum = sum((1 if bits.replace(" ", "")[-2] == bits.replace(" ", "")[-1] else -1) * count
                         for bits, count in counts.items())
        correlations[basis] = parity_sum / n if n else 0.0
        counts_by_basis[basis] = counts
    fidelity = (1 + correlations["X"] - correlations["Y"] + correlations["Z"]) / 4
    return {
        "backend": backend.name,
        "job_id": job.job_id(),
        "status": str(job.status()),
        "shots_per_basis": shots,
        "counts": counts_by_basis,
        "correlations": correlations,
        "bell_fidelity": min(1.0, max(0.0, fidelity)),
    }
