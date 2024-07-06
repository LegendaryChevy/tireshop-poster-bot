from libraries.PostUtils import PostUtils
import os
import random
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class RewardsPromo:

    class_id = 'RewardsPromo'
    location = None
    drive_service = None

    def generate_content(self):
        # Use PostUtils to obtain system message and prompt
        system_message = PostUtils.get_system_message(self.class_id, self.location)
        prompt = PostUtils.get_prompt(self.class_id)

        # Generate text content
        text_content = PostUtils.generate_text_content(prompt, system_message)
        if not text_content:
            return "Error generating rewards system promotion message."

        # Select between 1 and 5 random images
        num_images = random.randint(1, 5)
        image_folder_id = self.location["drive_folders"]["general"]
        image_paths = PostUtils.select_random_images(self.drive_service, image_folder_id, f'used_images_{self.class_id}_{self.location["name"]}.txt', num_images)

        # Return both text content and image paths
        return {
            'content': text_content,
            'media': image_paths
        }

    def post_content(self, content, media):
        PostUtils.post_to_all(content, media, self.location, self.class_id)
