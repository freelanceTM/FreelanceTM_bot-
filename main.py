import os
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Awaitable

from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, TelegramObject
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keep_alive import keep_alive

# =============================================================================
# CONFIGURATION
# =============================================================================
# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8175482134:AAHqRmvnTnq2StWQdD7CXoVpqsDPde74ccI")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@FreelanceTM_channel")

# Debug logging
print(f"BOT_TOKEN found: {'Yes' if BOT_TOKEN else 'No'}")
print(f"BOT_TOKEN length: {len(BOT_TOKEN) if BOT_TOKEN else 0}")
print(f"ADMIN_IDS: {ADMIN_IDS}")
print(f"REQUIRED_CHANNEL: {REQUIRED_CHANNEL}")

# Convert URL format to username format if needed
if REQUIRED_CHANNEL.startswith("https://t.me/"):
    REQUIRED_CHANNEL = "@" + REQUIRED_CHANNEL.replace("https://t.me/", "")

# Database configuration
DATA_DIR = "data"

# Business configuration
COMMISSION_RATE = 0.10  # 10% commission
WITHDRAWAL_COMMISSION = 0.10  # 10% withdrawal commission

# =============================================================================
# DATABASE OPERATIONS
# =============================================================================
logger = logging.getLogger(__name__)

# Global database variables
users_db = {}
orders_db = {}
responses_db = {}
reviews_db = {}
withdrawals_db = {}
services_db = {}
counters = {"user_id": 1, "order_id": 1, "withdrawal_id": 1, "service_id": 1}

def init_database():
    """Initialize database"""
    global users_db, orders_db, responses_db, reviews_db, withdrawals_db, counters

    # Create data directory if not exists
    Path(DATA_DIR).mkdir(exist_ok=True)

    # Load data from files
    users_db = load_json(f"{DATA_DIR}/users.json", {})
    orders_db = load_json(f"{DATA_DIR}/orders.json", {})
    responses_db = load_json(f"{DATA_DIR}/responses.json", {})
    reviews_db = load_json(f"{DATA_DIR}/reviews.json", {})
    withdrawals_db = load_json(f"{DATA_DIR}/withdrawals.json", {})
    services_db = load_json(f"{DATA_DIR}/services.json", {})

    # Load counters with fallback to root directory
    counters = load_json(f"{DATA_DIR}/counters.json", {"user_id": 1, "order_id": 1, "withdrawal_id": 1, "service_id": 1})
    if counters == {"user_id": 1, "order_id": 1, "withdrawal_id": 1, "service_id": 1}:
        # Try loading from root directory if data directory doesn't have it
        counters = load_json("counters.json", {"user_id": 1, "order_id": 1, "withdrawal_id": 1, "service_id": 1})

    logger.info(f"Database initialized: {len(users_db)} users, {len(orders_db)} orders")

def load_json(filename: str, default: Any) -> Any:
    """Load data from JSON file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        logger.error(f"JSON decode error in file {filename}")
        return default

def save_json(filename: str, data: Any):
    """Save data to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving to file {filename}: {e}")

def save_all_data():
    """Save all data to files"""
    save_json(f"{DATA_DIR}/users.json", users_db)
    save_json(f"{DATA_DIR}/orders.json", orders_db)
    save_json(f"{DATA_DIR}/responses.json", responses_db)
    save_json(f"{DATA_DIR}/reviews.json", reviews_db)
    save_json(f"{DATA_DIR}/withdrawals.json", withdrawals_db)
    save_json(f"{DATA_DIR}/services.json", services_db)
    save_json(f"{DATA_DIR}/counters.json", counters)

