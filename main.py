import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand
import random
import sqlite3
from datetime import datetime, timedelta
import time
import os
import threading
import shutil

# Замени на токен своего бота
TOKEN = "8970700402:AAEheb9WtnO20ZsdN_MEbNEdBgDCwoZrT3I"
bot = telebot.TeleBot(TOKEN)

# --- НАСТРОЙКА ПОДСКАЗОК КОМАНД ---
def set_bot_commands():
    commands = [
        BotCommand("start", "🚀 Запустить бота"),
        BotCommand("dep", "🎲 Сыграть 50/50 (пример: /dep 100)"),
        BotCommand("give", "💰 Передать халяльки (ответом на сообщение)"),
        BotCommand("salary", "💲 Получить зарплату (раз в 30 минут)"),
        BotCommand("balance", "💎 Проверить баланс"),
        BotCommand("top", "🏅 Топ игроков"),
        BotCommand("help", "📖 Помощь"),
    ]
    try:
        bot.set_my_commands(commands)
        print("✅ Команды бота установлены")
    except Exception as e:
        print(f"⚠️ Ошибка установки команд: {e}")

# --- КОНСОЛЬ РАЗРАБОТЧИКА ---
ADMIN_ID = 7818787996

dev_console_active = {}
give_cooldown = {}
db_lock = threading.Lock()

# --- НАСТРОЙКА ПУТИ К БД ---
DB_PATH = '/data/casino_bot.db'
BACKUP_PATH = 'casino_bot.db'

# --- ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ИМЕНИ ПОЛЬЗОВАТЕЛЯ ---
def get_user_full_name(user_id):
    """Возвращает полное имя пользователя (имя + фамилия)"""
    try:
        user_info = bot.get_chat(user_id)
        
        if user_info.first_name:
            if user_info.last_name:
                return f"{user_info.first_name} {user_info.last_name}"
            return user_info.first_name
        return str(user_id)
    except:
        return str(user_id)

# --- ФУНКЦИЯ ДЛЯ ЗАГРУЗКИ БД ---
def force_load_database():
    if os.path.exists(BACKUP_PATH):
        repo_size = os.path.getsize(BACKUP_PATH)
        print(f"✅ Найдена БД в репозитории: {repo_size} байт")
        
        if os.path.exists(DB_PATH):
            volume_size = os.path.getsize(DB_PATH)
            if volume_size < 1024 and repo_size > 1024:
                print("🔄 Копирую БД из репозитория...")
                os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
                shutil.copy2(BACKUP_PATH, DB_PATH)
                print(f"✅ БД скопирована!")
        else:
            print("🔄 Создаю БД в Volume...")
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            shutil.copy2(BACKUP_PATH, DB_PATH)
            print(f"✅ БД создана!")

# --- Функции БД ---
def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

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

# --- Клавиатура ---
def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_salary = KeyboardButton("💲 Зарплата")
    btn_balance = KeyboardButton("💎 Баланс")
    btn_top = KeyboardButton("🏅 Топ")
    keyboard.add(btn_salary, btn_balance, btn_top)
    return keyboard

# --- КОНСОЛЬ РАЗРАБОТЧИКА ---
@bot.message_handler(commands=['hail2805'])
def dev_console(message):
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Только в личных сообщениях!")
        return
    
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет доступа!")
        return
    
    dev_console_active[message.from_user.id] = True
    bot.reply_to(message, 
        "🔐 **Консоль разработчика активна!**\n\n"
        "📋 **Команды:**\n"
        "• `/online` - статистика игроков\n"
        "• `/resel` - обнулить зарплату всем\n"
        "• `/dbstats` - статистика БД\n"
        "• `/exit` - выйти",
        parse_mode="Markdown")

