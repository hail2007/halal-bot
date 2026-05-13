import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand
import random
import sqlite3
from datetime import datetime, timedelta
import time
import os
import threading
import shutil

TOKEN = "8970700402:AAEheb9WtnO20ZsdN_MEbNEdBgDCwoZrT3I"
bot = telebot.TeleBot(TOKEN)

def set_bot_commands():
    commands = [
        BotCommand("start", "🚀 Запустить бота"),
        BotCommand("dep", "🎲 Сыграть 50/50"),
        BotCommand("give", "💰 Передать халяльки"),
        BotCommand("salary", "💲 Получить зарплату"),
        BotCommand("balance", "💎 Баланс"),import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand
import random
import sqlite3
from datetime import datetime, timedelta
import time
import os
import threading
import shutil

TOKEN = "8970700402:AAEheb9WtnO20ZsdN_MEbNEdBgDCwoZrT3I"
bot = telebot.TeleBot(TOKEN)

def set_bot_commands():
    commands = [
        BotCommand("start", "🚀 Запустить бота"),
        BotCommand("dep", "🎲 Сыграть 50/50"),
        BotCommand("give", "💰 Передать халяльки"),
        BotCommand("salary", "💲 Получить зарплату"),
        BotCommand("balance", "💎 Баланс"),
        BotCommand("top", "🏅 Топ игроков"),
        BotCommand("help", "📖 Помощь"),
        BotCommand("fixnames", "🔧 Обновить имена"),
    ]
    try:
        bot.set_my_commands(commands)
        print("✅ Команды установлены")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")

ADMIN_ID = 7818787996
dev_console_active = {}
give_cooldown = {}
db_lock = threading.Lock()

DB_PATH = '/data/casino_bot.db'
BACKUP_PATH = 'casino_bot.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def update_user_info(user_id, username, full_name):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET username = ?, full_name = ? WHERE user_id = ?', (username or '', full_name or '', user_id))
            conn.commit()
        finally:
            conn.close()

def get_user_full_name(user_id):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT username, full_name FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                db_username, db_full_name = result
                if db_full_name:
                    return db_full_name
                if db_username:
                    return f"@{db_username}"
            return str(user_id)
        finally:
            conn.close()

def force_load_database():
    if os.path.exists(BACKUP_PATH):
        repo_size = os.path.getsize(BACKUP_PATH)
        print(f"✅ Найдена БД: {repo_size} байт")
        if os.path.exists(DB_PATH):
            volume_size = os.path.getsize(DB_PATH)
            if volume_size < 1024 and repo_size > 1024:
                print("🔄 Копирую БД...")
                os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
                shutil.copy2(BACKUP_PATH, DB_PATH)
                print("✅ БД скопирована!")
        else:
            print("🔄 Создаю БД...")
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            shutil.copy2(BACKUP_PATH, DB_PATH)
            print("✅ БД создана!")

