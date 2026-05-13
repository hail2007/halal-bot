from flask import Flask, request
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import random
import sqlite3
from datetime import datetime, timedelta
import time
import os
import threading

# Замени на токен своего бота
TOKEN = "8970700402:AAEheb9WtnO20ZsdN_MEbNEdBgDCwoZrT3I"
bot = telebot.TeleBot(TOKEN)

# Создаём Flask приложение
app = Flask(__name__)

# Словарь для хранения времени последнего использования /give
give_cooldown = {}
# Блокировка для синхронизации БД
db_lock = threading.Lock()

# --- КОНСОЛЬ РАЗРАБОТЧИКА ---
# Замени на свой Telegram ID (узнать можно у бота @userinfobot)
ADMIN_ID = 7818787996  # ВСТАВЬ СВОЙ ID СЮДА!

# Словарь для отслеживания активной консоли разработчика
dev_console_active = {}

# --- Настройка пути к БД ---
if os.path.exists('/data'):
    DB_PATH = '/data/casino_bot.db'
else:
    DB_PATH = 'casino_bot.db'

# --- Функция для получения соединения с БД ---
def get_db_connection():
    """Создаёт новое соединение с БД"""
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
    """Получает всех пользователей бота"""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id FROM users')
            return cursor.fetchall()
        finally:
            conn.close()

def reset_all_salaries():
    """Обнуляет таймер зарплаты для всех пользователей"""
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
            print("✅ Таблица users проверена/создана")
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
    # Проверяем, что команда в личных сообщениях
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Эта команда работает только в личных сообщениях!")
        return
    
    # Проверяем, что пользователь - админ
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У тебя нет доступа к консоли разработчика!")
        return
    
    dev_console_active[message.from_user.id] = True
    bot.reply_to(message, 
        "🔐 **Консоль разработчика активирована!**\n\n"
        "📋 **Доступные команды:**\n"
        "• `/online` - показать количество активных игроков\n"
        "• `/resel` - обнулить таймер зарплаты для всех игроков\n"
        "• `/exit` - выйти из консоли разработчика\n\n"
        "💡 Все команды работают только в этом чате!",
        parse_mode="Markdown")

@bot.message_handler(commands=['online'])
def online_command(message):
    # Проверяем, что консоль активна и пользователь админ
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    users = get_all_users()
    online_count = len(users)
    
    # Считаем активных за последние 24 часа (кто делал ставки или переводы)
    active_count = 0
    for (user_id,) in users:
        user = get_user(user_id)
        if user[2] > 0 or user[3] > 0:  # total_bet или total_win больше 0
            active_count += 1
    
    bot.reply_to(message,
        f"📊 **Статистика бота:**\n\n"
        f"👥 Всего игроков: **{online_count}**\n"
        f"🎮 Активных игроков: **{active_count}**\n"
        f"💰 Общий оборот: **{sum(u[1] for u in users)}** халялек",
        parse_mode="Markdown")

@bot.message_handler(commands=['resel'])
def resel_command(message):
    # Проверяем, что консоль активна и пользователь админ
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    count = reset_all_salaries()
    bot.reply_to(message,
        f"✅ **Таймер зарплаты обнулён!**\n\n"
        f"📊 Обновлено пользователей: **{count}**\n"
        f"💡 Теперь все игроки могут получить зарплату!",
        parse_mode="Markdown")

@bot.message_handler(commands=['exit'])
def exit_console(message):
    # Проверяем, что консоль активна и пользователь админ
    if not dev_console_active.get(message.from_user.id, False) or message.from_user.id != ADMIN_ID:
        return
    
    dev_console_active[message.from_user.id] = False
    bot.reply_to(message,
        "🔒 **Консоль разработчика деактивирована!**\n\n"
        "Для повторного входа используй `/hail2805`",
        parse_mode="Markdown")

