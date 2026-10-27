"""JARVIS Streamlit frontend. Run from the project root:  streamlit run frontend/app.py"""
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from jarvis.brain import Brain  # noqa: E402

st.set_page_config(page_title="J.A.R.V.I.S.", page_icon="🔵", layout="wide")

CSS = """
<style>
:root { --cyan:#00d9ff; --bg:#050b14; --panel:rgba(0,217,255,.06); --line:rgba(0,217,255,.28); }
.stApp { background: radial-gradient(circle at 50% 0%, #0b1d33 0%, var(--bg) 60%); color:#cfefff; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background:#07101c; border-right:1px solid var(--line); }
h1,h2,h3 { color:var(--cyan); letter-spacing:.2em; font-weight:300; }
.hud-title { text-align:center; color:var(--cyan); letter-spacing:.6em; font-size:1.6rem; font-weight:200;
  text-shadow:0 0 18px var(--cyan); margin:0; }
.hud-sub { text-align:center; color:#5fa8bd; letter-spacing:.3em; font-size:.7rem; margin-bottom:.5rem; }
.reactor { width:120px; height:120px; margin:.6rem auto 1rem; border-radius:50%;
  border:2px solid var(--cyan); position:relative;
  box-shadow:0 0 30px var(--cyan), inset 0 0 30px rgba(0,217,255,.5);
  animation:pulse 3s ease-in-out infinite; }
.reactor::before { content:""; position:absolute; inset:14px; border-radius:50%;
  border:2px dashed var(--cyan); animation:spin 12s linear infinite; }
.reactor::after { content:""; position:absolute; inset:38px; border-radius:50%;
  background:radial-gradient(circle,#fff 0%,var(--cyan) 55%,transparent 75%); }
.reactor.busy { animation:pulse .7s ease-in-out infinite; }
.reactor.busy::before { animation-duration:2s; }
@keyframes spin { to { transform:rotate(360deg); } }
@keyframes pulse { 50% { box-shadow:0 0 55px var(--cyan), inset 0 0 40px rgba(0,217,255,.8); } }
[data-testid="stChatMessage"] { background:var(--panel); border:1px solid var(--line); border-radius:10px; }
[data-testid="stChatInput"] { border:1px solid var(--line); border-radius:10px; }
.stButton>button { background:transparent; color:var(--cyan); border:1px solid var(--line); border-radius:8px; }
.stButton>button:hover { background:var(--panel); border-color:var(--cyan); box-shadow:0 0 12px var(--line); color:#fff; }
.tool-chip { display:inline-block; border:1px solid var(--line); border-radius:6px; padding:1px 8px;
  margin:2px; font-size:.72rem; color:#8fdcf0; font-family:monospace; }
.status-dot { color:#2dff8a; text-shadow:0 0 8px #2dff8a; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner="Initialising JARVIS systems...")
def get_brain() -> Brain:
    return Brain()


def speak(text: str) -> None:
    """Speak on the PC in the background so the UI doesn't block."""
    from jarvis.io.tts import Speaker

    threading.Thread(target=Speaker().say, args=(text,), daemon=True).start()


def listen_once() -> str | None:
    from jarvis.io.stt import Listener

    return Listener().listen()


class WakeService:
    """Background 'hey jarvis' loop: wake word -> listen -> queue the heard text for the UI."""

    def __init__(self):
        self.heard: queue.Queue[str] = queue.Queue()
        self.enabled = threading.Event()
        self.status = "off"
        self.error: str | None = None
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            from jarvis.io.stt import Listener
            from jarvis.io.wake import WakeWord

            wake, listener = WakeWord(), Listener()
        except Exception as e:
            self.error = str(e)
            return
        while True:
            self.enabled.wait()
            self.status = "waiting"
            if not wake.wait(should_stop=lambda: not self.enabled.is_set()):
                self.status = "off"
                continue
            self.status = "listening"
            heard = listener.listen()
            if heard:
                self.heard.put(heard)


@st.cache_resource
def get_wake() -> WakeService:
    return WakeService()


try:
    brain = get_brain()
except Exception as e:
    st.error(f"JARVIS failed to start: {e}")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Online and at your service.", "time": datetime.now()}
    ]
if "pending" not in st.session_state:
    st.session_state.pending = None

# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("### SYSTEMS")
    st.markdown('<span class="status-dot">●</span> Core online', unsafe_allow_html=True)
    st.caption(datetime.now().strftime("%A %d %B %Y"))

    voice_out = st.toggle("Speak replies", value=False)
    wake_on = st.toggle('Wake word ("Hey JARVIS")', value=True)
    wake = get_wake()
    if wake_on:
        wake.enabled.set()
    else:
        wake.enabled.clear()

    @st.fragment(run_every=1)
    def wake_poller():
        if wake.error:
            st.caption(f"Wake word unavailable: {wake.error}")
            return
        if wake_on:
            st.caption("Listening..." if wake.status == "listening" else 'Say "Hey JARVIS"')
        try:
            heard = wake.heard.get_nowait()
        except queue.Empty:
            return
        st.session_state.pending = heard
        st.rerun()

    wake_poller()

    st.markdown("### MODULES")
    for module, tool_names in brain.modules().items():
        names = "".join(f'<span class="tool-chip">{name}</span>' for name in tool_names)
        with st.expander(module.upper()):
            st.markdown(names, unsafe_allow_html=True)

    st.markdown("### QUICK ACTIONS")
    quick = {
        "What's on my calendar today?": "What's on my calendar today?",
        "Play something focused": "Play some music to help me focus",
        "What time is it?": "What time is it?",
        "Latest news": "Give me the latest news headlines",
    }
    for label, prompt in quick.items():
        if st.button(label, use_container_width=True):
            st.session_state.pending = prompt

    st.markdown("---")
    if st.button("Clear conversation", use_container_width=True):
        get_brain.clear()
        st.session_state.pop("messages")
        st.rerun()

# ---------------- main ----------------
st.markdown('<p class="hud-title">J.A.R.V.I.S.</p>', unsafe_allow_html=True)
st.markdown('<p class="hud-sub">JUST A RATHER VERY INTELLIGENT SYSTEM</p>', unsafe_allow_html=True)
reactor = st.empty()
reactor.markdown('<div class="reactor"></div>', unsafe_allow_html=True)

_, mic_col, _ = st.columns([2, 1, 2])
with mic_col:
    if st.button("🎙 Speak", use_container_width=True):
        with st.spinner("Listening..."):
            heard = listen_once()
        if heard:
            st.session_state.pending = heard
        else:
            st.toast("Didn't catch that.")

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🔵" if m["role"] == "assistant" else None):
        st.write(m["content"])
        st.caption(m["time"].strftime("%H:%M"))

typed = st.chat_input("Ask JARVIS anything...")
prompt = typed or st.session_state.pending
st.session_state.pending = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "time": datetime.now()})
    with st.chat_message("user"):
        st.write(prompt)
    reactor.markdown('<div class="reactor busy"></div>', unsafe_allow_html=True)
    with st.chat_message("assistant", avatar="🔵"):
        with st.spinner("Processing..."):
            reply = brain.ask(prompt)
        st.write(reply)
    reactor.markdown('<div class="reactor"></div>', unsafe_allow_html=True)
    st.session_state.messages.append({"role": "assistant", "content": reply, "time": datetime.now()})
    if voice_out:
        speak(reply)
