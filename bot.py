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
    
    # Foydalanuvchilar
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
    
    # Search history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Favorites
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_id INTEGER,
            movie_title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Statistics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            date TEXT PRIMARY KEY,
            users_count INTEGER DEFAULT 0,
            searches_count INTEGER DEFAULT 0
        )
    ''')
    
    # Bot sozlamalari
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    conn.commit()
    return conn

db = init_db()

# Sozlamalarni saqlash/o'qish
def get_setting(key, default=None):
    cursor = db.cursor()
    cursor.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    return result[0] if result else default

def set_setting(key, value):
    cursor = db.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO bot_settings (key, value)
        VALUES (?, ?)
    ''', (key, value))
    db.commit()

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
            'append_to_response': 'credits,videos,recommendations',
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
    
    def get_upcoming_movies(self, page=1):
        url = f"{self.base_url}/movie/upcoming"
        params = {
            'api_key': self.api_key,
            'page': page,
            'language': 'ru'
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Upcoming movies error: {e}")
            return None
    
    def get_top_rated(self, page=1):
        url = f"{self.base_url}/movie/top_rated"
        params = {
            'api_key': self.api_key,
            'page': page,
            'language': 'ru'
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Top rated error: {e}")
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

def get_user_count():
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    return cursor.fetchone()[0]

def get_search_count():
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM search_history')
    return cursor.fetchone()[0]

def get_all_users():
    cursor = db.cursor()
    cursor.execute('SELECT user_id, username, first_name, subscribed FROM users')
    return cursor.fetchall()

def update_stats():
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    cursor = db.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO statistics (date, users_count, searches_count)
        VALUES (?, ?, ?)
    ''', (today, get_user_count(), get_search_count()))
    db.commit()

# Admin check
def is_admin(user_id):
    return user_id in ADMIN_IDS

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

Asosiy menyu:
🎯 /popular - Mashhur filmlar
🚀 /upcoming - Tez kunda
🏆 /top - Eng yaxshilar
❤️ /favorites - Saqlanganlar
📊 /stats - Statistika
🎪 /genres - Janrlar

Admin panel: /admin
Yordam: /help
    """
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🔍 Qidirish", switch_inline_query_current_chat="")
    btn2 = types.InlineKeyboardButton("🎯 Mashhurlar", callback_data="popular_main")
    btn3 = types.InlineKeyboardButton("❤️ Saqlanganlar", callback_data="favorites_main")
    btn4 = types.InlineKeyboardButton("📊 Statistika", callback_data="stats_main")
    keyboard.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=keyboard)

@bot.message_handler(commands=['help'])
def help_cmd(message):
    help_text = """
Botdan foydalanish yo'riqnomasi:

1. Film nomi bilan qidirish:
Avengers, Titanic, Inception

2. Film ID bilan qidirish:
550, 680, 238

Mashhur film ID lari:
• 550 - Jangchi klubi
• 680 - Pulp Fiction  
• 238 - Krestiy ota
• 13 - Forrest Gump
• 155 - Qora ritsar

Buyruqlar:
/popular - Mashhur filmlar
/upcoming - Tez orada
/top - Eng yuqori reytingli
/favorites - Saqlangan filmlar
/stats - Shaxsiy statistika
/genres - Janrlar bo'yicha
/admin - Admin panel
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['popular'])
def popular_cmd(message):
    bot.send_message(message.chat.id, "🎯 Mashhur filmlar:", parse_mode='Markdown')
    movies = tmdb.get_popular_movies()
    if movies and 'results' in movies:
        for movie in movies['results'][:5]:
            send_movie_card(message.chat.id, movie, message.from_user.id)

@bot.message_handler(commands=['upcoming'])
def upcoming_cmd(message):
    bot.send_message(message.chat.id, "🚀 Tez orada chiqadigan filmlar:", parse_mode='Markdown')
    movies = tmdb.get_upcoming_movies()
    if movies and 'results' in movies:
        for movie in movies['results'][:5]:
            send_movie_card(message.chat.id, movie, message.from_user.id)

@bot.message_handler(commands=['top'])
def top_cmd(message):
    bot.send_message(message.chat.id, "🏆 Eng yuqori reytingli filmlar:", parse_mode='Markdown')
    movies = tmdb.get_top_rated()
    if movies and 'results' in movies:
        for movie in movies['results'][:5]:
            send_movie_card(message.chat.id, movie, message.from_user.id)

@bot.message_handler(commands=['favorites'])
def favorites_cmd(message):
    favorites = get_favorites(message.from_user.id)
    if not favorites:
        bot.send_message(message.chat.id, "❤️ Saqlangan filmlaringiz yo'q!")
        return
    
    bot.send_message(message.chat.id, f"❤️ Saqlangan filmlar ({len(favorites)} ta):", parse_mode='Markdown')
    for movie_id, title in favorites[:10]:
        movie = tmdb.get_movie_details(movie_id)
        if movie:
            send_movie_card(message.chat.id, movie, message.from_user.id)

@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    user_id = message.from_user.id
    favorites = get_favorites(user_id)
    
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM search_history WHERE user_id = ?', (user_id,))
    search_count = cursor.fetchone()[0]
    
    text = f"""
📊 Sizning statistikangiz:

🔍 Qidiruvlar soni: {search_count}
❤️ Saqlangan filmlar: {len(favorites)}
👤 Faollik darajasi: {'🎯 Yuqori' if search_count > 10 else '🟰 Oʻrta' if search_count > 5 else '🔰 Boshlangʻich'}
    """
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['genres'])
def genres_cmd(message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    genres = [
        ("🎭 Drama", "28"), ("🤣 Komediya", "35"), ("💥 Jangari", "28"),
        ("❤️ Romantika", "10749"), ("🔍 Detektiv", "9648"), ("🚀 Fantastika", "878"),
        ("👻 Qo'rqinchli", "27"), ("🎵 Musiqiy", "10402"), ("🏰 Tarixiy", "36")
    ]
    
    for genre_name, genre_id in genres:
        btn = types.InlineKeyboardButton(genre_name, callback_data=f"genre_{genre_id}")
        keyboard.add(btn)
    
    bot.send_message(message.chat.id, "🎪 Janrlar bo'yicha filmlar:", reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['myid'])
def get_my_id(message):
    user_id = message.from_user.id
    bot.send_message(message.chat.id, f"🆔 Sizning ID: {user_id}", parse_mode='Markdown')

# Admin commands
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Ruxsat yo'q!")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
    btn2 = types.InlineKeyboardButton("📢 Reklama", callback_data="admin_broadcast")
    btn3 = types.InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users")
    btn4 = types.InlineKeyboardButton("⚙️ Sozlamalar", callback_data="admin_settings")
    btn5 = types.InlineKeyboardButton("🔄 Yangilash", callback_data="admin_update")
    btn6 = types.InlineKeyboardButton("💾 Backup", callback_data="admin_backup")
    keyboard.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    admin_text = """
👨‍💼 Admin Panel

Bot ma'lumotlari:
• Foydalanuvchilar: {users_count}
• Qidiruvlar: {searches_count}
• Bot holati: 🟢 Faol
• Versiya: 2.0
    """.format(users_count=get_user_count(), searches_count=get_search_count())
    
    bot.send_message(message.chat.id, admin_text, parse_mode='Markdown', reply_markup=keyboard)

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
                
        elif data.startswith('admin_'):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
                return
                
            if data == 'admin_stats':
                show_admin_stats(call)
            elif data == 'admin_broadcast':
                start_broadcast(call)
            elif data == 'admin_users':
                show_admin_users(call)
            elif data == 'admin_settings':
                show_admin_settings(call)
            elif data == 'admin_update':
                update_stats()
                bot.answer_callback_query(call.id, "✅ Statistika yangilandi!")
            elif data == 'admin_backup':
                backup_database(call)
                
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
    runtime = movie.get('runtime', 'Noma\'lum')
    budget = movie.get('budget', 0)
    revenue = movie.get('revenue', 0)
    overview = movie.get('overview', 'Tavsif mavjud emas.')
    genres = [genre['name'] for genre in movie.get('genres', [])]
    
    # Aktyorlar
    credits = movie.get('credits', {})
    cast = credits.get('cast', [])[:5]
    cast_names = [actor['name'] for actor in cast]
    
    text = f"""
🎬 {title} ({year})

⭐ Reyting: {rating}/10
⏱️ Davomiylik: {runtime} daqiqa
🎭 Janr: {', '.join(genres) if genres else 'Noma\'lum'}
💰 Byudjet: ${budget:,}
🏦 Daromad: ${revenue:,}

👥 Aktyorlar: {', '.join(cast_names) if cast_names else 'Noma\'lum'}

📖 {overview}
    """
    
    keyboard = types.InlineKeyboardMarkup()
    
    # Treyler
    videos = movie.get('videos', {}).get('results', [])
    trailer = next((video for video in videos if video['type'] == 'Trailer'), None)
    if trailer:
        trailer_btn = types.InlineKeyboardButton("🎥 Treylerni ko'rish", url=f"https://www.youtube.com/watch?v={trailer['key']}")
        keyboard.add(trailer_btn)
    
    # Sevimlilar
    favorite_text = "❌ Sevimlilardan olib tashlash" if is_favorite(user_id, movie_id) else "❤️ Sevimlilarga qo'shish"
    favorite_btn = types.InlineKeyboardButton(favorite_text, callback_data=f"fav_{movie_id}_{title}")
    keyboard.add(favorite_btn)
    
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

# Admin functions
def show_admin_stats(call):
    update_stats()
    total_users = get_user_count()
    total_searches = get_search_count()
    
    text = f"""
📊 Bot Statistikasi:

👥 Jami foydalanuvchilar: {total_users}
🔍 Jami qidiruvlar: {total_searches}
🟢 Bot holati: Faol
🌐 24/7 rejimida
💾 Ma'lumotlar bazasi: Ishlamoqda
    """
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

def start_broadcast(call):
    msg = bot.send_message(call.message.chat.id, "📢 Reklama matnini yuboring:")
