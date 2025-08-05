import logging
import json
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram токен (иҷозати худро гузор)
TOKEN = "BOT_TOKEN"

# Travelpayouts cities.json URL
CITIES_URL = "https://api.travelpayouts.com/data/ru/cities.json"

# Сабти чиптаҳо барои истифодабаранда
USER_TICKETS = {}

# Забонҳо
MESSAGES = {
    "en": {
        "welcome": "✈️ Welcome to *SolihonTravelBot!*\nPlease choose a language:",
        "ask_route": "Please send your route and date like this:\n`Yekaterinburg - Dushanbe 20.08.2025`",
        "invalid_format": "❌ Invalid format. Please use:\n`City1 - City2 DD.MM.YYYY`",
        "no_ticket": "You don’t have any tickets yet.",
        "thank_you": "✅ Thank you for your purchase!",
        "your_ticket": "🎫 Your ticket:\n",
        "help": "Send your route like: *Moscow - Dubai 25.08.2025*\nUse /myticket to see your ticket."
    },
    "ru": {
        "welcome": "✈️ Добро пожаловать в *SolihonTravelBot!*\nПожалуйста, выберите язык:",
        "ask_route": "Пожалуйста, отправьте маршрут и дату в формате:\n`Екатеринбург - Душанбе 20.08.2025`",
        "invalid_format": "❌ Неверный формат. Используйте:\n`Город1 - Город2 ДД.ММ.ГГГГ`",
        "no_ticket": "У вас пока нет билетов.",
        "thank_you": "✅ Спасибо за покупку!",
        "your_ticket": "🎫 Ваш билет:\n",
        "help": "Отправьте маршрут, например: *Москва - Дубай 25.08.2025*\nИспользуйте /myticket, чтобы увидеть билет."
    }
}

def load_city_names():
    try:
        response = requests.get(CITIES_URL)
        response.raise_for_status()
        data = response.json()
        return {item["code"]: item["name_translations"]["ru"] for item in data}
    except Exception as e:
        logger.error("Failed to load city names: %s", e)
        return {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ]
    await update.message.reply_text("✈️ Welcome / Добро пожаловать", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.callback_query.data.split("_")[1]
    context.user_data["lang"] = lang
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(MESSAGES[lang]["ask_route"])

async def handle_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    text = update.message.text.strip()
    if not re.match(r"^[A-Za-zА-Яа-яЁё\s\-]{4,} - [A-Za-zА-Яа-яЁё\s\-]{4,} \d{2}\.\d{2}\.\d{4}$", text):
        await update.message.reply_text(MESSAGES[lang]["invalid_format"], parse_mode="Markdown")
        return

    with open("flights.json", "r", encoding="utf-8") as f:
        flight_data = json.load(f)

    city_names = load_city_names()

    for flight in flight_data:
        from_city = city_names.get(flight["from"], flight["from"])
        to_city = city_names.get(flight["to"], flight["to"])
        msg = (
            f"🛫 {from_city} → {to_city}\n"
            f"✈ {flight['airline']}\n"
            f"🛩 {flight['flight_number']} ({flight['aircraft']})\n"
            f"📍 {flight['stopovers']}\n"
            f"💲 {flight['price']}\n"
            f"Available via:"
        )
        buttons = [
            [InlineKeyboardButton(agent["name"], callback_data=f"buy_{agent['name']}_{flight['flight_number']}")]
            for agent in flight["agencies"]
        ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    data = update.callback_query.data.split("_")
    agent = data[1]
    flight_num = data[2]

    # Ссылка бо маркер
    link = f"https://yourtravel.site/buy?marker=123456&flight={flight_num}&agent={agent}"
    USER_TICKETS[update.effective_user.id] = f"{flight_num} via {agent}"

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(f"🔗 [Click here to buy]({link})", parse_mode="Markdown")
    await update.callback_query.message.reply_text(MESSAGES[lang]["thank_you"])

async def myticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    uid = update.effective_user.id
    if uid in USER_TICKETS:
        ticket = USER_TICKETS[uid]
        await update.message.reply_text(MESSAGES[lang]["your_ticket"] + ticket)
    else:
        await update.message.reply_text(MESSAGES[lang]["no_ticket"])

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(MESSAGES[lang]["help"])

def main():
    app = Application.builder().token(TOKEN).build()

    # Устанавливаем меню команд (синие кнопки справа в Telegram)
    commands = [
        BotCommand("start", "Start the bot / Запустить бота"),
        BotCommand("myticket", "Show your ticket / Показать билет"),
        BotCommand("help", "Help and info / Помощь и информация")
    ]
    app.bot.set_my_commands(commands)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_route))
    app.add_handler(CallbackQueryHandler(handle_buy, pattern="^buy_"))
    app.add_handler(CommandHandler("myticket", myticket))
    app.add_handler(CommandHandler("help", help_command))

    app.run_polling()

if __name__ == "__main__":
    main()
