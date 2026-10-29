"""Q-NetOps demo console: choose a network stressor, inspect a route, compare policies."""
import os
import base64
import importlib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import plotly.express as px
import folium
from folium.plugins import AntPath
import streamlit as st
from streamlit_folium import st_folium

import config as config_module
SimulationConfig = importlib.reload(config_module).SimulationConfig
from q_netops.engine.network import Network
from q_netops.engine.simulator import run_benchmark, forecast_path_quality
from q_netops.controllers.adaptive import QNetOpsController
from q_netops.metrics.evaluator import summarize
from q_netops.deployments import CORRIDORS
from q_netops.assistant import answer_question
from q_netops.mission_analyst import build_mission_analysis, mission_pdf_download

EXPERIMENT_DATA = pd.read_csv(Path(__file__).parent / "q_netops" / "data" / "bbm92_experiment_runs.csv")

st.set_page_config(page_title="Q-NetOps | Autonomous quantum network control", page_icon=":material/hub:", layout="wide")

# Shared editorial palette used by the landing screen, setup sidebar, and console.
st.html("""
<style>
  :root {color-scheme:light;--qno-ivory:#F5F1E6;--qno-cream:#FBF8F0;--qno-orange:#C6532D;--qno-charcoal:#292824;--qno-border:#D8CEBC;--qno-muted:#292824;}
  html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"] {background:var(--qno-ivory)!important;color:var(--qno-charcoal);font-family:"IBM Plex Sans","Segoe UI",Arial,sans-serif;font-size:18px;}
  [data-testid="stHeader"],[data-testid="stToolbar"] {background:var(--qno-ivory);}
  [data-testid="stAppDeployButton"] {display:none;}
  /* Streamlit's toolbar is fixed over the page canvas. Reserve a consistent
     top safe area so the first row on every view clears it. */
  [data-testid="stMainBlockContainer"] {max-width:1600px;padding:4.25rem clamp(1.5rem,3vw,3rem) 3rem!important;}
  [data-testid="stSidebar"] {background:var(--qno-cream);border-right:1px solid var(--qno-border);min-width:min(22rem,88vw)!important;max-width:min(24rem,90vw)!important;}
  [data-testid="stSidebarContent"] {padding:1.25rem 1rem 1.5rem;}
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {color:var(--qno-muted);font-size:17px;line-height:1.55;}
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {gap:6px;}
  [data-testid="stSidebar"] [data-testid="stRadio"] label {padding:11px 12px;border:1px solid transparent;border-radius:4px;color:var(--qno-muted);font-size:17px;line-height:1.4;transition:background-color .15s ease,border-color .15s ease,color .15s ease;}
  [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:var(--qno-ivory);color:var(--qno-charcoal);}
  [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {background:var(--qno-ivory);border-color:var(--qno-border);border-left:3px solid var(--qno-orange);color:var(--qno-charcoal);font-weight:650;}
  h1,h2,h3,h4 {color:var(--qno-charcoal)!important;letter-spacing:-.025em;font-family:"Roboto Condensed","Arial Narrow","Franklin Gothic Medium","Segoe UI",sans-serif;}
  h1 {font-size:40px!important;line-height:1.12!important;font-weight:750;margin-bottom:.35rem!important;} h2 {font-size:30px!important;line-height:1.2!important;font-weight:680;} h3 {font-size:25px!important;line-height:1.25!important;font-weight:650;} h4 {font-size:21px!important;line-height:1.3!important;font-weight:650;}
  p,li,label,[data-testid="stMarkdownContainer"] {color:var(--qno-muted);font-size:18px;line-height:1.65;}
  [data-testid="stCaptionContainer"],[data-testid="stCaption"] {font-size:15px!important;line-height:1.55!important;}
  [data-testid="stWidgetLabel"] p {font-size:17px!important;line-height:1.4!important;color:var(--qno-charcoal)!important;font-weight:550;}
  [data-testid="stVerticalBlock"] {gap:1rem;}
  [data-testid="stMarkdownContainer"] ul,[data-testid="stMarkdownContainer"] ol {padding-left:1.35rem;margin:.45rem 0 .8rem;}
  [data-testid="stMarkdownContainer"] li {margin:.3rem 0;}
  strong,b {color:var(--qno-charcoal);}
  a {color:var(--qno-orange);}
  [data-testid="stCaptionContainer"],[data-testid="stCaption"] {color:var(--qno-muted);}
  [data-testid="stMetric"] {height:100%;min-height:112px;background:var(--qno-cream);border:1px solid var(--qno-border);border-radius:5px;padding:18px 20px;}
  [data-testid="stMetricLabel"] {color:var(--qno-muted);font-size:17px;line-height:1.4;}
  [data-testid="stMetricValue"] {color:var(--qno-charcoal);font-size:34px;font-weight:680;line-height:1.15;}
  [data-testid="stMetricDelta"] {border-radius:3px;padding:2px 0;font-size:14px;}
  [data-testid="stTabs"] [role="tablist"] {gap:4px;border-bottom:1px solid var(--qno-border);flex-wrap:wrap;overflow-x:visible;height:auto;}
  [data-testid="stTabs"] button[role="tab"] {color:var(--qno-muted);border-radius:0;font-size:16px;font-weight:550;white-space:nowrap;}
  [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {color:var(--qno-orange);border-bottom:2px solid var(--qno-orange);}
  [data-testid="stVerticalBlockBorderWrapper"],[data-testid="stExpander"],[data-testid="stForm"],
  [data-testid="stDataFrame"],[data-testid="stTable"] {background:var(--qno-cream);border-color:var(--qno-border)!important;border-radius:5px;}
  [data-testid="stDataFrame"] {font-size:15px!important;}
  [data-testid="stForm"] {padding:16px!important;}
  [data-testid="stExpander"] summary {color:var(--qno-charcoal);}
  [data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button {border-radius:3px;border:1px solid var(--qno-orange);color:var(--qno-orange);background:var(--qno-cream);font-size:16px;font-weight:600;box-shadow:none;transition:background-color .18s ease,border-color .18s ease,color .18s ease;}
  [data-testid="stButton"] button:hover,[data-testid="stFormSubmitButton"] button:hover {background:var(--qno-orange);border-color:var(--qno-orange);color:var(--qno-cream);}
  [data-testid="stSelectbox"] [data-baseweb="select"] > div,
  [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
  [data-testid="stNumberInput"] [data-baseweb="input"],
  [data-testid="stTextInput"] [data-baseweb="input"],
  [data-testid="stTextArea"] textarea {background:var(--qno-cream);border-color:var(--qno-border);color:var(--qno-charcoal);font-size:16px;}
  [data-testid="stSelectbox"] [data-baseweb="select"],
  [data-testid="stMultiSelect"] [data-baseweb="select"],
  [data-testid="stNumberInput"] input,
  [data-testid="stTextInput"] input {font-size:16px!important;color:var(--qno-charcoal)!important;}
  [data-baseweb="popover"] ul,[data-baseweb="menu"],[role="listbox"] {background:var(--qno-cream);border:1px solid var(--qno-border);}
  [data-baseweb="popover"] li:hover,[role="option"][aria-selected="true"] {background:var(--qno-ivory);color:var(--qno-orange);}
  [data-testid="stSlider"] [role="slider"] {background:var(--qno-orange);border-color:var(--qno-orange);}
  [data-testid="stProgressBar"] > div > div {background:var(--qno-orange);}
  [data-testid="stAlert"] {background:var(--qno-cream);border:1px solid var(--qno-border);color:var(--qno-charcoal);}
  [data-testid="stChatMessage"] {background:var(--qno-cream);border:1px solid var(--qno-border);border-radius:4px;}
  [class*="st-key-qnetops_help_widget"] {position:fixed!important;right:22px;bottom:20px;z-index:100000;width:58px!important;min-width:58px!important;}
  [class*="st-key-qnetops_help_widget"] button {display:grid!important;place-items:center!important;width:56px!important;height:56px!important;padding:0!important;border-radius:50%!important;background:var(--qno-cream)!important;border:1px solid var(--qno-orange)!important;color:var(--qno-orange)!important;font-size:0!important;line-height:0!important;box-shadow:0 4px 14px rgba(41,40,36,.12);}
  [class*="st-key-qnetops_help_widget"] button svg {width:22px;height:22px;}
  [class*="st-key-qnetops_help_panel"] {position:fixed!important;right:22px;bottom:88px;width:min(390px,calc(100vw - 32px))!important;max-height:72vh;overflow-y:auto;z-index:99999;background:var(--qno-cream);border:1px solid var(--qno-border);border-radius:5px;padding:16px;box-shadow:0 14px 40px rgba(41,40,36,.16);}
  [class*="st-key-qnetops_help_panel"] [data-testid="stChatMessage"] {background:var(--qno-ivory);border:1px solid var(--qno-border);border-radius:4px;}
  .stApp button[kind="primary"],.stApp [data-testid="stBaseButton-primary"],.stApp [data-testid="baseButton-primary"] {background:var(--qno-orange)!important;border-color:var(--qno-orange)!important;color:var(--qno-cream)!important;}
  .stApp button[kind="primary"]:hover,.stApp [data-testid="stBaseButton-primary"]:hover {background:#A94324!important;border-color:#A94324!important;color:var(--qno-cream)!important;}
  [class*="st-key-qnetops_help_panel"] [data-testid="stFormSubmitButton"] button {background:var(--qno-orange)!important;border-color:var(--qno-orange)!important;color:var(--qno-cream)!important;}
  .qno-sidebar-group {margin:14px 0 5px;padding-top:9px;border-top:1px solid var(--qno-border);color:var(--qno-charcoal);font-size:16px;font-weight:650;letter-spacing:.01em;}
  .qno-finding-title {margin-bottom:.25rem;color:var(--qno-charcoal);font-size:17px;font-weight:650;}
  [data-testid="stPlotlyChart"] {background:var(--qno-cream);border:1px solid var(--qno-border);border-radius:5px;padding:12px 12px 4px;}
  @media(max-width:760px) {
    [data-testid="stMainBlockContainer"] {padding:3.75rem 1rem 2rem!important;}
    h1 {font-size:30px!important;} h2 {font-size:23px!important;} h3 {font-size:20px!important;}
    [data-testid="stMetric"] {min-height:96px;padding:14px;}
    [data-testid="stMetricValue"] {font-size:28px;}
    [data-testid="stSidebar"] {min-width:0!important;max-width:none!important;}
  }
  hr {border-color:var(--qno-border);}
  @media(prefers-reduced-motion:reduce) {*,*::before,*::after {scroll-behavior:auto!important;transition:none!important;animation:none!important;}}
</style>
""")

