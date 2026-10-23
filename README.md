<div align="center">

# Caffeine

**VTU-QFF-HC-0020** &nbsp;|&nbsp; Tier: **Both**

</div>

---

<div align="center">

| | |
| :--- | :--- |
| **Team** | Caffeine |
| **Team ID** | VTU-QFF-HC-0020 |
| **Tier** | Both |
| **Repository** | [vtu-hc-caffeine](https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-caffeine) |
| **Organisation** | [vtu-qiskit-fall-fest-2026](https://github.com/vtu-qiskit-fall-fest-2026) |
| **Event** | VTU-QFF Hackathon - VTU-Qiskit Fall Fest 2026 |

</div>

---

## 📌 Table of Contents

- [Team Members](#-team-members-github-ids)
- [Problem Statement](#-problem-statement)
- [Proposed Solution](#-proposed-solution)
- [Approach & Architecture](#-approach--architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [How to Run](#-how-to-run)
- [How to Push Code](#-how-to-push-code)
- [Submission Checklist](#-submission-checklist)
- [Resources](#-resources)
- [License](#-license)

---

## 👥 Team Members (GitHub IDs)

| # | Name | GitHub Username | Role |
| :-- | :--- | :--- | :--- |
| 1 | Harsha Oulkar | [harsha079513](https://github.com/harsha079513) | Team Lead |
| 2 | Dikshita Kullolli | [dikshitakullolli-123](https://github.com/dikshitakullolli-123) | Developer |
| 3 | Advika Gurav | [advika2006](https://github.com/advika2006) | Developer |

---

## ❓ Problem Statement

**Problem:** Quantum entanglement distribution across repeater networks is unreliable because photon loss makes link generation probabilistic, stored states decohere, swapping can fail, and repeater memories are limited. Classical shortest-path routing does not account for these changing physical and resource constraints, which can lead to wasted attempts, late deliveries, or pairs below an application's fidelity requirement.

**Why it matters:** Quantum key distribution and distributed quantum computing need dependable end-to-end entanglement. A controller that accounts for fidelity, memory availability, latency, and uncertainty can help evaluate better routing and scheduling decisions before deployment on real network hardware.

**Track / Category:** Tier Both · Quantum Communication and Networking · Autonomous quantum-network routing and scheduling.

---

## 💡 Proposed Solution

**Solution:** Q-NetOps is a Python prototype that simulates a repeater network and compares Static Dijkstra, greedy link-quality, and Q-NetOps adaptive controllers under the same seeded traffic and physical assumptions. Its dashboard visualizes mission configuration, route decisions, event traces, policy metrics, illustrative deployment corridors, mission analysis, and optional IBM Quantum circuit tomography.

**Key idea:** Use a read-only snapshot of simulated memory and link state, score candidate routes against fidelity, deadline, memory, lifetime, reliability, and recovery constraints, and combine that score with repeated rollouts of the same simulator.

**Why this works:** The adaptive controller considers more than distance and exposes reasons and candidate evaluations for review. Results are reproducible simulation evidence; they are not claims of a live quantum repeater network or trained machine-learning model.

---

## 🧩 Approach & Architecture

```mermaid
flowchart LR
    A[Mission configuration and seeded requests] --> B[Shared-network event simulator]
    B --> C[Network snapshot and candidate paths]
    C --> D[Feasibility gates and weighted route score]
    D --> E[64 deterministic candidate-route rollouts]
    E --> F[Controller action and event trace]
    F --> G[Metrics, mission analysis and PDF report]
    G --> H[Streamlit dashboard and FastAPI responses]
```

1. **Input** — Scenario, seed, request count, fidelity target, traffic load, noise, memory slots, retry budget, deadline, optional degraded link, and route-score weights.
2. **Preprocessing** — Validate and map controls into a `SimulationConfig`; construct the synthetic repeater graph and initialize a seeded request stream. Optional BBM92 calibration uses published QBER data as a fidelity proxy.
3. **Quantum core** — The main simulator uses analytic attenuation, Werner-state memory decay, and swapping equations. It is not a Qiskit density-matrix simulation. The optional IBM tab can run Bell-state preparation and tomography on a configured QPU; this is separate from repeater-network simulation.
4. **Post-processing** — Controllers choose routes/actions; the event engine records attempts, memory use, expiry, swaps, delivery, and route-repair events. Metrics aggregate delivery, fidelity, latency, memory, retries, and modeled risk.
5. **Output** — The Streamlit UI and local API expose policy comparisons, route/event analysis, deterministic assistant responses, and downloadable mission reports. Ocean corridors on the map are illustrative overlays and do not drive simulation routes.

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| Language | Python 3.11+ (verified locally on Python 3.13) |
| Dashboard | Streamlit, Pandas, Plotly |
| Maps | Folium, Streamlit-Folium, Leaflet, OpenStreetMap tiles |
| Backend API | FastAPI, Uvicorn, Pydantic validation |
| Quantum integration | Qiskit and Qiskit IBM Runtime (optional hardware tab) |
| Simulation | Project's seeded Python event simulator and analytic Werner-state model |
| Reports | ReportLab PDF generation and pypdf validation |
| Testing | Python `unittest` suite |
| Version control | Git and GitHub |

---

## 📁 Project Structure

```text
vtu-hc-caffeine/
├── app.py                         # Streamlit mission control and UI
├── config.py                      # Simulation configuration
├── main.py                        # CLI benchmark runner
├── simulator.py                   # Earlier standalone simulator module
├── requirements.txt               # Application dependencies
├── q_netops/
│   ├── api.py                     # FastAPI routes
│   ├── assistant.py               # Deterministic contextual assistant
│   ├── mission_analyst.py         # Mission analysis
│   ├── deployments.py             # Illustrative corridor map data
│   ├── controllers/               # Static, greedy and adaptive policies
│   ├── engine/                    # Physics, network, memory, simulator, IBM
│   ├── metrics/                   # KPI evaluation
│   └── data/                      # BBM92 calibration CSV
├── assets/                        # Local visual assets
├── benchmarks/                    # Precomputed robustness trials and summary
├── scripts/                       # Robustness benchmark runner
├── tests/                         # Unit tests
├── docs/
│   ├── qnetops_detailed_presentation_brief.pdf
│   └── DEMO_LINK.md               # YouTube demo URL (to be added)
├── .gitignore                     # Excludes secrets, caches and local outputs
└── README.md
```

---

## 🚀 How to Run

### Prerequisites

- Python 3.11 or newer
- [Git](https://git-scm.com/downloads)
- Internet access for OpenStreetMap tiles and optional IBM Quantum services
- IBM Quantum account/API key only if using the optional IBM hardware tab

### 1. Clone the repository

```bash
git clone https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-caffeine.git
cd vtu-hc-caffeine
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Run

Start the dashboard:

```bash
streamlit run app.py
```

Optional: start the local API in a second terminal:

```bash
uvicorn q_netops.api:app --host 127.0.0.1 --port 8000
```

Open the local API documentation at `http://127.0.0.1:8000/docs`. The API has no authentication or persistent storage; keep it bound to localhost. To use the optional IBM connector, create a local `.streamlit/secrets.toml` using the key names documented in the application setup. Never commit that file or paste real credentials into an issue, report, or presentation.

### 5. Run the tests

```bash
python -m unittest discover -s tests -v
```

Run the multi-seed robustness benchmark:

```bash
python scripts/run_robustness_benchmark.py --requests 100 --seeds 10 --first-seed 21
```

---

## 🔁 How to Push Code

> Follow the repository's branch and pull-request workflow. Do not push directly to `main`.

### Configure Git (first time only)

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### Everyday workflow

```bash
git checkout main
git pull origin main
git checkout -b feature/my-task
git add .
git commit -m "feat: describe the change"
git push -u origin feature/my-task
```

Then open a Pull Request from the pushed branch to `main`, review the diff, and merge after approval. Keep `.streamlit/secrets.toml`, `.env` files, credentials, virtual environments, caches, and local generated outputs out of Git. Use the Git & Collaboration Handbook linked below for the team's full workflow.

### Commit message convention

| Prefix | Meaning |
| :--- | :--- |
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `test:` | Adding or fixing tests |
| `refactor:` | Code restructure, no behaviour change |
| `chore:` | Build/config/dependency changes |

### Useful commands

```bash
git status
git log --oneline -10
git diff
git stash
git pull --rebase
```

### Collaborating on the same repo

- Never push directly to `main`; open a Pull Request.
- Pull before pushing to avoid rejected updates.
- Commit often with clear messages.
- Resolve conflicts locally and request review before merging.

---

## ✅ Submission Checklist

- [ ] Repository visibility and submission portal details confirmed by the team
- [x] Team listed above; confirm all collaborator invitations are accepted
- [x] README updated with the project problem, solution, architecture and run instructions
- [x] `requirements.txt` and relevant source, data, assets, benchmark and test files included
- [ ] Project installed and run from a clean clone by a teammate
- [ ] Submission branch reviewed and merged to `main` following the repository workflow
- [ ] YouTube demo recorded and link added to `docs/DEMO_LINK.md`
- [ ] PPT prepared and submitted through the official portal when instructions arrive
- [x] Detailed teammate presentation brief included at `docs/qnetops_detailed_presentation_brief.pdf`
- [ ] Short project summary submitted through the hackathon portal

---

## 📚 Resources

| Resource | Link |
| :--- | :--- |
| 🔁 Git & collaboration handbook | [Git & Collaboration Handbook](../vtu-hc-guide-git-and-collaboration) |
| ❓ Problem statements, solutions & terms | [Problem Statements, Solutions & Terms](../vtu-hc-guide-problem-and-solution) |
| 📄 README writing guide | [README Guide & Template](../vtu-hc-guide-readme-template) |
| 🧪 BBM92 experimental calibration data | [Aliro realistic BBM92 simulation/data](https://github.com/aliro-technologies/realistic-quantum-network-simulation-for-bbm92) |
| 🧭 Quantum network simulation reference | [SeQUeNCe](https://github.com/sequence-toolbox/SeQUeNCe) |
| 🧭 Quantum network simulation reference | [NIST MQNS](https://github.com/usnistgov/mqns) (GPLv3; reference only, no code copied) |
| ⚛️ Qiskit documentation | https://docs.quantum.ibm.com/ |
| ⚛️ Qiskit Runtime | https://quantum.cloud.ibm.com/docs/ |
| 💻 IBM Quantum Platform | https://quantum.ibm.com/ |
| 🗺️ OpenStreetMap | https://www.openstreetmap.org/ |
| 📋 GitHub Docs | https://docs.github.com/ |

---

## 📄 License

Released under the [MIT License](LICENSE). See `LICENSE` for details.

---

<div align="center">

**Caffeine** · Team ID `VTU-QFF-HC-0020` · Tier `Both`
· Built with Python, simulation and optional Qiskit integration for the VTU-QFF Hackathon

[⬆ Back to Top](#caffeine)

</div>
