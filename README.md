# Voice-First Multilingual Agricultural Assistant (कृषि वाणी)

An institutional, voice-first agricultural assistant engineered for Indian farmers. It accepts spoken voice notes in **Hindi**, **Marathi**, and **English**, retrieves verified crop advisories from official institutional sources (ICAR, KVK, State Agricultural Universities), fetches live mandi prices and agromet advisories, and synthesizes short, spoken-style grounded answers while enforcing a strict **Zero-Guessing safe refusal policy** and **Multi-Signal Agricultural Safety Guardrails**.

---

## 🌾 Core Capabilities & Architecture (Modules 01 – 14)

1. **Voice & WhatsApp Ingestion (Module 01 & 02)**:
   - **Native Web Voice Recording**: Browser microphone recording powered by Streamlit's `st.audio_input` and file uploader (`.wav`, `.mp3`, `.ogg`).
   - **WhatsApp Business Cloud API Adapter**: Credential-gated webhook handler parsing inbound text and audio payloads, adhering to Meta Graph API v19.0.
   - **Audio Preprocessing & VAD**: 16 kHz 16-bit mono PCM standardization and RMS voice activity detection for silence trimming.
2. **Multilingual Speech Recognition & Language Detection (Module 02 & 03)**:
   - Multilingual ASR for Hindi (`hi-IN`), Marathi (`mr-IN`), and English (`en-IN`).
   - Indic script character set heuristic language detector distinguishing Devanagari Hindi vs. Marathi grammatical markers.
   - ASR transcription confidence scoring with low-confidence repeat fallbacks.
3. **Multilingual NLU & Dynamic Query Routing (Module 03 & 04)**:
   - Intent classification: `mandi_price`, `weather`, `pest_disease`, `crop_advice`, `government_scheme`, and `out_of_scope`.
   - Entity extraction: Recognizes crops, districts, and pest/disease entities with inflected Indic forms.
   - Glossary manager with localized agricultural terminology (Cotton/Wheat/Onion/Soybean/Pink Bollworm/Yellow Rust).
4. **Institutional Knowledge Ingestion & Hybrid RAG (Module 05, 06 & 07)**:
   - PyMuPDF ingestion extracting clean text chunks with full institutional metadata.
   - Multi-layer approval workflow: Documents default to `pending` and are strictly excluded from search until approved by an authorized agronomist.
   - Hybrid retrieval combining FAISS dense vector search and BM25 sparse keyword search via Reciprocal Rank Fusion (RRF).
5. **Live Mandi Prices & Agromet Weather (Module 08)**:
   - **Mandi Prices**: Connects to Agmarknet / Data.gov.in schema providing modal, minimum, and maximum prices (`₹/Quintal`) with 12-hour local caching.
   - **Weather Advisories**: Open-Meteo forecast integration paired with IMD Agromet Advisory guidelines.
6. **Grounded Answer Generation & Safe Refusal (Module 09 & 10)**:
   - Concise, spoken-style answers strictly grounded in verified institutional citations.
   - Zero-guessing refusal: If evidence is missing or confidence is low, safely refuses and refers to the Kisan Call Centre (1800-180-1551).
7. **Multi-Signal Confidence Gate & Agricultural Guardrails (Module 10 & 12)**:
   - Composite confidence gate:
     $$\text{Composite} = 0.20 \times \text{ASR} + 0.20 \times \text{Intent} + 0.35 \times \text{Retrieval (RRF)} + 0.25 \times \text{Grounding}$$
   - Banned chemical detection (Monocrotophos, Endosulfan, Paraquat, etc.).
   - Dosage hallucination blocking: Strict regex scanning blocking unverified chemical quantities.
   - Mandatory CIBRC regulatory disclaimers and adversarial prompt injection defense.
8. **Indic Text-to-Speech (Module 11)**:
   - Synthesizes audio responses in Hindi and Marathi using `gTTS` with offline audio synthesis fallback.
9. **Automated Quality Evaluation Metrics (Module 13)**:
   - Word Error Rate (WER), Precision@k, Recall@k, MRR, Answer Faithfulness, and Safe Refusal Accuracy.
10. **Unified Web Application & Admin Review Console (Module 14)**:
    - Responsive Streamlit frontend with custom agricultural green-and-white theme.
    - Password-protected Admin Console (SHA-256 authenticated) for PDF ingestion, approval queues, user feedback audit logs, and system telemetry.

---

## 📁 Project Directory Structure

