import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand
import random
import sqlite3
from datetime import datetime, timedelta
import time
import os
import shutil

TOKEN = "8970700402:AAEheb9WtnO20ZsdN_MEbNEdBgDCwoZrT3I"
bot = telebot.TeleBot(TOKEN)

# --- АДМИН ID ---
ADMIN_ID = 7818787996  # ЗАМЕНИ!

# --- ПУТЬ К БД (для Railway Volume) ---
DB_PATH = '/data/casino_bot.db'
print(f"📁 Путь к БД: {DB_PATH}")

# Функция для проверки и создания БД
def check_db():
    """Проверяет существование БД и создаёт её при необходимости"""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"✅ Создана папка: {db_dir}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users
        (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            total_bet INTEGER DEFAULT 0,
            total_win INTEGER DEFAULT 0,
            last_salary TIMESTAMP
        )
    ''')
    conn.commit()
    
    # Проверяем количество записей
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    print(f"📊 В БД: {count} пользователей")
    
    conn.close()
    return True

# Функции для работы с БД
def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.execute('INSERT INTO users (user_id, balance, total_bet, total_win, last_salary) VALUES (?, 0, 0, 0, ?)',
                           (user_id, datetime.min))
            conn.commit()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
        return user
    finally:
        conn.close()

def update_balance(user_id, new_balance):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        conn.commit()
    finally:
        conn.close()

def update_stats(user_id, bet_amount, win_amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET total_bet = total_bet + ?, total_win = total_win + ? WHERE user_id = ?', 
                       (bet_amount, win_amount, user_id))
        conn.commit()
    finally:
        conn.close()

def update_last_salary(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET last_salary = ? WHERE user_id = ?', (datetime.now(), user_id))
        conn.commit()
    finally:
        conn.close()

def get_top_players(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?', (limit,))
        return cursor.fetchall()
    finally:
        conn.close()

# --- Команды ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    get_user(user_id)
    bot.reply_to(message, f"👋 Халяль, {message.from_user.first_name}!\n💰 Баланс: {get_user(user_id)[1]} халялек\n\n🎲 /dep 100 - сыграть\n💲 /salary - зарплата\n💎 /balance - баланс\n🏅 /top - топ")

@bot.message_handler(commands=['salary'])
def salary_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last_salary = datetime.fromisoformat(user[4]) if user[4] else datetime.min
    
    if datetime.now() - last_salary < timedelta(minutes=30):
        next_salary = last_salary + timedelta(minutes=30)
        remaining = next_salary - datetime.now()
        mins, secs = divmod(remaining.seconds, 60)
        bot.reply_to(message, f"⏰ Зарплата через {mins} мин {secs} сек")
        return
    
    update_balance(user_id, user[1] + 100)
    update_last_salary(user_id)
    bot.reply_to(message, f"💲 +100 халялек! Баланс: {user[1] + 100}")

@bot.message_handler(commands=['balance'])
def balance_command(message):
    user = get_user(message.from_user.id)
    bot.reply_to(message, f"💎 Баланс: {user[1]} халялек")

@bot.message_handler(commands=['top'])
def top_command(message):
    top_users = get_top_players(10)
    if not top_users:
        bot.reply_to(message, "🏅 Топ пока пуст")
        return
    text = "🏅 ТОП халялей 🏅\n\n"
    for i, (uid, bal) in enumerate(top_users, 1):
        name = str(uid)
        try:
            chat = bot.get_chat(uid)
            name = chat.first_name or name
        except:
            pass
        text += f"{i}. {name} — {bal}\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['dep'])
def dep(message):
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, "❗ /dep [сумма]")
        return
    try:
        bet = int(args[1])
        if bet <= 0:
            bot.reply_to(message, "❗ Сумма > 0")
            return
    except:
        bot.reply_to(message, "❗ Введи число")
        return
    
    user = get_user(message.from_user.id)
    if bet > user[1]:
        bot.reply_to(message, f"❗ Недостаточно! Баланс: {user[1]}")
        return
    
    if random.choice([True, False]):
        update_balance(message.from_user.id, user[1] + bet)
        update_stats(message.from_user.id, bet, bet)
        bot.reply_to(message, f"✅ ХАЛЯЛЬ! +{bet}\n💲 Баланс: {user[1] + bet}")
    else:
        update_balance(message.from_user.id, user[1] - bet)
        update_stats(message.from_user.id, bet, 0)
        bot.reply_to(message, f"❌ НЕ ХАЛЯЛЬ! -{bet}\n💲 Баланс: {user[1] - bet}")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "📖 /dep [сумма] - игра\n💲 /salary - зарплата (30 мин)\n💎 /balance - баланс\n🏅 /top - топ")

# --- Запуск ---
if __name__ == '__main__':
    print("🚀 Запуск бота...")
    check_db()  # Проверяем БД
    print(f"📁 БД находится: {DB_PATH}")
    print(f"📁 Файл существует: {os.path.exists(DB_PATH)}")
    
    bot.remove_webhook()
    print("✅ Бот готов!")
    
    bot.infinity_polling(timeout=60)
