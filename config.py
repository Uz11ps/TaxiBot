BOT_TOKEN = "8253612167:AAFSf1oATbC2ZsHyREh9JTyZVloV_Dou_OI"
ADMIN_ID = 916948327
ADMIN_IDS = [916948327, 8386636652]  # Список всех администраторов
DATABASE_URL = "sqlite:///taxi.db"

# Настройки города
CITY_NAME = "Светлогорск"
CITY_RADIUS = 10  # в километрах

# Популярные направления
POPULAR_DESTINATIONS = [
    "пгт Янтарный",
    "Аэропорт Храброво",
    "г.Зеленоградск",
    "г.Калининград",
    "г.Балтийск",
    "Куршская коса",
    "г.Советск",
    "г.Черняховск"
]

# Статусы водителей
DRIVER_STATUSES = {
    "ON_DUTY": "На линии",
    "ON_ORDER": "На заказе",
    "OFF_DUTY": "Дома",
    "ARRIVED": "На месте"
}

# Статусы заказов
ORDER_STATUSES = {
    "NEW": "Новый",
    "PRICE_OFFERED": "Предложена цена",
    "ACCEPTED": "Принят",
    "DECLINED": "Отклонен",
    "IN_PROGRESS": "Выполняется",
    "COMPLETED": "Завершен",
    "CANCELLED": "Отменен"
}