PRESETS = {
    "Nominal operation": {"noise": .8, "load": .10, "memory": 10},
    "Photon-loss spike": {"noise": 2.5, "load": .15, "memory": 10},
    "Memory squeeze": {"noise": 1.2, "load": .35, "memory": 2},
    "Traffic burst": {"noise": 1.0, "load": .75, "memory": 4},
}

PRIMARY_PAGES = [
    "Home",
    "Mission Simulation",
    "Network Control",
    "Reports & Analytics",
    "Policy Arena",
    "Model & Physics",
    "IBM Quantum Hardware",
    "Settings & Help",
]

PAGE_DESCRIPTIONS = {
    "Mission Simulation": "Configure a reproducible shared-network mission and inspect its outcome.",
    "Network Control": "Replay recorded controller decisions and inspect the simulated or conceptual network map.",
    "Reports & Analytics": "Review this mission’s grounded debrief and download reproducible reports.",
    "Policy Arena": "Compare controller reliability, request outcomes, and multi-seed robustness.",
    "Model & Physics": "Review the physical assumptions, calibration data, and model limits.",
    "IBM Quantum Hardware": "Discover IBM backends and run Bell-state validation when local credentials are configured.",
    "Settings & Help": "Get usage guidance and ask the local Q-NetOps assistant about the active mission.",
}


def navigate_to(page: str):
    """Set the sidebar destination from a callback before widgets are rebuilt."""
    st.session_state.qnetops_navigation = page


def start_judge_demo():
    """Load the existing reproducible judge mission and navigate to it."""
    st.session_state.update({
        "qnetops_navigation": "Mission Simulation", "qnetops_view": "console",
        "qnetops_judge_mode": True, "qnetops_judge_stage": 0,
        "mission_scenario": "Photon-loss spike", "requests_per_policy": 100,
        "mission_target": .70, "noise_multiplier": 2.5, "traffic_pressure": .35,
        "memory_capacity": 10, "retry_budget": 12, "deadline_ms": 100,
        "scenario_seed": 17, "calibration_source": "Published BBM92 experiment",
        "fault_link": "L2", "fault_severity": 90, "qnetops_judge_preset_applied": True,
    })


def render_help_widget(context=None):
    """Render a compact local help chat on every app view."""
    if "qnetops_chat" not in st.session_state:
        st.session_state.qnetops_chat = []
    if "qnetops_help_open" not in st.session_state:
        st.session_state.qnetops_help_open = False
    if st.session_state.qnetops_help_open:
        with st.container(key="qnetops_help_panel"):
            title_col, close_col = st.columns([5, 1], vertical_alignment="center")
            with title_col:
                st.markdown("#### Q-NetOps help")
            with close_col:
                if st.button("Close", key="close_floating_chat", icon=":material/close:"):
                    st.session_state.qnetops_help_open = False
                    st.rerun()
            st.caption("Ask how to use the console, read a result, or understand the simulation.")
            if not st.session_state.qnetops_chat:
                st.info("Try: “How do I run a mission?” or “What does fidelity mean?”", icon=":material/lightbulb:")
            else:
                # Keep the composer visible inside the compact floating panel;
                # the message history itself scrolls when it grows.
                with st.container(height=170, border=False):
                    for message in st.session_state.qnetops_chat[-8:]:
                        with st.chat_message(message["role"]):
                            st.markdown(message["content"])
                if st.button("Clear conversation", key="clear_floating_chat", icon=":material/delete_sweep:"):
                    st.session_state.qnetops_chat = []
                    st.rerun()
            with st.form("floating_qnetops_chat_form", clear_on_submit=True):
                prompt = st.text_input("Your question", placeholder="Ask a question…", label_visibility="collapsed", max_chars=1000)
                submitted = st.form_submit_button("Send", type="primary", icon=":material/send:", width="stretch")
            if submitted and prompt.strip():
                st.session_state.qnetops_chat.append({"role": "user", "content": prompt.strip()})
                st.session_state.qnetops_chat.append({
                    "role": "assistant",
                    "content": answer_question(prompt.strip(), context or {}),
                })
                st.rerun()
    with st.container(key="qnetops_help_widget"):
        if st.button(" ", key="open_floating_chat", icon=":material/chat:", help="Ask Q-NetOps for help"):
            st.session_state.qnetops_help_open = not st.session_state.qnetops_help_open
            st.rerun()

if "qnetops_view" not in st.session_state:
    st.session_state.qnetops_view = "landing"
if "qnetops_navigation" not in st.session_state:
    st.session_state.qnetops_navigation = "Home"
with st.sidebar:
    st.markdown("### Q / NETOPS")
    selected_page = st.radio(
        "Workspace",
        PRIMARY_PAGES,
        key="qnetops_navigation",
        label_visibility="collapsed",
        format_func=lambda page: {
            "Home": "⌂  Home",
            "Mission Simulation": "◉  Mission Simulation",
            "Network Control": "⌁  Network Control",
            "Reports & Analytics": "▤  Reports & Analytics",
            "Policy Arena": "⚖  Policy Arena",
            "Model & Physics": "∿  Model & Physics",
            "IBM Quantum Hardware": "⌘  IBM Quantum Hardware",
            "Settings & Help": "?  Settings & Help",
        }[page],
    )
    st.divider()

