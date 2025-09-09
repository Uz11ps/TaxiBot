from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from app.keyboards import get_admin_keyboard, get_main_keyboard, get_yes_no_keyboard
from app.utils import get_admin_order_view, format_driver_info
from app.database import Session, User, Driver, Order, Earning
from config import ADMIN_ID
from sqlalchemy import desc
import datetime

def register_admin_handlers(bot: TeleBot):
    """Регистрация обработчиков для администратора"""
    
    @bot.message_handler(commands=['admin'])
    def admin_command(message: Message):
        """Обработчик команды /admin"""
        user_id = message.from_user.id
        
        # Проверяем, является ли пользователь администратором
        if user_id != ADMIN_ID:
            bot.send_message(
                message.chat.id,
                "У вас нет доступа к административной панели."
            )
            return
        
        # Показываем админ-панель
        bot.send_message(
            message.chat.id,
            "👑 <b>Административная панель</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    
    @bot.message_handler(func=lambda message: message.text == "📊 Активные заказы" and message.from_user.id == ADMIN_ID)
    def active_orders(message: Message):
        """Показывает активные заказы"""
        session = Session()
        
        # Получаем все активные заказы (новые и принятые)
        orders = session.query(Order).filter(
            Order.status.in_(["NEW", "PRICE_OFFERED", "ACCEPTED", "IN_PROGRESS"])
        ).order_by(desc(Order.created_at)).all()
        
        if not orders:
            bot.send_message(
                message.chat.id,
                "Активных заказов нет.",
                reply_markup=get_admin_keyboard()
            )
            session.close()
            return
        
        # Отправляем информацию о каждом заказе
        for order in orders:
            order_text = get_admin_order_view(order)
            
            # Добавляем кнопки действий в зависимости от статуса заказа
            markup = None
            
            if order.status == "NEW":
                # Для новых заказов - кнопка установки цены
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("💰 Установить цену", callback_data=f"set_price:{order.id}"))
            
            elif order.status == "ACCEPTED":
                # Для принятых заказов - кнопка назначения водителя
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🚕 Назначить водителя", callback_data=f"assign_driver:{order.id}"))
            
            bot.send_message(
                message.chat.id,
                order_text,
                parse_mode="HTML",
                reply_markup=markup
            )
        
        session.close()
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_price:") and call.from_user.id == ADMIN_ID)
    def set_price_callback(call: CallbackQuery):
        """Обработка установки цены заказа"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        order_id = int(parts[1])
        
        # Запрашиваем цену
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
        bot.send_message(
            call.message.chat.id,
            f"Введите цену для заказа #{order_id} (только число в рублях):"
        )
        
        bot.register_next_step_handler(
            call.message,
            lambda m: process_price_input(m, order_id)
        )
    
    def process_price_input(message: Message, order_id: int):
        """Обработка введенной цены"""
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
            
            order.price = price
            order.status = "PRICE_OFFERED"
            session.commit()
            
            # Получаем клиента
            client = session.query(User).filter(User.id == order.client_id).first()
            client_id = client.user_id if client else None
            
            session.close()
            
            # Уведомляем администратора
            bot.send_message(
                message.chat.id,
                f"✅ Цена {price} руб. установлена для заказа #{order_id}.",
                reply_markup=get_admin_keyboard()
            )
            
            # Уведомляем клиента
            if client_id:
                from app.keyboards import get_price_response_keyboard
                
                client_text = f"💰 <b>Предложена цена за поездку</b>\n\n"
                client_text += f"Заказ #{order_id}\n"
                client_text += f"Цена: {price} руб.\n\n"
                client_text += "Выберите действие:"
                
                bot.send_message(
                    client_id,
                    client_text,
                    parse_mode="HTML",
                    reply_markup=get_price_response_keyboard(order_id)
                )
        
        except ValueError:
            bot.send_message(
                message.chat.id,
                "Ошибка: введите корректное число. Пожалуйста, попробуйте еще раз."
            )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("assign_driver:") and call.from_user.id == ADMIN_ID)
    def assign_driver_callback(call: CallbackQuery):
        """Обработка назначения водителя"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        order_id = int(parts[1])
        
        # Получаем список доступных водителей
        session = Session()
        drivers = session.query(Driver).filter(
            Driver.is_approved == True,
            Driver.status == "ON_DUTY"
        ).all()
        
        if not drivers:
            bot.answer_callback_query(call.id, "Нет доступных водителей")
            bot.send_message(
                call.message.chat.id,
                "В данный момент нет доступных водителей на линии."
            )
            session.close()
            return
        
        # Удаляем кнопки из предыдущего сообщения
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
        # Создаем клавиатуру с водителями
        markup = types.InlineKeyboardMarkup()
        for driver in drivers:
            button_text = f"{driver.first_name} - {driver.car_number}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=f"select_driver:{order_id}:{driver.id}"))
        
        bot.send_message(
            call.message.chat.id,
            f"Выберите водителя для заказа #{order_id}:",
            reply_markup=markup
        )
        
        session.close()
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("select_driver:") and call.from_user.id == ADMIN_ID)
    def select_driver_callback(call: CallbackQuery):
        """Обработка выбора водителя"""
        parts = call.data.split(":")
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        order_id = int(parts[1])
        driver_id = int(parts[2])
        
        # Назначаем водителя на заказ
        session = Session()
        order = session.query(Order).filter(Order.id == order_id).first()
        driver = session.query(Driver).filter(Driver.id == driver_id).first()
        
        if not order or not driver:
            bot.answer_callback_query(call.id, "Ошибка: заказ или водитель не найден")
            session.close()
            return
        
        # Обновляем заказ
        order.driver_id = driver_id
        order.status = "IN_PROGRESS"
        
        # Обновляем статус водителя
        driver.status = "ON_ORDER"
        
        session.commit()
        
        # Получаем клиента
        client = session.query(User).filter(User.id == order.client_id).first()
        client_id = client.user_id if client else None
        
        # Получаем ID водителя в Telegram
        driver_telegram_id = driver.user_id
        
        session.close()
        
        # Удаляем кнопки из предыдущего сообщения
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
        # Уведомляем администратора
        bot.send_message(
            call.message.chat.id,
            f"✅ Водитель {driver.first_name} ({driver.car_number}) назначен на заказ #{order_id}.",
            reply_markup=get_admin_keyboard()
        )
        
        # Уведомляем клиента
        if client_id:
            client_text = f"🚕 <b>Вам назначен водитель</b>\n\n"
            client_text += f"Заказ #{order_id}\n"
            client_text += f"Водитель: {driver.first_name}\n"
            client_text += f"Автомобиль: {driver.car_number}\n\n"
            client_text += "Водитель скоро прибудет на место посадки."
            
            bot.send_message(
                client_id,
                client_text,
                parse_mode="HTML"
            )
        
        # Уведомляем водителя
        if driver_telegram_id:
            driver_text = f"🆕 <b>Вам назначен новый заказ</b>\n\n"
            driver_text += f"Заказ #{order_id}\n"
            driver_text += f"От: {order.from_address}\n"
            driver_text += f"До: {order.to_address}\n"
            driver_text += f"Цена: {order.price} руб.\n"
            
            if order.comment:
                driver_text += f"Комментарий: {order.comment}\n"
            
            # Добавляем кнопки для управления заказом
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Заказ выполнен", callback_data=f"complete_order:{order_id}"))
            
            bot.send_message(
                driver_telegram_id,
                driver_text,
                parse_mode="HTML",
                reply_markup=markup
            )
    
    @bot.message_handler(func=lambda message: message.text == "👨‍✈️ Управление водителями" and message.from_user.id == ADMIN_ID)
    def manage_drivers(message: Message):
        """Управление водителями"""
        session = Session()
        
        # Получаем заявки на регистрацию водителей
        pending_drivers = session.query(Driver).filter(Driver.is_approved == False).all()
        
        if pending_drivers:
            bot.send_message(
                message.chat.id,
                f"📝 <b>Заявки на регистрацию водителей ({len(pending_drivers)}):</b>",
                parse_mode="HTML"
            )
            
            for driver in pending_drivers:
                driver_text = f"👤 <b>Имя:</b> {driver.first_name}\n"
                driver_text += f"🚗 <b>Госномер:</b> {driver.car_number}\n"
                driver_text += f"📄 <b>Водительское удостоверение:</b> {driver.license_number}\n"
                driver_text += f"📝 <b>ПТС:</b> {driver.car_registration}\n"
                
                # Кнопки для одобрения/отклонения
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_driver:{driver.id}"),
                    types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_driver:{driver.id}")
                )
                
                bot.send_message(
                    message.chat.id,
                    driver_text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
        
        # Получаем активных водителей
        active_drivers = session.query(Driver).filter(Driver.is_approved == True).all()
        
        if active_drivers:
            bot.send_message(
                message.chat.id,
                f"🚕 <b>Активные водители ({len(active_drivers)}):</b>",
                parse_mode="HTML"
            )
            
            for driver in active_drivers:
                driver_info = format_driver_info(driver)
                bot.send_message(
                    message.chat.id,
                    driver_info,
                    parse_mode="HTML"
                )
        
        if not pending_drivers and not active_drivers:
            bot.send_message(
                message.chat.id,
                "Нет водителей для отображения.",
                reply_markup=get_admin_keyboard()
            )
        
        session.close()
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("approve_driver:") and call.from_user.id == ADMIN_ID)
    def approve_driver_callback(call: CallbackQuery):
        """Обработка одобрения водителя"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        driver_id = int(parts[1])
        
        # Одобряем водителя
        session = Session()
        driver = session.query(Driver).filter(Driver.id == driver_id).first()
        
        if not driver:
            bot.answer_callback_query(call.id, "Ошибка: водитель не найден")
            session.close()
            return
        
        driver.is_approved = True
        session.commit()
        
        # Получаем ID водителя в Telegram
        driver_telegram_id = driver.user_id
        
        session.close()
        
        # Удаляем кнопки из предыдущего сообщения
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
        # Уведомляем администратора
        bot.send_message(
            call.message.chat.id,
            f"✅ Водитель {driver.first_name} ({driver.car_number}) одобрен.",
            reply_markup=get_admin_keyboard()
        )
        
        # Уведомляем водителя
        if driver_telegram_id:
            bot.send_message(
                driver_telegram_id,
                "🎉 <b>Поздравляем!</b>\n\n"
                "Ваша заявка на регистрацию в качестве водителя одобрена.\n"
                "Теперь вы можете начать работать. Используйте команду /driver для доступа к меню водителя.",
                parse_mode="HTML"
            )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_driver:") and call.from_user.id == ADMIN_ID)
    def reject_driver_callback(call: CallbackQuery):
        """Обработка отклонения водителя"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        driver_id = int(parts[1])
        
        # Получаем данные о водителе
        session = Session()
        driver = session.query(Driver).filter(Driver.id == driver_id).first()
        
        if not driver:
            bot.answer_callback_query(call.id, "Ошибка: водитель не найден")
            session.close()
            return
        
        # Получаем ID водителя в Telegram
        driver_telegram_id = driver.user_id
        driver_name = driver.first_name
        
        # Удаляем водителя из БД
        session.delete(driver)
        session.commit()
        session.close()
        
        # Удаляем кнопки из предыдущего сообщения
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
        # Уведомляем администратора
        bot.send_message(
            call.message.chat.id,
            f"❌ Заявка водителя {driver_name} отклонена.",
            reply_markup=get_admin_keyboard()
        )
        
        # Уведомляем водителя
        if driver_telegram_id:
            bot.send_message(
                driver_telegram_id,
                "❌ <b>Уведомление</b>\n\n"
                "К сожалению, ваша заявка на регистрацию в качестве водителя отклонена.\n"
                "Для получения дополнительной информации свяжитесь с администрацией.",
                parse_mode="HTML"
            )
    
    @bot.message_handler(func=lambda message: message.text == "📋 История заказов" and message.from_user.id == ADMIN_ID)
    def order_history(message: Message):
        """Показывает историю заказов"""
        session = Session()
        
        # Получаем последние 10 завершенных заказов
        orders = session.query(Order).filter(
            Order.status.in_(["COMPLETED", "CANCELLED"])
        ).order_by(desc(Order.created_at)).limit(10).all()
        
        if not orders:
            bot.send_message(
                message.chat.id,
                "История заказов пуста.",
                reply_markup=get_admin_keyboard()
            )
            session.close()
            return
        
        # Отправляем информацию о каждом заказе
        for order in orders:
            order_text = get_admin_order_view(order)
            bot.send_message(
                message.chat.id,
                order_text,
                parse_mode="HTML"
            )
        
        session.close()
    
    @bot.message_handler(func=lambda message: message.text == "📈 Статистика" and message.from_user.id == ADMIN_ID)
    def show_statistics(message: Message):
        """Показывает статистику"""
        session = Session()
        
        # Общее количество заказов
        total_orders = session.query(Order).count()
        
        # Количество завершенных заказов
        completed_orders = session.query(Order).filter(Order.status == "COMPLETED").count()
        
        # Количество отмененных заказов
        cancelled_orders = session.query(Order).filter(Order.status == "CANCELLED").count()
        
        # Количество активных заказов
        active_orders = session.query(Order).filter(
            Order.status.in_(["NEW", "PRICE_OFFERED", "ACCEPTED", "IN_PROGRESS"])
        ).count()
        
        # Количество клиентов
        total_clients = session.query(User).count()
        
        # Количество водителей
        total_drivers = session.query(Driver).filter(Driver.is_approved == True).count()
        
        # Общая сумма заработка
        total_earnings = session.query(func.sum(Order.price)).filter(Order.status == "COMPLETED").scalar() or 0
        
        # Средняя стоимость поездки
        avg_price = session.query(func.avg(Order.price)).filter(Order.status == "COMPLETED").scalar() or 0
        
        # Заказы за сегодня
        today = datetime.datetime.utcnow().date()
        start_of_day = datetime.datetime.combine(today, datetime.time.min)
        orders_today = session.query(Order).filter(Order.created_at >= start_of_day).count()
        
        # Заказы за текущий месяц
        start_of_month = datetime.datetime(today.year, today.month, 1)
        orders_month = session.query(Order).filter(Order.created_at >= start_of_month).count()
        
        session.close()
        
        # Формируем сообщение со статистикой
        stats_text = f"📊 <b>Статистика</b>\n\n"
        stats_text += f"<b>Заказы:</b>\n"
        stats_text += f"Всего заказов: {total_orders}\n"
        stats_text += f"Завершенных: {completed_orders}\n"
        stats_text += f"Отмененных: {cancelled_orders}\n"
        stats_text += f"Активных: {active_orders}\n"
        stats_text += f"За сегодня: {orders_today}\n"
        stats_text += f"За месяц: {orders_month}\n\n"
        
        stats_text += f"<b>Пользователи:</b>\n"
        stats_text += f"Клиентов: {total_clients}\n"
        stats_text += f"Водителей: {total_drivers}\n\n"
        
        stats_text += f"<b>Финансы:</b>\n"
        stats_text += f"Общий доход: {total_earnings:.2f} руб.\n"
        stats_text += f"Средняя стоимость поездки: {avg_price:.2f} руб.\n"
        
        bot.send_message(
            message.chat.id,
            stats_text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("complete_order:"))
    def complete_order_callback(call: CallbackQuery):
        """Обработка завершения заказа водителем"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки")
            return
        
        order_id = int(parts[1])
        
        # Получаем данные о заказе
        session = Session()
        order = session.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
            session.close()
            return
        
        # Проверяем, что заказ назначен на этого водителя
        driver = session.query(Driver).filter(Driver.user_id == call.from_user.id).first()
        
        if not driver or driver.id != order.driver_id:
            bot.answer_callback_query(call.id, "Ошибка: заказ не назначен на вас")
            session.close()
            return
        
        # Обновляем статус заказа
        order.status = "COMPLETED"
        order.completed_at = datetime.datetime.utcnow()
        
        # Обновляем статус водителя
        driver.status = "ON_DUTY"
        
        # Добавляем запись о заработке
        earning = Earning(
            driver_id=driver.id,
            order_id=order.id,
            amount=order.price
        )
        
        session.add(earning)
        session.commit()
        
        # Получаем клиента
        client = session.query(User).filter(User.id == order.client_id).first()
        client_id = client.user_id if client else None
        
        session.close()
        
        # Удаляем кнопки из предыдущего сообщения
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
        # Уведомляем водителя
        bot.send_message(
            call.message.chat.id,
            f"✅ Заказ #{order_id} успешно завершен.\n"
            f"Сумма {order.price} руб. добавлена к вашему заработку.",
            reply_markup=get_driver_keyboard()
        )
        
        # Уведомляем клиента и предлагаем оценить поездку
        if client_id:
            from app.keyboards import get_rating_keyboard
            
            client_text = f"✅ <b>Поездка завершена</b>\n\n"
            client_text += f"Заказ #{order_id} выполнен.\n"
            client_text += f"Спасибо за использование нашего сервиса!\n\n"
            client_text += "Пожалуйста, оцените поездку:"
            
            bot.send_message(
                client_id,
                client_text,
                parse_mode="HTML",
                reply_markup=get_rating_keyboard(order_id)
            )
        
        # Уведомляем админа
        bot.send_message(
            ADMIN_ID,
            f"✅ Заказ #{order_id} завершен водителем {driver.first_name} ({driver.car_number}).\n"
            f"Сумма: {order.price} руб."
        )
