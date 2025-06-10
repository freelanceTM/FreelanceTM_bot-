from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from utils import get_text
from texts import CATEGORIES
from bot import is_admin

def get_language_keyboard():
    """Get language selection keyboard"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇹🇲 Türkmen", callback_data="lang_tm")
    )
    return keyboard

def get_role_keyboard(lang="ru"):
    """Get role selection keyboard"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    if lang == "ru":
        keyboard.add(
            InlineKeyboardButton("👨‍💻 Фрилансер", callback_data="role_freelancer"),
            InlineKeyboardButton("🏢 Заказчик", callback_data="role_client")
        )
    else:
        keyboard.add(
            InlineKeyboardButton("👨‍💻 Frilanser", callback_data="role_freelancer"),
            InlineKeyboardButton("🏢 Müşderi", callback_data="role_client")
        )
    return keyboard

def get_main_menu_keyboard(role, lang="ru", user_id=None):
    """Get main menu keyboard based on role"""
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    if role == "freelancer":
        keyboard.add(
            KeyboardButton(get_text("btn_view_orders", lang)),
            KeyboardButton(get_text("btn_my_responses", lang))
        )
    else:  # client
        keyboard.add(
            KeyboardButton(get_text("btn_create_order", lang)),
            KeyboardButton(get_text("btn_my_orders", lang))
        )
    
    keyboard.add(
        KeyboardButton(get_text("btn_profile", lang)),
        KeyboardButton(get_text("btn_reviews", lang))
    )
    
    keyboard.add(KeyboardButton(get_text("btn_help", lang)))
    
    if user_id and is_admin(user_id):
        keyboard.add(KeyboardButton("👨‍💼 Админ панель"))
    
    return keyboard

def get_subscription_keyboard():
    """Get subscription check keyboard"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription"))
    return keyboard

def get_categories_keyboard(lang="ru"):
    """Get categories keyboard"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    categories = CATEGORIES.get(lang, CATEGORIES["ru"])
    
    buttons = []
    for key, value in categories.items():
        buttons.append(InlineKeyboardButton(value, callback_data=f"category_{key}"))
    
    # Add buttons in pairs
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.add(buttons[i], buttons[i + 1])
        else:
            keyboard.add(buttons[i])
    
    return keyboard

def get_order_response_keyboard(order_id, lang="ru"):
    """Get order response keyboard"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(get_text("respond_to_order", lang), callback_data=f"respond_{order_id}"))
    return keyboard

def get_back_keyboard(lang="ru"):
    """Get back keyboard"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(get_text("btn_back", lang)))
    return keyboard
