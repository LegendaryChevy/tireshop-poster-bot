import json
import random
import importlib
import os
import logging
from datetime import datetime
import argparse
from libraries.PostUtils import PostUtils
from libraries.GoogleDrive import GoogleDrive

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--post_type', help='Override the scheduled post type')
parser.add_argument('--location', help='Override the location')
args = parser.parse_args()

SERVICE_ACCOUNT_FILE = 'google-account.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

# Generate the post based on the selected post type
def generate_post(post_type, location, drive_service):
    # Dynamically import and instantiate the post type class
    post_class = importlib.import_module(f'post_types.{post_type}')
    post_instance = getattr(post_class, post_type)()

    # Set the location property on the post_instance class
    post_instance.location = location
    post_instance.drive_service = drive_service

    PostUtils.log(f'Generating post for {post_type} class for location {location["name"]}...')

    # Generate the content and get the content and media properties
    generated_content = post_instance.generate_content()
    print(generated_content)
    content = generated_content["content"]
    media = generated_content["media"]

    PostUtils.log(f'Content: {content}')
    PostUtils.log(f'Media: {media}')

    # Call the post_content function with the content and media properties
    post_instance.post_content(content, media)

    PostUtils.log(f'Post content successfully generated and posted for location {location["name"]}.')

    return generated_content

# Load the Google API credentials and build the Google Drive service
drive = GoogleDrive(SERVICE_ACCOUNT_FILE, SCOPES)
drive_service = drive.get_service()

# Load config file
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Get the current day of the week
current_day = datetime.now().strftime('%A')

# Get post types for the current day
post_types_for_today = [args.post_type] if args.post_type else config['schedule'][current_day]
locations = [loc for loc in config['locations'] if loc['name'] == args.location] if args.location else config['locations']

# Check if there are post types scheduled for today
if not post_types_for_today:
    PostUtils.log(f"No post types scheduled for {current_day}. Exiting...")
    exit()

# Loop over each location
for location in locations:
    PostUtils.log(f'Script started for location {location["name"]} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    # Randomly select a post type
    selected_post_type = random.choice(post_types_for_today)

    PostUtils.log(f'Selected post type: {selected_post_type} for location {location["name"]}')

    generated_post = generate_post(selected_post_type, location, drive_service)

PostUtils.log(f'Script ended at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
