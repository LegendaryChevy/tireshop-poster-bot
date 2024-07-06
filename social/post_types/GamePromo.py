from openai import OpenAI
import openai
from libraries.PostUtils import PostUtils
import os
import random
from dotenv import load_dotenv
import random
from mysql.connector import Error, connect
# Load .env file
load_dotenv()


def get_random_game():
    load_dotenv()

    db_config = {
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'host': os.getenv('MYSQL_HOST'),
        'database': os.getenv('MYSQL_DB'),
    }



    try:
        mysql_client = connect(**db_config)
        print('successfully connected to database')

        mysql_query = mysql_client.cursor()
    except Error as err:
        print(f"Error: {err}")


    cursor = mysql_client.cursor()

    cursor.execute('select id from vr_titles')

    rows = cursor.fetchall()

    game_ids = [row[0] for row in rows]

    if game_ids:
        games_to_select = random.sample(game_ids, 1)
        
        for game_id in games_to_select:
            cursor.execute(f'select  title, steam_id, images, store_url, description, age_rating from vr_titles where id={game_id}')
            game_data = cursor.fetchone()
            
            return game_data
newgame = get_random_game()
title, steam_id, images, age_rating, store_url, description = newgame
class GamePromo:

    class_id = 'GamePromo'
    location = None
    drive_service = None
   
    
    def text_generator(self,prompt, system_message):
      
        response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content":  title},
            {"role": "assistant", "content": description},
            {"role": "assistant", "content": age_rating},
            {"role": "assistant", "content": store_url}
            
        ]
    )
        return response.choices[0].message.content.strip()
        
        



    def generate_content(self, title=title):
        system_message = PostUtils.get_system_message(self.class_id, self.location)
        prompt = PostUtils.get_prompt(self.class_id)

        text_content = self.text_generator(prompt, system_message)
        if not text_content:
            return "Error generating game promotion message."

        num_images = random.randint(1, 3)

        # Update the path to include the variable 'title'
        image_folder_path = f'../../steam-store-poller/pics/{title}'
        image_paths = self.select_random_images(image_folder_path, num_images)

        return {
            'content': text_content,
            'media': image_paths
        }

    def select_random_images(self, folder_path, num_images):
        if not os.path.exists(folder_path):
            raise Exception(f"Path {folder_path} does not exist.")
        
        images = [os.path.join(folder_path, image) for image in os.listdir(folder_path) if image.endswith(('.png', '.jpg', '.jpeg'))]
        
        if len(images) < num_images:
            raise Exception(f"Only {len(images)} images in folder but requested {num_images} images.")
        
        selected_images = random.sample(images, num_images)
        
        return selected_images

    def post_content(self, content, media):
        PostUtils.post_to_all(content, media, self.location, self.class_id)