# User operations
def get_user(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    return users_db.get(str(user_id))

def create_user(user_id: int, user_data: Dict) -> Dict:
    """Create new user"""
    user_data['id'] = user_id
    user_data['created_at'] = datetime.now().isoformat()
    user_data['balance'] = 0.0  # Initialize balance for new users
    user_data['frozen_balance'] = 0.0  # Initialize frozen balance
    users_db[str(user_id)] = user_data
    save_all_data()
    return user_data

def update_user(user_id: int, updates: Dict) -> Optional[Dict]:
    """Update user data"""
    if str(user_id) in users_db:
        users_db[str(user_id)].update(updates)
        save_all_data()
        return users_db[str(user_id)]
    return None

def get_users_by_role(role: str) -> List[Dict]:
    """Get users by role"""
    return [user for user in users_db.values() if user.get('role') == role]

# Order operations
def get_order(order_id: int) -> Optional[Dict]:
    """Get order by ID"""
    return orders_db.get(str(order_id))

def create_order(order_data: Dict) -> Dict:
    """Create new order"""
    order_id = counters["order_id"]
    counters["order_id"] += 1

    order_data['id'] = order_id
    order_data['created_at'] = datetime.now().isoformat()
    order_data['status'] = 'active'
    orders_db[str(order_id)] = order_data
    save_all_data()
    return order_data

def update_order(order_id: int, updates: Dict) -> Optional[Dict]:
    """Update order"""
    if str(order_id) in orders_db:
        orders_db[str(order_id)].update(updates)
        save_all_data()
        return orders_db[str(order_id)]
    return None

def get_orders_by_client(client_id: int) -> List[Dict]:
    """Get orders by client"""
    return [order for order in orders_db.values() if order.get('client_id') == client_id]

def get_active_orders() -> List[Dict]:
    """Get active orders"""
    return [order for order in orders_db.values() if order.get('status') == 'active']

def get_active_orders_for_freelancer(freelancer_id: int) -> List[Dict]:
    """Get active orders excluding user's own orders and orders already responded to"""
    active_orders = []
    for order in orders_db.values():
        if order.get('status') != 'active':
            continue

        # Don't show user's own orders
        if order.get('client_id') == freelancer_id:
            continue

        # Don't show orders already responded to
        order_responses = get_responses(order['id'])
        if any(response['freelancer_id'] == freelancer_id for response in order_responses):
            continue

        active_orders.append(order)
    return active_orders

def get_orders_by_category(category: str) -> List[Dict]:
    """Get orders by category"""
    return [order for order in orders_db.values() if order.get('category') == category and order.get('status') == 'active']

# Response operations
def add_response(order_id: int, response_data: Dict) -> bool:
    """Add response to order"""
    if str(order_id) not in responses_db:
        responses_db[str(order_id)] = []

    # Check if freelancer already responded
    for response in responses_db[str(order_id)]:
        if response['freelancer_id'] == response_data['freelancer_id']:
            return False

    response_data['created_at'] = datetime.now().isoformat()
    responses_db[str(order_id)].append(response_data)
    save_all_data()
    return True

def get_responses(order_id: int) -> List[Dict]:
    """Get responses to order"""
    return responses_db.get(str(order_id), [])

def get_freelancer_responses(freelancer_id: int) -> List[Dict]:
    """Get freelancer responses"""
    responses = []
    for order_id, order_responses in responses_db.items():
        for response in order_responses:
            if response['freelancer_id'] == freelancer_id:
                order = get_order(int(order_id))
                if order:
                    response['order'] = order
                    responses.append(response)
    return responses

# Review operations
def add_review(order_id: int, reviewer_id: int, reviewed_id: int, review_data: Dict) -> bool:
    """Add review"""
    review_key = f"{order_id}_{reviewer_id}_{reviewed_id}"

    # Check if review already exists
    if review_key in reviews_db:
        return False

    review_data.update({
        'order_id': order_id,
        'reviewer_id': reviewer_id,
        'reviewed_id': reviewed_id,
        'created_at': datetime.now().isoformat()
    })
    reviews_db[review_key] = review_data
    save_all_data()
    return True

def get_user_reviews(user_id: int) -> List[Dict]:
    """Get reviews about user"""
    return [review for review in reviews_db.values() if review['reviewed_id'] == user_id]

def get_user_average_rating(user_id: int) -> float:
    """Get user average rating"""
    reviews = get_user_reviews(user_id)
    if not reviews:
        return 0.0

    total_rating = sum(review['rating'] for review in reviews)
    return total_rating / len(reviews)

def can_leave_review(order_id: int, reviewer_id: int, reviewed_id: int) -> bool:
    """Check if user can leave review"""
    order = get_order(order_id)
    if not order or order['status'] != 'completed':
        return False

    # Check if user participated in order
    if reviewer_id not in [order['client_id'], order.get('selected_freelancer')]:
        return False

    # Check if review already exists
    review_key = f"{order_id}_{reviewer_id}_{reviewed_id}"
    return review_key not in reviews_db

def get_stats() -> Dict:
    """Get platform statistics"""
    return {
        'total_users': len(users_db),
        'freelancers': len(get_users_by_role('freelancer')),
        'clients': len(get_users_by_role('client')),
        'total_orders': len(orders_db),
        'active_orders': len(get_active_orders()),
        'completed_orders': len([o for o in orders_db.values() if o.get('status') == 'completed']),
        'total_reviews': len(reviews_db)
    }

# Withdrawal operations
def get_user_balance(user_id: int) -> float:
    """Get user balance"""
    user = get_user(user_id)
    if user:
        # Initialize balance if not exists
        if 'balance' not in user:
            user['balance'] = 0.0
            save_all_data()
        return user.get('balance', 0.0)
    return 0.0

def add_to_balance(user_id: int, amount: float) -> bool:
    """Add amount to user balance"""
    user = get_user(user_id)
    if user:
        current_balance = user.get('balance', 0.0)
        user['balance'] = current_balance + amount
        save_all_data()
        return True
    return False

def subtract_from_balance(user_id: int, amount: float) -> bool:
    """Subtract amount from user balance"""
    user = get_user(user_id)
    if user:
        current_balance = user.get('balance', 0.0)
        if current_balance >= amount:
            user['balance'] = current_balance - amount
            save_all_data()
            return True
    return False

def create_withdrawal_request(user_id: int, amount: float, phone: str) -> Dict:
    """Create withdrawal request"""
    withdrawal_id = counters["withdrawal_id"]
    counters["withdrawal_id"] += 1

    withdrawal_data = {
        'id': withdrawal_id,
        'user_id': user_id,
        'amount': amount,
        'phone': phone,
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'balance_before': get_user_balance(user_id)
    }

    withdrawals_db[str(withdrawal_id)] = withdrawal_data
    save_all_data()
    return withdrawal_data

def get_withdrawal_request(withdrawal_id: int) -> Optional[Dict]:
    """Get withdrawal request by ID"""
    return withdrawals_db.get(str(withdrawal_id))

def update_withdrawal_request(withdrawal_id: int, updates: Dict) -> Optional[Dict]:
    """Update withdrawal request"""
    if str(withdrawal_id) in withdrawals_db:
        withdrawals_db[str(withdrawal_id)].update(updates)
        save_all_data()
        return withdrawals_db[str(withdrawal_id)]
    return None

def get_pending_withdrawals() -> List[Dict]:
    """Get pending withdrawal requests"""
    return [w for w in withdrawals_db.values() if w.get('status') == 'pending']

def get_user_withdrawals(user_id: int) -> List[Dict]:
    """Get user withdrawal requests"""
    return [w for w in withdrawals_db.values() if w.get('user_id') == user_id]

# Service operations
def create_service(service_data: Dict) -> Dict:
    """Create new service"""
    service_id = counters["service_id"]
    counters["service_id"] += 1

    service_data['id'] = service_id
    service_data['created_at'] = datetime.now().isoformat()
    services_db[str(service_id)] = service_data
    save_all_data()
    return service_data

def get_service(service_id: int) -> Optional[Dict]:
    """Get service by ID"""
    return services_db.get(str(service_id))

def update_service(service_id: int, updates: Dict) -> Optional[Dict]:
    """Update service"""
    if str(service_id) in services_db:
        services_db[str(service_id)].update(updates)
        save_all_data()
        return services_db[str(service_id)]
    return None

def delete_service(service_id: int) -> bool:
    """Delete service"""
    if str(service_id) in services_db:
        del services_db[str(service_id)]
        save_all_data()
        return True
    return False

def get_user_services(user_id: int) -> List[Dict]:
    """Get services by user"""
    return [service for service in services_db.values() if service.get('user_id') == user_id]

def get_services_by_category(category: str) -> List[Dict]:
    """Get services by category"""
    return [service for service in services_db.values() if service.get('category') == category]

def get_all_services() -> List[Dict]:
    """Get all services"""
    return list(services_db.values())

# Service order operations
def create_service_order(order_data: Dict) -> Dict:
    """Create new service order"""
    order_id = counters["order_id"]
    counters["order_id"] += 1

    order_data['id'] = order_id
    order_data['created_at'] = datetime.now().isoformat()
    order_data['status'] = 'waiting_payment'
    order_data['type'] = 'service_order'
    orders_db[str(order_id)] = order_data
    save_all_data()
    return order_data

def get_user_frozen_balance(user_id: int) -> float:
    """Get user frozen balance"""
    user = get_user(user_id)
    if user:
        return user.get('frozen_balance', 0.0)
    return 0.0

def freeze_balance(user_id: int, amount: float) -> bool:
    """Freeze amount in user balance"""
    user = get_user(user_id)
    if user:
        current_balance = user.get('balance', 0.0)
        if current_balance >= amount:
            user['balance'] = current_balance - amount
            user['frozen_balance'] = user.get('frozen_balance', 0.0) + amount
            save_all_data()
            return True
    return False

def unfreeze_balance(user_id: int, amount: float) -> bool:
    """Unfreeze amount from user balance"""
    user = get_user(user_id)
    if user:
        frozen = user.get('frozen_balance', 0.0)
        if frozen >= amount:
            user['frozen_balance'] = frozen - amount
            user['balance'] = user.get('balance', 0.0) + amount
            save_all_data()
            return True
    return False

def transfer_frozen_to_user(from_user_id: int, to_user_id: int, amount: float) -> bool:
    """Transfer frozen balance from one user to another"""
    from_user = get_user(from_user_id)
    to_user = get_user(to_user_id)
    
    if from_user and to_user:
        frozen = from_user.get('frozen_balance', 0.0)
        if frozen >= amount:
            from_user['frozen_balance'] = frozen - amount
            to_user['balance'] = to_user.get('balance', 0.0) + amount
            save_all_data()
            return True
    return False

def create_balance_request(user_id: int, request_type: str, amount: float, phone: str = None) -> Dict:
    """Create balance request (topup or withdraw)"""
    request_id = counters["withdrawal_id"]
    counters["withdrawal_id"] += 1

    request_data = {
        'id': request_id,
        'user_id': user_id,
        'type': request_type,  # 'topup' or 'withdraw'
        'amount': amount,
        'phone': phone,
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'balance_before': get_user_balance(user_id)
    }

    withdrawals_db[str(request_id)] = request_data
    save_all_data()
    return request_data

# =============================================================================
# TEXT CONSTANTS
# =============================================================================
TEXTS = {
    "ru": {
        "welcome": "🎉 Добро пожаловать в FreelanceTM!\n\n💼 Платформа для фрилансеров и заказчиков\n🔒 Гарантия безопасных сделок\n⭐ Система отзывов и рейтингов\n📢 Новости и обновления платформы\n🤝 Поддержка и помощь пользователям\n\nДля продолжения работы необходимо подписаться на наш канал:",
        "choose_language": "🌐 Выберите язык / Dil saýlaň:",
        "choose_role": "👤 Выберите вашу роль:",
        "registration_name": "👤 Введите ваше имя:",
        "registration_skills": "💼 Укажите ваши навыки:",
        "registration_description": "📝 Расскажите о себе:",
        "registration_contact": "📞 Укажите контакт для связи:",
        "registration_complete": "✅ Регистрация завершена! Добро пожаловать в FreelanceTM!",
        "main_menu_freelancer": "🏠 Главное меню фрилансера",
        "main_menu_client": "🏠 Главное меню заказчика",
        "btn_create_order": "➕ Создать заказ",
        "btn_view_orders": "📋 Просмотр заказов",
        "btn_my_orders": "📋 Мои заказы",
        "btn_my_responses": "📤 Мои отклики",
        "btn_profile": "👤 Профиль",
        "btn_reviews": "📝 Отзывы",
        "btn_help": "❓ Помощь",
        "btn_settings": "⚙️ Настройки",
        "btn_partners": "🤝 Партнёры",
        "btn_back": "◀️ Назад",
        "settings_menu": "⚙️ Настройки",
        "check_subscription": "✅ Проверить подписку",
        "subscription_required": "❌ Для использования бота необходимо подписаться на канал:",
        "order_title": "📝 Введите название заказа:",
        "order_description": "📋 Введите описание заказа:",
        "order_budget": "💰 Введите бюджет (в TMT):",
        "order_deadline": "⏰ Введите срок выполнения (в днях):",
        "order_contact": "📞 Введите контакт для связи:",
        "order_created": "✅ Заказ успешно создан!",
        "no_orders": "📭 Нет доступных заказов",
        "orders_list": "📋 Доступные заказы:",
        "my_orders_list": "📋 Ваши заказы:",
        "no_my_orders": "📭 У вас нет заказов",
        "respond_to_order": "📤 Откликнуться",
        "response_sent": "✅ Отклик отправлен!",
        "response_exists": "❌ Вы уже откликнулись на этот заказ",
        "new_response": "📨 Новый отклик на ваш заказ!",
        "btn_select_freelancer": "✅ Выбрать фрилансера",
        "btn_change_role": "🔄 Сменить роль",
        "btn_change_language": "🌐 Сменить язык",
        "btn_pay_guarantee": "💰 Оплатить",
        "btn_complete_order": "✅ Завершить заказ",
        "btn_confirm_completion": "✅ Подтвердить завершение",
        "payment_guarantee": "🛡️ Гарантийная оплата",
        "guarantee_info": "💰 Сумма к оплате: {amount} TMT + {commission} TMT (комиссия 10%)\nОбщая сумма: {total} TMT",
        "guarantee_request_sent": "✅ Запрос на оплату отправлен администратору",
        "order_selected": "✅ Фрилансер выбран",
        "freelancer_selected": "🎉 Вас выбрали для выполнения заказа!\n⚠️ НЕ НАЧИНАЙТЕ РАБОТУ до подтверждения оплаты администратором!",
        "payment_confirmed": "✅ Оплата подтверждена! Можете начинать работу.",
        "order_completed": "✅ Заказ завершен",
        "waiting_payment_confirmation": "⏳ Ожидается подтверждение оплаты от администратора",
        "both_confirm_required": "⚠️ Для завершения заказа требуется подтверждение от обеих сторон",
        "admin_payment_request": "💰 Новый запрос на гарантийную оплату",
        "admin_confirm_payment": "✅ Подтвердить оплату",
        "admin_release_payment": "💸 Выплатить фрилансеру",
        "error_not_freelancer": "❌ Эта функция доступна только фрилансерам",
        "error_not_client": "❌ Эта функция доступна только заказчикам",
        "error_order_not_found": "❌ Заказ не найден",
        "error_not_your_order": "❌ Это не ваш заказ",
        "error_user_not_found": "❌ Пользователь не найден",
        "profile_info": "👤 Ваш профиль:",
        "edit_profile": "✏️ Редактировать профиль",
        "edit_name": "✏️ Изменить имя",
        "edit_skills": "✏️ Изменить навыки",
        "edit_description": "✏️ Изменить описание",
        "edit_contact": "✏️ Изменить контакт",
        "profile_updated": "✅ Профиль обновлен",
        "leave_review": "⭐ Оставить отзыв",
        "select_rating": "⭐ Выберите оценку:",
        "enter_review_text": "📝 Напишите отзыв:",
        "review_added": "✅ Отзыв добавлен",
        "review_error": "❌ Не удалось добавить отзыв",
        "no_reviews": "📭 Отзывов пока нет",
        "reviews_about_you": "📝 Отзывы о вас:",
        "btn_balance": "💰 Баланс",
        "btn_withdraw": "💸 Вывод средств",
        "balance_info": "💰 Ваш баланс: {balance} TMT",
        "withdraw_request": "💸 Вывод средств",
        "withdraw_amount": "💰 Введите сумму для вывода:",
        "withdraw_phone": "📞 Введите номер телефона для перевода:",
        "withdraw_confirm": "Вы хотите вывести {amount} TMT на номер {phone}?\n\n⚠️ Комиссия за вывод: {commission} TMT\nК выводу: {final_amount} TMT",
        "btn_confirm_withdraw": "✅ Подтвердить",
        "btn_cancel_withdraw": "❌ Отменить",
        "withdraw_success": "✅ Запрос на вывод отправлен администратору",
        "withdraw_insufficient_funds": "❌ Недостаточно средств на балансе",
        "withdraw_invalid_amount": "❌ Некорректная сумма",
        "admin_new_withdrawal": "💸 Новый запрос на вывод",
        "admin_withdrawal_info": "👤 Пользователь: {user_name} (ID: {user_id})\n💰 Сумма: {amount} TMT\n📞 Телефон: {phone}\n📊 Баланс до: {balance_before} TMT\n📊 Баланс после: {balance_after} TMT",
        "btn_admin_confirm_withdrawal": "✅ Подтвердить вывод",
        "btn_admin_reject_withdrawal": "❌ Отклонить",
        "btn_withdrawal_requests": "💸 Заявки на вывод",
        "withdrawal_confirmed": "✅ Вывод подтвержден",
        "withdrawal_rejected": "❌ Вывод отклонен",
        "no_withdrawal_requests": "📭 Нет заявок на вывод",
        "btn_admin_panel": "⚙️ Админ панель",
        "partners_title": "🤝 Наши партнёры",
        "partners_finance_tm": "💰 Финансовый канал FinanceTM\n📈 Актуальная информация о курсах валют, инвестициях и финансовых новостях Туркменистана",
        "btn_my_services": "🧰 Мои услуги",
        "btn_find_freelancer": "🔍 Найти фрилансера",
        "btn_add_service": "➕ Добавить услугу",
        "btn_view_my_services": "📋 Мои услуги",
        "btn_contact": "📩 Связаться",
        "btn_order_service": "✅ Заказать",
        "btn_my_balance": "💰 Мой баланс",
        "btn_topup_balance": "➕ Пополнить",
        "service_order_confirm": "Вы хотите заказать эту услугу?\n\n💰 Стоимость: {price}\n⚠️ Сумма будет заблокирована на вашем балансе до завершения работы.",
        "service_order_success": "✅ Заказ оформлен! Средства заблокированы. Фрилансер получил уведомление.",
        "service_order_insufficient": "❌ Недостаточно средств на балансе",
        "balance_info_client": "💰 Мой баланс\n\n💳 Доступно: {balance} TMT\n🔒 Заморожено: {frozen} TMT\n💵 Всего: {total} TMT",
        "topup_amount": "💰 Введите сумму для пополнения (в TMT):",
        "topup_request_sent": "✅ Запрос на пополнение отправлен администратору",
        "admin_topup_request": "💰 Новый запрос на пополнение баланса",
        "admin_topup_info": "👤 Пользователь: {user_name} (ID: {user_id})\n💰 Сумма: {amount} TMT\n📊 Текущий баланс: {balance} TMT",
        "btn_admin_confirm_topup": "✅ Подтвердить пополнение",
        "topup_confirmed": "✅ Баланс пополнен на {amount} TMT",
        "freelancer_new_order": "🎉 Вас выбрали для выполнения услуги!\n\n📋 Услуга: {service_title}\n👤 Заказчик: {client_name}\n💰 Сумма: {amount} TMT\n\n⏳ Ожидайте подтверждение от администратора",
        "admin_service_order": "📋 Новый заказ услуги требует подтверждения",
        "service_add_category": "🏷️ Выберите категорию услуги:",
        "service_add_title": "📝 Введите название услуги:",
        "service_add_description": "📋 Введите описание услуги:",
        "service_add_price": "💰 Введите цену (например: 100 TMT или 'по договорённости'):",
        "service_confirm": "✅ Подтвердить добавление услуги?",
        "service_added": "✅ Услуга успешно добавлена! Теперь заказчики смогут вас найти!",
        "service_limit_reached": "❌ Максимум 3 активные услуги на пользователя",
        "no_services": "📭 У вас нет активных услуг",
        "my_services_list": "🧰 Ваши услуги:",
        "no_services_in_category": "📭 В этой категории пока нет услуг",
        "services_in_category": "🔍 Вот что мы нашли по выбранной категории:",
        "service_deleted": "✅ Услуга удалена",
        "btn_delete_service": "🗑️ Удалить",
        "btn_edit_service": "✏️ Редактировать",
        "select_service_action": "Выберите действие с услугой:",
    },
    "tm": {
        "welcome": "🎉 FreelanceTM-a hoş geldiňiz!\n\n💼 Frilanserler we müşderiler üçin platforma\n🔒 Howpsuz geleşikleriň kepilligi\n⭐ Syn we reýting ulgamy\n📢 Platformanyň täzelikleri we täzelenmeler\n🤝 Ulanyjylara goldaw we kömek\n\nIşlemegi dowam etdirmek üçin kanalymyza ýazylyň:",
        "choose_language": "🌐 Выберите язык / Dil saýlaň:",
        "choose_role": "👤 Rolüňizi saýlaň:",
        "registration_name": "👤 Adyňyzy giriziň:",
        "registration_skills": "💼 Başarnyklaryňyzy görkeziň:",
        "registration_description": "📝 Öziňiz hakda aýdyň:",
        "registration_contact": "📞 Aragatnaşyk üçin kontakt görkeziň:",
        "registration_complete": "✅ Hasaba alyş tamamlandy! FreelanceTM-a hoş geldiňiz!",
        "main_menu_freelancer": "🏠 Frilanseriniň esasy menýusy",
        "main_menu_client": "🏠 Müşderiniň esasy menýusy",
        "btn_create_order": "➕ Sargyt döretmek",
        "btn_view_orders": "📋 Sargytlary görmek",
        "btn_my_orders": "📋 Meniň sargytlarym",
        "btn_my_responses": "📤 Meniň jogaplarym",
        "btn_profile": "👤 Profil",
        "btn_reviews": "📝 Synlar",
        "btn_help": "❓ Kömek",
        "btn_settings": "⚙️ Sazlamalar",
        "btn_partners": "🤝 Hyzmatdaşlar",
        "btn_back": "◀️ Yza",
        "settings_menu": "⚙️ Sazlamalar",
        "check_subscription": "✅ Ýazylmagy barlamak",
        "subscription_required": "❌ Botu ulanmak üçin kanala ýazylmaly:",
        "order_title": "📝 Sargydyň adyny giriziň:",
        "order_description": "📋 Sargydyň beýanyny giriziň:",
        "order_budget": "💰 Býudjeti giriziň (TMT-de):",
        "order_deadline": "⏰ Ýerine ýetirmek möhletini giriziň (günlerde):",
        "order_contact": "📞 Aragatnaşyk üçin kontakt giriziň:",
        "order_created": "✅ Sargyt üstünlikli döredildi!",
        "no_orders": "📭 Elýeterli sargyt ýok",
        "orders_list": "📋 Elýeterli sargytlar:",
        "my_orders_list": "📋 Siziň sargytlaryňyz:",
        "no_my_orders": "📭 Siziň sargydyňyz ýok",
        "respond_to_order": "📤 Jogap bermek",
        "response_sent": "✅ Jogap iberildi!",
        "response_exists": "❌ Siz bu sargyta eýýäm jogap berdiňiz",
        "new_response": "📨 Sargydyňyza täze jogap!",
        "btn_select_freelancer": "✅ Frilanser saýlamak",
        "btn_change_role": "🔄 Roly üýtgetmek",
        "btn_change_language": "🌐 Dil üýtgetmek",
        "btn_pay_guarantee": "💰 Tölemek",
        "btn_complete_order": "✅ Sargyt tamamlamak",
        "btn_confirm_completion": "✅ Tamamlamagy tassyklamak",
        "payment_guarantee": "🛡️ Kepilli töleg",
        "guarantee_info": "💰 Töleg mukdary: {amount} TMT + {commission} TMT (komissiýa 10%)\nUmumi mukdar: {total} TMT",
        "guarantee_request_sent": "✅ Töleg sorawy administratora iberildi",
        "order_selected": "✅ Frilanser saýlandy",
        "freelancer_selected": "🎉 Sizi sargyt ýerine ýetirmek üçin saýladylar!\n⚠️ Administrator töleg tassyklaýança işe başlamaň!",
        "payment_confirmed": "✅ Töleg tassyklandy! Işe başlap bolýar.",
        "order_completed": "✅ Sargyt tamamlandy",
        "waiting_payment_confirmation": "⏳ Administratoryň töleg tassyklamagyna garaşýarys",
        "both_confirm_required": "⚠️ Sargyt tamamlamak üçin iki tarapyň tassyklamagy zerur",
        "admin_payment_request": "💰 Täze kepilli töleg sorawy",
        "admin_confirm_payment": "✅ Töleg tassyklamak",
        "admin_release_payment": "💸 Frilanser tölemek",
        "error_not_freelancer": "❌ Bu funksiýa diňe frilanserler üçin elýeterli",
        "error_not_client": "❌ Bu funksiýa diňe müşderiler üçin elýeterli",
        "error_order_not_found": "❌ Sargyt tapylmady",
        "error_not_your_order": "❌ Bu siziň sargydyňyz däl",
        "error_user_not_found": "❌ Ulanyjy tapylmady",
        "profile_info": "👤 Siziň profilyňyz:",
        "edit_profile": "✏️ Profili üýtgetmek",
        "edit_name": "✏️ Ady üýtgetmek",
        "edit_skills": "✏️ Başarnyklary üýtgetmek",
        "edit_description": "✏️ Beýany üýtgetmek",
        "edit_contact": "✏️ Kontakty üýtgetmek",
        "profile_updated": "✅ Profil täzelendi",
        "leave_review": "⭐ Syn galdyrmak",
        "select_rating": "⭐ Bahany saýlaň:",
        "enter_review_text": "📝 Syn ýazyň:",
        "review_added": "✅ Syn goşuldy",
        "review_error": "❌ Syn goşup bolmady",
        "no_reviews": "📭 Heniz syn ýok",
        "reviews_about_you": "📝 Siziň barada synlar:",
        "btn_balance": "💰 Balans",
        "btn_withdraw": "💸 Çykarmak",
        "balance_info": "💰 Siziň balansyňyz: {balance} TMT",
        "withdraw_request": "💸 Serişde çykarmak",
        "withdraw_amount": "💰 Çykarmak üçin mukdary giriziň:",
        "withdraw_phone": "📞 Geçirmek üçin telefon belgisini giriziň:",
        "withdraw_confirm": "Siz {amount} TMT {phone} belgisine çykarmak isleýärsiňizmi?\n\n⚠️ Çykarmak komissiýasy: {commission} TMT\nÇykarmaga: {final_amount} TMT",
        "btn_confirm_withdraw": "✅ Tassyklamak",
        "btn_cancel_withdraw": "❌ Ýatyrmak",
        "withdraw_success": "✅ Çykarmak sorawy administratora iberildi",
        "withdraw_insufficient_funds": "❌ Balansda ýeterlik serişde ýok",
        "withdraw_invalid_amount": "❌ Nädogry mukdar",
        "admin_new_withdrawal": "💸 Täze çykarmak sorawy",
        "admin_withdrawal_info": "👤 Ulanyjy: {user_name} (ID: {user_id})\n💰 Mukdar: {amount} TMT\n📞 Telefon: {phone}\n📊 Balans öň: {balance_before} TMT\n📊 Balans soň: {balance_after} TMT",
        "btn_admin_confirm_withdrawal": "✅ Çykarmagy tassyklamak",
        "btn_admin_reject_withdrawal": "❌ Ret etmek",
        "btn_withdrawal_requests": "💸 Çykarmak arzalary",
        "withdrawal_confirmed": "✅ Çykarmak tassyklandy",
        "withdrawal_rejected": "❌ Çykarmak ret edildi",
        "no_withdrawal_requests": "📭 Çykarmak arzasy ýok",
        "btn_admin_panel": "⚙️ Admin paneli",
        "partners_title": "🤝 Biziň hyzmatdaşlarymyz",
        "partners_finance_tm": "💰 Maliýe kanaly FinanceTM\n📈 Türkmenistanyň walýuta kurslary, maýa goýumlary we maliýe täzelikleri barada häzirki maglumatlar",
        "btn_my_services": "🧰 Meniň hyzmatlarym",
        "btn_find_freelancer": "🔍 Frilanser tapmak",
        "btn_add_service": "➕ Hyzmat goşmak",
        "btn_view_my_services": "📋 Meniň hyzmatlarym",
        "btn_contact": "📩 Habarlaşmak",
        "btn_order_service": "✅ Sargyt bermek",
        "btn_my_balance": "💰 Meniň balansym",
        "btn_topup_balance": "➕ Doldyrmak",
        "service_order_confirm": "Bu hyzmaty sargyt bermek isleýärsiňizmi?\n\n💰 Bahasy: {price}\n⚠️ Mukdar balansyňyzda işiň tamamlanmagyna çenli petiklener.",
        "service_order_success": "✅ Sargyt ýasaldy! Serişdeler petiklendi. Frilanser habar aldy.",
        "service_order_insufficient": "❌ Balansda ýeterlik serişde ýok",
        "balance_info_client": "💰 Meniň balansym\n\n💳 Elýeterli: {balance} TMT\n🔒 Petiklenen: {frozen} TMT\n💵 Jemi: {total} TMT",
        "topup_amount": "💰 Doldyrmak üçin mukdary giriziň (TMT-de):",
        "topup_request_sent": "✅ Doldyrmak sorawy administratora iberildi",
        "admin_topup_request": "💰 Balans doldyrmak üçin täze soraw",
        "admin_topup_info": "👤 Ulanyjy: {user_name} (ID: {user_id})\n💰 Mukdar: {amount} TMT\n📊 Häzirki balans: {balance} TMT",
        "btn_admin_confirm_topup": "✅ Doldyrmagy tassyklamak",
        "topup_confirmed": "✅ Balans {amount} TMT dolduryldy",
        "freelancer_new_order": "🎉 Sizi hyzmat üçin saýladylar!\n\n📋 Hyzmat: {service_title}\n👤 Müşderi: {client_name}\n💰 Mukdar: {amount} TMT\n\n⏳ Administratoryň tassyklamagyna garaşyň",
        "admin_service_order": "📋 Täze hyzmat sargyt tassyklamak gerek",
        "service_add_category": "🏷️ Hyzmat kategoriýasyny saýlaň:",
        "service_add_title": "📝 Hyzmat adyny giriziň:",
        "service_add_description": "📋 Hyzmat beýanyny giriziň:",
        "service_add_price": "💰 Bahany giriziň (meselem: 100 TMT ýa-da 'şertnama boýunça'):",
        "service_confirm": "✅ Hyzmat goşmagy tassyklaň?",
        "service_added": "✅ Hyzmat üstünlikli goşuldy! Indi müşderiler sizi tapyp bilerler!",
        "service_limit_reached": "❌ Ulanyjy üçin iň köp 3 işjeň hyzmat",
        "no_services": "📭 Siziň işjeň hyzmatlarynyz ýok",
        "my_services_list": "🧰 Siziň hyzmatlarynyz:",
        "no_services_in_category": "📭 Bu kategoriýada heniz hyzmat ýok",
        "services_in_category": "🔍 Saýlanan kategoriýa boýunça tapylan:",
        "service_deleted": "✅ Hyzmat pozuldy",
        "btn_delete_service": "🗑️ Pozmak",
        "btn_edit_service": "✏️ Üýtgetmek",
        "select_service_action": "Hyzmat bilen etjek işiňizi saýlaň:",
    }
}

# Categories
CATEGORIES = {
    "ru": {
        "web_development": "💻 Веб-разработка",
        "mobile_development": "📱 Мобильная разработка",
        "design": "🎨 Дизайн",
        "writing": "✍️ Копирайтинг",
        "translation": "🌐 Переводы",
        "marketing": "📈 Маркетинг",
        "video": "🎬 Видео",
        "other": "🔧 Другое"
    },
    "tm": {
        "web_development": "💻 Web ösüş",
        "mobile_development": "📱 Mobil ösüş",
        "design": "🎨 Dizaýn",
        "writing": "✍️ Ýazuw",
        "translation": "🌐 Terjime",
        "marketing": "📈 Marketing",
        "video": "🎬 Wideo",
        "other": "🔧 Beýleki"
    }
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
async def check_subscription(user_id: int, bot: Bot) -> bool:
    """Check user subscription to required channel"""
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking subscription for user {user_id}: {e}")
        return False

def get_text(key: str, lang: str = "ru") -> str:
    """Get text in specified language"""
    return TEXTS.get(lang, TEXTS["ru"]).get(key, f"[{key}]")

def get_user_language(user_id: int) -> str:
    """Get user language"""
    user = get_user(user_id)
    return user.get('language', 'ru') if user else 'ru'

def is_admin(user_id: int) -> bool:
    """Check admin permissions"""
    return user_id in ADMIN_IDS

def calculate_commission(amount: float) -> tuple:
    """Calculate commission for guarantee deal"""
    commission = amount * COMMISSION_RATE
    total = amount + commission
    return commission, total

def track_platform_earnings(amount: float):
    """Track platform earnings for analytics"""
    # This would be where you'd log platform revenue
    pass

def calculate_withdrawal_commission(amount: float) -> tuple:
    """Calculate commission for withdrawal"""
    commission = amount * WITHDRAWAL_COMMISSION
    final_amount = amount - commission
    return commission, final_amount

def format_contact_info(user: dict) -> str:
    """Format contact information"""
    contact = user.get('profile', {}).get('contact', '')
    username = user.get('username', '')

    if contact and username:
        return f"{contact}\n@{username}"
    elif contact:
        return contact
    elif username:
        return f"@{username}"
    else:
        return "Не указан"

def validate_budget(text: str) -> Optional[float]:
    """Validate budget input"""
    try:
        budget = float(text.replace(',', '.'))
        return budget if budget > 0 else None
    except ValueError:
        return None

def validate_deadline(text: str) -> Optional[int]:
    """Validate deadline input"""
    try:
        deadline = int(text)
        return deadline if deadline > 0 else None
    except ValueError:
        return None

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length"""
    if text is None:
        return ""
    return text[:max_length] + "..." if len(text) > max_length else text

def format_price(amount: float) -> str:
    """Format price"""
    return f"{amount:.2f}".rstrip('0').rstrip('.')

def get_status_emoji(status: str) -> str:
    """Get emoji for order status"""
    return {
        'active': '🟢',
        'in_progress': '🟡',
        'payment_pending': '🟠',
        'completion_pending': '🔵',
        'completed': '✅',
        'cancelled': '❌'
    }.get(status, '⚫')

def escape_html(text: str) -> str:
    """Escape HTML characters"""
    if not text:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def send_notification(bot: Bot, user_id: int, text: str, **kwargs):
    """Safe notification sending"""
    try:
        await bot.send_message(user_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Failed to send notification to {user_id}: {e}")

def format_order_text(order: dict, lang: str = "ru") -> str:
    """Format order text"""
    status_emoji = get_status_emoji(order.get('status', 'active'))

    text = f"""
{status_emoji} <b>{"Заказ" if lang == "ru" else "Sargyt"} #{order['id']}</b>

📝 <b>{"Название" if lang == "ru" else "Ady"}:</b> {escape_html(order['title'])}
📋 <b>{"Описание" if lang == "ru" else "Beýany"}:</b> {escape_html(truncate_text(order['description']))}
💰 <b>{"Бюджет" if lang == "ru" else "Býudjet"}:</b> {format_price(order['budget'])} TMT
⏰ <b>{"Срок" if lang == "ru" else "Möhlet"}:</b> {order['deadline']} {"дней" if lang == "ru" else "gün"}
🏷️ <b>{"Категория" if lang == "ru" else "Kategoriýa"}:</b> {CATEGORIES.get(lang, CATEGORIES["ru"]).get(order.get('category', 'other'), order.get('category', 'other'))}
"""

    if 'created_at' in order:
        created_date = datetime.fromisoformat(order['created_at']).strftime("%d.%m.%Y %H:%M")
        created_text = "Создан" if lang == "ru" else "Döredildi"
        text += f"\n📅 <b>{created_text}:</b> {created_date}"

    return text.strip()

def format_profile_text(user: dict, lang: str = "ru") -> str:
    """Format profile text"""
    profile = user.get('profile', {})
    rating = get_user_average_rating(user['id'])
    reviews_count = len(get_user_reviews(user['id']))

    text = f"""
👤 <b>{"Профиль" if lang == "ru" else "Profil"}</b>

📝 <b>{"Имя" if lang == "ru" else "Ady"}:</b> {escape_html(user.get('first_name', ''))}
👔 <b>{"Роль" if lang == "ru" else "Roly"}:</b> {"Фрилансер" if user.get('role') == 'freelancer' else "Заказчик" if lang == "ru" else "Frilanser" if user.get('role') == 'freelancer' else "Müşderi"}
💼 <b>{"Навыки" if lang == "ru" else "Başarnyklar"}:</b> {escape_html(profile.get('skills', 'Не указаны' if lang == "ru" else "Görkezilmedi"))}
📝 <b>{"Описание" if lang == "ru" else "Beýany"}:</b> {escape_html(profile.get('description', 'Не указано' if lang == "ru" else "Görkezilmedi"))}
📞 <b>{"Контакт" if lang == "ru" else "Kontakt"}:</b> {escape_html(profile.get('contact', 'Не указан' if lang == "ru" else "Görkezilmedi"))}
⭐ <b>{"Рейтинг" if lang == "ru" else "Reýting"}:</b> {rating:.1f}/5.0 ({reviews_count} {"отзывов" if lang == "ru" else "syn"})
"""

    return text.strip()

def format_review_text(review: dict, lang: str = "ru") -> str:
    """Format review text"""
    reviewer = get_user(review['reviewer_id'])
    reviewer_name = reviewer.get('first_name', 'Unknown') if reviewer else 'Unknown'

    stars = "⭐" * review['rating'] + "☆" * (5 - review['rating'])
    date = datetime.fromisoformat(review['created_at']).strftime("%d.%m.%Y")

    return f"""
{stars} <b>{review['rating']}/5</b>
👤 <b>{"От" if lang == "ru" else "Kimden"}:</b> {escape_html(reviewer_name)}
📝 <b>{"Отзыв" if lang == "ru" else "Teswir"}:</b> {escape_html(review.get('text', ''))}
📅 {date}
"""

def format_service_text(service: dict, lang: str = "ru", show_contact: bool = True) -> str:
    """Format service text"""
    user = get_user(service['user_id'])
    username = f"@{user.get('username')}" if user and user.get('username') else "нет username" if lang == "ru" else "username ýok"
    
    category_name = CATEGORIES.get(lang, CATEGORIES["ru"]).get(service.get('category'), service.get('category', ''))
    
    text = f"""
🧰 <b>{escape_html(service['title'])}</b>

🏷️ <b>{"Категория" if lang == "ru" else "Kategoriýa"}:</b> {category_name}
📝 <b>{"Описание" if lang == "ru" else "Beýany"}:</b> {escape_html(service['description'])}
💰 <b>{"Цена" if lang == "ru" else "Baha"}:</b> {escape_html(service['price'])}
👤 <b>{"Фрилансер" if lang == "ru" else "Frilanser"}:</b> {escape_html(user.get('first_name', 'Unknown') if user else 'Unknown')} ({username})
"""

    if show_contact and user:
        contact = format_contact_info(user)
        contact_label = "Контакт" if lang == "ru" else "Kontakt"
        text += f"\n📞 <b>{contact_label}:</b> {escape_html(contact)}"

    return text.strip()

# =============================================================================
# STATES
# =============================================================================
class RegistrationStates(StatesGroup):
    waiting_language = State()
    waiting_role = State()
    waiting_profile_name = State()
    waiting_profile_skills = State()
    waiting_profile_description = State()
    waiting_profile_contact = State()

class OrderStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_category = State()
    waiting_budget = State()
    waiting_deadline = State()
    waiting_contact = State()

class ProfileStates(StatesGroup):
    waiting_new_name = State()
    waiting_new_skills = State()
    waiting_new_description = State()
    waiting_new_contact = State()

class ReviewStates(StatesGroup):
    waiting_rating = State()
    waiting_review_text = State()

class WithdrawalStates(StatesGroup):
    waiting_amount = State()
    waiting_phone = State()

class AdminStates(StatesGroup):
    waiting_balance_command = State()
    waiting_user_search = State()

class ServiceStates(StatesGroup):
    waiting_category = State()
    waiting_title = State()
    waiting_description = State()
    waiting_price = State()
    waiting_confirm = State()

class ServiceOrderStates(StatesGroup):
    confirm_order = State()
    waiting_for_admin = State()
    waiting_for_completion = State()
    both_confirmed = State()

class BalanceStates(StatesGroup):
    waiting_topup_amount = State()
    waiting_withdraw_amount = State()
    waiting_withdraw_phone = State()

# =============================================================================
# KEYBOARDS
# =============================================================================
def get_language_keyboard():
    """Get language selection keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇹🇲 Türkmen", callback_data="lang_tm")
        ]
    ])

