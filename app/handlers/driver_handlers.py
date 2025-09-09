from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from app.keyboards import get_main_keyboard, get_driver_keyboard, get_driver_status_keyboard
from app.utils import get_user_by_id, get_driver_by_id, format_order_info, format_driver_info
from app.database import Session, User, Driver, Order, Earning
from config import ADMIN_ID, DRIVER_STATUSES
import json
import datetime

# Словарь для хранения временных данных регистрации водителя
driver_registration_data = {}

def register_driver_handlers(bot: TeleBot):
    """Регистрация обработчиков для водителей"""
    
    @bot.message_handler(commands=['driver'])
    def driver_command(message: Message):
        """Обработчик команды /driver"""
        user_id = message.from_user.id
        
        # Проверяем, зарегистрирован ли пользователь как водитель
        driver = get_driver_by_id(user_id)
        
        if driver:
            if driver.is_approved:
                # Если водитель уже одобрен, показываем меню водителя
                bot.send_message(
                    message.chat.id,
                    f"Здравствуйте, {driver.first_name}!\n"
                    f"Вы авторизованы как водитель.",
                    reply_markup=get_driver_keyboard()
                )
            else:
                # Если водитель еще не одобрен
                bot.send_message(
                    message.chat.id,
                    "Ваша заявка на регистрацию в качестве водителя находится на рассмотрении.\n"
                    "Пожалуйста, ожидайте решения администратора."
                )
        else:
            # Если пользователь еще не зарегистрирован как водитель
            bot.send_message(
                message.chat.id,
                "Для работы водителем необходимо зарегистрироваться.\n"
                "Хотите начать регистрацию?"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Да, начать регистрацию", callback_data="start_driver_reg"))
            markup.add(types.InlineKeyboardButton("❌ Нет", callback_data="cancel_driver_reg"))
            
            bot.send_message(
                message.chat.id,
                "Выберите действие:",
                reply_markup=markup
            )
    
    @bot.callback_query_handler(func=lambda call: call.data == "start_driver_reg")
    def start_driver_registration(call: CallbackQuery):
        """Начало регистрации водителя"""
        user_id = call.from_user.id
        
        # Инициализируем данные регистрации
        driver_registration_data[user_id] = {}
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Начинаем регистрацию водителя.\n\n"
                 "Пожалуйста, введите ваше полное имя:",
            reply_markup=None
        )
        
        bot.register_next_step_handler(call.message, process_driver_name)
    
    @bot.callback_query_handler(func=lambda call: call.data == "cancel_driver_reg")
    def cancel_driver_registration(call: CallbackQuery):
        """Отмена регистрации водителя"""
        user_id = call.from_user.id
        
        # Удаляем данные регистрации, если они есть
        if user_id in driver_registration_data:
            del driver_registration_data[user_id]
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Регистрация отменена.",
            reply_markup=None
        )
        
        bot.send_message(
            call.message.chat.id,
            "Вы можете вернуться в главное меню.",
            reply_markup=get_main_keyboard()
        )
    
    def process_driver_name(message: Message):
        """Обработка имени водителя"""
        user_id = message.from_user.id
        name = message.text
        
        if not name:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректное имя.")
            bot.register_next_step_handler(message, process_driver_name)
            return
        
        # Сохраняем имя
        driver_registration_data[user_id]['first_name'] = name
        
        # Запрашиваем номер водительского удостоверения
        bot.send_message(
            message.chat.id,
            "Введите номер вашего водительского удостоверения:"
        )
        bot.register_next_step_handler(message, process_driver_license)
    
    def process_driver_license(message: Message):
        """Обработка номера водительского удостоверения"""
        user_id = message.from_user.id
        license_number = message.text
        
        if not license_number:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректный номер удостоверения.")
            bot.register_next_step_handler(message, process_driver_license)
            return
        
        # Сохраняем номер удостоверения
        driver_registration_data[user_id]['license_number'] = license_number
        
        # Запрашиваем данные ПТС
        bot.send_message(
            message.chat.id,
            "Введите данные ПТС автомобиля (серия и номер):"
        )
        bot.register_next_step_handler(message, process_car_registration)
    
    def process_car_registration(message: Message):
        """Обработка данных ПТС"""
        user_id = message.from_user.id
        car_registration = message.text
        
        if not car_registration:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректные данные ПТС.")
            bot.register_next_step_handler(message, process_car_registration)
            return
        
        # Сохраняем данные ПТС
        driver_registration_data[user_id]['car_registration'] = car_registration
        
        # Запрашиваем госномер автомобиля
        bot.send_message(
            message.chat.id,
            "Введите госномер автомобиля:"
        )
        bot.register_next_step_handler(message, process_car_number)
    
    def process_car_number(message: Message):
        """Обработка госномера автомобиля"""
        user_id = message.from_user.id
        car_number = message.text
        
        if not car_number:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректный госномер.")
            bot.register_next_step_handler(message, process_car_number)
            return
        
        # Сохраняем госномер
        driver_registration_data[user_id]['car_number'] = car_number
        
        # Запрашиваем фото автомобиля спереди
        bot.send_message(
            message.chat.id,
            "Пожалуйста, отправьте фото автомобиля спереди:"
        )
        bot.register_next_step_handler(message, process_front_photo)
    
    def process_front_photo(message: Message):
        """Обработка фото автомобиля спереди"""
        user_id = message.from_user.id
        
        # Проверяем, что сообщение содержит фото
        if not message.photo:
            bot.send_message(message.chat.id, "Пожалуйста, отправьте фото автомобиля.")
            bot.register_next_step_handler(message, process_front_photo)
            return
        
        # Получаем фото наибольшего размера
        photo = message.photo[-1]
        file_id = photo.file_id
        
        # Инициализируем массив фото, если его еще нет
        if 'car_photos' not in driver_registration_data[user_id]:
            driver_registration_data[user_id]['car_photos'] = []
        
        # Сохраняем file_id фото
        driver_registration_data[user_id]['car_photos'].append({
            'position': 'front',
            'file_id': file_id
        })
        
        # Запрашиваем фото автомобиля сзади
        bot.send_message(
            message.chat.id,
            "Пожалуйста, отправьте фото автомобиля сзади:"
        )
        bot.register_next_step_handler(message, process_back_photo)
    
    def process_back_photo(message: Message):
        """Обработка фото автомобиля сзади"""
        user_id = message.from_user.id
        
        # Проверяем, что сообщение содержит фото
        if not message.photo:
            bot.send_message(message.chat.id, "Пожалуйста, отправьте фото автомобиля.")
            bot.register_next_step_handler(message, process_back_photo)
            return
        
        # Получаем фото наибольшего размера
        photo = message.photo[-1]
        file_id = photo.file_id
        
        # Сохраняем file_id фото
        driver_registration_data[user_id]['car_photos'].append({
            'position': 'back',
            'file_id': file_id
        })
        
        # Запрашиваем фото автомобиля слева
        bot.send_message(
            message.chat.id,
            "Пожалуйста, отправьте фото автомобиля слева:"
        )
        bot.register_next_step_handler(message, process_left_photo)
    
    def process_left_photo(message: Message):
        """Обработка фото автомобиля слева"""
        user_id = message.from_user.id
        
        # Проверяем, что сообщение содержит фото
        if not message.photo:
            bot.send_message(message.chat.id, "Пожалуйста, отправьте фото автомобиля.")
            bot.register_next_step_handler(message, process_left_photo)
            return
        
        # Получаем фото наибольшего размера
        photo = message.photo[-1]
        file_id = photo.file_id
        
        # Сохраняем file_id фото
        driver_registration_data[user_id]['car_photos'].append({
            'position': 'left',
            'file_id': file_id
        })
        
        # Запрашиваем фото автомобиля справа
        bot.send_message(
            message.chat.id,
            "Пожалуйста, отправьте фото автомобиля справа:"
        )
        bot.register_next_step_handler(message, process_right_photo)
    
    def process_right_photo(message: Message):
        """Обработка фото автомобиля справа"""
        user_id = message.from_user.id
        
        # Проверяем, что сообщение содержит фото
        if not message.photo:
            bot.send_message(message.chat.id, "Пожалуйста, отправьте фото автомобиля.")
            bot.register_next_step_handler(message, process_right_photo)
            return
        
        # Получаем фото наибольшего размера
        photo = message.photo[-1]
        file_id = photo.file_id
        
        # Сохраняем file_id фото
        driver_registration_data[user_id]['car_photos'].append({
            'position': 'right',
            'file_id': file_id
        })
        
        # Завершаем регистрацию
        complete_driver_registration(message)
    
    def complete_driver_registration(message: Message):
        """Завершение регистрации водителя"""
        user_id = message.from_user.id
        
        # Получаем все данные регистрации
        reg_data = driver_registration_data.get(user_id, {})
        
        if not reg_data:
            bot.send_message(message.chat.id, "Ошибка: данные регистрации не найдены.")
            return
        
        # Создаем запись о водителе в БД
        session = Session()
        
        # Преобразуем массив фотографий в JSON строку
        car_photos_json = json.dumps(reg_data.get('car_photos', []))
        
        new_driver = Driver(
            user_id=user_id,
            first_name=reg_data.get('first_name', ''),
            license_number=reg_data.get('license_number', ''),
            car_registration=reg_data.get('car_registration', ''),
            car_number=reg_data.get('car_number', ''),
            car_photos=car_photos_json,
            status="OFF_DUTY",
            is_approved=False
        )
        
        session.add(new_driver)
        session.commit()
        session.close()
        
        # Очищаем временные данные
        if user_id in driver_registration_data:
            del driver_registration_data[user_id]
        
        # Уведомляем пользователя
        bot.send_message(
            message.chat.id,
            "✅ Ваша заявка на регистрацию в качестве водителя успешно отправлена!\n\n"
            "Администратор рассмотрит вашу заявку в ближайшее время.\n"
            "Вы получите уведомление, когда заявка будет одобрена.",
            reply_markup=get_main_keyboard()
        )
        
        # Уведомляем админа о новой заявке
        admin_text = f"🆕 <b>Новая заявка на регистрацию водителя</b>\n\n"
        admin_text += f"👤 <b>Имя:</b> {reg_data.get('first_name', '')}\n"
        admin_text += f"🚗 <b>Госномер:</b> {reg_data.get('car_number', '')}\n"
        admin_text += f"📄 <b>Водительское удостоверение:</b> {reg_data.get('license_number', '')}\n"
        admin_text += f"📝 <b>ПТС:</b> {reg_data.get('car_registration', '')}\n"
        
        bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="HTML"
        )
        
        # Отправляем фотографии автомобиля админу
        for photo in reg_data.get('car_photos', []):
            caption = f"Фото автомобиля: {photo.get('position', '')}"
            bot.send_photo(ADMIN_ID, photo.get('file_id', ''), caption=caption)
    
    @bot.message_handler(func=lambda message: message.text == "🚗 Изменить статус")
    def change_driver_status(message: Message):
        """Обработчик изменения статуса водителя"""
        user_id = message.from_user.id
        
        # Проверяем, зарегистрирован ли пользователь как водитель
        driver = get_driver_by_id(user_id)
        
        if not driver:
            bot.send_message(
                message.chat.id,
                "Вы не зарегистрированы как водитель.",
                reply_markup=get_main_keyboard()
            )
            return
        
        if not driver.is_approved:
            bot.send_message(
                message.chat.id,
                "Ваша заявка на регистрацию еще не одобрена администратором.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Показываем текущий статус и предлагаем изменить
        current_status = DRIVER_STATUSES.get(driver.status, driver.status)
        
        bot.send_message(
            message.chat.id,
            f"Ваш текущий статус: <b>{current_status}</b>\n\n"
            f"Выберите новый статус:",
            parse_mode="HTML",
            reply_markup=get_driver_status_keyboard()
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("status:"))
    def process_status_change(call: CallbackQuery):
        """Обработка изменения статуса водителя"""
        parts = call.data.split(":")
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "Ошибка обработки статуса")
            return
        
        status = parts[1]
        user_id = call.from_user.id
        
        # Обновляем статус водителя в БД
        session = Session()
        driver = session.query(Driver).filter(Driver.user_id == user_id).first()
        
        if not driver:
            bot.answer_callback_query(call.id, "Ошибка: водитель не найден")
            session.close()
            return
        
        old_status = driver.status
        driver.status = status
        session.commit()
        session.close()
        
        # Уведомляем водителя
        new_status_text = DRIVER_STATUSES.get(status, status)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Ваш статус изменен на: <b>{new_status_text}</b>",
            parse_mode="HTML",
            reply_markup=None
        )
        
        # Уведомляем админа
        old_status_text = DRIVER_STATUSES.get(old_status, old_status)
        admin_text = f"🔄 <b>Изменение статуса водителя</b>\n\n"
        admin_text += f"👤 <b>Водитель:</b> {driver.first_name}\n"
        admin_text += f"🚗 <b>Госномер:</b> {driver.car_number}\n"
        admin_text += f"📊 <b>Статус:</b> {old_status_text} ➡️ {new_status_text}"
        
        bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="HTML"
        )
    
    @bot.message_handler(func=lambda message: message.text == "📋 Мои заказы")
    def driver_orders(message: Message):
        """Показывает заказы водителя"""
        user_id = message.from_user.id
        
        # Проверяем, зарегистрирован ли пользователь как водитель
        driver = get_driver_by_id(user_id)
        
        if not driver:
            bot.send_message(
                message.chat.id,
                "Вы не зарегистрированы как водитель.",
                reply_markup=get_main_keyboard()
            )
            return
        
        if not driver.is_approved:
            bot.send_message(
                message.chat.id,
                "Ваша заявка на регистрацию еще не одобрена администратором.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Получаем заказы водителя
        session = Session()
        orders = session.query(Order).filter(Order.driver_id == driver.id).order_by(Order.created_at.desc()).limit(5).all()
        
        if not orders:
            bot.send_message(
                message.chat.id,
                "У вас пока нет заказов.",
                reply_markup=get_driver_keyboard()
            )
            session.close()
            return
        
        # Отправляем информацию о каждом заказе
        for order in orders:
            order_text = format_order_info(order)
            bot.send_message(
                message.chat.id,
                order_text,
                parse_mode="HTML"
            )
        
        session.close()
    
    @bot.message_handler(func=lambda message: message.text == "💰 Мой заработок")
    def driver_earnings(message: Message):
        """Показывает заработок водителя"""
        user_id = message.from_user.id
        
        # Проверяем, зарегистрирован ли пользователь как водитель
        driver = get_driver_by_id(user_id)
        
        if not driver:
            bot.send_message(
                message.chat.id,
                "Вы не зарегистрированы как водитель.",
                reply_markup=get_main_keyboard()
            )
            return
        
        if not driver.is_approved:
            bot.send_message(
                message.chat.id,
                "Ваша заявка на регистрацию еще не одобрена администратором.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Получаем заработок водителя
        session = Session()
        
        # Общий заработок
        total_earnings = session.query(func.sum(Earning.amount)).filter(Earning.driver_id == driver.id).scalar() or 0
        
        # Заработок за текущий месяц
        now = datetime.datetime.utcnow()
        start_of_month = datetime.datetime(now.year, now.month, 1)
        monthly_earnings = session.query(func.sum(Earning.amount)).filter(
            Earning.driver_id == driver.id,
            Earning.date >= start_of_month
        ).scalar() or 0
        
        # Заработок за текущую неделю
        today = now.date()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        start_of_week = datetime.datetime.combine(start_of_week, datetime.time.min)
        weekly_earnings = session.query(func.sum(Earning.amount)).filter(
            Earning.driver_id == driver.id,
            Earning.date >= start_of_week
        ).scalar() or 0
        
        # Заработок за сегодня
        start_of_day = datetime.datetime.combine(today, datetime.time.min)
        daily_earnings = session.query(func.sum(Earning.amount)).filter(
            Earning.driver_id == driver.id,
            Earning.date >= start_of_day
        ).scalar() or 0
        
        session.close()
        
        # Формируем сообщение
        earnings_text = f"💰 <b>Ваш заработок</b>\n\n"
        earnings_text += f"Сегодня: {daily_earnings} руб.\n"
        earnings_text += f"За неделю: {weekly_earnings} руб.\n"
        earnings_text += f"За месяц: {monthly_earnings} руб.\n"
        earnings_text += f"Всего: {total_earnings} руб."
        
        bot.send_message(
            message.chat.id,
            earnings_text,
            parse_mode="HTML",
            reply_markup=get_driver_keyboard()
        )