if selected_page == "Home":
    def inline_asset(filename):
        image_bytes = (Path(__file__).parent / "assets" / filename).read_bytes()
        # The markup supplies the data-URI MIME prefix; return only its payload.
        return base64.b64encode(image_bytes).decode("ascii")

    atom_logo = inline_asset("qnetops-quantum-mark.jpg")
    orbital_surface = inline_asset("qnetops-orbital-surface.jpg")
    st.html("""
    <style>
      .qno-landing{position:relative;overflow:hidden;isolation:isolate;min-height:420px;border:1px solid #D8CEBC;border-radius:4px;
        padding:26px clamp(24px,5vw,72px) 40px;background:#FBF8F0;color:#292824;}
      .qno-landing:before{content:"";position:absolute;inset:0;z-index:-1;opacity:.36;pointer-events:none;
        background-image:radial-gradient(#D8CEBC .7px,transparent .8px);background-size:15px 15px;
        mask-image:linear-gradient(90deg,transparent 10%,#000 68%);animation:qno-dots 30s ease-in-out infinite alternate;}
      .qno-top{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #D8CEBC;padding-bottom:18px;letter-spacing:.12em;font-size:14px;color:#292824;text-transform:uppercase}
      .qno-brand{display:flex;align-items:center;gap:12px;color:#292824;font-weight:700;letter-spacing:.2em}.qno-mark{width:42px;height:42px;object-fit:cover;border-radius:50%;mix-blend-mode:multiply;filter:grayscale(1) sepia(.75) saturate(.85) hue-rotate(335deg);border:1px solid #D8CEBC}
      .qno-state{display:flex;align-items:center;gap:9px;color:#C6532D}.qno-dot{width:7px;height:7px;border-radius:50%;background:#C6532D;}
      .qno-hero{display:grid;grid-template-columns:1.03fr .97fr;align-items:center;gap:22px;min-height:290px}.qno-copy{max-width:620px;padding:24px 0 16px;animation:qno-enter .55s ease-out both}.qno-kicker{color:#292824;font-size:14px;letter-spacing:.16em;text-transform:uppercase;margin-bottom:18px}
      .qno-copy h1{font-family:"Roboto Condensed","Arial Narrow","Franklin Gothic Medium",sans-serif;font-size:clamp(44px,5.8vw,74px);line-height:.98;letter-spacing:-.045em;font-weight:750;margin:0 0 22px;color:#292824}.qno-copy h1 span{display:block;color:#C6532D;}
      .qno-copy p{max-width:500px;font-size:18px;line-height:1.7;color:#292824;margin:0}.qno-note{display:flex;align-items:center;gap:10px;margin-top:22px;color:#292824;font-size:14px;letter-spacing:.06em;text-transform:uppercase}
      .qno-art{position:relative;height:310px;display:grid;place-items:center;animation:qno-enter .65s .08s ease-out both}.qno-orb-image{position:relative;z-index:1;width:min(100%,340px);height:310px;object-fit:cover;object-position:center 43%;mix-blend-mode:multiply;opacity:.56;-webkit-mask-image:radial-gradient(ellipse 50% 50% at center,#000 48%,rgba(0,0,0,.6) 67%,transparent 100%);mask-image:radial-gradient(ellipse 50% 50% at center,#000 48%,rgba(0,0,0,.6) 67%,transparent 100%);filter:grayscale(1) sepia(.7) saturate(.8) hue-rotate(338deg) contrast(.88);transition:transform .45s ease,opacity .45s ease;animation:qno-float 7s ease-in-out infinite}.qno-art:hover .qno-orb-image{transform:translateY(-4px) scale(1.015);opacity:.68}
      .qno-ring{position:absolute;z-index:0;width:min(43vw,450px);height:155px;border:1px solid #C6532D70;border-radius:50%;transform:rotate(-24deg);transition:translate .45s ease,opacity .45s ease;}
      .qno-art:hover .qno-ring{translate:-4px -3px;opacity:.88}.qno-art:hover .qno-ring.r2{translate:4px 2px;opacity:.8}.qno-art:hover .qno-ring.r3{translate:-2px 4px;opacity:.72}
      .qno-ring.r2{width:min(49vw,500px);height:220px;transform:rotate(26deg);border-color:#D8CEBC}.qno-ring.r3{width:min(38vw,390px);height:300px;transform:rotate(68deg);border-style:dashed;border-color:#C6532D45}
      .qno-satellite{position:absolute;z-index:2;width:7px;height:7px;border-radius:50%;background:#C6532D;left:17%;top:47%;transition:translate .45s ease,scale .45s ease}.qno-art:hover .qno-satellite{translate:8px -5px;scale:1.1}
      .qno-orbit-label{position:absolute;z-index:2;padding:9px 12px;border:1px solid #C6532D;border-radius:3px;background:#FBF8F0;color:#C6532D;font-size:12px;letter-spacing:.12em;text-transform:uppercase;transition:background .2s ease,transform .2s ease}.qno-orbit-label:hover{background:#F5F1E6;transform:translateY(-2px)}.qno-orbit-label.l1{right:2%;top:20%}.qno-orbit-label.l2{left:0;bottom:18%}.qno-art:hover .qno-orbit-label.l1{translate:3px -2px}.qno-art:hover .qno-orbit-label.l2{translate:-3px 2px}.qno-art-caption{position:absolute;z-index:2;bottom:2px;color:#292824;font-size:12px;letter-spacing:.12em;text-transform:uppercase}
      .qno-landing-footer{display:flex;justify-content:space-between;align-items:center;border-top:1px solid #D8CEBC;padding-top:17px;color:#292824;font-size:13px;letter-spacing:.1em;text-transform:uppercase}
      @keyframes qno-enter{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}@keyframes qno-dots{to{background-position:8px 5px}}@keyframes qno-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
      @media(max-width:760px){.qno-hero{grid-template-columns:1fr;gap:0}.qno-copy{padding:30px 0 0}.qno-art{height:300px}.qno-orb-image{height:300px;width:min(100%,340px)}.qno-ring{width:330px!important}.qno-top{font-size:12px}.qno-state{display:none}.qno-landing{padding:20px 22px 26px;min-height:unset}.qno-landing-footer{font-size:11px}}
      @media(prefers-reduced-motion:reduce){.qno-landing *, .qno-landing:before{animation:none!important;scroll-behavior:auto!important}}
    </style>
    <section class="qno-landing" aria-label="Q-NetOps mission control introduction">
      <header class="qno-top"><div class="qno-brand"><img class="qno-mark" src="data:image/jpeg;base64,__ATOM_LOGO__" alt=""/><span>Q / NETOPS</span></div><div>QUANTUM NETWORK CONTROL</div><div class="qno-state"><i class="qno-dot"></i> SIMULATION READY</div></header>
      <div class="qno-hero"><div class="qno-copy"><div class="qno-kicker">Autonomous entanglement orchestration · 01 / 04</div>
        <h1>ROUTE THE<br><span>QUANTUM FUTURE.</span></h1>
        <p>Coordinate entanglement across noisy links. Choose routes by fidelity, schedule around finite memory, and see every controller decision unfold.</p>
        <div class="qno-note"><span class="qno-dot"></span> Adaptive control · Shared-network simulation</div>
      </div><div class="qno-art" role="img" aria-label="Decorative animated quantum mesh and orbital visualization">
        <div class="qno-ring"></div><div class="qno-ring r2"></div><div class="qno-ring r3"></div><img class="qno-orb-image" src="data:image/jpeg;base64,__ORBITAL_SURFACE__" alt="Abstract quantum network surface"/><div class="qno-satellite"></div>
        <div class="qno-orbit-label l1">Fidelity-aware routing</div><div class="qno-orbit-label l2">Memory in the loop</div><div class="qno-art-caption">Decorative system visualization · not live telemetry</div>
      </div></div>
      <footer class="qno-landing-footer"><span>Q-NETOPS / AUTONOMOUS CONTROL</span><span>SIMULATED TOPOLOGY · SEE MODEL ASSUMPTIONS</span></footer>
    </section>
    """.replace("__ATOM_LOGO__", atom_logo)
         .replace("__ORBITAL_SURFACE__", orbital_surface))
    launch_col, judge_col, skip_col = st.columns([1.1, 1.1, 1.1], vertical_alignment="center")
    with launch_col:
        st.button("Launch simulation", icon=":material/rocket_launch:", type="primary", width="stretch",
                  key="launch_mission_control", on_click=navigate_to, args=("Mission Simulation",))
    with skip_col:
        has_previous_mission = bool(st.session_state.get("qnetops_last_mission_identity"))
        st.button("View latest results" if has_previous_mission else "Explore network control",
                  icon=":material/arrow_forward:", width="stretch", key="skip_landing",
                  on_click=navigate_to,
                  args=("Reports & Analytics" if has_previous_mission else "Network Control",))
    with judge_col:
        st.button("Run judge demo", icon=":material/movie:", width="stretch", key="start_judge_demo",
                  help="Load the seeded photon-loss scenario and guided controller comparison",
                  on_click=start_judge_demo)
    render_help_widget({"page": "landing"})
    st.subheader("A network controller built around quantum constraints", anchor=False)
    with st.container(horizontal=True):
        with st.container(border=True):
            st.caption("01 / ROUTING")
            st.markdown("**Fidelity before distance**")
            st.caption("Forecast candidate paths against attenuation, noise, and end-to-end quality requirements.")
        with st.container(border=True):
            st.caption("02 / SCHEDULING")
            st.markdown("**Memory-aware decisions**")
            st.caption("Coordinate overlapping requests while repeater memories are occupied or decohering.")
        with st.container(border=True):
            st.caption("03 / EVALUATION")
            st.markdown("**Replay every outcome**")
            st.caption("Compare adaptive control with classical baselines under the same seeded traffic.")
    with st.container(horizontal=True):
        with st.container(border=True):
            st.caption("04 / EVENT REPLAY")
            st.markdown("**Inspect each decision**")
            st.caption("Scrub recorded attempts, swaps, repairs, and terminal outcomes request by request.")
        with st.container(border=True):
            st.caption("05 / DIGITAL TWIN")
            st.markdown("**Compare route futures**")
            st.caption("Review forecast alternatives alongside the actual selected route.")
        with st.container(border=True):
            st.caption("06 / MISSION REPORTING")
            st.markdown("**Export reproducible evidence**")
            st.caption("Download the debrief, PDF report, request traces, and benchmark data.")
    st.caption("Prototype notice: India-wide and Indian Ocean corridors are geographic concepts. Controller results come from a separate synthetic five-node Chennai simulation.")
    st.stop()

scenario = st.session_state.get("mission_scenario", "Photon-loss spike")
preset = PRESETS.get(scenario, PRESETS["Photon-loss spike"])
requests = int(st.session_state.get("requests_per_policy", 200))
target = float(st.session_state.get("mission_target", .70))
noise = float(st.session_state.get("noise_multiplier", preset["noise"]))
load = float(st.session_state.get("traffic_pressure", preset["load"]))
capacity = int(st.session_state.get("memory_capacity", preset["memory"]))
retries = int(st.session_state.get("retry_budget", 12))
deadline_ms = int(st.session_state.get("deadline_ms", 100))
seed = int(st.session_state.get("scenario_seed", 7))
calibration_source = st.session_state.get("calibration_source", "Published BBM92 experiment")
calibration_run = st.session_state.get("calibration_run", "mar20-run1")
fault_link = st.session_state.get("fault_link", "None")
fault_severity = int(st.session_state.get("fault_severity", 90))
weight_reliability = float(st.session_state.get("route_weight_reliability", .30))
weight_fidelity = float(st.session_state.get("route_weight_fidelity", .28))
weight_latency = float(st.session_state.get("route_weight_latency", .16))
weight_resources = float(st.session_state.get("route_weight_resources", .14))
weight_recovery = float(st.session_state.get("route_weight_recovery", .12))

if selected_page == "Mission Simulation":
    with st.sidebar:
        st.title("Mission setup", anchor=False, icon=":material/tune:")
        if st.session_state.get("qnetops_judge_mode"):
            # Keep the guided demo's fixed, reproducible mission visible as read-only.
            scenario = "Photon-loss spike"
            requests, target, noise, load = 100, .70, 2.5, .35
            capacity, retries, deadline_ms, seed = 10, 12, 100, 17
            calibration_source = "Published BBM92 experiment"
            calibration_run = "mar20-run1"
            fault_link, fault_severity = "L2", 90
            weight_reliability, weight_fidelity, weight_latency = .30, .28, .16
            weight_resources, weight_recovery = .14, .12
            st.caption("JUDGE DEMO · FIXED REPRODUCIBLE RUN")
            st.markdown(
                "**Photon-loss spike**  \n"
                "100 requests per policy · seed 17  \n"
                "Target fidelity 0.70 · arrival pressure 0.35  \n"
                "10 memory slots · 12 retries · 100 ms deadline  \n"
                "L2 success reduction 90% · Published BBM92 calibration"
            )
            if st.button("Edit mission settings", key="judge_edit_settings", width="stretch"):
                st.session_state.qnetops_judge_mode = False
                st.session_state.qnetops_judge_preset_applied = False
                st.rerun()
        else:
            st.markdown("Set the shared mission conditions and submit to evaluate all controllers on the same seeded arrivals.")
            with st.form("mission_setup"):
                st.markdown('<div class="qno-sidebar-group">Traffic & quality</div>', unsafe_allow_html=True)
                scenario = st.selectbox("Stress scenario", list(PRESETS), index=1, key="mission_scenario")
                preset = PRESETS[scenario]
                requests = st.slider("Requests per policy", 50, 500, 200, 50, key="requests_per_policy")
                target = st.slider("Required fidelity", .55, .90, .70, .01, key="mission_target")
                noise = st.slider("Noise multiplier", 0.0, 3.0, preset["noise"], .1, key="noise_multiplier")
                load = st.slider("Request arrival pressure", 0.0, .8, preset["load"], .05, key="traffic_pressure")
                st.markdown('<div class="qno-sidebar-group">Memory & timing</div>', unsafe_allow_html=True)
                capacity = st.slider("Memory slots per repeater", 1, 20, preset["memory"], key="memory_capacity")
                retries = st.slider("Retry budget", 1, 30, 12, key="retry_budget")
                deadline_ms = st.slider("Connection deadline (ms)", 20, 250, 100, 10, key="deadline_ms")
                seed = st.number_input("Scenario seed", 0, 999999, 7, key="scenario_seed")
                st.markdown('<div class="qno-sidebar-group">Calibration & link fault</div>', unsafe_allow_html=True)
                calibration_source = st.selectbox("Link calibration", ["Published BBM92 experiment", "Problem-statement nominal model"], key="calibration_source")
                calibration_run = st.selectbox("Experimental run", EXPERIMENT_DATA.run.tolist(),
                                               disabled=calibration_source != "Published BBM92 experiment", key="calibration_run")
                fault_link = st.selectbox("Injected link fault", ["None", *[f"L{i}" for i in range(1, 9)]], key="fault_link")
                fault_severity = st.slider("Link success reduction (%)", 10, 100, 90, 5, key="fault_severity",
                                           disabled=fault_link == "None")
                with st.expander("Routing objective weights", expanded=False):
                    st.caption("Weights are normalized at evaluation time; they change route ranking, not the physical model.")
                    weight_reliability = st.slider("Reliability", 0.0, 1.0, .30, .01, key="route_weight_reliability")
                    weight_fidelity = st.slider("Fidelity", 0.0, 1.0, .28, .01, key="route_weight_fidelity")
                    weight_latency = st.slider("Latency", 0.0, 1.0, .16, .01, key="route_weight_latency")
                    weight_resources = st.slider("Resource headroom", 0.0, 1.0, .14, .01, key="route_weight_resources")
                    weight_recovery = st.slider("Recovery exposure", 0.0, 1.0, .12, .01, key="route_weight_recovery")
                st.form_submit_button("Run this mission", icon=":material/rocket_launch:", type="primary", width="stretch")
            st.caption("Requests overlap on one shared network. Higher arrival pressure shortens the mean time between requests.")