def get_role_keyboard(lang="ru"):
    """Get role selection keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨‍💻 Фрилансер" if lang == "ru" else "👨‍💻 Frilanser", callback_data="role_freelancer"),
            InlineKeyboardButton(text="👤 Заказчик" if lang == "ru" else "👤 Müşderi", callback_data="role_client")
        ]
    ])

def get_main_menu_keyboard(role, lang="ru", user_id=None):
    """Get main menu keyboard based on role"""
    buttons = []

    if role == "client":
        buttons.extend([
            [KeyboardButton(text=get_text("btn_create_order", lang))],
            [KeyboardButton(text=get_text("btn_my_orders", lang))],
            [KeyboardButton(text=get_text("btn_find_freelancer", lang))],
            [KeyboardButton(text=get_text("btn_my_balance", lang))]
        ])
    elif role == "freelancer":
        buttons.extend([
            [KeyboardButton(text=get_text("btn_view_orders", lang))],
            [KeyboardButton(text=get_text("btn_my_responses", lang))],
            [KeyboardButton(text=get_text("btn_my_services", lang))],
            [KeyboardButton(text=get_text("btn_balance", lang)), KeyboardButton(text=get_text("btn_withdraw", lang))]
        ])

    buttons.extend([
        [KeyboardButton(text=get_text("btn_settings", lang)), KeyboardButton(text=get_text("btn_partners", lang))]
    ])

    # Add admin menu for admins
    if user_id and is_admin(user_id):
        buttons.append([KeyboardButton(text="⚙️ Админ панель" if lang == "ru" else "⚙️ Admin paneli")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_settings_keyboard(lang="ru"):
    """Get settings menu keyboard"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=get_text("btn_profile", lang)), KeyboardButton(text=get_text("btn_reviews", lang))],
        [KeyboardButton(text=get_text("btn_change_role", lang)), KeyboardButton(text=get_text("btn_change_language", lang))],
        [KeyboardButton(text=get_text("btn_help", lang))],
        [KeyboardButton(text=get_text("btn_back", lang))]
    ], resize_keyboard=True)

def get_subscription_keyboard():
    """Get subscription check keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")]
    ])

def get_categories_keyboard(lang="ru"):
    """Get categories keyboard"""
    categories = CATEGORIES.get(lang, CATEGORIES["ru"])
    keyboard = []

    for key, value in categories.items():
        keyboard.append([InlineKeyboardButton(text=value, callback_data=f"category_{key}")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_order_response_keyboard(order_id, lang="ru"):
    """Get order response keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("respond_to_order", lang), callback_data=f"respond_{order_id}")]
    ])

def get_order_actions_keyboard(order_id, freelancer_id, lang="ru"):
    """Get order actions keyboard for client"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выбрать фрилансера" if lang == "ru" else "✅ Frilanser saýlamak", callback_data=f"select_{order_id}_{freelancer_id}")
        ]
    ])



def get_order_completion_keyboard(order_id, lang="ru"):
    """Get order completion keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("btn_confirm_completion", lang), callback_data=f"confirm_completion_{order_id}")]
    ])

def get_admin_payment_keyboard(orders, action_type="confirm"):
    """Get admin payment keyboard"""
    if not orders:
        return None

    keyboard = []
    for order in orders[:10]:  # Limit to 10 orders
        if action_type == "confirm":
            keyboard.append([
                InlineKeyboardButton(text=f"✅ #{order['id']}", callback_data=f"admin_confirm_payment_{order['id']}"),
                InlineKeyboardButton(text=f"❌ #{order['id']}", callback_data=f"admin_reject_{order['id']}")
            ])
        else:
            text = f"#{order['id']} - {truncate_text(order['title'], 30)}"
            callback_data = f"admin_{action_type}_{order['id']}"
            keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_rating_keyboard(lang="ru"):
    """Get rating keyboard"""
    keyboard = []
    for i in range(1, 6):
        stars = "⭐" * i + "☆" * (5 - i)
        keyboard.append([InlineKeyboardButton(text=f"{stars} {i}/5", callback_data=f"rating_{i}")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_profile_edit_keyboard(lang="ru"):
    """Get profile edit keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text("edit_name", lang), callback_data="edit_name"),
            InlineKeyboardButton(text=get_text("edit_skills", lang), callback_data="edit_skills")
        ],
        [
            InlineKeyboardButton(text=get_text("edit_description", lang), callback_data="edit_description"),
            InlineKeyboardButton(text=get_text("edit_contact", lang), callback_data="edit_contact")
        ]
    ])

def get_back_keyboard(lang="ru"):
    """Get back keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_text("btn_back", lang))]],
        resize_keyboard=True
    )

def get_withdrawal_confirmation_keyboard(withdrawal_id, lang="ru"):
    """Get withdrawal confirmation keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text("btn_confirm_withdraw", lang), callback_data=f"confirm_withdraw_{withdrawal_id}"),
            InlineKeyboardButton(text=get_text("btn_cancel_withdraw", lang), callback_data="cancel_withdraw")
        ]
    ])

def get_admin_withdrawal_keyboard(withdrawal_id, lang="ru"):
    """Get admin withdrawal keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text("btn_admin_confirm_withdrawal", lang), callback_data=f"admin_confirm_withdrawal_{withdrawal_id}"),
            InlineKeyboardButton(text=get_text("btn_admin_reject_withdrawal", lang), callback_data=f"admin_reject_withdrawal_{withdrawal_id}")
        ]
    ])

def get_services_menu_keyboard(lang="ru"):
    """Get services menu keyboard for freelancers"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text("btn_add_service", lang), callback_data="add_service"),
            InlineKeyboardButton(text=get_text("btn_view_my_services", lang), callback_data="view_my_services")
        ]
    ])

def get_service_actions_keyboard(service_id, lang="ru"):
    """Get service actions keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text("btn_edit_service", lang), callback_data=f"edit_service_{service_id}"),
            InlineKeyboardButton(text=get_text("btn_delete_service", lang), callback_data=f"delete_service_{service_id}")
        ]
    ])

def get_service_contact_keyboard(user_id, service_id, lang="ru"):
    """Get service contact and order keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text("btn_contact", lang), url=f"tg://user?id={user_id}"),
            InlineKeyboardButton(text=get_text("btn_order_service", lang), callback_data=f"order_service_{service_id}")
        ]
    ])

def get_balance_menu_keyboard(lang="ru"):
    """Get balance menu keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text("btn_topup_balance", lang), callback_data="topup_balance"),
            InlineKeyboardButton(text=get_text("btn_withdraw", lang), callback_data="withdraw_balance")
        ]
    ])

def get_service_order_confirmation_keyboard(service_id, lang="ru"):
    """Get service order confirmation keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да" if lang == "ru" else "✅ Hawa", callback_data=f"confirm_service_order_{service_id}"),
            InlineKeyboardButton(text="❌ Нет" if lang == "ru" else "❌ Ýok", callback_data="cancel_service_order")
        ]
    ])

def get_admin_topup_keyboard(request_id, lang="ru"):
    """Get admin topup confirmation keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("btn_admin_confirm_topup", lang), callback_data=f"admin_confirm_topup_{request_id}")]
    ])

