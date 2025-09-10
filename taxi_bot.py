# Функция driver_arrived_callback перенесена ниже после создания bot

import telebot
import logging
import os
import sys
import sqlite3
import json
import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Импортируем конфигурацию
from config import BOT_TOKEN, ADMIN_ID, ADMIN_IDS, POPULAR_DESTINATIONS, CITY_NAME, CITY_RADIUS, DRIVER_STATUSES

# Функция для проверки прав администратора
def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    if user_id in ADMIN_IDS:
        return True
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except Exception:
        return False

# Функция для отправки сообщения всем администраторам
def send_to_admins(text, parse_mode=None, reply_markup=None):
    """Отправляет сообщение всем администраторам"""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу {admin_id}: {e}")

# Функция для отправки фото всем администраторам
def send_photo_to_admins(photo, caption=None):
    """Отправляет фото всем администраторам"""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_photo(admin_id, photo, caption=caption)
        except Exception as e:
            logger.error(f"Ошибка отправки фото админу {admin_id}: {e}")

# Создание базы данных SQLite
def init_db():
    conn = sqlite3.connect('taxi.db')
    cursor = conn.cursor()
    
    # Создаем таблицу пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        phone_number TEXT,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Создаем таблицу водителей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        license_number TEXT NOT NULL,
        car_registration TEXT NOT NULL,
        car_number TEXT NOT NULL,
        car_photos TEXT,
        status TEXT DEFAULT 'OFF_DUTY',
        is_approved INTEGER DEFAULT 0,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Создаем таблицу заказов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        driver_id INTEGER,
        from_address TEXT NOT NULL,
        to_address TEXT NOT NULL,
        scheduled_at TEXT,
        payment_method TEXT,
        comment TEXT,
        price REAL,
        counter_offer REAL,
        status TEXT DEFAULT 'NEW',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES users (id),
        FOREIGN KEY (driver_id) REFERENCES drivers (id)
    )
    ''')
    
    # Миграция: добавляем столбец payment_method, если отсутствует (для существующих БД)
    try:
        cursor.execute("PRAGMA table_info(orders)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'payment_method' not in cols:
            cursor.execute('ALTER TABLE orders ADD COLUMN payment_method TEXT')
        if 'scheduled_at' not in cols:
            cursor.execute('ALTER TABLE orders ADD COLUMN scheduled_at TEXT')
    except Exception as e:
        logger.error(f"Ошибка миграции orders.payment_method: {e}")
    
    # Таблица администраторов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        first_name TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Создаем таблицу отзывов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER UNIQUE,
        client_id INTEGER,
        driver_id INTEGER,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (client_id) REFERENCES users (id),
        FOREIGN KEY (driver_id) REFERENCES drivers (id)
    )
    ''')
    
    # Создаем таблицу заработка
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS earnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER,
        order_id INTEGER UNIQUE,
        amount REAL NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (driver_id) REFERENCES drivers (id),
        FOREIGN KEY (order_id) REFERENCES orders (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# Функции для работы с базой данных
def get_db_connection():
    conn = sqlite3.connect('taxi.db')
    conn.row_factory = sqlite3.Row
    return conn

def save_user_data(user_id, username, first_name, last_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем, существует ли пользователь
    cursor.execute('SELECT id FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        # Создаем нового пользователя
        cursor.execute(
            'INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
            (user_id, username, first_name, last_name)
        )
        conn.commit()
        cursor.execute('SELECT id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
    else:
        # Обновляем данные пользователя
        cursor.execute(
            'UPDATE users SET username = ?, first_name = ?, last_name = ? WHERE user_id = ?',
            (username, first_name, last_name, user_id)
        )
        conn.commit()
    
    user_id = user['id']
    conn.close()
    return user_id

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_driver_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM drivers WHERE user_id = ?', (user_id,))
    driver = cursor.fetchone()
    conn.close()
    return driver

# Создание клавиатур
def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🚕 Заказать предварительно такси"))
    markup.add(telebot.types.KeyboardButton("📝 Мои заказы"), telebot.types.KeyboardButton("🤝 Стать нашим партнером"))
    markup.add(telebot.types.KeyboardButton("📞 Связаться с нами"))
    return markup

def get_admin_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("📊 Активные заказы"))
    markup.add(telebot.types.KeyboardButton("👨‍✈️ Управление водителями"), telebot.types.KeyboardButton("📋 История заказов"))
    markup.add(telebot.types.KeyboardButton("📈 Статистика"), telebot.types.KeyboardButton("🗑️ Очистить заказы"))
    markup.add(telebot.types.KeyboardButton("➕ Добавить администратора"))
    markup.add(telebot.types.KeyboardButton("🔙 Главное меню"))
    return markup

def get_driver_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🚗 Изменить статус"), telebot.types.KeyboardButton("📍 На месте"))
    markup.add(telebot.types.KeyboardButton("📋 Мои заказы"), telebot.types.KeyboardButton("💰 Мой заработок"))
    markup.add(telebot.types.KeyboardButton("🔙 Главное меню"))
    return markup

def get_popular_destinations_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for destination in POPULAR_DESTINATIONS:
        markup.add(telebot.types.KeyboardButton(destination))
    markup.add(telebot.types.KeyboardButton("✏️ Ввести другой адрес"))
    markup.add(telebot.types.KeyboardButton("🔙 Назад"))
    return markup

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith("driver_arrived:"))
def driver_arrived_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    user_id = call.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    if not order:
        bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
        conn.close()
        return
    
    driver = get_driver_by_id(user_id)
    if not driver or driver['id'] != order['driver_id']:
        bot.answer_callback_query(call.id, "Ошибка: заказ не назначен на вас")
        conn.close()
        return
    
    # Обновляем статус водителя на ARRIVED
    cursor.execute('UPDATE drivers SET status = ? WHERE id = ?', ('ARRIVED', driver['id']))
    conn.commit()
    
    # Уведомляем клиента о прибытии
    cursor.execute('SELECT user_id FROM users WHERE id = ?', (order['client_id'],))
    client = cursor.fetchone()
    client_user_id = client['user_id'] if client else None
    conn.close()
    
    # Снимаем кнопки прежнего сообщения
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
    
    if client_user_id:
        try:
            bot.send_message(client_user_id, "🚗 Водитель прибыл на точку А. Подходите, пожалуйста.")
        except Exception as e:
            logger.error(f"Ошибка уведомления клиента о прибытии: {e}")
    
    # Отправляем водителю сообщение о начале поездки с кнопкой завершения
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Заказ выполнен", callback_data=f"complete_order:{order_id}"))
    bot.send_message(call.message.chat.id, "▶️ Поездка началась. Нажмите, когда заказ будет выполнен.", reply_markup=markup)

# Временное хранилище данных
user_order_data = {}
driver_registration_data = {}

# Обработчики команд
@bot.message_handler(commands=['start'])
def start_command(message):
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

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "🚕 <b>Такси Светлогорск39</b> - бот для заказа такси\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать справку\n"
        "/order - Заказать такси\n"
        "/profile - Ваш профиль\n"
        "/driver - Меню водителя\n"
        "/admin - Админ-панель (только для администраторов)\n\n"
        "Для заказа такси нажмите кнопку 'Заказать такси' в меню.",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['admin'])
def admin_command(message):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
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

@bot.message_handler(commands=['order'])
@bot.message_handler(func=lambda message: message.text == "🚕 Заказать предварительно такси")
def order_taxi(message):
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
    
    # Новый шаг: дата и время
    bot.send_message(
        message.chat.id,
        "Укажите дату и время подачи такси (например: 10.09 14:30):",
        reply_markup=None
    )
    bot.register_next_step_handler(message, process_schedule_datetime)

def process_schedule_datetime(message):
    user_id = message.from_user.id
    text = message.text.strip()
    # Примем формат DD.MM HH:MM
    try:
        # Подставим текущий год
        now = datetime.datetime.now()
        day, rest = text.split('.')
        month, time_part = rest.split(' ')
        hours, minutes = time_part.split(':')
        dt = datetime.datetime(year=now.year, month=int(month), day=int(day), hour=int(hours), minute=int(minutes))
        if dt < now:
            raise ValueError('past')
    except Exception:
        bot.send_message(message.chat.id, "Неверный формат. Пример: 10.09 14:30. Повторите ввод:")
        bot.register_next_step_handler(message, process_schedule_datetime)
        return
    
    user_order_data.setdefault(user_id, {})['scheduled_at'] = dt.isoformat()
    
    # Далее точка А: только ручной ввод
    bot.send_message(message.chat.id, "Точка А должна быть в Светлогорске (и 10 км). Введите корректный адрес:")
    bot.register_next_step_handler(message, process_manual_from_address)

def process_preorder_destination(message):
    user_id = message.from_user.id
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отмена.", reply_markup=get_main_keyboard())
        return
    
    if message.text not in POPULAR_DESTINATIONS:
        bot.send_message(message.chat.id, "Пожалуйста, выберите один из предложенных вариантов.")
        bot.register_next_step_handler(message, process_preorder_destination)
        return
    
    user_order_data[user_id]['to_address'] = message.text
    
    # Адрес отправления (точка А) вручную
    bot.send_message(message.chat.id, "Введите адрес отправления (улица и дом):", reply_markup=None)
    bot.register_next_step_handler(message, process_preorder_from_address)

def process_preorder_from_address(message):
    user_id = message.from_user.id
    from_address = message.text.strip()
    if not from_address:
        bot.send_message(message.chat.id, "Адрес не должен быть пустым. Введите адрес отправления:")
        bot.register_next_step_handler(message, process_preorder_from_address)
        return
    
    if CITY_NAME.lower() not in from_address.lower():
        bot.send_message(message.chat.id, "Точка А должна быть в Светлогорске (и 10 км). Введите корректный адрес:")
        bot.register_next_step_handler(message, process_preorder_from_address)
        return
    
    user_order_data[user_id]['from_address'] = from_address
    
    # Комментарий
    bot.send_message(message.chat.id, "Добавьте комментарий (или '-' если не нужно):")
    bot.register_next_step_handler(message, process_preorder_comment)

def process_preorder_comment(message):
    user_id = message.from_user.id
    comment = message.text.strip()
    if comment == '-':
        comment = None
    user_order_data[user_id]['comment'] = comment
    
    # Способ оплаты
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(telebot.types.KeyboardButton("💵 Наличные"), telebot.types.KeyboardButton("💳 Перевод на карту"))
    bot.send_message(message.chat.id, "Выберите способ оплаты:", reply_markup=markup)
    bot.register_next_step_handler(message, process_preorder_payment)

def process_preorder_payment(message):
    user_id = message.from_user.id
    pm = message.text
    if pm not in ["💵 Наличные", "💳 Перевод на карту"]:
        bot.send_message(message.chat.id, "Выберите один из вариантов оплаты.")
        bot.register_next_step_handler(message, process_preorder_payment)
        return
    
    payment_method = 'CASH' if pm == "💵 Наличные" else 'CARD'
    user_order_data[user_id]['payment_method'] = payment_method
    
    # Подтверждение заказа
    data = user_order_data[user_id]
    text = (
        "Проверьте детали предзаказа:\n\n"
        f"Откуда: {data['from_address']}\n"
        f"Куда: {data['to_address']}\n"
        f"Когда: {datetime.datetime.fromisoformat(data['scheduled_at']).strftime('%d.%m %H:%M')}\n"
        f"Оплата: {'Наличные' if payment_method=='CASH' else 'Перевод на карту'}\n"
        f"Комментарий: {data.get('comment') or '—'}\n\n"
        "Подтвердить заказ?"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_preorder"),
        telebot.types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_preorder")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ("confirm_preorder","cancel_preorder"))
def confirm_preorder_callback(call):
    user_id = call.from_user.id
    if call.data == 'cancel_preorder':
        bot.edit_message_text("Заказ отменен.", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Возвращаемся в меню.", reply_markup=get_main_keyboard())
        user_order_data.pop(user_id, None)
        return
    
    data = user_order_data.get(user_id)
    if not data:
        bot.answer_callback_query(call.id, "Данные заказа не найдены")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE user_id = ?', (user_id,))
    u = cursor.fetchone()
    if not u:
        conn.close()
        bot.answer_callback_query(call.id, "Пользователь не найден")
        return
    
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ?', (u['id'],))
    client_order_number = cursor.fetchone()[0] + 1
    
    cursor.execute(
        'INSERT INTO orders (client_id, from_address, to_address, payment_method, comment, status, scheduled_at) VALUES (?,?,?,?,?,?,?)',
        (u['id'], data['from_address'], data['to_address'], data.get('payment_method'), data.get('comment'), 'NEW', data.get('scheduled_at'))
    )
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    
    bot.edit_message_text(
        f"✅ Предварительный заказ #{client_order_number} создан. Ожидайте цены.",
        call.message.chat.id,
        call.message.message_id
    )
    bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=get_main_keyboard())
    
    # Админам
    admin_text = (
        f"🆕 <b>Новый предзаказ #{client_order_number}</b> (ID: {order_id})\n\n"
        f"Откуда: {data['from_address']}\n"
        f"Куда: {data['to_address']}\n"
        f"Когда: {datetime.datetime.fromisoformat(data['scheduled_at']).strftime('%d.%m %H:%M')}\n"
        f"Оплата: {'Наличные' if data.get('payment_method')=='CASH' else 'Перевод на карту'}\n"
        f"Комментарий: {data.get('comment') or '—'}"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("💰 Установить цену", callback_data=f"set_price:{order_id}"))
    send_to_admins(admin_text, parse_mode="HTML", reply_markup=markup)
    
    user_order_data.pop(user_id, None)

def process_from_address(message):
    user_id = message.from_user.id
    
    # Проверяем, не выбрал ли пользователь "Назад"
    if message.text == "🔙 Назад":
        bot.send_message(
            message.chat.id,
            "Заказ отменен.",
            reply_markup=get_main_keyboard()
        )
        return
    
    if message.text == "✏️ Ввести адрес вручную":
        # Запрашиваем ввод адреса вручную
        bot.send_message(
            message.chat.id,
            "Введите адрес отправления:",
            reply_markup=None
        )
        bot.register_next_step_handler(message, process_manual_from_address)
        return
        
    else:
        from_address = message.text
        
        # Проверяем, что адрес в пределах города (упрощенная проверка)
        if CITY_NAME.lower() not in from_address.lower():
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(telebot.types.KeyboardButton("✏️ Ввести адрес вручную"))
            markup.add(telebot.types.KeyboardButton("🔙 Назад"))
            
            bot.send_message(
                message.chat.id,
                "К сожалению, указанный адрес находится за пределами зоны обслуживания.\n"
                "Мы работаем только в г. Светлогорск и в радиусе 10 км.\n\n"
                "Пожалуйста, попробуйте еще раз:",
                reply_markup=markup
            )
            # Повторно регистрируем обработчик для ввода адреса
            bot.register_next_step_handler(message, process_from_address)
            return
        
        # Сохраняем адрес отправления
        user_order_data[user_id]['from_address'] = from_address
    
    # Запрашиваем адрес назначения
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for destination in POPULAR_DESTINATIONS:
        markup.add(telebot.types.KeyboardButton(destination))
    markup.add(telebot.types.KeyboardButton("✏️ Ввести другой адрес"))
    markup.add(telebot.types.KeyboardButton("🔙 Назад"))
    
    bot.send_message(
        message.chat.id,
        "Теперь укажите адрес назначения (точка Б):",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, process_to_address)

def process_manual_from_address(message):
    """Обработка ручного ввода адреса отправления"""
    user_id = message.from_user.id
    from_address = message.text
    
    # Проверяем, что адрес в пределах города
    if CITY_NAME.lower() not in from_address.lower():
        bot.send_message(
            message.chat.id,
            "К сожалению, указанный адрес находится за пределами зоны обслуживания.\n"
            "Пожалуйста, введите корректный адрес отправления:"
        )
        bot.register_next_step_handler(message, process_manual_from_address)
        return
    
    # Сохраняем адрес отправления
    user_order_data[user_id]['from_address'] = from_address
    
    # Теперь выбор направления для точки Б
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for destination in POPULAR_DESTINATIONS:
        markup.add(telebot.types.KeyboardButton(destination))
    markup.add(telebot.types.KeyboardButton("✏️ Ввести другой адрес"))
    markup.add(telebot.types.KeyboardButton("🔙 Назад"))
    bot.send_message(message.chat.id, "Выберите направление (точка Б) или введите другой адрес:", reply_markup=markup)
    bot.register_next_step_handler(message, process_to_address)

def process_to_address(message):
    user_id = message.from_user.id
    
    # Проверяем, не выбрал ли пользователь "Назад"
    if message.text == "🔙 Назад":
        order_taxi(message)
        return
    
    if message.text == "✏️ Ввести другой адрес":
        bot.send_message(
            message.chat.id,
            "Пожалуйста, введите адрес назначения:",
            reply_markup=None
        )
        bot.register_next_step_handler(message, process_custom_to_address)
        return
    
    # Если пользователь выбрал город из списка
    if message.text in POPULAR_DESTINATIONS:
        to_city = message.text
        user_order_data[user_id]['to_city'] = to_city
        
        # Для аэропорта не спрашиваем адрес - он один
        if "Аэропорт" in message.text:
            user_order_data[user_id]['to_address'] = message.text
            # Переходим сразу к комментарию
            bot.send_message(message.chat.id, "Добавьте комментарий к заказу (необязательно). Если не нужен, отправьте '-':", reply_markup=None)
            bot.register_next_step_handler(message, process_preorder_comment)
            return
        
        bot.send_message(
            message.chat.id,
            f"Введите улицу и дом в пункте назначения ({to_city}):",
            reply_markup=None
        )
        bot.register_next_step_handler(message, process_to_city_street)
        return
    
    # Иначе просим выбрать город из списка
    bot.send_message(message.chat.id, "Пожалуйста, выберите город назначения кнопкой или введите другой адрес.")
    bot.register_next_step_handler(message, process_to_address)
    return
    
    # Комментарий
    bot.send_message(message.chat.id, "Добавьте комментарий к заказу (необязательно). Если не нужен, отправьте '-':", reply_markup=None)
    bot.register_next_step_handler(message, process_preorder_comment)

def process_custom_to_address(message):
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
    bot.register_next_step_handler(message, process_preorder_comment)

def process_to_city_street(message):
    user_id = message.from_user.id
    street = message.text.strip()
    to_city = user_order_data.get(user_id, {}).get('to_city')
    if not to_city:
        bot.send_message(message.chat.id, "Произошла ошибка выбора города. Повторите выбор.")
        # Вернемся к выбору города
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        for destination in POPULAR_DESTINATIONS:
            markup.add(telebot.types.KeyboardButton(destination))
        markup.add(telebot.types.KeyboardButton("✏️ Ввести другой адрес"))
        markup.add(telebot.types.KeyboardButton("🔙 Назад"))
        bot.send_message(message.chat.id, "Выберите направление (точка Б) или введите другой адрес:", reply_markup=markup)
        bot.register_next_step_handler(message, process_to_address)
        return
    
    # Формируем полный адрес назначения
    to_address = f"{to_city}, {street}"
    user_order_data[user_id]['to_address'] = to_address
    
    # Комментарий
    bot.send_message(message.chat.id, "Добавьте комментарий к заказу (необязательно). Если не нужен, отправьте '-':", reply_markup=None)
    bot.register_next_step_handler(message, process_preorder_comment)

def process_comment(message):
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
    
    # Создаем клавиатуру для подтверждения
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_order"),
        telebot.types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_order")
    )
    
    bot.send_message(
        message.chat.id,
        confirmation_text,
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_order")
def confirm_order_callback(call):
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
    
    # Создаем заказ в БД с индивидуальной нумерацией для клиента
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем количество заказов у данного клиента
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ?', (user['id'],))
    client_orders_count = cursor.fetchone()[0]
    client_order_number = client_orders_count + 1
    
    cursor.execute(
        '''INSERT INTO orders (client_id, from_address, to_address, comment, status)
           VALUES (?, ?, ?, ?, ?)''',
        (user['id'], order_data['from_address'], order_data['to_address'], order_data.get('comment'), 'NEW')
    )
    
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    
    # Уведомляем пользователя
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Заказ #{client_order_number} успешно создан и отправлен диспетчеру.\n\n"
             f"Ожидайте, в ближайшее время вам будет предложена цена поездки.",
        reply_markup=None
    )
    
    # Возвращаем главное меню
    bot.send_message(
        call.message.chat.id,
        "Вы можете создать новый заказ или воспользоваться другими функциями бота.",
        reply_markup=get_main_keyboard()
    )
    
    # Отправляем уведомление админу
    admin_text = f"🆕 <b>Новый заказ #{client_order_number}</b> (ID: {order_id})\n\n"
    admin_text += f"👤 <b>Клиент:</b> {call.from_user.first_name} {call.from_user.last_name or ''}\n"
    admin_text += f"📍 <b>Откуда:</b> {order_data['from_address']}\n"
    admin_text += f"🏁 <b>Куда:</b> {order_data['to_address']}\n"
    
    if order_data.get('comment'):
        admin_text += f"💬 <b>Комментарий:</b> {order_data['comment']}\n"
    
    # Добавляем кнопку для установки цены
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("💰 Установить цену", callback_data=f"set_price:{order_id}"))
    
    send_to_admins(
        admin_text,
        parse_mode="HTML",
        reply_markup=markup
    )
    
    # Очищаем временные данные
    if user_id in user_order_data:
        del user_order_data[user_id]

