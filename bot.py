import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

# Сюди встав свій токен бота
BOT_TOKEN = "8614016552:AAFBw5Gh8pXB7LrLmZ_bdR5foqYisUD3Ty8"

# Після запуску ngrok заміни на свою актуальну адресу (без /static)
WEB_APP_URL = "https://siamese-lilly-impotent.ngrok-free.dev"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    btn = KeyboardButton(text='🎰 Відкрити казино', web_app=WebAppInfo(url=WEB_APP_URL))
    markup = ReplyKeyboardMarkup(keyboard=[[btn]], resize_keyboard=True)
    await message.answer("Ласкаво просимо до віртуального казино! 🍀", reply_markup=markup)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())