def get_admin_service_order_keyboard(order_id, lang="ru"):
    """Get admin service order keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить заказ" if lang == "ru" else "✅ Sargyt tassyklamak", callback_data=f"admin_confirm_service_order_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить" if lang == "ru" else "❌ Ret etmek", callback_data=f"admin_reject_service_order_{order_id}")
        ]
    ])

# =============================================================================
# MIDDLEWARE
# =============================================================================
class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None

            if user_id:
                # Skip subscription check for admins
                if is_admin(user_id):
                    return await handler(event, data)

                # Skip subscription check for /start command
                if isinstance(event, Message) and event.text and event.text.startswith('/start'):
                    return await handler(event, data)

                user = get_user(user_id)
                if user and not await check_subscription(user_id, data.get('bot')):
                    lang = user.get('language', 'ru')
                    subscription_text = f"{get_text('subscription_required', lang)} {REQUIRED_CHANNEL}"

                    if isinstance(event, Message):
                        await event.answer(subscription_text, reply_markup=get_subscription_keyboard())
                    elif isinstance(event, CallbackQuery):
                        try:
                            await event.message.edit_text(subscription_text, reply_markup=get_subscription_keyboard())
                        except Exception:
                            # If message can't be edited, send a new one
                            await event.message.answer(subscription_text, reply_markup=get_subscription_keyboard())
                        await event.answer()
                    return

        return await handler(event, data)

# =============================================================================
# HANDLERS
# =============================================================================
router = Router()

# Registration handlers
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        # New user - start registration
        await message.answer(get_text("choose_language"), reply_markup=get_language_keyboard())
        await state.set_state(RegistrationStates.waiting_language)
    else:
        # Existing user - check subscription and show main menu
        lang = user.get('language', 'ru')

        if not await check_subscription(user_id, message.bot):
            subscription_text = f"{get_text('subscription_required', lang)} {REQUIRED_CHANNEL}"
            await message.answer(subscription_text, reply_markup=get_subscription_keyboard())
            return

        role = user.get('role')
        welcome_text = get_text(f"main_menu_{role}", lang)
        await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(role, lang, message.from_user.id))

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)

    if not user:
        await callback.answer("❌ Сначала зарегистрируйтесь")
        return

    lang = user.get('language', 'ru')

    if await check_subscription(user_id, callback.bot):
        role = user.get('role')
        welcome_text = get_text(f"main_menu_{role}", lang)
        await callback.message.edit_text(welcome_text)
        await callback.message.answer(welcome_text, reply_markup=get_main_menu_keyboard(role, lang, callback.from_user.id))
        await callback.answer("✅ Подписка подтверждена!" if lang == "ru" else "✅ Ýazylma tassyklandy!")
    else:
        await callback.answer("❌ Подпишитесь на канал!" if lang == "ru" else "❌ Kanala ýazylyň!")

@router.callback_query(F.data.startswith("lang_"))
async def language_selected(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user = get_user(user_id)

    if user:
        # Existing user - update language
        update_user(user_id, {'language': lang})
        role = user.get('role')
        welcome_text = get_text(f"main_menu_{role}", lang)
        await callback.message.edit_text(welcome_text)
        await callback.message.answer(welcome_text, reply_markup=get_main_menu_keyboard(role, lang, user_id))
        await callback.answer("✅ Язык изменен!" if lang == "ru" else "✅ Dil üýtgedildi!")
    else:
        # New user - continue registration
        await state.update_data(language=lang)
        await callback.message.edit_text(get_text("choose_role", lang), reply_markup=get_role_keyboard(lang))
        await state.set_state(RegistrationStates.waiting_role)
        await callback.answer()

@router.callback_query(F.data.startswith("role_"))
async def role_selected(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    data = await state.get_data()
    lang = data.get('language', 'ru')

    await state.update_data(role=role)
    await callback.message.edit_text(get_text("registration_name", lang))
    await state.set_state(RegistrationStates.waiting_profile_name)
    await callback.answer()

@router.message(RegistrationStates.waiting_profile_name)
async def profile_name_received(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('language', 'ru')

    await state.update_data(profile_name=message.text)
    await message.answer(get_text("registration_skills", lang))
    await state.set_state(RegistrationStates.waiting_profile_skills)

@router.message(RegistrationStates.waiting_profile_skills)
async def profile_skills_received(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('language', 'ru')

    await state.update_data(profile_skills=message.text)
    await message.answer(get_text("registration_description", lang))
    await state.set_state(RegistrationStates.waiting_profile_description)

@router.message(RegistrationStates.waiting_profile_description)
async def profile_description_received(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('language', 'ru')

    await state.update_data(profile_description=message.text)
    await message.answer(get_text("registration_contact", lang))
    await state.set_state(RegistrationStates.waiting_profile_contact)

@router.message(RegistrationStates.waiting_profile_contact)
async def profile_contact_received(message: Message, state: FSMContext):
    data = await state.get_data()
    await complete_registration(message, state)

async def complete_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id

    user_data = {
        'first_name': message.from_user.first_name,
        'username': message.from_user.username,
        'language': data.get('language', 'ru'),
        'role': data.get('role'),
        'profile': {
            'name': data.get('profile_name'),
            'skills': data.get('profile_skills'),
            'description': data.get('profile_description'),
            'contact': message.text
        }
    }

    create_user(user_id, user_data)

    lang = data.get('language', 'ru')
    role = data.get('role')

    await message.answer(get_text("registration_complete", lang))
    await message.answer(get_text(f"main_menu_{role}", lang), reply_markup=get_main_menu_keyboard(role, lang, message.from_user.id))
    await state.clear()

# Order creation handlers
@router.message(F.text.in_(["➕ Создать заказ", "➕ Sargyt döretmek"]))
async def create_order_start(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user or user.get('role') != 'client':
        lang = user.get('language', 'ru') if user else 'ru'
        await message.answer(get_text("error_not_client", lang))
        return

    lang = user.get('language', 'ru')
    await message.answer(get_text("order_title", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(OrderStates.waiting_title)

@router.message(OrderStates.waiting_title)
async def order_title_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    if message.text == get_text("btn_back", lang):
        role = user.get('role')
        await message.answer(get_text(f"main_menu_{role}", lang), reply_markup=get_main_menu_keyboard(role, lang, message.from_user.id))
        await state.clear()
        return

    await state.update_data(title=message.text)
    await message.answer(get_text("order_description", lang))
    await state.set_state(OrderStates.waiting_description)

@router.message(OrderStates.waiting_description)
async def order_description_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    await state.update_data(description=message.text)
    await message.answer("🏷️ Выберите категорию:" if lang == "ru" else "🏷️ Kategoriýa saýlaň:", reply_markup=get_categories_keyboard(lang))
    await state.set_state(OrderStates.waiting_category)

@router.callback_query(F.data.startswith("category_"), StateFilter(OrderStates.waiting_category))
async def category_selected(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[1]
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await state.update_data(category=category)
    await callback.message.edit_text(get_text("order_budget", lang))
    await state.set_state(OrderStates.waiting_budget)
    await callback.answer()

@router.message(OrderStates.waiting_budget)
async def order_budget_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    budget = validate_budget(message.text)
    if not budget:
        await message.answer("❌ Введите корректную сумму" if lang == "ru" else "❌ Dogry mukdar giriziň")
        return

    await state.update_data(budget=budget)
    await message.answer(get_text("order_deadline", lang))
    await state.set_state(OrderStates.waiting_deadline)

@router.message(OrderStates.waiting_deadline)
async def order_deadline_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    deadline = validate_deadline(message.text)
    if not deadline:
        await message.answer("❌ Введите корректное количество дней" if lang == "ru" else "❌ Dogry gün sanyny giriziň")
        return

    await state.update_data(deadline=deadline)
    await message.answer(get_text("order_contact", lang))
    await state.set_state(OrderStates.waiting_contact)

@router.message(OrderStates.waiting_contact)
async def order_contact_received(message: Message, state: FSMContext):
    data = await state.get_data()
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    # Check if client has enough balance
    budget = data['budget']
    client_balance = get_user_balance(message.from_user.id)
    
    if client_balance < budget:
        insufficient_text = f"❌ {'Недостаточно средств на балансе!' if lang == 'ru' else 'Balansda ýeterlik serişde ýok!'}\n\n💰 {'Требуется' if lang == 'ru' else 'Gerek'}: {budget} TMT\n💳 {'Доступно' if lang == 'ru' else 'Elýeterli'}: {client_balance} TMT\n\n{'Пополните баланс для создания заказа' if lang == 'ru' else 'Sargyt döretmek üçin balansyňyzy dolduryň'}"
        
        await message.answer(insufficient_text)
        role = user.get('role')
        await message.answer(get_text(f"main_menu_{role}", lang), reply_markup=get_main_menu_keyboard(role, lang, message.from_user.id))
        await state.clear()
        return

    order_data = {
        'client_id': message.from_user.id,
        'title': data['title'],
        'description': data['description'],
        'category': data['category'],
        'budget': data['budget'],
        'deadline': data['deadline'],
        'contact': message.text
    }

    order = create_order(order_data)

    await message.answer(get_text("order_created", lang))
    await message.answer(format_order_text(order, lang), parse_mode="HTML")

    role = user.get('role')
    await message.answer(get_text(f"main_menu_{role}", lang), reply_markup=get_main_menu_keyboard(role, lang, message.from_user.id))
    await state.clear()

# Order viewing handlers
@router.message(F.text.in_(["📋 Просмотр заказов", "📋 Sargytlary görmek"]))
async def view_orders(message: Message):
    user = get_user(message.from_user.id)
    if not user or user.get('role') != 'freelancer':
        lang = user.get('language', 'ru') if user else 'ru'
        await message.answer(get_text("error_not_freelancer", lang))
        return

    lang = user.get('language', 'ru')
    orders = get_active_orders_for_freelancer(user['id'])

    if not orders:
        await message.answer(get_text("no_orders", lang))
        return

    await message.answer(get_text("orders_list", lang))
    for order in orders[:10]:  # Show first 10 orders
        order_text = format_order_text(order, lang)
        keyboard = get_order_response_keyboard(order['id'], lang)
        await message.answer(order_text, reply_markup=keyboard, parse_mode="HTML")

@router.message(F.text.in_(["📋 Мои заказы", "📋 Meniň sargytlarym"]))
async def my_orders(message: Message):
    user = get_user(message.from_user.id)
    if not user or user.get('role') != 'client':
        lang = user.get('language', 'ru') if user else 'ru'
        await message.answer(get_text("error_not_client", lang))
        return

    lang = user.get('language', 'ru')
    orders = get_orders_by_client(message.from_user.id)

    if not orders:
        await message.answer(get_text("no_my_orders", lang))
        return

    await message.answer(get_text("my_orders_list", lang))
    for order in orders:
        order_text = format_order_text(order, lang)

        # Add responses info
        responses = get_responses(order['id'])
        if responses:
            order_text += f"\n\n📨 {len(responses)} {'откликов' if lang == 'ru' else 'jogap'}"

            # Show responses with action buttons
            for response in responses[:3]:  # Show first 3 responses
                freelancer = get_user(response['freelancer_id'])
                if freelancer:
                    freelancer_text = f"\n\n👤 {escape_html(freelancer['first_name'])}"
                    if freelancer.get('username'):
                        freelancer_text += f" (@{freelancer['username']})"

                    # Add rating
                    rating = get_user_average_rating(freelancer['id'])
                    freelancer_text += f"\n⭐ {rating:.1f}/5.0"

                    # Add skills
                    skills = freelancer.get('profile', {}).get('skills', '')
                    if skills:
                        freelancer_text += f"\n💼 {escape_html(truncate_text(skills, 50))}"

                    # Add response message if exists
                    if response.get('message'):
                        freelancer_text += f"\n💬 {escape_html(truncate_text(response['message'], 100))}"

                    # Action buttons for active orders
                    if order.get('status') == 'active':
                        keyboard = get_order_actions_keyboard(order['id'], freelancer['id'], lang)
                        await message.answer(freelancer_text, reply_markup=keyboard, parse_mode="HTML")
                    else:
                        await message.answer(freelancer_text, parse_mode="HTML")

        await message.answer(order_text, parse_mode="HTML")

@router.message(F.text.in_(["📤 Мои отклики", "📤 Meniň jogaplarym"]))
async def my_responses(message: Message):
    user = get_user(message.from_user.id)
    if not user or user.get('role') != 'freelancer':
        lang = user.get('language', 'ru') if user else 'ru'
        await message.answer(get_text("error_not_freelancer", lang))
        return

    lang = user.get('language', 'ru')
    responses = get_freelancer_responses(message.from_user.id)

    if not responses:
        await message.answer("📭 У вас нет откликов" if lang == "ru" else "📭 Siziň jogapyňyz ýok")
        return

    await message.answer("📤 Ваши отклики:" if lang == "ru" else "📤 Siziň jogaplaryňyz:")
    for response in responses:
        order = response.get('order')
        if order:
            order_text = format_order_text(order, lang)

            # Add response status
            status = order.get('status', 'active')
            if status == 'active':
                status_text = "⏳ Ожидает рассмотрения" if lang == "ru" else "⏳ Seredilmegine garaşýar"
            elif status == 'in_progress' and order.get('selected_freelancer') == message.from_user.id:
                status_text = "✅ Вы выбраны для работы" if lang == "ru" else "✅ Siz iş üçin saýlandyňyz"
            elif status == 'completed':
                status_text = "✅ Заказ завершен" if lang == "ru" else "✅ Sargyt tamamlandy"
            else:
                status_text = "❌ Выбран другой фрилансер" if lang == "ru" else "❌ Başga frilanser saýlandy"

            order_text += f"\n\n📋 Статус: {status_text}"

            await message.answer(order_text, parse_mode="HTML")

# Response handlers
@router.callback_query(F.data.startswith("respond_"))
async def respond_to_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user = get_user(callback.from_user.id)

    if not user or user.get('role') != 'freelancer':
        lang = user.get('language', 'ru') if user else 'ru'
        await callback.answer(get_text("error_not_freelancer", lang))
        return

    lang = user.get('language', 'ru')

    # Check if user is trying to respond to their own order
    order = get_order(order_id)
    if order and order.get('client_id') == user['id']:
        await callback.answer("❌ Нельзя откликаться на свой заказ" if lang == "ru" else "❌ Öz sargydyňyza jogap berip bolmaýar")
        return

    response_data = {
        'freelancer_id': callback.from_user.id,
        'message': f"Готов выполнить заказ!" if lang == "ru" else "Sargyt ýerine ýetirmäge taýyn!"
    }

    if add_response(order_id, response_data):
        # Notify client about new response
        order = get_order(order_id)
        if order:
            client = get_user(order['client_id'])
            if client:
                client_lang = client['language']
                freelancer_username = f"@{user.get('username')}" if user.get('username') else ("нет username" if client_lang == "ru" else "username ýok")
                freelancer_info = f"""
📨 <b>{"Новый отклик на ваш заказ!" if client_lang == "ru" else "Sargydyňyza täze jogap!"}</b>

📋 <b>{"Заказ" if client_lang == "ru" else "Sargyt"} #{order['id']}:</b> {escape_html(order['title'])}

👤 <b>{"Фрилансер" if client_lang == "ru" else "Frilanser"}:</b> {escape_html(user['first_name'])}
📱 <b>Username:</b> {freelancer_username}
🆔 <b>ID:</b> <code>{user['id']}</code>
⭐ <b>{"Рейтинг" if client_lang == "ru" else "Reýting"}:</b> {get_user_average_rating(user['id']):.1f}/5.0
💼 <b>{"Навыки" if client_lang == "ru" else "Başarnyklar"}:</b> {escape_html(user.get('profile', {}).get('skills', 'Не указаны' if client_lang == "ru" else "Görkezilmedi"))}
📞 <b>{"Контакт" if client_lang == "ru" else "Kontakt"}:</b> {escape_html(format_contact_info(user))}
"""

                keyboard = get_order_actions_keyboard(order_id, callback.from_user.id, client_lang)
                await callback.bot.send_message(order['client_id'], freelancer_info, reply_markup=keyboard, parse_mode="HTML")

        await callback.answer(get_text("response_sent", lang))
    else:
        await callback.answer(get_text("response_exists", lang))

@router.callback_query(F.data.startswith("select_"))
async def select_freelancer(callback: CallbackQuery):
    parts = callback.data.split("_")
    order_id, freelancer_id = int(parts[1]), int(parts[2])

    user = get_user(callback.from_user.id)
    order = get_order(order_id)
    freelancer = get_user(freelancer_id)
    lang = user['language']

    if not order or order['client_id'] != callback.from_user.id:
        await callback.answer(get_text("error_not_your_order", lang))
        return

    # Check if client has enough balance
    budget = order['budget']
    client_balance = get_user_balance(callback.from_user.id)
    
    if client_balance < budget:
        await callback.answer(f"❌ {'Недостаточно средств на балансе!' if lang == 'ru' else 'Balansda ýeterlik serişde ýok!'}")
        return

    # Freeze balance immediately
    freeze_balance(callback.from_user.id, budget)

    # Update order status to in_progress immediately
    update_order(order_id, {
        'selected_freelancer': freelancer_id,
        'selected_freelancer_username': freelancer.get('username'),
        'selected_freelancer_name': freelancer.get('first_name'),
        'status': 'in_progress',
        'client_confirmed': False,
        'freelancer_confirmed': False
    })

    # Notify client
    freelancer_contact = format_contact_info(freelancer)
    freelancer_username = f"@{freelancer.get('username')}" if freelancer.get('username') else ("нет username" if lang == "ru" else "username ýok")
    client_text = f"""
✅ <b>{"Фрилансер выбран и средства заблокированы!" if lang == "ru" else "Frilanser saýlandy we serişdeler petiklendi!"}</b>