# --- Команда /start ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    get_user(user_id)
    
    if message.chat.type == 'private':
        bot.send_message(message.chat.id,
            f"👋 Халяль, {message.from_user.first_name}!\n"
            f"Твой баланс: 0 халялек.\n\n"
            f"🎲 Играть: `/dep [сумма]`\n"
            f"💰 Передать халяльки: ответь на сообщение и напиши `/give [сумма]`\n"
            f"⏰ Зарплата каждые **30 минут**!\n"
            f"📱 Или используй кнопки внизу:",
            reply_markup=main_keyboard(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id,
            f"👋 Халяль, {message.from_user.first_name}!\n"
            f"Твой баланс: 0 халялек.\n\n"
            f"🎲 Играть: `/dep [сумма]`\n"
            f"💰 Передать халяльки: ответь на сообщение и напиши `/give [сумма]`\n"
            f"⏰ Зарплата каждые **30 минут**!",
            parse_mode="Markdown")

# --- Команда /salary (с секундами и 30 минутами) ---
@bot.message_handler(commands=['salary'])
def salary_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last_salary_str = user[4]
    
    last_salary = datetime.fromisoformat(last_salary_str) if last_salary_str else datetime.min
    now = datetime.now()
    
    # КД 30 МИНУТ вместо часа
    if now - last_salary < timedelta(minutes=30):
        next_salary = last_salary + timedelta(minutes=30)
        remaining = next_salary - now
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        seconds = remaining.seconds % 60
        
        time_str = ""
        if hours > 0:
            time_str += f"{hours} ч "
        if minutes > 0 or hours > 0:
            time_str += f"{minutes} мин "
        time_str += f"{seconds} сек"
        
        bot.reply_to(message, f"⏰ Зарплата через: **{time_str}**",
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
    bot.reply_to(message, f"💎 Твой баланс: {user[1]} халялек",
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
        bot.reply_to(message, "❗ Формат: `/dep [сумма]`", parse_mode="Markdown")
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
        "📖 **Команды:**\n\n"
        "🎲 `/dep [сумма]` - сыграть 50/50\n"
        "💰 `/give [сумма]` - перевести (ответом)\n"
        "💲 `/salary` - зарплата (каждые 30 минут)\n"
        "💎 `/balance` - баланс\n"
        "🏅 `/top` - топ игроков\n\n"
        "⏰ Зарплата выдается **каждые 30 минут** по 100 халялек!\n"
        "📱 Кнопки внизу для быстрого доступа!",
        parse_mode="Markdown")

# --- Webhook endpoint ---
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# --- Запуск ---
if __name__ == '__main__':
    print("✅ Бот запущен с Webhook!")
    print(f"📁 База данных: {DB_PATH}")
    print("📱 Кнопки: Зарплата | Баланс | Топ")
    print("🔧 Консоль разработчика: /hail2805 (только для админа)")
    
    # Инициализируем БД
    init_db()
    
    # Копируем локальную БД если есть
    if not os.path.exists(DB_PATH) and os.path.exists('casino_bot.db'):
        import shutil
        shutil.copy2('casino_bot.db', DB_PATH)
        print(f"✅ База данных скопирована в {DB_PATH}")
    
    # Удаляем вебхук
    bot.remove_webhook()
    
    # Получаем PORT от Railway
    port = int(os.environ.get('PORT', 8080))
    
    # Получаем URL для webhook
    railway_url = os.environ.get('RAILWAY_STATIC_URL')
    if railway_url:
        webhook_url = f"https://{railway_url}/webhook"
    else:
        webhook_url = f"https://{os.environ.get('PUBLIC_URL', 'localhost')}/webhook"
    
    # Устанавливаем вебхук
    try:
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook установлен: {webhook_url}")
    except Exception as e:
        print(f"⚠️ Ошибка установки webhook: {e}")
    
    # Запускаем Flask сервер
    print(f"🚀 Запуск Flask сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)
