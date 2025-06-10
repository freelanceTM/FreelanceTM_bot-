import os
import logging
from flask import Flask, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import telebot

# Configure logging for Vercel
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "fallback_secret_key_for_webhook")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@FreelanceTM_channel")

# Convert URL format to username format if needed
if REQUIRED_CHANNEL.startswith("https://t.me/"):
    REQUIRED_CHANNEL = "@" + REQUIRED_CHANNEL.replace("https://t.me/", "")

# Initialize bot
bot = None
if BOT_TOKEN:
    try:
        bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
        logger.info("Bot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
else:
    logger.warning("BOT_TOKEN not provided - bot functionality will be limited")

# Import and setup handlers only if bot is available
if bot:
    try:
        from handlers import setup_handlers
        setup_handlers(bot)
        logger.info("Bot handlers setup completed")
    except Exception as e:
        logger.error(f"Failed to setup handlers: {e}")

# Initialize database
try:
    from database import init_database
    init_database()
    logger.info("Database initialized")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")

@app.route('/', methods=['GET'])
def index():
    """Health check endpoint"""
    return jsonify({
        "status": "FreelanceTM Bot webhook server is running",
        "bot_configured": bot is not None,
        "webhook_ready": True
    })

@app.route('/webhook', methods=['POST'])  
def webhook():
    """Handle incoming webhook updates from Telegram"""
    if not bot:
        return jsonify({"error": "Bot not configured"}), 503
    
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            if update:
                bot.process_new_updates([update])
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Invalid content type"}), 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/<token>', methods=['POST'])
def webhook_with_token(token):
    """Handle webhook with token in URL (Telegram format)"""
    if not bot or not BOT_TOKEN or token != BOT_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            if update:
                bot.process_new_updates([update])
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Invalid content type"}), 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/set_webhook', methods=['POST'])
def set_webhook():
    """Set webhook URL for the bot"""
    if not bot:
        return jsonify({"error": "Bot not configured"}), 503
    
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url') if data else None
        if not webhook_url:
            return jsonify({"error": "webhook_url is required"}), 400
        
        result = bot.set_webhook(url=webhook_url)
        if result:
            logger.info(f"Webhook set to: {webhook_url}")
            return jsonify({"status": "Webhook set successfully", "url": webhook_url})
        else:
            return jsonify({"error": "Failed to set webhook"}), 500
    except Exception as e:
        logger.error(f"Set webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/bot_info', methods=['GET'])
def bot_info():
    """Get bot information"""
    if not bot:
        return jsonify({
            "status": "Bot not configured",
            "bot_token_required": True,
            "webhook_url": None,
            "has_webhook": False
        })
    
    try:
        info = bot.get_me()
        webhook_info = bot.get_webhook_info()
        return jsonify({
            "bot_id": info.id,
            "bot_username": info.username,
            "bot_name": info.first_name,
            "webhook_url": webhook_info.url,
            "has_webhook": bool(webhook_info.url),
            "pending_update_count": webhook_info.pending_update_count
        })
    except Exception as e:
        logger.error(f"Bot info error: {e}")
        return jsonify({"error": str(e)}), 500
