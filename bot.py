import os
import logging
import requests
import sqlite3
import datetime
import json
from telebot import TeleBot, types
from threading import Thread
import time
from flask import Flask

# Flask server for 24/7
app = Flask('')

@app.route('/')
def home():
    return "🎬 Mukammal Kino Bot 24/7 Ishlamoqda!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# Log sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguratsiya
BOT_TOKEN = "7353875365:AAENeauCMHfEfUKGGKR9yr6WurVAqERctKA"
TMDB_API_KEY = "2f2bcc9e158dd28f93c2363cfb33a964"
ADMIN_IDS = [7439952029]

bot = TeleBot(BOT_TOKEN)

# Ma'lumotlar bazasi
def init_db():
    conn = sqlite3.connect('movie_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            subscribed INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_id INTEGER,
            movie_title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn

db = init_db()

# TMDB Helper
class TMDBHelper:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p/w500"
    
    def search_movies(self, query, page=1):
        url = f"{self.base_url}/search/movie"
        params = {
            'api_key': self.api_key,
            'query': query,
            'page': page,
            'language': 'ru'
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None
    
    def get_movie_details(self, movie_id):
        url = f"{self.base_url}/movie/{movie_id}"
        params = {
            'api_key': self.api_key,
            'append_to_response': 'credits,videos',
            'language': 'ru'
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Movie details error: {e}")
            return None
    
    def get_popular_movies(self, page=1):
        url = f"{self.base_url}/movie/popular"
        params = {
            'api_key': self.api_key,
            'page': page,
            'language': 'ru'
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Popular movies error: {e}")
            return None

tmdb = TMDBHelper(TMDB_API_KEY)

# Database functions
def save_user(user_id, username, first_name, last_name):
    cursor = db.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, subscribed)
        VALUES (?, ?, ?, ?, 1)
    ''', (user_id, username, first_name, last_name))
    db.commit()

def save_search(user_id, query):
    cursor = db.cursor()
    cursor.execute('INSERT INTO search_history (user_id, query) VALUES (?, ?)', (user_id, query))
    db.commit()

def add_favorite(user_id, movie_id, movie_title):
    cursor = db.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO favorites (user_id, movie_id, movie_title)
        VALUES (?, ?, ?)
    ''', (user_id, movie_id, movie_title))
    db.commit()

def remove_favorite(user_id, movie_id):
    cursor = db.cursor()
    cursor.execute('DELETE FROM favorites WHERE user_id = ? AND movie_id = ?', (user_id, movie_id))
    db.commit()

def get_favorites(user_id):
    cursor = db.cursor()
    cursor.execute('SELECT movie_id, movie_title FROM favorites WHERE user_id = ?', (user_id,))
    return cursor.fetchall()

def is_favorite(user_id, movie_id):
    cursor = db.cursor()
    cursor.execute('SELECT 1 FROM favorites WHERE user_id = ? AND movie_id = ?', (user_id, movie_id))
    return cursor.fetchone() is not None

# Movie search functions
def is_movie_id(text):
    return text.isdigit()

def search_by_id(movie_id, chat_id, user_id=None):
    movie = tmdb.get_movie_details(movie_id)
    if movie and 'title' in movie:
        send_movie_card(chat_id, movie, user_id)
    else:
        bot.send_message(chat_id, f"❌ {movie_id} ID li film topilmadi!")

def search_by_name(query, chat_id, user_id):
    save_search(user_id, query)
    results = tmdb.search_movies(query)
    
    if results and 'results' in results and results['results']:
        movies = results['results'][:5]
        for movie in movies:
            send_movie_card(chat_id, movie, user_id)
    else:
        bot.send_message(chat_id, f"❌ '{query}' bo'yicha film topilmadi!")

def send_movie_card(chat_id, movie, user_id=None):
    title = movie.get('title', 'Noma\'lum')
    year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'Noma\'lum'
    rating = movie.get('vote_average', 0)
    overview = movie.get('overview', 'Tavsif mavjud emas.')
    movie_id = movie.get('id', 'Noma\'lum')
    
    text = f"""
🎬 *{title}* ({year})
⭐ {rating}/10 | 🆔 {movie_id}

{overview[:150]}...
    """
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    details_btn = types.InlineKeyboardButton("📖 Batafsil", callback_data=f"details_{movie_id}")
    trailer_btn = types.InlineKeyboardButton("🎥 Treyler", callback_data=f"trailer_{movie_id}")
    
    if user_id:
        favorite_text = "❌ Olib tashlash" if is_favorite(user_id, movie_id) else "❤️ Saqlash"
        favorite_btn = types.InlineKeyboardButton(favorite_text, callback_data=f"fav_{movie_id}_{title}")
        keyboard.add(details_btn, trailer_btn, favorite_btn)
    else:
        keyboard.add(details_btn, trailer_btn)
    
    poster = movie.get('poster_path')
    if poster:
        try:
            photo_url = f"{tmdb.image_base_url}{poster}"
            bot.send_photo(chat_id, photo_url, caption=text, reply_markup=keyboard, parse_mode='Markdown')
            return
        except:
            pass
    
    bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='Markdown')

# User commands
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user = message.from_user
    save_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = """
🎬 Mukammal Kino Botiga Xush Kelibsiz!

Qidirish usullari:
🔍 Film nomi: Avengers
🔢 Film ID: 550

Buyruqlar:
/popular - Mashhur filmlar
/favorites - Saqlanganlar
/help - Yordam
    """
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_cmd(message):
    help_text = """
Botdan foydalanish yo'riqnomasi:

1. Film nomi bilan qidirish:
Avengers, Titanic, Inception

2. Film ID bilan qidirish:
550, 680, 238

Buyruqlar:
/popular - Mashhur filmlar
/favorites - Saqlangan filmlar
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['popular'])
def popular_cmd(message):
    bot.send_message(message.chat.id, "🎯 Mashhur filmlar:", parse_mode='Markdown')
    movies = tmdb.get_popular_movies()
    if movies and 'results' in movies:
        for movie in movies['results'][:3]:
            send_movie_card(message.chat.id, movie, message.from_user.id)

@bot.message_handler(commands=['favorites'])
def favorites_cmd(message):
    favorites = get_favorites(message.from_user.id)
    if not favorites:
        bot.send_message(message.chat.id, "❤️ Saqlangan filmlaringiz yo'q!")
        return
    
    bot.send_message(message.chat.id, f"❤️ Saqlangan filmlar ({len(favorites)} ta):", parse_mode='Markdown')
    for movie_id, title in favorites[:5]:
        movie = tmdb.get_movie_details(movie_id)
        if movie:
            send_movie_card(message.chat.id, movie, message.from_user.id)

# Callback handlers
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    
    try:
        if data.startswith('details_'):
            movie_id = data.split('_')[1]
            show_movie_details(call.message.chat.id, movie_id, user_id)
            
        elif data.startswith('trailer_'):
            movie_id = data.split('_')[1]
            show_trailer(call.message.chat.id, movie_id)
            
        elif data.startswith('fav_'):
            parts = data.split('_')
            movie_id = parts[1]
            movie_title = '_'.join(parts[2:])
            
            if is_favorite(user_id, movie_id):
                remove_favorite(user_id, movie_id)
                bot.answer_callback_query(call.id, "❌ Saqlanganlardan olib tashlandi!")
            else:
                add_favorite(user_id, movie_id, movie_title.replace('_', ' '))
                bot.answer_callback_query(call.id, "❤️ Saqlandi!")
                
    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi!")

def show_movie_details(chat_id, movie_id, user_id):
    movie = tmdb.get_movie_details(movie_id)
    if not movie:
        bot.send_message(chat_id, "❌ Ma'lumot topilmadi!")
        return
    
    title = movie.get('title', 'Noma\'lum')
    rating = movie.get('vote_average', 0)
    year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'Noma\'lum'
    overview = movie.get('overview', 'Tavsif mavjud emas.')
    genres = [genre['name'] for genre in movie.get('genres', [])]
    
    text = f"""
🎬 {title} ({year})

⭐ Reyting: {rating}/10
🎭 Janr: {', '.join(genres) if genres else 'Noma\'lum'}

📖 {overview}
    """
    
    keyboard = types.InlineKeyboardMarkup()
    
    # Treyler
    videos = movie.get('videos', {}).get('results', [])
    trailer = next((video for video in videos if video['type'] == 'Trailer'), None)
    if trailer:
        trailer_btn = types.InlineKeyboardButton("🎥 Treylerni ko'rish", url=f"https://www.youtube.com/watch?v={trailer['key']}")
        keyboard.add(trailer_btn)
    
    bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='Markdown')

def show_trailer(chat_id, movie_id):
    movie = tmdb.get_movie_details(movie_id)
    if not movie:
        bot.send_message(chat_id, "❌ Treyler topilmadi!")
        return
    
    videos = movie.get('videos', {}).get('results', [])
    trailer = next((video for video in videos if video['type'] == 'Trailer'), None)
    
    if trailer:
        keyboard = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("🎥 YouTube da ko'rish", url=f"https://www.youtube.com/watch?v={trailer['key']}")
        keyboard.add(btn)
        bot.send_message(chat_id, f"🎬 {movie.get('title')} - Treyler", reply_markup=keyboard)
    else:
        bot.send_message(chat_id, "❌ Bu film uchun treyler topilmadi!")

# Main message handler
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_input = message.text.strip()
    
    if user_input.startswith('/'):
        bot.send_message(message.chat.id, "❌ Noma'lum buyruq! /help ni bosing.")
        return
    
    if is_movie_id(user_input):
        search_by_id(user_input, message.chat.id, message.from_user.id)
    else:
        search_by_name(user_input, message.chat.id, message.from_user.id)

# Botni ishga tushirish
if __name__ == '__main__':
    keep_alive()
    print("🎬 Mukammal Kino Bot ishga tushdi!")
    print("🌐 24/7 rejimida ishlayapti!")
    
    try:
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"Xato: {e}")
        time.sleep(15)