👤 <b>{"Фрилансер" if lang == "ru" else "Frilanser"}:</b> {escape_html(freelancer['first_name'])}
📱 <b>Username:</b> {freelancer_username}
🆔 <b>ID:</b> <code>{freelancer['id']}</code>
📞 <b>{"Контакт" if lang == "ru" else "Kontakt"}:</b> {escape_html(freelancer_contact)}
⭐ <b>{"Рейтинг" if lang == "ru" else "Reýting"}:</b> {get_user_average_rating(freelancer['id']):.1f}/5.0
📋 <b>{"Заказ" if lang == "ru" else "Sargyt"}:</b> {escape_html(order['title'])}
💰 <b>{"Заблокировано" if lang == "ru" else "Petiklendi"}:</b> {budget} TMT

🛡️ {"Средства заблокированы до завершения работы" if lang == "ru" else "Serişdeler işiň tamamlanmagyna çenli petiklendi"}
"""

    completion_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Подтвердить завершение" if lang == "ru" else "✅ Tamamlamagy tassyklamak",
            callback_data=f"confirm_completion_{order_id}"
        )]
    ])

    await callback.message.edit_text(client_text, reply_markup=completion_keyboard, parse_mode="HTML")

    # Notify freelancer that they can start work immediately
    if freelancer:
        freelancer_lang = freelancer['language']
        client_contact = format_contact_info(user)
        client_username = f"@{user.get('username')}" if user.get('username') else ("нет username" if freelancer_lang == "ru" else "username ýok")
        freelancer_text = f"""
🎉 <b>{"Вас выбрали! Средства заблокированы, можете начинать работу!" if freelancer_lang == "ru" else "Sizi saýladylar! Serişdeler petiklendi, işe başlap bilersiňiz!"}</b>

📋 <b>{"Заказ" if freelancer_lang == "ru" else "Sargyt"} #{order['id']}:</b> {escape_html(order['title'])}
💰 <b>{"Сумма" if freelancer_lang == "ru" else "Mukdar"}:</b> {budget} TMT
👤 <b>{"Заказчик" if freelancer_lang == "ru" else "Müşderi"}:</b> {escape_html(user['first_name'])}
📱 <b>Username:</b> {client_username}
🆔 <b>ID:</b> <code>{user['id']}</code>
📞 <b>{"Контакт для связи" if freelancer_lang == "ru" else "Aragatnaşyk üçin kontakt"}:</b> {escape_html(client_contact)}

🎯 {"После завершения работы нажмите кнопку для подтверждения" if freelancer_lang == "ru" else "Işi gutarandan soň tassyklamak üçin düwmä basyň"}
"""

        completion_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Работа завершена" if freelancer_lang == "ru" else "✅ Iş tamamlandy",
                callback_data=f"confirm_completion_{order_id}"
            )]
        ])

        await callback.bot.send_message(freelancer_id, freelancer_text, reply_markup=completion_keyboard, parse_mode="HTML")

    await callback.answer(get_text("order_selected", lang))





@router.callback_query(F.data.startswith("confirm_completion_"))
async def confirm_completion(callback: CallbackQuery):
    """Handle completion confirmation from client or freelancer"""
    order_id = int(callback.data.split("_")[2])
    order = get_order(order_id)
    user = get_user(callback.from_user.id)

    if not order or not user:
        await callback.answer("❌ Ошибка")
        return

    lang = user['language']

    # Check if user is part of this order
    if callback.from_user.id not in [order['client_id'], order.get('selected_freelancer')]:
        await callback.answer(get_text("error_not_your_order", lang))
        return

    # Determine who confirmed
    is_client = callback.from_user.id == order['client_id']
    is_freelancer = callback.from_user.id == order.get('selected_freelancer')

    # Update confirmation status
    if is_client:
        update_order(order_id, {'client_confirmed': True})
        order['client_confirmed'] = True
    elif is_freelancer:
        update_order(order_id, {'freelancer_confirmed': True})
        order['freelancer_confirmed'] = True

    # Check if both confirmed
    if order.get('client_confirmed') and order.get('freelancer_confirmed'):
        # Both confirmed - transfer money automatically
        update_order(order_id, {'status': 'completed', 'completed_at': datetime.now().isoformat()})

        # Transfer money from frozen balance to freelancer
        transfer_frozen_to_user(order['client_id'], order['selected_freelancer'], order['budget'])

        client = get_user(order['client_id'])
        freelancer = get_user(order['selected_freelancer'])

        # Notify client that order is completed and payment was transferred
        if client:
            client_lang = client['language']
            client_completion_text = f"""
🎉 <b>{"Заказ успешно завершен!" if client_lang == "ru" else "Sargyt üstünlikli tamamlandy!"}</b>

📋 <b>{"Заказ" if client_lang == "ru" else "Sargyt"} #{order_id}:</b> {escape_html(order['title'])}
👤 <b>{"Фрилансер" if client_lang == "ru" else "Frilanser"}:</b> {escape_html(freelancer['first_name'])}
💰 <b>{"Списано с баланса" if client_lang == "ru" else "Balansdan çykaryldy"}:</b> {order['budget']} TMT

🛡️ {"Средства переведены фрилансеру. Сделка завершена!" if client_lang == "ru" else "Serişdeler frilanser geçirildi. Geleşik tamamlandy!"}

⭐ {"Помогите другим пользователям - оставьте отзыв о фрилансере:" if client_lang == "ru" else "Beýleki ulanyjylara kömek ediň - frilanser barada teswir galdyryň:"}
"""

            review_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="⭐ Оставить отзыв" if client_lang == "ru" else "⭐ Teswir galdyrmak",
                    callback_data=f"review_{order_id}_{freelancer['id']}_{client['id']}"
                )]
            ])

            await callback.bot.send_message(
                order['client_id'],
                client_completion_text,
                parse_mode="HTML",
                reply_markup=review_keyboard
            )

        # Notify freelancer that payment was received
        if freelancer:
            freelancer_lang = freelancer['language']
            freelancer_completion_text = f"""
💰 <b>{"Заказ завершен! Средства зачислены на баланс." if freelancer_lang == "ru" else "Sargyt tamamlandy! Serişdeler balansa geçirildi."}</b>

📋 <b>{"Заказ" if freelancer_lang == "ru" else "Sargyt"} #{order_id}:</b> {escape_html(order['title'])}
👤 <b>{"Заказчик" if freelancer_lang == "ru" else "Müşderi"}:</b> {escape_html(client['first_name'])}
💰 <b>{"Зачислено на баланс" if freelancer_lang == "ru" else "Balansa geçirildi"}:</b> {order['budget']} TMT

💳 {"Средства доступны для вывода через кнопку 'Вывод средств'" if freelancer_lang == "ru" else "Serişdeler 'Çykarmak' düwmesi arkaly çykarmak üçin elýeterli"}
⚠️ {"При выводе взимается комиссия 10%" if freelancer_lang == "ru" else "Çykaranda 10% komissiýa alynýar"}

🎉 {"Поздравляем с успешным завершением работы!" if freelancer_lang == "ru" else "Işiň üstünlikli tamamlanmagy bilen gutlaýarys!"}
"""

            review_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="⭐ Оставить отзыв заказчику" if freelancer_lang == "ru" else "⭐ Müşderi barada teswir",
                    callback_data=f"review_{order_id}_{client['id']}_{freelancer['id']}"
                )]
            ])

            await callback.bot.send_message(
                order['selected_freelancer'],
                freelancer_completion_text,
                parse_mode="HTML",
                reply_markup=review_keyboard
            )

        await callback.answer("✅ Заказ завершен, средства переведены!" if lang == "ru" else "✅ Sargyt tamamlandy, serişdeler geçirildi!")
    else:
        # Only one side confirmed
        confirmation_status = ""
        if order.get('client_confirmed'):
            confirmation_status = "✅ Заказчик подтвердил" if lang == "ru" else "✅ Müşderi tassyklady"
        if order.get('freelancer_confirmed'):
            if confirmation_status:
                confirmation_status += "\n"
            confirmation_status += "✅ Фрилансер подтвердил" if lang == "ru" else "✅ Frilanser tassyklady"

        status_text = f"""
⏳ <b>{"Ожидается подтверждение от обеих сторон" if lang == "ru" else "Iki tarapyň tassyklamagyna garaşylýar"}</b>

{confirmation_status}
"""

        await callback.message.edit_text(status_text, parse_mode="HTML")
        await callback.answer("✅ Ваше подтверждение принято" if lang == "ru" else "✅ Siziň tassyklamaňyz kabul edildi")



# Profile handlers
@router.message(F.text.in_(["👤 Профиль", "👤 Profil"]))
async def show_profile(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')
    profile_text = format_profile_text(user, lang)
    await message.answer(profile_text, reply_markup=get_profile_edit_keyboard(lang), parse_mode="HTML")

@router.callback_query(F.data == "edit_name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await callback.message.answer("Введите новое имя:" if lang == "ru" else "Täze ady giriziň:", reply_markup=get_back_keyboard(lang))
    await state.set_state(ProfileStates.waiting_new_name)
    await callback.answer()

@router.message(ProfileStates.waiting_new_name)
async def name_updated(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    if message.text == get_text("btn_back", lang):
        await show_profile(message)
        await state.clear()
        return

    # Update user profile
    profile = user.get('profile', {})
    profile['name'] = message.text
    update_user(message.from_user.id, {'profile': profile})

    await message.answer(get_text("profile_updated", lang))
    await show_profile(message)
    await state.clear()

@router.callback_query(F.data == "edit_skills")
async def edit_skills(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await callback.message.answer("Введите новые навыки:" if lang == "ru" else "Täze başarnyklary giriziň:", reply_markup=get_back_keyboard(lang))
    await state.set_state(ProfileStates.waiting_new_skills)
    await callback.answer()

@router.message(ProfileStates.waiting_new_skills)
async def skills_updated(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    if message.text == get_text("btn_back", lang):
        await show_profile(message)
        await state.clear()
        return

    # Update user profile
    profile = user.get('profile', {})
    profile['skills'] = message.text
    update_user(message.from_user.id, {'profile': profile})

    await message.answer(get_text("profile_updated", lang))
    await show_profile(message)
    await state.clear()

@router.callback_query(F.data == "edit_description")
async def edit_description(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await callback.message.answer("Введите новое описание:" if lang == "ru" else "Täze beýany giriziň:", reply_markup=get_back_keyboard(lang))
    await state.set_state(ProfileStates.waiting_new_description)
    await callback.answer()

@router.message(ProfileStates.waiting_new_description)
async def description_updated(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    if message.text == get_text("btn_back", lang):
        await show_profile(message)
        await state.clear()
        return

    # Update user profile
    profile = user.get('profile', {})
    profile['description'] = message.text
    update_user(message.from_user.id, {'profile': profile})

    await message.answer(get_text("profile_updated", lang))
    await show_profile(message)
    await state.clear()

@router.callback_query(F.data == "edit_contact")
async def edit_contact(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await callback.message.answer("Введите новый контакт:" if lang == "ru" else "Täze kontakty giriziň:", reply_markup=get_back_keyboard(lang))
    await state.set_state(ProfileStates.waiting_new_contact)
    await callback.answer()

@router.message(ProfileStates.waiting_new_contact)
async def contact_updated(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    if message.text == get_text("btn_back", lang):
        await show_profile(message)
        await state.clear()
        return

    # Update user profile
    profile = user.get('profile', {})
    profile['contact'] = message.text
    update_user(message.from_user.id, {'profile': profile})

    await message.answer(get_text("profile_updated", lang))
    await show_profile(message)
    await state.clear()

# Reviews handlers
@router.message(F.text.in_(["📝 Отзывы", "📝 Synlar"]))
async def show_reviews(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')
    reviews = get_user_reviews(message.from_user.id)

    if not reviews:
        await message.answer(get_text("no_reviews", lang))
        return

    await message.answer(get_text("reviews_about_you", lang))
    for review in reviews:
        review_text = format_review_text(review, lang)
        await message.answer(review_text, parse_mode="HTML")

@router.callback_query(F.data.startswith("review_"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    order_id, reviewed_id, reviewer_id = int(parts[1]), int(parts[2]), int(parts[3])

    user = get_user(callback.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')

    ## Check if user can leave review
    if not can_leave_review(order_id, reviewer_id, reviewed_id):
        await callback.answer(get_text("review_error", lang))
        return

    await state.update_data(order_id=order_id, reviewed_id=reviewed_id, reviewer_id=reviewer_id)
    await callback.message.edit_text(get_text("select_rating", lang), reply_markup=get_rating_keyboard(lang))
    await state.set_state(ReviewStates.waiting_rating)
    await callback.answer()

@router.callback_query(F.data.startswith("rating_"), StateFilter(ReviewStates.waiting_rating))
async def rating_selected(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await state.update_data(rating=rating)
    await callback.message.edit_text(get_text("enter_review_text", lang))
    await state.set_state(ReviewStates.waiting_review_text)
    await callback.answer()

@router.message(ReviewStates.waiting_review_text)
async def review_text_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    data = await state.get_data()
    order_id = data['order_id']
    reviewed_id = data['reviewed_id']
    reviewer_id = data['reviewer_id']
    rating = data['rating']

    review_data = {
        'rating': rating,
        'text': message.text
    }

    if add_review(order_id, reviewer_id, reviewed_id, review_data):
        await message.answer(get_text("review_added", lang))
    else:
        await message.answer(get_text("review_error", lang))

    await state.clear()

# Role change handler
@router.message(F.text.in_(["🔄 Сменить роль", "🔄 Roly üýtgetmek"]))
async def change_role(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')
    current_role = user.get('role')
    new_role = 'client' if current_role == 'freelancer' else 'freelancer'

    update_user(message.from_user.id, {'role': new_role})

    welcome_text = get_text(f"main_menu_{new_role}", lang)
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(new_role, lang, message.from_user.id))

# Change language handler
@router.message(F.text.in_(["🌐 Сменить язык", "🌐 Dil üýtgetmek"]))
async def change_language(message: Message):
    """Change user language"""
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await message.answer("❌ Пользователь не найден / Ulanyjy tapylmady")
        return

    await message.answer(
        get_text("choose_language"),
        reply_markup=get_language_keyboard()
    )

# Settings handler
@router.message(F.text.in_(["⚙️ Настройки", "⚙️ Sazlamalar"]))
async def show_settings(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')
    settings_text = get_text("settings_menu", lang)
    await message.answer(settings_text, reply_markup=get_settings_keyboard(lang))

# Back from settings handler
@router.message(F.text == "◀️ Назад")
async def back_from_settings(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')
    role = user.get('role')
    welcome_text = get_text(f"main_menu_{role}", lang)
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(role, lang, message.from_user.id))

@router.message(F.text == "◀️ Yza")
async def back_from_settings_tm(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'tm')
    role = user.get('role')
    welcome_text = get_text(f"main_menu_{role}", lang)
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(role, lang, message.from_user.id))

# Partners handler
@router.message(F.text.in_(["🤝 Партнёры", "🤝 Hyzmatdaşlar"]))
async def show_partners(message: Message):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru') if user else 'ru'

    partners_text = f"""
{get_text("partners_title", lang)}

💰 <b>FinanceTM Gazanç</b>
{get_text("partners_finance_tm", lang)}

🔗 <b>{"Ссылка" if lang == "ru" else "Baglanyşyk"}:</b> https://t.me/finance_tm_gazanc

📱 {"Подписывайтесь на канал для получения актуальной финансовой информации!" if lang == "ru" else "Häzirki maliýe maglumatlaryny almak üçin kanala ýazylyň!"}
"""

    # Create inline keyboard with channel link
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Перейти в канал" if lang == "ru" else "📱 Kanala geçmek", url="https://t.me/finance_tm_gazanc")]
    ])

    await message.answer(partners_text, reply_markup=keyboard, parse_mode="HTML")

# Help handler
@router.message(F.text.in_(["❓ Помощь", "❓ Kömek"]))
async def show_help(message: Message):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru') if user else 'ru'

    help_text = """
🤖 <b>FreelanceTM Bot - Справка</b>

📋 <b>Основные функции:</b>
• Создание и просмотр заказов
• Система откликов фрилансеров
• Безопасная оплата через эскроу
• Система отзывов и рейтингов
• Смена роли между фрилансером и заказчиком

💰 <b>Система оплаты:</b>
• Комиссия платформы: 10%
• Гарантийная блокировка средств
• Зачисление на баланс после завершения
• Вывод средств с комиссией 10%

🚫 <b>Правила платформы:</b>
• ВСЕ ПЛАТЕЖИ ТОЛЬКО ЧЕРЕЗ ПЛАТФОРМУ!
• Прямые переводы между пользователями ЗАПРЕЩЕНЫ!
• Нарушение правил = блокировка аккаунта
• Платформа гарантирует безопасность сделок

📞 <b>Поддержка:</b>
📧 Email: freelancetmbot@gmail.com
👤 Администратор: @FreelanceTM_admin
💬 По всем вопросам обращайтесь к администратору
""" if lang == "ru" else """
🤖 <b>FreelanceTM Bot - Kömek</b>

📋 <b>Esasy funksiýalar:</b>
• Sargyt döretmek we görmek
• Frilanser jogap ulgamy
• Howpsuz töleg (eskrou)
• Teswir we reýting ulgamy
• Frilanser we müşderi arasynda rol üýtgetmek

💰 <b>Töleg ulgamy:</b>
• Platformanyň komissiýasy: 10%
• Kepilli pul petiklemek
• Tamamlanandan soň balansa geçirmek
• 10% komissiýa bilen çykarmak

