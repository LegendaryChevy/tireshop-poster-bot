import discord
import asyncio
from libraries.Utils import is_uploaded, add_to_log, file_exists_in_drive, download_file, upload_to_drive
import os
import json

class DiscordClient(discord.Client):

    def __init__(self, locations, drive_service, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locations = locations
        self.drive_service = drive_service

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')

        for location in self.locations:
            discord_channel_id = location['discord_channel_id']
            google_drive_folder_id = location['google_drive_folder_id']

            # Get the specific channel
            channel = self.get_channel(discord_channel_id)

            # Load the last processed message ID
            last_message_id_file = f'logs/{location["name"]}_last_message_id.txt'
            if os.path.exists(last_message_id_file):
                with open(last_message_id_file, 'r') as f:
                    file_content = f.read()
                    # Check if the file content is not empty before trying to convert it into an integer
                    last_message_id = int(file_content) if file_content != '' else None
            else:
                last_message_id = None

            # Set the maximum number of messages to fetch per request
            messages_per_request = 1000

            # First message ID in each batch
            first_message_id_in_batch = None

            # Fetch attachments from channel messages
            while True:
                keep_fetching = False  # Reset the flag
                after = discord.Object(id=last_message_id) if last_message_id else None

                async for message in channel.history(limit=messages_per_request, after=after):
                    if not first_message_id_in_batch:
                        # Save the ID of the first message in the batch (most recent message)
                        first_message_id_in_batch = message.id

                    keep_fetching = True  # As long as there are messages, keep fetching

                    for attachment in message.attachments:
                        # Check if file already exists on Google Drive
                        if is_uploaded(attachment.filename, location['name']):
                            continue
                        elif file_exists_in_drive(attachment.filename, google_drive_folder_id, self.drive_service):
                            # If the file exists on Google Drive but not in our log, add it to the log
                            add_to_log(attachment.filename, location['name'])
                            print(f'File {attachment.filename} already exists on Google Drive.')
                            continue

                        # Download the attachment
                        content = await download_file(attachment.url)

                        # Create a unique local folder for each location
                        local_image_folder = os.path.join('downloads', location['name'])
                        os.makedirs(local_image_folder, exist_ok=True)

                        # Create the local file path
                        local_file_path = os.path.join(local_image_folder, attachment.filename)

                        # Check if file already exists locally
                        if os.path.exists(local_file_path):
                            print(f'File {local_file_path} exists already')
                            continue

                        # Save the file to the local folder
                        with open(local_file_path, 'wb') as f:
                            f.write(content)

                        # Upload the file to Google Drive
                        drive_file = upload_to_drive(attachment.filename, content, google_drive_folder_id, self.drive_service)
                        print(f'File {attachment.filename} uploaded to Google Drive with ID {drive_file.get("id")}.')

                        # Add the filename to the location specific log
                        add_to_log(attachment.filename, location['name'])

                if not keep_fetching:
                    # If no more messages to fetch, break the while loop
                    break

                # Update last_message_id to the ID of the first message in the batch
                last_message_id = first_message_id_in_batch
                first_message_id_in_batch = None  # Reset for the next batch

            # Save the last processed message ID
            with open(last_message_id_file, 'w') as f:
                f.write(str(last_message_id))

            print(f'Image sync for {location["name"]} complete.')

        await self.close()  # Gracefully shutdown the bot after completing all tasks
