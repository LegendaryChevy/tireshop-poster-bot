from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO
import aiohttp
import os

def is_uploaded(filename, location):
    log_file = f'logs/{location}_uploaded_images.log'

    # Check if the log file exists, if not, create it
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f:
            pass

    with open(log_file, 'r') as f:
        uploaded_images = f.read().splitlines()

    return filename in uploaded_images

def add_to_log(filename, location):
    log_file = f'logs/{location}_uploaded_images.log'

    # Check if the log file exists, if not, create it
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f:
            pass

    with open(log_file, 'a') as f:
        f.write(f"{filename}\n")
        
def file_exists_in_drive(filename, parent_id, drive_service):
    query = f"name = '{filename}' and '{parent_id}' in parents and trashed = false"
    files = drive_service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
    return len(files['files']) > 0

async def download_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                return None

def upload_to_drive(name, content, google_drive_folder_id, drive_service):
    file_metadata = {'name': name, 'parents': [google_drive_folder_id]}
    file = MediaIoBaseUpload(BytesIO(content), resumable=True, mimetype='image/jpeg')
    file = drive_service.files().create(body=file_metadata, media_body=file, fields='id').execute()
    return file
