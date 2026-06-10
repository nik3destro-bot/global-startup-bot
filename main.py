import os
import threading
import psycopg2
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, HTMLResponse
from telebot import TeleBot, types
import uvicorn

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ТВОЙ_ТОКЕН")
# Облако само передаст адрес базы данных в переменную DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL")

app = FastAPI(title="Global Startup Engine")
bot = TeleBot(BOT_TOKEN)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ POSTGRESQL ---
def init_db():
    if not DATABASE_URL:
        print("Ошибка: Переменная DATABASE_URL не найдена!")
        return
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    # В PostgreSQL синтаксис немного отличается (SERIAL вместо AUTOINCREMENT)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id SERIAL PRIMARY KEY,
            link_id TEXT,
            platform TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

if DATABASE_URL:
    init_db()

# --- ВЕБ-САЙТ И СИСТЕМА ТРЕКИНГА ---

@app.get("/", response_class=HTMLResponse)
def read_root():
    # Проверяем, существует ли файл index.html в корневой папке проекта
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as file:
            # Возвращаем содержимое HTML-файла с кодом 200 (ОК)
            return HTMLResponse(content=file.read(), status_code=200)
    
    # Если файл забыли загрузить, сервер покажет понятную ошибку вместо падения
    return HTMLResponse(
        content="<h1>Ошибка: файл index.html не найден в корне проекта!</h1>", 
        status_code=404
    )

@app.get("/redirect/{link_id}")
def track_and_redirect(link_id: str):
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clicks (link_id, platform) VALUES (%s, %s)", (link_id, "web"))
        conn.commit()
        conn.close()
    return RedirectResponse(url="https://t.me/your_channel_name") # Укажи свою ссылку

# --- ТЕЛЕГРАМ-БОТ ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clicks (link_id, platform) VALUES (%s, %s)", ("bot_start", "telegram"))
        conn.commit()
        conn.close()

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("🔥 Тест ссылки", url="https://global-startup-bot.onrender.com/redirect/bot_promo")
    btn2 = types.InlineKeyboardButton("📊 Статистика кликов", callback_data="stats")
    markup.add(btn1, btn2)
    
    bot.send_message(message.chat.id, "Система запущена в облаке 24/7!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "stats")
def show_stats(call):
    if not DATABASE_URL:
        bot.send_message(call.message.chat.id, "База данных не подключена")
        return
        
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM clicks WHERE platform='web'")
    web_clicks = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM clicks WHERE platform='telegram'")
    tg_clicks = cursor.fetchone()[0]
    conn.close()

    bot.send_message(call.message.chat.id, f"📊 Статистика из облака:\n\n💻 Клики на сайте: {web_clicks}\n🤖 Боты: {tg_clicks}")

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Порт 10000 стандартный для Render
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)