selected_measurement = EXPERIMENT_DATA.loc[EXPERIMENT_DATA.run == calibration_run].iloc[0]
# Under a symmetric Werner-state assumption, QBER=(1-V)/2 and F=(1+3V)/4,
# giving F=1-1.5*QBER. This converts measured BBM92 QBER to a calibration proxy.
measured_link_fidelity = max(.25, min(1.0, 1 - 1.5 * float(selected_measurement.qber)))
calibration = measured_link_fidelity if calibration_source == "Published BBM92 experiment" else None
config = SimulationConfig(request_count=requests, target_fidelity=target,
                          noise_scale=noise, traffic_load=load,
                          memory_slots_per_node=capacity, max_retries=retries, seed=int(seed),
                          request_deadline_s=deadline_ms / 1000,
                          link_fidelity_calibration=calibration,
                          degraded_link_id=None if fault_link == "None" else fault_link,
                          failure_severity=0 if fault_link == "None" else fault_severity / 100,
                          route_weight_reliability=weight_reliability,
                          route_weight_fidelity=weight_fidelity,
                          route_weight_latency=weight_latency,
                          route_weight_resources=weight_resources,
                          route_weight_recovery=weight_recovery)

@st.cache_data(show_spinner="Running network trials…", max_entries=12)
def load_results(cfg, engine_revision="local-repair-aging-v3"):
    return run_benchmark(cfg)


@st.cache_data(show_spinner="Forecasting alternative routes…", max_entries=24)
def forecast_route_alternatives(cfg):
    """Score candidate routes under the exact mission fault and physics settings."""
    network = Network.demo(cfg.memory_slots_per_node, cfg.noise_scale, 0.0,
                           cfg.link_fidelity_calibration, cfg.degraded_link_id,
                           cfg.failure_severity)
    controller = QNetOpsController()
    candidates = controller.paths(network, "A", "B")
    rows = []
    repetitions = 16
    for path in candidates:
        forecast = forecast_path_quality(network, path, cfg, repetitions=repetitions)
        nodes = ["A"]
        for edge in path:
            nodes.append(network.other(edge, nodes[-1]))
        slots_by_node = {node: 1 for node in nodes}
        for node in nodes[1:-1]:
            slots_by_node[node] += 1
        rows.append({
            "Candidate route": " → ".join(nodes),
            "Links": len(path),
            "Distance (km)": sum(edge.length_km for edge in path),
            "Forecast qualified": forecast["delivery_rate"],
            "Peak slots / node": max(slots_by_node.values(), default=0),
            "Mean latency (ms)": forecast["mean_success_latency_s"] * 1000,
            "Mean fidelity": forecast["mean_success_fidelity"],
            "Rollouts": repetitions,
        })
    return sorted(rows, key=lambda row: (row["Forecast qualified"], -row["Mean latency (ms)"],
                                         row["Mean fidelity"]), reverse=True)

results = load_results(config)
frame = pd.DataFrame(results)
summary = summarize(results)
adaptive = summary.loc[summary.policy == "Q-NetOps adaptive"].iloc[0]
static = summary.loc[summary.policy == "Static Dijkstra"].iloc[0]
mission_identity = hashlib.sha256(json.dumps({"scenario": scenario, "configuration": config.__dict__},
                                              sort_keys=True, default=str).encode()).hexdigest()[:16]
st.session_state.qnetops_last_mission_identity = mission_identity
analysis_timestamp_key = f"qnetops_analysis_timestamp_{mission_identity}"
if analysis_timestamp_key not in st.session_state:
    st.session_state[analysis_timestamp_key] = datetime.now(timezone.utc).isoformat(timespec="seconds")

@st.cache_data(show_spinner=False, max_entries=12)
def cached_mission_analysis(identity, _config, _results, _summary_rows, _scenario, _timestamp):
    """Reuse the debrief for a stable mission identity across page navigation."""
    return build_mission_analysis(_config, _results, _summary_rows, _scenario, timestamp=_timestamp)

mission_analysis = cached_mission_analysis(
    mission_identity, config, results, summary.to_dict(orient="records"), scenario,
    st.session_state[analysis_timestamp_key],
)
active_policy_name = st.session_state.get("qnetops_active_policy", "Q-NetOps adaptive")
active_policy_summary = summary.loc[summary.policy == active_policy_name].iloc[0]
chat_context = {
    "scenario": scenario,
    "policy": active_policy_name,
    "fault": {"link": fault_link, "severity": fault_severity if fault_link != "None" else 0},
    "request": st.session_state.get("qnetops_active_request", {}),
    "metrics": {
        "delivery_rate": float(active_policy_summary.success_rate),
        "mean_delivered_fidelity": (float(active_policy_summary.mean_delivered_fidelity)
                                    if pd.notna(active_policy_summary.mean_delivered_fidelity) else None),
    },
    "mission_analysis": mission_analysis,
}

home, head, status = st.columns([1.2, 2.8, 1], vertical_alignment="center")
with home:
    st.markdown("**Q / NETOPS**")
with head:
    st.caption("AUTONOMOUS QUANTUM NETWORK CONTROL · SHARED-NETWORK SIMULATION")
with status:
    st.badge("MISSION COMPLETE", icon=":material/check_circle:", color="orange")
    st.caption(f"{scenario} · seed {int(seed)}")

st.title(selected_page, anchor=False, icon=":material/hub:")
st.caption(PAGE_DESCRIPTIONS.get(selected_page, "Overview of the Q-NetOps quantum network operations prototype."))

if selected_page in ("Mission Simulation", "Reports & Analytics"):
    with st.container(horizontal=True):
        st.metric("Qualified delivery", f"{adaptive.success_rate:.1%}",
                  f"{adaptive.success_rate-static.success_rate:+.1%} vs static", border=True,
                  help="Share of adaptive requests delivered with the requested fidelity before their deadline.")
        delivered_f = adaptive.mean_delivered_fidelity
        static_delivered_f = static.mean_delivered_fidelity
        fidelity_delta = (f"{delivered_f-static_delivered_f:+.3f} vs static"
                          if pd.notna(delivered_f) and pd.notna(static_delivered_f) else None)
        st.metric("Delivered-pair fidelity", f"{delivered_f:.3f}" if pd.notna(delivered_f) else "—",
                  fidelity_delta, border=True, help="Mean fidelity for pairs delivered by the adaptive controller.")
        st.metric("Mean delivery time", f"{adaptive.mean_latency_s*1000:.1f} ms",
                  f"{(adaptive.mean_latency_s-static.mean_latency_s)*1000:+.1f} ms vs static", delta_color="inverse", border=True,
                  help="Mean request latency; lower is better.")
        st.metric("Memory occupancy", f"{adaptive.mean_memory_utilization:.1%}",
                  f"{adaptive.mean_memory_utilization-static.mean_memory_utilization:+.1%} vs static", delta_color="inverse", border=True,
                  help="Mean repeater-memory utilization; lower occupancy leaves more spare capacity.")
    st.caption(
        f"Active configuration · {scenario} · {requests} requests per policy · seed {int(seed)} · "
        f"target fidelity {target:.2f} · arrival pressure {load:.2f} · {capacity} memory slots per repeater · "
        f"{retries} retries · {deadline_ms} ms deadline"
    )

    with st.container(border=True):
        st.subheader("Mission Analyst · automatic debrief", anchor=False, icon=":material/analytics:")
        st.caption(f"{mission_analysis['scenario']} · seed {mission_analysis['seed']} · {mission_analysis['request_count']} adaptive requests · generated {mission_analysis['generated_at']}. All values below are completed simulator outputs unless marked as model estimates.")
        with st.container(border=True):
            st.markdown('<div class="qno-finding-title">Mission summary</div>', unsafe_allow_html=True)
            st.markdown(f"**Qualified delivery:** {mission_analysis['metrics']['qualified_deliveries']}/{mission_analysis['request_count']} ({mission_analysis['metrics']['qualified_delivery_rate']:.1%})")
            st.caption(mission_analysis["metrics"]["qualified_delivery_definition"])
        findings_col, bottleneck_col = st.columns(2)
        with findings_col:
            with st.container(border=True):
                st.markdown('<div class="qno-finding-title">Strengths</div>', unsafe_allow_html=True)
                for item in mission_analysis["strengths"]:
                    st.markdown(f"- {item}")
        with bottleneck_col:
            with st.container(border=True):
                st.markdown('<div class="qno-finding-title">Bottlenecks</div>', unsafe_allow_html=True)
                for item in mission_analysis["bottlenecks"]:
                    st.markdown(f"- {item}")
        with st.container(border=True):
            st.markdown('<div class="qno-finding-title">Recommended experiments</div>', unsafe_allow_html=True)
            for item in mission_analysis["recommendations"]:
                st.markdown(f"- {item}")
        with st.expander("Configuration, routes, decisions & failure evidence"):
            st.json({"configuration": mission_analysis["configuration"],
                     "adaptive_routes": mission_analysis["routes"],
                     "controller_actions": mission_analysis["controller_actions"],
                     "decision_rationales": mission_analysis["decision_rationales"],
                     "recorded_event_counts": mission_analysis["event_counts"],
                     "unqualified_requests": mission_analysis["failed_requests"],
                     "data_limitations": mission_analysis["limitations"]}, expanded=False)
        report_id = hashlib.sha256(json.dumps(mission_analysis, sort_keys=True, default=str).encode()).hexdigest()[:16]
        pdf_state_key = f"qnetops_mission_pdf_{report_id}"
        if st.button("Generate PDF report", icon=":material/picture_as_pdf:", key="generate_mission_pdf"):
            try:
                with st.spinner("Preparing the mission report…"):
                    st.session_state[pdf_state_key] = mission_pdf_download(mission_analysis)
                st.success("PDF report is ready to download.")
            except Exception as error:
                st.error(f"Could not generate the PDF report: {error}")
        if pdf_state_key in st.session_state:
            download = st.session_state[pdf_state_key]
            st.download_button("Download mission PDF", data=download["data"], file_name=download["file_name"],
                               mime=download["mime"], icon=":material/download:", key=f"download_mission_pdf_{report_id}")
        else:
            st.caption("The report uses this completed mission’s configuration, policy results, and recorded event trace; unavailable failure causes are labeled as such.")

