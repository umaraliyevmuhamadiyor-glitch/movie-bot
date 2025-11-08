import os
import logging
import sqlite3
import datetime
from telebot import TeleBot, types
from threading import Thread
import time
from flask import Flask, request
import requests

# Flask server for 24/7
app = Flask(__name__)

# Log sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguratsiya
BOT_TOKEN = "7353875365:AAENeauCMHfEfUKGGKR9yr6WurVAqERctKA"
ADMIN_ID = 7439952029

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
            subscribed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Kinolar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            file_id TEXT,
            file_type TEXT,
            description TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Majburiy kanallar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            channel_name TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Statistika
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            date TEXT PRIMARY KEY,
            users_count INTEGER DEFAULT 0,
            movies_count INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    return conn

db = init_db()

# Database functions
def save_user(user_id, username, first_name, last_name):
    cursor = db.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    db.commit()

def update_user_subscription(user_id, subscribed):
    cursor = db.cursor()
    cursor.execute('UPDATE users SET subscribed = ? WHERE user_id = ?', (subscribed, user_id))
    db.commit()

def get_user(user_id):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def add_movie(code, file_id, file_type, description, added_by):
    cursor = db.cursor()
    try:
        cursor.execute('''
            INSERT INTO movies (code, file_id, file_type, description, added_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (code, file_id, file_type, description, added_by))
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_movie(code):
    cursor = db.cursor()
    cursor.execute('DELETE FROM movies WHERE code = ?', (code,))
    db.commit()
    return cursor.rowcount > 0

def get_movie(code):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM movies WHERE code = ?', (code,))
    return cursor.fetchone()

def get_all_movies():
    cursor = db.cursor()
    cursor.execute('SELECT code, description FROM movies ORDER BY added_at DESC')
    return cursor.fetchall()

def add_channel(channel_id, channel_name, added_by):
    cursor = db.cursor()
    try:
        cursor.execute('''
            INSERT INTO channels (channel_id, channel_name, added_by)
            VALUES (?, ?, ?)
        ''', (channel_id, channel_name, added_by))
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_channel(channel_id):
    cursor = db.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    db.commit()
    return cursor.rowcount > 0

def get_channels():
    cursor = db.cursor()
    cursor.execute('SELECT channel_id, channel_name FROM channels')
    return cursor.fetchall()

def get_user_count():
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    return cursor.fetchone()[0]

def get_movies_count():
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM movies')
    return cursor.fetchone()[0]

def get_subscribed_users_count():
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE subscribed = 1')
    return cursor.fetchone()[0]

# Admin check
def is_admin(user_id):
    return user_id == ADMIN_ID

# Channel subscription check
def check_subscription(user_id):
    channels = get_channels()
    if not channels:
        return True
    
    for channel in channels:
        try:
            chat_member = bot.get_chat_member(channel[0], user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logger.error(f"Channel check error: {e}")
            return False
    return True

# Flask routes
@app.route('/')
def home():
    return "🎬 Kino Bot 24/7 Ishlamoqda!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'OK'

# User commands
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user = message.from_user
    save_user(user.id, user.username, user.first_name, user.last_name)
    
    if is_admin(user.id):
        # Admin uchun
        admin_text = """
👨‍💼 *Admin Panelga Xush Kelibsiz!*

*Admin Buyruqlari:*
🎬 /addmovie - Kino qo'shish
🗑️ /deletemovie - Kino o'chirish  
📊 /stats - Statistika
📢 /broadcast - Xabar yuborish
📺 /channels - Kanallarni boshqarish

*Foydalanuvchi Buyruqlari:*
🔍 Kod yuboring - Kino olish
        """
        bot.send_message(message.chat.id, admin_text, parse_mode='Markdown')
    else:
        # Foydalanuvchi uchun
        user_text = """
🎬 *Kino Botga Xush Kelibsiz!*

Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling va kod yuboring.

*Qanday ishlaydi:*
1. Kanallarga obuna bo'ling
2. "Obuna boldim" tugmasini bosing
3. Kod yuboring
4. Kino oling!

Kod yuborish uchun faqat raqam yuboring.
        """
        
        # Kanallarni tekshirish
        if check_subscription(user.id):
            update_user_subscription(user.id, 1)
            bot.send_message(message.chat.id, user_text, parse_mode='Markdown')
        else:
            show_subscription_request(message.chat.id)

def show_subscription_request(chat_id):
    channels = get_channels()
    if not channels:
        bot.send_message(chat_id, "✅ Siz botdan foydalana olasiz! Kod yuboring.")
        return
    
    keyboard = types.InlineKeyboardMarkup()
    
    for channel in channels:
        btn = types.InlineKeyboardButton(f"📺 {channel[1]}", url=f"https://t.me/{channel[0][1:]}")
        keyboard.add(btn)
    
    check_btn = types.InlineKeyboardButton("✅ Obuna boldim", callback_data="check_subscription")
    keyboard.add(check_btn)
    
    text = "📺 *Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:*"
    bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    user_id = call.from_user.id
    
    if check_subscription(user_id):
        update_user_subscription(user_id, 1)
        bot.edit_message_text(
            "✅ *Obuna tekshirildi! Endi kod yuborib kino olishingiz mumkin.*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    else:
        bot.answer_callback_query(call.id, "❌ Hali barcha kanallarga obuna bo'lmagansiz!")

# Movie search
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    
    # Admin buyruqlari
    if is_admin(user_id):
        handle_admin_commands(message)
        return
    
    # Foydalanuvchi uchun
    user = get_user(user_id)
    if not user or user[4] == 0:  # subscribed = 0
        show_subscription_request(message.chat.id)
        return
    
    # Kod qidirish
    code = message.text.strip()
    movie = get_movie(code)
    
    if movie:
        try:
            if movie[3] == 'video':  # file_type
                bot.send_video(message.chat.id, movie[2], caption=movie[4])
            else:  # photo yoki document
                bot.send_document(message.chat.id, movie[2], caption=movie[4])
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xatolik: {e}")
    else:
        bot.send_message(message.chat.id, "❌ Bu kod bo'yicha kino topilmadi!")

# Admin commands handler
def handle_admin_commands(message):
    text = message.text.strip()
    
    if text == '/stats':
        show_stats(message)
    elif text == '/channels':
        show_channels_management(message)
    elif text == '/addmovie':
        msg = bot.send_message(message.chat.id, "🎬 Kino qo'shish:\nKodni kiriting:")
        bot.register_next_step_handler(msg, process_movie_code)
    elif text == '/deletemovie':
        msg = bot.send_message(message.chat.id, "🗑️ Kino o'chirish:\nO'chiriladigan kodni kiriting:")
        bot.register_next_step_handler(msg, process_delete_movie)
    elif text == '/broadcast':
        msg = bot.send_message(message.chat.id, "📢 Xabar yuborish:\nXabarni kiriting:")
        bot.register_next_step_handler(msg, process_broadcast)

def process_movie_code(message):
    code = message.text.strip()
    msg = bot.send_message(message.chat.id, "📝 Kino tavsifini kiriting:")
    bot.register_next_step_handler(msg, process_movie_description, code)

def process_movie_description(message, code):
    description = message.text.strip()
    msg = bot.send_message(message.chat.id, "📁 Kino faylini yuboring (video yoki file):")
    bot.register_next_step_handler(msg, process_movie_file, code, description)

def process_movie_file(message, code, description):
    if message.video:
        file_id = message.video.file_id
        file_type = 'video'
    elif message.document:
        file_id = message.document.file_id
        file_type = 'document'
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = 'photo'
    else:
        bot.send_message(message.chat.id, "❌ Faqat video yoki fayl yuboring!")
        return
    
    if add_movie(code, file_id, file_type, description, message.from_user.id):
        bot.send_message(message.chat.id, f"✅ Kino qo'shildi!\nKod: {code}")
    else:
        bot.send_message(message.chat.id, "❌ Bu kod allaqachon mavjud!")

def process_delete_movie(message):
    code = message.text.strip()
    if delete_movie(code):
        bot.send_message(message.chat.id, f"✅ Kino o'chirildi!\nKod: {code}")
    else:
        bot.send_message(message.chat.id, "❌ Bu kod bo'yicha kino topilmadi!")

def show_stats(message):
    total_users = get_user_count()
    total_movies = get_movies_count()
    subscribed_users = get_subscribed_users_count()
    
    text = f"""
📊 *Bot Statistikasi:*

👥 Jami foydalanuvchilar: {total_users}
✅ Obuna bo'lganlar: {subscribed_users}
🎬 Jami kinolar: {total_movies}
🟢 Bot holati: Faol
    """
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def show_channels_management(message):
    channels = get_channels()
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    add_btn = types.InlineKeyboardButton("📺 Kanal qo'shish", callback_data="add_channel")
    delete_btn = types.InlineKeyboardButton("🗑️ Kanal o'chirish", callback_data="delete_channel")
    list_btn = types.InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="list_channels")
    keyboard.add(add_btn, delete_btn, list_btn)
    
    text = "📺 *Kanallarni Boshqarish*"
    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith(('add_channel', 'delete_channel', 'list_channels')))
def handle_channels_callbacks(call):
    if call.data == 'add_channel':
        msg = bot.send_message(call.message.chat.id, "Kanal username ni kiriting (@ belgisi bilan):")
        bot.register_next_step_handler(msg, process_add_channel)
    elif call.data == 'delete_channel':
        msg = bot.send_message(call.message.chat.id, "O'chiriladikan kanal username ni kiriting:")
        bot.register_next_step_handler(msg, process_delete_channel)
    elif call.data == 'list_channels':
        show_channels_list(call.message.chat.id)

def process_add_channel(message):
    channel_id = message.text.strip()
    if not channel_id.startswith('@'):
        bot.send_message(message.chat.id, "❌ Kanal username @ belgisi bilan boshlanishi kerak!")
        return
    
    try:
        chat = bot.get_chat(channel_id)
        if add_channel(channel_id, chat.title, message.from_user.id):
            bot.send_message(message.chat.id, f"✅ Kanal qo'shildi: {chat.title}")
        else:
            bot.send_message(message.chat.id, "❌ Bu kanal allaqachon qo'shilgan!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Kanal topilmadi yoki bot admin emas!")

def process_delete_channel(message):
    channel_id = message.text.strip()
    if delete_channel(channel_id):
        bot.send_message(message.chat.id, f"✅ Kanal o'chirildi: {channel_id}")
    else:
        bot.send_message(message.chat.id, "❌ Bu kanal topilmadi!")

def show_channels_list(chat_id):
    channels = get_channels()
    if not channels:
        bot.send_message(chat_id, "📺 Hozircha kanallar mavjud emas.")
        return
    
    text = "📺 *Majburiy Kanallar:*\n\n"
    for i, channel in enumerate(channels, 1):
        text += f"{i}. {channel[1]} ({channel[0]})\n"
    
    bot.send_message(chat_id, text, parse_mode='Markdown')

def process_broadcast(message):
    if not is_admin(message.from_user.id):
        return
    
    users = db.cursor().execute('SELECT user_id FROM users').fetchall()
    success = 0
    failed = 0
    
    bot.send_message(message.chat.id, f"📢 Xabar {len(users)} foydalanuvchiga yuborilmoqda...")
    
    for user in users:
        try:
            bot.send_message(user[0], f"📢 {message.text}")
            success += 1
            time.sleep(0.1)
        except:
            failed += 1
    
    bot.send_message(message.chat.id, f"""
✅ Xabar yuborildi:
✔️ Muvaffaqiyatli: {success}
❌ Xatolik: {failed}
    """)

# Background task for cleanup
def background_tasks():
    while True:
        try:
            # Har 1 soatda ma'lumotlarni yangilash
            time.sleep(3600)
        except Exception as e:
            logger.error(f"Background task error: {e}")
            time.sleep(300)

# Start background task
Thread(target=background_tasks, daemon=True).start()

# Botni ishga tushirish
if __name__ == '__main__':
    # Webhook sozlash
    try:
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"https://movie-bot-jegapomember.com/{BOT_TOKEN}"
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook sozlandi: {webhook_url}")
    except Exception as e:
        print(f"❌ Webhook sozlashda xato: {e}")
    
    print("🎬 Kino Bot ishga tushdi!")
    print("🌐 Webhook rejimida ishlayapti!")
    print("💾 Ma'lumotlar bazasi ishga tushirildi!")
    
    # Flask serverni ishga tushirish
    app.run(host='0.0.0.0', port=8080)