@bot.callback_query_handler(func=lambda call: call.data == "cancel_order")
def cancel_order_callback(call):
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

@bot.message_handler(func=lambda message: message.text == "📞 Связаться с нами")
def contact_us(message):
    bot.send_message(
        message.chat.id,
        "Если у вас возникли вопросы или проблемы, свяжитесь с нами:\n\n"
        "📞 Телефон: +7 (XXX) XXX-XX-XX\n"
        "📧 Email: taxi@svetlogorsk39.ru\n"
        "🌐 Сайт: svetlogorsk39-taxi.ru"
    )

@bot.message_handler(func=lambda message: message.text == "🔙 Главное меню")
def back_to_main_menu(message):
    bot.send_message(
        message.chat.id,
        "Вы вернулись в главное меню.",
        reply_markup=get_main_keyboard()
    )

# Обработчики админских кнопок
@bot.message_handler(func=lambda message: message.text == "📊 Активные заказы")
def active_orders(message):
    # Проверка прав администратора внутри хендлера, чтобы событие точно доходило
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Доступ запрещен.")
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT o.*, u.first_name, u.last_name, u.username
        FROM orders o
        JOIN users u ON o.client_id = u.id
        WHERE o.status IN ('NEW', 'PRICE_OFFERED', 'ACCEPTED', 'IN_PROGRESS')
        ORDER BY o.created_at DESC
    ''')
    
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        bot.send_message(
            message.chat.id,
            "Активных заказов нет.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    for order in orders:
        # Получаем номер заказа для клиента
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order['id']))
        client_order_number = cursor.fetchone()[0]
        conn.close()
        
        order_text = f"🚕 <b>Заказ #{client_order_number}</b> (ID: {order['id']})\n\n"
        order_text += f"👤 <b>Клиент:</b> {order['first_name']} {order['last_name'] or ''}\n"
        order_text += f"📍 <b>Откуда:</b> {order['from_address']}\n"
        order_text += f"🏁 <b>Куда:</b> {order['to_address']}\n"
        
        if order['comment']:
            order_text += f"💬 <b>Комментарий:</b> {order['comment']}\n"
        
        if order['price']:
            order_text += f"💰 <b>Цена:</b> {order['price']} руб.\n"
        
        # Добавляем запланированное время для админа
        if order.get('scheduled_at'):
            try:
                scheduled_time = datetime.datetime.fromisoformat(order['scheduled_at']).strftime('%d.%m %H:%M')
                order_text += f"🕐 <b>Запланированное время:</b> {scheduled_time}\n"
            except:
                pass
        
        status_map = {
            "NEW": "Новый",
            "PRICE_OFFERED": "Предложена цена", 
            "ACCEPTED": "Принят",
            "IN_PROGRESS": "Выполняется"
        }
        order_text += f"📊 <b>Статус:</b> {status_map.get(order['status'], order['status'])}\n"
        
        # Добавляем кнопки действий
        markup = telebot.types.InlineKeyboardMarkup()
        
        if order['status'] == 'NEW':
            markup.add(telebot.types.InlineKeyboardButton("💰 Установить цену", callback_data=f"set_price:{order['id']}"))
        elif order['status'] == 'ACCEPTED':
            markup.add(telebot.types.InlineKeyboardButton("🚕 Назначить водителя", callback_data=f"assign_driver:{order['id']}"))
        
        bot.send_message(
            message.chat.id,
            order_text,
            parse_mode="HTML",
            reply_markup=markup
        )

@bot.message_handler(func=lambda message: message.text == "📈 Статистика" and is_admin(message.from_user.id))
def show_statistics(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Общее количество заказов
    cursor.execute('SELECT COUNT(*) FROM orders')
    total_orders = cursor.fetchone()[0]
    
    # Завершенные заказы
    cursor.execute('SELECT COUNT(*) FROM orders WHERE status = "COMPLETED"')
    completed_orders = cursor.fetchone()[0]
    
    # Активные заказы
    cursor.execute('SELECT COUNT(*) FROM orders WHERE status IN ("NEW", "PRICE_OFFERED", "ACCEPTED", "IN_PROGRESS")')
    active_orders = cursor.fetchone()[0]
    
    # Количество клиентов
    cursor.execute('SELECT COUNT(*) FROM users')
    total_clients = cursor.fetchone()[0]
    
    # Количество водителей
    cursor.execute('SELECT COUNT(*) FROM drivers WHERE is_approved = 1')
    total_drivers = cursor.fetchone()[0]
    
    conn.close()
    
    stats_text = f"📊 <b>Статистика</b>\n\n"
    stats_text += f"<b>Заказы:</b>\n"
    stats_text += f"Всего заказов: {total_orders}\n"
    stats_text += f"Завершенных: {completed_orders}\n" 
    stats_text += f"Активных: {active_orders}\n\n"
    stats_text += f"<b>Пользователи:</b>\n"
    stats_text += f"Клиентов: {total_clients}\n"
    stats_text += f"Водителей: {total_drivers}\n"
    
    bot.send_message(
        message.chat.id,
        stats_text,
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "➕ Добавить администратора" and is_admin(message.from_user.id))
def add_admin_start(message):
    bot.send_message(message.chat.id, "Отправьте Telegram ID пользователя, которого нужно назначить администратором:")
    bot.register_next_step_handler(message, add_admin_process)

def add_admin_process(message):
    try:
        new_admin_id = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "Некорректный ID. Введите число:")
        bot.register_next_step_handler(message, add_admin_process)
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO admins (user_id, first_name) VALUES (?, ?)', (new_admin_id, None))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, f"✅ Пользователь {new_admin_id} добавлен в администраторы.", reply_markup=get_admin_keyboard())
    
    # Уведомим нового админа, если возможен контакт
    try:
        bot.send_message(new_admin_id, "👑 Вам выданы права администратора бота.")
    except Exception:
        pass

@bot.message_handler(func=lambda message: message.text == "📋 История заказов" and is_admin(message.from_user.id))
def order_history(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT o.*, u.first_name, u.last_name
        FROM orders o
        JOIN users u ON o.client_id = u.id
        WHERE o.status IN ('COMPLETED', 'CANCELLED')
        ORDER BY o.created_at DESC
        LIMIT 10
    ''')
    
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        bot.send_message(
            message.chat.id,
            "История заказов пуста.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    for order in orders:
        # Получаем номер заказа для клиента
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order['id']))
        client_order_number = cursor.fetchone()[0]
        conn.close()
        
        order_text = f"📋 <b>Заказ #{client_order_number}</b> (ID: {order['id']})\n\n"
        order_text += f"👤 <b>Клиент:</b> {order['first_name']} {order['last_name'] or ''}\n"
        order_text += f"📍 <b>Откуда:</b> {order['from_address']}\n"
        order_text += f"🏁 <b>Куда:</b> {order['to_address']}\n"
        
        if order['price']:
            order_text += f"💰 <b>Цена:</b> {order['price']} руб.\n"
        
        status_map = {
            "COMPLETED": "Завершен",
            "CANCELLED": "Отменен"
        }
        order_text += f"📊 <b>Статус:</b> {status_map.get(order['status'], order['status'])}\n"
        
        bot.send_message(
            message.chat.id,
            order_text,
            parse_mode="HTML"
        )

