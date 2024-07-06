import facebook
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

class PostUtils:

    @staticmethod
    def log(message):
        print(message)

    @staticmethod
    def get_fb_api(cfg):
        try:
            api = facebook.GraphAPI(cfg['access_token'])
            return api
        except facebook.GraphAPIError as e:
            PostUtils.log(f"An error occurred while accessing the Facebook API: {e}")
            raise

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
        response = requests.get(f"https://graph.facebook.com/me?access_token={access_token}")
        return response.status_code != 200

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

def test_facebook_token_and_call():
    page_id = os.getenv('FB_TEST_PAGE_ID2')
    app_id = os.getenv('FB_APP_ID')
    app_secret = os.getenv('FB_APP_SECRET')
    expired_token = 'intentionally_invalid_token_to_test_refresh'

    cfg = {
        "page_id": page_id,
        "access_token": expired_token
    }

    # Simulate the current token being expired
    if PostUtils.fb_token_expired(cfg['access_token']):
        PostUtils.log("Simulated expired token. Attempting to fetch new token...")

        # Attempt to load a real short-lived token from file
        short_lived_token = PostUtils.load_facebook_token(page_id)

        if not short_lived_token:
            PostUtils.log("No short-lived token found. Please make sure the token file exists.")
            return

        # Attempt to refresh the token
        cfg['access_token'] = PostUtils.get_fb_long_token(app_id, app_secret, short_lived_token, page_id)
        if not cfg['access_token']:
            PostUtils.log("Failed to refresh the token.")
            return

    try:
        api = PostUtils.get_fb_api(cfg)
        # Perform a test API call. For example, get the page's own details:
        page_details = api.get_object(id=page_id)
        PostUtils.log(f"Test API call successful. Page details: {page_details}")
    except facebook.GraphAPIError as e:
        PostUtils.log(f"An error occurred during the test API call: {e}")

if __name__ == '__main__':
    test_facebook_token_and_call()
