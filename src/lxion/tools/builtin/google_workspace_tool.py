import base64
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from email.message import EmailMessage
from lxion.tools.base import BaseTool
from lxion.core.logger import logger

from lxion.core.config import settings
TOKEN_FILE = settings.BASE_DIR / "credentials" / "token.json"

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/tasks'
]

def get_google_creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not TOKEN_FILE.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(str(TOKEN_FILE), 'w') as f:
                f.write(creds.to_json())
        return creds
    except Exception as e:
        logger.error(f"Failed to load or refresh Google credentials: {e}")
        return None

class GoogleWorkspaceTool(BaseTool):
    name = "google_workspace"
    description = (
        "Unified all-in-one Google Workspace tool (Gmail, Drive, Calendar, Docs, Sheets, Tasks). "
        "Allows sending/reading emails, uploading/searching Drive files, scheduling Calendar events, "
        "and reading/editing Docs & Sheets without writing manual scripts. "
        "Services: 'gmail', 'drive', 'calendar', 'docs', 'sheets', 'tasks'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "enum": ["gmail", "drive", "calendar", "docs", "sheets", "tasks"],
                "description": "The Google service to access."
            },
            "action": {
                "type": "string",
                "description": (
                    "The operation to perform: "
                    "gmail: 'send', 'list', 'read'. "
                    "drive: 'list', 'read', 'upload', 'create_folder'. "
                    "calendar: 'list', 'create'. "
                    "docs: 'create', 'read', 'append'. "
                    "sheets: 'read', 'append', 'create'. "
                    "tasks: 'list', 'create', 'complete'."
                )
            },
            "params": {
                "type": "object",
                "description": (
                    "Parameters for the action. Examples: "
                    "gmail send: {'to': 'user@gmail.com', 'subject': '...', 'body': '...'}. "
                    "gmail list: {'query': '...', 'max_results': 5}. "
                    "drive list: {'query': '...', 'max_results': 10}. "
                    "drive upload: {'file_path': '...', 'folder_id': '...'}. "
                    "calendar create: {'summary': '...', 'start_time': '2026-09-15T09:00:00', 'end_time': '2026-09-15T10:00:00', 'description': '...'}. "
                    "docs create: {'title': '...', 'content': '...'}. "
                    "sheets append: {'spreadsheet_id': '...', 'range': 'Sheet1!A1', 'values': [['val1', 'val2']]}. "
                    "tasks create: {'title': '...', 'notes': '...'}"
                )
            }
        },
        "required": ["service", "action"]
    }

    async def execute(self, service: str, action: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        creds = get_google_creds()
        if not creds:
            return {
                "success": False,
                "error": "Google Workspace is not authenticated. Please run 'python scripts/auth_google.py' to login."
            }

        params = params or {}
        srv = service.strip().lower()
        act = action.strip().lower()

        try:
            from googleapiclient.discovery import build

            # 1. GMAIL SERVICE
            if srv == "gmail":
                gmail_svc = build('gmail', 'v1', credentials=creds)
                if act == "send":
                    to_email = params.get("to") or params.get("to_email")
                    subject = params.get("subject", "Pesan dari LXION")
                    body = params.get("body", "")
                    if not to_email:
                        return {"success": False, "error": "Missing 'to' parameter for sending email."}
                    
                    msg = EmailMessage()
                    msg.set_content(body)
                    msg['To'] = to_email
                    msg['Subject'] = subject
                    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                    res = gmail_svc.users().messages().send(userId='me', body={'raw': encoded}).execute()
                    return {
                        "success": True,
                        "service": "gmail",
                        "action": "send",
                        "recipient": to_email,
                        "subject": subject,
                        "message_id": res.get("id"),
                        "message": f"Email successfully sent to {to_email} (ID: {res.get('id')})"
                    }

                elif act == "list":
                    max_r = int(params.get("max_results", 5))
                    q = params.get("query", "")
                    res = gmail_svc.users().messages().list(userId='me', maxResults=max_r, q=q).execute()
                    messages = res.get('messages', [])
                    results = []
                    for m in messages:
                        detail = gmail_svc.users().messages().get(userId='me', id=m['id'], format='minimal').execute()
                        results.append({"id": m['id'], "snippet": detail.get('snippet', '')})
                    return {"success": True, "service": "gmail", "action": "list", "count": len(results), "messages": results}

                elif act == "read":
                    mid = params.get("message_id") or params.get("id")
                    if not mid:
                        return {"success": False, "error": "Missing 'message_id'."}
                    res = gmail_svc.users().messages().get(userId='me', id=mid, format='full').execute()
                    return {"success": True, "service": "gmail", "action": "read", "message": res}

            # 2. DRIVE SERVICE
            elif srv == "drive":
                drive_svc = build('drive', 'v3', credentials=creds)
                if act == "list":
                    max_r = int(params.get("max_results", 10))
                    q = params.get("query")
                    res = drive_svc.files().list(
                        pageSize=max_r,
                        fields="files(id, name, mimeType, modifiedTime, size)",
                        q=q or None
                    ).execute()
                    return {"success": True, "service": "drive", "action": "list", "files": res.get('files', [])}

                elif act == "create_folder":
                    name = params.get("name", "New Folder")
                    meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
                    if params.get("parent_id"):
                        meta['parents'] = [params["parent_id"]]
                    folder = drive_svc.files().create(body=meta, fields='id, name').execute()
                    return {"success": True, "service": "drive", "action": "create_folder", "folder": folder}

                elif act == "upload":
                    from googleapiclient.http import MediaFileUpload
                    file_path = params.get("file_path")
                    if not file_path:
                        return {"success": False, "error": "Missing 'file_path'."}
                    from lxion.memory.workspace import workspace
                    safe_path = workspace._resolve_safe_path(file_path)
                    if not safe_path.exists():
                        return {"success": False, "error": f"File '{file_path}' not found on disk."}
                    media = MediaFileUpload(str(safe_path), resumable=True)
                    meta = {'name': safe_path.name}
                    if params.get("folder_id"):
                        meta['parents'] = [params["folder_id"]]
                    uploaded = drive_svc.files().create(body=meta, media_body=media, fields='id, name, webViewLink').execute()
                    return {"success": True, "service": "drive", "action": "upload", "file": uploaded}

                elif act == "read":
                    fid = params.get("file_id") or params.get("id")
                    if not fid:
                        return {"success": False, "error": "Missing 'file_id'."}
                    # Try export as plain text first if it's a google doc
                    try:
                        data = drive_svc.files().export(fileId=fid, mimeType='text/plain').execute()
                        content = data.decode('utf-8', errors='replace') if isinstance(data, bytes) else str(data)
                        return {"success": True, "service": "drive", "action": "read", "file_id": fid, "content": content}
                    except Exception:
                        meta = drive_svc.files().get(fileId=fid, fields="id, name, mimeType, webViewLink").execute()
                        return {"success": True, "service": "drive", "action": "read", "file_meta": meta}

            # 3. CALENDAR SERVICE
            elif srv == "calendar":
                cal_svc = build('calendar', 'v3', credentials=creds)
                if act == "list":
                    max_r = int(params.get("max_results", 10))
                    import datetime
                    now = datetime.datetime.utcnow().isoformat() + 'Z'
                    events_res = cal_svc.events().list(
                        calendarId='primary',
                        timeMin=params.get("time_min", now),
                        maxResults=max_r,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    return {"success": True, "service": "calendar", "action": "list", "events": events_res.get('items', [])}

                elif act == "create":
                    summary = params.get("summary", "Event baru dari LXION")
                    start = params.get("start_time")  # e.g. 2026-09-15T09:00:00
                    end = params.get("end_time")      # e.g. 2026-09-15T10:00:00
                    desc = params.get("description", "")
                    if not start or not end:
                        return {"success": False, "error": "Missing 'start_time' or 'end_time' (format: YYYY-MM-DDTHH:MM:SS)."}
                    body = {
                        'summary': summary,
                        'description': desc,
                        'start': {'dateTime': start if 'T' in start else f"{start}T09:00:00+07:00", 'timeZone': 'Asia/Jakarta'},
                        'end': {'dateTime': end if 'T' in end else f"{end}T10:00:00+07:00", 'timeZone': 'Asia/Jakarta'}
                    }
                    ev = cal_svc.events().insert(calendarId='primary', body=body).execute()
                    return {"success": True, "service": "calendar", "action": "create", "event": ev, "link": ev.get("htmlLink")}

            # 4. DOCS SERVICE
            elif srv == "docs":
                docs_svc = build('docs', 'v1', credentials=creds)
                if act == "create":
                    title = params.get("title", "Dokumen Baru")
                    doc = docs_svc.documents().create(body={'title': title}).execute()
                    doc_id = doc.get("documentId")
                    content = params.get("content")
                    if content and doc_id:
                        docs_svc.documents().batchUpdate(
                            documentId=doc_id,
                            body={'requests': [{'insertText': {'endOfSegmentLocation': {}, 'text': content}}]}
                        ).execute()
                    return {"success": True, "service": "docs", "action": "create", "doc_id": doc_id, "title": title, "url": f"https://docs.google.com/document/d/{doc_id}/edit"}

                elif act == "read":
                    doc_id = params.get("doc_id")
                    if not doc_id:
                        return {"success": False, "error": "Missing 'doc_id'."}
                    doc = docs_svc.documents().get(documentId=doc_id).execute()
                    text_parts = []
                    for item in doc.get('body', {}).get('content', []):
                        p = item.get('paragraph')
                        if p:
                            for el in p.get('elements', []):
                                text_parts.append(el.get('textRun', {}).get('content', ''))
                    return {"success": True, "service": "docs", "action": "read", "title": doc.get("title"), "content": "".join(text_parts)}

                elif act == "append":
                    doc_id = params.get("doc_id")
                    text = params.get("text", "")
                    if not doc_id or not text:
                        return {"success": False, "error": "Missing 'doc_id' or 'text'."}
                    docs_svc.documents().batchUpdate(
                        documentId=doc_id,
                        body={'requests': [{'insertText': {'endOfSegmentLocation': {}, 'text': f"\n{text}"}}]}
                    ).execute()
                    return {"success": True, "service": "docs", "action": "append", "doc_id": doc_id}

            # 5. SHEETS SERVICE
            elif srv == "sheets":
                sheets_svc = build('sheets', 'v4', credentials=creds)
                if act == "create":
                    title = params.get("title", "Spreadsheet Baru")
                    sh = sheets_svc.spreadsheets().create(body={'properties': {'title': title}}).execute()
                    sid = sh.get("spreadsheetId")
                    return {"success": True, "service": "sheets", "action": "create", "spreadsheet_id": sid, "url": f"https://docs.google.com/spreadsheets/d/{sid}/edit"}

                elif act == "read":
                    sid = params.get("spreadsheet_id")
                    rng = params.get("range", "Sheet1!A1:Z100")
                    if not sid:
                        return {"success": False, "error": "Missing 'spreadsheet_id'."}
                    res = sheets_svc.spreadsheets().values().get(spreadsheetId=sid, range=rng).execute()
                    return {"success": True, "service": "sheets", "action": "read", "values": res.get("values", [])}

                elif act == "append":
                    sid = params.get("spreadsheet_id")
                    rng = params.get("range", "Sheet1!A1")
                    vals = params.get("values", [])
                    if not sid or not vals:
                        return {"success": False, "error": "Missing 'spreadsheet_id' or 'values'."}
                    res = sheets_svc.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range=rng,
                        valueInputOption='USER_ENTERED',
                        body={'values': vals}
                    ).execute()
                    return {"success": True, "service": "sheets", "action": "append", "updated_cells": res.get("updates", {}).get("updatedCells")}

            # 6. TASKS SERVICE
            elif srv == "tasks":
                tasks_svc = build('tasks', 'v1', credentials=creds)
                if act == "list":
                    res = tasks_svc.tasks().list(tasklist='@default').execute()
                    return {"success": True, "service": "tasks", "action": "list", "tasks": res.get("items", [])}

                elif act == "create":
                    title = params.get("title", "Tugas baru")
                    notes = params.get("notes", "")
                    due = params.get("due") # RFC 3339 e.g. 2026-09-15T00:00:00Z
                    task_body = {'title': title, 'notes': notes}
                    if due:
                        task_body['due'] = due
                    t = tasks_svc.tasks().insert(tasklist='@default', body=task_body).execute()
                    return {"success": True, "service": "tasks", "action": "create", "task": t}

                elif act == "complete":
                    tid = params.get("task_id")
                    if not tid:
                        return {"success": False, "error": "Missing 'task_id'."}
                    t = tasks_svc.tasks().patch(tasklist='@default', task=tid, body={'status': 'completed'}).execute()
                    return {"success": True, "service": "tasks", "action": "complete", "task": t}

            return {
                "success": False,
                "error": f"Unknown service '{service}' or action '{action}'."
            }

        except Exception as e:
            logger.error(f"Google Workspace tool execution error ({service}.{action}): {e}")
            return {"success": False, "service": service, "action": action, "error": str(e)}
