import json
import os
from dotenv import load_dotenv
from libraries.Utils import download_file, upload_to_drive, is_uploaded, add_to_log
from libraries.GoogleDrive import GoogleDrive
from libraries.DiscordClient import DiscordClient
import discord

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SERVICE_ACCOUNT_FILE = 'google-account.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

# Load the Google API credentials and build the Google Drive service
drive = GoogleDrive(SERVICE_ACCOUNT_FILE, SCOPES)
drive_service = drive.get_service()

# Load the list of locations from the configuration file
with open('config.json') as f:
    locations = json.load(f)

# Setup and run Discord client
intents = discord.Intents.default()
intents.typing = False
intents.presences = True
intents.members = True
intents.message_content = True

client = DiscordClient(locations, drive_service, intents=intents)
client.run(DISCORD_TOKEN)
