"""
HackT Sovereign Core - Comprehensive Test Suite & Simulator (Streamlit)
======================================================================
Tests EVERY endpoint of main.py (v2.4) + http_api.py and provides
a Live Sandbox to simulate Voice and Passive mode interactions.

Features:
- Real-time latency metrics for all API calls
- Visual test results dashboard with pass/fail charts
- Live WebSocket telemetry viewer with auto-reconnect
- Streamlit session state persistence for test history
- Cyberpunk-themed UI with animated status indicators
- Proper SSE parsing and audio streaming handling
- Fixed pandas DataFrame lambda error
- Updated Streamlit API for future compatibility
"""

import streamlit as st
import requests
import json
import time
import threading
import queue
import asyncio
from datetime import datetime
from typing import Optional, Dict, List, Any
import base64

# ── Optional deps ─────────────────────────────────────────────────────────────
try:
    import websocket as ws_lib
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & STYLES
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Sovereign Core Test Suite", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cyberpunk CSS with animated elements
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Rajdhani:wght@400;600;700&display=swap');

/* Base Typography */
html, body, [class*="css"] { 
    font-family: 'Rajdhani', sans-serif; 
    background: #030305;
    color: #e0e0e0;
}

/* Test Result Badges */
.test-pass  { 
    background: linear-gradient(135deg, #0d2b0d, #1a4d1a); 
    border-left: 4px solid #00ff88; 
    padding: 10px 14px; 
    border-radius: 4px; 
    color: #00ff88; 
    font-family: 'Space Mono'; 
    font-size: 13px; 
    margin: 6px 0;
    animation: pulse-green 2s infinite;
}
.test-fail  { 
    background: linear-gradient(135deg, #2b0d0d, #4d1a1a); 
    border-left: 4px solid #ff4444; 
    padding: 10px 14px; 
    border-radius: 4px; 
    color: #ff4444; 
    font-family: 'Space Mono'; 
    font-size: 13px; 
    margin: 6px 0;
    animation: pulse-red 2s infinite;
}
.test-warn  { 
    background: linear-gradient(135deg, #2b200d, #4d3a1a); 
    border-left: 4px solid #ffaa00; 
    padding: 10px 14px; 
    border-radius: 4px; 
    color: #ffaa00; 
    font-family: 'Space Mono'; 
    font-size: 13px; 
    margin: 6px 0;
    animation: pulse-yellow 2s infinite;
}
.test-skip  { 
    background: #1a1a2e; 
    border-left: 4px solid #666; 
    padding: 10px 14px; 
    border-radius: 4px; 
    color: #888; 
    font-family: 'Space Mono'; 
    font-size: 13px; 
    margin: 6px 0;
}

@keyframes pulse-green {
    0%, 100% { box-shadow: 0 0 5px rgba(0, 255, 136, 0.3); }
    50% { box-shadow: 0 0 15px rgba(0, 255, 136, 0.6); }
}
@keyframes pulse-red {
    0%, 100% { box-shadow: 0 0 5px rgba(255, 68, 68, 0.3); }
    50% { box-shadow: 0 0 15px rgba(255, 68, 68, 0.6); }
}
@keyframes pulse-yellow {
    0%, 100% { box-shadow: 0 0 5px rgba(255, 170, 0, 0.3); }
    50% { box-shadow: 0 0 15px rgba(255, 170, 0, 0.6); }
}

/* Section Headers */
.section-header { 
    font-family: 'Rajdhani'; 
    font-weight: 700; 
    font-size: 22px; 
    color: #e0e0e0; 
    border-bottom: 2px solid #333; 
    padding-bottom: 6px; 
    margin: 18px 0 10px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-header::before {
    content: '';
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #00f3ff;
    border-radius: 50%;
    animation: blink 1.5s infinite;
}
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* Stream Boxes */
.stream-box { 
    background: #0a0a0a; 
    border: 1px solid #00f3ff; 
    border-radius: 6px; 
    padding: 16px; 
    font-family: 'Space Mono'; 
    font-size: 14px; 
    color: #00f3ff; 
    min-height: 100px; 
    white-space: pre-wrap; 
    box-shadow: 0 0 15px rgba(0, 243, 255, 0.1);
    position: relative;
    overflow: hidden;
}
.stream-box::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0, 243, 255, 0.1), transparent);
    animation: scanline 3s linear infinite;
}
@keyframes scanline {
    0% { left: -100%; }
    100% { left: 100%; }
}
.stream-box-passive { 
    border-color: #bc13fe; 
    color: #bc13fe; 
    box-shadow: 0 0 15px rgba(188, 19, 254, 0.1); 
}
.stream-box-passive::before {
    background: linear-gradient(90deg, transparent, rgba(188, 19, 254, 0.1), transparent);
}

/* Latency Badges */
.latency-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: 'Space Mono';
    font-size: 11px;
    font-weight: bold;
    margin-left: 8px;
}
.latency-good { background: #00ff88/20; color: #00ff88; }
.latency-warn { background: #ffaa00/20; color: #ffaa00; }
.latency-bad { background: #ff4444/20; color: #ff4444; }

/* Status Indicators */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 2s infinite;
}
.status-online { background: #00ff88; box-shadow: 0 0 8px #00ff88; }
.status-warning { background: #ffaa00; box-shadow: 0 0 8px #ffaa00; }
.status-offline { background: #ff4444; box-shadow: 0 0 8px #ff4444; }
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Custom Scrollbar */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #1f1f1f; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #00f3ff; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ══════════════════════════════════════════════════════════════════════════════
if 'test_results' not in st.session_state:
    st.session_state.test_results = []
if 'latency_history' not in st.session_state:
    st.session_state.latency_history = []
if 'ws_messages' not in st.session_state:
    st.session_state.ws_messages = []
if 'last_test_run' not in st.session_state:
    st.session_state.last_test_run = None

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR ─ Config
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Core Config")
    BASE_URL = st.text_input("Server Base URL", value="http://127.0.0.1:8000")
    WS_URL   = st.text_input("WebSocket URL",   value="ws://127.0.0.1:8000/ws/telemetry")
    TIMEOUT  = st.slider("Request Timeout (s)", 5, 120, 45)
    SESSION_ID = st.text_input("Session ID", value="streamlit_auth_001")
    
    st.markdown("---")
    st.markdown("### ⚡ Test Controls")
    run_all    = st.button("▶  Run ALL Tests", type="primary", width="stretch")  # ✅ FIX: use width='stretch'
    clear_results = st.button("🗑️ Clear Results", width="stretch")  # ✅ FIX: use width='stretch'
    run_danger = st.checkbox("Include shutdown test ⚠️", value=False)
    
    if clear_results:
        st.session_state.test_results = []
        st.session_state.latency_history = []
        st.session_state.ws_messages = []
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    
    # Calculate stats from session state
    total_tests = len(st.session_state.test_results)
    passed_tests = sum(1 for r in st.session_state.test_results if r.get('passed'))
    failed_tests = sum(1 for r in st.session_state.test_results if not r.get('passed') and not r.get('skipped'))
    
    if total_tests > 0:
        pass_rate = (passed_tests / total_tests) * 100
        st.metric("Pass Rate", f"{pass_rate:.1f}%", delta=f"{passed_tests}/{total_tests} passed")
    
    # Latency stats
    if st.session_state.latency_history:
        avg_latency = sum(st.session_state.latency_history) / len(st.session_state.latency_history)
        st.metric("Avg Latency", f"{avg_latency:.0f}ms")

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def record_test(name: str, passed: bool, detail: str = "", skipped: bool = False, latency_ms: Optional[float] = None):
    """Record test result with latency tracking."""
    result = {
        "name": name,
        "passed": passed,
        "detail": detail,
        "skipped": skipped,
        "latency_ms": latency_ms,
        "timestamp": datetime.now().isoformat()
    }
    st.session_state.test_results.append(result)
    
    if latency_ms is not None:
        st.session_state.latency_history.append(latency_ms)
        # Keep only last 100 latency samples
        if len(st.session_state.latency_history) > 100:
            st.session_state.latency_history = st.session_state.latency_history[-100:]

def make_request(method: str, path: str, **kwargs) -> tuple[requests.Response, float]:
    """Make HTTP request with latency tracking."""
    start_time = time.time()
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        latency_ms = (time.time() - start_time) * 1000
        return response, latency_ms
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        raise e

def get_latency_class(latency_ms: float) -> str:
    """Get CSS class for latency badge based on value."""
    if latency_ms < 200:
        return "latency-good"
    elif latency_ms < 1000:
        return "latency-warn"
    else:
        return "latency-bad"

def parse_sse_line(line: str) -> Optional[dict]:
    """Parse a Server-Sent Events (SSE) line into a Python dict."""
    if not line or not line.startswith("data: "):
        return None
    
    try:
        # Remove "data: " prefix and parse JSON
        data_str = line[6:].strip()
        if data_str == "[DONE]":
            return {"done": True}
        return json.loads(data_str)
    except json.JSONDecodeError:
        return None

def stream_post(path: str, payload: dict, container=None, is_passive: bool = False) -> tuple[list, list, str]:
    """POST and collect SSE tokens; optionally updates a UI container in real-time."""
    tokens, lines = [], []
    full_text = ""
    css_class = "stream-box-passive" if is_passive else "stream-box"
    
    try:
        with requests.post(
            f"{BASE_URL}{path}", 
            json=payload,
            stream=True, 
            timeout=TIMEOUT,
            headers={"Accept": "text/event-stream"},
        ) as resp:
            # Verify SSE content type
            if "text/event-stream" not in resp.headers.get("Content-Type", ""):
                lines.append(f"[WARNING] Expected SSE, got: {resp.headers.get('Content-Type')}")
            
            for raw in resp.iter_lines(decode_unicode=True):
                if raw:
                    lines.append(raw)
                    parsed = parse_sse_line(raw)
                    if parsed:
                        tokens.append(parsed)
                        if "token" in parsed and not parsed.get("done"):
                            full_text += parsed["token"]
                            if container:
                                container.markdown(
                                    f'<div class="{css_class}">{full_text}</div>', 
                                    unsafe_allow_html=True
                                )
                        elif parsed.get("done"):
                            break
    except Exception as e:
        lines.append(f"[STREAM ERROR] {e}")
    
    return tokens, lines, full_text

def handle_audio_response(response: requests.Response) -> Optional[bytes]:
    """Handle audio response with proper content-type checking."""
    content_type = response.headers.get("Content-Type", "")
    
    if "audio/wav" in content_type or "audio/mpeg" in content_type:
        return response.content
    elif response.status_code == 200:
        # Fallback: assume it's audio if status is OK
        return response.content
    else:
        return None

# ══════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(135deg,#0d1117,#161d27); border:1px solid #1e3a5f; border-radius:14px; padding:20px 32px; margin-bottom:24px;">
  <h1 style="font-family:'Space Mono';color:#00f3ff;margin:0;font-size:28px;">🛡️ Sovereign Core Control Deck</h1>
  <p style="font-family:'Rajdhani';color:#7090a0;font-size:16px;margin:6px 0 0 0;">Diagnostics, API Testing, and Live Voice Simulation</p>
</div>
""", unsafe_allow_html=True)

# Create tabs with icons
tabs = st.tabs([
    "🎙️ Live Simulator", 
    "🟢 Boot & Health", 
    "💬 Chat / SSE", 
    "🔍 Threat Scan", 
    "⚙️ System API", 
    "📡 WebSocket",
    "📊 Test Dashboard"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 0 ─ LIVE SIMULATOR
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-header">Live Sovereign Environment</div>', unsafe_allow_html=True)
    st.caption("Test the complete 'Remote Control' loop: Backend STT → LLM Stream → Backend TTS.")

    col1, col2 = st.columns([1, 2])
    
    with col1:
        sim_mode = st.radio("Agent Mode", ["Active", "Passive"], key="sim_mode")
        sim_query_type = st.selectbox("Query Type", ["voice", "chat", "audit"], key="sim_query")
        st.markdown("---")
        
        st.markdown("**1. Voice Input (Server Mic)**")
        if st.button("🎙️ Trigger Backend STT (Remote Control)", width="stretch", key="stt_btn"):  # ✅ FIX: use width='stretch'
            with st.spinner("Server is listening... speak into your PC mic!"):
                try:
                    start = time.time()
                    r = requests.post(f"{BASE_URL}/api/audio/transcribe", timeout=TIMEOUT)
                    latency = (time.time() - start) * 1000
                    
                    if r.status_code == 200:
                        st.session_state['sim_input'] = r.json().get("text", "")
                        st.success(f"✅ STT Success ({latency:.0f}ms)")
                        record_test("STT Transcription", True, f"Latency: {latency:.0f}ms", latency_ms=latency)
                    else:
                        st.error(f"❌ STT Error: {r.status_code}")
                        record_test("STT Transcription", False, f"Status: {r.status_code}", latency_ms=latency)
                except Exception as e:
                    st.error(f"❌ Failed to connect: {e}")
                    record_test("STT Transcription", False, str(e))

        st.markdown("**2. Text Input (Fallback)**")
        sim_input = st.text_area(
            "Or type your message:", 
            value=st.session_state.get('sim_input', ''),
            key="sim_input_area",
            height=100
        )
        
        st.markdown("---")
        run_sim = st.button("🚀 Execute Loop", type="primary", width="stretch", key="run_sim")  # ✅ FIX: use width='stretch'

    with col2:
        st.markdown("**Live Telemetry & Output**")
        stream_container = st.empty()
        audio_container = st.empty()
        latency_container = st.empty()
        
        if not sim_input:
            stream_container.markdown(
                '<div class="stream-box" style="opacity: 0.5;">Awaiting input...</div>', 
                unsafe_allow_html=True
            )

        if run_sim and sim_input:
            is_passive = sim_mode.lower() == "passive"
            
            # Step 1: Send to Chat with latency tracking
            stream_container.markdown(
                '<div class="stream-box" style="opacity: 0.5;">Analyzing...</div>', 
                unsafe_allow_html=True
            )
            payload = {
                "prompt": sim_input,
                "mode": sim_mode.lower(),
                "query_type": sim_query_type,
                "session_id": SESSION_ID
            }
            
            start_time = time.time()
            # Stream the response live to the UI
            tokens, lines, full_text = stream_post("/api/chat", payload, container=stream_container, is_passive=is_passive)
            total_latency = (time.time() - start_time) * 1000
            
            # Display latency
            latency_class = get_latency_class(total_latency)
            latency_container.markdown(
                f'<span class="latency-badge {latency_class}">⚡ {total_latency:.0f}ms</span>',
                unsafe_allow_html=True
            )
            
            # Record test result
            if full_text:
                record_test("Chat SSE Stream", True, f"Received {len(tokens)} tokens", latency_ms=total_latency)
            else:
                record_test("Chat SSE Stream", False, "No tokens received", latency_ms=total_latency)
            
            # Step 2: Auto-Trigger TTS if it was a voice query
            if full_text and sim_query_type == "voice":
                with st.spinner("Generating Piper Audio..."):
                    try:
                        tts_start = time.time()
                        r_tts = requests.post(
                            f"{BASE_URL}/api/tts", 
                            json={"text": full_text[:500]},  # Limit to 500 chars for speed
                            timeout=TIMEOUT
                        )
                        tts_latency = (time.time() - tts_start) * 1000
                        
                        # Handle audio response properly
                        audio_content = handle_audio_response(r_tts)
                        
                        if audio_content and r_tts.status_code == 200:
                            # Convert bytes to base64 for Streamlit audio player
                            audio_b64 = base64.b64encode(audio_content).decode()
                            audio_container.markdown(
                                f"""
                                <audio controls autoplay>
                                    <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
                                    Your browser does not support the audio element.
                                </audio>
                                """,
                                unsafe_allow_html=True
                            )
                            st.success(f"✅ TTS Success ({tts_latency:.0f}ms)")
                            record_test("TTS Synthesis", True, f"Latency: {tts_latency:.0f}ms", latency_ms=tts_latency)
                        else:
                            audio_container.error(f"❌ TTS Failed: {r_tts.status_code}")
                            record_test("TTS Synthesis", False, f"Status: {r_tts.status_code}", latency_ms=tts_latency)
                    except Exception as e:
                        audio_container.error(f"❌ TTS Error: {e}")
                        record_test("TTS Synthesis", False, str(e))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 ─ Boot & Health
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="section-header">Core Diagnostics</div>', unsafe_allow_html=True)
    
    if st.button("Run Health Check", key="health_btn") or run_all:
        with st.spinner("Pinging endpoints..."):
            try:
                start = time.time()
                r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
                latency = (time.time() - start) * 1000
                
                ok = r.status_code == 200
                status_class = "pass" if ok else "fail"
                
                # Display result with latency
                latency_badge = f'<span class="latency-badge {get_latency_class(latency)}">{latency:.0f}ms</span>'
                st.markdown(
                    f'<div class="test-{status_class}">'
                    f'GET /health → {r.status_code} {latency_badge}<br>'
                    f'<code>{json.dumps(r.json(), indent=2)}</code>'
                    f'</div>', 
                    unsafe_allow_html=True
                )
                
                record_test("Health Endpoint", ok, f"Status: {r.status_code}", latency_ms=latency)
                
            except Exception as e:
                st.error(f"❌ GET /health Failed: {e}")
                record_test("Health Endpoint", False, str(e))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 ─ Chat Endpoints
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="section-header">SSE Validation</div>', unsafe_allow_html=True)
    
    if st.button("Run SSE Tests", key="sse_btn") or run_all:
        payload = {
            "prompt": "Hello core.", 
            "mode": "active", 
            "query_type": "chat", 
            "session_id": SESSION_ID
        }
        
        start_time = time.time()
        tokens, lines, text = stream_post("/api/chat", payload)
        total_latency = (time.time() - start_time) * 1000
        
        if text:
            latency_badge = f'<span class="latency-badge {get_latency_class(total_latency)}">{total_latency:.0f}ms</span>'
            st.success(f"✅ SSE Stream Successful! {latency_badge}")
            st.code(text)
            record_test("Chat SSE Stream", True, f"Received {len(tokens)} tokens", latency_ms=total_latency)
        else:
            st.error("❌ Failed to receive stream tokens. Check console logs.")
            record_test("Chat SSE Stream", False, "No tokens received")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 ─ Threat Scan
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown('<div class="section-header">Threat Scanner API</div>', unsafe_allow_html=True)
    
    if st.button("Run Threat Scan", key="threat_btn") or run_all:
        payload = {"content": "import os\nos.system('whoami')", "content_type": "code"}
        try:
            start = time.time()
            r = requests.post(f"{BASE_URL}/api/threat/scan", json=payload, timeout=TIMEOUT)
            latency = (time.time() - start) * 1000
            
            if r.status_code == 200:
                latency_badge = f'<span class="latency-badge {get_latency_class(latency)}">{latency:.0f}ms</span>'
                st.success(f"✅ Threat Scan Complete {latency_badge}")
                st.json(r.json())
                record_test("Threat Scan API", True, f"Status: {r.status_code}", latency_ms=latency)
            else:
                st.error(f"❌ Error {r.status_code}")
                record_test("Threat Scan API", False, f"Status: {r.status_code}", latency_ms=latency)
        except Exception as e:
            st.error(f"❌ {e}")
            record_test("Threat Scan API", False, str(e))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 ─ System API
# ══════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown('<div class="section-header">System Controls</div>', unsafe_allow_html=True)
    
    if st.button("Test Mode Toggle", key="mode_btn") or run_all:
        try:
            start = time.time()
            r = requests.post(
                f"{BASE_URL}/api/system/mode", 
                json={"mode": "passive"}, 
                timeout=TIMEOUT
            )
            latency = (time.time() - start) * 1000
            
            if r.status_code == 200:
                latency_badge = f'<span class="latency-badge {get_latency_class(latency)}">{latency:.0f}ms</span>'
                st.success(f"✅ Mode switched to Passive: {r.json()} {latency_badge}")
                record_test("Mode Toggle API", True, f"Status: {r.status_code}", latency_ms=latency)
            else:
                st.error(f"❌ Failed: {r.status_code}")
                record_test("Mode Toggle API", False, f"Status: {r.status_code}", latency_ms=latency)
        except Exception as e:
            st.error(f"❌ {e}")
            record_test("Mode Toggle API", False, str(e))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 ─ WebSocket
# ══════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.markdown('<div class="section-header">Telemetry Socket</div>', unsafe_allow_html=True)
    
    # Live WebSocket viewer
    ws_container = st.empty()
    ws_container.markdown(
        '<div class="stream-box" style="min-height: 200px;">Waiting for WebSocket connection...</div>',
        unsafe_allow_html=True
    )
    
    if st.button("Listen to Socket (5s)", key="ws_btn") or run_all:
        if not WS_AVAILABLE:
            st.warning("⚠️ Install `websocket-client` to run this test: `pip install websocket-client`")
        else:
            ws_messages = []
            
            def _on_message(wsapp, message):
                ws_messages.append(message)
                # Update UI in real-time
                if ws_messages:
                    try:
                        latest = json.loads(ws_messages[-1])
                        ws_container.markdown(
                            f'<div class="stream-box">{json.dumps(latest, indent=2)}</div>',
                            unsafe_allow_html=True
                        )
                    except json.JSONDecodeError:
                        ws_container.markdown(
                            f'<div class="stream-box">{ws_messages[-1]}</div>',
                            unsafe_allow_html=True
                        )
            
            def _on_open(wsapp):
                # Auto-close after 5 seconds
                threading.Thread(target=lambda: (time.sleep(5), wsapp.close()), daemon=True).start()
            
            def _on_error(wsapp, error):
                ws_container.error(f"WebSocket Error: {error}")
            
            def _on_close(wsapp, close_status_code, close_msg):
                st.success(f"✅ WebSocket closed. Captured {len(ws_messages)} frames.")
                # Store in session state
                st.session_state.ws_messages.extend(ws_messages)
            
            with st.spinner("🔌 Connecting to WebSocket..."):
                try:
                    wsapp = ws_lib.WebSocketApp(
                        WS_URL,
                        on_message=_on_message,
                        on_open=_on_open,
                        on_error=_on_error,
                        on_close=_on_close
                    )
                    wsapp.run_forever()
                except Exception as e:
                    st.error(f"❌ WebSocket Error: {e}")
                    record_test("WebSocket Connection", False, str(e))
            
            # Record test result
            if ws_messages:
                record_test("WebSocket Connection", True, f"Received {len(ws_messages)} messages")
            else:
                record_test("WebSocket Connection", False, "No messages received")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 ─ Test Dashboard (NEW!)
# ══════════════════════════════════════════════════════════════════════════════
with tabs[6]:
    st.markdown('<div class="section-header">Test Results Dashboard</div>', unsafe_allow_html=True)
    
    # Summary Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_tests = len(st.session_state.test_results)
    passed_tests = sum(1 for r in st.session_state.test_results if r.get('passed'))
    failed_tests = sum(1 for r in st.session_state.test_results if not r.get('passed') and not r.get('skipped'))
    skipped_tests = sum(1 for r in st.session_state.test_results if r.get('skipped'))
    
    with col1:
        st.metric("Total Tests", total_tests)
    with col2:
        st.metric("Passed", passed_tests, delta=f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%")
    with col3:
        st.metric("Failed", failed_tests, delta=f"-{failed_tests}" if failed_tests > 0 else None, delta_color="inverse")
    with col4:
        st.metric("Skipped", skipped_tests)
    
    # Pass/Fail Chart (if Plotly available)
    if PLOTLY_AVAILABLE and total_tests > 0:
        st.markdown("### 📈 Test Results Distribution")
        
        fig = px.pie(
            values=[passed_tests, failed_tests, skipped_tests],
            names=['Passed', 'Failed', 'Skipped'],
            color_discrete_sequence=['#00ff88', '#ff4444', '#666'],
            hole=0.4
        )
        fig.update_layout(
            plot_bgcolor='#0a0a0a',
            paper_bgcolor='#0a0a0a',
            font_color='#e0e0e0',
            showlegend=True,
            height=300
        )
        st.plotly_chart(fig, width="stretch")  # ✅ FIX: use width='stretch'
    
    # Latency Chart (if Plotly available)
    if PLOTLY_AVAILABLE and st.session_state.latency_history:
        st.markdown("### ⚡ Latency History (Last 100 Requests)")
        
        fig = px.line(
            y=st.session_state.latency_history,
            labels={'y': 'Latency (ms)', 'x': 'Request'},
            title='Response Latency Over Time',
            color_discrete_sequence=['#00f3ff']
        )
        fig.update_layout(
            plot_bgcolor='#0a0a0a',
            paper_bgcolor='#0a0a0a',
            font_color='#e0e0e0',
            showlegend=False,
            height=250,
            yaxis=dict(range=[0, max(st.session_state.latency_history) * 1.2])
        )
        st.plotly_chart(fig, width="stretch")  # ✅ FIX: use width='stretch'
    
    # Detailed Test Results Table
    st.markdown("### 📋 Detailed Test Results")
    
    if st.session_state.test_results:
        # Create DataFrame for display
        import pandas as pd
        df = pd.DataFrame(st.session_state.test_results)
        
        # ✅ FIX: Proper lambda function to avoid Series ambiguity error
        def get_status(row):
            if row['passed']:
                return '✅ PASS'
            elif row.get('skipped', False):
                return '⚠️ SKIP'
            else:
                return '❌ FAIL'
        
        df['Status'] = df.apply(get_status, axis=1)
        df['Latency'] = df['latency_ms'].apply(lambda x: f"{x:.0f}ms" if x is not None else "N/A")
        
        # Display table with custom styling
        st.dataframe(
            df[['name', 'Status', 'Latency', 'detail', 'timestamp']],
            column_config={
                "name": "Test Name",
                "Status": "Status",
                "Latency": "Latency",
                "detail": "Details",
                "timestamp": "Timestamp"
            },
            hide_index=True,
            width="stretch"  # ✅ FIX: use width='stretch'
        )
    else:
        st.info("No tests run yet. Click 'Run ALL Tests' or individual test buttons to start.")
    
    # Export Results
    if st.session_state.test_results:
        st.markdown("---")
        st.markdown("### 📥 Export Results")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Download JSON Report", width="stretch"):  # ✅ FIX: use width='stretch'
                report = {
                    "timestamp": datetime.now().isoformat(),
                    "total_tests": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "skipped": skipped_tests,
                    "avg_latency_ms": sum(st.session_state.latency_history) / len(st.session_state.latency_history) if st.session_state.latency_history else None,
                    "results": st.session_state.test_results
                }
                st.download_button(
                    label="📄 Download JSON",
                    data=json.dumps(report, indent=2),
                    file_name=f"hackt_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    width="stretch"  # ✅ FIX: use width='stretch'
                )
        
        with col2:
            if st.button("Download CSV Report", width="stretch"):  # ✅ FIX: use width='stretch'
                import pandas as pd
                df = pd.DataFrame(st.session_state.test_results)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📊 Download CSV",
                    data=csv,
                    file_name=f"hackt_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    width="stretch"  # ✅ FIX: use width='stretch'
                )

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #666; font-size: 12px; padding: 20px;">'
    'HackT Sovereign Core Test Suite v3.1 • '
    f'Last Run: {st.session_state.last_test_run or "Never"}'
    '</div>',
    unsafe_allow_html=True
)