def advance_trace_request(max_request: int):
    """Advance the replay selector before Streamlit instantiates it on rerun."""
    st.session_state.trace_request = st.session_state.get("trace_request", 1) % max_request + 1

if selected_page == "Network Control":
    control_view = st.radio(
        "Control workspace", ["Live control", "Deployment concepts"],
        horizontal=True, key="network_control_view",
    )

if selected_page == "Mission Simulation":
    st.subheader("Judge demo · controlled failure, adaptive response", anchor=False, icon=":material/movie:")
    st.caption("A guided walk-through of the same reproducible simulation used in the controller and policy comparison.")
    fault_summary = (f"{fault_link} · {fault_severity}% success-probability reduction" if fault_link != "None"
                     else "No link fault injected")
    st.info(f"Mission: **{scenario}** · seed **{int(seed)}** · {requests} requests per policy · {fault_summary}. All policies receive the same mission settings and seeded request arrivals.", icon=":material/science:")
    judge_stage = int(st.session_state.get("qnetops_judge_stage", 0))
    st.progress((judge_stage + 1) / 3, text=f"Demo beat {judge_stage + 1} of 3")
    if judge_stage == 0:
        st.markdown("#### 1 · Stress a real simulated link")
        if fault_link != "None":
            st.write(f"The mission degrades **{fault_link}** by {fault_severity}% in the Chennai test graph. This reduces its heralded generation probability for every policy; it is a controlled simulator fault, not a network outage.")
        else:
            st.write("No fault is active yet. Choose a link and severity in Mission setup, then submit the form to compare how each policy responds to the same controlled fault.")
    elif judge_stage == 1:
        st.markdown("#### 2 · Compare the controller response")
        comparison = summary.set_index("policy")
        static_rate = float(comparison.loc["Static Dijkstra", "success_rate"])
        adaptive_rate = float(comparison.loc["Q-NetOps adaptive", "success_rate"])
        adaptive_requests = frame[frame.policy == "Q-NetOps adaptive"]
        repairs = int(adaptive_requests.local_repairs.sum())
        preserved = int(adaptive_requests.preserved_segments.sum())
        refreshes = sum(event.get("kind") == "pair_refresh"
                        for events in adaptive_requests.events for event in events)
        st.write(f"Static Dijkstra delivered **{static_rate:.1%}** of requests; Q-NetOps adaptive delivered **{adaptive_rate:.1%}** under the same seeded mission. The adaptive run performed **{repairs} local repairs**, preserved **{preserved} reusable segments**, and made **{refreshes} fidelity-aware pair refreshes**. The route and request traces show the evidence behind these decisions.")
        metric_cols = st.columns(3)
        metric_cols[0].metric("Adaptive qualified delivery", f"{adaptive_rate:.1%}")
        metric_cols[1].metric("vs shortest-path baseline", f"{adaptive_rate-static_rate:+.1%}")
        metric_cols[2].metric("Faulted edge", f"{fault_link} · {fault_severity}%" if fault_link != "None" else "None")
    else:
        st.markdown("#### 3 · Inspect and reproduce")
        st.write("Use Network control to play through request events and inspect the route choice. Open Policy arena for the full policy leaderboard and export the mission report to reproduce this exact seed, fault, and parameter set.")
    previous_col, next_col, stop_col = st.columns([1, 1, 2])
    with previous_col:
        if st.button("Previous beat", disabled=judge_stage == 0, key="judge_previous"):
            st.session_state.qnetops_judge_stage = max(0, judge_stage - 1)
            st.rerun()
    with next_col:
        if st.button("Next beat", disabled=judge_stage == 2, type="primary", key="judge_next"):
            st.session_state.qnetops_judge_stage = min(2, judge_stage + 1)
            st.rerun()
    with stop_col:
        if st.button("Exit judge demo", key="judge_exit"):
            st.session_state.qnetops_judge_mode = False
            st.session_state.qnetops_judge_preset_applied = False
            st.rerun()

