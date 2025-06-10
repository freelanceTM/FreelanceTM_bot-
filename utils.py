import logging
from datetime import datetime
from texts import TEXTS, CATEGORIES

logger = logging.getLogger(__name__)

def get_text(key: str, lang: str = "ru") -> str:
    """Get text in specified language"""
    return TEXTS.get(lang, TEXTS["ru"]).get(key, f"[{key}]")

def get_user_language(user_id: int) -> str:
    """Get user language"""
    from database import get_user
    user = get_user(user_id)
    return user.get('language', 'ru') if user else 'ru'

def escape_html(text: str) -> str:
    """Escape HTML characters"""
    if not text:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length"""
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
    from database import get_user_average_rating, get_user_reviews
    
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