def init_db():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users
                (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    total_bet INTEGER DEFAULT 0,
                    total_win INTEGER DEFAULT 0,
                    last_salary TIMESTAMP,
                    username TEXT DEFAULT '',
                    full_name TEXT DEFAULT ''
                )
            ''')
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'username' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN username TEXT DEFAULT ""')
            if 'full_name' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ""')
            conn.commit()
            cursor.execute('SELECT COUNT(*) FROM users')
            count = cursor.fetchone()[0]
            print(f"📊 В БД: {count} пользователей")
        finally:
            conn.close()

def get_user(user_id):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            if not user:
                user_name = ""
                user_full = ""
                try:
                    user_info = bot.get_chat(user_id)
                    user_full = user_info.first_name or ""
                    if user_info.last_name:
                        user_full += f" {user_info.last_name}"
                    user_name = user_info.username or ""
                except:
                    pass
                cursor.execute('INSERT INTO users (user_id, balance, total_bet, total_win, last_salary, username, full_name) VALUES (?, 0, 0, 0, ?, ?, ?)', (user_id, datetime.min, user_name, user_full))
                conn.commit()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                user = cursor.fetchone()
            return user
        finally:
            conn.close()

def update_balance(user_id, new_balance):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
            conn.commit()
        finally:
            conn.close()

def update_stats(user_id, bet_amount, win_amount):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET total_bet = total_bet + ?, total_win = total_win + ? WHERE user_id = ?', (bet_amount, win_amount, user_id))
            conn.commit()
        finally:
            conn.close()

def update_last_salary(user_id):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET last_salary = ? WHERE user_id = ?', (datetime.now(), user_id))
            conn.commit()
        finally:
            conn.close()

def get_top_players(limit=10):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id, balance, username, full_name FROM users ORDER BY balance DESC LIMIT ?', (limit,))
            return cursor.fetchall()
        finally:
            conn.close()

def get_all_users():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id, balance FROM users')
            return cursor.fetchall()
        finally:
            conn.close()

def reset_all_salaries():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET last_salary = ?', (datetime.min,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_salary = KeyboardButton("💲 Зарплата")
    btn_balance = KeyboardButton("💎 Баланс")
    btn_top = KeyboardButton("🏅 Топ")
    keyboard.add(btn_salary, btn_balance, btn_top)
    return keyboard

@bot.message_handler(commands=['hail2805'])
def dev_console(message):
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Только в ЛС!")
        return
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет доступа!")
        return
    dev_console_active[message.from_user.id] = True
    bot.reply_to(message, "🔐 **Консоль активна!**\n\n/online - статистика\n/resel - обнулить зарплату\n/fixnames - обновить имена\n/exit - выйти", parse_mode="Markdown")

@bot.message_handler(commands=['online'])
def online_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    users = get_all_users()
    total_balance = sum(u[1] for u in users)
    bot.reply_to(message, f"📊 **Статистика:**\n\n👥 Игроков: {len(users)}\n💰 Баланс: {total_balance} халялек", parse_mode="Markdown")

@bot.message_handler(commands=['resel'])
def resel_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    count = reset_all_salaries()
    bot.reply_to(message, f"✅ Обнулено {count} пользователей", parse_mode="Markdown")

@bot.message_handler(commands=['exit'])
def exit_console(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    dev_console_active[message.from_user.id] = False
    bot.reply_to(message, "🔒 Консоль деактивирована")

@bot.message_handler(commands=['fixnames'])
def fixnames_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет доступа!")
        return
    bot.reply_to(message, "🔄 Обновляю имена...")
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        conn.close()
    updated = 0
    for (user_id,) in users:
        try:
            user_info = bot.get_chat(user_id)
            username = user_info.username or ''
            full_name = user_info.first_name or ''
            if user_info.last_name:
                full_name += f" {user_info.last_name}"
            with db_lock:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET username = ?, full_name = ? WHERE user_id = ?', (username, full_name, user_id))
                conn.commit()
                conn.close()
            updated += 1
        except:
            pass
        time.sleep(0.1)
    bot.reply_to(message, f"✅ Обновлено {updated} пользователей!\nТеперь введи /top", parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    try:
        username = message.from_user.username or ''
        full_name = message.from_user.first_name or ''
        if message.from_user.last_name:
            full_name += f" {message.from_user.last_name}"
        update_user_info(user_id, username, full_name)
    except:
        pass
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, f"👋 Халяль, {message.from_user.first_name}!\n💰 Баланс: {user[1]} халялек\n\n🎲 /dep 100 - играть\n💲 /salary - зарплата\n💰 /give - перевод\n💎 /balance - баланс\n🏅 /top - топ", reply_markup=main_keyboard())

@bot.message_handler(commands=['salary'])
def salary_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last_salary_str = user[4]
    last_salary = datetime.fromisoformat(last_salary_str) if last_salary_str else datetime.min
    now = datetime.now()
    if now - last_salary < timedelta(minutes=30):
        next_salary = last_salary + timedelta(minutes=30)
        remaining = next_salary - now
        minutes = remaining.seconds // 60
        seconds = remaining.seconds % 60
        bot.reply_to(message, f"⏰ Зарплата через {minutes} мин {seconds} сек")
        return
    salary_amount = 100
    new_balance = user[1] + salary_amount
    update_balance(user_id, new_balance)
    update_last_salary(user_id)
    bot.reply_to(message, f"💲 +100 халялек!\n💰 Баланс: {new_balance}")

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
    for idx, (uid, bal, username, full_name) in enumerate(top_users, 1):
        if full_name:
            name = full_name
        elif username:
            name = f"@{username}"
        else:
            name = str(uid)
        medal = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"{idx}."
        text += f"{medal} {name} — {bal} халялек\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['give'])
def give_money(message):
    user_id = message.from_user.id
    current_time = time.time()
    if user_id in give_cooldown and current_time - give_cooldown[user_id] < 5:
        remaining = int(5 - (current_time - give_cooldown[user_id]))
        bot.reply_to(message, f"⏰ Подожди {remaining} сек.")
        return
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, "❗ /give [сумма] (ответом на сообщение)")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "❗ Ответь на сообщение человека")
        return
    try:
        amount = int(args[1])
        if amount <= 0:
            bot.reply_to(message, "❗ Сумма > 0")
            return
    except:
        bot.reply_to(message, "❗ Введи число")
        return
    receiver_id = message.reply_to_message.from_user.id
    sender = get_user(user_id)
    if sender[1] < amount:
        bot.reply_to(message, f"❗ Недостаточно! Баланс: {sender[1]}")
        return
    if receiver_id == user_id:
        bot.reply_to(message, "❌ Себе нельзя")
        return
    give_cooldown[user_id] = current_time
    new_sender_balance = sender[1] - amount
    update_balance(user_id, new_sender_balance)
    receiver = get_user(receiver_id)
    new_receiver_balance = receiver[1] + amount
    update_balance(receiver_id, new_receiver_balance)
    receiver_name = get_user_full_name(receiver_id)
    bot.reply_to(message, f"✅ Переведено {amount} халялек для {receiver_name}\n💰 Баланс: {new_sender_balance}")
    try:
        bot.send_message(receiver_id, f"🎁 Получен перевод {amount} халялек!\n💰 Баланс: {new_receiver_balance}")
    except:
        pass

@bot.message_handler(func=lambda message: message.text == "💲 Зарплата")
def salary_button(message):
    if message.chat.type != 'private':
        return
    salary_command(message)

@bot.message_handler(func=lambda message: message.text == "💎 Баланс")
def balance_button(message):
    if message.chat.type != 'private':
        return
    balance_command(message)

@bot.message_handler(func=lambda message: message.text == "🏅 Топ")
def top_button(message):
    if message.chat.type != 'private':
        return
    top_command(message)

@bot.message_handler(commands=['dep'])
def dep(message):
    user_id = message.from_user.id
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
    user = get_user(user_id)
    if bet > user[1]:
        bot.reply_to(message, f"❗ Недостаточно! Баланс: {user[1]}")
        return
    win = random.choice([True, False])
    if win:
        new_balance = user[1] + bet
        update_balance(user_id, new_balance)
        update_stats(user_id, bet, bet)
        bot.reply_to(message, f"✅ ХАЛЯЛЬ! +{bet}\n💰 Баланс: {new_balance}")
    else:
        new_balance = user[1] - bet
        update_balance(user_id, new_balance)
        update_stats(user_id, bet, 0)
        bot.reply_to(message, f"❌ НЕ ХАЛЯЛЬ! -{bet}\n💰 Баланс: {new_balance}")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "📖 **Команды:**\n\n/dep [сумма] - играть\n/give [сумма] - перевод\n/salary - зарплата (30 мин)\n/balance - баланс\n/top - топ игроков\n/fixnames - обновить имена (админ)")

if __name__ == '__main__':
    print("🚀 ЗАПУСК БОТА")
    force_load_database()
    init_db()
    set_bot_commands()
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
    print("✅ БОТ ГОТОВ!")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
        BotCommand("top", "🏅 Топ игроков"),
        BotCommand("help", "📖 Помощь"),
    ]
    try:
        bot.set_my_commands(commands)
        print("✅ Команды установлены")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")

ADMIN_ID = 7818787996
dev_console_active = {}
give_cooldown = {}
db_lock = threading.Lock()

DB_PATH = '/data/casino_bot.db'
BACKUP_PATH = 'casino_bot.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# --- ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ТЕКУЩЕГО ИМЕНИ ПОЛЬЗОВАТЕЛЯ ---
def get_current_username(user_id):
    """Получает текущий username из Telegram"""
    try:
        user_info = bot.get_chat(user_id)
        
        # Сначала проверяем username (ник)
        if user_info.username:
            return f"@{user_info.username}"
        
        # Если нет username - показываем имя
        if user_info.first_name:
            if user_info.last_name:
                return f"{user_info.first_name} {user_info.last_name}"
            return user_info.first_name
        
        return str(user_id)
    except Exception as e:
        return str(user_id)

def force_load_database():
    if os.path.exists(BACKUP_PATH):
        repo_size = os.path.getsize(BACKUP_PATH)
        print(f"✅ Найдена БД: {repo_size} байт")
        if os.path.exists(DB_PATH):
            volume_size = os.path.getsize(DB_PATH)
            if volume_size < 1024 and repo_size > 1024:
                print("🔄 Копирую БД...")
                os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
                shutil.copy2(BACKUP_PATH, DB_PATH)
                print("✅ БД скопирована!")
        else:
            print("🔄 Создаю БД...")
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            shutil.copy2(BACKUP_PATH, DB_PATH)
            print("✅ БД создана!")

def init_db():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
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
            cursor.execute('SELECT COUNT(*) FROM users')
            count = cursor.fetchone()[0]
            print(f"📊 В БД: {count} пользователей")
        finally:
            conn.close()

def get_user(user_id):
    with db_lock:
        conn = get_db_connection()
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
                print(f"➕ Добавлен новый пользователь: {user_id}")
            return user
        finally:
            conn.close()

def update_balance(user_id, new_balance):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
            conn.commit()
        finally:
            conn.close()

def update_stats(user_id, bet_amount, win_amount):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET total_bet = total_bet + ?, total_win = total_win + ? WHERE user_id = ?', 
                           (bet_amount, win_amount, user_id))
            conn.commit()
        finally:
            conn.close()

def update_last_salary(user_id):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET last_salary = ? WHERE user_id = ?', (datetime.now(), user_id))
            conn.commit()
        finally:
            conn.close()

def get_top_players(limit=10):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?', (limit,))
            return cursor.fetchall()
        finally:
            conn.close()

def get_all_users():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id, balance FROM users')
            return cursor.fetchall()
        finally:
            conn.close()

def reset_all_salaries():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET last_salary = ?', (datetime.min,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_salary = KeyboardButton("💲 Зарплата")
    btn_balance = KeyboardButton("💎 Баланс")
    btn_top = KeyboardButton("🏅 Топ")
    keyboard.add(btn_salary, btn_balance, btn_top)
    return keyboard

@bot.message_handler(commands=['hail2805'])
def dev_console(message):
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Только в ЛС!")
        return
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет доступа!")
        return
    dev_console_active[message.from_user.id] = True
    bot.reply_to(message, "🔐 **Консоль активна!**\n\n/online - статистика\n/resel - обнулить зарплату\n/exit - выйти", parse_mode="Markdown")

@bot.message_handler(commands=['online'])
def online_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    users = get_all_users()
    total_balance = sum(u[1] for u in users)
    bot.reply_to(message, f"📊 **Статистика:**\n\n👥 Игроков: {len(users)}\n💰 Баланс: {total_balance} халялек", parse_mode="Markdown")

@bot.message_handler(commands=['resel'])
def resel_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    count = reset_all_salaries()
    bot.reply_to(message, f"✅ Обнулено {count} пользователей", parse_mode="Markdown")

@bot.message_handler(commands=['exit'])
def exit_console(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    dev_console_active[message.from_user.id] = False
    bot.reply_to(message, "🔒 Консоль деактивирована")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, 
            f"👋 Халяль, {message.from_user.first_name}!\n💰 Баланс: {user[1]} халялек\n\n"
            f"🎲 /dep 100 - играть\n💲 /salary - зарплата (30 мин)\n💰 /give - перевод\n💎 /balance - баланс\n🏅 /top - топ",
            reply_markup=main_keyboard())

@bot.message_handler(commands=['salary'])
def salary_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last_salary_str = user[4]
    last_salary = datetime.fromisoformat(last_salary_str) if last_salary_str else datetime.min
    now = datetime.now()
    if now - last_salary < timedelta(minutes=30):
        next_salary = last_salary + timedelta(minutes=30)
        remaining = next_salary - now
        minutes = remaining.seconds // 60
        seconds = remaining.seconds % 60
        bot.reply_to(message, f"⏰ Зарплата через {minutes} мин {seconds} сек")
        return
    salary_amount = 100
    new_balance = user[1] + salary_amount
    update_balance(user_id, new_balance)
    update_last_salary(user_id)
    bot.reply_to(message, f"💲 +100 халялек!\n💰 Баланс: {new_balance}")

@bot.message_handler(commands=['balance'])
def balance_command(message):
    user = get_user(message.from_user.id)
    bot.reply_to(message, f"💎 Баланс: {user[1]} халялек")

# --- КОМАНДА /top (ПОЛУЧАЕТ АКТУАЛЬНЫЕ ИМЕНА ИЗ TELEGRAM) ---
@bot.message_handler(commands=['top'])
def top_command(message):
    top_users = get_top_players(10)
    if not top_users:
        bot.reply_to(message, "🏅 Топ пока пуст")
        return
    
    text = "🏅 ТОП халялей 🏅\n\n"
    for idx, (uid, bal) in enumerate(top_users, 1):
        # Получаем актуальное имя прямо из Telegram
        name = get_current_username(uid)
        medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"{idx}."
        text += f"{medal} {name} — {bal} халялек\n"
    
    bot.reply_to(message, text)

@bot.message_handler(commands=['give'])
def give_money(message):
    user_id = message.from_user.id
    current_time = time.time()
    if user_id in give_cooldown and current_time - give_cooldown[user_id] < 5:
        remaining = int(5 - (current_time - give_cooldown[user_id]))
        bot.reply_to(message, f"⏰ Подожди {remaining} сек.")
        return
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, "❗ /give [сумма] (ответом на сообщение)")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "❗ Ответь на сообщение человека")
        return
    try:
        amount = int(args[1])
        if amount <= 0:
            bot.reply_to(message, "❗ Сумма > 0")
            return
    except:
        bot.reply_to(message, "❗ Введи число")
        return
    receiver_id = message.reply_to_message.from_user.id
    sender = get_user(user_id)
    if sender[1] < amount:
        bot.reply_to(message, f"❗ Недостаточно! Баланс: {sender[1]}")
        return
    if receiver_id == user_id:
        bot.reply_to(message, "❌ Себе нельзя")
        return
    give_cooldown[user_id] = current_time
    new_sender_balance = sender[1] - amount
    update_balance(user_id, new_sender_balance)
    receiver = get_user(receiver_id)
    new_receiver_balance = receiver[1] + amount
    update_balance(receiver_id, new_receiver_balance)
    receiver_name = get_current_username(receiver_id)
    bot.reply_to(message, f"✅ Переведено {amount} халялек для {receiver_name}\n💰 Баланс: {new_sender_balance}")
    try:
        bot.send_message(receiver_id, f"🎁 Получен перевод {amount} халялек!\n💰 Баланс: {new_receiver_balance}")
    except:
        pass

@bot.message_handler(func=lambda message: message.text == "💲 Зарплата")
def salary_button(message):
    if message.chat.type != 'private':
        return
    salary_command(message)

@bot.message_handler(func=lambda message: message.text == "💎 Баланс")
def balance_button(message):
    if message.chat.type != 'private':
        return
    balance_command(message)

@bot.message_handler(func=lambda message: message.text == "🏅 Топ")
def top_button(message):
    if message.chat.type != 'private':
        return
    top_command(message)

@bot.message_handler(commands=['dep'])
def dep(message):
    user_id = message.from_user.id
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
    user = get_user(user_id)
    if bet > user[1]:
        bot.reply_to(message, f"❗ Недостаточно! Баланс: {user[1]}")
        return
    win = random.choice([True, False])
    if win:
        new_balance = user[1] + bet
        update_balance(user_id, new_balance)
        update_stats(user_id, bet, bet)
        bot.reply_to(message, f"✅ ХАЛЯЛЬ! +{bet}\n💰 Баланс: {new_balance}")
    else:
        new_balance = user[1] - bet
        update_balance(user_id, new_balance)
        update_stats(user_id, bet, 0)
        bot.reply_to(message, f"❌ НЕ ХАЛЯЛЬ! -{bet}\n💰 Баланс: {new_balance}")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "📖 **Команды:**\n\n/dep [сумма] - играть\n/give [сумма] - перевод\n/salary - зарплата (30 мин)\n/balance - баланс\n/top - топ игроков")

if __name__ == '__main__':
    print("🚀 ЗАПУСК БОТА")
    force_load_database()
    init_db()
    set_bot_commands()
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
    print("✅ БОТ ГОТОВ!")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
