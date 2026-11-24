"""
Voice-First Multilingual Agricultural Assistant (Phase 6 Final Application).
Unified Streamlit Web Application & Admin Review Console (Modules 01 - 14).
Supports BOTH:
  1. Streamlit Web Interface (Voice In, Text In, Audio Out, Mandi, Weather, Admin)
  2. WhatsApp Business Cloud API (Webhook Verification, Inbound Text/Audio, Outbound Messages)
Powered by the exact same underlying agricultural AI backend, multilingual NLU, and verified RAG.
"""
import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src.core.voice_assistant import VoiceAgriculturalAssistant
from src.admin.admin_service import AdminService
from src.channel.whatsapp_client import WhatsAppCloudClient
from src.channel.twilio_client import TwilioWhatsAppClient
from src.knowledge.models import DocumentMetadata
from src.tools.mandi_price_tool import MandiPriceTool
from src.tools.weather_tool import WeatherTool
from src.evaluation.benchmark_runner import AgriculturalBenchmarkRunner


# ==============================================================================
# Page Configuration & Agricultural Styling
# ==============================================================================
st.set_page_config(
    page_title="AgriVoice Assistant | कृषि वाणी",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Agricultural Green & White Theme
st.markdown("""
<style>
    :root {
        --primary-green: #2E7D32;
        --dark-green: #1B5E20;
        --light-green: #E8F5E9;
        --accent-gold: #F9A825;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        color: #FFFFFF !important;
        margin: 0;
        font-size: 2.2rem;
    }
    .main-header p {
        color: #E8F5E9 !important;
        margin: 0.3rem 0 0 0;
        font-size: 1.1rem;
    }
    .badge-pill {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
        margin-right: 0.5rem;
    }
    .badge-success { background-color: #C8E6C9; color: #1B5E20; }
    .badge-warning { background-color: #FFF9C4; color: #F57F17; }
    .badge-refused { background-color: #FFCDD2; color: #B71C1C; }
    
    .evidence-card {
        background-color: #F1F8E9;
        border-left: 4px solid #2E7D32;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin-top: 0.8rem;
    }
    .whatsapp-bubble {
        background-color: #DCF8C6;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
        border: 1px solid #C5E1A5;
        font-family: sans-serif;
    }
    .stat-card {
        background-color: #FFFFFF;
        border: 1px solid #C8E6C9;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# Service Instances (Reloadable Session-Based to Prevent Stale Caching)
# ==============================================================================
def get_services(force_reload: bool = False):
    if force_reload or "assistant_instance" not in st.session_state:
        st.session_state.assistant_instance = VoiceAgriculturalAssistant(data_dir="data")
        st.session_state.admin_service_instance = AdminService(data_dir="data")
        st.session_state.whatsapp_client_instance = WhatsAppCloudClient(data_dir="data")
        st.session_state.twilio_client_instance = TwilioWhatsAppClient(data_dir="data")
    return (
        st.session_state.assistant_instance,
        st.session_state.admin_service_instance,
        st.session_state.whatsapp_client_instance,
        st.session_state.twilio_client_instance
    )


assistant, admin_service, whatsapp_client, twilio_client = get_services()


# ==============================================================================
# Session State Initialization
# ==============================================================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

if "user_consent" not in st.session_state:
    st.session_state.user_consent = True

if "whatsapp_sim_history" not in st.session_state:
    st.session_state.whatsapp_sim_history = []


# ==============================================================================
# Sidebar: Language & Navigation
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/wheat.png", width=64)
    st.title("🌾 AgriVoice")
    st.caption("Voice-First Indic Agricultural Assistant")

    # Language Switcher
    lang_choice = st.selectbox(
        "🌐 भाषा निवडा / भाषा चुनें / Language",
        options=["hi", "mr", "en"],
        format_func=lambda x: {"hi": "हिंदी (Hindi)", "mr": "मराठी (Marathi)", "en": "English"}[x]
    )

    st.markdown("---")
    nav_option = st.radio(
        "📌 Navigation",
        options=[
            "🎙️ Farmer Assistant (शेतकरी मित्र)",
            "📊 Live Mandi & Weather (मंडी व हवामान)",
            "📱 WhatsApp Channel (व्हॉट्सॲप चॅनेल)",
            "📈 Quality Benchmark (गुणवत्ता मूल्यमापन)",
            "🔐 Admin Console (प्रशासक कक्ष)"
        ]
    )

    st.markdown("---")
    st.session_state.user_consent = st.checkbox(
        "✅ I consent to voice query processing for agricultural advisory (डेटा गोपनीयता संमती)",
        value=st.session_state.user_consent
    )
    if st.button("🗑️ Clear Chat History (इतिहास हटवा)"):
        st.session_state.chat_history = []
        assistant.privacy_manager.cleanup_all_session_audio()
        get_services(force_reload=True)
        st.rerun()

    if st.button("🔄 Reload Services (सर्व्हिसेस रीलोड करा)"):
        get_services(force_reload=True)
        st.toast("✅ सर्व्हिसेस व डेटा रीलोड झाला! (Services reloaded)")
        st.rerun()
        st.rerun()

    st.caption("🔒 All audio processed according to privacy policy. Phone numbers hashed.")


# ==============================================================================
# Helper Labels & Translations
# ==============================================================================
LABELS = {
    "hi": {
        "title": "आवाज-प्रथम बहुभाषी कृषि सहायक",
        "subtitle": "भारतीय किसानों के लिए प्रामाणिक फसल परामर्श, मौसम और लाइव मंडी भाव",
        "input_placeholder": "अपना कृषि प्रश्न यहां लिखें या नीचे माइक से बोलें...",
        "record_audio": "माइक से अपनी आवाज रिकॉर्ड करें (Microphone Voice Input)",
        "upload_audio": "या ऑडियो फाइल अपलोड करें (.wav, .mp3)",
        "source": "स्रोत",
        "decision": "निर्णय",
        "confidence": "विश्वास स्कोर",
        "kisan_helpline": "किसान कॉल सेंटर: 1800-180-1551 (टोल-फ्री)"
    },
    "mr": {
        "title": "आवाज-प्रथम बहुभाषिक कृषी सहाय्यक",
        "subtitle": "शेतकऱ्यांसाठी अधिकृत पीक सल्ला, हवामान आणि थेट बाजारभाव",
        "input_placeholder": "आपला कृषी प्रश्न येथे लिहा किंवा खाली माइकद्वारे बोला...",
        "record_audio": "माइकद्वारे आपला आवाज रेकॉर्ड करा (Microphone Voice Input)",
        "upload_audio": "किंवा ऑडिओ फाइल अपलोड करा (.wav, .mp3)",
        "source": "स्रोत",
        "decision": "निर्णय",
        "confidence": "विश्वास निर्देशांक",
        "kisan_helpline": "किसान कॉल सेंटर: 1800-180-1551 (टोल-फ्री)"
    },
    "en": {
        "title": "Voice-First Multilingual Agricultural Assistant",
        "subtitle": "Institutional Crop Advisory, Weather Forecasts & Live Mandi Prices for Indian Farmers",
        "input_placeholder": "Type your farming question here or speak into the microphone below...",
        "record_audio": "Record your voice with microphone (Microphone Voice Input)",
        "upload_audio": "Or upload an audio file (.wav, .mp3)",
        "source": "Source",
        "decision": "Decision",
        "confidence": "Confidence",
        "kisan_helpline": "Kisan Call Centre: 1800-180-1551 (Toll-Free)"
    }
}
L = LABELS[lang_choice]


# ==============================================================================
# VIEW 1: Farmer Assistant (Chat, Voice In, Audio Out, RAG)
# ==============================================================================
if nav_option.startswith("🎙️"):
    st.markdown(f"""
    <div class="main-header">
        <h1>🌾 {L['title']}</h1>
        <p>{L['subtitle']}</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.user_consent:
        st.warning("⚠️ कृपया ऑडिओ प्रक्रिया सुरू करण्यासाठी डाव्या बाजूला संमती (Consent) चेकबॉक्स निवडा.")
        st.stop()

    col_input1, col_input2 = st.columns([1, 1])
    audio_to_process = None

    with col_input1:
        st.markdown(f"**🎙️ {L['record_audio']}**")
        mic_audio = st.audio_input("Record Voice Note", key="mic_recorder")
        if mic_audio is not None:
            audio_to_process = mic_audio

    with col_input2:
        st.markdown(f"**📁 {L['upload_audio']}**")
        uploaded_audio = st.file_uploader("Upload Audio Note", type=["wav", "mp3", "ogg"], key="file_audio")
        if uploaded_audio is not None:
            audio_to_process = uploaded_audio

    user_text_input = st.chat_input(L["input_placeholder"])

    # Determine unique audio identifier to prevent re-processing identical audio
    audio_id = None
    if audio_to_process is not None:
        audio_size = getattr(audio_to_process, "size", 0)
        audio_name = getattr(audio_to_process, "name", "audio")
        audio_id = f"{audio_name}_{audio_size}"

    if audio_to_process is not None and ("last_processed_audio_id" not in st.session_state or st.session_state.last_processed_audio_id != audio_id):
        with st.spinner("🎧 आवाज प्रक्रिया व विश्लेषण सुरू आहे... (Processing audio)..."):
            temp_dir = Path("data/cache/temp_audio")
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_audio_path = temp_dir / f"user_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"

            with open(temp_audio_path, "wb") as f:
                f.write(audio_to_process.read())

            res = assistant.process_voice_query(
                audio_path=str(temp_audio_path),
                language_hint=lang_choice
            )

            st.session_state.last_processed_audio_id = audio_id
            st.session_state.last_submit_time = datetime.now()

            # Prevent duplicate consecutive entries
            query_text = res.get("transcript") or "(Unrecognized Voice)"
            if not (st.session_state.chat_history and st.session_state.chat_history[-1].get("query") == query_text):
                st.session_state.chat_history.append({
                    "type": "voice",
                    "query": query_text,
                    "result": res,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })

    elif user_text_input:
        query_clean = user_text_input.strip()
        last_query = st.session_state.get("last_processed_text_query", "")
        last_time = st.session_state.get("last_submit_time", datetime.min)
        is_rapid_duplicate = (query_clean == last_query and (datetime.now() - last_time).total_seconds() < 2.0)

        if not is_rapid_duplicate:
            with st.spinner("🌱 कृषी सल्ला शोधत आहे... (Retrieving verified advice)..."):
                res = assistant.process_text_query(
                    query=query_clean,
                    language_hint=lang_choice
                )
                st.session_state.last_processed_text_query = query_clean
                st.session_state.last_submit_time = datetime.now()

                # Guard against duplicate consecutive appends
                if not (st.session_state.chat_history and st.session_state.chat_history[-1].get("query") == query_clean):
                    st.session_state.chat_history.append({
                        "type": "text",
                        "query": query_clean,
                        "result": res,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })

    # Sanitize chat history: deduplicate any consecutive identical queries
    if st.session_state.chat_history:
        cleaned_history = []
        for entry in st.session_state.chat_history:
            if not cleaned_history or cleaned_history[-1].get("query") != entry.get("query") or cleaned_history[-1].get("timestamp") != entry.get("timestamp"):
                cleaned_history.append(entry)
        st.session_state.chat_history = cleaned_history

    st.markdown("### 💬 संवाद (Conversation Feed)")
    if not st.session_state.chat_history:
        st.info("💡 **टीप / संकेत (Sample Questions):**\n"
                "- *'नागपुर मंडी में कपास का भाव क्या है?'* (मंडी भाव)\n"
                "- *'पुणे येथील आजचे हवामान कसे आहे?'* (हवामान सल्ला)\n"
                "- *'कपास में गुलाबी सुंडी की रोकथाम के लिए क्या करें?'* (कीड व्यवस्थापन)\n"
                "- *'गहू पिकावरील पिवळा तांबेरा रोगाची लक्षणे काय आहेत?'* (रोग निदान)")

    for idx, item in enumerate(reversed(st.session_state.chat_history)):
        res = item["result"]
        status = res.get("status", "unknown")

        with st.container():
            icon = "🎙️" if item["type"] == "voice" else "👤"
            st.markdown(f"**{icon} शेतकरी / Farmer ({item['timestamp']}):** {item['query']}")

            badge_class = "badge-success" if status in ["success", "answered"] else ("badge-warning" if status == "clarification_required" else "badge-refused")
            st.markdown(f"<span class='badge-pill {badge_class}'>STATUS: {status.upper()}</span>", unsafe_allow_html=True)

            raw_text = res.get("text_response") or res.get("spoken_text") or res.get("tool_data", {}).get("message") or res.get("message") or ""
            if not raw_text.strip():
                if status == "not_found":
                    response_text = (
                        "सध्या या विषयावर प्रमाणित अधिकृत माहिती उपलब्ध होऊ शकली नाही. चुकीची माहिती टाळण्यासाठी आम्ही अंदाजे उत्तरे देत नाही. कृपया अधिकृत Agmarknet पोर्टल (agmarknet.gov.in) पहा किंवा किसान कॉल सेंटर 1800-180-1551 वर संपर्क साधा."
                        if lang_choice == "mr" else
                        "वर्तमान में इस विषय पर प्रमाणित आधिकारिक जानकारी उपलब्ध नहीं हो सकी। भ्रामक सलाह से बचने के लिए हम अनुमानित उत्तर नहीं देते। कृपया आधिकारिक Agmarknet पोर्टल (agmarknet.gov.in) देखें या किसान कॉल सेंटर 1800-180-1551 पर संपर्क करें।"
                    )
                elif status == "clarification_required":
                    response_text = (
                        "कृपया आपला प्रश्न अधिक स्पष्ट करा (उदा. पिकाचे किंवा बाजार समितीचे नाव सांगा)."
                        if lang_choice == "mr" else
                        "कृपया अपना प्रश्न अधिक स्पष्ट करें (जैसे फसल अथवा मंडी का नाम बताएं)।"
                    )
                else:
                    response_text = (
                        "माहिती उपलब्ध होऊ शकली नाही. कृपया किसान कॉल सेंटर (1800-180-1551) वर संपर्क साधा."
                        if lang_choice == "mr" else
                        "जानकारी उपलब्ध नहीं हो सकी। कृपया किसान कॉल सेंटर (1800-180-1551) पर संपर्क करें।"
                    )
            else:
                response_text = raw_text

            st.markdown(f"**🌾 कृषी सहाय्यक / AgriVoice:**\n{response_text}")

            if "audio_response_path" in res and Path(res["audio_response_path"]).exists():
                st.audio(res["audio_response_path"])

            citations = res.get("citations", [])
            if citations:
                with st.expander(f"📚 {L['source']} व संदर्भ (Verified Sources - {len(citations)})"):
                    for c in citations:
                        st.markdown(f"- 🏛️ **{c}**")
                    if res.get("evidence_passages"):
                        st.markdown("---")
                        st.markdown("**प्रमाणित उतारे (Retrieved Evidence Passages):**")
                        for ep in res["evidence_passages"][:2]:
                            st.caption(f"[{ep.get('source')}] {ep.get('text')}")

            c_fb1, c_fb2, c_fb3 = st.columns([1, 1, 8])
            with c_fb1:
                if st.button("👍 उपयुक्त", key=f"up_{idx}"):
                    admin_service.record_user_feedback(res.get("user_id_hash", "anon"), item["query"], status, "thumbs_up")
                    st.toast("धन्यवाद! आपला प्रतिसाद नोंदवला गेला आहे.")
            with c_fb2:
                if st.button("👎 चुकीचे", key=f"down_{idx}"):
                    admin_service.record_user_feedback(res.get("user_id_hash", "anon"), item["query"], status, "thumbs_down")
                    st.toast("नोंद घेतली गेली. तज्ज्ञ कृषी अधिकारी याची पडताळणी करतील.")

            st.markdown("---")


# ==============================================================================
# VIEW 2: Live Mandi & Weather Dashboard
# ==============================================================================
elif nav_option.startswith("📊"):
    st.markdown("""
    <div class="main-header">
        <h1>📊 थेट बाजारभाव व हवामान सल्ला (Live Mandi & Weather)</h1>
        <p>अधिकृत Agmarknet बाजारभाव आणि Open-Meteo व IMD आधारित हवामान सूचना</p>
    </div>
    """, unsafe_allow_html=True)

    tab_mandi, tab_weather = st.tabs(["💰 मंडी भाव (Mandi Prices)", "🌦️ हवामान अंदाज (Weather Advisory)"])

    with tab_mandi:
        st.markdown("### 🌾 Agmarknet थेट कमोडिटी बाजारभाव")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            crop_select = st.selectbox("पिक / Commodity", ["Cotton", "Wheat", "Onion", "Soybean", "Rice"])
        with col_m2:
            district_select = st.selectbox("जिल्हा / District", ["Nagpur", "Nashik", "Pune", "Akola", "Ludhiana", "Indore", "All"])

        mandi_res = assistant.mandi_tool.get_mandi_prices(
            commodity=crop_select,
            district=None if district_select == "All" else district_select
        )

        if mandi_res["status"] == "success":
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("सरासरी भाव (Modal Price)", f"₹ {mandi_res['modal_price']}", f"प्रति {mandi_res['unit']}")
            with col_stat2:
                st.metric("किमान भाव (Min Price)", f"₹ {mandi_res['min_price']}")
            with col_stat3:
                st.metric("कमाल भाव (Max Price)", f"₹ {mandi_res['max_price']}")

            st.success(f"📍 **मंडी:** {mandi_res['market']} ({mandi_res['district']}) | 📅 **तारीख:** {mandi_res['arrival_date']}")
            historical_tag = "🔴 लाइव सत्यापित (Live Verified)" if mandi_res.get("is_live") else "🟡 ऐतिहासिक संदर्भ नोंद (Historical Agmarknet Record)"
            st.caption(f"🏛️ **स्रोत (Source):** {mandi_res['source']} | **नोंद प्रकार:** {historical_tag}")
        else:
            st.warning(mandi_res.get("message"))

    with tab_weather:
        st.markdown("### 🌦️ Open-Meteo व IMD कृषी हवामान सल्ला")
        weather_dist = st.selectbox("स्थान / जिल्हा निवडा (Select District)", list(WeatherTool.DISTRICT_COORDINATES.keys()), format_func=lambda x: x.capitalize())

        w_res = assistant.weather_tool.get_weather(weather_dist)
        if w_res["status"] == "success":
            w = w_res["weather"]
            col_w1, col_w2, col_w3, col_w4 = st.columns(4)
            with col_w1:
                st.metric("तापमान (Temperature)", f"{w['temperature']} °C", f"कमाल {w['max_temperature']}° / किमान {w['min_temperature']}°")
            with col_w2:
                st.metric("हवेतील आर्द्रता (Humidity)", f"{w['humidity']} %")
            with col_w3:
                st.metric("पाऊस (Rainfall)", f"{w['precipitation_mm']} mm")
            with col_w4:
                st.metric("वाऱ्याचा वेग (Wind)", f"{w['wind_speed_kmh']} km/h")

            st.markdown(f"""
            <div class="evidence-card">
                <h4>🚜 हवामान कृषी सल्ला (Agromet Advisory):</h4>
                <p><b>मराठी:</b> {w_res['agromet_advisory']['mr']}</p>
                <p><b>हिंदी:</b> {w_res['agromet_advisory']['hi']}</p>
            </div>
            """, unsafe_allow_html=True)
            st.caption(f"🏛️ **स्रोत व तारीख:** {w_res['source']} | Sync: {w_res['timestamp'][:16].replace('T', ' ')}")


# ==============================================================================
# VIEW 3: WhatsApp Business Cloud API Integration (Module 01)
# ==============================================================================
elif nav_option.startswith("📱"):
    st.markdown("""
    <div class="main-header">
        <h1>📱 WhatsApp Business Cloud API चॅनेल (Module 01)</h1>
        <p>शेतकऱ्यांसाठी थेट व्हॉट्सॲपवरून आवाज व मजकूर सल्ला — Unified AI Backend Architecture</p>
    </div>
    """, unsafe_allow_html=True)

    tab_wa_status, tab_wa_sim, tab_wa_guide = st.tabs([
        "📡 API स्थिती व वेबहुक तपशील (API Status & Webhook)",
        "🧪 व्हॉट्सॲप सिम्युलेटर (Interactive Simulator)",
        "📖 Meta Cloud API सेटअप मार्गदर्शक (Setup Guide)"
    ])

    with tab_wa_status:
        st.markdown("### 🟢 Twilio WhatsApp Sandbox (Active College Project Mode)")
        col_tw1, col_tw2, col_tw3 = st.columns(3)
        with col_tw1:
            if twilio_client.is_configured:
                st.success("🟢 **स्थिती: TWILIO CONFIGURED**")
            else:
                st.info("🟡 **स्थिती: LOCAL DEV / SANDBOX READY**")
            st.caption("Twilio Account SID & Auth Token")
        with col_tw2:
            st.info(f"**Twilio Sandbox Number:** `{twilio_client.from_number}`")
            st.caption("WhatsApp Sandbox Gateway")
        with col_tw3:
            st.metric("Signature Check", "ENFORCED" if twilio_client.auth_token else "OPTIONAL (Dev)")
            st.caption("HMAC-SHA1 Request Validation")

        st.markdown("#### 🔗 Twilio Sandbox Webhook Settings")
        st.code("""
# In Twilio Console -> Messaging -> Try it out -> Send a WhatsApp message -> Sandbox Settings:
# WHEN A MESSAGE COMES IN:
URL:    https://<your-ngrok-tunnel>.ngrok-free.app/twilio/webhook
METHOD: HTTP POST
RESPONSE: Returns TwiML XML (<Response><Message>...</Message></Response>)
        """, language="bash")

        st.markdown("---")
        st.markdown("### ⚙️ Meta WhatsApp Business Cloud API (Optional Enterprise Adapter)")
        col_wa1, col_wa2, col_wa3 = st.columns(3)
        with col_wa1:
            if whatsapp_client.is_configured:
                st.success("🟢 **स्थिती: LIVE CONFIGURED**")
            else:
                st.warning("🟡 **स्थिती: CREDENTIAL-GATED (सुरक्षित ऑफलाइन मोड)**")
            st.caption("Meta credentials check in `.env`")
        with col_wa2:
            st.info(f"**Graph API Version:** `{whatsapp_client.GRAPH_API_VERSION}`")
            st.caption("Official Meta WhatsApp Business Cloud API")
        with col_wa3:
            st.metric("Verify Token Set", "होय (Active)" if whatsapp_client.verify_token else "नाही")
            st.caption("Used for Meta Webhook Handshake")

        st.markdown("#### 🔗 Meta Cloud API Webhook Endpoints")
        st.code("""
# Meta Webhook Verification (GET) and Delivery (POST):
https://<your-ngrok-tunnel>.ngrok-free.app/webhook
        """, language="bash")

        st.info("💡 **टीप (Architecture Guarantee):** Twilio WhatsApp, Meta WhatsApp आणि Streamlit वेब अ‍ॅप तिन्ही **एकाच AI बॅकएंड** वर चालतात — समान NLU, भाषा ओळख, सुरक्षितता पडताळणी, FAISS/BM25 RAG, आणि Agmarknet थेट बाजारभाव.")

    with tab_wa_sim:
        st.markdown("### 🧪 परस्परसंवादी व्हॉट्सॲप सिम्युलेटर (Interactive Message Simulator)")
        st.caption("Meta developer खात्याशिवाय व्हॉट्सॲप संदेशांचे थेट बॅकएंड प्रोसेसिंग तपासा.")

        sim_phone = st.text_input("शेतकऱ्याचा फोन नंबर (Sender Phone Number)", value="919876543210")
        sim_type = st.radio("संदेश प्रकार (Message Type)", ["Text Message (मजकूर)", "Voice Note Simulation (आवाज)"], horizontal=True)

        if sim_type.startswith("Text"):
            sim_query = st.text_area(
                "शेतकऱ्याचा प्रश्न (Farmer Message)",
                value="कपास में गुलाबी सुंडी नियंत्रण के लिए क्या करें?",
                placeholder="उदा. नागपुर मंडी में कपास का भाव क्या है?"
            )
            sample_btns = st.columns(3)
            with sample_btns[0]:
                if st.button("📋 Sample: मंडी भाव (Mandi Price)"):
                    sim_query = "नागपुर मंडी में कपास का भाव क्या है?"
            with sample_btns[1]:
                if st.button("📋 Sample: हवामान (Weather)"):
                    sim_query = "पुणे येथील आजचे हवामान कसे आहे?"
            with sample_btns[2]:
                if st.button("📋 Sample: प्रतिबंधित कीटकनाशक (Banned Chemical)"):
                    sim_query = "मोनोक्रोटोफॉस कीटनाशक का स्प्रे कैसे करें?"

            if st.button("📤 सिम्युलेटेड व्हॉट्सॲप संदेश पाठवा (Simulate WhatsApp Inbound)"):
                with st.spinner("व्हॉट्सॲप वेबहुक प्रक्रिया सुरू आहे..."):
                    parsed_payload = {
                        "message_id": f"WAMID_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "sender_phone": sim_phone,
                        "type": "text",
                        "content": sim_query
                    }
                    sim_res = whatsapp_client.process_incoming_message(parsed_payload, assistant)
                    st.session_state.whatsapp_sim_history.append(sim_res)

        else:
            st.info("🎙️ व्हॉट्सॲप व्हॉइस संदेश चाचणी: उपलब्ध प्रात्यक्षिक ऑडिओ निवडा किंवा नवीन चाचणी करा.")
            sample_audio_choice = st.selectbox(
                "चाचणीसाठी ऑडिओ निवडा",
                ["farmer_hi_cotton.wav", "farmer_mr_wheat.wav", "voice_mandi_cotton.wav"]
            )
            if st.button("📤 सिम्युलेटेड व्हॉट्सॲप व्हॉइस पाठवा"):
                audio_path = Path("data/cache/demo_voice_inputs") / sample_audio_choice
                if audio_path.exists():
                    with st.spinner("व्हॉट्सॲप व्हॉइस प्रक्रिया सुरू आहे..."):
                        parsed_payload = {
                            "message_id": f"WAMID_VOICE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            "sender_phone": sim_phone,
                            "type": "audio",
                            "media_id": f"MEDIA_{sample_audio_choice}"
                        }
                        # Run through speech pipeline
                        v_res = assistant.process_voice_query(
                            audio_path=str(audio_path),
                            user_phone_or_id=sim_phone
                        )
                        reply = whatsapp_client.format_whatsapp_reply(v_res)
                        st.session_state.whatsapp_sim_history.append({
                            "status": "success",
                            "type": "audio",
                            "sender_phone": sim_phone,
                            "transcript": v_res.get("transcript"),
                            "assistant_result": v_res,
                            "reply_text": reply
                        })
                else:
                    st.warning("डेमो ऑडिओ फाइल उपलब्ध नाही.")

        # Display WhatsApp simulation outputs
        if st.session_state.whatsapp_sim_history:
            st.markdown("---")
            st.markdown("#### 📱 व्हॉट्सॲप चॅट पूर्वावलोकन (WhatsApp Message Feed)")
            for item in reversed(st.session_state.whatsapp_sim_history):
                with st.container():
                    st.markdown(f"**👤 शेतकरी ({item.get('sender_phone')}):**")
                    if item.get("type") == "audio":
                        st.markdown(f"🎙️ *[व्हॉइस नोट]* Transcript: *\"{item.get('transcript')}\"*")
                    else:
                        st.markdown(f"💬 {item.get('query')}")

                    st.markdown("**🌾 AgriVoice WhatsApp Reply:**")
                    st.markdown(f"""
                    <div class="whatsapp-bubble">
                        <pre style="white-space: pre-wrap; font-family: inherit; margin: 0;">{item.get('reply_text')}</pre>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"🔒 Hashed User ID: `{item.get('assistant_result', {}).get('user_id_hash', 'N/A')}`")
                    st.markdown("---")

    with tab_wa_guide:
        st.markdown("### 📖 Meta WhatsApp Business Cloud API थेट कनेक्ट कसे करावे")
        st.markdown("""
        अधिकृत WhatsApp Cloud API द्वारे थेट लाइव्ह मेसेजिंग सुरू करण्यासाठी खालील सोप्या पायऱ्या फॉलो करा:

        1. **Meta for Developers खाते तयार करा:**
           - [developers.facebook.com](https://developers.facebook.com/) ला भेट द्या.
           - नवीन **Business App** तयार करा आणि **WhatsApp** प्रॉडक्ट जोडा.
        2. **क्रेडेन्शियल्स मिळवा:**
           - **Phone Number ID**: WhatsApp -> API Setup पेजवरून कॉपी करा.
           - **Temporary or Permanent Access Token**: कॉपी करा.
        3. **`.env` फाइलमध्ये नमूद करा:**
           ```bash
           WHATSAPP_PHONE_NUMBER_ID=109283746592837
           WHATSAPP_ACCESS_TOKEN=EAAG...
           WHATSAPP_VERIFY_TOKEN=agri_assistant_verify_token
           ```
        4. **वेबहुक सर्व्हर सुरू करा:**
           ```powershell
           .\\.venv\\Scripts\\python.exe -m src.channel.whatsapp_server --port 8000
           ```
        5. **ngrok किंवा Cloudflare Tunnel द्वारे सार्वजनिक URL तयार करा:**
           ```powershell
           ngrok http 8000
           ```
        6. **Meta Console मध्ये Webhook URL कॉन्फिगर करा:**
           - Callback URL: `https://<your-ngrok-url>.ngrok-free.app/webhook`
           - Verify Token: `agri_assistant_verify_token`
           - Webhook Fields: `messages` सबस्क्राइब करा.
        """)


# ==============================================================================
# VIEW 4: Quality Benchmark & Automated Metrics Dashboard
# ==============================================================================
elif nav_option.startswith("📈"):
    st.markdown("""
    <div class="main-header">
        <h1>📈 गुणवत्ता मूल्यमापन व बेंचमार्क (Quality Evaluation Dashboard)</h1>
        <p>Sagveek Technologies ब्लूप्रिंटनुसार अचूकता, विश्वसनीयता आणि सुरक्षित नकार मोजमाप</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚀 Run Live 10-Case Automated Benchmark Suite"):
        with st.spinner("मूल्यमापन सुरू आहे (Evaluating benchmark test cases)..."):
            runner = AgriculturalBenchmarkRunner(assistant)
            metrics = runner.run_benchmark()

            col_met1, col_met2, col_met3 = st.columns(3)
            with col_met1:
                st.metric("Safe Refusal & Routing Accuracy", f"{metrics['refusal_and_routing_accuracy']}%", "Blueprint Target: >= 90%")
            with col_met2:
                st.metric("Retrieval Recall@5", f"{metrics['retrieval_recall_at_5']}%", "Blueprint Target: >= 85%")
            with col_met3:
                st.metric("Grounding Faithfulness", f"{metrics['average_faithfulness']}%", "Blueprint Target: >= 85%")

            st.markdown("### 📋 चाचणी निकाल तपशील (Test Cases Breakdown)")
            table_data = []
            for r in metrics["detailed_results"]:
                table_data.append({
                    "Case ID": r["case_id"],
                    "Category": r["category"],
                    "Query": r["query"],
                    "Expected Decision": r["expected"],
                    "Actual Decision": r["actual"],
                    "Status": "✅ PASS" if r["passed"] else "❌ FAIL"
                })
            st.dataframe(table_data, use_container_width=True)


# ==============================================================================
# VIEW 5: Admin Console & Expert Review Loop (Module 14)
# ==============================================================================
elif nav_option.startswith("🔐"):
    st.markdown("""
    <div class="main-header">
        <h1>🔐 प्रशासक कक्ष व कृषी तज्ज्ञ पुनरावलोकन (Admin Console & Review Loop)</h1>
        <p>Module 14: दस्तऐवज पडताळणी, इंडेक्स व्यवस्थापन आणि वापरकर्ता प्रतिसाद</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.admin_authenticated:
        with st.form("admin_login_form"):
            st.markdown("### 🔑 प्रशासक लॉगिन (Administrator Authentication)")
            admin_user = st.text_input("Username", value="admin")
            admin_pwd = st.text_input("Password", type="password")
            submitted = st.form_submit_button("लॉगिन करा (Login)")

            if submitted:
                if AdminService.verify_credentials(admin_user, admin_pwd):
                    st.session_state.admin_authenticated = True
                    st.success("✅ यशस्वीरित्या लॉगिन झाले!")
                    st.rerun()
                else:
                    st.error("❌ अमान्य क्रेडेन्शियल! (Invalid username or password. Default: admin / admin@agri2026)")
        st.stop()

    st.sidebar.button("🚪 Logout (बाहेर पडा)", on_click=lambda: st.session_state.update(admin_authenticated=False))

    tab_admin_docs, tab_admin_upload, tab_admin_telemetry = st.tabs([
        "📑 दस्तऐवज यादी व पुनरावलोकन (Document Review)",
        "📤 नवीन PDF अपलोड करा (Upload Advisory PDF)",
        "📊 सिस्टम टेलिमेट्री व फीडबॅक (Telemetry & Feedback)"
    ])

    with tab_admin_docs:
        inv = admin_service.get_document_inventory()
        st.markdown(f"**एकूण दस्तऐवज:** {inv['total_documents']} (प्रलंबित / Pending: {len(inv['pending'])}, मंजूर / Approved: {len(inv['approved'])})")

        if inv["pending"]:
            st.markdown("#### ⏳ पुनरावलोकनासाठी प्रलंबित दस्तऐवज (Pending Approval Queue)")
            for doc in inv["pending"]:
                with st.container():
                    st.warning(f"📄 **{doc['title']}** (ID: `{doc['doc_id']}`)")
                    st.caption(f"स्रोत: {doc['source']} | पिक: {doc['crop']} | तुकडे: {doc['chunk_count']}")
                    c_app, c_rej = st.columns([1, 1])
                    with c_app:
                        if st.button("✅ मंजूर करा (Approve Document)", key=f"app_{doc['doc_id']}"):
                            admin_service.approve_document(doc['doc_id'], approved_by="Chief Agronomist")
                            st.success(f"{doc['title']} मंजूर झाले आणि शोध इंडेक्समध्ये जोडले गेले!")
                            st.rerun()
                    with c_rej:
                        if st.button("❌ नाकारा (Reject Document)", key=f"rej_{doc['doc_id']}"):
                            admin_service.reject_document(doc['doc_id'], reason="Unverified")
                            st.error(f"{doc['title']} नाकारले गेले.")
                            st.rerun()
                    st.markdown("---")

        st.markdown("#### ✅ मंजूर दस्तऐवज (Active Searchable Knowledge Base)")
        for doc in inv["approved"]:
            st.markdown(f"- 🏛️ **{doc['title']}** | पिक: `{doc['crop']}` | आवृत्ती: `v{doc['version']}` | तुकडे: `{doc['chunk_count']}`")

    with tab_admin_upload:
        st.markdown("### 📤 नवीन कृषी सल्लागार PDF जोडा")
        with st.form("upload_pdf_form"):
            pdf_file = st.file_uploader("अधिकृत PDF दस्तऐवज निवडा", type=["pdf"])
            doc_id = st.text_input("Document ID", value=f"DOC_ADVISORY_{datetime.now().strftime('%Y%m%d%H%M')}")
            doc_title = st.text_input("Title (शीर्षक)", value="नवीन पीक व्यवस्थापन सल्ला")
            doc_publisher = st.text_input("Publisher (संस्था)", value="ICAR / KVK")
            doc_source = st.text_input("Source (स्रोत)", value="कृषी विद्यापीठ सल्लागार बुलेटिन २०२६")
            doc_crop = st.selectbox("Crop (पिक)", ["Cotton", "Wheat", "Soybean", "Onion", "Rice", "Sugarcane", "General"])
            doc_region = st.selectbox("Region (प्रदेश)", ["Maharashtra", "Punjab", "Madhya Pradesh", "National"])
            auto_app = st.checkbox("थेट मंजूर करा (Auto-Approve immediately for RAG retrieval)", value=False)

            upload_submit = st.form_submit_button("अपलोड व इंडेक्स करा (Ingest Document)")
            if upload_submit and pdf_file is not None:
                meta = DocumentMetadata(
                    doc_id=doc_id,
                    title=doc_title,
                    source=doc_source,
                    publisher=doc_publisher,
                    crop=doc_crop,
                    region=doc_region,
                    publication_date=datetime.now().strftime("%Y-%m-%d"),
                    approval_status="approved" if auto_app else "pending"
                )
                res = admin_service.upload_and_ingest_pdf(
                    file_bytes=pdf_file.read(),
                    filename=pdf_file.name,
                    metadata=meta,
                    auto_approve=auto_app
                )
                st.success(f"✅ यशस्वीरित्या अपलोड झाले! {res['chunks_created']} तुकडे तयार करण्यात आले.")
                st.rerun()

    with tab_admin_telemetry:
        tel = admin_service.get_system_telemetry()
        st.markdown("### 📊 सिस्टम वापर व इंडेक्स आकडेवारी")
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.metric("एकूण दस्तऐवज", tel["total_documents"])
            st.metric("मंजूर तुकडे (FAISS)", tel["approved_chunks_in_faiss"])
        with col_t2:
            st.metric("FAISS इंडेक्स नोंदी", tel["faiss_index_entries"])
            st.metric("BM25 कॉर्पस आकार", tel["bm25_corpus_size"])
        with col_t3:
            st.metric("वापरकर्ता फीडबॅक संख्या", tel["feedback_total"])
            st.metric("सकारात्मक प्रतिसाद", f"👍 {tel['feedback_positive']} / 👎 {tel['feedback_negative']}")

        st.markdown("---")
        st.markdown("#### 💬 शेतकरी प्रतिसाद नोंदी (Recent Feedback Logs)")
        fb_logs = admin_service.get_feedback_logs()
        if fb_logs:
            st.dataframe(fb_logs, use_container_width=True)
        else:
            st.info("अद्याप कोणताही वापरकर्ता प्रतिसाद नोंदवला गेलेला नाही.")