@bot.message_handler(commands=['online'])
def online_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    users = get_all_users()
    online_count = len(users)
    
    active_count = 0
    total_balance = 0
    for (user_id, balance) in users:
        if balance > 0:
            active_count += 1
        total_balance += balance
    
    bot.reply_to(message,
        f"📊 **Статистика бота:**\n\n"
        f"👥 Всего игроков: **{online_count}**\n"
        f"🎮 Активных: **{active_count}**\n"
        f"💰 Общий баланс: **{total_balance}** халялек\n"
        f"📁 БД: `{DB_PATH}`",
        parse_mode="Markdown")

@bot.message_handler(commands=['resel'])
def resel_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    count = reset_all_salaries()
    bot.reply_to(message,
        f"✅ **Таймер зарплаты обнулён!**\n"
        f"📊 Обновлено: **{count}** пользователей",
        parse_mode="Markdown")

@bot.message_handler(commands=['dbstats'])
def dbstats_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    try:
        size = os.path.getsize(DB_PATH)
        size_kb = size / 1024
        users = get_all_users()
        
        bot.reply_to(message,
            f"📊 **Статистика БД:**\n\n"
            f"📁 Путь: `{DB_PATH}`\n"
            f"📦 Размер: **{size_kb:.2f} KB**\n"
            f"👥 Пользователей: **{len(users)}**\n"
            f"💰 Общий баланс: **{sum(u[1] for u in users)}**",
            parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['exit'])
