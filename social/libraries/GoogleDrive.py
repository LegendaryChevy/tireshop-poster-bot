from google.oauth2 import service_account
from googleapiclient.discovery import build

class GoogleDrive:
    def __init__(self, service_account_file, scopes):
        self.creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=scopes)
        self.service = build('drive', 'v3', credentials=self.creds)

    def get_service(self):
        return self.service
