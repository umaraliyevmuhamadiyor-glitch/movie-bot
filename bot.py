import telebot
from telebot import types
from pymongo import MongoClient
import os

# TOKENLAR
TOKEN = os.environ.get('TOKEN', "8420039863:AAFHchjf05kE8edLqPOfIY9xZjGqPikQ_wc")
MONGO_URL = os.environ.get('MONGO_URL', "mongodb+srv://umacriljewm.hamadiyor_db_user:kit7nqhk8Vv4nC7i@cluster0.evt8ebo.mongodb.net/?appName=Cluster0")

bot = telebot.TeleBot(TOKEN)
client = MongoClient(MONGO_URL)
db = client["kinochi_bot"]
collection = db["videos"]

# obuna bolish kerak bolgan kanallar
CHANNELS = ["@kinolamimi"]

# User kanallaga obuna bolganmi tekshirish
def check_user(user_id):
    for ch in CHANNELS:
        try:
            status = bot.get_chat_member(ch, user_id).status
            if status in ['left', 'kicked']:
                return False
        except:
            return False
    return True

# Kanalda video qo'shilganda
@bot.channel_post_handler(content_types=["video"])
def handle_channel_post(message):
    if message.chat.username == "kinolamimi":
        collection.insert_one({
            "file_id": message.video.file_id,
            "caption": message.caption or ""
        })

# obuna so'rovi
def ask_to_subscribe(chat_id):
    markup = types.InlineKeyboardMarkup()
    for ch in CHANNELS:
        markup.add(types.InlineKeyboardButton(text=ch, url=f"https://t.me/{ch[1:]}"))
    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check"))
    bot.send_message(chat_id, "📺 Botdan foydalanish uchun kanalga obuna bo'ling:", reply_markup=markup)

# start komandasi
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if check_user(user_id):
        bot.send_message(message.chat.id, "🎬 Botdan foydalanishingiz mumkin! Kod yuboring.")
    else:
        ask_to_subscribe(message.chat.id)

# tekshirish tugmasi
@bot.callback_query_handler(func=lambda call: call.data == "check")
def check_callback(call):
    user_id = call.from_user.id
    if check_user(user_id):
        bot.send_message(call.message.chat.id, "✅ Botdan foydalanishingiz mumkin! Kod yuboring.")
    else:
        bot.send_message(call.message.chat.id, "❌ Kanalga obuna bo'lmagansiz!")

# kod orqali video qidirish
@bot.message_handler(func=lambda message: True)
def all_messages(message):
    user_id = message.from_user.id
    if not check_user(user_id):
        ask_to_subscribe(message.chat.id)
        return

    if message.text.isdigit():
        found = False
        for video in collection.find():
            if video.get("caption") and f"Kod: {message.text}" in video["caption"]:
                bot.send_video(message.chat.id, video["file_id"], caption=video["caption"])
                found = True
                break
        if not found:
            bot.send_message(message.chat.id, f"❌ {message.text} kodli video topilmadi!")
    else:
        bot.send_message(message.chat.id, "🔢 Iltimos, faqat raqam yuboring!")

print("🚀 Bot ishga tushdi...")
bot.polling()
