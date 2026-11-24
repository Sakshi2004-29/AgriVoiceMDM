# AgriVoice Admin Console & Review Guide (Module 14)

This guide is intended for institutional agricultural officers, agronomists, and system administrators who manage the agricultural knowledge base and review farmer feedback.

---

## 🔐 Administrator Authentication

1. In the sidebar, select **🔐 Admin Console (प्रशासक कक्ष)**.
2. Enter your administrator credentials:
   - **Username**: `admin`
   - **Password**: `admin@agri2026`
3. Click **लॉगिन करा (Login)**. The credentials are authenticated using salted SHA-256 password hashing.

---

## 📑 Managing the Agricultural Knowledge Base

### 1. Document Inventory & Review Queue
Under the **📑 दस्तऐवज यादी व पुनरावलोकन (Document Review)** tab:
- **Pending Queue (प्रलंबित दस्तऐवज)**: Displays newly uploaded documents that have not yet been approved. These documents are strictly excluded from search indexes until reviewed.
  - Click **✅ मंजूर करा (Approve Document)** to approve the document and automatically index its chunks into FAISS and BM25.
  - Click **❌ नाकारा (Reject Document)** to reject inaccurate or unverified material.
- **Approved Documents (मंजूर दस्तऐवज)**: Lists all active documents currently queried by the hybrid RAG system.

### 2. Ingesting New Advisory PDFs
Under the **📤 नवीन PDF अपलोड करा (Upload Advisory PDF)** tab:
1. Select an authentic ICAR/KVK advisory PDF file (`.pdf`).
2. Provide metadata:
   - **Document ID**: Unique alphanumeric identifier (e.g. `DOC_ICAR_COTTON_2026`).
   - **Title**: Official document title.
   - **Publisher**: Publishing body (e.g., ICAR, KVK, State Agricultural University).
   - **Source**: Citation or bulletin issue number.
   - **Crop & Region**: Target crop and applicable state.
   - **Auto-Approve Checkbox**: Leave unchecked for standard review, or check to immediately add to the active RAG index.
3. Click **अपलोड व इंडेक्स करा (Ingest Document)**. PyMuPDF automatically parses, cleans, splits into structure-aware chunks, and saves the document metadata.

---

## 📊 System Telemetry & Feedback Logs

Under the **📊 सिस्टम टेलिमेट्री व फीडबॅक (Telemetry & Feedback)** tab:
- **Live Index Metrics**:
  - Total documents registered.
  - Number of approved chunks in FAISS vector database.
  - BM25 corpus size and active entries.
- **Farmer Feedback Audit Trail**:
  - Inspect positive (👍) and negative (👎) feedback submitted by farmers.
  - Review queries that received negative feedback to identify knowledge gaps or advisory updates needed.

---

## 📱 WhatsApp Business Cloud API Administration

Administrators can monitor and test the WhatsApp channel directly:
1. **API Status**: Check whether Meta credentials (`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`) are active or in safe offline diagnostic mode.
2. **Interactive Simulator**: Navigate to **📱 WhatsApp Channel** to test simulated inbound text and voice queries through the unified backend.
3. **Webhook Server**:
   Start the standalone webhook server to handle live callbacks from Meta:
   ```powershell
   .\.venv\Scripts\python.exe -m src.channel.whatsapp_server --port 8000
   ```
4. **Tunneling for Meta Webhook Registration**:
   Use ngrok or Cloudflare Tunnel to expose port 8000 to Meta:
   ```powershell
   ngrok http 8000
   ```
   Set Callback URL in Meta Developer Dashboard:
   - `https://<tunnel-id>.ngrok-free.app/webhook`
   - Verify Token: `agri_assistant_verify_token`

---

## 🔒 Security & Privacy Standards
- All farmer phone numbers and user identifiers are hashed using SHA-256 before telemetry logging.
- Passwords are never stored in plaintext.
- Unapproved documents are strictly prevented from appearing in retrieved evidence chunks.
