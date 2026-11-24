# WhatsApp Business Cloud API Setup Guide

## AgriVoice — Voice-First Multilingual Agricultural Assistant

This guide explains how to connect the AgriVoice application to the official **Meta WhatsApp Business Cloud API**. Follow each step carefully. No programming experience is required for the setup steps.

> **Current status**: The WhatsApp backend is fully implemented and tested locally. All webhook handling, security signatures, and message processing logic is ready. You only need to obtain Meta credentials and register the webhook URL once your Meta Business Portfolio is approved.

---

## 📋 What You Will Need

| Credential | Where to Find It | Required? |
|---|---|---|
| `WHATSAPP_PHONE_NUMBER_ID` | Meta for Developers → Your App → WhatsApp → API Setup | ✅ Yes |
| `WHATSAPP_ACCESS_TOKEN` | Same page → Temporary or Permanent token | ✅ Yes |
| `WHATSAPP_APP_SECRET` | App Settings → Basic → App Secret → click **Show** | ✅ Strongly recommended |
| `WHATSAPP_VERIFY_TOKEN` | A string you choose yourself (default: `agri_assistant_verify_token`) | ✅ Yes |
| `WHATSAPP_API_VERSION` | Recommended: `v19.0` (already set as default) | Optional |

---

## 🔑 Step 1 — Obtain Meta Credentials

### 1.1 — Wait for Business Portfolio Approval

If your Facebook account is new, Meta temporarily restricts Business Portfolio creation. This is a Meta account-level hold, not an application problem. Options:

