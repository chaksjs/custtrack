# 🚀 CustTrack — Deploy to SAP BTP from SAP Business Application Studio (BAS)

## What is CustTrack?
A Python/Flask customer reminder tool hosted on SAP BTP Cloud Foundry, backed by SAP HANA Cloud.

---

## 📁 Project Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application |
| `manifest.yml` | Cloud Foundry deployment config |
| `requirements.txt` | Python dependencies |
| `runtime.txt` | Python version (`python-3.11.x`) |
| `hana_config.json` | HANA + email credentials (loaded at runtime) |
| `templates/login.html` | Login page |
| `templates/index.html` | Main customer tracker page |
| `templates/settings.html` | Admin settings page |
| `templates/admin.html` | Super admin dashboard |
| `templates/admin_otp.html` | Admin OTP verification page |

---

## ✅ Prerequisites

Before deploying, ensure you have:
- An **SAP BTP Trial or paid account** at https://cockpit.btp.cloud.sap
- A **Cloud Foundry space** created (e.g. `dev`)
- An **SAP HANA Cloud** instance running in the same CF space
- Access to **SAP Business Application Studio (BAS)**

---

## 🛠️ Step-by-Step Deployment from SAP BAS

### Step 1 — Open a Terminal in BAS
In SAP Business Application Studio, go to:
**Terminal → New Terminal**

### Step 2 — Upload the project zip to BAS
In BAS File Explorer, right-click and choose **Upload Files**, then upload `custtrack.zip`.

Extract it:
```bash
mkdir custtrack && cd custtrack
unzip ../custtrack.zip
```

### Step 3 — Log in to Cloud Foundry
```bash
cf login -a https://api.cf.eu10.hana.ondemand.com
```
> Replace `eu10` with your BTP region (e.g. `us10`, `ap10`).  
> Enter your **SAP BTP email** and **password** when prompted.  
> Select your **Org** and **Space** (e.g. `dev`).

### Step 4 — Verify your HANA Cloud service
```bash
cf services
```
You should see your HANA Cloud service listed (e.g. `hana-cloud-custtrack`).

If not yet created:
```bash
cf create-service hana-cloud hana hana-cloud-custtrack \
  -c '{"data":{"edition":"cloud","systempassword":"YourPassword123!"}}'
```
> ⚠️ This sets the initial DBADMIN password. Save it — you'll need it in Settings.

### Step 5 — Update credentials before deploying
Edit `hana_config.json` with your actual HANA host, credentials, and Gmail app password:
```bash
nano hana_config.json
```
Update these fields:
```json
{
  "host": "YOUR-HANA-HOST.hanacloud.ondemand.com",
  "port": 443,
  "user": "DBADMIN",
  "password": "YourHANAPassword",
  "admin_email": "your-admin@email.com",
  "sender_email": "your-gmail@gmail.com",
  "sender_password": "your-16-char-app-password",
  "admin_password": "YourAdminPassword",
  "settings_users": ["your-username"]
}
```

### Step 6 — Deploy the app
```bash
cf push
```
This reads `manifest.yml` and deploys `custtrack` with 512 MB memory using the Python buildpack.

### Step 7 — Get the live URL
```bash
cf app custtrack
```
Look for the **routes** line — e.g.:
```
routes:   custtrack.cfapps.eu10.hana.ondemand.com
```
Open that URL in your browser. 🎉

---

## 🔄 Redeployment (after code changes)

```bash
cd custtrack
cf push
```

## 📋 Useful CF Commands

```bash
cf logs custtrack --recent     # View recent logs
cf logs custtrack              # Stream live logs
cf restart custtrack           # Restart without redeploying
cf stop custtrack              # Stop the app (saves memory quota)
cf start custtrack             # Start it again
cf delete custtrack            # Delete the app
cf env custtrack               # View environment variables
```

---

## 💰 SAP BTP Services Used & Cost Estimation

### Services Required

| Service | Plan | Purpose | Est. Cost |
|---------|------|---------|-----------|
| **SAP HANA Cloud** | `hana` (paid) | Customer DB, user records, reminders | ~120 BTP Credits/mo |
| **Cloud Foundry Runtime** | Standard | Hosts Python/Flask app (512 MB) | ~86 BTP Credits/mo |
| **SAP BTP Cockpit** | — | Deployment & monitoring | Included |
| **Gmail SMTP** | — | OTP & reminder emails | Free (external) |

> 💡 **1 BTP Credit ≈ $1 USD**

---

### Monthly BTP Credit Estimates by Usage

| Scenario | Users | HANA Cloud | CF Runtime | DB Activity | **Total/mo** |
|----------|-------|-----------|-----------|-------------|-------------|
| 🚀 **Starter** | 1–10 | 120 cr | 86 cr | ~2 cr | **~208 cr** |
| 🏢 **Team** | 10–50 | 120 cr | 86 cr | ~15 cr | **~221 cr** |
| 🏭 **Enterprise** | 50–100 | 240 cr | 172 cr | ~50 cr | **~462 cr** |

> Estimates assume 1 HANA Cloud instance (15 GB, 2 vCPU, 32 GB RAM) + 512 MB CF memory.  
> Scale up HANA to 4 vCPU / 64 GB RAM for Team/Enterprise (~240 cr/mo).

---

### Cost Breakdown Details

**SAP HANA Cloud (Standard Plan)**
- 1 instance × 15 GB storage × 2 vCPU × 32 GB RAM
- ~120 BTP Credits/month (always-on)
- Stop the instance when not in use to save credits

