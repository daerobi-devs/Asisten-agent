import os
import json
import base64
from pathlib import Path
from email.message import EmailMessage
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/tasks'
]

ROOT_DIR = Path(r"d:\ASISTENPRIBADI")
CREDS_FILE = ROOT_DIR / "credentials.json"
TOKEN_FILE = ROOT_DIR / "credentials" / "token.json"
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

def authenticate():
    if not CREDS_FILE.exists():
        print(f"ERROR: File {CREDS_FILE} not found!")
        return None

    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[INFO] Refreshing expired token...")
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds or not creds.valid:
            print("[INFO] Starting OAuth Local Server on port 8080...")
            print("[INFO] Browser will open automatically. Please login and click 'Allow'.")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDS_FILE),
                scopes=SCOPES
            )
            # Run local server on port 8080 to auto-capture authorization code
            creds = flow.run_local_server(port=8080, prompt='consent')

        # Save token
        with open(str(TOKEN_FILE), 'w') as token:
            token.write(creds.to_json())
        print(f"[SUCCESS] Token successfully saved to {TOKEN_FILE}!")

        # Also copy to workspace/integrations/google/token.json for compatibility
        compat_dir = ROOT_DIR / "workspace" / "integrations" / "google"
        compat_dir.mkdir(parents=True, exist_ok=True)
        compat_file = compat_dir / "token.json"
        with open(str(compat_file), 'w') as f:
            f.write(creds.to_json())
        print(f"[SUCCESS] Copied token to {compat_file}!")

    return creds

def send_real_email(to_email: str, subject: str, body: str):
    creds = authenticate()
    if not creds:
        print("[ERROR] Cannot send email, authentication failed.")
        return False

    service = build('gmail', 'v1', credentials=creds)
    message = EmailMessage()
    message.set_content(body)
    message['To'] = to_email
    message['Subject'] = subject

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {'raw': encoded_message}

    try:
        sent = service.users().messages().send(userId="me", body=create_message).execute()
        msg_id = sent.get('id')
        print(f"\n=======================================================")
        print(f" REAL GMAIL SUCCESS!")
        print(f" Message successfully sent to: {to_email}")
        print(f" Real Google Message ID: {msg_id}")
        print(f"=======================================================\n")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email via Gmail API: {e}")
        return False

if __name__ == "__main__":
    import sys
    to = sys.argv[1] if len(sys.argv) > 1 else "ahmadchou23@gmail.com"
    msg = sys.argv[2] if len(sys.argv) > 2 else "haloo sayang ku cinta ku"
    send_real_email(to_email=to, subject="Pesan Sayang dari LXION & Advan", body=msg)
