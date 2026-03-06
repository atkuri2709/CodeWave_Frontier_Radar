# How to Get SMTP Credentials for Digest Email

The app sends the daily digest (PDF) to recipients using SMTP. You need **one** of the options below.

---

## Option 1: Gmail (free) — Step-by-step

Gmail does **not** show “SMTP credentials” in one place. You use your **email address** and a **16-character App Password** (not your normal Gmail password). Follow these steps.

---

### Step 1: Turn on 2-Step Verification (required for App Passwords)

1. Open: **[Google Account → Security](https://myaccount.google.com/security)**  
   (Or: Google → profile picture → **Manage your Google Account** → **Security**.)
2. Under **“How you sign in to Google”**, find **“2-Step Verification”**.
3. Click it and turn it **On**. Complete the prompts (phone number, code, etc.).

You must complete this before App Passwords will appear.

---

### Step 2: Create an App Password (this is your “SMTP password”)

1. Open: **[App Passwords](https://myaccount.google.com/apppasswords)**  
   (Or: Security page → **2-Step Verification** → scroll down to **“App passwords”** → click it.)
2. You may need to sign in again.
3. Under **“Select app”**: choose **Mail**.
4. Under **“Select device”**: choose **Other (Custom name)** and type e.g. **Frontier AI Radar**.
5. Click **Generate**.
6. Google shows a **16-character password** in a yellow box (e.g. `abcd efgh ijkl mnop`).
   - **This is the only place you see this password.** Copy it now.
   - Paste it into your `.env` as `SMTP_PASSWORD=...` **with no spaces** (e.g. `abcdefghijklmnop`).
   - You cannot look up this password again later; if you lose it, generate a new App Password.

---

### Step 3: Where each “credential” comes from

| Credential   | Where you get it in Gmail |
|-------------|----------------------------|
| **SMTP_HOST**   | Always `smtp.gmail.com` (not something you “see” in Gmail). |
| **SMTP_PORT**   | Always `587` (standard for Gmail). |
| **SMTP_USER**   | Your Gmail address, e.g. `sriharsha2713@gmail.com` (profile/account settings or top-right in Gmail). |
| **SMTP_PASSWORD** | The **16-character App Password** from Step 2 (only on the App Passwords page after you click Generate). **Not** your normal Gmail login password. |
| **SMTP_FROM**   | Same as SMTP_USER: your Gmail address. |

---

### Step 4: Put them in `backend/.env`

Open `backend/.env` and set (use your real Gmail and the 16-character password **without spaces**):

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=sriharsha2713@gmail.com
SMTP_PASSWORD=your16charapppassword
SMTP_FROM=sriharsha2713@gmail.com
```

Then **restart the backend** (stop and start `uvicorn`) so it reloads `.env`.

---

### If you still get “535 Username and Password not accepted”

- Confirm **2-Step Verification** is On (Step 1).
- Use a **new App Password**: go back to [App Passwords](https://myaccount.google.com/apppasswords), create another one (e.g. “Frontier AI Radar 2”), copy the new 16 characters **without spaces** into `SMTP_PASSWORD`, restart the backend.
- Never use your normal Gmail password in `SMTP_PASSWORD`; Gmail will reject it.

---

## Option 2: SendGrid (free tier, 100 emails/day)

1. Sign up at [sendgrid.com](https://sendgrid.com/).

2. **Create an API Key** (or use SMTP):
   - Settings → API Keys → Create API Key (Restricted or Full).
   - Or use **SMTP**: Settings → Sender Authentication (verify a sender), then use SMTP relay.

3. **SendGrid SMTP details:**
   - Host: `smtp.sendgrid.net`
   - Port: `587`
   - User: `apikey` (literally the word "apikey")
   - Password: your SendGrid API key

4. **Set in `.env`:**
   ```env
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USER=apikey
   SMTP_PASSWORD=SG.your_sendgrid_api_key_here
   SMTP_FROM=your-verified-sender@yourdomain.com
   ```
   You must verify a sender (single sender or domain) in SendGrid first.

---

## Option 3: Outlook / Microsoft 365

1. Use your Outlook or work/school Microsoft account.

2. **Set in `.env`:**
   ```env
   SMTP_HOST=smtp.office365.com
   SMTP_PORT=587
   SMTP_USER=you@outlook.com
   SMTP_PASSWORD=your_password
   SMTP_FROM=you@outlook.com
   ```

---

## After setting `.env`

1. Restart the backend.
2. Add recipient emails on the **Digests** page in the app and click **Save recipients**.
3. Run the pipeline; when the digest PDF is generated, the email will be sent to those recipients.

---

## Troubleshooting

- **535 "Username and Password not accepted" (Gmail)**  
  Gmail is **rejecting the login**. Do this:
  1. Turn on **2-Step Verification** for the Gmail account: [Google Account → Security](https://myaccount.google.com/security).
  2. Create a **new App Password**: [App Passwords](https://myaccount.google.com/apppasswords) → Mail, Other (e.g. "Frontier AI Radar") → Generate.
  3. Copy the **16-character** password **with no spaces** into `.env` as `SMTP_PASSWORD=...`. Do **not** use your normal Gmail password.
  4. Restart the backend after changing `.env`.  
  More: [Gmail BadCredentials](https://support.google.com/mail/?p=BadCredentials).

- **"getaddrinfo failed"** or **"[Errno 11001]"**  
  The machine running the backend **cannot reach the SMTP server** (DNS/network). The credentials are not used until a connection is made.  
  - Check that the machine has internet (e.g. open a website in a browser).  
  - In PowerShell run: `Test-NetConnection smtp.gmail.com -Port 587` (or `ping smtp.gmail.com`).  
  - If you're on office/school Wi‑Fi or a VPN, SMTP is often blocked; try from home Wi‑Fi or mobile hotspot.  
  - Temporarily disable VPN/firewall to test.

- **App Password in `.env`**: use the 16-character password **without spaces** (e.g. `swslgtviiwmwngk`), or the value may be cut off.