- Wait 7–30 days and retry at [business.facebook.com](https://business.facebook.com).
- Use an older Facebook account that already has a verified Business Portfolio.
- Request a review through Meta Business Support at [facebook.com/business/help](https://www.facebook.com/business/help).

### 1.2 — Create a Meta App

1. Go to [developers.facebook.com](https://developers.facebook.com) and sign in.
2. Click **My Apps → Create App**.
3. Select **Business** as the app type.
4. Choose your Business Portfolio.
5. Give the app a name (e.g., `AgriVoice Assistant`).
6. Click **Create App**.

### 1.3 — Add WhatsApp to Your App

1. In your app dashboard, click **Add a Product**.
2. Find **WhatsApp** and click **Set Up**.
3. Follow the prompts to add a phone number (you can use Meta's free test number during development).

### 1.4 — Collect the Credentials

Go to **WhatsApp → API Setup** in your app dashboard:

- Copy **Phone Number ID** → this is your `WHATSAPP_PHONE_NUMBER_ID`.
- Copy the **Temporary Access Token** → this is your `WHATSAPP_ACCESS_TOKEN`.

Go to **App Settings → Basic**:

- Find **App Secret** and click **Show** → this is your `WHATSAPP_APP_SECRET`.

---

## ⚙️ Step 2 — Configure the `.env` File

1. Open a file manager and navigate to `c:\Users\Sakshi\OneDrive\Desktop\agri_assistant\`.
2. Find the file named `.env.example`.
3. Make a copy of it and rename the copy to `.env` (remove the `.example` part).
4. Open `.env` with Notepad (right-click → Open with → Notepad).
5. Find the WhatsApp section and fill in your values:

```env
# ─── WhatsApp Business Cloud API ──────────────────────────────────────
WHATSAPP_ACCESS_TOKEN=your_access_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WHATSAPP_VERIFY_TOKEN=agri_assistant_verify_token
WHATSAPP_APP_SECRET=your_app_secret_here
WHATSAPP_API_VERSION=v19.0
```

6. Save the file and close Notepad.

> ⚠️ **Never share your `.env` file or post it online.** It contains private credentials.

---

## 🚀 Step 3 — Run the Webhook Server Locally

Open **PowerShell** and run:

```powershell
cd c:\Users\Sakshi\OneDrive\Desktop\agri_assistant
.\.venv\Scripts\python.exe -m src.channel.whatsapp_server --port 8000
```

You should see output like:

```
AgriVoice WhatsApp Webhook Server
Port      : 8000
HMAC Sig  : ENFORCED (app_secret is set)
Endpoints : GET  /webhook  — Meta verification
            POST /webhook  — Incoming messages
            GET  /health   — Health check
Server started. Press Ctrl+C to stop.
```

If `WHATSAPP_APP_SECRET` is not configured yet, you will see `OPTIONAL` instead of `ENFORCED`. The server still works for testing.

---

## 🌐 Step 4 — Expose the Local Server with ngrok

Meta needs a **public HTTPS URL** to reach your webhook. Use **ngrok** to create a secure tunnel.

### 4.1 — Install ngrok

Download from [ngrok.com/download](https://ngrok.com/download). Extract the `.exe` file to a folder (e.g., `C:\ngrok\`).

### 4.2 — Start the Tunnel

In a **new** PowerShell window (keep the webhook server running in the first window):

```powershell
C:\ngrok\ngrok.exe http 8000
```

You will see output like:

```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

Copy the `https://...ngrok-free.app` URL — you will need it in the next step.

> **Note**: Each time you restart ngrok, you get a new URL. You will need to update the webhook URL in Meta Developer Console each time, unless you have a paid ngrok plan with a fixed domain.

---

## 📡 Step 5 — Register the Webhook in Meta Developer Console

1. Go to [developers.facebook.com](https://developers.facebook.com) → Your App → **WhatsApp → Configuration**.
2. Find the **Webhooks** section and click **Edit**.
3. Fill in:
   - **Callback URL**: `https://abc123.ngrok-free.app/webhook` (use your actual ngrok URL)
   - **Verify Token**: `agri_assistant_verify_token` (or whatever you put in `.env`)
4. Click **Verify and Save**.

If the verification succeeds, you will see a checkmark. If it fails:
- Make sure your webhook server is running (Step 3).
- Make sure ngrok is running (Step 4).
- Make sure the Verify Token matches exactly (case-sensitive).

5. Under **Webhook Fields**, find **messages** and click **Subscribe**.

---

## 💬 Step 6 — Send Your First Test Message

### Option A — Use Meta's Test Tool
In **WhatsApp → API Setup**, Meta provides a **Send Message** tool. Use it to send a test message to your registered test phone number.

### Option B — WhatsApp from Your Phone
1. Add the test phone number Meta provided to your phone contacts.
2. Open WhatsApp and message it: `आज गेहूं का भाव क्या है?`

### Option C — Use AgriVoice Streamlit Simulator (No Credentials Needed)
In the Streamlit app, go to **WhatsApp Channel** tab. The built-in simulator lets you test the full AI pipeline without real Meta credentials.

---

## ✅ Step 7 — Verify It Worked

Watch the PowerShell window where the webhook server is running. When a message arrives, you will see logs like:

```
[INFO] POST /webhook — 1 messages received
[INFO] Processing WhatsApp text message from +91XXXXXXXXXX (hi)
[INFO] Sending WhatsApp reply to +91XXXXXXXXXX
```

If the reply is sent successfully, the farmer receives the response in WhatsApp.

---

## 🎤 Voice Messages (OGG Audio Notes)

WhatsApp sends voice notes as OGG/Opus audio files. The AgriVoice backend:

1. Downloads the audio using `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID`.
2. Converts it for the ASR (Speech Recognition) pipeline.
3. Returns a text reply in the farmer's detected language.

> **Requirement**: Both `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` must be configured to download voice notes. Without credentials, the farmer receives a helpful fallback message with the Kisan Call Centre number (1800-180-1551).

---

## 🔒 Security — HMAC Signature Verification

When `WHATSAPP_APP_SECRET` is set in `.env`, the server validates every incoming request using **HMAC-SHA256** to confirm it genuinely came from Meta. This prevents fake webhook calls.

| `WHATSAPP_APP_SECRET` | Behavior |
|---|---|
| ✅ Configured | Every POST request must have a valid `X-Hub-Signature-256` header or it is rejected with HTTP 401 |
| ❌ Not configured | Signature check is skipped — safe for local development only |

**Always configure `WHATSAPP_APP_SECRET` in production.**

---

## 🏥 Health Check Endpoint

While the server is running, you can check its status:

```powershell
# In a new PowerShell window
Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing | Select-Object -Expand Content
```

Expected response:
```json
{
  "status": "ok",
  "service": "AgriVoice WhatsApp Webhook",
  "phone_number_id_set": true,
  "access_token_set": true,
  "app_secret_set": true,
  "verify_token_set": true,
  "api_version": "v19.0"
}
```

---

## 🔄 Running Both Streamlit and WhatsApp Together

You can run the Streamlit web app and the WhatsApp webhook server **at the same time** — they share the same AI backend.

**Terminal 1 — Streamlit Web App:**
```powershell
cd c:\Users\Sakshi\OneDrive\Desktop\agri_assistant
.\.venv\Scripts\streamlit.exe run src/app.py
```

**Terminal 2 — WhatsApp Webhook Server:**
```powershell
cd c:\Users\Sakshi\OneDrive\Desktop\agri_assistant
.\.venv\Scripts\python.exe -m src.channel.whatsapp_server --port 8000
```

**Terminal 3 — ngrok Tunnel (after getting Meta credentials):**
```powershell
C:\ngrok\ngrok.exe http 8000
```

---

## 🚨 Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| Meta webhook verification fails | Verify Token mismatch or server not running | Check `.env` token and confirm server is running |
| `HTTP 401 Unauthorized` on POST | HMAC signature invalid | Check `WHATSAPP_APP_SECRET` matches your Meta App Secret exactly |
| Voice messages not processed | Missing credentials or OGG not supported | Ensure `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` are set |
| Server shows `OPTIONAL` HMAC | `WHATSAPP_APP_SECRET` not configured | Add App Secret to `.env` |
| ngrok URL changes after restart | Free ngrok plan | Update webhook URL in Meta Console each time, or get a fixed ngrok domain |
| Business Portfolio blocked | Facebook account is new | Wait and retry, or use an older account |

---

## 📞 Support Contacts

- **Kisan Call Centre (Free)**: 1800-180-1551
- **Meta Developer Support**: [developers.facebook.com/support](https://developers.facebook.com/support)
- **ngrok Documentation**: [ngrok.com/docs](https://ngrok.com/docs)
- **WhatsApp Business API Docs**: [developers.facebook.com/docs/whatsapp](https://developers.facebook.com/docs/whatsapp)

---

## 📊 WhatsApp Integration Status

| Feature | Status |
|---|---|
| Webhook GET verification (hub.mode / hub.challenge) | ✅ Implemented & Tested |
| HMAC-SHA256 payload signature verification | ✅ Implemented & Tested |
| Inbound text message handling | ✅ Implemented & Tested |
| Inbound voice message handling (OGG/Opus) | ✅ Implemented (credential-gated) |
| Duplicate webhook delivery protection | ✅ Implemented & Tested |
| Outbound message dispatch via Meta Graph API | ✅ Implemented (requires credentials) |
| Multilingual support (Hindi, Marathi, English) | ✅ Implemented & Tested |
| Banned chemical / safety guardrails | ✅ Implemented & Tested |
| Health check endpoint | ✅ Implemented |
| Live Meta API communication | ⏳ Pending — requires Business Portfolio approval |
| OGG voice note download & conversion | ⏳ Pending — requires live credentials |

---

*Last updated: Phase 6 completion — 131/131 tests passing.*