# Обработчик установки цены
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_price:") and is_admin(call.from_user.id))
def set_price_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    bot.send_message(
        call.message.chat.id,
        f"Введите цену для заказа ID {order_id} (только число в рублях):"
    )
    
    bot.register_next_step_handler(call.message, lambda m: process_price_input(m, order_id))

def process_price_input(message, order_id):
    try:
        price = float(message.text)
        
        if price <= 0:
            bot.send_message(
                message.chat.id,
                "Цена должна быть положительным числом. Попробуйте еще раз."
            )
            return
        
        # Обновляем заказ
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE orders SET price = ?, status = ? WHERE id = ?', (price, 'PRICE_OFFERED', order_id))
        
        # Получаем данные заказа и клиента
        cursor.execute('''
            SELECT o.*, u.user_id, u.first_name
            FROM orders o
            JOIN users u ON o.client_id = u.id
            WHERE o.id = ?
        ''', (order_id,))
        
        order = cursor.fetchone()
        conn.commit()
        conn.close()
        
        if not order:
            bot.send_message(message.chat.id, "Ошибка: заказ не найден")
            return
        
        # Получаем номер заказа для клиента
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order_id))
        client_order_number = cursor.fetchone()[0]
        conn.close()
        
        # Уведомляем админа
        bot.send_message(
            message.chat.id,
            f"✅ Цена {price} руб. установлена для заказа #{client_order_number} (ID: {order_id}).",
            reply_markup=get_admin_keyboard()
        )
        
        # Уведомляем клиента
        client_text = f"💰 <b>Предложена цена за поездку</b>\n\n"
        client_text += f"Заказ #{client_order_number}\n"
        client_text += f"Цена: {price} руб.\n\n"
        client_text += "Выберите действие:"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("✅ Согласен", callback_data=f"accept_price:{order_id}"),
            telebot.types.InlineKeyboardButton("❌ Не согласен", callback_data=f"decline_price:{order_id}")
        )
        markup.add(telebot.types.InlineKeyboardButton("💰 Предложить свою цену", callback_data=f"counter_offer:{order_id}"))
        
        bot.send_message(
            order['user_id'],
            client_text,
            parse_mode="HTML",
            reply_markup=markup
        )
        
    except ValueError:
        bot.send_message(
            message.chat.id,
            "Ошибка: введите корректное число."
        )