if selected_page == "Network Control" and st.session_state.get("network_control_view", "Live control") == "Live control":
    if "trace_playing" not in st.session_state:
        st.session_state.trace_playing = False
    play_col, note_col = st.columns([1, 4], vertical_alignment="center")
    with play_col:
        if st.button("Pause replay" if st.session_state.trace_playing else "Play event trace",
                     icon=":material/pause:" if st.session_state.trace_playing else ":material/play_arrow:",
                     type="primary" if not st.session_state.trace_playing else "secondary",
                     key="trace_playback_toggle"):
            st.session_state.trace_playing = not st.session_state.trace_playing
            st.rerun()
    with note_col:
        st.caption("Auto-advances the selected request through its recorded simulation events. You can still scrub the slider manually.")
    @st.fragment(run_every=0.8 if st.session_state.trace_playing else None)
    def render_live_control():
        controls, _ = st.columns([1,4])
        with controls:
            policy = st.segmented_control("Controller in focus", frame.policy.unique().tolist(),
                                          default="Q-NetOps adaptive", key="active_policy") or "Q-NetOps adaptive"
            policy_rows = frame[frame.policy == policy]
            if "trace_request" not in st.session_state:
                st.session_state.trace_request = 1
            max_request = int(policy_rows.request_id.max())
            st.session_state.trace_request = min(st.session_state.trace_request, max_request)
            request_id = st.selectbox("Replay request", policy_rows.request_id.tolist(), key="trace_request")
            st.button("Next request", icon=":material/skip_next:", width="stretch",
                      on_click=advance_trace_request, args=(max_request,))
        row = frame[(frame.policy == policy) & (frame.request_id == request_id)].iloc[0]
        st.session_state.qnetops_active_policy = policy
        st.session_state.qnetops_active_request = {
            "request_id": int(request_id), "path": str(row.path), "action": str(row.action),
            "reason": str(row.reason), "fidelity": float(row.fidelity), "delivered": bool(row.delivered),
        }
        event_records = row.events if isinstance(row.events, list) and row.events else [{
            "time_ms": 0.0, "kind": "summary", "message": row.reason, "action": row.action,
            "path": row.path, "edge": None, "fidelity": row.fidelity, "active_pairs": 0,
        }]
        event_key = f"event_{policy}_{request_id}"
        if st.session_state.trace_playing:
            current_event = int(st.session_state.get(event_key, 0))
            if current_event >= len(event_records) - 1:
                st.session_state.trace_playing = False
                st.rerun(scope="app")
            st.session_state[event_key] = current_event + 1
        event_index = st.slider("Replay the controller event", 0, len(event_records)-1, 0,
                                key=event_key, format="Event %d")
        replay_event = event_records[event_index]

        coords = {
            "A": (13.0100, 80.2350), "R1": (12.9866, 80.2430),
            "R2": (12.9705, 80.2525), "R3": (13.0150, 80.2810),
            "B": (13.0550, 80.2450),
        }
        labels = {"A":"IIT Madras-side gateway", "R1":"Research Park-side repeater",
                  "R2":"South metro repeater", "R3":"East metro repeater", "B":"North metro gateway"}
        network = Network.demo(capacity, noise, load, calibration,
                               config.degraded_link_id, config.failure_severity)
        memory_snapshot = replay_event.get("memory_slots_by_node", {})
        event_path = replay_event.get("path") or row.path
        path_nodes = event_path.split(" → ") if event_path != "unavailable" else []
        chosen_edges = {frozenset((a,b)) for a,b in zip(path_nodes,path_nodes[1:])}

        map_col, panel_col = st.columns([2.2,1], gap="medium")
        with map_col:
            with st.container(border=True):
                map_view = st.radio("Map view", ["India & Indian Ocean", "Chennai simulator"],
                                    horizontal=True, key="network_map_view")
                if map_view == "India & Indian Ocean":
                    st.subheader("Network geography · India & Indian Ocean", anchor=False, icon=":material/public:")
                    map_obj = folium.Map(location=[5, 80], zoom_start=4, tiles="OpenStreetMap",
                                         control_scale=True, prefer_canvas=True)
                    india_corridors = [corridor for corridor in CORRIDORS.values()
                                       if any(area in corridor["ocean"] for area in ("India", "Bay of Bengal", "Arabian Sea"))]
                    corridor_colors = ["#C6532D", "#A78459", "#766D60"]
                    for corridor_index, corridor in enumerate(india_corridors):
                        color = corridor_colors[corridor_index % len(corridor_colors)]
                        folium.PolyLine(corridor["coordinates"], color=color, weight=3.5,
                            opacity=.88, dash_array="8, 10",
                            tooltip=f"Concept route · {corridor['ocean']}").add_to(map_obj)
                        for waypoint_index, (name, point) in enumerate(zip(corridor["route"], corridor["coordinates"])):
                            folium.CircleMarker(point, radius=5.5, color="#FBF8F0", weight=2,
                                fill=True, fill_color=color, fill_opacity=.94,
                                tooltip=f"{name} · illustrative waypoint · {corridor['ocean']}").add_to(map_obj)
                    map_obj.fit_bounds([[-23, 38], [36, 108]], padding=(16, 16))
                    st_folium(map_obj, width=1200, height=570, key="qnetops_indian_overview",
                              returned_objects=[], use_container_width=True)
                    st.caption("Dashed routes and markers are geographic concepts across India and the Indian Ocean. They do not show verified fiber paths or deployed quantum repeaters. The controller’s measured replay remains the Chennai simulation; choose Chennai simulator to inspect its nodes and active path.")
                else:
                    st.subheader("Simulator topology · Chennai", anchor=False, icon=":material/route:")
                    map_obj = folium.Map(location=[13.015,80.255], zoom_start=11, tiles="OpenStreetMap",
                                         control_scale=True, prefer_canvas=True)
                    for edge in network.links:
                        p = .8*10**(-.2*edge.length_km/10)*(1-edge.noise)*(1-edge.demand_penalty)
                        key = frozenset((edge.u,edge.v))
                        faulted = edge.link_id == config.degraded_link_id
                        color = "#A64C32" if faulted else "#C6532D" if p >= .18 else "#A78459" if p >= .06 else "#766D60"
                        folium.PolyLine([coords[edge.u],coords[edge.v]], color=color,
                            weight=9 if faulted else 7 if edge.link_id == replay_event.get("edge") else 5 if key in chosen_edges else 2.4,
                            opacity=1 if edge.link_id == replay_event.get("edge") or key in chosen_edges else .68,
                            tooltip=(f"{edge.u} ↔ {edge.v} · {edge.length_km} km fiber · Pgen {p:.3f} · F0 {edge.base_fidelity:.2f}"
                                     + (f" · INJECTED FAULT −{fault_severity}%" if faulted else ""))).add_to(map_obj)
                    if len(path_nodes) > 1:
                        AntPath([coords[n] for n in path_nodes], color="#C6532D", pulse_color="#FBF8F0",
                                delay=650, dash_array=[13,20], weight=5, opacity=.95).add_to(map_obj)
                    for node, point in coords.items():
                        selected = node in path_nodes
                        used_slots = int(memory_snapshot.get(node, 0))
                        folium.CircleMarker(point, radius=10 if node in ("A","B") else 8,
                            color="#FBF8F0", weight=2, fill=True,
                            fill_color="#C6532D" if selected else "#766D60", fill_opacity=1,
                            tooltip=f"{labels[node]} · {node}",
                            popup=folium.Popup(f"<b>{labels[node]}</b><br>Node {node}<br>Memory: {used_slots}/{capacity} slots occupied · {capacity-used_slots} free", max_width=260)).add_to(map_obj)
                    map_event = st_folium(map_obj, width=1200, height=570, key="qnetops_leaflet",
                                          returned_objects=["last_object_clicked"], use_container_width=True)
                    st.caption("Synthetic five-node Chennai graph used by the simulator; it is not deployed infrastructure.")
                    clicked = (map_event or {}).get("last_object_clicked")
                    if clicked and "lat" in clicked and "lng" in clicked:
                        nearest = min(coords, key=lambda n: (coords[n][0]-clicked["lat"])**2+(coords[n][1]-clicked["lng"])**2)
                        st.toast(f"Inspected {labels[nearest]} · {nearest}", icon=":material/location_searching:")
        with panel_col:
            with st.container(border=True):
                st.subheader("Controller decision", anchor=False)
                color = "orange"
                st.badge(row.action, icon=":material/bolt:", color=color)
                st.space("small")
                st.metric("Chosen path", row.path)
                st.metric("End-to-end fidelity", f"{row.fidelity:.3f}",
                          "qualified" if row.delivered else "below service level",
                          delta_color="normal" if row.delivered else "inverse")
                st.metric("Generation attempts", int(row.generation_attempts),
                          f"{int(row.wasted_attempts)} wasted", delta_color="inverse")
                st.metric("Peak concurrent sessions", int(row.peak_concurrent_requests),
                          f"{int(row.memory_blocked_ticks)} blocked · {int(row.local_repairs)} local repairs · {int(row.preserved_segments)} segments kept")
                st.status("Decision rationale", state="complete", expanded=True).write(row.reason)
                if pd.notna(row.get("predicted_failure_risk")):
                    st.metric("Modeled failure risk", f"{float(row.predicted_failure_risk):.1%}",
                              "simulation estimate · not live telemetry", delta_color="inverse")
                candidates = row.get("decision_candidates", [])
                with st.expander("Digital twin · evaluated route futures", expanded=False):
                    st.caption("Read-only candidate scores use a snapshot of simulated memory and link state. The 64-rollout forecast is model output; actual delivery is reported separately.")
                    if isinstance(candidates, list) and candidates:
                        candidate_frame = pd.DataFrame(candidates)
                        columns = ["route", "feasible", "objective_score", "modeled_failure_risk",
                                   "route_reliability", "projected_fidelity", "estimated_latency_s",
                                   "memory_headroom", "forecast_delivery_rate"]
                        candidate_frame = candidate_frame[[column for column in columns
                                                           if column in candidate_frame.columns]]
                        if "objective_score" in candidate_frame:
                            candidate_frame["objective_score"] = candidate_frame.objective_score.map(lambda value: f"{value:.3f}")
                        for column in ("modeled_failure_risk", "route_reliability", "memory_headroom", "forecast_delivery_rate"):
                            if column in candidate_frame:
                                candidate_frame[column] = candidate_frame[column].map(
                                    lambda value: f"{value:.1%}" if pd.notna(value) else "—")
                        if "projected_fidelity" in candidate_frame:
                            candidate_frame["projected_fidelity"] = candidate_frame.projected_fidelity.map(lambda value: f"{value:.3f}")
                        if "estimated_latency_s" in candidate_frame:
                            candidate_frame["estimated_latency_s"] = candidate_frame.estimated_latency_s.map(lambda value: f"{value*1000:.1f} ms")
                        st.dataframe(candidate_frame, hide_index=True, width="stretch",
                                     alt="Digital-twin route candidate scores and predicted outcomes")
                    else:
                        st.caption("This controller does not produce adaptive route candidate forecasts.")
                st.caption(f"Request {request_id} of {max_request} · {policy}")
                with st.expander("Resource & entanglement state", expanded=False):
                    resource_rows = [{
                        "Node": node_id,
                        "Memory used": int(memory_snapshot.get(node_id, 0)),
                        "Capacity": int(capacity),
                        "Free": int(capacity) - int(memory_snapshot.get(node_id, 0)),
                    } for node_id in network.nodes]
                    st.dataframe(pd.DataFrame(resource_rows), hide_index=True,
                                 width="stretch", alt="Memory occupancy by repeater at the selected event")
                    stored_pairs = replay_event.get("stored_pairs", [])
                    if stored_pairs:
                        pair_frame = pd.DataFrame(stored_pairs).rename(columns={
                            "link": "Link", "age_ms": "Pair age (ms)", "fidelity": "Current fidelity",
                        })
                        st.dataframe(pair_frame, hide_index=True, width="stretch",
                                     alt="Stored entangled-pair age and decayed fidelity")
                    else:
                        st.caption("No completed elementary pairs are stored at this event.")
                if fault_link != "None":
                    st.warning(f"Fault active on {fault_link}: {fault_severity}% reduction to link-generation success probability. Shared by all policies in this mission.", icon=":material/bolt:")
                with st.expander("Route alternatives · Q-NetOps forecast", expanded=False):
                    st.caption("Independent 16-rollout estimates under the active mission settings. They explain route tradeoffs; the adaptive request-time decision uses its own 64-rollout forecast.")
                    alternative_rows = forecast_route_alternatives(config)
                    alternatives = pd.DataFrame(alternative_rows)
                    if not alternatives.empty:
                        alternatives.insert(0, "Observed request route", alternatives["Candidate route"].eq(str(row.path)))
                        alternatives["Forecast qualified"] = alternatives["Forecast qualified"].map(lambda value: f"{value:.0%}")
                        alternatives["Mean latency (ms)"] = alternatives["Mean latency (ms)"].map(lambda value: f"{value:.1f}")
                        alternatives["Mean fidelity"] = alternatives["Mean fidelity"].map(lambda value: f"{value:.3f}")
                        st.dataframe(alternatives, hide_index=True, width="stretch", alt="Forecasted route alternatives and tradeoffs")
        st.markdown(f"**Event {event_index+1}/{len(event_records)} · {replay_event['time_ms']:.2f} ms · {replay_event['kind'].replace('_', ' ').title()}**")
        st.write(replay_event["message"])
        event_frame = pd.DataFrame(event_records)
        event_frame.insert(0, "event", range(1, len(event_frame)+1))
        event_chart = px.scatter(event_frame, x="time_ms", y="event", color="kind", hover_data=["message", "action", "edge"],
            color_discrete_sequence=["#C6532D", "#A78459", "#766D60", "#A64C32", "#D1A98D"])
        event_chart.add_vline(x=replay_event["time_ms"], line_color="#C6532D", line_dash="dash")
        event_chart.update_layout(template="plotly_white", paper_bgcolor="#F5F1E6", plot_bgcolor="#FBF8F0",
            font=dict(color="#292824", family="Arial, sans-serif"),
            margin=dict(l=10,r=10,t=10,b=10), xaxis_title="Elapsed time from arrival (ms)", yaxis_title="Recorded event", legend_title="",
            xaxis=dict(gridcolor="#D8CEBC", zerolinecolor="#D8CEBC", linecolor="#D8CEBC"),
            yaxis=dict(gridcolor="#D8CEBC", zerolinecolor="#D8CEBC", linecolor="#D8CEBC"))
        st.plotly_chart(event_chart, width="stretch", theme="streamlit", key="mission_event_timeline")
        st.dataframe(event_frame[["event", "time_ms", "kind", "message", "action", "edge", "fidelity", "active_pairs"]],
                     hide_index=True, width="stretch", height=250, alt="Chronological controller event trace for the selected request")

    render_live_control()

