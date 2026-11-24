# Twilio WhatsApp Sandbox Setup Guide

## AgriVoice — Voice-First Multilingual Agricultural Assistant

This beginner-friendly guide walks you through connecting your **personal WhatsApp** to the AgriVoice assistant using the **Twilio WhatsApp Sandbox** for your college project demonstration.

---

## 📋 What You Need from Twilio

Log in to your [Twilio Console](https://console.twilio.com/):

| Credential | Where to Find It on Twilio Console | Purpose |
|---|---|---|
| **Account SID** | Dashboard → **Account Info** (`AC...`) | Identifies your Twilio account |
| **Auth Token** | Dashboard → **Account Info** (click **Show**) | Validates webhook signatures (`X-Twilio-Signature`) |
| **Sandbox Number** | Messaging → Try it out → Send a WhatsApp message (usually `+1 415 523 8886`) | The WhatsApp number you message |
| **Join Code** | Same page (e.g., `join word-word`) | Activates the sandbox session from your phone |

---

## ⚙️ Step 1 — Configure the `.env` File

Open `.env` in the project root (`c:\Users\Sakshi\OneDrive\Desktop\agri_assistant\.env`) with Notepad and add or update your Twilio settings:

```env
# ─── Twilio WhatsApp Sandbox ──────────────────────────────────────────
TWILIO_ACCOUNT_SID=your_actual_account_sid_here
TWILIO_AUTH_TOKEN=your_actual_auth_token_here
TWILIO_PHONE_NUMBER=whatsapp:+14155238886
# Optional: your public ngrok webhook URL for strict signature verification
TWILIO_WEBHOOK_URL=
```

> 🔒 **Security Notice**: Never commit your `.env` file to git or share your Auth Token publicly.

---

## 🚀 Step 2 — Start the AgriVoice Webhook Server

Open **PowerShell** in the project directory and run:

```powershell
cd c:\Users\Sakshi\OneDrive\Desktop\agri_assistant
.\.venv\Scripts\python.exe -m src.channel.whatsapp_server --port 8000
```

*(You can also use `.\.venv\Scripts\python.exe -m src.channel.twilio_server --port 8000`)*

You will see the startup banner:
```
🌾 AgriVoice WhatsApp Webhook Server listening on 0.0.0.0:8000
   ► Twilio WhatsApp Webhook: http://localhost:8000/twilio/webhook (POST -> TwiML)
   ► Meta WhatsApp Webhook  : http://localhost:8000/webhook (GET/POST)
   ► Health & Diagnostics   : http://localhost:8000/health
   Twilio Auth Check        : ENFORCED (or OPTIONAL if token not set)
```

Keep this window open!

---

## 🌐 Step 3 — Expose the Server with ngrok

Twilio needs a public HTTPS URL to deliver incoming WhatsApp messages to your local computer.

1. Download [ngrok](https://ngrok.com/download) if you haven't already.
2. In a **new PowerShell window**, run:

```powershell
ngrok http 8000
```

3. Look for the **Forwarding** line in the ngrok output:
```
Forwarding  https://xxxx-xx-xx-xx.ngrok-free.app -> http://localhost:8000
```
4. Copy that **HTTPS** URL (e.g. `https://xxxx-xx-xx-xx.ngrok-free.app`).

---

## 📡 Step 4 — Enter the Webhook URL into Twilio Console

1. In the Twilio Console, go to:
   **Messaging → Try it out → Send a WhatsApp message → Sandbox settings**
   *(Direct URL: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn)*
2. Find the setting:
   **"WHEN A MESSAGE COMES IN"**
3. Enter the exact URL and HTTP method:
   - **URL**: `https://<your-ngrok-domain>.ngrok-free.app/twilio/webhook`
   - **Method**: Select **`HTTP POST`**
4. Click **Save** at the bottom of the page.

---

## 💬 Step 5 — Test from Your Personal WhatsApp

1. Add the Twilio Sandbox phone number (`+1 415 523 8886`) to your phone contacts (e.g. "AgriVoice Sandbox").
2. Open WhatsApp on your phone and message the sandbox join code shown on your Twilio page:
   ```
   join <your-two-words>
   ```
   Twilio will immediately reply: *"You are all set! The sandbox will expire in 3 days."*
3. Now send any agricultural query!

### Sample Test Messages to Try:

| Language | Query to Send | Expected Response |
|---|---|---|
| **Hindi** | `पुणे मंडी में आज प्याज का भाव क्या है?` | Verified Pune APMC onion rate with min/max/modal prices and citations. |
| **Marathi** | `पुण्यात कांद्याचे भाव काय आहेत?` | Verified Pune APMC onion rate in Marathi. |
| **English** | `What is the price of cotton in Nagpur?` | Nagpur Mandi cotton rate in English. |
| **Crop Advice** | `कपास में गुलाबी सुंडी नियंत्रण के लिए क्या करें?` | Verified ICAR advisory on pheromone traps & summer plowing. |
| **Refusal Test** | `What is the price of dragon fruit in Pune?` | Safe refusal with Kisan Call Centre helpline (no false rice rates). |
| **Safety Test** | `मोनोक्रोटोफॉस कीटनाशक का स्प्रे कैसे करें?` | Safety alert for banned chemical with regulatory disclaimer. |

---

## 🛠️ How It Works (Behind the Scenes)

```
Farmer WhatsApp
      │
      ▼ (HTTP POST with Body, From, MessageSid)
Twilio WhatsApp Gateway
      │
      ▼ (HTTPS Forwarding)
ngrok Tunnel
      │
      ▼ (POST /twilio/webhook)
AgriVoice Webhook Server
      ├── 1. Validates X-Twilio-Signature (HMAC-SHA1)
      ├── 2. Parses phone number (anonymized with SHA-256)
      ├── 3. Routes query to VoiceAgriculturalAssistant
      │      (RAG + Agmarknet Mandi Prices + Open-Meteo Weather)
      └── 4. Formats localized reply with citations & Kisan helpline
      │
      ▼ (HTTP 200 with TwiML XML <Response><Message>...</Message></Response>)
Twilio WhatsApp Gateway
      │
      ▼
Farmer receives formatted WhatsApp message!
```

---

## 🚨 Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| Twilio error: *"11200 HTTP retrieval failure"* | ngrok is not running or port mismatch | Confirm server is running on port 8000 and `ngrok http 8000` is active. |
| HTTP 401 Unauthorized | `TWILIO_AUTH_TOKEN` mismatch | Check that your Auth Token in `.env` matches the token in Twilio Console. |
| No reply on phone | Sandbox session expired or phone not joined | Send `join <keyword>` again to `+1 415 523 8886`. |
| ngrok URL changed | Restarted ngrok | Free ngrok gives a new URL on restart. Update the URL in Twilio Console. |
