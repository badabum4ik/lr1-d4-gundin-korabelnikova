import logging
import random
import asyncio
import nest_asyncio  # Новое подключение
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import pymysql
from flask import Flask, render_template, request, redirect, url_for
from flask_bootstrap import Bootstrap
from threading import Thread
from pymysql import Error
import os

nest_asyncio.apply()
app = Flask(__name__)
Bootstrap(app)

# Функция для подключения к базе данных
def get_db_connection():
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='root',
            database='lr1db',
            port=3306
        )
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        return connection
    except Error as e:
        print(f"Ошибка подключения: {e}")
        return None

# Глобальная переменная для хранения состояния команд
command_states = {
    "start": True,
    "start_timer": True,
    "stop_timer": True,
    "register": True,
    "start_game": True,
    "stop_game": True
}

@app.route('/')
def home():
    conn = get_db_connection()
    if conn is None:
        return "Ошибка подключения к базе данных"

    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM lr1db")
        users = cursor.fetchall()
    finally:
        conn.close()

    return render_template('users.html', users=users, commands=command_states)

@app.route('/toggle_command', methods=['POST'])
def toggle_command():
    global command_states

    # Обновляем состояния команд в зависимости от данных из формы
    for command in command_states:
        command_states[command] = request.form.get(command) == "on"

    return redirect(url_for('home'))

# Обработчик команды регистрации пользователя
async def handle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not command_states["register"]:
        await notify_command_disabled(update, "/register")
        return

    user = update.effective_user
    telegram_id = user.id
    username = user.username

    conn = get_db_connection()
    if conn is None:
        bot_reply = "Ошибка подключения к базе данных."
        await update.message.reply_text(bot_reply)
        return

    try:
        cursor = conn.cursor()

        # Используем INSERT IGNORE для предотвращения повторений
        cursor.execute(
            "INSERT IGNORE INTO lr1db (telegram_id, username) VALUES (%s, %s)",
            (telegram_id, username)
        )
        conn.commit()

        # Проверяем, была ли вставка в таблицу
        if cursor.rowcount > 0:
            bot_reply = "Вы успешно зарегистрированы!"
        else:
            bot_reply = "Вы уже зарегистрированы!"
    except Error as e:
        bot_reply = f"Ошибка регистрации: {e}"
    finally:
        conn.close()

    await update.message.reply_text(bot_reply)



# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = '7437730276:AAEcGcKzegUuB1qWBHa67uXOBxdLLdGiq0I'
bot = Bot(token=TOKEN)

# Словарь случайных сообщений
random_messages_dict = [
    "Привет!", "Как дела?", "Что нового?", "Здравствуй!", "Приятно тебя видеть!"
]

# Файл с фразами
file_name = "random_phrases.txt"

# Файл для сохранения переписки
conversation_log_file = "conversation_log.txt"

# Список для игры
game_words = ["яблоко", "груша", "банан", "апельсин", "ананас", "виноград", "фейхоа", "стоп"]
game_active = False
secret_word = None
timer_task = None
game_active = False  # Глобальная переменная для состояния игры
secret_word = None  # Секретное слово для игры

# Обработка команды /start_game
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_active, secret_word

    if not command_states["start_game"]:
        await update.message.reply_text("Команда /start_game отключена.")
        return

    if game_active:
        await update.message.reply_text("Игра уже идет! Угадайте слово.")
        return

    game_active = True
    secret_word = random.choice(game_words)
    await update.message.reply_text("Игра началась! Угадайте слово из списка: яблоко, груша, банан, апельсин, ананас, виноград, фейхоа. Напишите слово в чат! Чтобы закончить игру напишите слово стоп или используйте команду /stop_game ")

# Обработка команды /stop_game
async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_active

    if not command_states["stop_game"]:
        await update.message.reply_text("Команда /stop_game отключена.")
        return

    if not game_active:
        await update.message.reply_text("Игра не активна.")
        return

    game_active = False
    await update.message.reply_text("Игра остановлена.")

