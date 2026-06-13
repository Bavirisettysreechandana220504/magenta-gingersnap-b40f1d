# Derm Assist

Derm Assist is a Flask + SQLite skincare assistant with registration, login, AI-style image scan analysis, scan history, product suggestions, cart checkout, and a Capacitor Android wrapper.

## Web App Setup

Install Python 3.10 or newer, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py app.py
```

Open:

```text
http://127.0.0.1:5000
```

The app serves the HTML screens and API from the same Flask server, so old ngrok URLs are not needed for local use.

## Android Sync

After editing any web files, sync them into the Android project:

```powershell
npm run android:sync
```

Then open Android Studio:

```powershell
npm run android:open
```

## Main Files

- `app.py` - Flask API, SQLite tables, image upload, scan analysis, profile and history routes.
- `*.html` - Web screens used by the Flask app.
- `www/` - Synced web assets for Capacitor.
- `android/` - Capacitor Android project.
