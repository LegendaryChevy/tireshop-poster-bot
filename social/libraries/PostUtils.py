import openai
import time
import os
from dotenv import load_dotenv
import random
import asyncio
import json
import requests
import facebook
import logging
from googleapiclient.http import MediaIoBaseDownload
import boto3
from botocore.exceptions import NoCredentialsError
import mimetypes
from PIL import Image
from openai import OpenAI

load_dotenv('post_types/.env')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

openai_client = OpenAI(api_key = OPENAI_API_KEY)
print(OPENAI_API_KEY)
class PostUtils:

    # Create a logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Set up logging
    logging.basicConfig(filename='logs/posts.log', level=logging.INFO, format='%(asctime)s %(message)s')

    @staticmethod
    def log(message):
        print(message)
        logging.info(message)

    @staticmethod
    async def gpt_write(prompt, system_message="", model="gpt-4-1106-preview", max_tokens=1500, temperature=0.8):
        retries = 3
        delay = 5  # seconds

        while retries > 0:
            try:
                response = openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                    n=1,
                    stop=None,
                    temperature=temperature,
                )
                return response
            except openai.BadRequestError as e:
                error_msg = f"Error: {e}"
                print(error_msg)
                return None
            except Exception as e:
                error_msg = f"Error: {e}"
                print(error_msg)
                retries -= 1
                if retries > 0:
                    retry_msg = f"Retrying in {delay} seconds... ({retries} retries left)"
                    print(retry_msg)
                    time.sleep(delay)
                else:
                    return None

    @staticmethod
    def select_random_images(drive_service, images_folder_id, used_images_file, num_images):
        # Define logs directory
        logs_directory = 'logs'
        if not os.path.exists(logs_directory):
            os.makedirs(logs_directory)

        # Adjust used_images_file to be in logs directory
        used_images_file = os.path.join(logs_directory, used_images_file)

        # Load used images file or create an empty set
        if os.path.exists(used_images_file):
            with open(used_images_file, 'r') as file:
                used_images = set(line.strip() for line in file)
        else:
            used_images = set()

        # Get list of all files in the Google Drive folder using pagination
        all_images = {}
        request = drive_service.files().list(
            q="'{}' in parents and trashed=false".format(images_folder_id),
            fields="nextPageToken, files(id, name)"
        )

        while request is not None:
            response = request.execute()
            items = response.get('files', [])
            for file in items:
                file_name = file['name'].lower()

                # Check file extension to ensure it's an image
                if file_name.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    all_images[file['id']] = file['name']

            request = drive_service.files().list_next(previous_request=request, previous_response=response)

        unused_images = set(all_images.keys()).difference(used_images)

        # Reset used images if all images have been used
        if not unused_images:
            used_images = set()
            unused_images = set(all_images.keys())

        # Select random images, ensuring num_images is not larger than the length of unused_images
        num_images = min(num_images, len(unused_images))
        selected_images = random.sample(unused_images, num_images)

        # Update used images file
        with open(used_images_file, 'a') as file:
            for image_id in selected_images:
                file.write(f'{image_id}\n')

        selected_images = [(image_id, all_images[image_id]) for image_id in selected_images]

        # Download them and return the paths
        return PostUtils.download_drive_images(drive_service, selected_images)

    @staticmethod
    def download_drive_images(drive_service, images):
        local_image_folder = 'downloads'
        os.makedirs(local_image_folder, exist_ok=True)
        for image_id, image_name in images:
            local_file_path = os.path.join(local_image_folder, image_name)
            PostUtils.log(f'Download image from drive to {local_file_path}')

            # Check if file already exists locally and skip downloading if it does
            if os.path.exists(local_file_path):
                continue

            request = drive_service.files().get_media(fileId=image_id)
            with open(local_file_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()

        return [os.path.join(local_image_folder, image[1]) for image in images]

    @staticmethod
    def post_discord(content, media, location, post_type=None):
        # Get discord webhook url from .env file
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

        if not webhook_url:
            PostUtils.log("Error: DISCORD_WEBHOOK_URL not set in .env file.")
            return

        # Prepend the post type and location to the content
        if post_type:
            content = f"Making a {post_type} social media post for {location['name']}:\n\n{content}"

        # Prepare the payload
        payload = {
            "content": content,
            "embeds": []
        }

        # Add each media file to the payload as an embed
        for media_item in media:
            payload["embeds"].append({
                "image": {
                    "url": "attachment://" + os.path.basename(media_item)
                }
            })

        # Prepare the payload as JSON
        payload_json = json.dumps(payload)

        # Prepare the files for the multipart/form-data POST request
        files = [('payload_json', (None, payload_json, 'application/json'))]
        files.extend([(f"file{i}", (os.path.basename(media_item), open(media_item, "rb"), 'application/octet-stream')) for i, media_item in enumerate(media)])

        # Send POST request to Discord Webhook URL
        response = requests.post(webhook_url, files=files)

        # Check if the request was successful
        if response.status_code != 200 and response.status_code != 204:
            PostUtils.log(f"Error posting to Discord: {response.status_code}, {response.text}")
        else:
            PostUtils.log("Successfully posted to Discord")

    @staticmethod
    def post_facebook(content, media, location):
        page_id = location['facebook']['page_id']
        cfg = {
            "page_id"      : page_id,
            "access_token" : PostUtils.load_facebook_token(page_id)
        }

        if not cfg['page_id'] or not cfg['access_token']:
            PostUtils.log("Skipping Facebook due to missing config")
            return

        # Check if the token is expired and get a new one if it is
        if PostUtils.fb_token_expired(cfg['access_token']):
            cfg['access_token'] = PostUtils.get_fb_long_token(os.getenv('FB_APP_ID'), os.getenv('FB_APP_SECRET'), cfg['access_token'], page_id)

        attached_media = []

        try:
            api = PostUtils.get_fb_api(cfg)
        except facebook.GraphAPIError as e:
            PostUtils.log(f"An error occurred while getting the Facebook API: {e}")
            return

        for image_path in media:
            if not os.path.isfile(image_path):
                PostUtils.log(f"No such file: {image_path}")
                continue

            try:
                with open(image_path, "rb") as image:
                    photo_response = api.put_photo(image=image, published=False)
                    attached_media.append({"media_fbid": photo_response["id"]})
            except IOError as e:
                PostUtils.log(f"An error occurred while reading the file: {e}")
            except facebook.GraphAPIError as e:
                PostUtils.log(f"An error occurred while uploading the photo: {e}")

        if not attached_media:
            PostUtils.log("No photos to post")
            return

        try:
            post_response = api.put_object(
                parent_object='me',
                connection_name='feed',
                message=content,
                attached_media=json.dumps(attached_media)
            )
            PostUtils.log(f'Successfully posted to Facebook page ID {cfg["page_id"]}')
        except facebook.GraphAPIError as e:
            PostUtils.log(f"An error occurred while posting to Facebook: {e}")

    @staticmethod
    def get_fb_api(cfg):
        try:
            # Instantiate the GraphAPI object with the page's access token
            api = facebook.GraphAPI(cfg['access_token'])
        except facebook.GraphAPIError as e:
            PostUtils.log(f"An error occurred while accessing the Facebook API: {e}")
            raise
        return api

    @staticmethod
    def load_facebook_token(page_id):
        try:
            with open(f'facebook_token_{page_id}.txt', 'r') as token_file:
                return token_file.read().strip()
        except FileNotFoundError:
            PostUtils.log(f"Facebook token file not found for page {page_id}.")
            return None

    @staticmethod
    def fb_token_expired(access_token):
        try:
            response = requests.get(f"https://graph.facebook.com/me?access_token={access_token}")
            return response.status_code != 200
        except Exception as e:
            PostUtils.log(f"An error occurred while checking token expiry: {e}")
            return True

    @staticmethod
    def get_fb_long_token(app_id, app_secret, short_lived_token, page_id):
        url = f"https://graph.facebook.com/v18.0/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_lived_token
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            long_lived_token = response.json().get('access_token')

            # Ensure we have a non-empty string token before writing to the file
            if long_lived_token and isinstance(long_lived_token, str):
                with open(f'facebook_token_{page_id}.txt', 'w') as token_file:
                    token_file.write(long_lived_token)
                return long_lived_token
            else:
                # Log an error if the token is None or not a string
                PostUtils.log(f"Received invalid token for page {page_id}: {long_lived_token}")
                return None
        else:
            PostUtils.log(f"An error occurred while obtaining the long-lived token for page {page_id}: {response.content}")
            return None

    @staticmethod
    def post_instagram(content, media, location):
        page_id = location['facebook']['page_id']
        cfg = {
            "ig_user_id": location['instagram']['ig_user_id'],
            "access_token" : PostUtils.load_facebook_token(page_id)  # access_token from Facebook
        }

        # Check if 'ig_user_id' is null or an empty string
        if not cfg['ig_user_id'] or not cfg['access_token']:
            PostUtils.log("Skipping Instagram due to missing config")
            return

        # Check if the token is expired and get a new one if it is
        if PostUtils.fb_token_expired(cfg['access_token']):
            cfg['access_token'] = PostUtils.get_fb_long_token(os.getenv('FB_APP_ID'), os.getenv('FB_APP_SECRET'), cfg['access_token'], page_id)

        # If media array is empty, print an error message and return
        if not media:
            PostUtils.log("No photos to post to Instagram")
            return

        # Use the first image from the media array
        image_path = media[0]

        # Create a cropped version for Instagram
        cropped_image_path = PostUtils.crop_for_instagram(image_path)

        # Upload image to S3 and get the URL
        s3_url = PostUtils.upload_to_s3(cropped_image_path)

        if not s3_url:
            PostUtils.log(f"Error uploading image to S3")
            return

        try:
            api = PostUtils.get_fb_api(cfg)

            # Step 1: Use POST /{ig-user-id}/media endpoint to create a container
            container = api.request(f"{cfg['ig_user_id']}/media", method='POST', args={
                'image_url': s3_url,
                'caption': content,
            })

            if 'id' in container:
                container_id = container['id']

                # Step 2: Use POST /{ig_user_id}/media_publish endpoint to publish the container
                publish_response = api.request(f"{cfg['ig_user_id']}/media_publish", method='POST', args={
                    'creation_id': container_id,
                })

                if 'id' in publish_response:
                    PostUtils.log(f'Successfully posted to Instagram user ID {cfg["ig_user_id"]}')
                else:
                    PostUtils.log(f"An error occurred while publishing to Instagram: {publish_response}")

            else:
                PostUtils.log(f"An error occurred while creating Instagram container: {container}")

        except facebook.GraphAPIError as e:
            PostUtils.log(f"An error occurred while posting to Instagram: {e}")

    @staticmethod
    def post_twitter(content, media, location):
        # Skeleton code for posting content and media to Twitter
        pass

    @staticmethod
    def post_linkedin(content, media, location):
        # Skeleton code for posting content and media to LinkedIn
        pass

    @staticmethod
    def post_pinterest(content, media, location):
        # Skeleton code for posting content and media to Pinterest
        pass

    @staticmethod
    def post_reddit(content, media, location):
        # Skeleton code for posting content and media to Reddit
        pass

    @staticmethod
    def post_to_all(content, media, location, post_type=None):
        PostUtils.post_discord(content, media, location, post_type)
        #PostUtils.post_facebook(content, media, location)
        #PostUtils.post_instagram(content, media, location)
        #PostUtils.post_twitter(content, media, location)
        #PostUtils.post_linkedin(content, media, location)
        #PostUtils.post_pinterest(content, media, location)
        #PostUtils.post_reddit(content, media, location)
        return


    @staticmethod
    def crop_for_instagram(image_path):
        # Open the image file
        with Image.open(image_path) as im:
            width, height = im.size

            # Determine the aspect ratio
            aspect_ratio = width / height

            # If the aspect ratio is outside the acceptable range, crop the image
            if aspect_ratio < 0.8 or aspect_ratio > 1.91:
                new_width = min(width, height * 1.91)
                new_height = min(height, width / 0.8)
                left = (width - new_width) / 2
                top = (height - new_height) / 2
                right = (width + new_width) / 2
                bottom = (height + new_height) / 2

                # Crop the image
                cropped_im = im.crop((left, top, right, bottom))

                # Save the cropped image as a new file
                base_name, ext = os.path.splitext(image_path)
                cropped_image_path = f"{base_name}_instagram{ext}"
                cropped_im.save(cropped_image_path)

                return cropped_image_path

            else:
                return image_path  # Return the original path if no cropping is needed

    @staticmethod
    def get_system_message(class_id, location, default_message=""):
        # Get role for the given class_id or use the default role
        role = location['roles'].get(class_id, location['roles']['default'])
        if not role:
            role = location['roles']['default']

        # Read system message from file
        sys_msg_file = f"roles/{role}.txt"
        try:
            with open(sys_msg_file, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return default_message

    @staticmethod
    def get_prompt(role):
        # Read prompt from file
        prompt_file = f"prompts/{role}.txt"
        try:
            with open(prompt_file, 'r') as file:
                return file.read()
        except FileNotFoundError:
            PostUtils.log('Error: Prompt file not found.')
            return

    @staticmethod
    def generate_text_content(prompt, system_message):
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(PostUtils.gpt_write(prompt, system_message=system_message))
        if not response:
            return None
        return response.choices[0].message.content.strip()

    @staticmethod
    def upload_to_s3(image_path):
        PostUtils.log(f'Uploading image to S3 bucket: {image_path}')

        # Load AWS credentials from environment variables
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        bucket_name = os.getenv('S3_BUCKET_NAME')

        s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

        # If file doesn't exist, return None
        if not os.path.isfile(image_path):
            PostUtils.log(f"No such file: {image_path}")
            return None

        try:
            # Construct the S3 object key from the image path
            key = os.path.basename(image_path)

            # Check if the file already exists in the bucket
            s3.head_object(Bucket=bucket_name, Key=key)
            PostUtils.log(f"File {key} already exists in bucket {bucket_name}")

        except NoCredentialsError:
            PostUtils.log("No AWS credentials found")
            return None
        except s3.exceptions.ClientError as e:
            # If the file doesn't exist in the bucket, upload it
            if e.response['Error']['Code'] == "404":
                content_type = mimetypes.guess_type(image_path)[0] or 'binary/octet-stream'
                s3.upload_file(
                    image_path,
                    bucket_name,
                    key,
                    ExtraArgs={
                        'ACL': 'public-read',
                        'ContentType': content_type
                    }
                )
            else:
                # Some other exception occurred
                PostUtils.log(f"An error occurred while accessing S3: {e}")
                return None

        # Return the public URL of the image
        url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
        return url
