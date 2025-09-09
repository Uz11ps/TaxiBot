import telebot
import logging
import os
import sys

# Добавляем текущую директорию в sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import BOT_TOKEN
from app.database.models import init_db
from app.handlers.user_handlers import register_user_handlers
from app.handlers.admin_handlers import register_admin_handlers
from app.handlers.driver_handlers import register_driver_handlers
from app.handlers.order_handlers import register_order_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота Такси Светлогорск39")
    
    # Инициализация базы данных
    init_db()
    logger.info("База данных инициализирована")
    
    # Создание экземпляра бота
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
    
    # Регистрация обработчиков
    register_user_handlers(bot)
    register_admin_handlers(bot)
    register_driver_handlers(bot)
    register_order_handlers(bot)
    
    logger.info("Обработчики зарегистрированы")
    
    # Установка имени бота
    bot_info = bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username} ({bot_info.first_name})")
    
    # Запуск бота
    try:
        logger.info("Бот начал прослушивание сообщений")
        bot.set_my_commands([
            telebot.types.BotCommand("/start", "Начать работу с ботом"),
            telebot.types.BotCommand("/help", "Показать справку"),
            telebot.types.BotCommand("/order", "Заказать такси"),
            telebot.types.BotCommand("/profile", "Ваш профиль"),
            telebot.types.BotCommand("/driver", "Меню водителя"),
            telebot.types.BotCommand("/admin", "Админ-панель (только для администраторов)")
        ])
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
    finally:
        logger.info("Бот остановлен")

if __name__ == "__main__":
    main()