```text
agri_assistant/
│
├── .venv/                              # Python 3.11 virtual environment
├── Voice_First_Agri_Assistant_Problem_Statement.pdf
│
├── data/
│   ├── raw_documents/                  # Authentic prototype PDFs (ICAR, KVK)
│   ├── processed_chunks/               # Cleaned JSON chunks & document registry
│   ├── vector_db/                      # FAISS vector database files
│   ├── glossary/                       # Multilingual agricultural glossary
│   └── cache/                          # Mandi prices, weather & audio cache
│
├── docs/
│   ├── USER_GUIDE.md                   # Guide for farmers and end-users
│   ├── ADMIN_GUIDE.md                  # Guide for agronomists and administrators
│   └── EVALUATION_REPORT.md            # Benchmark evaluation report
│
├── src/
│   ├── admin/                          # M14: Admin console service, review queue, telemetry
│   ├── asr/                            # M02: Audio preprocessor, VAD, ASR transcriber, language detector
│   ├── channel/                        # M01: Microphone recorder, WhatsApp Cloud client, privacy manager
│   ├── core/                           # Unified VoiceAgriculturalAssistant orchestrator
│   ├── evaluation/                     # M13: Metrics calculator & benchmark runner
│   ├── generation/                     # M09: Grounded Gemini generation with citations
│   ├── guardrails/                     # M10 & M12: Confidence gate, chemical safety, injection defense
│   ├── knowledge/                      # M05 & M06: Ingestion, chunking & RAG service
│   ├── nlu/                            # M03: Intent classifier, entity extractor, query router
│   ├── retrieval/                      # M07: FAISS vector, BM25 & Hybrid RRF
│   ├── tools/                          # M08: Mandi price tool & Open-Meteo weather tool
│   ├── translation/                    # M04: Glossary manager & translation
│   ├── tts/                            # M11: Text-to-Speech synthesis & audio player
│   └── app.py                          # Unified Streamlit Web Application (Phase 6)
│
├── scripts/
│   ├── generate_sample_pdfs.py         # Generates authentic prototype advisory PDFs
│   ├── demo_phase2_rag.py              # Interactive Phase 2 text RAG demo
│   ├── demo_phase3_voice.py            # Interactive Phase 3 voice interaction demo
│   ├── demo_phase4_live_tools.py       # Interactive Phase 4 live tools & NLU demo
│   └── demo_phase5_guardrails_and_eval.py # Interactive Phase 5 safety guardrails & benchmark demo
│
├── tests/
│   ├── test_phase2.py                  # Phase 2 test suite (10 tests)
│   ├── test_phase3.py                  # Phase 3 voice test suite (12 tests)
│   ├── test_phase4.py                  # Phase 4 live tools & NLU test suite (15 tests)
│   ├── test_phase5.py                  # Phase 5 guardrails & metrics test suite (16 tests)
│   ├── test_phase6.py                  # Phase 6 app, admin, WhatsApp & integration (54 tests)
│   ├── test_whatsapp.py               # WhatsApp security, webhook & message handling (22 tests)
│   └── test_twilio.py                 # Twilio WhatsApp sandbox & TwiML integration (20 tests)
│
├── requirements.txt                    # Project dependencies
├── .env.example / .env                 # Safe environment configuration
├── .gitignore                          # Exclusions for git
├── WHATSAPP_SETUP.md                   # Meta WhatsApp Cloud API setup guide
└── TWILIO_SETUP.md                     # Twilio WhatsApp Sandbox quickstart guide
```

---

## 🚀 Getting Started on Windows

### 1. Prerequisites & Environment Setup
Ensure Python 3.11 is installed. Activate the project virtual environment in Windows PowerShell:
```powershell
cd c:\Users\Sakshi\OneDrive\Desktop\agri_assistant
.\.venv\Scripts\Activate.ps1
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and configure your API keys (optional for offline testing):
```powershell
cp .env.example .env
```
*(The system automatically runs in deterministic local offline mode if API keys are omitted).*

---

## 💻 Launching the Streamlit Web Application

To run the full agricultural assistant with the farmer chat interface, voice recording, live dashboard, benchmark runner, and admin console:

```powershell
.\.venv\Scripts\streamlit.exe run src/app.py
```

The application will open in your default browser at:
**`http://localhost:8501`**

### Application Views & Navigation:
1. **🎙️ Farmer Assistant (शेतकरी मित्र)**:
   - Voice note recording (`st.audio_input`) or audio file upload (`.wav`, `.mp3`).
   - Multilingual text chat in Hindi, Marathi, or English.
   - Audio playback of responses, verified institutional citations, and feedback buttons.
2. **📊 Live Mandi & Weather (मंडी व हवामान)**:
   - Filter commodity prices by crop and district with min/max/modal pricing.
   - District-level weather forecasts and agricultural agromet warnings.
3. **📱 WhatsApp Channel (व्हॉट्सॲप चॅनेल)**:
   - View Meta Cloud API configuration status (Live vs. Safe Offline Mode).
   - Inspect webhook endpoints (`/webhook`, `/health`).
   - Interactive WhatsApp Message Simulator: Test incoming text & voice messages without needing an external webhook or Meta account.
4. **📈 Quality Benchmark (गुणवत्ता मूल्यमापन)**:
   - 10-case automated test suite checking routing, retrieval recall, and grounding faithfulness.
