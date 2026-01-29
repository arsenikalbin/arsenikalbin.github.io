import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import sys

# ---------------- Configuration ----------------
SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'client_secret_966125481217-ftoha82uccnfg2f4mg6h0it05k2m0tor.apps.googleusercontent.com.json'
TOKEN_FILE = 'token.pickle'

SHARED_DRIVE_ID = '0AKbbJo0Vmj08Uk9PVA'  # Arsenrobotics Media
BASE_FOLDER_PATH = 'photography/website'   # inside Shared Drive

# Receive file, date, icao from command line
if len(sys.argv) != 5:
    print("Usage: python upload_to_gdrive.py <jpg_file> <json_file> <date> <icao>")
    sys.exit(1)

JPG_FILE = sys.argv[1]
JSON_FILE = sys.argv[2]
DATE = sys.argv[3]
ICAO = sys.argv[4]

# ---------------- Authenticate ----------------
creds = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=False)
    with open(TOKEN_FILE, 'wb') as token:
        pickle.dump(creds, token)

service = build('drive', 'v3', credentials=creds)

# ---------------- Helper functions ----------------
def find_or_create_folder(name, parent_id):
    """Find a folder by name under parent_id, or create it."""
    query = f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    
    # List existing folders
    results = service.files().list(
        q=query,
        corpora='drive',
        driveId=SHARED_DRIVE_ID,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields="files(id, name)"
    ).execute()
    
    files = results.get('files', [])
    if files:
        return files[0]['id']
    
    # Create folder if it doesn't exist
    file_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]  # Parent must be a folder ID in Shared Drive
    }
    
    folder = service.files().create(
        body=file_metadata,
        supportsAllDrives=True,
        fields='id'
    ).execute()
    
    return folder['id']

# ---------------- Upload file ----------------
# Step 1: create base folder if it doesn't exist
base_folder_id = find_or_create_folder(BASE_FOLDER_PATH.split('/')[0], SHARED_DRIVE_ID)
for part in BASE_FOLDER_PATH.split('/')[1:]:
    base_folder_id = find_or_create_folder(part, base_folder_id)

# Step 2: create date_icao folder
target_folder_name = f"{DATE}_{ICAO.lower()}"
target_folder_id = find_or_create_folder(target_folder_name, base_folder_id)

# Step 3: upload the file
def upload_file(path):
    file_metadata = {
        'name': os.path.basename(path),
        'parents': [target_folder_id]
    }
    media = MediaFileUpload(path, resumable=True)
    file = service.files().create(body=file_metadata,
                                media_body=media,
                                supportsAllDrives=True,
                                fields='id').execute()

    # make public
    service.permissions().create(
        fileId=file['id'],
        body={'role': 'reader', 'type': 'anyone'},
        supportsAllDrives=True
    ).execute()

    print(f"Uploaded '{path}' to folder '{target_folder_name}' with file ID: {file['id']}")

upload_file(JPG_FILE)
upload_file(JSON_FILE)
