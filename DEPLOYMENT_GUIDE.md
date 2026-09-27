# J.A.R.V.I.S. Pinnacle Quantitative Terminal: Full Deployment Guide

This guide details how to host, run, and install this application as a **Live Public Website** or an **Installed Mobile/Desktop App**.

---

## 1. Deploy as a Public Web Application (Free or Cheap Cloud Hosting)

Because this system runs on a standard **PEP 3333 WSGI server (`gunicorn`)** with an embedded SQLite database, you can host it anywhere that runs Python or Docker.

### Option A: Render.com (Easiest / Free Tier Available)
1. Push this project to GitHub (or create a private repository).
2. Go to [Render.com](https://render.com) and click **New > Web Service**.
3. Connect your GitHub repository.
4. Render automatically reads the included `render.yaml` or fill in:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 wsgi_application:application`
5. Click **Create Web Service**. Within 2 minutes, you will receive a public HTTPS URL (e.g. `https://jarvis-pinnacle.onrender.com`).

### Option B: Railway.app
1. Go to [Railway.app](https://railway.app) and create a **New Project**.
2. Select **Deploy from GitHub repo**.
3. Railway will detect the `Dockerfile` and start the server automatically.

### Option C: Fly.io (Ultra-Low Latency Edge Hosting)
1. Install the Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Run in the project directory:
   ```bash
   fly launch
   fly deploy
   ```
3. Uses the pre-configured `fly.toml` and launches on a dedicated edge server in seconds.

---

## 2. Turn It into a Native Mobile App (iOS & Android)

You don't need to rewrite the app in Swift or Kotlin. You have two production-ready options:

### Option A: PWA (Progressive Web App - Zero Store Approvals Needed)
The terminal has been configured with `pwa_manifest.json` and standalone display capabilities.
* **On iPhone / iPad (Safari):**
  1. Open your hosted HTTPS URL in Safari.
  2. Tap the **Share** button (the box with the arrow pointing up).
  3. Scroll down and tap **"Add to Home Screen"**.
  4. The app will install with its own glowing Arc Reactor app icon, launching fullscreen without Safari URL bars, giving it a 100% native feel.
* **On Android (Chrome):**
  1. Open your hosted URL in Chrome.
  2. Tap the three dots menu > **"Install app"** or **"Add to Home screen"**.

### Option B: Native Wrapper (Capacitor / Tauri)
If you want to package it as an `.ipa` or `.apk`:
1. Use **CapacitorJS**:
   ```bash
   npm init @capacitor/app
   npx cap add ios
   npx cap add android
   ```
2. Point the Capacitor `server.url` in `capacitor.config.json` to your deployed cloud URL:
   ```json
   {
     "appId": "com.stark.pinnaclejarvis",
     "appName": "JARVIS Pinnacle",
     "webDir": "www",
     "server": {
       "url": "https://your-deployed-domain.com",
       "cleartext": false
     }
   }
   ```
3. Run `npx cap open ios` or `npx cap open android` to build it directly in Xcode or Android Studio.

---

## 3. Turn It into a Desktop App (Mac / Windows / Linux)

### Option A: PyWebView (Zero Extra Build Steps)
You can create a standalone `.exe` or `.app` desktop window in 5 lines of Python:
```python
import webview
import subprocess

# Start WSGI server in background
subprocess.Popen(["python3", "-m", "gunicorn", "--bind", "127.0.0.1:8000", "wsgi_application:application"])

# Open standalone native desktop GUI
webview.create_window("J.A.R.V.I.S. Pinnacle Terminal", "http://127.0.0.1:8000", width=1400, height=900)
webview.start()
```

### Option B: Electron / Nativefier
Run one terminal command on your computer to bundle it into a native desktop `.app` or `.exe`:
```bash
npx nativefier --name "JARVIS Pinnacle" --icon icon.png "https://your-deployed-domain.com"
```

---

## Summary of Prepared Files in Your Workspace

| File | Purpose |
| :--- | :--- |
| `wsgi_application.py` | Production WSGI app (Gunicorn compatible) |
| `pinnacle_core.py` | Andrew Mack quantitative Poisson engine & Kelly logic |
| `real_pinnacle_ingest.py` | Direct real-time connection to Pinnacle Arcadia API |
| `requirements.txt` | Minimal Python dependencies (`gunicorn`, `requests`, `scipy`, `numpy`) |
| `Dockerfile` | Container configuration for Railway, Fly.io, or AWS ECS |
| `render.yaml` | One-click deployment blueprint for Render.com |
| `fly.toml` | Low-latency edge deployment for Fly.io |
| `pwa_manifest.json` | Web App Manifest for iPhone & Android home screens |