# Обработка сообщений во время игры
async def game_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_active, secret_word

    if not game_active:
        return

    user_guess = update.message.text.lower()

    if user_guess == secret_word:
        game_active = False
        await update.message.reply_text(f"Поздравляю! Вы угадали слово: {secret_word}")
    elif user_guess == "стоп":
        game_active = False
        await update.message.reply_text("Игра остановлена по вашему запросу.")
    else:
        await update.message.reply_text("Неправильно! Попробуйте еще раз.")

# Функция для записи сообщений в файл
def log_conversation(user_id, username, message, bot_reply):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(conversation_log_file, "a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {username} (ID: {user_id}): {message}\n")
        log_file.write(f"[{timestamp}] Бот: {bot_reply}\n\n")

# Обработчик команды /start
async def send_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not command_states["start"]:
        await notify_command_disabled(update, "/start")
        return

    random_message = random.choice(random_messages_dict)
    user = update.effective_user
    await update.message.reply_text(random_message)
    log_conversation(user.id, user.username, "/start", random_message)

# Таймер для отправки случайных фраз из файла
async def send_random_phrase_from_file(chat_id, bot: Bot):
    while True:
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    random_line = random.choice(lines).strip()
                    await bot.send_message(chat_id=chat_id, text=random_line)
                    log_conversation(chat_id, chat_id, "Таймер: фраза", random_line)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Ошибка при чтении файла: {e}")
            await asyncio.sleep(5)

# Обработчик команды для запуска таймера
async def start_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not command_states["start_timer"]:
        await notify_command_disabled(update, "/start_timer")
        return

    global timer_task
    chat_id = update.message.chat_id

    if timer_task:
        bot_reply = "Таймер уже запущен."
        await update.message.reply_text(bot_reply)
        log_conversation(update.effective_user.id, update.effective_user.username, "/start_timer", bot_reply)
        return

    bot_reply = "Таймер запущен. Буду отправлять случайные фразы каждые 5 секунд!"
    await update.message.reply_text(bot_reply)
    log_conversation(update.effective_user.id, update.effective_user.username, "/start_timer", bot_reply)

    async def timer_wrapper():
        await send_random_phrase_from_file(chat_id, context.bot)

    timer_task = asyncio.create_task(timer_wrapper())

# Обработчик команды для остановки таймера
async def stop_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not command_states["stop_timer"]:
        await notify_command_disabled(update, "/stop_timer")
        return

    global timer_task
    if timer_task:
        timer_task.cancel()
        timer_task = None
        bot_reply = "Таймер остановлен."
    else:
        bot_reply = "Таймер не был запущен."

    await update.message.reply_text(bot_reply)
    log_conversation(update.effective_user.id, update.effective_user.username, "/stop_timer", bot_reply)

# Обработка текстовых файлов
async def handle_text_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if document.mime_type == "text/plain":
        file = await document.get_file()
        file_path = f"downloads/{document.file_name}"

        # Проверка и создание директории 'downloads', если она не существует
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        await file.download_to_drive(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        await update.message.reply_text(f"Файл получен! Содержимое:\n{content}")
    else:
        await update.message.reply_text("Файл не является текстовым. Пожалуйста, отправьте текстовый файл (.txt).")

# Основная функция для запуска бота
async def main():
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", send_welcome))
    application.add_handler(CommandHandler("start_timer", start_timer))
    application.add_handler(CommandHandler("stop_timer", stop_timer))
    application.add_handler(CommandHandler("register", handle_registration))
    application.add_handler(CommandHandler("start_game", start_game))
    application.add_handler(CommandHandler("stop_game", stop_game))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, game_guess))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_text_file))

    # Запуск бота
    logger.info("Бот запущен!")
    await application.run_polling()


async def notify_command_disabled(update: Update, command_name: str):
    message = f"Команда {command_name} отключена администратором."
    await update.message.reply_text(message)
    log_conversation(update.effective_user.id, update.effective_user.username, command_name, message)


def run_flask():
    app.run(debug=True, port=5000, use_reloader=False)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Получаем текущий событийный цикл
    loop = asyncio.get_event_loop()

    # Запускаем Telegram-бота в этом же цикле
    loop.run_until_complete(main())