if selected_page == "Network Control" and st.session_state.get("network_control_view") == "Deployment concepts":
    st.subheader("Where fidelity-aware network control could apply", anchor=False, icon=":material/public:")
    corridor_name = st.selectbox("Illustrative corridor", list(CORRIDORS))
    corridor = CORRIDORS[corridor_name]
    with st.container(border=True):
        st.markdown(f"**{corridor['ocean']} · {' → '.join(corridor['route'])}**")
        st.write(corridor["use"])
        st.warning("Geographic concept only. These markers and connecting lines do not represent deployed quantum repeaters, verified fiber routes, live traffic, or simulation results.", icon=":material/info:")
        center = [sum(point[0] for point in corridor["coordinates"])/len(corridor["coordinates"]),
                  sum(point[1] for point in corridor["coordinates"])/len(corridor["coordinates"])]
        concept_map = folium.Map(location=center, zoom_start=3, tiles="OpenStreetMap", control_scale=True, prefer_canvas=True)
        folium.PolyLine(corridor["coordinates"], color="#C6532D", weight=3, opacity=.88, dash_array="10, 12",
                        tooltip="Illustrative corridor · not a deployed link").add_to(concept_map)
        for index, (name, point) in enumerate(zip(corridor["route"], corridor["coordinates"])):
            folium.CircleMarker(point, radius=8, color="#FBF8F0", weight=2, fill=True,
                fill_color="#C6532D", fill_opacity=.96,
                tooltip=f"Concept waypoint {index+1}: {name}").add_to(concept_map)
            folium.Marker(point, tooltip=name).add_to(concept_map)
        st_folium(concept_map, width=1200, height=500, key=f"concept_{corridor_name}",
                  returned_objects=[], use_container_width=True)
    st.caption("India and ocean corridor maps broaden the geographic planning view; the network-control metrics still come from the separate five-node Chennai simulation.")

if selected_page == "Reports & Analytics":
    mission_report = json.dumps({
        "project": "Q-NetOps",
        "report_type": "reproducible synthetic-network mission",
        "network_scope": "five-node synthetic Chennai repeater graph; no live repeater telemetry",
        "configuration": config.__dict__,
        "policy_summary": json.loads(summary.to_json(orient="records")),
        "request_results_and_event_traces": json.loads(frame.to_json(orient="records")),
        "assumptions": [
            "All policies share the same seeded request arrivals and injected link fault.",
            "India and Indian Ocean corridors are illustrative geographic concepts, not deployed routes.",
            "Published BBM92 data, when selected, is static experimental calibration and not live telemetry.",
        ],
    }, indent=2)
    with st.container(border=True):
        report_col, download_col = st.columns([3, 1], vertical_alignment="center")
        with report_col:
            st.markdown("**Reproducible mission report**")
            st.caption("Includes the seed, model parameters, injected fault, policy metrics, and full per-request event traces.")
        with download_col:
            st.download_button("Download report", mission_report,
                               f"qnetops_mission_seed_{int(seed)}.json", "application/json",
                               icon=":material/download:", width="stretch", key="download_mission_report")
    st.subheader("Reliability through the run", anchor=False, icon=":material/show_chart:")
    rolling_rows = []
    for name, group in frame.groupby("policy"):
        group = group.sort_values("request_id")
        rate = group.delivered.astype(float).rolling(25, min_periods=5).mean()
        rolling_rows.extend({"request": int(rid), "delivery rate (25-request window)": val, "policy": name}
                            for rid,val in zip(group.request_id,rate) if pd.notna(val))
    reliability = pd.DataFrame(rolling_rows)
    line = px.line(reliability, x="request", y="delivery rate (25-request window)", color="policy",
        color_discrete_map={"Static Dijkstra":"#A78459","Greedy link quality":"#766D60","Q-NetOps adaptive":"#C6532D"})
    line.update_traces(line_width=2.7)
    line.add_hline(y=target, line_dash="dash", line_color="#766D60", annotation_text=f"Fidelity target {target:.2f}")
    line.update_layout(template="plotly_white",paper_bgcolor="#F5F1E6",plot_bgcolor="#FBF8F0",
        height=440, font=dict(color="#292824", family="IBM Plex Sans, Segoe UI, Arial, sans-serif", size=16),
        yaxis=dict(title="Qualified delivery rate", range=[0,1], tickformat=".0%", tickfont=dict(size=15),
                   gridcolor="#D8CEBC", zerolinecolor="#D8CEBC", linecolor="#D8CEBC"),
        xaxis=dict(title="Request sequence", tickfont=dict(size=15), gridcolor="#D8CEBC",
                   zerolinecolor="#D8CEBC", linecolor="#D8CEBC"),
        margin=dict(l=70,r=24,t=28,b=58),legend_title="",legend=dict(font=dict(size=15),orientation="h",y=1.08,x=0))
    st.plotly_chart(line, width="stretch", theme="streamlit", key="reliability_chart",
                    config={"displaylogo": False})
if selected_page == "Policy Arena":
    st.subheader("Controller leaderboard", anchor=False, icon=":material/trophy:")
    display = summary.sort_values("success_rate",ascending=False).copy()
    percent_columns = ["success_rate", "mean_memory_utilization", "fidelity_constraint_rate",
                       "request_expiration_rate", "mean_modeled_failure_risk", "recovery_success_rate"]
    for column in percent_columns:
        if column in display:
            display[column] = display[column].map(lambda value: f"{value:.1%}" if pd.notna(value) else "—")
    for column in ["mean_fidelity", "mean_delivered_fidelity"]:
        if column in display:
            display[column] = display[column].map(lambda value: f"{value:.3f}" if pd.notna(value) else "—")
    if "mean_latency_s" in display:
        display["mean_latency_s"] = display.mean_latency_s.map(lambda value:f"{value*1000:.1f} ms" if pd.notna(value) else "—")
    for column in ["mean_generation_attempts", "mean_wasted_attempts", "mean_repairs_per_repaired_request"]:
        if column in display:
            display[column] = display[column].map(lambda value:f"{value:.1f}" if pd.notna(value) else "—")
    if "mean_risk_calibration_gap" in display:
        display["mean_risk_calibration_gap"] = display.mean_risk_calibration_gap.map(
            lambda value:f"{value:+.3f}" if pd.notna(value) else "—")
    display = display.rename(columns={
        "policy": "Controller", "success_rate": "Qualified delivery", "mean_fidelity": "Mean fidelity",
        "mean_delivered_fidelity": "Delivered fidelity", "mean_latency_s": "Mean latency",
        "mean_memory_utilization": "Mean memory occupancy", "mean_generation_attempts": "Generation attempts",
        "mean_wasted_attempts": "Wasted attempts", "fidelity_constraint_rate": "Fidelity-qualified rate",
        "request_expiration_rate": "Request expiration", "mean_modeled_failure_risk": "Modeled failure risk",
        "mean_risk_calibration_gap": "Risk calibration gap", "recovery_success_rate": "Delivery rate after repair",
        "mean_repairs_per_repaired_request": "Repairs / repaired request",
    })
    st.dataframe(display, hide_index=True, width="stretch", alt="Controller leaderboard for the selected scenario")
    st.subheader("Shared network request log", anchor=False, icon=":material/receipt_long:")
    st.caption("Rows are independent sessions that shared link attempts and memory slots during the same simulated run.")
    log_columns = ["request_id", "arrival_s", "policy", "path", "delivered", "latency_s",
                   "peak_concurrent_requests", "memory_blocked_ticks", "reroutes",
                   "local_repairs", "preserved_segments", "wasted_attempts"]
    request_log = frame[log_columns].copy()
    request_log["arrival_s"] = request_log.arrival_s.map(lambda value: f"{value*1000:.1f} ms")
    request_log["latency_s"] = request_log.latency_s.map(lambda value: f"{value*1000:.1f} ms")
    request_log = request_log.rename(columns={
        "request_id": "Request", "arrival_s": "Arrival", "policy": "Controller", "path": "Selected route",
        "delivered": "Delivered", "latency_s": "Latency", "peak_concurrent_requests": "Peak concurrent requests",
        "memory_blocked_ticks": "Memory-blocked ticks", "reroutes": "Reroutes", "local_repairs": "Local repairs",
        "preserved_segments": "Preserved segments", "wasted_attempts": "Wasted attempts",
    })
    st.dataframe(request_log, hide_index=True, width="stretch", height=280,
                 alt="Request-level outcomes under shared network contention")
    st.download_button("Export trial data", frame.to_csv(index=False), "q_netops_results.csv", "text/csv",
                       icon=":material/download:")
    robustness_path = Path(__file__).parent / "benchmarks" / "robustness_summary.csv"
    if robustness_path.exists():
        robustness = pd.read_csv(robustness_path)
        st.subheader("Robustness across independent seeds", anchor=False, icon=":material/verified:")
        st.caption("Precomputed evaluation: 100 requests × 10 seeds per policy in each stress scenario. Error bars show 95% intervals across seed-level delivery rates.")
        robust_display = robustness[["scenario", "policy", "success_rate", "success_ci_low", "success_ci_high",
                                     "mean_delivered_fidelity", "mean_latency_s"]].copy()
        robust_display = robust_display.rename(columns={"scenario": "Scenario", "policy": "Controller",
            "success_rate": "Qualified delivery", "success_ci_low": "95% interval low",
            "success_ci_high": "95% interval high", "mean_delivered_fidelity": "Delivered fidelity",
            "mean_latency_s": "Mean latency"})
        for column in ["Qualified delivery", "95% interval low", "95% interval high"]:
            robust_display[column] = robust_display[column].map(lambda value: f"{value:.1%}")
        robust_display["Delivered fidelity"] = robust_display["Delivered fidelity"].map(
            lambda value: f"{value:.3f}" if pd.notna(value) else "—")
        robust_display["Mean latency"] = robust_display["Mean latency"].map(lambda value: f"{value*1000:.1f} ms")
        st.dataframe(robust_display, hide_index=True, width="stretch", alt="Multi-seed robustness benchmark results")
        st.download_button("Download robustness summary", robustness.to_csv(index=False),
                           "q_netops_robustness_summary.csv", "text/csv", icon=":material/download:")

