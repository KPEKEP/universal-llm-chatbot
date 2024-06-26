import asyncio
from bot.telegram_bot import TelegramBot
from utils.config import load_config
from utils.localization import load_localization

def main():
    config = load_config()
    localization = load_localization()
    bot = TelegramBot(config, localization)
    bot.run()

if __name__ == '__main__':
    main()