import logging
from datetime import datetime
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import bot, check_subscription, is_admin
from database import (
    get_user, create_user, update_user, get_order, create_order, update_order,
    get_active_orders_for_freelancer, add_response, get_responses, get_stats,
    add_review
)
from utils import get_text, get_user_language, format_order_text, format_profile_text
from keyboards import (
    get_language_keyboard, get_role_keyboard, get_main_menu_keyboard,
    get_subscription_keyboard, get_categories_keyboard, get_order_response_keyboard,
    get_back_keyboard
)
from texts import REQUIRED_CHANNEL

logger = logging.getLogger(__name__)

# User states for registration and operations
user_states = {}

def setup_handlers(bot_instance):
    """Setup all bot handlers"""
    global bot
    bot = bot_instance
    
    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if user:
            # User already registered, show main menu
            lang = user.get('language', 'ru')
            role = user.get('role')
            bot.send_message(
                message.chat.id,
                get_text("main_menu_freelancer" if role == "freelancer" else "main_menu_client", lang),
                reply_markup=get_main_menu_keyboard(role, lang, user_id),
                parse_mode='HTML'
            )
            return
        
        # Check subscription
        if not check_subscription(user_id):
            bot.send_message(
                message.chat.id,
                f"{get_text('welcome', 'ru')}\n\n{REQUIRED_CHANNEL}",
                reply_markup=get_subscription_keyboard(),
                parse_mode='HTML'
            )
            return
        
        # Start registration
        bot.send_message(
            message.chat.id,
            get_text("choose_language", "ru"),
            reply_markup=get_language_keyboard(),
            parse_mode='HTML'
        )

    @bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
    def check_subscription_callback(call):
        user_id = call.from_user.id
        
        if check_subscription(user_id):
            bot.edit_message_text(
                get_text("choose_language", "ru"),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_language_keyboard(),
                parse_mode='HTML'
            )
        else:
            bot.answer_callback_query(call.id, get_text("subscription_required", "ru"))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
    def language_selected(call):
        user_id = call.from_user.id
        lang = call.data.split("_")[1]
        
        # Save language choice temporarily
        user_states[user_id] = {"step": "role", "language": lang}
        
        bot.edit_message_text(
            get_text("choose_role", lang),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_role_keyboard(lang),
            parse_mode='HTML'
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("role_"))
    def role_selected(call):
        user_id = call.from_user.id
        role = call.data.split("_")[1]
        
        if user_id not in user_states:
            return
        
        lang = user_states[user_id]["language"]
        user_states[user_id] = {"step": "name", "language": lang, "role": role}
        
        bot.edit_message_text(
            get_text("registration_name", lang),
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "name")
    def profile_name_received(message):
        user_id = message.from_user.id
        lang = user_states[user_id]["language"]
        
        user_states[user_id]["name"] = message.text
        user_states[user_id]["step"] = "skills"
        
        bot.send_message(
            message.chat.id,
            get_text("registration_skills", lang),
            reply_markup=get_back_keyboard(lang),
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "skills")
    def profile_skills_received(message):
        user_id = message.from_user.id
        lang = user_states[user_id]["language"]
        
        user_states[user_id]["skills"] = message.text
        user_states[user_id]["step"] = "description"
        
        bot.send_message(
            message.chat.id,
            get_text("registration_description", lang),
            reply_markup=get_back_keyboard(lang),
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "description")
    def profile_description_received(message):
        user_id = message.from_user.id
        lang = user_states[user_id]["language"]
        
        user_states[user_id]["description"] = message.text
        user_states[user_id]["step"] = "contact"
        
        bot.send_message(
            message.chat.id,
            get_text("registration_contact", lang),
            reply_markup=get_back_keyboard(lang),
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "contact")
    def profile_contact_received(message):
        user_id = message.from_user.id
        state = user_states[user_id]
        lang = state["language"]
        
        # Create user
        user_data = {
            'first_name': message.from_user.first_name or '',
            'username': message.from_user.username or '',
            'language': lang,
            'role': state["role"],
            'profile': {
                'name': state["name"],
                'skills': state["skills"],
                'description': state["description"],
                'contact': message.text
            }
        }
        
        create_user(user_id, user_data)
        
        # Clear state
        del user_states[user_id]
        
        bot.send_message(
            message.chat.id,
            get_text("registration_complete", lang),
            reply_markup=get_main_menu_keyboard(state["role"], lang, user_id),
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda message: message.text in [get_text("btn_view_orders", "ru"), get_text("btn_view_orders", "tm")])
    def view_orders(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            cmd_start(message)
            return
        
        lang = user.get('language', 'ru')
        role = user.get('role')
        
        if role != 'freelancer':
            bot.send_message(message.chat.id, get_text("error_not_freelancer", lang), parse_mode='HTML')
            return
        
        orders = get_active_orders_for_freelancer(user_id)
        
        if not orders:
            bot.send_message(message.chat.id, get_text("no_orders", lang), parse_mode='HTML')
            return
        
        bot.send_message(message.chat.id, get_text("orders_list", lang), parse_mode='HTML')
        
        for order in orders[:10]:  # Show first 10 orders
            order_text = format_order_text(order, lang)
            keyboard = get_order_response_keyboard(order['id'], lang)
            
            bot.send_message(
                message.chat.id,
                order_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )

    @bot.message_handler(func=lambda message: message.text in [get_text("btn_create_order", "ru"), get_text("btn_create_order", "tm")])
    def create_order_start(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            cmd_start(message)
            return
        
        lang = user.get('language', 'ru')
        role = user.get('role')
        
        if role != 'client':
            bot.send_message(message.chat.id, get_text("error_not_client", lang), parse_mode='HTML')
            return
        
        user_states[user_id] = {"step": "order_title", "language": lang}
        
        bot.send_message(
            message.chat.id,
            get_text("order_title", lang),
            reply_markup=get_back_keyboard(lang),
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "order_title")
    def order_title_received(message):
        user_id = message.from_user.id
        lang = user_states[user_id]["language"]
        
        user_states[user_id]["title"] = message.text
        user_states[user_id]["step"] = "order_description"
        
        bot.send_message(
            message.chat.id,
            get_text("order_description", lang),
            reply_markup=get_back_keyboard(lang),
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "order_description")
    def order_description_received(message):
        user_id = message.from_user.id
        lang = user_states[user_id]["language"]
        
        user_states[user_id]["description"] = message.text
        user_states[user_id]["step"] = "order_category"
        
        bot.send_message(
            message.chat.id,
            "🏷️ Выберите категорию:" if lang == "ru" else "🏷️ Kategoriýany saýlaň:",
            reply_markup=get_categories_keyboard(lang),
            parse_mode='HTML'
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("category_"))
    def category_selected(call):
        user_id = call.from_user.id
        
        if user_id not in user_states:
            return
        
        category = call.data.split("_")[1]
        lang = user_states[user_id]["language"]
        
        user_states[user_id]["category"] = category
        user_states[user_id]["step"] = "order_budget"
        
        bot.edit_message_text(
            get_text("order_budget", lang),
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "order_budget")
    def order_budget_received(message):
        user_id = message.from_user.id
        lang = user_states[user_id]["language"]
        
        try:
            budget = float(message.text.replace(',', '.'))
            if budget <= 0:
                raise ValueError()
            
            user_states[user_id]["budget"] = budget
            user_states[user_id]["step"] = "order_deadline"
            
            bot.send_message(
                message.chat.id,
                get_text("order_deadline", lang),
                reply_markup=get_back_keyboard(lang),
                parse_mode='HTML'
            )
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Введите корректную сумму" if lang == "ru" else "❌ Dogry mukdary giriziň",
                parse_mode='HTML'
            )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "order_deadline")
    def order_deadline_received(message):
        user_id = message.from_user.id
        lang = user_states[user_id]["language"]
        
        try:
            deadline = int(message.text)
            if deadline <= 0:
                raise ValueError()
            
            user_states[user_id]["deadline"] = deadline
            user_states[user_id]["step"] = "order_contact"
            
            bot.send_message(
                message.chat.id,
                get_text("order_contact", lang),
                reply_markup=get_back_keyboard(lang),
                parse_mode='HTML'
            )
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Введите количество дней числом" if lang == "ru" else "❌ Günleriň sanyny giriziň",
                parse_mode='HTML'
            )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "order_contact")
    def order_contact_received(message):
        user_id = message.from_user.id
        state = user_states[user_id]
        lang = state["language"]
        user = get_user(user_id)
        
        # Create order
        order_data = {
            'client_id': user_id,
            'title': state["title"],
            'description': state["description"],
            'category': state["category"],
            'budget': state["budget"],
            'deadline': state["deadline"],
            'contact': message.text
        }
        
        order = create_order(order_data)
        
        # Clear state
        del user_states[user_id]
        
        if user and user.get('role'):
            bot.send_message(
                message.chat.id,
                get_text("order_created", lang),
                reply_markup=get_main_menu_keyboard(user['role'], lang, user_id),
                parse_mode='HTML'
            )
        else:
            bot.send_message(message.chat.id, get_text("order_created", lang), parse_mode='HTML')

    @bot.callback_query_handler(func=lambda call: call.data.startswith("respond_"))
    def respond_to_order(call):
        user_id = call.from_user.id
        order_id = int(call.data.split("_")[1])
        user = get_user(user_id)
        
        if not user:
            return
        
        lang = user.get('language', 'ru')
        order = get_order(order_id)
        
        if not order:
            bot.answer_callback_query(call.id, get_text("error_order_not_found", lang))
            return
        
        # Add response
        response_data = {
            'freelancer_id': user_id,
            'message': f"Отклик от {user.get('first_name', 'Пользователя')}"
        }
        
        if add_response(order_id, response_data):
            bot.answer_callback_query(call.id, get_text("response_sent", lang))
            
            # Notify client
            try:
                client_user = get_user(order['client_id'])
                if client_user:
                    client_lang = client_user.get('language', 'ru')
                    notification_text = f"📨 Новый отклик на ваш заказ!\n\n{format_order_text(order, client_lang)}" if client_lang == "ru" else f"📨 Täze jogap!\n\n{format_order_text(order, client_lang)}"
                    bot.send_message(order['client_id'], notification_text, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Failed to notify client: {e}")
        else:
            bot.answer_callback_query(call.id, get_text("response_exists", lang))

    @bot.message_handler(func=lambda message: message.text in [get_text("btn_profile", "ru"), get_text("btn_profile", "tm")])
    def show_profile(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            cmd_start(message)
            return
        
        lang = user.get('language', 'ru')
        profile_text = format_profile_text(user, lang)
        
        bot.send_message(message.chat.id, profile_text, parse_mode='HTML')

    @bot.message_handler(func=lambda message: message.text in [get_text("btn_my_orders", "ru"), get_text("btn_my_orders", "tm")])
    def my_orders(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            cmd_start(message)
            return
        
        lang = user.get('language', 'ru')
        role = user.get('role')
        
        if role != 'client':
            bot.send_message(message.chat.id, get_text("error_not_client", lang), parse_mode='HTML')
            return
        
        from database import get_orders_by_client
        orders = get_orders_by_client(user_id)
        
        if not orders:
            bot.send_message(message.chat.id, get_text("no_my_orders", lang), parse_mode='HTML')
            return
        
        bot.send_message(message.chat.id, get_text("my_orders_list", lang), parse_mode='HTML')
        
        for order in orders[:10]:  # Show first 10 orders
            order_text = format_order_text(order, lang)
            responses_count = len(get_responses(order['id']))
            
            if responses_count > 0:
                order_text += f"\n\n📤 {'Откликов' if lang == 'ru' else 'Jogap'}: {responses_count}"
            
            # Add view responses button if there are responses
            keyboard = InlineKeyboardMarkup()
            if responses_count > 0:
                keyboard.add(InlineKeyboardButton(
                    f"👀 {'Посмотреть отклики' if lang == 'ru' else 'Jogaplary görmek'} ({responses_count})",
                    callback_data=f"view_responses_{order['id']}"
                ))
            
            bot.send_message(
                message.chat.id,
                order_text,
                reply_markup=keyboard if responses_count > 0 else None,
                parse_mode='HTML'
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("view_responses_"))
    def view_responses(call):
        user_id = call.from_user.id
        order_id = int(call.data.split("_")[2])
        user = get_user(user_id)
        
        if not user:
            return
        
        lang = user.get('language', 'ru')
        order = get_order(order_id)
        
        if not order or order['client_id'] != user_id:
            bot.answer_callback_query(call.id, get_text("error_not_your_order", lang))
            return
        
        responses = get_responses(order_id)
        
        if not responses:
            bot.answer_callback_query(call.id, "Нет откликов" if lang == 'ru' else "Jogap ýok")
            return
        
        bot.edit_message_text(
            f"📤 {'Отклики на заказ' if lang == 'ru' else 'Sargyta jogaplar'} #{order_id}:",
            call.message.chat.id,
            call.message.message_id
        )
        
        for i, response in enumerate(responses[:5], 1):  # Show first 5 responses
            freelancer = get_user(response['freelancer_id'])
            if freelancer:
                freelancer_info = format_profile_text(freelancer, lang)
                response_text = f"📤 {'Отклик' if lang == 'ru' else 'Jogap'} #{i}\n\n{freelancer_info}"
                
                # Add contact freelancer button
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(
                    f"💬 {'Связаться' if lang == 'ru' else 'Habarlaşmak'}",
                    callback_data=f"contact_{response['freelancer_id']}"
                ))
                
                bot.send_message(
                    call.message.chat.id,
                    response_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )

    @bot.message_handler(func=lambda message: message.text in [get_text("btn_my_responses", "ru"), get_text("btn_my_responses", "tm")])
    def my_responses(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            cmd_start(message)
            return
        
        lang = user.get('language', 'ru')
        role = user.get('role')
        
        if role != 'freelancer':
            bot.send_message(message.chat.id, get_text("error_not_freelancer", lang), parse_mode='HTML')
            return
        
        from database import get_freelancer_responses
        responses = get_freelancer_responses(user_id)
        
        if not responses:
            bot.send_message(message.chat.id, 
                "📭 У вас пока нет откликов" if lang == 'ru' else "📭 Heniz jogapyňyz ýok", 
                parse_mode='HTML')
            return
        
        bot.send_message(message.chat.id, 
            f"📤 {'Ваши отклики' if lang == 'ru' else 'Siziň jogaplaryňyz'}:", 
            parse_mode='HTML')
        
        for response in responses[:10]:  # Show first 10 responses
            if 'order' in response:
                order_text = format_order_text(response['order'], lang)
                status_text = f"\n\n⏰ {'Отклик отправлен' if lang == 'ru' else 'Jogap iberildi'}: {response['created_at'][:10]}"
                
                bot.send_message(
                    message.chat.id,
                    order_text + status_text,
                    parse_mode='HTML'
                )

    @bot.message_handler(func=lambda message: message.text in [get_text("btn_reviews", "ru"), get_text("btn_reviews", "tm")])
    def reviews(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            cmd_start(message)
            return
        
        lang = user.get('language', 'ru')
        
        from database import get_user_reviews, get_user_average_rating
        reviews_list = get_user_reviews(user_id)
        avg_rating = get_user_average_rating(user_id)
        
        if not reviews_list:
            bot.send_message(message.chat.id, get_text("no_reviews", lang), parse_mode='HTML')
            return
        
        reviews_text = f"⭐ {'Ваши отзывы' if lang == 'ru' else 'Siziň synlaryňyz'}\n\n"
        reviews_text += f"📊 {'Средний рейтинг' if lang == 'ru' else 'Ortaça reýting'}: {avg_rating:.1f}/5.0\n"
        reviews_text += f"📝 {'Всего отзывов' if lang == 'ru' else 'Jemi synlar'}: {len(reviews_list)}\n\n"
        
        for i, review in enumerate(reviews_list[:5], 1):  # Show first 5 reviews
            reviewer = get_user(review['reviewer_id'])
            reviewer_name = reviewer.get('first_name', 'Пользователь') if reviewer else 'Пользователь'
            
            reviews_text += f"⭐ {review['rating']}/5 - {reviewer_name}\n"
            if review.get('comment'):
                reviews_text += f"💬 {review['comment']}\n"
            reviews_text += f"📅 {review['created_at'][:10]}\n\n"
        
        bot.send_message(message.chat.id, reviews_text, parse_mode='HTML')

    @bot.callback_query_handler(func=lambda call: call.data.startswith("contact_"))
    def contact_user(call):
        user_id = call.from_user.id
        target_user_id = int(call.data.split("_")[1])
        user = get_user(user_id)
        target_user = get_user(target_user_id)
        
        if not user or not target_user:
            return
        
        lang = user.get('language', 'ru')
        
        # Get contact info from target user's profile
        contact_info = target_user.get('profile', {}).get('contact', '')
        target_name = target_user.get('first_name', 'Пользователь')
        
        if contact_info:
            contact_text = f"📞 {'Контакт пользователя' if lang == 'ru' else 'Ulanyjynyň kontakty'} {target_name}:\n\n{contact_info}"
        else:
            contact_text = f"❌ {'У пользователя не указан контакт' if lang == 'ru' else 'Ulanyjyda kontakt görkezilmedi'}"
        
        bot.answer_callback_query(call.id, "")
        bot.send_message(call.message.chat.id, contact_text, parse_mode='HTML')

    # Add order management functions
    @bot.callback_query_handler(func=lambda call: call.data.startswith("accept_"))
    def accept_freelancer(call):
        user_id = call.from_user.id
        freelancer_id = int(call.data.split("_")[1])
        order_id = int(call.data.split("_")[2]) if len(call.data.split("_")) > 2 else None
        
        user = get_user(user_id)
        if not user:
            return
        
        lang = user.get('language', 'ru')
        
        if not order_id:
            bot.answer_callback_query(call.id, "Ошибка: заказ не найден" if lang == 'ru' else "Ýalňyşlyk: sargyt tapylmady")
            return
        
        order = get_order(order_id)
        if not order or order['client_id'] != user_id:
            bot.answer_callback_query(call.id, get_text("error_not_your_order", lang))
            return
        
        # Update order status and assign freelancer
        update_order(order_id, {
            'status': 'in_progress',
            'freelancer_id': freelancer_id,
            'accepted_at': datetime.now().isoformat()
        })
        
        # Notify freelancer
        freelancer = get_user(freelancer_id)
        if freelancer:
            freelancer_lang = freelancer.get('language', 'ru')
            notification = f"🎉 {'Ваш отклик принят!' if freelancer_lang == 'ru' else 'Siziň jogapyňyz kabul edildi!'}\n\n{format_order_text(order, freelancer_lang)}"
            try:
                bot.send_message(freelancer_id, notification, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Failed to notify freelancer: {e}")
        
        bot.answer_callback_query(call.id, "Фрилансер выбран!" if lang == 'ru' else "Frilanser saýlandy!")
        
        # Update the message
        bot.edit_message_text(
            f"✅ {'Фрилансер выбран для заказа' if lang == 'ru' else 'Sargyt üçin frilanser saýlandy'} #{order_id}",
            call.message.chat.id,
            call.message.message_id
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("complete_order_"))
    def complete_order(call):
        user_id = call.from_user.id
        order_id = int(call.data.split("_")[2])
        user = get_user(user_id)
        
        if not user:
            return
        
        lang = user.get('language', 'ru')
        order = get_order(order_id)
        
        if not order:
            bot.answer_callback_query(call.id, get_text("error_order_not_found", lang))
            return
        
        # Check if user is client or freelancer of this order
        if order['client_id'] != user_id and order.get('freelancer_id') != user_id:
            bot.answer_callback_query(call.id, get_text("error_not_your_order", lang))
            return
        
        # Update order status
        update_order(order_id, {
            'status': 'completed',
            'completed_at': datetime.now().isoformat()
        })
        
        bot.answer_callback_query(call.id, "Заказ завершен!" if lang == 'ru' else "Sargyt tamamlandy!")
        
        # Send completion notification
        completion_text = f"✅ {'Заказ завершен' if lang == 'ru' else 'Sargyt tamamlandy'} #{order_id}\n\n"
        completion_text += f"{'Теперь вы можете оставить отзыв о работе' if lang == 'ru' else 'Indi işe syn galdyryp bilersiňiz'}"
        
        # Create review keyboard
        keyboard = InlineKeyboardMarkup()
        if order['client_id'] == user_id and order.get('freelancer_id'):
            # Client can review freelancer
            keyboard.add(InlineKeyboardButton(
                f"⭐ {'Оставить отзыв фрилансеру' if lang == 'ru' else 'Frilaansera syn galdyrmak'}",
                callback_data=f"review_{order.get('freelancer_id')}_{order_id}"
            ))
        elif order.get('freelancer_id') == user_id:
            # Freelancer can review client
            keyboard.add(InlineKeyboardButton(
                f"⭐ {'Оставить отзыв заказчику' if lang == 'ru' else 'Müşderä syn galdyrmak'}",
                callback_data=f"review_{order['client_id']}_{order_id}"
            ))
        
        bot.send_message(
            call.message.chat.id,
            completion_text,
            reply_markup=keyboard if keyboard.keyboard else None,
            parse_mode='HTML'
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("review_"))
    def start_review(call):
        user_id = call.from_user.id
        parts = call.data.split("_")
        reviewed_user_id = int(parts[1])
        order_id = int(parts[2])
        
        user = get_user(user_id)
        if not user:
            return
        
        lang = user.get('language', 'ru')
        
        # Store review state
        user_states[user_id] = {
            'step': 'review_rating',
            'reviewed_user_id': reviewed_user_id,
            'order_id': order_id,
            'language': lang
        }
        
        # Create rating keyboard
        keyboard = InlineKeyboardMarkup(row_width=5)
        rating_buttons = []
        for i in range(1, 6):
            rating_buttons.append(InlineKeyboardButton(f"{i}⭐", callback_data=f"rating_{i}"))
        keyboard.add(*rating_buttons)
        
        bot.edit_message_text(
            get_text("select_rating", lang),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rating_"))
    def rating_selected(call):
        user_id = call.from_user.id
        rating = int(call.data.split("_")[1])
        
        if user_id not in user_states or user_states[user_id].get('step') != 'review_rating':
            return
        
        user_states[user_id]['rating'] = rating
        user_states[user_id]['step'] = 'review_comment'
        
        lang = user_states[user_id]['language']
        
        bot.edit_message_text(
            f"{get_text('enter_review_text', lang)}\n\n⭐ {rating}/5",
            call.message.chat.id,
            call.message.message_id
        )

    @bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("step") == "review_comment")
    def review_comment_received(message):
        user_id = message.from_user.id
        state = user_states[user_id]
        lang = state['language']
        
        # Add review to database
        review_data = {
            'rating': state['rating'],
            'comment': message.text
        }
        
        success = add_review(
            state['order_id'],
            user_id,
            state['reviewed_user_id'],
            review_data
        )
        
        if success:
            bot.send_message(message.chat.id, get_text("review_added", lang), parse_mode='HTML')
            
            # Notify reviewed user
            reviewed_user = get_user(state['reviewed_user_id'])
            if reviewed_user:
                reviewed_lang = reviewed_user.get('language', 'ru')
                notification = f"⭐ {'Вам оставили новый отзыв!' if reviewed_lang == 'ru' else 'Size täze syn goýuldy!'}\n\n"
                notification += f"⭐ {state['rating']}/5\n💬 {message.text}"
                try:
                    bot.send_message(state['reviewed_user_id'], notification, parse_mode='HTML')
                except Exception as e:
                    logger.error(f"Failed to notify reviewed user: {e}")
        else:
            bot.send_message(message.chat.id, get_text("review_error", lang), parse_mode='HTML')
        
        # Clear state
        del user_states[user_id]
        
        # Return to main menu
        user = get_user(user_id)
        if user:
            role = user.get('role')
            bot.send_message(
                message.chat.id,
                get_text("main_menu_freelancer" if role == "freelancer" else "main_menu_client", lang),
                reply_markup=get_main_menu_keyboard(role, lang, user_id),
                parse_mode='HTML'
            )

    @bot.message_handler(func=lambda message: message.text in [get_text("btn_help", "ru"), get_text("btn_help", "tm")])
    def help_command(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        lang = user.get('language', 'ru') if user else 'ru'
        
        help_text = """
❓ <b>Справка по FreelanceTM Bot</b>

🔍 <b>Основные функции:</b>
• Регистрация как фрилансер или заказчик
• Создание и поиск заказов
• Система откликов на заказы
• Гарантийная система оплаты
• Отзывы и рейтинги

📋 <b>Для заказчиков:</b>
• Создавайте заказы с подробным описанием
• Выбирайте лучших фрилансеров из откликов
• Используйте гарантийную оплату для безопасности

👨‍💻 <b>Для фрилансеров:</b>
• Откликайтесь на интересные заказы
• Получайте оплату через гарантийную систему
• Набирайте рейтинг через отзывы клиентов

🆘 <b>Поддержка:</b>
По всем вопросам обращайтесь к администратору бота
""" if lang == "ru" else """
❓ <b>FreelanceTM Bot barada maglumat</b>

🔍 <b>Esasy funksiýalar:</b>
• Frilanser ýa-da müşderi hökmünde hasaba alyş
• Sargyt döretmek we gözlemek
• Sargytlara jogap bermek ulgamy
• Kepilli töleg ulgamy
• Synlar we reýtingler

📋 <b>Müşderiler üçin:</b>
• Jikme-jik beýany bilen sargyt dörediň
• Jogaplardan iň gowy frilanser saýlaň
• Howpsuzlyk üçin kepilli töleg ulanyň

👨‍💻 <b>Frilanserler üçin:</b>
• Gyzykly sargytlara jogap beriň
• Kepilli ulgam arkaly töleg alyň
• Müşderileriň synlary arkaly reýting ýygnaň

🆘 <b>Goldaw:</b>
Ähli soraglar boýunça administrator bilen habarlaşyň
"""
        
        bot.send_message(message.chat.id, help_text, parse_mode='HTML')

    @bot.message_handler(func=lambda message: message.text == "👨‍💼 Админ панель")
    def admin_panel(message):
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            return
        
        stats = get_stats()
        
        admin_text = f"""
👨‍💼 <b>Административная панель</b>

📊 <b>Статистика платформы:</b>
👥 Всего пользователей: {stats['total_users']}
👨‍💻 Фрилансеров: {stats['freelancers']}
🏢 Заказчиков: {stats['clients']}
📋 Всего заказов: {stats['total_orders']}
🟢 Активных заказов: {stats['active_orders']}
✅ Завершенных заказов: {stats['completed_orders']}
⭐ Всего отзывов: {stats['total_reviews']}
"""
        
        bot.send_message(message.chat.id, admin_text, parse_mode='HTML')

    @bot.message_handler(func=lambda message: message.text in [get_text("btn_back", "ru"), get_text("btn_back", "tm")])
    def back_button(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if user_id in user_states:
            del user_states[user_id]
        
        if user:
            lang = user.get('language', 'ru')
            role = user.get('role')
            bot.send_message(
                message.chat.id,
                get_text("main_menu_freelancer" if role == "freelancer" else "main_menu_client", lang),
                reply_markup=get_main_menu_keyboard(role, lang, user_id),
                parse_mode='HTML'
            )
        else:
            cmd_start(message)

    @bot.message_handler(func=lambda message: True)
    def unknown_message(message):
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            cmd_start(message)
            return
        
        lang = user.get('language', 'ru')
        role = user.get('role')
        
        bot.send_message(
            message.chat.id,
            f"❓ {'Неизвестная команда. Используйте меню.' if lang == 'ru' else 'Näbelli buýruk. Menýu ulanyň.'}",
            reply_markup=get_main_menu_keyboard(role, lang, user_id),
            parse_mode='HTML'
        )
