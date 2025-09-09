import telebot
import logging
from config import BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, "Привет! Я бот такси Светлогорск39.")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "Это тестовая версия бота такси Светлогорск39.")

if __name__ == "__main__":
    logger.info("Запуск упрощенной версии бота")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
    finally:
        logger.info("Бот остановлен")