🚫 <b>Platforma düzgünleri:</b>
• ÄHLI TÖLEGLER DIŇE PLATFORMA ARKALY!
• Ulanyjylaryň arasynda göni geçirmeler GADAGAN!
• Düzgünleri bozmak = hasaby petiklemek
• Platforma geleşikleriň howpsuzlygyny kepillendirýär

📞 <b>Goldaw:</b>
📧 Email: freelancetmbot@gmail.com
👤 Administrator: @FreelanceTM_admin
💬 Ähli soraglar üçin administratora ýüz tutuň
"""

    await message.answer(help_text, parse_mode="HTML")

# =============================================================================
# SERVICE HANDLERS
# =============================================================================

# My services handler for freelancers
@router.message(F.text.in_(["🧰 Мои услуги", "🧰 Meniň hyzmatlarym"]))
async def my_services_menu(message: Message):
    user = get_user(message.from_user.id)
    if not user or user.get('role') != 'freelancer':
        lang = user.get('language', 'ru') if user else 'ru'
        await message.answer(get_text("error_not_freelancer", lang))
        return

    lang = user.get('language', 'ru')
    services_text = "🧰 Управление услугами" if lang == "ru" else "🧰 Hyzmat dolandyryş"
    await message.answer(services_text, reply_markup=get_services_menu_keyboard(lang))

# Find freelancer handler for clients
@router.message(F.text.in_(["🔍 Найти фрилансера", "🔍 Frilanser tapmak"]))
async def find_freelancer(message: Message):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru') if user else 'ru'

    await message.answer(get_text("service_add_category", lang), reply_markup=get_categories_keyboard(lang))

# Client balance handler
@router.message(F.text.in_(["💰 Мой баланс", "💰 Meniň balansym"]))
async def show_client_balance(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')
    balance = get_user_balance(user['id'])
    frozen = get_user_frozen_balance(user['id'])
    total = balance + frozen

    balance_text = get_text("balance_info_client", lang).format(
        balance=format_price(balance),
        frozen=format_price(frozen),
        total=format_price(total)
    )

    await message.answer(balance_text, reply_markup=get_balance_menu_keyboard(lang))

# Topup balance callback
@router.callback_query(F.data == "topup_balance")
async def topup_balance_start(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await callback.message.edit_text(get_text("topup_amount", lang))
    await state.set_state(BalanceStates.waiting_topup_amount)
    await callback.answer()

# Withdraw balance callback
@router.callback_query(F.data == "withdraw_balance")
async def withdraw_balance_start(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    balance = get_user_balance(user['id'])
    if balance <= 0:
        await callback.message.edit_text(get_text("withdraw_insufficient_funds", lang))
        await callback.answer()
        return

    await callback.message.edit_text(get_text("withdraw_amount", lang))
    await state.set_state(WithdrawalStates.waiting_amount)
    await callback.answer()

# Topup amount input
@router.message(BalanceStates.waiting_topup_amount)
async def topup_amount_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Введите корректную сумму" if lang == "ru" else "❌ Dogry mukdar giriziň")
            return

        # Create topup request
        request = create_balance_request(user['id'], 'topup', amount)

        # Notify user
        await message.answer(get_text("topup_request_sent", lang))

        # Notify admin
        admin_text = get_text("admin_topup_request", lang) + "\n\n"
        username_text = f"@{user.get('username')}" if user.get('username') else "нет username"
        admin_text += get_text("admin_topup_info", lang).format(
            user_name=user.get('first_name', 'Unknown'),
            user_id=user['id'],
            amount=format_price(amount),
            balance=format_price(get_user_balance(user['id']))
        )
        admin_text += f"\n📱 <b>Username:</b> {username_text}"

        for admin_id in ADMIN_IDS:
            await message.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=get_admin_topup_keyboard(request['id'], lang),
                parse_mode="HTML"
            )

        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат суммы" if lang == "ru" else "❌ Nädogry mukdar formaty")

# Admin confirm topup
@router.callback_query(F.data.startswith("admin_confirm_topup_"))
async def admin_confirm_topup(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return

    request_id = int(callback.data.split("_")[3])
    request = withdrawals_db.get(str(request_id))

    if not request or request['type'] != 'topup':
        await callback.answer("❌ Запрос не найден")
        return

    # Add money to user balance
    add_to_balance(request['user_id'], request['amount'])

    # Update request status
    request['status'] = 'completed'
    save_all_data()

    # Notify user
    target_user = get_user(request['user_id'])
    if target_user:
        user_lang = target_user.get('language', 'ru')
        user_text = get_text("topup_confirmed", user_lang).format(amount=format_price(request['amount']))
        await send_notification(callback.bot, request['user_id'], user_text)

    await callback.message.edit_text(f"✅ Пополнение на {request['amount']} TMT подтверждено")
    await callback.answer()

# Service ordering callback
@router.callback_query(F.data.startswith("order_service_"))
async def order_service_start(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split("_")[2])
    service = get_service(service_id)
    user = get_user(callback.from_user.id)

    if not service or not user:
        await callback.answer("❌ Услуга не найдена")
        return

    lang = user.get('language', 'ru')

    # Check if user is trying to order their own service
    if service['user_id'] == user['id']:
        await callback.answer("❌ Нельзя заказать свою услугу" if lang == "ru" else "❌ Öz hyzmatyňyzy sargyt edip bolmaýar")
        return

    # Show confirmation
    price_text = service['price']
    confirm_text = get_text("service_order_confirm", lang).format(price=price_text)
    
    await state.update_data(service_id=service_id)
    await callback.message.edit_text(confirm_text, reply_markup=get_service_order_confirmation_keyboard(service_id, lang))
    await callback.answer()

# Confirm service order
@router.callback_query(F.data.startswith("confirm_service_order_"))
async def confirm_service_order(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split("_")[3])
    service = get_service(service_id)
    user = get_user(callback.from_user.id)

    if not service or not user:
        await callback.answer("❌ Ошибка")
        return

    lang = user.get('language', 'ru')

    # Try to parse price from service
    try:
        price_str = service['price'].replace('TMT', '').replace('тмт', '').strip()
        # Remove any non-numeric characters except decimal point
        import re
        price_match = re.search(r'(\d+(?:\.\d+)?)', price_str)
        if price_match:
            amount = float(price_match.group(1))
        else:
            # If can't parse, ask admin to handle manually
            amount = 0
    except:
        amount = 0

    if amount > 0:
        # Check balance
        balance = get_user_balance(user['id'])
        if balance < amount:
            await callback.message.edit_text(get_text("service_order_insufficient", lang))
            await callback.answer()
            return

        # Freeze balance
        freeze_balance(user['id'], amount)
    
    # Create service order
    order_data = {
        'client_id': user['id'],
        'freelancer_id': service['user_id'],
        'service_id': service_id,
        'service_title': service['title'],
        'amount': amount,
        'client_name': user.get('first_name', 'Unknown'),
        'freelancer_name': get_user(service['user_id']).get('first_name', 'Unknown') if get_user(service['user_id']) else 'Unknown'
    }
    
    order = create_service_order(order_data)

    # Notify client
    await callback.message.edit_text(get_text("service_order_success", lang))

    # Notify freelancer
    freelancer = get_user(service['user_id'])
    if freelancer:
        freelancer_lang = freelancer.get('language', 'ru')
        freelancer_text = get_text("freelancer_new_order", freelancer_lang).format(
            service_title=service['title'],
            client_name=user.get('first_name', 'Unknown'),
            amount=f"{amount} TMT" if amount > 0 else service['price']
        )
        await send_notification(callback.bot, service['user_id'], freelancer_text)

    # Notify admin
    client_username = f"@{user.get('username')}" if user.get('username') else "нет"
    freelancer_username = f"@{freelancer.get('username')}" if freelancer and freelancer.get('username') else "нет"
    
    admin_text = f"""
{get_text("admin_service_order", "ru")}

📋 <b>Услуга:</b> {escape_html(service['title'])}
💰 <b>Стоимость:</b> {service['price']}
👤 <b>Заказчик:</b> {escape_html(user.get('first_name', 'Unknown'))} ({client_username})
   ID: <code>{user['id']}</code>
👨‍💻 <b>Фрилансер:</b> {escape_html(freelancer.get('first_name', 'Unknown') if freelancer else 'Unknown')} ({freelancer_username})
   ID: <code>{service['user_id']}</code>
🆔 <b>ID заказа:</b> {order['id']}

💰 <b>Заблокированная сумма:</b> {amount} TMT
"""

    for admin_id in ADMIN_IDS:
        await callback.bot.send_message(
            admin_id,
            admin_text,
            reply_markup=get_admin_service_order_keyboard(order['id'], "ru"),
            parse_mode="HTML"
        )

    await callback.answer()
    await state.clear()

# Cancel service order
@router.callback_query(F.data == "cancel_service_order")
async def cancel_service_order(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')
    
    await callback.message.edit_text("❌ Заказ отменен" if lang == "ru" else "❌ Sargyt ýatyryldy")
    await callback.answer()
    await state.clear()

# Admin confirm service order
@router.callback_query(F.data.startswith("admin_confirm_service_order_"))
async def admin_confirm_service_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return

    order_id = int(callback.data.split("_")[4])
    order = get_order(order_id)

    if not order or order.get('type') != 'service_order':
        await callback.answer("❌ Заказ не найден")
        return

    # Update order status
    update_order(order_id, {'status': 'in_progress', 'confirmed_by_admin': True})

    client = get_user(order['client_id'])
    freelancer = get_user(order['freelancer_id'])

    # Notify client
    if client:
        client_lang = client.get('language', 'ru')
        client_text = f"✅ {'Ваш заказ подтвержден администратором!' if client_lang == 'ru' else 'Sargydyňyz administrator tarapyndan tassyklandy!'}\n\n📋 {order['service_title']}"
        await send_notification(callback.bot, order['client_id'], client_text)

    # Notify freelancer
    if freelancer:
        freelancer_lang = freelancer.get('language', 'ru')
        freelancer_text = f"🎉 {'Администратор подтвердил заказ! Можете начинать работу.' if freelancer_lang == 'ru' else 'Administrator sargyt tassyklady! Işe başlap bilersiňiz.'}\n\n📋 {order['service_title']}"
        
        # Add completion button
        completion_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Работа завершена" if freelancer_lang == "ru" else "✅ Iş tamamlandy",
                callback_data=f"service_work_completed_{order_id}"
            )]
        ])
        
        await callback.bot.send_message(order['freelancer_id'], freelancer_text, reply_markup=completion_keyboard)

    await callback.message.edit_text(f"✅ Заказ услуги #{order_id} подтвержден")
    await callback.answer()

# Admin reject service order  
@router.callback_query(F.data.startswith("admin_reject_service_order_"))
async def admin_reject_service_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return

    order_id = int(callback.data.split("_")[4])
    order = get_order(order_id)

    if not order or order.get('type') != 'service_order':
        await callback.answer("❌ Заказ не найден")
        return

    # Unfreeze balance if any
    if order.get('amount', 0) > 0:
        unfreeze_balance(order['client_id'], order['amount'])

    # Update order status
    update_order(order_id, {'status': 'cancelled'})

    client = get_user(order['client_id'])
    freelancer = get_user(order['freelancer_id'])

    # Notify both parties
    if client:
        client_lang = client.get('language', 'ru')
        client_text = f"❌ {'Заказ отклонен администратором. Средства разблокированы.' if client_lang == 'ru' else 'Sargyt administrator tarapyndan ret edildi. Serişdeler açyldy.'}"
        await send_notification(callback.bot, order['client_id'], client_text)

    if freelancer:
        freelancer_lang = freelancer.get('language', 'ru')
        freelancer_text = f"❌ {'Заказ отклонен администратором.' if freelancer_lang == 'ru' else 'Sargyt administrator tarapyndan ret edildi.'}"
        await send_notification(callback.bot, order['freelancer_id'], freelancer_text)

    await callback.message.edit_text(f"❌ Заказ услуги #{order_id} отклонен")
    await callback.answer()

# Service work completed
@router.callback_query(F.data.startswith("service_work_completed_"))
async def service_work_completed(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = get_order(order_id)
    user = get_user(callback.from_user.id)

    if not order or not user or order.get('freelancer_id') != user['id']:
        await callback.answer("❌ Ошибка")
        return

    lang = user.get('language', 'ru')

    # Update order - waiting for client confirmation
    update_order(order_id, {'freelancer_completed': True})

    client = get_user(order['client_id'])
    if client:
        client_lang = client.get('language', 'ru')
        client_text = f"""
✅ {'Фрилансер завершил работу!' if client_lang == 'ru' else 'Frilanser işi gutardy!'}

📋 <b>{'Услуга' if client_lang == 'ru' else 'Hyzmat'}:</b> {escape_html(order['service_title'])}
👨‍💻 <b>{'Фрилансер' if client_lang == 'ru' else 'Frilanser'}:</b> {escape_html(order['freelancer_name'])}

{'Подтвердите завершение работы, если результат вас устраивает:' if client_lang == 'ru' else 'Netije ýaramsa, işiň tamamlanmagyny tassyklaň:'}
"""

        completion_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Подтвердить завершение" if client_lang == "ru" else "✅ Tamamlamagy tassyklamak",
                callback_data=f"client_confirm_service_{order_id}"
            )]
        ])

        await callback.bot.send_message(order['client_id'], client_text, reply_markup=completion_keyboard, parse_mode="HTML")

    await callback.message.edit_text("✅ Ваша заявка о завершении отправлена заказчику" if lang == "ru" else "✅ Tamamlamak barada habarlamanyňyz müşderi iberldi")
    await callback.answer()

# Client confirm service completion
@router.callback_query(F.data.startswith("client_confirm_service_"))
async def client_confirm_service(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    order = get_order(order_id)
    user = get_user(callback.from_user.id)

    if not order or not user or order.get('client_id') != user['id']:
        await callback.answer("❌ Ошибка")
        return

    lang = user.get('language', 'ru')

    # Transfer money from frozen to freelancer
    if order.get('amount', 0) > 0:
        transfer_frozen_to_user(order['client_id'], order['freelancer_id'], order['amount'])

    # Update order status
    update_order(order_id, {'status': 'completed', 'completed_at': datetime.now().isoformat()})

    # Notify freelancer
    freelancer = get_user(order['freelancer_id'])
    if freelancer:
        freelancer_lang = freelancer.get('language', 'ru')
        freelancer_text = f"""
🎉 {'Заказ завершен! Средства зачислены на баланс.' if freelancer_lang == 'ru' else 'Sargyt tamamlandy! Serişdeler balansa geçirildi.'}

📋 <b>{'Услуга' if freelancer_lang == 'ru' else 'Hyzmat'}:</b> {escape_html(order['service_title'])}
💰 <b>{'Зачислено' if freelancer_lang == 'ru' else 'Geçirildi'}:</b> {order.get('amount', 0)} TMT
"""
        await send_notification(callback.bot, order['freelancer_id'], freelancer_text)

    await callback.message.edit_text("✅ Заказ завершен! Спасибо за использование платформы!" if lang == "ru" else "✅ Sargyt tamamlandy! Platformany ulananyňyz üçin sag boluň!")
    await callback.answer()

# Update the service display to include order button
@router.callback_query(F.data.startswith("category_"), ~StateFilter(ServiceStates.waiting_category))
async def find_services_by_category(callback: CallbackQuery):
    category = callback.data.split("_")[1]
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru') if user else 'ru'

    services = get_services_by_category(category)

    if not services:
        await callback.message.edit_text(get_text("no_services_in_category", lang))
        return

    await callback.message.edit_text(get_text("services_in_category", lang))

    for service in services[:10]:  # Show first 10 services
        service_text = format_service_text(service, lang)
        # Use updated keyboard with order button
        keyboard = get_service_contact_keyboard(service['user_id'], service['id'], lang)
        await callback.message.answer(service_text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()

# Add service callback
@router.callback_query(F.data == "add_service")
async def add_service_start(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if not user or user.get('role') != 'freelancer':
        lang = user.get('language', 'ru') if user else 'ru'
        await callback.answer(get_text("error_not_freelancer", lang))
        return

    lang = user.get('language', 'ru')
    
    # Check service limit
    user_services = get_user_services(callback.from_user.id)
    if len(user_services) >= 3:
        await callback.answer(get_text("service_limit_reached", lang))
        return

    await callback.message.edit_text(get_text("service_add_category", lang), reply_markup=get_categories_keyboard(lang))
    await state.set_state(ServiceStates.waiting_category)
    await callback.answer()

# View my services callback
@router.callback_query(F.data == "view_my_services")
async def view_my_services(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user or user.get('role') != 'freelancer':
        lang = user.get('language', 'ru') if user else 'ru'
        await callback.answer(get_text("error_not_freelancer", lang))
        return

    lang = user.get('language', 'ru')
    services = get_user_services(callback.from_user.id)

    if not services:
        await callback.message.edit_text(get_text("no_services", lang))
        return

    await callback.message.edit_text(get_text("my_services_list", lang))
    
    for service in services:
        service_text = format_service_text(service, lang, show_contact=False)
        keyboard = get_service_actions_keyboard(service['id'], lang)
        await callback.message.answer(service_text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()

# Service category selection for adding service
@router.callback_query(F.data.startswith("category_"), StateFilter(ServiceStates.waiting_category))
async def service_category_selected(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[1]
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await state.update_data(category=category)
    await callback.message.edit_text(get_text("service_add_title", lang))
    await state.set_state(ServiceStates.waiting_title)
    await callback.answer()

# Service category selection for finding freelancers
@router.callback_query(F.data.startswith("category_"), ~StateFilter(ServiceStates.waiting_category))
async def find_services_by_category(callback: CallbackQuery):
    category = callback.data.split("_")[1]
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru') if user else 'ru'

    services = get_services_by_category(category)

    if not services:
        await callback.message.edit_text(get_text("no_services_in_category", lang))
        return

    await callback.message.edit_text(get_text("services_in_category", lang))

    for service in services[:10]:  # Show first 10 services
        service_text = format_service_text(service, lang)
        keyboard = get_service_contact_keyboard(service['user_id'], lang)
        await callback.message.answer(service_text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()

# Service title input
@router.message(ServiceStates.waiting_title)
async def service_title_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    await state.update_data(title=message.text)
    await message.answer(get_text("service_add_description", lang))
    await state.set_state(ServiceStates.waiting_description)

# Service description input
@router.message(ServiceStates.waiting_description)
async def service_description_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    await state.update_data(description=message.text)
    await message.answer(get_text("service_add_price", lang))
    await state.set_state(ServiceStates.waiting_price)

# Service price input
@router.message(ServiceStates.waiting_price)
async def service_price_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    data = await state.get_data()
    
    # Show confirmation
    category_name = CATEGORIES.get(lang, CATEGORIES["ru"]).get(data['category'], data['category'])
    confirm_text = f"""
{get_text("service_confirm", lang)}

