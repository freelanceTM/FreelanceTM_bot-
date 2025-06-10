import os
import json
import logging
from flask import Flask, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import telebot
# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "fallback_secret_key_for_webhook")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Import bot after app creation to avoid circular imports
from bot import bot
from handlers import setup_handlers

# Setup bot handlers only if bot is initialized
if bot:
    setup_handlers(bot)
    logger.info("Bot handlers setup completed")
else:
    logger.warning("Bot not initialized - handlers not setup")

@app.route('/', methods=['GET'])
def index():
    """Health check endpoint"""
    return jsonify({
        "status": "FreelanceTM Bot webhook server is running",
        "bot_info": "Webhook endpoint ready for Telegram updates"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook updates from Telegram"""
    if not bot:
        logger.warning("Bot not initialized - webhook request ignored")
        return jsonify({"error": "Bot not configured"}), 503
    
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            if update:
                bot.process_new_updates([update])
            return jsonify({"status": "ok"})
        else:
            logger.warning("Invalid content type for webhook")
            return jsonify({"error": "Invalid content type"}), 400
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/set_webhook', methods=['POST'])
def set_webhook():
    """Set webhook URL for the bot"""
    if not bot:
        return jsonify({"error": "Bot not configured"}), 503
    
    try:
        webhook_url = request.json.get('webhook_url') if request.json else None
        if not webhook_url:
            return jsonify({"error": "webhook_url is required"}), 400
        
        result = bot.set_webhook(url=webhook_url)
        if result:
            logger.info(f"Webhook set successfully to: {webhook_url}")
            return jsonify({"status": "Webhook set successfully", "url": webhook_url})
        else:
            logger.error("Failed to set webhook")
            return jsonify({"error": "Failed to set webhook"}), 500
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/remove_webhook', methods=['POST'])
def remove_webhook():
    """Remove webhook and switch back to polling (for development)"""
    if not bot:
        return jsonify({"error": "Bot not configured"}), 503
    
    try:
        result = bot.remove_webhook()
        if result:
            logger.info("Webhook removed successfully")
            return jsonify({"status": "Webhook removed successfully"})
        else:
            logger.error("Failed to remove webhook")
            return jsonify({"error": "Failed to remove webhook"}), 500
    except Exception as e:
        logger.error(f"Error removing webhook: {e}")
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
        logger.error(f"Error getting bot info: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # This will only run in development, not on Vercel
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