# Обработчики ответов клиента на цену
@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_price:"))
def accept_price_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    
    # Обновляем статус заказа
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT price, scheduled_at FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order:
        bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
        conn.close()
        return
    
    cursor.execute('UPDATE orders SET status = ? WHERE id = ?', ('ACCEPTED', order_id))
    conn.commit()
    conn.close()
    
    # Получаем номер заказа для клиента
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.client_id
        FROM orders o
        WHERE o.id = ?
    ''', (order_id,))
    result = cursor.fetchone()
    
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (result['client_id'], order_id))
    client_order_number = cursor.fetchone()[0]
    conn.close()
    
    # Уведомляем клиента
    scheduled_text = ""
    if order['scheduled_at']:
        try:
            scheduled_time = datetime.datetime.fromisoformat(order['scheduled_at']).strftime('%d.%m %H:%M')
            scheduled_text = f"\n🕐 Запланированное время: {scheduled_time}"
        except:
            pass
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Вы приняли цену {order['price']} руб. за поездку #{client_order_number}.{scheduled_text}\n\n"
             f"Ожидайте, в ближайшее время вам будет назначен водитель.",
        reply_markup=None
    )
    
    # Возвращаем главное меню
    bot.send_message(
        call.message.chat.id,
        "Вы можете создать новый заказ или воспользоваться другими функциями бота.",
        reply_markup=get_main_keyboard()
    )
    
    # Уведомляем админа
    send_to_admins(
        f"✅ Клиент принял цену {order['price']} руб. за заказ #{client_order_number} (ID: {order_id}).\n"
        f"Необходимо назначить водителя."
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("decline_price:"))
def decline_price_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    
    # Обновляем статус заказа
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT price, client_id FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order:
        bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
        conn.close()
        return
    
    cursor.execute('UPDATE orders SET status = ? WHERE id = ?', ('DECLINED', order_id))
    conn.commit()
    
    # Получаем номер заказа для клиента
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order_id))
    client_order_number = cursor.fetchone()[0]
    
    conn.close()
    
    # Уведомляем клиента
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ Вы отклонили цену {order['price']} руб. за поездку #{client_order_number}.\n\n"
             f"Заказ отменен.",
        reply_markup=None
    )
    
    # Возвращаем главное меню
    bot.send_message(
        call.message.chat.id,
        "Вы можете создать новый заказ или воспользоваться другими функциями бота.",
        reply_markup=get_main_keyboard()
    )
    
    # Уведомляем админа
    send_to_admins(
        f"❌ Клиент отклонил цену {order['price']} руб. за заказ #{client_order_number} (ID: {order_id})."
    )

# Обработчик назначения водителя
@bot.callback_query_handler(func=lambda call: call.data.startswith("assign_driver:") and is_admin(call.from_user.id))
def assign_driver_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    
    # Получаем список доступных водителей (исключаем только тех, кто дома или на месте)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM drivers WHERE is_approved = 1 AND status IN ("ON_DUTY", "ON_ORDER")')
    drivers = cursor.fetchall()
    
    if not drivers:
        bot.answer_callback_query(call.id, "Нет доступных водителей")
        bot.send_message(
            call.message.chat.id,
            "В данный момент нет доступных водителей на линии."
        )
        conn.close()
        return
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    # Создаем клавиатуру с водителями
    markup = telebot.types.InlineKeyboardMarkup()
    for driver in drivers:
        # Подсчитываем активные заказы водителя
        cursor.execute('SELECT COUNT(*) FROM orders WHERE driver_id = ? AND status IN ("IN_PROGRESS", "ACCEPTED")', (driver['id'],))
        active_orders_count = cursor.fetchone()[0]
        
        if active_orders_count > 0:
            button_text = f"{driver['first_name']} - {driver['car_number']} ({active_orders_count} заказ{'а' if active_orders_count > 1 else ''})"
        else:
            button_text = f"{driver['first_name']} - {driver['car_number']}"
        markup.add(telebot.types.InlineKeyboardButton(button_text, callback_data=f"select_driver:{order_id}:{driver['id']}"))
    
    bot.send_message(
        call.message.chat.id,
        f"Выберите водителя для заказа ID {order_id}:",
        reply_markup=markup
    )
    
    conn.close()

# Кнопка водителя: На месте
@bot.message_handler(func=lambda message: message.text == "📍 На месте" and get_driver_by_id(message.from_user.id))
def driver_arrived(message):
    """Водитель прибыл на точку А"""
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM drivers WHERE user_id = ?', (user_id,))
    driver = cursor.fetchone()
    if not driver:
        conn.close()
        bot.send_message(message.chat.id, "Вы не зарегистрированы как водитель.")
        return
    
    # Находим активный заказ водителя
    cursor.execute('SELECT id, client_id FROM orders WHERE driver_id = ? AND status = ?', (driver['id'], 'IN_PROGRESS'))
    order = cursor.fetchone()
    if not order:
        conn.close()
        bot.send_message(message.chat.id, "У вас нет активного заказа.")
        return
    
    # Обновляем статус водителя
    cursor.execute('UPDATE drivers SET status = ? WHERE id = ?', ('ARRIVED', driver['id']))
    conn.commit()
    
    # Уведомляем клиента
    cursor.execute('SELECT user_id FROM users WHERE id = ?', (order['client_id'],))
    client = cursor.fetchone()
    conn.close()
    if client:
        try:
            bot.send_message(client['user_id'], "🚗 Ваш водитель прибыл на место (точка А). Подходите, пожалуйста.")
        except Exception as e:
            logger.error(f"Не удалось уведомить клиента о прибытии: {e}")
    
    bot.send_message(message.chat.id, "Статус обновлен: На месте.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_driver:") and is_admin(call.from_user.id))
def select_driver_callback(call):
    parts = call.data.split(":")
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    driver_id = int(parts[2])
    
    # Назначаем водителя на заказ
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    cursor.execute('SELECT * FROM drivers WHERE id = ?', (driver_id,))
    driver = cursor.fetchone()
    
    if not order or not driver:
        bot.answer_callback_query(call.id, "Ошибка: заказ или водитель не найден")
        conn.close()
        return
    
    # Обновляем заказ
    cursor.execute('UPDATE orders SET driver_id = ?, status = ? WHERE id = ?', (driver_id, 'IN_PROGRESS', order_id))
    
    # Обновляем статус водителя на "На заказе" только если он был "На линии"
    if driver['status'] == 'ON_DUTY':
        cursor.execute('UPDATE drivers SET status = ? WHERE id = ?', ('ON_ORDER', driver_id))
    
    conn.commit()
    
    # Получаем клиента
    cursor.execute('SELECT user_id FROM users WHERE id = ?', (order['client_id'],))
    client = cursor.fetchone()
    client_user_id = client['user_id'] if client else None
    
    # Получаем номер заказа для клиента
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order_id))
    client_order_number = cursor.fetchone()[0]
    
    conn.close()
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    # Уведомляем администратора
    bot.send_message(
        call.message.chat.id,
        f"✅ Водитель {driver['first_name']} ({driver['car_number']}) назначен на заказ #{client_order_number} (ID: {order_id}).",
        reply_markup=get_admin_keyboard()
    )
    
    # Уведомляем клиента
    if client_user_id:
        client_text = f"🚕 <b>Вам назначен водитель</b>\n\n"
        client_text += f"Заказ #{client_order_number}\n"
        client_text += f"Водитель: {driver['first_name']}\n"
        client_text += f"Автомобиль: {driver['car_number']}\n\n"
        client_text += "Водитель скоро прибудет на место посадки."
        
        bot.send_message(
            client_user_id,
            client_text,
            parse_mode="HTML"
        )
    
    # Уведомляем водителя
    driver_text = f"🆕 <b>Вам назначен новый заказ</b>\n\n"
    driver_text += f"Заказ #{client_order_number} (ID: {order_id})\n"
    driver_text += f"От: {order['from_address']}\n"
    driver_text += f"До: {order['to_address']}\n"
    driver_text += f"Цена: {order['price']} руб.\n"
    
    # Добавляем время заказа
    if order.get('scheduled_at'):
        try:
            scheduled_time = datetime.datetime.fromisoformat(order['scheduled_at']).strftime('%d.%m %H:%M')
            driver_text += f"🕐 Время подачи: {scheduled_time}\n"
        except:
            pass
    
    if order['comment']:
        driver_text += f"Комментарий: {order['comment']}\n"
    
    # Кнопка прибытия на точку А (после этого начнется поездка)
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🚗 Водитель подъехал в точку А", callback_data=f"driver_arrived:{order_id}"))
    
    bot.send_message(
        driver['user_id'],
        driver_text,
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("counter_offer:"))
def counter_offer_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    bot.send_message(
        call.message.chat.id,
        "Введите вашу цену за поездку (только число в рублях):"
    )
    
    bot.register_next_step_handler(call.message, lambda m: process_counter_offer(m, order_id))

def process_counter_offer(message, order_id):
    try:
        price = float(message.text)
        
        if price <= 0:
            bot.send_message(
                message.chat.id,
                "Цена должна быть положительным числом. Попробуйте еще раз."
            )
            bot.register_next_step_handler(message, lambda m: process_counter_offer(m, order_id))
            return
        
        # Обновляем заказ
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT price, client_id FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            bot.send_message(message.chat.id, "Ошибка: заказ не найден")
            conn.close()
            return
        
        cursor.execute('UPDATE orders SET counter_offer = ? WHERE id = ?', (price, order_id))
        conn.commit()
        
        # Получаем номер заказа для клиента
        cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order_id))
        client_order_number = cursor.fetchone()[0]
        
        conn.close()
        
        # Уведомляем клиента
        bot.send_message(
            message.chat.id,
            f"✅ Ваше предложение цены {price} руб. отправлено диспетчеру.\n"
            f"Ожидайте ответа.",
            reply_markup=get_main_keyboard()
        )
        
        # Уведомляем админа с кнопками для ответа
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("✅ Принять цену", callback_data=f"accept_counter_offer:{order_id}"),
            telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_counter_offer:{order_id}")
        )
        markup.add(telebot.types.InlineKeyboardButton("💰 Предложить другую цену", callback_data=f"admin_counter_offer:{order_id}"))
        
        send_to_admins(
            f"💰 <b>Встречное предложение клиента</b>\n\n"
            f"Заказ #{client_order_number} (ID: {order_id})\n"
            f"Ваша цена: {order['price']} руб.\n"
            f"Предложение клиента: {price} руб.\n\n"
            f"Выберите действие:",
            parse_mode="HTML",
            reply_markup=markup
        )
        
    except ValueError:
        bot.send_message(
            message.chat.id,
            "Ошибка: введите корректное число. Попробуйте еще раз."
        )
        bot.register_next_step_handler(message, lambda m: process_counter_offer(m, order_id))

# Обработчики ответов администратора на встречные предложения
@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_counter_offer:") and is_admin(call.from_user.id))
def accept_counter_offer_callback(call):
    """Админ принимает встречное предложение клиента"""
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    
    # Обновляем заказ - устанавливаем цену клиента как окончательную
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT counter_offer, client_id FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order or not order['counter_offer']:
        bot.answer_callback_query(call.id, "Ошибка: заказ или предложение не найдено")
        conn.close()
        return
    
    # Устанавливаем цену клиента как окончательную и меняем статус на принятый
    cursor.execute('UPDATE orders SET price = ?, status = ? WHERE id = ?', (order['counter_offer'], 'ACCEPTED', order_id))
    conn.commit()
    
    # Получаем номер заказа для клиента
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order_id))
    client_order_number = cursor.fetchone()[0]
    
    # Получаем клиента
    cursor.execute('SELECT user_id FROM users WHERE id = ?', (order['client_id'],))
    client = cursor.fetchone()
    client_user_id = client['user_id'] if client else None
    
    conn.close()
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    # Уведомляем администратора
    bot.send_message(
        call.message.chat.id,
        f"✅ Вы приняли предложение клиента {order['counter_offer']} руб. за заказ #{client_order_number} (ID: {order_id}).\n"
        f"Теперь можно назначить водителя.",
        reply_markup=get_admin_keyboard()
    )
    
    # Уведомляем клиента
    if client_user_id:
        bot.send_message(
            client_user_id,
            f"🎉 <b>Отличные новости!</b>\n\n"
            f"Ваше предложение цены {order['counter_offer']} руб. за заказ #{client_order_number} принято!\n\n"
            f"Ожидайте, в ближайшее время вам будет назначен водитель.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("decline_counter_offer:") and is_admin(call.from_user.id))
def decline_counter_offer_callback(call):
    """Админ отклоняет встречное предложение клиента"""
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    
    # Получаем данные заказа
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT counter_offer, price, client_id FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order:
        bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
        conn.close()
        return
    
    # Обновляем статус заказа на отклоненный
    cursor.execute('UPDATE orders SET status = ? WHERE id = ?', ('DECLINED', order_id))
    conn.commit()
    
    # Получаем номер заказа для клиента
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order_id))
    client_order_number = cursor.fetchone()[0]
    
    # Получаем клиента
    cursor.execute('SELECT user_id FROM users WHERE id = ?', (order['client_id'],))
    client = cursor.fetchone()
    client_user_id = client['user_id'] if client else None
    
    conn.close()
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    # Уведомляем администратора
    bot.send_message(
        call.message.chat.id,
        f"❌ Вы отклонили предложение клиента {order['counter_offer']} руб. за заказ #{client_order_number} (ID: {order_id}).\n"
        f"Заказ отменен.",
        reply_markup=get_admin_keyboard()
    )
    
    # Уведомляем клиента
    if client_user_id:
        bot.send_message(
            client_user_id,
            f"😔 <b>Ваше предложение отклонено</b>\n\n"
            f"К сожалению, ваше предложение цены {order['counter_offer']} руб. за заказ #{client_order_number} отклонено.\n\n"
            f"Заказ отменен. Вы можете создать новый заказ.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_counter_offer:") and is_admin(call.from_user.id))
def admin_counter_offer_callback(call):
    """Админ предлагает свою встречную цену"""
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    bot.send_message(
        call.message.chat.id,
        f"Введите вашу встречную цену для заказа ID {order_id} (только число в рублях):"
    )
    
    bot.register_next_step_handler(call.message, lambda m: process_admin_counter_offer(m, order_id))

def process_admin_counter_offer(message, order_id):
    """Обработка встречной цены от администратора"""
    try:
        price = float(message.text)
        
        if price <= 0:
            bot.send_message(
                message.chat.id,
                "Цена должна быть положительным числом. Попробуйте еще раз."
            )
            bot.register_next_step_handler(message, lambda m: process_admin_counter_offer(m, order_id))
            return
        
        # Обновляем заказ
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT counter_offer, client_id FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            bot.send_message(message.chat.id, "Ошибка: заказ не найден")
            conn.close()
            return
        
        # Устанавливаем новую цену администратора и возвращаем статус к "предложена цена"
        cursor.execute('UPDATE orders SET price = ?, status = ? WHERE id = ?', (price, 'PRICE_OFFERED', order_id))
        conn.commit()
        
        # Получаем номер заказа для клиента
        cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order_id))
        client_order_number = cursor.fetchone()[0]
        
        # Получаем клиента
        cursor.execute('SELECT user_id FROM users WHERE id = ?', (order['client_id'],))
        client = cursor.fetchone()
        client_user_id = client['user_id'] if client else None
        
        conn.close()
        
        # Уведомляем администратора
        bot.send_message(
            message.chat.id,
            f"✅ Ваша встречная цена {price} руб. отправлена клиенту за заказ #{client_order_number} (ID: {order_id}).\n"
            f"Предложение клиента было: {order['counter_offer']} руб.",
            reply_markup=get_admin_keyboard()
        )
        
        # Уведомляем клиента с новым предложением
        if client_user_id:
            
            client_text = f"💰 <b>Встречное предложение от диспетчера</b>\n\n"
            client_text += f"Заказ #{client_order_number}\n"
            client_text += f"Ваше предложение: {order['counter_offer']} руб.\n"
            client_text += f"Новая цена диспетчера: {price} руб.\n\n"
            client_text += "Выберите действие:"
            
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(
                telebot.types.InlineKeyboardButton("✅ Согласен", callback_data=f"accept_price:{order_id}"),
                telebot.types.InlineKeyboardButton("❌ Не согласен", callback_data=f"decline_price:{order_id}")
            )
            markup.add(telebot.types.InlineKeyboardButton("💰 Предложить свою цену", callback_data=f"counter_offer:{order_id}"))
            
            bot.send_message(
                client_user_id,
                client_text,
                parse_mode="HTML",
                reply_markup=markup
            )
        
    except ValueError:
        bot.send_message(
            message.chat.id,
            "Ошибка: введите корректное число. Попробуйте еще раз."
        )
        bot.register_next_step_handler(message, lambda m: process_admin_counter_offer(m, order_id))

# Обработчик кнопки "Очистить заказы" (только для админа)
@bot.message_handler(func=lambda message: message.text == "🗑️ Очистить заказы" and is_admin(message.from_user.id))
def clear_orders(message):
    """Админ может очистить активные заказы"""
    # Получаем количество активных заказов
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM orders WHERE status NOT IN (?, ?)', ('COMPLETED', 'CANCELLED'))
    active_count = cursor.fetchone()[0]
    
    if active_count == 0:
        bot.send_message(
            message.chat.id,
            "✅ Активных заказов нет.",
            reply_markup=get_admin_keyboard()
        )
        conn.close()
        return
    
    # Предлагаем подтверждение
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Да, очистить все", callback_data="confirm_clear_orders"),
        telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear_orders")
    )
    
    bot.send_message(
        message.chat.id,
        f"⚠️ <b>Подтверждение очистки</b>\n\n"
        f"Найдено активных заказов: <b>{active_count}</b>\n\n"
        f"Это действие:\n"
        f"• Отменит все активные заказы\n"
        f"• Освободит всех водителей\n"
        f"• Уведомит клиентов об отмене\n\n"
        f"<b>Внимание!</b> Это действие необратимо.\n\n"
        f"Продолжить?",
        parse_mode="HTML",
        reply_markup=markup
    )
    
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data == "confirm_clear_orders" and is_admin(call.from_user.id))
def confirm_clear_orders_callback(call):
    """Подтверждение очистки заказов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем активные заказы с информацией о клиентах и водителях
    cursor.execute('''
        SELECT o.id, o.client_id, o.driver_id, u.user_id as client_user_id, d.user_id as driver_user_id
        FROM orders o
        LEFT JOIN users u ON o.client_id = u.id
        LEFT JOIN drivers d ON o.driver_id = d.id
        WHERE o.status NOT IN (?, ?)
    ''', ('COMPLETED', 'CANCELLED'))
    
    active_orders = cursor.fetchall()
    cleared_count = len(active_orders)
    
    if cleared_count == 0:
        bot.edit_message_text(
            "✅ Активных заказов нет.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        return
    
    # Отменяем все активные заказы
    cursor.execute('UPDATE orders SET status = ? WHERE status NOT IN (?, ?)', ('CANCELLED', 'COMPLETED', 'CANCELLED'))
    
    # Освобождаем всех водителей (ставим статус "На линии")
    cursor.execute('UPDATE drivers SET status = ? WHERE status = ?', ('ON_DUTY', 'ON_ORDER'))
    
    conn.commit()
    conn.close()
    
    # Уведомляем клиентов об отмене заказов
    notified_clients = 0
    for order in active_orders:
        if order['client_user_id']:
            try:
                # Получаем номер заказа для клиента
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order['id']))
                client_order_number = cursor.fetchone()[0]
                conn.close()
                
                bot.send_message(
                    order['client_user_id'],
                    f"❌ <b>Заказ отменен администратором</b>\n\n"
                    f"Ваш заказ #{client_order_number} был отменен по техническим причинам.\n\n"
                    f"Приносим извинения за неудобства. Вы можете создать новый заказ.",
                    parse_mode="HTML",
                    reply_markup=get_main_keyboard()
                )
                notified_clients += 1
            except Exception as e:
                logger.error(f"Ошибка уведомления клиента {order['client_user_id']}: {e}")
    
    # Уведомляем водителей об освобождении
    notified_drivers = 0
    for order in active_orders:
        if order['driver_user_id'] and order['driver_id']:
            try:
                bot.send_message(
                    order['driver_user_id'],
                    f"ℹ️ <b>Заказ отменен администратором</b>\n\n"
                    f"Ваш текущий заказ был отменен по техническим причинам.\n"
                    f"Ваш статус изменен на: <b>🟢 На линии</b>\n\n"
                    f"Вы можете принимать новые заказы.",
                    parse_mode="HTML",
                    reply_markup=get_driver_keyboard()
                )
                notified_drivers += 1
            except Exception as e:
                logger.error(f"Ошибка уведомления водителя {order['driver_user_id']}: {e}")
    
    # Обновляем сообщение администратора
    bot.edit_message_text(
        f"✅ <b>Очистка завершена</b>\n\n"
        f"Отменено заказов: <b>{cleared_count}</b>\n"
        f"Уведомлено клиентов: <b>{notified_clients}</b>\n"
        f"Уведомлено водителей: <b>{notified_drivers}</b>\n\n"
        f"Все водители переведены в статус \"На линии\".",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="HTML"
    )
    
    # Возвращаем админ-клавиатуру
    bot.send_message(
        call.message.chat.id,
        "Готово! Можете продолжить работу.",
        reply_markup=get_admin_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_clear_orders" and is_admin(call.from_user.id))
def cancel_clear_orders_callback(call):
    """Отмена очистки заказов"""
    bot.edit_message_text(
        "❌ Очистка заказов отменена.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    
    bot.send_message(
        call.message.chat.id,
        "Возвращаемся в админ-панель.",
        reply_markup=get_admin_keyboard()
    )

# Обработчик кнопки "Мои заказы"
@bot.message_handler(func=lambda message: message.text == "📝 Мои заказы")
def my_orders(message):
    user_id = message.from_user.id
    user = get_user_by_id(user_id)
    
    if not user:
        bot.send_message(message.chat.id, "Ошибка получения данных пользователя.")
        return
    
    # Получаем заказы пользователя
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE client_id = ? ORDER BY created_at DESC LIMIT 5', (user['id'],))
    orders = cursor.fetchall()
    
    if not orders:
        bot.send_message(
            message.chat.id, 
            "У вас пока нет заказов.",
            reply_markup=get_main_keyboard()
        )
        conn.close()
        return
    
    for order in orders:
        # Получаем номер заказа для клиента
        cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (user['id'], order['id']))
        client_order_number = cursor.fetchone()[0]
        
        order_text = f"🚕 <b>Заказ #{client_order_number}</b>\n\n"
        order_text += f"📍 <b>Откуда:</b> {order['from_address']}\n"
        order_text += f"🏁 <b>Куда:</b> {order['to_address']}\n"
        
        if order['comment']:
            order_text += f"💬 <b>Комментарий:</b> {order['comment']}\n"
        
        if order['price']:
            order_text += f"💰 <b>Цена:</b> {order['price']} руб.\n"
        
        if order['counter_offer']:
            order_text += f"💸 <b>Ваше предложение:</b> {order['counter_offer']} руб.\n"
        
        # Добавляем запланированное время
        if order.get('scheduled_at'):
            try:
                scheduled_time = datetime.datetime.fromisoformat(order['scheduled_at']).strftime('%d.%m %H:%M')
                order_text += f"🕐 <b>Запланированное время:</b> {scheduled_time}\n"
            except:
                pass
        
        status_map = {
            "NEW": "Новый",
            "PRICE_OFFERED": "Предложена цена",
            "ACCEPTED": "Принят",
            "DECLINED": "Отклонен",
            "IN_PROGRESS": "Выполняется",
            "COMPLETED": "Завершен",
            "CANCELLED": "Отменен"
        }
        order_text += f"📊 <b>Статус:</b> {status_map.get(order['status'], order['status'])}\n"
        order_text += f"🕒 <b>Создан:</b> {order['created_at']}\n"
        
        # Добавляем кнопку для оценки, если заказ завершен и еще не оценен
        markup = None
        if order['status'] == "COMPLETED":
            cursor.execute('SELECT * FROM reviews WHERE order_id = ?', (order['id'],))
            review = cursor.fetchone()
            if not review:
                markup = telebot.types.InlineKeyboardMarkup()
                for i in range(1, 6):
                    markup.add(telebot.types.InlineKeyboardButton(f"⭐ {i}", callback_data=f"rate:{order['id']}:{i}"))
        
        bot.send_message(
            message.chat.id,
            order_text,
            parse_mode="HTML",
            reply_markup=markup
        )
    
    conn.close()

# Обработчик оценки поездки
@bot.callback_query_handler(func=lambda call: call.data.startswith("rate:"))
def process_rating(call):
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE id = ? AND client_id = ?', (order_id, user['id']))
    order = cursor.fetchone()
    
    if not order:
        bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
        conn.close()
        return
    
    # Проверяем, есть ли уже отзыв
    cursor.execute('SELECT * FROM reviews WHERE order_id = ?', (order_id,))
    existing_review = cursor.fetchone()
    if existing_review:
        bot.answer_callback_query(call.id, "Вы уже оставили отзыв на этот заказ")
        conn.close()
        return
    
    # Создаем отзыв
    cursor.execute(
        'INSERT INTO reviews (order_id, client_id, driver_id, rating) VALUES (?, ?, ?, ?)',
        (order_id, user['id'], order['driver_id'], rating)
    )
    conn.commit()
    conn.close()
    
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

def process_review_comment(message, order_id):
    comment = message.text
    
    if comment and comment != '-':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE reviews SET comment = ? WHERE order_id = ?', (comment, order_id))
        conn.commit()
        conn.close()
        
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

# Обработчик кнопки "Стать нашим партнером"
@bot.message_handler(func=lambda message: message.text == "🤝 Стать нашим партнером")
def become_partner(message):
    user_id = message.from_user.id
    
    # Проверяем, не зарегистрирован ли пользователь уже как водитель
    driver = get_driver_by_id(user_id)
    
    if driver:
        if driver['is_approved']:
            bot.send_message(
                message.chat.id,
                f"Вы уже зарегистрированы как водитель!\n"
                f"Используйте команду /driver для доступа к меню водителя.",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "Ваша заявка на регистрацию в качестве водителя уже отправлена и находится на рассмотрении.\n"
                "Пожалуйста, ожидайте решения администратора.",
                reply_markup=get_main_keyboard()
            )
        return
    
    # Начинаем процесс регистрации водителя
    bot.send_message(
        message.chat.id,
        "🚗 <b>Регистрация водителя-партнера</b>\n\n"
        "Для работы в нашем сервисе необходимо пройти регистрацию.\n"
        "Вам потребуется предоставить следующие данные:\n\n"
        "• Полное имя\n"
        "• Номер водительского удостоверения\n"
        "• Данные ПТС автомобиля\n"
        "• Госномер автомобиля\n"
        "• Фотографии автомобиля с 4-х сторон\n\n"
        "Готовы начать регистрацию?",
        parse_mode="HTML"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Да, начать регистрацию", callback_data="start_driver_reg"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_driver_reg"))
    
    bot.send_message(
        message.chat.id,
        "Выберите действие:",
        reply_markup=markup
    )

# Обработчики регистрации водителя
@bot.callback_query_handler(func=lambda call: call.data == "start_driver_reg")
def start_driver_registration(call):
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
def cancel_driver_registration(call):
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

def process_driver_name(message):
    user_id = message.from_user.id
    name = message.text.strip()
    
    if not name or len(name) < 2:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректное полное имя (минимум 2 символа).")
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

def process_driver_license(message):
    user_id = message.from_user.id
    license_number = message.text.strip()
    
    if not license_number or len(license_number) < 5:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный номер водительского удостоверения.")
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

def process_car_registration(message):
    user_id = message.from_user.id
    car_registration = message.text.strip()
    
    if not car_registration or len(car_registration) < 5:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректные данные ПТС.")
        bot.register_next_step_handler(message, process_car_registration)
        return
    
    # Сохраняем данные ПТС
    driver_registration_data[user_id]['car_registration'] = car_registration
    
    # Запрашиваем госномер автомобиля
    bot.send_message(
        message.chat.id,
        "Введите госномер автомобиля (например: А123БВ78):"
    )
    bot.register_next_step_handler(message, process_car_number)

def process_car_number(message):
    user_id = message.from_user.id
    car_number = message.text.strip().upper()
    
    if not car_number or len(car_number) < 6:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный госномер автомобиля.")
        bot.register_next_step_handler(message, process_car_number)
        return
    
    # Сохраняем госномер
    driver_registration_data[user_id]['car_number'] = car_number
    driver_registration_data[user_id]['car_photos'] = []
    
    # Запрашиваем фото автомобиля спереди
    bot.send_message(
        message.chat.id,
        "Теперь отправьте фотографии автомобиля.\n\n"
        "📸 Отправьте фото автомобиля <b>СПЕРЕДИ</b>:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(message, process_front_photo)

def process_front_photo(message):
    user_id = message.from_user.id
    
    if not message.photo:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте фотографию автомобиля спереди.")
        bot.register_next_step_handler(message, process_front_photo)
        return
    
    # Сохраняем фото спереди
    photo = message.photo[-1]
    driver_registration_data[user_id]['car_photos'].append({
        'position': 'front',
        'file_id': photo.file_id
    })
    
    bot.send_message(
        message.chat.id,
        "✅ Фото спереди получено!\n\n"
        "📸 Теперь отправьте фото автомобиля <b>СЗАДИ</b>:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(message, process_back_photo)

def process_back_photo(message):
    user_id = message.from_user.id
    
    if not message.photo:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте фотографию автомобиля сзади.")
        bot.register_next_step_handler(message, process_back_photo)
        return
    
    # Сохраняем фото сзади
    photo = message.photo[-1]
    driver_registration_data[user_id]['car_photos'].append({
        'position': 'back',
        'file_id': photo.file_id
    })
    
    bot.send_message(
        message.chat.id,
        "✅ Фото сзади получено!\n\n"
        "📸 Теперь отправьте фото автомобиля <b>СЛЕВА</b>:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(message, process_left_photo)

def process_left_photo(message):
    user_id = message.from_user.id
    
    if not message.photo:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте фотографию автомобиля слева.")
        bot.register_next_step_handler(message, process_left_photo)
        return
    
    # Сохраняем фото слева
    photo = message.photo[-1]
    driver_registration_data[user_id]['car_photos'].append({
        'position': 'left',
        'file_id': photo.file_id
    })
    
    bot.send_message(
        message.chat.id,
        "✅ Фото слева получено!\n\n"
        "📸 И последнее - отправьте фото автомобиля <b>СПРАВА</b>:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(message, process_right_photo)

def process_right_photo(message):
    user_id = message.from_user.id
    
    if not message.photo:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте фотографию автомобиля справа.")
        bot.register_next_step_handler(message, process_right_photo)
        return
    
    # Сохраняем фото справа
    photo = message.photo[-1]
    driver_registration_data[user_id]['car_photos'].append({
        'position': 'right',
        'file_id': photo.file_id
    })
    
    # Завершаем регистрацию
    complete_driver_registration(message)

def complete_driver_registration(message):
    user_id = message.from_user.id
    
    # Получаем все данные регистрации
    reg_data = driver_registration_data.get(user_id, {})
    
    if not reg_data:
        bot.send_message(message.chat.id, "Ошибка: данные регистрации не найдены.")
        return
    
    # Создаем запись о водителе в БД
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Преобразуем массив фотографий в JSON строку
    car_photos_json = json.dumps(reg_data.get('car_photos', []))
    
    cursor.execute('''
        INSERT INTO drivers (user_id, first_name, license_number, car_registration, car_number, car_photos, status, is_approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        reg_data.get('first_name', ''),
        reg_data.get('license_number', ''),
        reg_data.get('car_registration', ''),
        reg_data.get('car_number', ''),
        car_photos_json,
        'OFF_DUTY',
        0  # Не одобрен
    ))
    
    conn.commit()
    conn.close()
    
    # Очищаем временные данные
    if user_id in driver_registration_data:
        del driver_registration_data[user_id]
    
    # Уведомляем пользователя
    bot.send_message(
        message.chat.id,
        "✅ <b>Заявка успешно отправлена!</b>\n\n"
        "Ваша заявка на регистрацию в качестве водителя-партнера отправлена администратору.\n"
        "Вы получите уведомление, когда заявка будет рассмотрена.\n\n"
        "Спасибо за интерес к сотрудничеству с нами! 🚗",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    
    # Уведомляем админа о новой заявке
    admin_text = f"🆕 <b>Новая заявка на регистрацию водителя</b>\n\n"
    admin_text += f"👤 <b>Имя:</b> {reg_data.get('first_name', '')}\n"
    admin_text += f"🚗 <b>Госномер:</b> {reg_data.get('car_number', '')}\n"
    admin_text += f"📄 <b>Водительское удостоверение:</b> {reg_data.get('license_number', '')}\n"
    admin_text += f"📝 <b>ПТС:</b> {reg_data.get('car_registration', '')}\n"
    admin_text += f"👤 <b>Telegram:</b> @{message.from_user.username or 'не указан'}\n"
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_driver_new:{user_id}"),
        telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_driver_new:{user_id}")
    )
    
    send_to_admins(
        admin_text,
        parse_mode="HTML",
        reply_markup=markup
    )
    
    # Отправляем фотографии автомобиля админу
    for photo in reg_data.get('car_photos', []):
        caption = f"Фото автомобиля {reg_data.get('car_number', '')}: {photo.get('position', '')}"
        send_photo_to_admins(photo.get('file_id', ''), caption=caption)

