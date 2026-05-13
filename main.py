import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import random
import sqlite3
from datetime import datetime, timedelta
import time
import os

# Замени на токен своего бота
TOKEN = "8970700402:AAHnQF-JYKGX8KsFIQ7SP66tj0zYHHT-VGo"
bot = telebot.TeleBot(TOKEN)

# Словарь для хранения времени последнего использования /give
give_cooldown = {}

# --- Используем переменную окружения для пути к БД (Railway монтирует volume) ---
# Если есть volume, используем его, иначе локальную папку
if os.path.exists('/data'):
    DB_PATH = '/data/casino_bot.db'
else:
    DB_PATH = 'casino_bot.db'

# --- Инициализация базы данных ---
# Проверяем, существует ли файл БД, если нет - создаём
if not os.path.exists(DB_PATH):
    # Копируем из локальной БД если есть
    if os.path.exists('casino_bot.db'):
        import shutil

        shutil.copy2('casino_bot.db', DB_PATH)
        print(f"✅ База данных скопирована в {DB_PATH}")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
               CREATE TABLE IF NOT EXISTS users
               (
                   user_id
                   INTEGER
                   PRIMARY
                   KEY,
                   balance
                   INTEGER
                   DEFAULT
                   0,
                   total_bet
                   INTEGER
                   DEFAULT
                   0,
                   total_win
                   INTEGER
                   DEFAULT
                   0,
                   last_salary
                   TIMESTAMP
               )
               ''')
conn.commit()


# --- Функции БД ---
def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute('INSERT INTO users (user_id, balance, total_bet, total_win, last_salary) VALUES (?, 0, 0, 0, ?)',
                       (user_id, datetime.min))
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
    return user


def update_balance(user_id, new_balance):
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    conn.commit()


def update_stats(user_id, bet_amount, win_amount):
    cursor.execute('UPDATE users SET total_bet = total_bet + ?, total_win = total_win + ? WHERE user_id = ?',
                   (bet_amount, win_amount, user_id))
    conn.commit()


def update_last_salary(user_id):
    cursor.execute('UPDATE users SET last_salary = ? WHERE user_id = ?', (datetime.now(), user_id))
    conn.commit()


def get_top_players(limit=10):
    cursor.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?', (limit,))
    return cursor.fetchall()


# --- Клавиатура ---
def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_salary = KeyboardButton("💲 Зарплата")
    btn_balance = KeyboardButton("💎 Баланс")
    btn_top = KeyboardButton("🏅 Топ")
    keyboard.add(btn_salary, btn_balance, btn_top)
    return keyboard


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
                         f"📱 Или используй кнопки внизу:",
                         reply_markup=main_keyboard(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id,
                         f"👋 Халяль, {message.from_user.first_name}!\n"
                         f"Твой баланс: 0 халялек.\n\n"
                         f"🎲 Играть: `/dep [сумма]`\n"
                         f"💰 Передать халяльки: ответь на сообщение и напиши `/give [сумма]`",
                         parse_mode="Markdown")


# --- Команда /salary ---
@bot.message_handler(commands=['salary'])
def salary_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last_salary_str = user[4]

    last_salary = datetime.fromisoformat(last_salary_str) if last_salary_str else datetime.min
    now = datetime.now()

    if now - last_salary < timedelta(hours=1):
        next_hour = last_salary + timedelta(hours=1)
        wait_minutes = int((next_hour - now).total_seconds() // 60)
        bot.reply_to(message, f"⏰ Зарплата через {wait_minutes} мин",
                     reply_markup=main_keyboard() if message.chat.type == 'private' else None)
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
        bot.send_message(receiver_id,
                         f"🎁 Получен перевод {amount} халялек от {message.from_user.first_name}\n💎 Баланс: {new_receiver_balance}")
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
                 "💲 `/salary` - зарплата (раз в час)\n"
                 "💎 `/balance` - баланс\n"
                 "🏅 `/top` - топ игроков\n\n"
                 "📱 Кнопки внизу для быстрого доступа!",
                 parse_mode="Markdown")


# --- Запуск бота ---
if __name__ == '__main__':
    print("✅ Бот запущен!")
    print(f"📁 База данных: {DB_PATH}")
    print("📱 Кнопки: Зарплата | Баланс | Топ")
    print("🎲 /dep [сумма]")
    print("💰 /give [сумма] (ответом)")

    # Удаляем вебхук
    try:
        bot.remove_webhook()
        print("Webhook удалён")
    except:
        pass

    # Запускаем polling
    bot.infinity_polling(timeout=60, long_polling_timeout=60)