🏷️ <b>{"Категория" if lang == "ru" else "Kategoriýa"}:</b> {category_name}
📝 <b>{"Название" if lang == "ru" else "Ady"}:</b> {escape_html(data['title'])}
📋 <b>{"Описание" if lang == "ru" else "Beýany"}:</b> {escape_html(data['description'])}
💰 <b>{"Цена" if lang == "ru" else "Baha"}:</b> {escape_html(message.text)}
"""

    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да" if lang == "ru" else "✅ Hawa", callback_data="confirm_add_service"),
            InlineKeyboardButton(text="❌ Нет" if lang == "ru" else "❌ Ýok", callback_data="cancel_add_service")
        ]
    ])

    await state.update_data(price=message.text)
    await message.answer(confirm_text, reply_markup=confirm_keyboard, parse_mode="HTML")
    await state.set_state(ServiceStates.waiting_confirm)

# Confirm add service
@router.callback_query(F.data == "confirm_add_service", StateFilter(ServiceStates.waiting_confirm))
async def confirm_add_service(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    data = await state.get_data()

    service_data = {
        'user_id': callback.from_user.id,
        'username': callback.from_user.username,
        'category': data['category'],
        'title': data['title'],
        'description': data['description'],
        'price': data['price']
    }

    create_service(service_data)

    await callback.message.edit_text(get_text("service_added", lang))
    await callback.answer()
    await state.clear()

# Cancel add service
@router.callback_query(F.data == "cancel_add_service", StateFilter(ServiceStates.waiting_confirm))
async def cancel_add_service(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await callback.message.edit_text("❌ Добавление услуги отменено" if lang == "ru" else "❌ Hyzmat goşmak ýatyryldy")
    await callback.answer()
    await state.clear()

# Delete service
@router.callback_query(F.data.startswith("delete_service_"))
async def delete_service_callback(callback: CallbackQuery):
    service_id = int(callback.data.split("_")[2])
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    service = get_service(service_id)
    if not service or service['user_id'] != callback.from_user.id:
        await callback.answer("❌ Услуга не найдена" if lang == "ru" else "❌ Hyzmat tapylmady")
        return

    delete_service(service_id)
    await callback.message.edit_text(get_text("service_deleted", lang))
    await callback.answer()

# Edit service (placeholder - can be extended)
@router.callback_query(F.data.startswith("edit_service_"))
async def edit_service_callback(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')
    
    await callback.answer("🚧 Функция редактирования в разработке" if lang == "ru" else "🚧 Üýtgetmek funksiýasy ösdürilýär")

# Admin handlers
@router.message(F.text.in_(["⚙️ Админ панель", "⚙️ Admin paneli"]))
async def admin_panel_button(message: Message):
    """Admin panel button handler"""
    await admin_command(message)

@router.message(Command("admin"))
async def admin_command(message: Message):
    """Admin panel command"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("❌ У вас нет доступа к админ панели")
        return

    stats = get_stats()
    stats_text = f"""
📊 <b>Статистика платформы</b>

👥 <b>Пользователи:</b>
• Всего: {stats['total_users']}
• Фрилансеры: {stats['freelancers']}
• Заказчики: {stats['clients']}

📋 <b>Заказы:</b>
• Всего: {stats['total_orders']}
• Активные: {stats['active_orders']}
• Завершенные: {stats['completed_orders']}

📝 <b>Отзывы:</b> {stats['total_reviews']}

💰 <b>Финансы:</b>
• Ожидают оплаты: {len([o for o in orders_db.values() if o.get('status') == 'payment_pending'])}
• Ожидают выплаты: {len([o for o in orders_db.values() if o.get('status') == 'completion_pending'])}
"""

    # Admin menu keyboard
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑️ Управление заказами", callback_data="admin_manage_orders"),
            InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_manage_users")
        ],
        [
            InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin_show_withdrawals"),
            InlineKeyboardButton(text="📊 Обновить статистику", callback_data="admin_refresh_stats")
        ]
    ])

    await message.answer(stats_text, reply_markup=admin_keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_manage_orders")
async def admin_manage_orders(callback: CallbackQuery):
    """Show orders management for admin"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    all_orders = list(orders_db.values())
    if not all_orders:
        await callback.message.edit_text("📭 Заказов нет")
        return

    # Show first 10 orders with delete buttons
    keyboard = []
    text = "🗑️ <b>Управление заказами</b>\n\n"
    
    for order in all_orders[:10]:
        status_emoji = get_status_emoji(order.get('status', 'active'))
        text += f"{status_emoji} <b>#{order['id']}</b> - {escape_html(truncate_text(order['title'], 30))}\n"
        text += f"💰 {order['budget']} TMT | 📅 {datetime.fromisoformat(order['created_at']).strftime('%d.%m')}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(text=f"🗑️ Удалить #{order['id']}", callback_data=f"admin_delete_order_{order['id']}")
        ])

    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_delete_order_"))
async def admin_delete_order(callback: CallbackQuery):
    """Delete order by admin"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    order_id = int(callback.data.split("_")[3])
    order = get_order(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден")
        return

    # Delete order
    if str(order_id) in orders_db:
        del orders_db[str(order_id)]
    
    # Delete responses
    if str(order_id) in responses_db:
        del responses_db[str(order_id)]
    
    # Delete related reviews
    reviews_to_delete = []
    for review_key, review in reviews_db.items():
        if review.get('order_id') == order_id:
            reviews_to_delete.append(review_key)
    
    for review_key in reviews_to_delete:
        del reviews_db[review_key]

    save_all_data()

    await callback.message.edit_text(f"✅ Заказ #{order_id} успешно удален")
    await callback.answer()

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    """Return to admin panel"""
    await admin_command(callback.message)
    await callback.answer()

@router.callback_query(F.data == "admin_refresh_stats")
async def admin_refresh_stats(callback: CallbackQuery):
    """Refresh admin statistics"""
    await admin_command(callback.message)
    await callback.answer("📊 Статистика обновлена")

@router.callback_query(F.data == "admin_manage_users")
async def admin_manage_users(callback: CallbackQuery):
    """Show users management for admin"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    all_users = list(users_db.values())
    if not all_users:
        await callback.message.edit_text("📭 Пользователей нет")
        return

    # Show first 10 users
    keyboard = []
    text = "👥 <b>Управление пользователями</b>\n\n"
    
    for user in all_users[:10]:
        role_emoji = "👨‍💻" if user.get('role') == 'freelancer' else "👤"
        username_text = f"@{user.get('username')}" if user.get('username') else "без username"
        balance = get_user_balance(user['id'])
        
        text += f"{role_emoji} <b>{escape_html(user.get('first_name', 'Unknown'))}</b> ({username_text})\n"
        text += f"💰 Баланс: {balance:.2f} TMT | ID: {user['id']}\n"
        text += f"📅 {datetime.fromisoformat(user['created_at']).strftime('%d.%m.%Y')}\n\n"

    keyboard.append([InlineKeyboardButton(text="💰 Управление балансами", callback_data="admin_manage_balances")])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_manage_balances")
async def admin_manage_balances(callback: CallbackQuery):
    """Show balance management for admin"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    all_users = list(users_db.values())
    if not all_users:
        await callback.message.edit_text("📭 Пользователей нет")
        return

    text = "💰 <b>Управление балансами</b>\n\n"
    text += "Выберите пользователя для управления балансом:\n\n"
    
    keyboard = []
    
    # Show first 10 users
    for user in all_users[:10]:
        role_emoji = "👨‍💻" if user.get('role') == 'freelancer' else "👤"
        username_text = f"@{user.get('username')}" if user.get('username') else "нет"
        balance = get_user_balance(user['id'])
        
        text += f"{role_emoji} <b>{escape_html(user.get('first_name', 'Unknown'))}</b> ({username_text})\n"
        text += f"💰 Баланс: {balance:.2f} TMT | ID: {user['id']}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{role_emoji} {user.get('first_name', 'Unknown')[:15]} - {balance:.2f} TMT",
                callback_data=f"admin_select_user_{user['id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="👥 Показать всех", callback_data="admin_show_all_users")])
    keyboard.append([InlineKeyboardButton(text="🔍 Найти по ID", callback_data="admin_search_user")])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_users")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_select_user_"))
async def admin_select_user(callback: CallbackQuery):
    """Select user for balance management"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    target_user_id = int(callback.data.split("_")[3])
    target_user = get_user(target_user_id)

    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return

    balance = get_user_balance(target_user_id)
    role_emoji = "👨‍💻" if target_user.get('role') == 'freelancer' else "👤"
    username_text = f"@{target_user.get('username')}" if target_user.get('username') else "нет"

    text = f"""
{role_emoji} <b>Управление балансом пользователя</b>

👤 <b>Имя:</b> {escape_html(target_user.get('first_name', 'Unknown'))}
🆔 <b>ID:</b> <code>{target_user_id}</code>
📱 <b>Username:</b> {username_text}
💰 <b>Текущий баланс:</b> {balance:.2f} TMT

Выберите действие:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить 10 TMT", callback_data=f"admin_balance_{target_user_id}_add_10"),
            InlineKeyboardButton(text="➕ Добавить 50 TMT", callback_data=f"admin_balance_{target_user_id}_add_50")
        ],
        [
            InlineKeyboardButton(text="➕ Добавить 100 TMT", callback_data=f"admin_balance_{target_user_id}_add_100"),
            InlineKeyboardButton(text="➕ Добавить 500 TMT", callback_data=f"admin_balance_{target_user_id}_add_500")
        ],
        [
            InlineKeyboardButton(text="➖ Списать 10 TMT", callback_data=f"admin_balance_{target_user_id}_subtract_10"),
            InlineKeyboardButton(text="➖ Списать 50 TMT", callback_data=f"admin_balance_{target_user_id}_subtract_50")
        ],
        [
            InlineKeyboardButton(text="🔄 Установить 0", callback_data=f"admin_balance_{target_user_id}_set_0"),
            InlineKeyboardButton(text="🔄 Установить 100", callback_data=f"admin_balance_{target_user_id}_set_100")
        ],
        [
            InlineKeyboardButton(text="📝 Произвольная сумма", callback_data=f"admin_custom_balance_{target_user_id}")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_balances")
        ]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_balance_"))
async def admin_balance_action(callback: CallbackQuery):
    """Execute balance action"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    parts = callback.data.split("_")
    target_user_id = int(parts[2])
    action = parts[3]
    amount = float(parts[4])

    target_user = get_user(target_user_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return

    old_balance = get_user_balance(target_user_id)

    try:
        if action == 'add':
            add_to_balance(target_user_id, amount)
            new_balance = get_user_balance(target_user_id)
            action_text = "добавлено"
            success = True
        elif action == 'subtract':
            if old_balance < amount:
                await callback.answer("❌ Недостаточно средств на балансе")
                return
            subtract_from_balance(target_user_id, amount)
            new_balance = get_user_balance(target_user_id)
            action_text = "списано"
            success = True
        elif action == 'set':
            target_user['balance'] = amount
            save_all_data()
            new_balance = amount
            action_text = "установлено"
            success = True
        else:
            success = False

        if success:
            # Update message with new balance
            balance_text = f"""
✅ <b>Баланс изменен</b>

👤 <b>Пользователь:</b> {escape_html(target_user.get('first_name', 'Unknown'))}
💰 <b>Было:</b> {old_balance:.2f} TMT
💰 <b>Стало:</b> {new_balance:.2f} TMT
📊 <b>Действие:</b> {action_text} {amount:.2f} TMT
"""

            # Notify user about balance change
            user_lang = target_user.get('language', 'ru')
            if action == 'add':
                user_text = f"💰 Ваш баланс пополнен на {amount:.2f} TMT\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💰 Balansyňyz {amount:.2f} TMT-e dolduryldy\nHäzirki balans: {new_balance:.2f} TMT"
            elif action == 'subtract':
                user_text = f"💸 С вашего баланса списано {amount:.2f} TMT\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💸 Balansyňyzdan {amount:.2f} TMT çykaryldy\nHäzirki balans: {new_balance:.2f} TMT"
            else:
                user_text = f"💰 Ваш баланс изменен администратором\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💰 Balansyňyz administrator tarapyndan üýtgedildi\nHäzirki balans: {new_balance:.2f} TMT"

            await send_notification(callback.bot, target_user_id, user_text)

            # Return to user selection with updated info
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Изменить еще", callback_data=f"admin_select_user_{target_user_id}")],
                [InlineKeyboardButton(text="◀️ К списку пользователей", callback_data="admin_manage_balances")]
            ])

            await callback.message.edit_text(balance_text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer("✅ Баланс изменен")

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}")

@router.callback_query(F.data.startswith("admin_custom_balance_"))
async def admin_custom_balance(callback: CallbackQuery, state: FSMContext):
    """Start custom balance input"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    target_user_id = int(callback.data.split("_")[3])
    target_user = get_user(target_user_id)

    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return

    await state.update_data(admin_target_user_id=target_user_id)

    text = f"""
📝 <b>Произвольное изменение баланса</b>

👤 <b>Пользователь:</b> {escape_html(target_user.get('first_name', 'Unknown'))}
💰 <b>Текущий баланс:</b> {get_user_balance(target_user_id):.2f} TMT

Отправьте команду в формате:
<code>действие сумма</code>

<b>Действия:</b>
• <code>add 100</code> - добавить 100 TMT
• <code>subtract 50</code> - списать 50 TMT
• <code>set 200</code> - установить баланс 200 TMT

Или нажмите "Отмена" для возврата.
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_select_user_{target_user_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_balance_command)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_balance_command))
async def admin_custom_balance_command(message: Message, state: FSMContext):
    """Handle custom balance command"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("❌ У вас нет доступа")
        await state.clear()
        return

    try:
        data = await state.get_data()
        target_user_id = data.get('admin_target_user_id')
        
        if not target_user_id:
            await message.answer("❌ Ошибка: пользователь не выбран")
            await state.clear()
            return

        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат. Используйте: действие сумма\nПример: add 100")
            return

        action = parts[0].lower()
        amount = float(parts[1])

        if action not in ['add', 'subtract', 'set']:
            await message.answer("❌ Действие должно быть: add, subtract или set")
            return

        if amount < 0:
            await message.answer("❌ Сумма должна быть положительной")
            return

        target_user = get_user(target_user_id)
        if not target_user:
            await message.answer("❌ Пользователь не найден")
            await state.clear()
            return

        old_balance = get_user_balance(target_user_id)

        if action == 'add':
            add_to_balance(target_user_id, amount)
            new_balance = get_user_balance(target_user_id)
            action_text = "добавлено"
        elif action == 'subtract':
            if old_balance < amount:
                await message.answer("❌ Недостаточно средств на балансе пользователя")
                return
            subtract_from_balance(target_user_id, amount)
            new_balance = get_user_balance(target_user_id)
            action_text = "списано"
        else:  # set
            target_user['balance'] = amount
            save_all_data()
            new_balance = amount
            action_text = "установлено"

        result_text = f"""
✅ <b>Баланс изменен</b>

👤 <b>Пользователь:</b> {escape_html(target_user.get('first_name', 'Unknown'))}
🆔 <b>ID:</b> {target_user_id}
💰 <b>Было:</b> {old_balance:.2f} TMT
💰 <b>Стало:</b> {new_balance:.2f} TMT
📊 <b>Действие:</b> {action_text} {amount:.2f} TMT
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Изменить еще", callback_data=f"admin_select_user_{target_user_id}")],
            [InlineKeyboardButton(text="◀️ К списку пользователей", callback_data="admin_manage_balances")]
        ])

        await message.answer(result_text, reply_markup=keyboard, parse_mode="HTML")

        # Notify user about balance change
        user_lang = target_user.get('language', 'ru')
        if action == 'add':
            user_text = f"💰 Ваш баланс пополнен на {amount:.2f} TMT\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💰 Balansyňyz {amount:.2f} TMT-e dolduryldy\nHäzirki balans: {new_balance:.2f} TMT"
        elif action == 'subtract':
            user_text = f"💸 С вашего баланса списано {amount:.2f} TMT\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💸 Balansyňyzdan {amount:.2f} TMT çykaryldy\nHäzirki balans: {new_balance:.2f} TMT"
        else:
            user_text = f"💰 Ваш баланс изменен администратором\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💰 Balansyňyz administrator tarapyndan üýtgedildi\nHäzirki balans: {new_balance:.2f} TMT"

        await send_notification(message.bot, target_user_id, user_text)
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат суммы")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.callback_query(F.data == "admin_search_user")
async def admin_search_user(callback: CallbackQuery, state: FSMContext):
    """Start user search by ID"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    text = """
