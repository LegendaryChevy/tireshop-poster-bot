import os
import json
import random
from mysql.connector import Error, connect
from dotenv import load_dotenv


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
           
            title,steam_id, images, age_rating, store_url, description = game_data
           
            print(f'Title: {title}\nImages: {images}\nStore URL: {store_url}\nDescription: {description}\nAge Rating: {age_rating}\n')  # Prints all fields
get_random_game()