if selected_page == "Model & Physics":
    st.subheader("Model assumptions", anchor=False, icon=":material/science:")
    st.markdown("The simulator runs overlapping requests against persistent repeater memories. The adaptive scheduler scores urgency, route completion, estimated delivery quality, generation success probability, and available memory headroom. Each fiber link allows one generation attempt at a time; completion includes round-trip fiber propagation and entangled pairs reserve memory until swap, expiry, or request deadline. Request arrivals use a seeded exponential process, and every policy sees the same arrival schedule.")
    st.markdown("When a link repeatedly fails, Q-NetOps replans around that section and carries forward still-valid pairs and in-flight attempts on links shared by both routes. Each stored pair is tracked by creation time and decayed fidelity. If a full route misses its fidelity target but refreshing one aging segment is forecast to recover the target within the deadline, only that segment is regenerated; otherwise the controller proceeds to swapping or normal expiry.")
    st.latex(r"P_{link}=P_0\,10^{-\alpha L/10},\qquad F(t)=0.25+(F_0-0.25)e^{-t/T_{coh}}")
    st.latex(r"F_{swap}=F_1F_2+\frac{(1-F_1)(1-F_2)}{3},\qquad P_{swap}=0.50")
    st.markdown(f"**Active scenario:** {scenario}  \n**Target fidelity:** {target:.2f}  ·  **Memory coherence:** {config.coherence_time_s*1000:.0f} ms  ·  **Purge floor:** {config.purge_fidelity:.2f}  ·  **Swap attempts:** {retries}  ·  **Request deadline:** {deadline_ms} ms")
    if calibration is not None:
        st.subheader("Experimental calibration", anchor=False, icon=":material/query_stats:")
        st.markdown(f"Using **{calibration_run}**: QBER {selected_measurement.qber:.1%}, pair rate {selected_measurement.pair_rate_cps:,.0f} pairs/s, optical loss {selected_measurement.loss_alice_db + selected_measurement.loss_bob_db:.1f} dB, detector dark counts {selected_measurement.dark_counts_alice_cps + selected_measurement.dark_counts_bob_cps:,.0f}/s combined.")
        st.metric("Inferred elementary-link fidelity", f"{measured_link_fidelity:.3f}", "derived from measured QBER")
        st.caption("Calibration proxy assumes symmetric Werner noise: F = 1 − 1.5 × QBER. The source experiment is an experimental BBM92 QKD link; these values calibrate the simulated elementary links and are not telemetry from the synthetic Chennai repeater topology.")
        st.dataframe(EXPERIMENT_DATA, hide_index=True, width="stretch")
        st.download_button("Download source measurements", EXPERIMENT_DATA.to_csv(index=False),
                           "bbm92_experiment_runs.csv", "text/csv", icon=":material/download:")
        st.markdown("Source: [Aliro Technologies experimental BBM92 dataset and analysis](https://github.com/aliro-technologies/realistic-quantum-network-simulation-for-bbm92).")
    st.warning("The adaptive policy combines deterministic route rollouts, current memory headroom, bounded rerouting after memory stalls, and least-slack scheduling. It is not a trained ML model. The experiment-derived calibration is static published data, not a live feed. The Chennai repeater topology is simulated; no public repeater-network telemetry endpoint is connected. IBM Quantum Open Plan offers free QPU circuit execution, but that is not a quantum repeater network and needs your own API key.", icon=":material/info:")

if selected_page == "IBM Quantum Hardware":
    st.subheader("Real IBM QPU · Bell-state validation", anchor=False, icon=":material/memory:")
    st.markdown("This prepares a two-qubit Bell state and measures X, Y, and Z correlations on IBM hardware. The three correlations give a Bell-state fidelity estimate from a real QPU job.")
    st.caption("Credentials stay on this machine. The app reads IBM_QUANTUM_API_KEY and optional IBM_QUANTUM_INSTANCE from .streamlit/secrets.toml or environment variables; it never displays the key.")
    api_key = os.getenv("IBM_QUANTUM_API_KEY", "")
    instance = os.getenv("IBM_QUANTUM_INSTANCE", "")
    try:
        api_key = api_key or st.secrets.get("IBM_QUANTUM_API_KEY", "")
        instance = instance or st.secrets.get("IBM_QUANTUM_INSTANCE", "")
    except Exception:
        pass

    if not api_key:
        st.info("Add your key to the local secrets file using the template at .streamlit/secrets.toml.example, then restart or refresh Streamlit. Do not paste the key into this chat or commit it.", icon=":material/key:")
    else:
        st.success("IBM API key found locally · Open Plan preferred · us-east", icon=":material/verified_user:")
        if instance:
            if st.button("Refresh IBM usage", icon=":material/refresh:"):
                with st.spinner("Reading account usage from IBM…"):
                    try:
                        from q_netops.engine.ibm_quantum import get_instance_usage
                        st.session_state.ibm_usage = get_instance_usage(api_key, instance)
                    except Exception as exc:
                        st.error(f"Could not read IBM usage: {exc}")
            usage = st.session_state.get("ibm_usage")
            if usage:
                used = float(usage.get("usage_consumed_seconds", 0) or 0)
                limit = float(usage.get("usage_limit_seconds", 600) or 600)
                remain = max(0, limit - used)
                u1, u2, u3 = st.columns(3)
                u1.metric("Open Plan time used", f"{used/60:.2f} min")
                u2.metric("Remaining this window", f"{remain/60:.2f} min")
                u3.metric("Usage limit reached", "Yes" if usage.get("usage_limit_reached") else "No")
                st.caption(f"Usage period resets: {usage.get('time_available_at', 'not reported')} · Refresh to update.")
        else:
            st.info("Add your IBM instance CRN to show usage totals.")
        if st.button("Find available QPUs", type="primary", icon=":material/search:"):
            with st.spinner("Checking IBM Quantum backends…"):
                try:
                    from q_netops.engine.ibm_quantum import list_qpus
                    st.session_state.ibm_backends = list_qpus(api_key, instance or None)
                    if not st.session_state.ibm_backends:
                        st.warning("No operational two-qubit QPU is currently available for this instance.")
                except Exception as exc:
                    st.error(f"IBM connection failed: {exc}")
        backends = st.session_state.get("ibm_backends", [])
        if backends:
            backend_by_name = {item["name"]: item for item in backends}
            backend_name = st.selectbox("Choose a real QPU", list(backend_by_name))
            st.caption(f"{backend_by_name[backend_name]['qubits']} qubits · backend availability can change while jobs queue.")
            shots = st.select_slider("Shots per measurement basis", options=[128, 256, 512], value=256)
            if st.button("Run Bell tomography on QPU", type="primary", icon=":material/rocket_launch:"):
                with st.spinner("Submitting job and waiting for hardware results…"):
                    try:
                        from q_netops.engine.ibm_quantum import run_bell_tomography
                        job_result = run_bell_tomography(api_key, backend_name, shots, instance or None)
                        st.session_state.ibm_tomography_result = job_result
                    except Exception as exc:
                        st.error(f"IBM job failed: {exc}")
            job_result = st.session_state.get("ibm_tomography_result")
            if job_result:
                st.badge(f"{job_result['status']} · {job_result['backend']}", icon=":material/check_circle:", color="orange")
                correlations = job_result["correlations"]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Bell fidelity estimate", f"{job_result['bell_fidelity']:.3f}")
                m2.metric("X correlation", f"{correlations['X']:+.3f}")
                m3.metric("Y correlation", f"{correlations['Y']:+.3f}")
                m4.metric("Z correlation", f"{correlations['Z']:+.3f}")
                st.caption(f"{job_result['shots_per_basis']:,} shots per basis · {job_result['shots_per_basis'] * 3:,} total shots · job {job_result['job_id']}")
                count_frame = pd.DataFrame(job_result["counts"]).fillna(0).astype(int)
                st.bar_chart(count_frame, color=["#C6532D", "#A78459", "#766D60"])
                st.caption("The estimate uses FΦ+ = (1 + ⟨XX⟩ − ⟨YY⟩ + ⟨ZZ⟩)/4. It characterizes the on-chip circuit and readout under current hardware noise; it does not estimate fiber-link fidelity or validate the simulated repeater route.")

if selected_page == "Reports & Analytics":
    st.subheader("Mission Analyst", anchor=False, icon=":material/analytics:")
    st.caption("Ask about this completed mission. Answers use its actual policy results and recorded adaptive events; forecasts are identified as estimates.")
    suggested = st.columns(4)
    suggested_questions = ["Why did requests fail?", "Which routes did adaptive control choose?",
                          "How did adaptive compare with static?", "What should we test next?"]
    for index, question in enumerate(suggested_questions):
        if suggested[index].button(question, key=f"analyst_suggestion_{index}", width="stretch"):
            st.session_state.setdefault("qnetops_chat", []).append({"role": "user", "content": question})
            st.session_state.qnetops_chat.append({"role": "assistant", "content": answer_question(question, {"mission_analysis": mission_analysis})})
            st.rerun()
    for message in st.session_state.get("qnetops_chat", [])[-8:]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    with st.form("mission_analyst_question_form", clear_on_submit=True):
        analyst_question = st.text_input("Ask about this mission", placeholder="Ask about a route, failure, fidelity, memory, or baseline…", max_chars=1000)
        analyst_submit = st.form_submit_button("Ask Mission Analyst", icon=":material/send:", type="primary")
    if analyst_submit and analyst_question.strip():
        st.session_state.setdefault("qnetops_chat", []).append({"role": "user", "content": analyst_question.strip()})
        st.session_state.qnetops_chat.append({"role": "assistant", "content": answer_question(analyst_question.strip(), {"mission_analysis": mission_analysis})})
        st.rerun()
if selected_page == "Settings & Help":
    st.subheader("Help & user guide", anchor=False, icon=":material/help:")
    st.caption("The Ask Q-NetOps button stays in the lower-right corner on every view. It uses a local, context-aware help service; no external LLM call is made.")
    st.markdown("#### Run a mission")
    st.markdown("1. Open **Mission Simulation**, set the stress scenario, quality target, traffic, memory, retries, deadline, seed, calibration, and any injected link fault in the sidebar, then submit **Run this mission**.\n2. The guided demo walks through the same reproducible mission; use its Previous and Next controls to compare the fault, controller response, and recorded evidence.\n3. Open **Reports & Analytics** for the automatic debrief, grounded Mission Analyst follow-up, PDF, and reproducible JSON report.\n4. Open **Network Control** to select a controller and request, play or scrub its event trace, inspect memory and route forecasts, and switch between the Chennai simulator and illustrative corridor maps.\n5. Use **Policy Arena** for rolling reliability, the full controller leaderboard, request-level contention outcomes, and multi-seed robustness results. **Model & Physics** documents the simulation assumptions; **IBM Quantum Hardware** handles optional QPU validation.")
    st.markdown("#### What the help chat can explain")
    st.markdown("Ask about routes and controller decisions, fidelity and thresholds, latency and memory metrics, injected faults, route alternatives, reproducible reports, the local API, or IBM QPU validation. The assistant uses documented simulator behavior and the active mission context when available.")
    st.caption("Local API docs: http://127.0.0.1:8000/docs · the dashboard chat also works without the API process.")

render_help_widget(chat_context)