def exit_console(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    dev_console_active[message.from_user.id] = False
    bot.reply_to(message, "🔒 Консоль деактивирована! Для входа: `/hail2805`", parse_mode="Markdown")

# --- Команда /start ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if message.chat.type == 'private':
        bot.send_message(message.chat.id,
            f"👋 Халяль, {message.from_user.first_name}!\n"
            f"Твой баланс: **{user[1]}** халялек.\n\n"
            f"🎲 **Играть:** `/dep 100`\n"
            f"💰 **Перевести:** ответь на сообщение и напиши `/give 50`\n"
            f"💲 **Зарплата:** `/salary` (каждые 30 мин)\n"
            f"💎 **Баланс:** `/balance`\n"
            f"🏅 **Топ:** `/top`\n\n"
            f"📱 **Кнопки** внизу экрана!",
            reply_markup=main_keyboard(), parse_mode="Markdown")

# --- Команда /salary ---
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
        bot.reply_to(message, f"⏰ Зарплата через: **{minutes} мин {seconds} сек**",
                     reply_markup=main_keyboard() if message.chat.type == 'private' else None,
                     parse_mode="Markdown")
        return
    
    salary_amount = 100
    new_balance = user[1] + salary_amount
    update_balance(user_id, new_balance)
    update_last_salary(user_id)
    bot.reply_to(message, f"💲 +{salary_amount} халялек!\n💎 Баланс: {new_balance}",
                 reply_markup=main_keyboard() if message.chat.type == 'private' else None)

# --- Команда /balance ---
@bot.message_handler(commands=['balance'])
def balance_command(message):
    user = get_user(message.from_user.id)
    bot.reply_to(message, f"💎 Баланс: {user[1]} халялек",
                 reply_markup=main_keyboard() if message.chat.type == 'private' else None)

# --- Команда /top (показывает имя и фамилию) ---
@bot.message_handler(commands=['top'])
def top_command(message):
    top_users = get_top_players(10)
    if not top_users:
        bot.reply_to(message, "🏅 Топ пока пуст")
        return
    
    text = "🏅 ТОП халялей 🏅\n\n"
    for idx, (uid, bal) in enumerate(top_users, 1):
        name = get_user_full_name(uid)
        medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"{idx}."
        text += f"{medal} {name} — {bal} халялек\n"
    
    bot.reply_to(message, text, reply_markup=main_keyboard() if message.chat.type == 'private' else None)

# --- Команда /give ---
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
        bot.reply_to(message, "❗ Формат: `/give [сумма]` (ответом на сообщение)", parse_mode="Markdown")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❗ Ответь на сообщение человека")
        return
    
    try:
        amount = int(args[1])
        if amount <= 0:
            bot.reply_to(message, "❗ Сумма > 0")
            return
    except ValueError:
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
    
    # Получаем красивое имя получателя и отправителя
    receiver_name = get_user_full_name(receiver_id)
    sender_name = get_user_full_name(user_id)
    
    bot.reply_to(message, f"✅ Переведено {amount} халялек для {receiver_name}\n💎 Твой баланс: {new_sender_balance}")
    
    try:
        bot.send_message(receiver_id, f"🎁 Получен перевод {amount} халялек от {sender_name}\n💎 Баланс: {new_receiver_balance}")
    except:
        pass

# --- Кнопки ---
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

# --- Команда /dep ---
@bot.message_handler(commands=['dep'])
def dep(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    if len(args) != 2:
        bot.reply_to(message, "❗ Формат: `/dep [сумма]`\nПример: `/dep 100`", parse_mode="Markdown")
        return
    
    try:
        bet = int(args[1])
        if bet <= 0:
            bot.reply_to(message, "❗ Сумма > 0")
            return
    except ValueError:
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
        bot.reply_to(message, f"✅ ХАЛЯЛЬ! +{bet}\n💲 Баланс: {new_balance}")
    else:
        new_balance = user[1] - bet
        update_balance(user_id, new_balance)
        update_stats(user_id, bet, 0)
        bot.reply_to(message, f"❌ НЕ ХАЛЯЛЬ! -{bet}\n💲 Баланс: {new_balance}")

# --- Команда /help ---
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message,
        "📖 **Команды бота:**\n\n"
        "🎲 `/dep [сумма]` - сыграть 50/50\n"
        "💰 `/give [сумма]` - перевести халяльки (ответом на сообщение)\n"
        "💲 `/salary` - получить зарплату 100 халялек (каждые 30 мин)\n"
        "💎 `/balance` - проверить свой баланс\n"
        "🏅 `/top` - топ игроков по халялькам\n\n"
        "📱 **Кнопки** внизу экрана для быстрого доступа!",
        parse_mode="Markdown")

# --- Запуск бота ---
if __name__ == '__main__':
    print("🚀 ЗАПУСК БОТА")
    
    # Загружаем БД
    force_load_database()
    
    # Инициализируем БД
    init_db()
    
    # Устанавливаем команды
    set_bot_commands()
    
    # Удаляем вебхук
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
    
    print("✅ БОТ ГОТОВ К РАБОТЕ!")
    print(f"📁 База данных: {DB_PATH}")
    
    # Запускаем polling
    bot.infinity_polling(timeout=60, long_polling_timeout=60)import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand
import random
import sqlite3
from datetime import datetime, timedelta
import time
import os
import threading
import shutil

# Замени на токен своего бота
TOKEN = "8970700402:AAEheb9WtnO20ZsdN_MEbNEdBgDCwoZrT3I"
bot = telebot.TeleBot(TOKEN)

# --- НАСТРОЙКА ПОДСКАЗОК КОМАНД ---
def set_bot_commands():
    commands = [
        BotCommand("start", "🚀 Запустить бота"),
        BotCommand("dep", "🎲 Сыграть 50/50 (пример: /dep 100)"),
        BotCommand("give", "💰 Передать халяльки (ответом на сообщение)"),
        BotCommand("salary", "💲 Получить зарплату (раз в 30 минут)"),
        BotCommand("balance", "💎 Проверить баланс"),
        BotCommand("top", "🏅 Топ игроков"),
        BotCommand("help", "📖 Помощь"),
    ]
    try:
        bot.set_my_commands(commands)
        print("✅ Команды бота установлены")
    except Exception as e:
        print(f"⚠️ Ошибка установки команд: {e}")

# --- КОНСОЛЬ РАЗРАБОТЧИКА ---
ADMIN_ID = 7818787996

dev_console_active = {}
give_cooldown = {}
db_lock = threading.Lock()

# --- НАСТРОЙКА ПУТИ К БД ---
DB_PATH = '/data/casino_bot.db'  # Всегда используем Volume
BACKUP_PATH = 'casino_bot.db'     # БД в репозитории

# --- ФУНКЦИЯ ДЛЯ ПРИНУДИТЕЛЬНОЙ ЗАГРУЗКИ БД ---
def force_load_database():
    """Принудительно копирует БД из репозитория в Volume"""
    
    print("\n" + "=" * 50)
    print("📁 ПРОВЕРКА БАЗЫ ДАННЫХ")
    print("=" * 50)
    
    # 1. Проверяем, есть ли БД в репозитории
    if os.path.exists(BACKUP_PATH):
        repo_size = os.path.getsize(BACKUP_PATH)
        print(f"✅ Найдена БД в репозитории: {repo_size} байт")
        
        # Показываем содержимое БД из репозитория
        try:
            conn = sqlite3.connect(BACKUP_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            count = cursor.fetchone()[0]
            print(f"📊 В БД репозитория: {count} пользователей")
            
            if count > 0:
                cursor.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5')
                top = cursor.fetchall()
                print("🏆 Топ из репозитория:")
                for uid, bal in top:
                    print(f"   - {uid}: {bal} халялек")
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка чтения БД репозитория: {e}")
    else:
        print(f"❌ БД в репозитории не найдена! Искал: {BACKUP_PATH}")
        print("   Создам новую пустую БД")
        return False
    
    # 2. Проверяем, есть ли БД в Volume
    if os.path.exists(DB_PATH):
        volume_size = os.path.getsize(DB_PATH)
        print(f"📁 БД в Volume: {volume_size} байт")
        
        # Проверяем, сколько пользователей в Volume
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            volume_count = cursor.fetchone()[0]
            print(f"📊 В БД Volume: {volume_count} пользователей")
            conn.close()
        except Exception as e:
            print(f"⚠️ Ошибка чтения Volume: {e}")
            volume_count = 0
    else:
        print(f"📁 БД в Volume не существует")
        volume_count = 0
    
    # 3. Решаем, нужно ли копировать
    if volume_count == 0:
        print("\n🔄 Обнаружена пустая БД в Volume! Копирую из репозитория...")
        
        # Создаём папку /data если её нет
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # Копируем файл
        shutil.copy2(BACKUP_PATH, DB_PATH)
        print(f"✅ БД скопирована!")
        
        # Проверяем результат
        if os.path.exists(DB_PATH):
            new_size = os.path.getsize(DB_PATH)
            print(f"📁 Новая БД в Volume: {new_size} байт")
            
            # Показываем содержимое скопированной БД
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM users')
                new_count = cursor.fetchone()[0]
                print(f"📊 В скопированной БД: {new_count} пользователей")
                
                if new_count > 0:
                    cursor.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5')
                    top = cursor.fetchall()
                    print("🏆 Топ из новой БД:")
                    for uid, bal in top:
                        print(f"   - {uid}: {bal} халялек")
                conn.close()
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
        else:
            print("❌ Ошибка копирования!")
        return True
    else:
        print("\n✅ БД в Volume уже содержит данные, копирование не требуется")
        return True

# --- Функция для получения соединения с БД ---
def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# --- Функции БД ---
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

def show_db_stats():
    """Показывает статистику БД"""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM users')
            count = cursor.fetchone()[0]
            print(f"\n📊 СТАТИСТИКА БД:")
            print(f"   Пользователей: {count}")
            
            if count > 0:
                cursor.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5')
                top = cursor.fetchall()
                print(f"   Топ 5 по балансу:")
                for uid, bal in top:
                    print(f"      - {uid}: {bal}")
        finally:
            conn.close()

# --- Клавиатура ---
def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_salary = KeyboardButton("💲 Зарплата")
    btn_balance = KeyboardButton("💎 Баланс")
    btn_top = KeyboardButton("🏅 Топ")
    keyboard.add(btn_salary, btn_balance, btn_top)
    return keyboard

# --- КОНСОЛЬ РАЗРАБОТЧИКА ---
@bot.message_handler(commands=['hail2805'])
def dev_console(message):
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Только в личных сообщениях!")
        return
    
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет доступа!")
        return
    
    dev_console_active[message.from_user.id] = True
    bot.reply_to(message, 
        "🔐 **Консоль разработчика активна!**\n\n"
        "📋 **Команды:**\n"
        "• `/online` - статистика игроков\n"
        "• `/resel` - обнулить зарплату всем\n"
        "• `/dbstats` - статистика БД\n"
        "• `/exit` - выйти",
        parse_mode="Markdown")

@bot.message_handler(commands=['online'])
def online_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    users = get_all_users()
    online_count = len(users)
    
    active_count = 0
    total_balance = 0
    for (user_id, balance) in users:
        if balance > 0:
            active_count += 1
        total_balance += balance
    
    bot.reply_to(message,
        f"📊 **Статистика бота:**\n\n"
        f"👥 Всего игроков: **{online_count}**\n"
        f"🎮 Активных: **{active_count}**\n"
        f"💰 Общий баланс: **{total_balance}** халялек\n"
        f"📁 БД: `{DB_PATH}`",
        parse_mode="Markdown")

@bot.message_handler(commands=['resel'])
def resel_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    count = reset_all_salaries()
    bot.reply_to(message,
        f"✅ **Таймер зарплаты обнулён!**\n"
        f"📊 Обновлено: **{count}** пользователей",
        parse_mode="Markdown")

@bot.message_handler(commands=['dbstats'])
def dbstats_command(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    try:
        size = os.path.getsize(DB_PATH)
        size_kb = size / 1024
        users = get_all_users()
        
        bot.reply_to(message,
            f"📊 **Статистика БД:**\n\n"
            f"📁 Путь: `{DB_PATH}`\n"
            f"📦 Размер: **{size_kb:.2f} KB**\n"
            f"👥 Пользователей: **{len(users)}**\n"
            f"💰 Общий баланс: **{sum(u[1] for u in users)}**",
            parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['exit'])
def exit_console(message):
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    dev_console_active[message.from_user.id] = False
    bot.reply_to(message, "🔒 Консоль деактивирована! Для входа: `/hail2805`", parse_mode="Markdown")

# --- Команда /start ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if message.chat.type == 'private':
        bot.send_message(message.chat.id,
            f"👋 Халяль, {message.from_user.first_name}!\n"
            f"Твой баланс: **{user[1]}** халялек.\n\n"
            f"🎲 **Играть:** `/dep 100`\n"
            f"💰 **Перевести:** ответь на сообщение и напиши `/give 50`\n"
            f"💲 **Зарплата:** `/salary` (каждые 30 мин)\n"
            f"💎 **Баланс:** `/balance`\n"
            f"🏅 **Топ:** `/top`\n\n"
            f"📱 **Кнопки** внизу экрана!\n"
            f"💡 **Совет:** Нажми `/` для подсказки команд!",
            reply_markup=main_keyboard(), parse_mode="Markdown")

# --- Команда /salary ---
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
        bot.reply_to(message, f"⏰ Зарплата через: **{minutes} мин {seconds} сек**",
                     reply_markup=main_keyboard() if message.chat.type == 'private' else None,
                     parse_mode="Markdown")
        return
    
    salary_amount = 100
    new_balance = user[1] + salary_amount
    update_balance(user_id, new_balance)
    update_last_salary(user_id)
    bot.reply_to(message, f"💲 +{salary_amount} халялек!\n💎 Баланс: {new_balance}",
                 reply_markup=main_keyboard() if message.chat.type == 'private' else None)

# --- Команда /balance ---
@bot.message_handler(commands=['balance'])
def balance_command(message):
    user = get_user(message.from_user.id)
    bot.reply_to(message, f"💎 Баланс: {user[1]} халялек",
                 reply_markup=main_keyboard() if message.chat.type == 'private' else None)

# --- Команда /top ---
@bot.message_handler(commands=['top'])
def top_command(message):
    top_users = get_top_players(10)
    if not top_users:
        bot.reply_to(message, "🏅 Топ пока пуст")
        return
    
    text = "🏅 ТОП халялей 🏅\n\n"
    for idx, (uid, bal) in enumerate(top_users, 1):
        try:
            user_info = bot.get_chat(uid)
            name = user_info.first_name or str(uid)
        except:
            name = str(uid)
        medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"{idx}."
        text += f"{medal} {name} — {bal} халялек\n"
    
    bot.reply_to(message, text, reply_markup=main_keyboard() if message.chat.type == 'private' else None)

# --- Команда /give ---
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
        bot.reply_to(message, "❗ Формат: `/give [сумма]` (ответом на сообщение)", parse_mode="Markdown")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❗ Ответь на сообщение человека")
        return
    
    try:
        amount = int(args[1])
        if amount <= 0:
            bot.reply_to(message, "❗ Сумма > 0")
            return
    except ValueError:
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
    
    receiver_name = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else message.reply_to_message.from_user.first_name
    
    bot.reply_to(message, f"✅ Переведено {amount} халялек для {receiver_name}\n💎 Твой баланс: {new_sender_balance}")
    
    try:
        bot.send_message(receiver_id, f"🎁 Получен перевод {amount} халялек от {message.from_user.first_name}\n💎 Баланс: {new_receiver_balance}")
    except:
        pass

# --- Кнопки ---
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

# --- Команда /dep ---
@bot.message_handler(commands=['dep'])
def dep(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    if len(args) != 2:
        bot.reply_to(message, "❗ Формат: `/dep [сумма]`\nПример: `/dep 100`", parse_mode="Markdown")
        return
    
    try:
        bet = int(args[1])
        if bet <= 0:
            bot.reply_to(message, "❗ Сумма > 0")
            return
    except ValueError:
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
        bot.reply_to(message, f"✅ ХАЛЯЛЬ! +{bet}\n💲 Баланс: {new_balance}")
    else:
        new_balance = user[1] - bet
        update_balance(user_id, new_balance)
        update_stats(user_id, bet, 0)
        bot.reply_to(message, f"❌ НЕ ХАЛЯЛЬ! -{bet}\n💲 Баланс: {new_balance}")

# --- Команда /help ---
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message,
        "📖 **Команды бота:**\n\n"
        "🎲 `/dep [сумма]` - сыграть 50/50 (удвоить или потерять)\n"
        "💰 `/give [сумма]` - перевести халяльки (ответом на сообщение)\n"
        "💲 `/salary` - получить зарплату 100 халялек (каждые 30 мин)\n"
        "💎 `/balance` - проверить свой баланс\n"
        "🏅 `/top` - топ игроков по халялькам\n\n"
        "💡 **Совет:** Нажми `/` в поле ввода, чтобы увидеть все команды!\n"
        "📱 **Кнопки** внизу экрана для быстрого доступа!",
        parse_mode="Markdown")

# --- Запуск бота ---
if __name__ == '__main__':
    print("=" * 60)
    print("🚀 ЗАПУСК БОТА")
    print("=" * 60)
    
    # 1. Принудительно загружаем БД из репозитория
    print("\n📁 ШАГ 1: Загрузка базы данных...")
    force_load_database()
    
    # 2. Показываем статистику БД
    print("\n📊 ШАГ 2: Статистика базы данных...")
    show_db_stats()
    
    # 3. Устанавливаем команды
    print("\n🔧 ШАГ 3: Настройка команд...")
    set_bot_commands()
    
    # 4. Удаляем вебхук
    print("\n🌐 ШАГ 4: Настройка webhook...")
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
    
    print("\n" + "=" * 60)
    print("✅ БОТ ГОТОВ К РАБОТЕ!")
    print(f"📁 База данных: {DB_PATH}")
    if os.path.exists(DB_PATH):
        print(f"📁 Размер БД: {os.path.getsize(DB_PATH)} байт")
    else:
        print("❌ БД не найдена!")
    print("🔧 Консоль разработчика: /hail2805")
    print("=" * 60)
    
    # Запускаем polling
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
