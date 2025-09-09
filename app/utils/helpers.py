from app.database import Session, User, Driver, Order, Review
from sqlalchemy import func
from config import CITY_NAME, CITY_RADIUS
import json

def save_user_data(user_id, username, first_name, last_name):
    """Сохраняет или обновляет данные пользователя"""
    session = Session()
    user = session.query(User).filter(User.user_id == user_id).first()
    
    if not user:
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        session.add(user)
    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
    
    session.commit()
    user_id = user.id
    session.close()
    return user_id

def get_user_by_id(user_id):
    """Получает пользователя по Telegram ID"""
    session = Session()
    user = session.query(User).filter(User.user_id == user_id).first()
    session.close()
    return user

def get_driver_by_id(user_id):
    """Получает водителя по Telegram ID"""
    session = Session()
    driver = session.query(Driver).filter(Driver.user_id == user_id).first()
    session.close()
    return driver

def format_order_info(order):
    """Форматирует информацию о заказе для отображения"""
    status_map = {
        "NEW": "Новый",
        "PRICE_OFFERED": "Предложена цена",
        "ACCEPTED": "Принят",
        "DECLINED": "Отклонен",
        "IN_PROGRESS": "Выполняется",
        "COMPLETED": "Завершен",
        "CANCELLED": "Отменен"
    }
    
    text = f"🚕 <b>Заказ #{order.id}</b>\n\n"
    text += f"📍 <b>Откуда:</b> {order.from_address}\n"
    text += f"🏁 <b>Куда:</b> {order.to_address}\n"
    
    if order.comment:
        text += f"💬 <b>Комментарий:</b> {order.comment}\n"
    
    if order.price:
        text += f"💰 <b>Цена:</b> {order.price} руб.\n"
    
    if order.counter_offer:
        text += f"💸 <b>Встречное предложение:</b> {order.counter_offer} руб.\n"
    
    text += f"📊 <b>Статус:</b> {status_map.get(order.status, order.status)}\n"
    text += f"🕒 <b>Создан:</b> {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    
    if order.completed_at:
        text += f"✅ <b>Завершен:</b> {order.completed_at.strftime('%d.%m.%Y %H:%M')}\n"
    
    return text

def format_driver_info(driver):
    """Форматирует информацию о водителе для отображения"""
    status_map = {
        "ON_DUTY": "На линии",
        "ON_ORDER": "На заказе",
        "OFF_DUTY": "Дома"
    }
    
    text = f"👨‍✈️ <b>Водитель:</b> {driver.first_name}\n"
    text += f"🚗 <b>Номер авто:</b> {driver.car_number}\n"
    text += f"📊 <b>Статус:</b> {status_map.get(driver.status, driver.status)}\n"
    
    # Расчет рейтинга
    session = Session()
    avg_rating = session.query(func.avg(Review.rating)).filter(Review.driver_id == driver.id).scalar()
    session.close()
    
    if avg_rating:
        text += f"⭐ <b>Рейтинг:</b> {avg_rating:.1f}/5.0\n"
    
    return text

def calculate_rating(driver_id):
    """Рассчитывает средний рейтинг водителя"""
    session = Session()
    avg_rating = session.query(func.avg(Review.rating)).filter(Review.driver_id == driver_id).scalar() or 0
    session.close()
    return avg_rating

def is_within_city_radius(address):
    """
    Проверяет, находится ли адрес в пределах радиуса города
    
    В реальном приложении здесь должна быть интеграция с геокодером и расчет расстояния.
    Для демонстрации просто проверяем, что адрес содержит название города.
    """
    return CITY_NAME.lower() in address.lower()

def get_admin_order_view(order):
    """Форматирует информацию о заказе для админа"""
    text = format_order_info(order)
    
    session = Session()
    client = session.query(User).filter(User.id == order.client_id).first()
    
    if client:
        text += f"\n👤 <b>Клиент:</b> {client.first_name or ''} {client.last_name or ''}\n"
        text += f"📱 <b>Телефон:</b> {client.phone_number or 'Не указан'}\n"
    
    if order.driver_id:
        driver = session.query(Driver).filter(Driver.id == order.driver_id).first()
        if driver:
            text += f"\n🚕 <b>Водитель:</b> {driver.first_name}\n"
            text += f"🚗 <b>Номер авто:</b> {driver.car_number}\n"
    
    session.close()
    return text
