from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from app.keyboards import (
    get_main_keyboard,
    get_popular_destinations_keyboard,
    get_order_confirmation_keyboard,
    get_price_response_keyboard,
    get_rating_keyboard
)
from app.utils import save_user_data, get_user_by_id, is_within_city_radius, format_order_info
from app.database import Session, User, Order, Driver, Review
from config import ADMIN_ID, POPULAR_DESTINATIONS
import datetime

# Словарь для хранения временных данных заказа
user_order_data = {}

def register_order_handlers(bot: TeleBot):
    """Регистрация обработчиков для заказов"""
    
    @bot.message_handler(commands=['order'])
    @bot.message_handler(func=lambda message: message.text == "🚕 Заказать такси")
    def order_taxi(message: Message):
        """Обработчик команды заказа такси"""
        user_id = message.from_user.id
        
        # Сохраняем пользователя в БД, если его еще нет
        save_user_data(
            user_id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        # Инициализируем данные заказа
        user_order_data[user_id] = {}
        
        # Запрашиваем адрес отправления
        bot.send_message(
            message.chat.id,
            "Пожалуйста, укажите адрес отправления (точка А).\n\n"
            "⚠️ Обратите внимание, что заказы принимаются только из г. Светлогорск и в радиусе 10 км.",
            reply_markup=None
        )
        bot.register_next_step_handler(message, process_from_address)
    
    def process_from_address(message: Message):
        """Обработка адреса отправления"""
        user_id = message.from_user.id
        from_address = message.text
        
        # Проверяем, что адрес в пределах города
        if not is_within_city_radius(from_address):
            bot.send_message(
                message.chat.id,
                "К сожалению, указанный адрес находится за пределами зоны обслуживания.\n"
                "Мы работаем только в г. Светлогорск и в радиусе 10 км.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Сохраняем адрес отправления
        user_order_data[user_id]['from_address'] = from_address
        
        # Запрашиваем адрес назначения
        bot.send_message(
            message.chat.id,
            "Теперь укажите адрес назначения (точка Б):",
            reply_markup=get_popular_destinations_keyboard()
        )
        bot.register_next_step_handler(message, process_to_address)
    
    def process_to_address(message: Message):
        """Обработка адреса назначения"""
        user_id = message.from_user.id
        to_address = message.text
        
        # Проверяем, не выбрал ли пользователь "Назад"
        if to_address == "🔙 Назад":
            order_taxi(message)
            return
        
        # Если пользователь выбрал "Ввести другой адрес"
        if to_address == "✏️ Ввести другой адрес":
            bot.send_message(
                message.chat.id,
                "Пожалуйста, введите адрес назначения:",
                reply_markup=None
            )
            bot.register_next_step_handler(message, process_custom_to_address)
            return
        
        # Сохраняем адрес назначения
        user_order_data[user_id]['to_address'] = to_address
        
        # Запрашиваем комментарий к заказу
        bot.send_message(
            message.chat.id,
            "Добавьте комментарий к заказу (необязательно).\n"
            "Если комментарий не нужен, отправьте '-':",
            reply_markup=None
        )
        bot.register_next_step_handler(message, process_comment)
    
    def process_custom_to_address(message: Message):
        """Обработка пользовательского адреса назначения"""
        user_id = message.from_user.id
        to_address = message.text
        
        # Сохраняем адрес назначения
        user_order_data[user_id]['to_address'] = to_address
        
        # Запрашиваем комментарий к заказу
        bot.send_message(
            message.chat.id,
            "Добавьте комментарий к заказу (необязательно).\n"
            "Если комментарий не нужен, отправьте '-':",
            reply_markup=None
        )
        bot.register_next_step_handler(message, process_comment)
    
    def process_comment(message: Message):
        """Обработка комментария к заказу"""
        user_id = message.from_user.id
        comment = message.text
        
        # Сохраняем комментарий, если он не пустой
        if comment and comment != '-':
            user_order_data[user_id]['comment'] = comment
        else:
            user_order_data[user_id]['comment'] = None
        
        # Показываем информацию о заказе для подтверждения
        from_address = user_order_data[user_id]['from_address']
        to_address = user_order_data[user_id]['to_address']
        comment_text = user_order_data[user_id].get('comment', None)
        
        confirmation_text = f"📋 <b>Информация о заказе:</b>\n\n"
        confirmation_text += f"📍 <b>Откуда:</b> {from_address}\n"
        confirmation_text += f"🏁 <b>Куда:</b> {to_address}\n"
        
        if comment_text:
            confirmation_text += f"💬 <b>Комментарий:</b> {comment_text}\n"
        
        confirmation_text += "\nПодтвердите заказ:"
        
        bot.send_message(
            message.chat.id,
            confirmation_text,
            parse_mode="HTML",
            reply_markup=get_order_confirmation_keyboard()
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "confirm_order")
    def confirm_order_callback(call: CallbackQuery):
        """Обработка подтверждения заказа"""
        user_id = call.from_user.id
        
        # Проверяем наличие данных заказа
        if user_id not in user_order_data:
            bot.answer_callback_query(call.id, "Ошибка: данные заказа не найдены")
            bot.send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, начните заказ заново.")
            return
        
        # Получаем данные заказа
        order_data = user_order_data[user_id]
        
        # Получаем ID пользователя в БД
        user = get_user_by_id(user_id)
        if not user:
            bot.answer_callback_query(call.id, "Ошибка: пользователь не найден")
            bot.send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, начните заказ заново.")
            return
        
        # Создаем заказ в БД
        session = Session()
        new_order = Order(
            client_id=user.id,
            from_address=order_data['from_address'],
            to_address=order_data['to_address'],
            comment=order_data.get('comment'),
            status="NEW"
        )
        session.add(new_order)
        session.commit()
        order_id = new_order.id
        session.close()
        
        # Уведомляем пользователя
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Заказ #{order_id} успешно создан и отправлен диспетчеру.\n\n"
                 f"Ожидайте, в ближайшее время вам будет предложена цена поездки.",
            reply_markup=None
        )
        
        # Отправляем уведомление админу
        admin_text = f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
        admin_text += f"👤 <b>Клиент:</b> {call.from_user.first_name} {call.from_user.last_name or ''}\n"
        admin_text += f"📍 <b>Откуда:</b> {order_data['from_address']}\n"
        admin_text += f"🏁 <b>Куда:</b> {order_data['to_address']}\n"
        
        if order_data.get('comment'):
            admin_text += f"💬 <b>Комментарий:</b> {order_data['comment']}\n"
        
        bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="HTML"
        )
        
        # Очищаем временные данные
        if user_id in user_order_data:
            del user_order_data[user_id]
    
    @bot.callback_query_handler(func=lambda call: call.data == "cancel_order")
    def cancel_order_callback(call: CallbackQuery):
        """Обработка отмены заказа"""
        user_id = call.from_user.id
        
        # Очищаем временные данные
        if user_id in user_order_data:
            del user_order_data[user_id]
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Заказ отменен.",
            reply_markup=None
        )
        
        bot.send_message(
            call.message.chat.id,
            "Вы можете создать новый заказ или вернуться в главное меню.",
            reply_markup=get_main_keyboard()
        )
    
    @bot.message_handler(func=lambda message: message.text == "📝 Мои заказы")
    def my_orders(message: Message):
        """Показывает историю заказов пользователя"""
        user_id = message.from_user.id
        user = get_user_by_id(user_id)
        
        if not user:
            bot.send_message(message.chat.id, "Ошибка получения данных пользователя.")
            return
        
        # Получаем заказы пользователя
        session = Session()
        orders = session.query(Order).filter(Order.client_id == user.id).order_by(Order.created_at.desc()).limit(5).all()
        
        if not orders:
            bot.send_message(message.chat.id, "У вас пока нет заказов.")
            return
        
        for order in orders:
            order_text = format_order_info(order)
            
            # Добавляем кнопку для оценки, если заказ завершен и еще не оценен
            markup = None
            if order.status == "COMPLETED":
                # Проверяем, есть ли уже отзыв
                review = session.query(Review).filter(Review.order_id == order.id).first()
                if not review:
                    markup = get_rating_keyboard(order.id)
            
            bot.send_message(
                message.chat.id,
                order_text,
                parse_mode="HTML",
                reply_markup=markup
            )
        
        session.close()
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("rate:"))
    def process_rating(call: CallbackQuery):
        """Обработка оценки поездки"""
        parts = call.data.split(":")
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "Ошибка обработки оценки")
            return
        
        order_id = int(parts[1])
        rating = int(parts[2])
        user_id = call.from_user.id
        
        # Получаем пользователя
        user = get_user_by_id(user_id)
        if not user:
            bot.answer_callback_query(call.id, "Ошибка: пользователь не найден")
            return
        
        # Проверяем заказ и добавляем отзыв
        session = Session()
        order = session.query(Order).filter(Order.id == order_id, Order.client_id == user.id).first()
        
        if not order:
            bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
            session.close()
            return
        
        # Проверяем, есть ли уже отзыв
        existing_review = session.query(Review).filter(Review.order_id == order_id).first()
        if existing_review:
            bot.answer_callback_query(call.id, "Вы уже оставили отзыв на этот заказ")
            session.close()
            return
        
        # Создаем отзыв
        review = Review(
            order_id=order_id,
            client_id=user.id,
            driver_id=order.driver_id,
            rating=rating
        )
        session.add(review)
        session.commit()
        session.close()
        
        # Удаляем кнопки оценки
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
        # Запрашиваем комментарий к отзыву
        bot.send_message(
            call.message.chat.id,
            f"Спасибо за оценку {rating}/5! Хотите добавить комментарий к отзыву?\n"
            "Если нет, отправьте '-':"
        )
        bot.register_next_step_handler(call.message, lambda m: process_review_comment(m, order_id))
    
    def process_review_comment(message: Message, order_id: int):
        """Обработка комментария к отзыву"""
        comment = message.text
        
        if comment and comment != '-':
            session = Session()
            review = session.query(Review).filter(Review.order_id == order_id).first()
            
            if review:
                review.comment = comment
                session.commit()
            
            session.close()
            
            bot.send_message(
                message.chat.id,
                "Спасибо за ваш отзыв! Мы ценим ваше мнение.",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "Спасибо за вашу оценку!",
                reply_markup=get_main_keyboard()
            )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("accept_price:"))
    def accept_price_callback(call: CallbackQuery):
        """Обработка принятия цены"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        order_id = int(parts[1])
        
        # Обновляем статус заказа
        session = Session()
        order = session.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
            session.close()
            return
        
        order.status = "ACCEPTED"
        session.commit()
        session.close()
        
        # Уведомляем пользователя
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Вы приняли цену {order.price} руб. за поездку.\n\n"
                 f"Ожидайте, в ближайшее время вам будет назначен водитель.",
            reply_markup=None
        )
        
        # Уведомляем админа
        bot.send_message(
            ADMIN_ID,
            f"✅ Клиент принял цену {order.price} руб. за заказ #{order_id}.\n"
            f"Необходимо назначить водителя."
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("decline_price:"))
    def decline_price_callback(call: CallbackQuery):
        """Обработка отклонения цены"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        order_id = int(parts[1])
        
        # Обновляем статус заказа
        session = Session()
        order = session.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
            session.close()
            return
        
        order.status = "DECLINED"
        session.commit()
        session.close()
        
        # Уведомляем пользователя
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"❌ Вы отклонили цену {order.price} руб. за поездку.\n\n"
                 f"Заказ отменен.",
            reply_markup=None
        )
        
        # Уведомляем админа
        bot.send_message(
            ADMIN_ID,
            f"❌ Клиент отклонил цену {order.price} руб. за заказ #{order_id}."
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("counter_offer:"))
    def counter_offer_callback(call: CallbackQuery):
        """Обработка встречного предложения цены"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        order_id = int(parts[1])
        
        # Запрашиваем новую цену
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Введите вашу цену за поездку (только число в рублях):",
            reply_markup=None
        )
        
        bot.register_next_step_handler(
            call.message,
            lambda m: process_counter_offer(m, order_id)
        )
    
    def process_counter_offer(message: Message, order_id: int):
        """Обработка введенной встречной цены"""
        try:
            price = float(message.text)
            
            if price <= 0:
                bot.send_message(
                    message.chat.id,
                    "Цена должна быть положительным числом. Пожалуйста, попробуйте еще раз."
                )
                return
            
            # Обновляем заказ
            session = Session()
            order = session.query(Order).filter(Order.id == order_id).first()
            
            if not order:
                bot.send_message(message.chat.id, "Ошибка: заказ не найден")
                session.close()
                return
            
            order.counter_offer = price
            session.commit()
            session.close()
            
            # Уведомляем пользователя
            bot.send_message(
                message.chat.id,
                f"✅ Ваше предложение цены {price} руб. отправлено диспетчеру.\n"
                f"Ожидайте ответа.",
                reply_markup=get_main_keyboard()
            )
            
            # Уведомляем админа
            bot.send_message(
                ADMIN_ID,
                f"💰 Клиент предложил свою цену {price} руб. за заказ #{order_id}.\n"
                f"Исходная цена: {order.price} руб."
            )
            
        except ValueError:
            bot.send_message(
                message.chat.id,
                "Ошибка: введите корректное число. Пожалуйста, попробуйте еще раз."
            )
