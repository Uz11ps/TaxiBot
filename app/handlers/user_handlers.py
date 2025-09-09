from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from app.keyboards import get_main_keyboard
from app.utils import save_user_data, get_user_by_id
from app.database import Session, User

def register_user_handlers(bot: TeleBot):
    """Регистрация обработчиков команд пользователей"""
    
    @bot.message_handler(commands=['start'])
    def start_command(message: Message):
        """Обработчик команды /start"""
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        # Сохраняем пользователя в БД
        save_user_data(user_id, username, first_name, last_name)
        
        # Приветственное сообщение
        bot.send_message(
            message.chat.id,
            f"Добро пожаловать в Такси Светлогорск39, {first_name}!\n\n"
            f"С помощью этого бота вы можете заказать такси в Светлогорске и окрестностях.",
            reply_markup=get_main_keyboard()
        )
    
    @bot.message_handler(func=lambda message: message.text == "📞 Связаться с нами")
    def contact_us(message: Message):
        """Обработчик кнопки 'Связаться с нами'"""
        bot.send_message(
            message.chat.id,
            "Если у вас возникли вопросы или проблемы, свяжитесь с нами:\n\n"
            "📞 Телефон: +7 (XXX) XXX-XX-XX\n"
            "📧 Email: taxi@svetlogorsk39.ru\n"
            "🌐 Сайт: svetlogorsk39-taxi.ru"
        )
    
    @bot.message_handler(func=lambda message: message.text == "🔙 Главное меню")
    def back_to_main_menu(message: Message):
        """Обработчик кнопки 'Главное меню'"""
        bot.send_message(
            message.chat.id,
            "Вы вернулись в главное меню.",
            reply_markup=get_main_keyboard()
        )
    
    @bot.message_handler(commands=['help'])
    def help_command(message: Message):
        """Обработчик команды /help"""
        bot.send_message(
            message.chat.id,
            "🚕 <b>Такси Светлогорск39</b> - бот для заказа такси\n\n"
            "<b>Доступные команды:</b>\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать справку\n"
            "/order - Заказать такси\n"
            "/profile - Ваш профиль\n\n"
            "Для заказа такси нажмите кнопку 'Заказать такси' в меню.",
            parse_mode="HTML"
        )
    
    @bot.message_handler(commands=['profile'])
    def profile_command(message: Message):
        """Обработчик команды /profile"""
        user_id = message.from_user.id
        user = get_user_by_id(user_id)
        
        if not user:
            bot.send_message(message.chat.id, "Ошибка получения данных профиля.")
            return
        
        # Получаем историю заказов
        session = Session()
        orders_count = session.query(User).filter(User.user_id == user_id).count()
        session.close()
        
        profile_text = f"👤 <b>Ваш профиль</b>\n\n"
        profile_text += f"Имя: {user.first_name or 'Не указано'} {user.last_name or ''}\n"
        profile_text += f"Телефон: {user.phone_number or 'Не указан'}\n"
        profile_text += f"Количество заказов: {orders_count}\n"
        
        bot.send_message(message.chat.id, profile_text, parse_mode="HTML")
        
        # Если телефон не указан, предлагаем его указать
        if not user.phone_number:
            bot.send_message(
                message.chat.id,
                "Для удобства заказа такси рекомендуем указать номер телефона.",
                reply_markup=get_phone_request_keyboard()
            )
    
    def get_phone_request_keyboard():
        """Клавиатура для запроса номера телефона"""
        from telebot import types
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        button = types.KeyboardButton("📱 Отправить номер телефона", request_contact=True)
        markup.add(button)
        markup.add(types.KeyboardButton("🔙 Главное меню"))
        return markup
    
    @bot.message_handler(content_types=['contact'])
    def contact_handler(message: Message):
        """Обработчик получения контакта (номера телефона)"""
        if message.contact is not None:
            user_id = message.from_user.id
            phone = message.contact.phone_number
            
            # Сохраняем телефон в БД
            session = Session()
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                user.phone_number = phone
                session.commit()
            session.close()
            
            bot.send_message(
                message.chat.id,
                "Спасибо! Ваш номер телефона сохранен.",
                reply_markup=get_main_keyboard()
            )
