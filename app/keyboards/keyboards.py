from telebot import types
from config import POPULAR_DESTINATIONS, DRIVER_STATUSES

def get_main_keyboard():
    """Основная клавиатура для пользователей"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚕 Заказать такси"))
    markup.add(types.KeyboardButton("📝 Мои заказы"), types.KeyboardButton("📞 Связаться с нами"))
    return markup

def get_admin_keyboard():
    """Клавиатура для администратора"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📊 Активные заказы"))
    markup.add(types.KeyboardButton("👨‍✈️ Управление водителями"), types.KeyboardButton("📋 История заказов"))
    markup.add(types.KeyboardButton("📈 Статистика"), types.KeyboardButton("🔙 Главное меню"))
    return markup

def get_driver_keyboard():
    """Клавиатура для водителей"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚗 Изменить статус"))
    markup.add(types.KeyboardButton("📋 Мои заказы"), types.KeyboardButton("💰 Мой заработок"))
    markup.add(types.KeyboardButton("🔙 Главное меню"))
    return markup

def get_popular_destinations_keyboard():
    """Клавиатура с популярными направлениями"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for destination in POPULAR_DESTINATIONS:
        markup.add(types.KeyboardButton(destination))
    markup.add(types.KeyboardButton("✏️ Ввести другой адрес"))
    markup.add(types.KeyboardButton("🔙 Назад"))
    return markup

def get_order_confirmation_keyboard():
    """Клавиатура для подтверждения заказа"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_order"),
        types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_order")
    )
    return markup

def get_price_response_keyboard(order_id):
    """Клавиатура для ответа на предложенную цену"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Согласен", callback_data=f"accept_price:{order_id}"),
        types.InlineKeyboardButton("❌ Не согласен", callback_data=f"decline_price:{order_id}")
    )
    markup.add(types.InlineKeyboardButton("💰 Предложить свою цену", callback_data=f"counter_offer:{order_id}"))
    return markup

def get_driver_status_keyboard():
    """Клавиатура для изменения статуса водителя"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(DRIVER_STATUSES["ON_DUTY"], callback_data="status:ON_DUTY"))
    markup.add(types.InlineKeyboardButton(DRIVER_STATUSES["ON_ORDER"], callback_data="status:ON_ORDER"))
    markup.add(types.InlineKeyboardButton(DRIVER_STATUSES["OFF_DUTY"], callback_data="status:OFF_DUTY"))
    return markup

def get_rating_keyboard(order_id):
    """Клавиатура для оценки поездки"""
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = [types.InlineKeyboardButton(str(i), callback_data=f"rate:{order_id}:{i}") for i in range(1, 6)]
    markup.add(*buttons)
    return markup

def get_yes_no_keyboard(action, item_id):
    """Универсальная клавиатура да/нет"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Да", callback_data=f"{action}_yes:{item_id}"),
        types.InlineKeyboardButton("❌ Нет", callback_data=f"{action}_no:{item_id}")
    )
    return markup
