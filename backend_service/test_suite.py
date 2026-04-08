"""
HackT Sovereign Core - Unified Pipeline Simulator (Streamlit)
======================================================================
Simulates the exact lifecycle of the Tauri frontend talking to the v5.1 API.

Features:
- Native Microphone Recording -> STT -> LLM Stream -> TTS
- Live "Brain Logs" showing RAG Citations and Token telemetry
- 🌟 NEW: Modal Popup Dialog for final output
- Independent API Diagnostic endpoints
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & STYLES
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Sovereign Core Simulator", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Rajdhani:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; background: #030305; color: #e0e0e0; }
.section-header { font-family: 'Rajdhani'; font-weight: 700; font-size: 22px; color: #e0e0e0; border-bottom: 2px solid #333; padding-bottom: 6px; margin: 18px 0 10px 0; }
.stream-box { background: #0a0a0a; border: 1px solid #00f3ff; border-radius: 6px; padding: 16px; font-family: 'Space Mono'; font-size: 14px; color: #00f3ff; min-height: 100px; white-space: pre-wrap; box-shadow: 0 0 15px rgba(0, 243, 255, 0.1); }
.log-box { background: #111; border-left: 3px solid #bc13fe; padding: 10px; font-family: 'Space Mono'; font-size: 12px; color: #bc13fe; margin-top: 10px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-family: 'Space Mono'; font-size: 12px; font-weight: bold; margin-right: 8px; }
.badge-good { background: #00ff88/20; color: #00ff88; }
.badge-warn { background: #ffaa00/20; color: #ffaa00; }
.badge-bad { background: #ff4444/20; color: #ff4444; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG & STATE
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL = "http://127.0.0.1:8000/api"
TIMEOUT = 60

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

def parse_sse_line(line: str) -> Optional[dict]:
    if not line or not line.startswith("data: "):
        return None
    try:
        return json.loads(line[6:].strip())
    except json.JSONDecodeError:
        return None

# ══════════════════════════════════════════════════════════════════════════════
# POPUP DIALOG DEFINITION
# ══════════════════════════════════════════════════════════════════════════════
@st.dialog("✅ Sovereign Execution Complete", width="large")
def show_final_popup(prompt: str, response: str, audio_bytes: Optional[bytes]):
    """Creates a modal popup over the UI to display the final result."""
    st.markdown("### 🗣️ You Said:")
    st.info(prompt)
    
    st.markdown("### 🤖 HackT Responded:")
    st.success(response)
    
    if audio_bytes:
        st.markdown("### 🔊 Audio Synthesis:")
        st.audio(audio_bytes, format="audio/wav", autoplay=True)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(135deg,#0d1117,#161d27); border:1px solid #1e3a5f; border-radius:14px; padding:20px; margin-bottom:24px;">
  <h1 style="font-family:'Space Mono';color:#00f3ff;margin:0;font-size:28px;">🛡️ Sovereign Core Control Deck</h1>
  <p style="color:#7090a0;margin:6px 0 0 0;">Unified Pipeline Simulator (v5.1 API)</p>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs(["🎙️ The Sovereign Pipeline", "⚙️ API Diagnostics"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 ─ THE UNIFIED PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-header">End-to-End Execution: Voice → Brain → Voice</div>', unsafe_allow_html=True)
    
    col_input, col_output = st.columns([1, 2])
    
    with col_input:
        st.markdown("### 1. Audio Input")
        audio_data = st.audio_input("Record your command")
        
        st.markdown("### OR Text Input")
        text_data = st.text_input("Type a command instead:")
        
        trigger_pipeline = st.button("🚀 Execute Pipeline", type="primary", use_container_width=True)

    with col_output:
        st.markdown("### 2. Live Telemetry")
        stream_ui = st.empty()
        log_ui = st.empty()
        audio_ui = st.empty()
        
        if not audio_data and not text_data:
            stream_ui.markdown('<div class="stream-box" style="opacity: 0.5;">Awaiting input...</div>', unsafe_allow_html=True)

        if trigger_pipeline:
            # --- PHASE 1: STT (Speech to Text) ---
            prompt_text = text_data
            
            if audio_data:
                stream_ui.markdown('<div class="stream-box">🎧 Sending audio to Whisper STT...</div>', unsafe_allow_html=True)
                try:
                    start_stt = time.time()
                    res_stt = requests.post(f"{BASE_URL}/audio/transcribe", data=audio_data.getvalue(), timeout=TIMEOUT)
                    res_stt.raise_for_status()
                    prompt_text = res_stt.json().get("text", "")
                    stt_time = (time.time() - start_stt) * 1000
                    log_ui.markdown(f'<div class="log-box">✅ Transcribed in {stt_time:.0f}ms: "{prompt_text}"</div>', unsafe_allow_html=True)
                except Exception as e:
                    stream_ui.error(f"STT Failed: {e}")
                    st.stop()
            
            if not prompt_text:
                stream_ui.error("No input detected. Aborting pipeline.")
                st.stop()

            # --- PHASE 2: LLM & RAG (Chat Stream) ---
            stream_ui.markdown(f'<div class="stream-box">🧠 Processing: "{prompt_text}"...</div>', unsafe_allow_html=True)
            
            payload = {
                "prompt": prompt_text,
                "mode": "active",
                "session_id": "streamlit_sim_001",
                "query_type": "voice" if audio_data else "chat"
            }
            
            full_response = ""
            citations_found = []
            
            start_llm = time.time()
            try:
                with requests.post(f"{BASE_URL}/chat", json=payload, stream=True, timeout=TIMEOUT) as res_chat:
                    res_chat.raise_for_status()
                    for raw in res_chat.iter_lines(decode_unicode=True):
                        parsed = parse_sse_line(raw)
                        if parsed:
                            if parsed.get("done"):
                                break
                            
                            token = parsed.get("token", "")
                            full_response += token
                            
                            cits = parsed.get("citations", [])
                            if cits and not citations_found:
                                citations_found = cits
                                
                            stream_ui.markdown(f'<div class="stream-box">{full_response}▌</div>', unsafe_allow_html=True)
                
                llm_time = (time.time() - start_llm) * 1000
                stream_ui.markdown(f'<div class="stream-box">{full_response}</div>', unsafe_allow_html=True)
                
                cit_html = "<br>".join(citations_found) if citations_found else "No context retrieved."
                log_ui.markdown(
                    f'<div class="log-box">'
                    f'✅ LLM Streamed in {llm_time:.0f}ms<br>'
                    f'📚 <b>RAG Citations:</b><br>{cit_html}'
                    f'</div>', 
                    unsafe_allow_html=True
                )
            except Exception as e:
                stream_ui.error(f"Chat Stream Failed: {e}")
                st.stop()

            # --- PHASE 3: TTS (Text to Speech) ---
            stream_ui.markdown(f'<div class="stream-box">{full_response}\n\n🔊 Generating Voice...</div>', unsafe_allow_html=True)
            
            final_audio_bytes = None
            try:
                start_tts = time.time()
                tts_text = full_response[:500] 
                res_tts = requests.post(f"{BASE_URL}/tts", json={"text": tts_text}, timeout=TIMEOUT)
                res_tts.raise_for_status()
                
                final_audio_bytes = res_tts.content
                tts_time = (time.time() - start_tts) * 1000
                stream_ui.markdown(f'<div class="stream-box">{full_response}</div>', unsafe_allow_html=True)
                log_ui.markdown(
                    f'<div class="log-box">'
                    f'✅ Audio Synthesized in {tts_time:.0f}ms'
                    f'</div>', 
                    unsafe_allow_html=True
                )
            except Exception as e:
                audio_ui.error(f"TTS Failed: {e}")

            # --- PHASE 4: TRIGGER POPUP DIALOG ---
            # This dims the background and pushes the final summary to the front!
            show_final_popup(prompt_text, full_response, final_audio_bytes)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 ─ API DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="section-header">Direct REST API Diagnostics</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 1. Health Check (`GET /api/health`)")
        if st.button("Ping Core Health", use_container_width=True):
            try:
                start = time.time()
                r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
                lat = (time.time() - start) * 1000
                st.success(f"✅ {r.status_code} OK ({lat:.0f}ms)")
                st.json(r.json())
            except Exception as e:
                st.error(f"❌ Connection Failed: {e}")
                
        st.markdown("### 2. Nuclear Kill Switch (`POST /api/system/shutdown`)")
        if st.button("⚠️ Trigger Shutdown (Danger)", use_container_width=True, type="secondary"):
            try:
                r = requests.post(f"{BASE_URL}/system/shutdown", timeout=5)
                st.warning("Shutdown signal sent. Server should be terminating.")
            except Exception as e:
                st.error("Server is likely already dead, or connection failed.")

    with col2:
        st.markdown("### 3. TTS Isolation (`POST /api/tts`)")
        tts_test = st.text_area("Text to synthesize:", "System diagnostics complete. All systems nominal.")
        if st.button("Generate Audio", use_container_width=True):
            with st.spinner("Synthesizing..."):
                try:
                    start = time.time()
                    r = requests.post(f"{BASE_URL}/tts", json={"text": tts_test}, timeout=TIMEOUT)
                    r.raise_for_status()
                    st.success(f"✅ Success ({(time.time()-start)*1000:.0f}ms)")
                    st.audio(r.content, format="audio/wav")
                except Exception as e:
                    st.error(f"❌ {e}")