# Обработчики для одобрения/отклонения водителей
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_driver_new:") and is_admin(call.from_user.id))
def approve_driver_new_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    driver_user_id = int(parts[1])
    
    # Одобряем водителя
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE drivers SET is_approved = 1 WHERE user_id = ?', (driver_user_id,))
    cursor.execute('SELECT first_name, car_number FROM drivers WHERE user_id = ?', (driver_user_id,))
    driver = cursor.fetchone()
    conn.commit()
    conn.close()
    
    if not driver:
        bot.answer_callback_query(call.id, "Ошибка: водитель не найден")
        return
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    # Уведомляем администратора
    bot.send_message(
        call.message.chat.id,
        f"✅ Водитель {driver['first_name']} ({driver['car_number']}) одобрен.",
        reply_markup=get_admin_keyboard()
    )
    
    # Уведомляем водителя
    bot.send_message(
        driver_user_id,
        "🎉 <b>Поздравляем!</b>\n\n"
        "Ваша заявка на регистрацию в качестве водителя одобрена.\n"
        "Теперь вы можете начать работать. Используйте команду /driver для доступа к меню водителя.",
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_driver_new:") and is_admin(call.from_user.id))
def reject_driver_new_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    driver_user_id = int(parts[1])
    
    # Получаем данные о водителе
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT first_name FROM drivers WHERE user_id = ?', (driver_user_id,))
    driver = cursor.fetchone()
    
    if driver:
        driver_name = driver['first_name']
        # Удаляем водителя из БД
        cursor.execute('DELETE FROM drivers WHERE user_id = ?', (driver_user_id,))
        conn.commit()
    else:
        driver_name = "Неизвестный"
    
    conn.close()
    
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
    bot.send_message(
        driver_user_id,
        "❌ <b>Уведомление</b>\n\n"
        "К сожалению, ваша заявка на регистрацию в качестве водителя отклонена.\n"
        "Для получения дополнительной информации свяжитесь с администрацией.",
        parse_mode="HTML"
    )

# Обработчик кнопки "Управление водителями"
@bot.message_handler(func=lambda message: message.text == "👨‍✈️ Управление водителями" and is_admin(message.from_user.id))
def manage_drivers(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем заявки на регистрацию водителей
    cursor.execute('SELECT * FROM drivers WHERE is_approved = 0')
    pending_drivers = cursor.fetchall()
    
    if pending_drivers:
        bot.send_message(
            message.chat.id,
            f"📝 <b>Заявки на регистрацию водителей ({len(pending_drivers)}):</b>",
            parse_mode="HTML"
        )
        
        for driver in pending_drivers:
            driver_text = f"👤 <b>Имя:</b> {driver['first_name']}\n"
            driver_text += f"🚗 <b>Госномер:</b> {driver['car_number']}\n"
            driver_text += f"📄 <b>Водительское удостоверение:</b> {driver['license_number']}\n"
            driver_text += f"📝 <b>ПТС:</b> {driver['car_registration']}\n"
            
            # Кнопки для одобрения/отклонения
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(
                telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_driver_new:{driver['user_id']}"),
                telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_driver_new:{driver['user_id']}")
            )
            
            bot.send_message(
                message.chat.id,
                driver_text,
                parse_mode="HTML",
                reply_markup=markup
            )
    
    # Получаем активных водителей
    cursor.execute('SELECT * FROM drivers WHERE is_approved = 1')
    active_drivers = cursor.fetchall()
    
    if active_drivers:
        bot.send_message(
            message.chat.id,
            f"🚕 <b>Активные водители ({len(active_drivers)}):</b>",
            parse_mode="HTML"
        )
        
        for driver in active_drivers:
            # Получаем средний рейтинг водителя
            cursor.execute('SELECT AVG(rating) FROM reviews WHERE driver_id = ?', (driver['id'],))
            avg_rating = cursor.fetchone()[0] or 0
            
            # Получаем общий заработок водителя
            cursor.execute('SELECT SUM(amount) FROM earnings WHERE driver_id = ?', (driver['id'],))
            total_earnings = cursor.fetchone()[0] or 0
            
            status_map = {
                "ON_DUTY": "На линии",
                "ON_ORDER": "На заказе",
                "OFF_DUTY": "Дома",
                "ARRIVED": "На месте"
            }
            
            driver_text = f"👨‍✈️ <b>{driver['first_name']}</b>\n"
            driver_text += f"🚗 <b>Номер авто:</b> {driver['car_number']}\n"
            driver_text += f"📊 <b>Статус:</b> {status_map.get(driver['status'], driver['status'])}\n"
            driver_text += f"⭐ <b>Рейтинг:</b> {avg_rating:.1f}/5.0\n"
            driver_text += f"💰 <b>Общий заработок:</b> {total_earnings} руб.\n"
            
            bot.send_message(
                message.chat.id,
                driver_text,
                parse_mode="HTML"
            )
    
    if not pending_drivers and not active_drivers:
        bot.send_message(
            message.chat.id,
            "Нет водителей для отображения.",
            reply_markup=get_admin_keyboard()
        )
    
    conn.close()

# Обработчик команды /profile
@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    user = get_user_by_id(user_id)
    
    if not user:
        bot.send_message(message.chat.id, "Ошибка получения данных профиля.")
        return
    
    # Получаем количество заказов пользователя
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ?', (user['id'],))
    orders_count = cursor.fetchone()[0]
    conn.close()
    
    profile_text = f"👤 <b>Ваш профиль</b>\n\n"
    profile_text += f"Имя: {user['first_name'] or 'Не указано'} {user['last_name'] or ''}\n"
    profile_text += f"Username: @{user['username'] or 'не указан'}\n"
    profile_text += f"Телефон: {user['phone_number'] or 'Не указан'}\n"
    profile_text += f"Количество заказов: {orders_count}\n"
    profile_text += f"Дата регистрации: {user['registration_date']}\n"
    
    bot.send_message(message.chat.id, profile_text, parse_mode="HTML")
    
    # Если телефон не указан, предлагаем его указать
    if not user['phone_number']:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        button = telebot.types.KeyboardButton("📱 Отправить номер телефона", request_contact=True)
        markup.add(button)
        markup.add(telebot.types.KeyboardButton("🔙 Главное меню"))
        
        bot.send_message(
            message.chat.id,
            "Для удобства заказа такси рекомендуем указать номер телефона.",
            reply_markup=markup
        )

@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    if message.contact is not None:
        user_id = message.from_user.id
        phone = message.contact.phone_number
        
        # Сохраняем телефон в БД
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET phone_number = ? WHERE user_id = ?', (phone, user_id))
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            "Спасибо! Ваш номер телефона сохранен.",
            reply_markup=get_main_keyboard()
        )

# Геолокация отключена: отдельный обработчик более не требуется

# Обработчик команды /driver
@bot.message_handler(commands=['driver'])
def driver_command(message):
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь как водитель
    driver = get_driver_by_id(user_id)
    
    if not driver:
        bot.send_message(
            message.chat.id,
            "Вы не зарегистрированы как водитель.\n"
            "Для регистрации нажмите кнопку '🤝 Стать нашим партнером' в главном меню.",
            reply_markup=get_main_keyboard()
        )
        return
    
    if not driver['is_approved']:
        bot.send_message(
            message.chat.id,
            "Ваша заявка на регистрацию в качестве водителя находится на рассмотрении.\n"
            "Пожалуйста, ожидайте решения администратора."
        )
        return
    
    # Показываем меню водителя
    bot.send_message(
        message.chat.id,
        f"🚗 <b>Меню водителя</b>\n\n"
        f"Здравствуйте, {driver['first_name']}!\n"
        f"Автомобиль: {driver['car_number']}",
        parse_mode="HTML",
        reply_markup=get_driver_keyboard()
    )

def get_driver_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🚗 Изменить статус"))
    markup.add(telebot.types.KeyboardButton("📋 Мои заказы"), telebot.types.KeyboardButton("💰 Мой заработок"))
    markup.add(telebot.types.KeyboardButton("🔙 Главное меню"))
    return markup

# Обработчик изменения статуса водителя
@bot.message_handler(func=lambda message: message.text == "🚗 Изменить статус")
def change_driver_status(message):
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь как водитель
    driver = get_driver_by_id(user_id)
    
    if not driver or not driver['is_approved']:
        bot.send_message(
            message.chat.id,
            "У вас нет доступа к этой функции.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Показываем текущий статус и предлагаем изменить
    status_map = {
        "ON_DUTY": "На линии",
        "ON_ORDER": "На заказе", 
        "OFF_DUTY": "Дома"
    }
    current_status = status_map.get(driver['status'], driver['status'])
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🟢 На линии", callback_data="status:ON_DUTY"))
    markup.add(telebot.types.InlineKeyboardButton("🔴 Дома", callback_data="status:OFF_DUTY"))
    
    bot.send_message(
        message.chat.id,
        f"Ваш текущий статус: <b>{current_status}</b>\n\n"
        f"Выберите новый статус:",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("status:"))
def process_status_change(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки статуса")
        return
    
    status = parts[1]
    user_id = call.from_user.id
    
    # Обновляем статус водителя в БД
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM drivers WHERE user_id = ?', (user_id,))
    driver = cursor.fetchone()
    
    if not driver:
        bot.answer_callback_query(call.id, "Ошибка: водитель не найден")
        conn.close()
        return
    
    old_status = driver['status']
    cursor.execute('UPDATE drivers SET status = ? WHERE user_id = ?', (status, user_id))
    conn.commit()
    conn.close()
    
    # Уведомляем водителя
    status_map = {
        "ON_DUTY": "На линии",
        "ON_ORDER": "На заказе",
        "OFF_DUTY": "Дома"
    }
    new_status_text = status_map.get(status, status)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Ваш статус изменен на: <b>{new_status_text}</b>",
        parse_mode="HTML",
        reply_markup=None
    )
    
    # Уведомляем админа
    old_status_text = status_map.get(old_status, old_status)
    admin_text = f"🔄 <b>Изменение статуса водителя</b>\n\n"
    admin_text += f"👤 <b>Водитель:</b> {driver['first_name']}\n"
    admin_text += f"🚗 <b>Госномер:</b> {driver['car_number']}\n"
    admin_text += f"📊 <b>Статус:</b> {old_status_text} ➡️ {new_status_text}"
    
    send_to_admins(
        admin_text,
        parse_mode="HTML"
    )

# Обработчик "Мои заказы" для водителей
@bot.message_handler(func=lambda message: message.text == "📋 Мои заказы" and get_driver_by_id(message.from_user.id))
def driver_orders(message):
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь как водитель
    driver = get_driver_by_id(user_id)
    
    if not driver or not driver['is_approved']:
        bot.send_message(
            message.chat.id,
            "У вас нет доступа к этой функции.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Получаем заказы водителя (сначала активные, потом последние завершенные)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM orders WHERE driver_id = ? 
        ORDER BY 
            CASE 
                WHEN status IN ('IN_PROGRESS', 'ACCEPTED', 'ARRIVED') THEN 0 
                ELSE 1 
            END,
            created_at DESC 
        LIMIT 10
    ''', (driver['id'],))
    orders = cursor.fetchall()
    
    if not orders:
        bot.send_message(
            message.chat.id,
            "У вас пока нет заказов.",
            reply_markup=get_driver_keyboard()
        )
        conn.close()
        return
    
    # Подсчитываем активные заказы
    active_orders = [order for order in orders if order['status'] in ('IN_PROGRESS', 'ACCEPTED', 'ARRIVED')]
    completed_orders = [order for order in orders if order['status'] not in ('IN_PROGRESS', 'ACCEPTED', 'ARRIVED')]
    
    # Отправляем заголовок с количеством активных заказов
    if active_orders:
        header_text = f"🚕 <b>Ваши заказы</b>\n\n📋 Активных заказов: {len(active_orders)}\n{'='*30}"
        bot.send_message(message.chat.id, header_text, parse_mode="HTML")
    
    # Отправляем информацию о каждом заказе
    for order in orders:
        # Получаем номер заказа для клиента
        cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order['id']))
        client_order_number = cursor.fetchone()[0]
        
        order_text = f"🚕 <b>Заказ #{client_order_number}</b> (ID: {order['id']})\n\n"
        order_text += f"📍 <b>Откуда:</b> {order['from_address']}\n"
        order_text += f"🏁 <b>Куда:</b> {order['to_address']}\n"
        
        if order['comment']:
            order_text += f"💬 <b>Комментарий:</b> {order['comment']}\n"
        
        if order['price']:
            order_text += f"💰 <b>Цена:</b> {order['price']} руб.\n"
        
        # Добавляем запланированное время для водителя
        if order.get('scheduled_at'):
            try:
                scheduled_time = datetime.datetime.fromisoformat(order['scheduled_at']).strftime('%d.%m %H:%M')
                order_text += f"🕐 <b>Время подачи:</b> {scheduled_time}\n"
            except:
                pass
        
        status_map = {
            "NEW": "Новый",
            "PRICE_OFFERED": "Предложена цена",
            "ACCEPTED": "Принят",
            "DECLINED": "Отклонен",
            "IN_PROGRESS": "Выполняется",
            "COMPLETED": "Завершен",
            "CANCELLED": "Отменен"
        }
        order_text += f"📊 <b>Статус:</b> {status_map.get(order['status'], order['status'])}\n"
        order_text += f"🕒 <b>Создан:</b> {order['created_at']}\n"
        
        # Добавляем кнопку завершения заказа, если он в процессе
        markup = None
        if order['status'] == 'IN_PROGRESS':
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("✅ Заказ выполнен", callback_data=f"complete_order:{order['id']}"))
        
        bot.send_message(
            message.chat.id,
            order_text,
            parse_mode="HTML",
            reply_markup=markup
        )
    
    conn.close()

# Обработчик завершения заказа водителем
@bot.callback_query_handler(func=lambda call: call.data.startswith("complete_order:"))
def complete_order_callback(call):
    parts = call.data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Ошибка обработки")
        return
    
    order_id = int(parts[1])
    user_id = call.from_user.id
    
    # Получаем данные о заказе
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order:
        bot.answer_callback_query(call.id, "Ошибка: заказ не найден")
        conn.close()
        return
    
    # Проверяем, что заказ назначен на этого водителя
    driver = get_driver_by_id(user_id)
    
    if not driver or driver['id'] != order['driver_id']:
        bot.answer_callback_query(call.id, "Ошибка: заказ не назначен на вас")
        conn.close()
        return
    
    # Обновляем статус заказа
    cursor.execute('UPDATE orders SET status = ?, completed_at = ? WHERE id = ?', ('COMPLETED', datetime.datetime.now(datetime.timezone.utc).isoformat(), order_id))
    
    # Проверяем, есть ли у водителя другие активные заказы
    cursor.execute('SELECT COUNT(*) FROM orders WHERE driver_id = ? AND status IN ("IN_PROGRESS", "ACCEPTED", "ARRIVED") AND id != ?', (driver['id'], order_id))
    other_active_orders = cursor.fetchone()[0]
    
    # Обновляем статус водителя только если нет других активных заказов
    if other_active_orders == 0:
        cursor.execute('UPDATE drivers SET status = ? WHERE id = ?', ('ON_DUTY', driver['id']))
    
    # Добавляем запись о заработке
    cursor.execute('INSERT INTO earnings (driver_id, order_id, amount) VALUES (?, ?, ?)', (driver['id'], order_id, order['price']))
    
    conn.commit()
    
    # Получаем клиента
    cursor.execute('SELECT user_id FROM users WHERE id = ?', (order['client_id'],))
    client = cursor.fetchone()
    client_user_id = client['user_id'] if client else None
    
    # Получаем номер заказа для клиента
    cursor.execute('SELECT COUNT(*) FROM orders WHERE client_id = ? AND id <= ?', (order['client_id'], order_id))
    client_order_number = cursor.fetchone()[0]
    
    conn.close()
    
    # Удаляем кнопки из предыдущего сообщения
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    # Уведомляем водителя
    completion_message = f"✅ Заказ #{client_order_number} успешно завершен.\n" \
                        f"Сумма {order['price']} руб. добавлена к вашему заработку."
    
    if other_active_orders > 0:
        completion_message += f"\n\n📋 У вас осталось активных заказов: {other_active_orders}"
    else:
        completion_message += f"\n\n🏠 Вы переведены в статус 'На линии'"
    
    bot.send_message(
        call.message.chat.id,
        completion_message,
        reply_markup=get_driver_keyboard()
    )
    
    # Уведомляем клиента и предлагаем оценить поездку
    if client_user_id:
        client_text = f"✅ <b>Поездка завершена</b>\n\n"
        client_text += f"Заказ #{client_order_number} выполнен.\n"
        client_text += f"Спасибо за использование нашего сервиса!\n\n"
        client_text += "Пожалуйста, оцените поездку:"
        
        markup = telebot.types.InlineKeyboardMarkup()
        for i in range(1, 6):
            markup.add(telebot.types.InlineKeyboardButton(f"⭐ {i}", callback_data=f"rate:{order_id}:{i}"))
        
        bot.send_message(
            client_user_id,
            client_text,
            parse_mode="HTML",
            reply_markup=markup
        )
    
    # Уведомляем админа
    send_to_admins(
        f"✅ Заказ #{client_order_number} (ID: {order_id}) завершен водителем {driver['first_name']} ({driver['car_number']}).\n"
        f"Сумма: {order['price']} руб."
    )

# Обработчик "Мой заработок" для водителей
@bot.message_handler(func=lambda message: message.text == "💰 Мой заработок")
def driver_earnings(message):
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь как водитель
    driver = get_driver_by_id(user_id)
    
    if not driver or not driver['is_approved']:
        bot.send_message(
            message.chat.id,
            "У вас нет доступа к этой функции.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Получаем заработок водителя
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Общий заработок
    cursor.execute('SELECT SUM(amount) FROM earnings WHERE driver_id = ?', (driver['id'],))
    total_earnings = cursor.fetchone()[0] or 0
    
    # Заработок за текущий месяц
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_month = datetime.datetime(now.year, now.month, 1, tzinfo=datetime.timezone.utc).isoformat()
    cursor.execute('SELECT SUM(amount) FROM earnings WHERE driver_id = ? AND date >= ?', (driver['id'], start_of_month))
    monthly_earnings = cursor.fetchone()[0] or 0
    
    # Заработок за сегодня
    start_of_day = datetime.datetime.combine(now.date(), datetime.time.min, tzinfo=datetime.timezone.utc).isoformat()
    cursor.execute('SELECT SUM(amount) FROM earnings WHERE driver_id = ? AND date >= ?', (driver['id'], start_of_day))
    daily_earnings = cursor.fetchone()[0] or 0
    
    conn.close()
    
    # Формируем сообщение
    earnings_text = f"💰 <b>Ваш заработок</b>\n\n"
    earnings_text += f"Сегодня: {daily_earnings} руб.\n"
    earnings_text += f"За месяц: {monthly_earnings} руб.\n"
    earnings_text += f"Всего: {total_earnings} руб."
    
    bot.send_message(
        message.chat.id,
        earnings_text,
        parse_mode="HTML",
        reply_markup=get_driver_keyboard()
    )

# Запуск бота
if __name__ == "__main__":
    logger.info("Запуск бота Такси Светлогорск39")
    
    # Инициализация базы данных
    init_db()
    
    # Установка команд бота
    bot.set_my_commands([
        telebot.types.BotCommand("/start", "Начать работу с ботом"),
        telebot.types.BotCommand("/help", "Показать справку"),
        telebot.types.BotCommand("/order", "Заказать такси"),
        telebot.types.BotCommand("/profile", "Ваш профиль"),
        telebot.types.BotCommand("/driver", "Меню водителя"),
        telebot.types.BotCommand("/admin", "Админ-панель (только для администраторов)")
    ])
    
    # Получение информации о боте
    bot_info = bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username} ({bot_info.first_name})")
    
    # Запуск бота
    try:
        logger.info("Бот начал прослушивание сообщений")
        
        # Бесконечный цикл с обработкой ошибок
        while True:
            try:
                bot.polling(none_stop=True, interval=1, timeout=30)
            except Exception as e:
                logger.error(f"Ошибка при polling: {e}")
                logger.info("Перезапуск polling через 5 секунд...")
                import time
                time.sleep(5)
                continue
                
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        logger.error(f"Трассировка: {traceback.format_exc()}")
    finally:
        logger.info("Бот завершил работу")