**Cloud Foundry Runtime**
- 512 MB memory × 1 instance × 730 hrs/month
- ~86 BTP Credits/month
- Use `cf stop custtrack` when not needed

**Total for development/testing (1–5 users):**
```
HANA Cloud:    120 cr/mo
CF Runtime:     86 cr/mo
─────────────────────────
TOTAL:         206 cr/mo  (~$206 USD/mo)
```

**To reduce costs:**
- Stop HANA Cloud instance when not in use (BTP Cockpit → HANA Cloud → Stop)
- Use `cf stop custtrack` to stop the CF app
- Consider SAP BTP Free Tier for HANA Cloud (limited to 15 GB, 1 instance — sufficient for small teams)

---

## 🔐 Security Notes

- `hana_config.json` contains credentials — **do not commit to public git repos**
- Change `FLASK_SECRET_KEY` in `manifest.yml` to a random string before deploying
- Use a Gmail **App Password** (not your main password) for `sender_password`
  - Google Account → Security → 2-Step Verification → App Passwords

---

## 📞 Support

For issues, use the **💬 Help** button inside the app to send a screenshot to the developer.

---

## 🏗️ SAP Build Lobby — Which Stack to Choose?

### Short Answer: Do NOT use SAP Build Lobby for CustTrack

CustTrack is a **Python/Flask** application. SAP Build Lobby does not support Python backends. Here is a comparison of all available stacks:

| Stack | Technology | Fits CustTrack? |
|-------|-----------|----------------|
| **Full Stack Cloud Application** | CAP (Node.js or Java) + SAPUI5/Fiori | ❌ No — CAP is Node.js/Java only |
| **SAP Build Apps** | Low-code drag-and-drop UI | ❌ No — no Python backend |
| **SAP Build Process Automation** | Workflow / RPA automation | ❌ No |
| **HTML5 Application** | Pure frontend, no backend | ❌ No |

### ✅ Correct Way to Deploy CustTrack from BAS

Use **SAP Business Application Studio directly** — NOT via Build Lobby:

1. Open BAS → Create a new **Dev Space**
   - Choose type: **"Basic"** or **"Full Stack Cloud Application"** (either works — you just need a terminal)
2. In the terminal, upload and extract `custtrack.zip` (see Step 2 above)
3. Use the **CF CLI** (pre-installed in BAS) to deploy:
   ```bash
   cf login -a https://api.cf.eu10.hana.ondemand.com
   cf push
   ```

### 🔄 If You Want to Rewrite CustTrack as a Native SAP App (Future)

To use SAP Build Lobby, you would need to rewrite CustTrack using:

| Layer | Technology |
|-------|-----------|
| **Backend** | CAP Node.js with `@sap/hana-client` |
| **Frontend** | SAPUI5 or Fiori Elements |
| **Auth** | SAP BTP XSUAA (OAuth2) |
| **Build Lobby Stack** | **"Full Stack Cloud Application"** |

> ⚠️ This is a significant rewrite. The current Python/Flask approach is simpler and fully supported on BTP Cloud Foundry without any SAP-specific framework.

---

## 🗄️ Where Are Admin Credentials Stored?

**CustTrack does NOT store credentials in HANA tables.** All credentials are stored in `hana_config.json` on the server filesystem.

### Credential Storage Map

| Credential | Stored In | JSON Key |
|-----------|-----------|---------|
| Admin email | `hana_config.json` | `admin_email` |
| Admin password | `hana_config.json` | `admin_password` |
| HANA DB password | `hana_config.json` | `password` |
| Gmail App Password | `hana_config.json` | `sender_password` |
| Sub-admin users | `hana_config.json` | `settings_users` (array) |
| Setup complete flag | `hana_config.json` | `setup_complete` |

### HANA Tables Used

Only **one table** is used in HANA (schema: `DBADMIN`):

| Table | Purpose |
|-------|---------|
| `CUSTOMERS` | Stores customer records (name, CRM ID, location, reminders, status) |

No user accounts, passwords, or admin credentials are stored in HANA.

### ⚠️ Important: `hana_config.json` on BTP Cloud Foundry

On BTP Cloud Foundry, the app filesystem is **ephemeral** — `hana_config.json` is wiped on every `cf push` or app crash/restart. This means:

- After each `cf push`, the app will show the **setup wizard** again (since `hana_config.json` is gone)
- **Workaround options:**

**Option A — Include `hana_config.json` in the deployment zip** (simplest):
```bash
# Make sure hana_config.json has setup_complete: true before cf push
cf push
```
> ⚠️ Never commit this file to a public git repo — it contains passwords.

**Option B — Use CF Environment Variables** (recommended for production):
Add to `manifest.yml`:
```yaml
env:
  HANA_HOST: your-host.hanacloud.ondemand.com
  HANA_PASSWORD: YourPassword
  ADMIN_EMAIL: admin@email.com
  ADMIN_PASSWORD: YourAdminPw
  SENDER_EMAIL: gmail@gmail.com
  SENDER_PASSWORD: app-password-16chars
```
Then update `app.py` to read from `os.environ` instead of `hana_config.json`.

**Option C — SAP Credential Store** (most secure, BTP-native):
- Create a **Credential Store** service instance in BTP Cockpit
- Bind it to the `custtrack` CF app
- Store all secrets there and read via the Credential Store REST API
