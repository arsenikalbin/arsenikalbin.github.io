import os
import pickle
import json
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ---------------- Configuration ----------------
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
CREDENTIALS_FILE = 'client_secret.json'
TOKEN_FILE = 'token.pickle'

SHARED_DRIVE_ID = '0AKbbJo0Vmj08Uk9PVA'
BASE_FOLDER_PATH = 'photography/website'  # root folder in shared drive
OUTPUT_JSON = 'gallery.json'

# ---------------- Authenticate ----------------
creds = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, 'rb') as f:
        creds = pickle.load(f)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=False)
    with open(TOKEN_FILE, 'wb') as f:
        pickle.dump(creds, f)

service = build('drive', 'v3', credentials=creds)
headers = {'Authorization': 'Bearer ' + creds.token}

# ---------------- Helper functions ----------------
def list_folders(parent_id):
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(
        q=query,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        fields="files(id, name)"
    ).execute()
    return results.get('files', [])

def list_files(folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        fields="files(id, name)"
    ).execute()
    return results.get('files', [])

def find_folder_by_path(path):
    parts = path.split('/')
    parent_id = SHARED_DRIVE_ID
    for part in parts:
        folders = list_folders(parent_id)
        match = next((f for f in folders if f['name'] == part), None)
        if not match:
            raise Exception(f"Folder '{part}' not found in Drive")
        parent_id = match['id']
    return parent_id

def fetch_sidecar_json(file_id):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    return {}

# ---------------- Generate gallery.json ----------------
base_folder_id = find_folder_by_path(BASE_FOLDER_PATH)
gallery = []

for folder in list_folders(base_folder_id):
    folder_id = folder['id']
    folder_name = folder['name']
    files = list_files(folder_id)

    photos = []
    for file in files:
        if file['name'].endswith('.json'):
            continue  # skip sidecar files

        # remove extension to find sidecar
        base_name = os.path.splitext(file['name'])[0]
        sidecar = next((s for s in files if s['name'] == f"{base_name}.json"), None)

        metadata = {}
        if sidecar:
            metadata = fetch_sidecar_json(sidecar['id'])

        # generate thumbnail URL
        thumbnail_url = f"https://drive.google.com/thumbnail?id={file['id']}&sz=w100"

        photos.append({
            "name": file['name'],
            "id": file['id'],
            "thumbnail_url": thumbnail_url,
            "metadata": metadata
        })

    gallery.append({
        "folder": folder_name,
        "photos": photos
    })

# ---------------- Save json ----------------
with open(OUTPUT_JSON, 'w') as f:
    json.dump(gallery, f, indent=2)

print(f"Generated {OUTPUT_JSON} with {len(gallery)} folders")