🔍 <b>Поиск пользователя</b>

Отправьте ID пользователя для поиска.
Например: <code>123456789</code>

Или нажмите "Отмена" для возврата.
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_balances")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_user_search)
    await callback.answer()

@router.message(StateFilter(AdminStates.waiting_user_search))
async def admin_user_search_result(message: Message, state: FSMContext):
    """Handle user search result"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("❌ У вас нет доступа")
        await state.clear()
        return

    try:
        target_user_id = int(message.text.strip())
        target_user = get_user(target_user_id)

        if not target_user:
            await message.answer("❌ Пользователь не найден")
            return

        balance = get_user_balance(target_user_id)
        role_emoji = "👨‍💻" if target_user.get('role') == 'freelancer' else "👤"
        username_text = f"@{target_user.get('username')}" if target_user.get('username') else "нет"

        user_info = f"""
✅ <b>Пользователь найден</b>

{role_emoji} <b>Имя:</b> {escape_html(target_user.get('first_name', 'Unknown'))}
🆔 <b>ID:</b> <code>{target_user_id}</code>
📱 <b>Username:</b> {username_text}
🔰 <b>Роль:</b> {"Фрилансер" if target_user.get('role') == 'freelancer' else "Заказчик"}
💰 <b>Баланс:</b> {balance:.2f} TMT
📅 <b>Регистрация:</b> {datetime.fromisoformat(target_user['created_at']).strftime('%d.%m.%Y %H:%M')}
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Управлять балансом", callback_data=f"admin_select_user_{target_user_id}")],
            [InlineKeyboardButton(text="🔍 Искать другого", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_balances")]
        ])

        await message.answer(user_info, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат ID")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.callback_query(F.data == "admin_show_all_users")
async def admin_show_all_users(callback: CallbackQuery):
    """Show all users with their balances"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    all_users = list(users_db.values())
    if not all_users:
        await callback.message.edit_text("📭 Пользователей нет")
        return

    text = "👥 <b>Все пользователи с балансами:</b>\n\n"
    
    for user in all_users:
        role_emoji = "👨‍💻" if user.get('role') == 'freelancer' else "👤"
        username_text = f"@{user.get('username')}" if user.get('username') else "нет"
        balance = get_user_balance(user['id'])
        
        text += f"{role_emoji} <b>{escape_html(user.get('first_name', 'Unknown'))}</b>\n"
        text += f"Username: {username_text}\n"
        text += f"ID: <code>{user['id']}</code>\n"
        text += f"💰 Баланс: {balance:.2f} TMT\n"
        text += f"📅 {datetime.fromisoformat(user['created_at']).strftime('%d.%m.%Y')}\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_balances")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(Command("balance"))
async def admin_balance_command(message: Message):
    """Admin command to manage user balances"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    try:
        parts = message.text.split()
        if len(parts) != 4:
            await message.answer("❌ Неверный формат. Используйте: /balance [ID] [действие] [сумма]")
            return

        target_user_id = int(parts[1])
        action = parts[2].lower()
        amount = float(parts[3])

        if action not in ['add', 'subtract', 'set']:
            await message.answer("❌ Действие должно быть: add, subtract или set")
            return

        if amount < 0:
            await message.answer("❌ Сумма должна быть положительной")
            return

        target_user = get_user(target_user_id)
        if not target_user:
            await message.answer("❌ Пользователь не найден")
            return

        old_balance = get_user_balance(target_user_id)

        if action == 'add':
            add_to_balance(target_user_id, amount)
            new_balance = get_user_balance(target_user_id)
            action_text = "добавлено"
        elif action == 'subtract':
            if old_balance < amount:
                await message.answer("❌ Недостаточно средств на балансе пользователя")
                return
            subtract_from_balance(target_user_id, amount)
            new_balance = get_user_balance(target_user_id)
            action_text = "списано"
        else:  # set
            target_user['balance'] = amount
            save_all_data()
            new_balance = amount
            action_text = "установлено"

        admin_text = f"""
✅ <b>Баланс изменен</b>

👤 <b>Пользователь:</b> {escape_html(target_user.get('first_name', 'Unknown'))}
🆔 <b>ID:</b> {target_user_id}
💰 <b>Было:</b> {old_balance:.2f} TMT
💰 <b>Стало:</b> {new_balance:.2f} TMT
📊 <b>Действие:</b> {action_text} {amount:.2f} TMT
"""

        await message.answer(admin_text, parse_mode="HTML")

        # Notify user about balance change
        user_lang = target_user.get('language', 'ru')
        if action == 'add':
            user_text = f"💰 Ваш баланс пополнен на {amount:.2f} TMT\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💰 Balansyňyz {amount:.2f} TMT-e dolduryldy\nHäzirki balans: {new_balance:.2f} TMT"
        elif action == 'subtract':
            user_text = f"💸 С вашего баланса списано {amount:.2f} TMT\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💸 Balansyňyzdan {amount:.2f} TMT çykaryldy\nHäzirki balans: {new_balance:.2f} TMT"
        else:
            user_text = f"💰 Ваш баланс изменен администратором\nТекущий баланс: {new_balance:.2f} TMT" if user_lang == 'ru' else f"💰 Balansyňyz administrator tarapyndan üýtgedildi\nHäzirki balans: {new_balance:.2f} TMT"

        await send_notification(message.bot, target_user_id, user_text)

    except ValueError:
        await message.answer("❌ Неверный формат ID или суммы")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(Command("find_user"))
async def admin_find_user(message: Message):
    """Admin command to find user by ID"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Используйте: /find_user [ID]")
            return

        target_user_id = int(parts[1])
        target_user = get_user(target_user_id)

        if not target_user:
            await message.answer("❌ Пользователь не найден")
            return

        balance = get_user_balance(target_user_id)
        role_emoji = "👨‍💻" if target_user.get('role') == 'freelancer' else "👤"
        username_text = f"@{target_user.get('username')}" if target_user.get('username') else "нет"

        user_info = f"""
{role_emoji} <b>Информация о пользователе</b>

👤 <b>Имя:</b> {escape_html(target_user.get('first_name', 'Unknown'))}
🆔 <b>ID:</b> <code>{target_user_id}</code>
📱 <b>Username:</b> {username_text}
🔰 <b>Роль:</b> {"Фрилансер" if target_user.get('role') == 'freelancer' else "Заказчик"}
🌐 <b>Язык:</b> {target_user.get('language', 'ru').upper()}
💰 <b>Баланс:</b> {balance:.2f} TMT
📅 <b>Регистрация:</b> {datetime.fromisoformat(target_user['created_at']).strftime('%d.%m.%Y %H:%M')}

📊 <b>Профиль:</b>
• <b>Навыки:</b> {escape_html(target_user.get('profile', {}).get('skills', 'Не указаны'))}
• <b>Описание:</b> {escape_html(target_user.get('profile', {}).get('description', 'Не указано'))}
• <b>Контакт:</b> {escape_html(target_user.get('profile', {}).get('contact', 'Не указан'))}
"""

        await message.answer(user_info, parse_mode="HTML")

    except ValueError:
        await message.answer("❌ Неверный формат ID")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")



@router.callback_query(F.data == "admin_show_withdrawals")
async def admin_show_withdrawals_callback(callback: CallbackQuery):
    """Show withdrawal requests via callback"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа")
        return

    pending_withdrawals = get_pending_withdrawals()

    if not pending_withdrawals:
        await callback.message.edit_text("📭 Нет заявок на вывод")
        return

    text = "💸 <b>Заявки на вывод</b>\n\n"

    for withdrawal in pending_withdrawals[:5]:  # Show first 5
        withdrawal_user = get_user(withdrawal['user_id'])
        user_name = withdrawal_user.get('first_name', 'Unknown') if withdrawal_user else 'Unknown'

        text += f"🔹 <b>ID:</b> {withdrawal['id']}\n"
        text += f"👤 <b>Пользователь:</b> {user_name} ({withdrawal['user_id']})\n"
        text += f"💰 <b>Сумма:</b> {format_price(withdrawal['amount'])} TMT\n"
        text += f"📞 <b>Телефон:</b> {withdrawal['phone']}\n"
        text += f"📅 <b>Дата:</b> {datetime.fromisoformat(withdrawal['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"

    keyboard = []
    for withdrawal in pending_withdrawals[:3]:  # Show buttons for first 3
        keyboard.append([
            InlineKeyboardButton(
                text=f"✅ #{withdrawal['id']} - {format_price(withdrawal['amount'])} TMT",
                callback_data=f"admin_confirm_withdrawal_{withdrawal['id']}"
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"admin_reject_withdrawal_{withdrawal['id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await callback.answer()

# =============================================================================
# WITHDRAWAL HANDLERS
# =============================================================================

# Balance handler - now works for both freelancers and clients
@router.message(F.text.in_(["💰 Баланс", "💰 Balans"]))
async def show_balance(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')
    role = user.get('role')

    if role == 'client':
        # For clients show balance with frozen amount
        balance = get_user_balance(user['id'])
        frozen = get_user_frozen_balance(user['id'])
        total = balance + frozen

        balance_text = get_text("balance_info_client", lang).format(
            balance=format_price(balance),
            frozen=format_price(frozen),
            total=format_price(total)
        )
        
        # Add withdrawal button for clients too
        await message.answer(balance_text, reply_markup=get_balance_menu_keyboard(lang))
    else:
        # For freelancers show simple balance
        balance = get_user_balance(user['id'])
        balance_text = get_text("balance_info", lang).format(balance=format_price(balance))
        await message.answer(balance_text)

# Withdrawal handler - now works for both freelancers and clients
@router.message(F.text.in_(["💸 Вывод средств", "💸 Çykarmak"]))
async def start_withdrawal(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        return

    lang = user.get('language', 'ru')

    balance = get_user_balance(user['id'])
    if balance <= 0:
        await message.answer(get_text("withdraw_insufficient_funds", lang))
        return

    await message.answer(get_text("withdraw_amount", lang), reply_markup=get_back_keyboard(lang))
    await state.set_state(WithdrawalStates.waiting_amount)

@router.message(WithdrawalStates.waiting_amount)
async def withdrawal_amount_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer(get_text("withdraw_invalid_amount", lang))
            return

        balance = get_user_balance(user['id'])
        if amount > balance:
            await message.answer(get_text("withdraw_insufficient_funds", lang))
            return

        await state.update_data(amount=amount)
        await message.answer(get_text("withdraw_phone", lang), reply_markup=get_back_keyboard(lang))
        await state.set_state(WithdrawalStates.waiting_phone)

    except ValueError:
        await message.answer(get_text("withdraw_invalid_amount", lang))

@router.message(WithdrawalStates.waiting_phone)
async def withdrawal_phone_received(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user.get('language', 'ru')

    phone = message.text.strip()
    data = await state.get_data()
    amount = data['amount']

    commission, final_amount = calculate_withdrawal_commission(amount)

    # Create temporary withdrawal (not saved yet)
    temp_withdrawal = {
        'amount': amount,
        'phone': phone,
        'commission': commission,
        'final_amount': final_amount
    }

    confirm_text = get_text("withdraw_confirm", lang).format(
        amount=format_price(amount),
        phone=phone,
        commission=format_price(commission),
        final_amount=format_price(final_amount)
    )

    await state.update_data(temp_withdrawal=temp_withdrawal)
    await message.answer(
        confirm_text,
        reply_markup=get_withdrawal_confirmation_keyboard(0, lang),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("confirm_withdraw_"))
async def confirm_withdrawal(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    # Get the temp withdrawal data (we need to retrieve it from state)
    data = await state.get_data()
    temp_withdrawal = data.get('temp_withdrawal')

    if not temp_withdrawal:
        await callback.answer("❌ Ошибка: данные не найдены")
        return

    # Create actual withdrawal request
    withdrawal = create_withdrawal_request(
        user['id'],
        temp_withdrawal['amount'],
        temp_withdrawal['phone']
    )

    # Subtract amount from balance
    subtract_from_balance(user['id'], temp_withdrawal['amount'])

    # Notify user
    await callback.message.edit_text(get_text("withdraw_success", lang))

    # Notify admin
    admin_text = get_text("admin_new_withdrawal", lang) + "\n\n"
    username_text = f"@{user.get('username')}" if user.get('username') else "нет username"
    admin_text += get_text("admin_withdrawal_info", lang).format(
        user_name=user.get('first_name', 'Unknown'),
        user_id=user['id'],
        amount=format_price(temp_withdrawal['amount']),
        phone=temp_withdrawal['phone'],
        balance_before=temp_withdrawal['amount'] + get_user_balance(user['id']),
        balance_after=get_user_balance(user['id'])
    )
    admin_text += f"\n📱 <b>Username:</b> {username_text}"

    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=get_admin_withdrawal_keyboard(withdrawal['id'], lang),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    await callback.answer()
    await state.clear()

@router.callback_query(F.data == "cancel_withdraw")
async def cancel_withdrawal(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user.get('language', 'ru')

    await callback.message.edit_text("❌ Вывод отменен" if lang == "ru" else "❌ Çykarmak ýatyryldy")
    await callback.answer()
    await state.clear()

# Admin withdrawal management
@router.message(F.text.in_(["💸 Заявки на вывод", "💸 Çykarmak arzalary"]))
async def show_withdrawal_requests(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    lang = user.get('language', 'ru') if user else 'ru'

    if not is_admin(user_id):
        await message.answer("❌ У вас нет доступа к админ панели")
        return

    pending_withdrawals = get_pending_withdrawals()

    if not pending_withdrawals:
        await message.answer(get_text("no_withdrawal_requests", lang))
        return

    text = f"💸 <b>{'Заявки на вывод' if lang == 'ru' else 'Çykarmak arzalary'}</b>\n\n"

    for withdrawal in pending_withdrawals[:10]:  # Show first 10
        withdrawal_user = get_user(withdrawal['user_id'])
        user_name = withdrawal_user.get('first_name', 'Unknown') if withdrawal_user else 'Unknown'

        text += f"🔹 <b>ID:</b> {withdrawal['id']}\n"
        text += f"👤 <b>{'Пользователь' if lang == 'ru' else 'Ulanyjy'}:</b> {user_name} ({withdrawal['user_id']})\n"
        text += f"💰 <b>{'Сумма' if lang == 'ru' else 'Mukdar'}:</b> {format_price(withdrawal['amount'])} TMT\n"
        text += f"📞 <b>{'Телефон' if lang == 'ru' else 'Telefon'}:</b> {withdrawal['phone']}\n"
        text += f"📅 <b>{'Дата' if lang == 'ru' else 'Sene'}:</b> {datetime.fromisoformat(withdrawal['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for withdrawal in pending_withdrawals[:5]:  # Show buttons for first 5
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"✅ #{withdrawal['id']} - {format_price(withdrawal['amount'])} TMT",
                callback_data=f"admin_confirm_withdrawal_{withdrawal['id']}"
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"admin_reject_withdrawal_{withdrawal['id']}"
            )
        ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_confirm_withdrawal_"))
async def admin_confirm_withdrawal(callback: CallbackQuery):
    withdrawal_id = int(callback.data.split("_")[3])
    withdrawal = get_withdrawal_request(withdrawal_id)

    if not withdrawal:
        await callback.answer("❌ Заявка не найдена")
        return

    if withdrawal['status'] != 'pending':
        await callback.answer("❌ Заявка уже обработана")
        return

    # Update withdrawal status
    update_withdrawal_request(withdrawal_id, {'status': 'completed', 'completed_at': datetime.now().isoformat()})

    # Notify user
    withdrawal_user = get_user(withdrawal['user_id'])
    if withdrawal_user:
        lang = withdrawal_user.get('language', 'ru')
        try:
            await callback.bot.send_message(
                withdrawal['user_id'],
                get_text("withdrawal_confirmed", lang),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify user {withdrawal['user_id']}: {e}")

    await callback.message.edit_text(f"✅ Вывод #{withdrawal_id} подтвержден")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_reject_withdrawal_"))
async def admin_reject_withdrawal(callback: CallbackQuery):
    withdrawal_id = int(callback.data.split("_")[3])
    withdrawal = get_withdrawal_request(withdrawal_id)

    if not withdrawal:
        await callback.answer("❌ Заявка не найдена")
        return

    if withdrawal['status'] != 'pending':
        await callback.answer("❌ Заявка уже обработана")
        return

    # Update withdrawal status
    update_withdrawal_request(withdrawal_id, {'status': 'rejected', 'rejected_at': datetime.now().isoformat()})

    # Return money to user balance
    add_to_balance(withdrawal['user_id'], withdrawal['amount'])

    # Notify user
    withdrawal_user = get_user(withdrawal['user_id'])
    if withdrawal_user:
        lang = withdrawal_user.get('language', 'ru')
        try:
            await callback.bot.send_message(
                withdrawal['user_id'],
                get_text("withdrawal_rejected", lang),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify user {withdrawal['user_id']}: {e}")

    await callback.message.edit_text(f"❌ Вывод #{withdrawal_id} отклонен")
    await callback.answer()

# =============================================================================
# MAIN FUNCTION
# =============================================================================
async def main():
    """Main function to run the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        return

    # Initialize database
    init_database()

    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Add middleware
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Include router
    dp.include_router(router)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info("Bot starting...")

    # Start keep alive server
    keep_alive()

    # Start polling
    try:
        logger.info("Starting bot polling...")
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())