5. **🔐 Admin Console (प्रशासक कक्ष)**:
   - Protected by SHA-256 password authentication.
   - **Default Credentials**: Username: `admin` | Password: `admin@agri2026`
   - Upload new advisory PDFs, review/approve pending documents, and view real-time system telemetry.

---

## 📱 Launching the WhatsApp Business Cloud API Server

The WhatsApp Webhook server listens for Meta's verification handshake and incoming messages:

```powershell
.\.venv\Scripts\python.exe -m src.channel.whatsapp_server --port 8000
```

- **Health check**: `http://localhost:8000/health`
- **Webhook endpoint**: `http://localhost:8000/webhook`

Both the Streamlit app and the WhatsApp server share the **identical underlying agricultural AI backend**, ensuring consistent advisories, safety guardrails, and market data.

---

## 🧪 Running the Automated Test Suite (151 Total Tests)

Run all unit, integration, and regression tests across all phases:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

### Test Suite Breakdown:
| Test Suite | Focus Area | Tests | Status |
|---|---|:---:|:---:|
| `tests/test_phase2.py` | PyMuPDF Ingestion, FAISS, BM25, RRF Hybrid RAG | 10 | ✅ PASS |
| `tests/test_phase3.py` | Audio Preprocessing, VAD, Speech Recognition, TTS | 12 | ✅ PASS |
| `tests/test_phase4.py` | Agmarknet Mandi Prices, Open-Meteo Weather, NLU Router | 17 | ✅ PASS |
| `tests/test_phase5.py` | Multi-Signal Gate, Chemical Guardrails, Benchmark | 16 | ✅ PASS |
| `tests/test_phase6.py` | Admin Console, WhatsApp Adapter & Webhook, App, Regressions | 54 | ✅ PASS |
| `tests/test_whatsapp.py` | Meta HMAC Security, Deduplication, Inbound/Outbound, Voice Fallback | 22 | ✅ PASS |
| `tests/test_twilio.py` | Twilio HMAC-SHA1 Security, TwiML Response, Multilingual Routing | 20 | ✅ PASS |
| **Total** | **All 14 Modules Integrated Across Web & Both WhatsApp Gateways** | **151** | **✅ 100% PASS** |

---

## 🟢 Twilio WhatsApp Sandbox Integration (Recommended for College Demo)

The system includes a dedicated adapter for the Twilio WhatsApp Sandbox (`src/channel/twilio_client.py`):
- **TwiML Generation**: Returns valid `<Response><Message>...</Message></Response>` XML directly in the HTTP 200 response for instant WhatsApp replies without separate outbound REST calls.
- **HMAC-SHA1 Signature Validation**: Validates `X-Twilio-Signature` using `TWILIO_AUTH_TOKEN`.
- **Deduplication Guard**: MessageSid cache prevents double-processing if Twilio retries webhook delivery.
- **Privacy Protection**: Anonymizes farmer phone numbers with irreversible SHA-256 hashes before logging.
- **Shared Agricultural Intelligence**: Evaluates queries against the exact same verified RAG, Agmarknet mandi data, and IMD/Open-Meteo weather services.

> 📖 See [`TWILIO_SETUP.md`](TWILIO_SETUP.md) for step-by-step instructions to connect your personal phone in under 2 minutes.

---

## 📱 WhatsApp Business Cloud API Integration (Module 01)

The system includes a production-ready adapter for the Meta WhatsApp Business Cloud API (`src/channel/whatsapp_client.py`):
- **Webhook Verification**: Validates Meta webhook subscription handshake (`GET /webhook`).
- **HMAC-SHA256 Security**: Every inbound POST is signature-verified against `WHATSAPP_APP_SECRET`; requests with invalid signatures are rejected with HTTP 401.
- **Inbound Message Parsing**: Extracts sender phone number, message text, and voice audio media IDs (`POST /webhook`).
- **Duplicate Delivery Protection**: Bounded 5000-entry deduplication cache prevents reprocessing the same message_id.
- **Privacy Enforcement**: All phone numbers are hashed using SHA-256 before storage or telemetry logging.
- **Credential-Gated Safeguard**: When external credentials (`WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`) are absent, the adapter operates safely in diagnostic mode without network errors.
- **Configurable API Version**: Defaults to `v19.0`; override with `WHATSAPP_API_VERSION` env var.

> 📖 See [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md) for the complete beginner-friendly guide to obtaining Meta credentials and registering the webhook.

---

## 🔒 Privacy & Safety Compliance
- **Zero-Guessing Policy**: Strict refusal for unverified chemical dosages or unapproved advisories.
- **Helpline Integration**: All refusals and safety alerts direct farmers to the toll-free **Kisan Call Centre: 1800-180-1551**.
- **Data Protection**: Temporary audio recordings are automatically cleaned up, and user identifiers are irreversibly hashed.
