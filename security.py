import os
import logging
import hashlib
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Rate limiting storage (in-memory for serverless)
rate_limits = {}
blocked_users = {}

# Security configuration
MAX_REQUESTS_PER_MINUTE = 20
MAX_REQUESTS_PER_HOUR = 100
BLOCK_DURATION = 3600  # 1 hour in seconds

def check_rate_limit(user_id: int) -> bool:
    """Check if user is within rate limits"""
    current_time = time.time()
    
    # Clean old entries
    cleanup_rate_limits(current_time)
    
    # Check if user is blocked
    if user_id in blocked_users:
        if current_time < blocked_users[user_id]:
            return False
        else:
            del blocked_users[user_id]
    
    # Initialize user rate limit if not exists
    if user_id not in rate_limits:
        rate_limits[user_id] = {'minute': [], 'hour': []}
    
    user_limits = rate_limits[user_id]
    
    # Add current request
    user_limits['minute'].append(current_time)
    user_limits['hour'].append(current_time)
    
    # Clean old requests
    user_limits['minute'] = [t for t in user_limits['minute'] if current_time - t < 60]
    user_limits['hour'] = [t for t in user_limits['hour'] if current_time - t < 3600]
    
    # Check limits
    if len(user_limits['minute']) > MAX_REQUESTS_PER_MINUTE:
        block_user(user_id, current_time)
        return False
    
    if len(user_limits['hour']) > MAX_REQUESTS_PER_HOUR:
        block_user(user_id, current_time)
        return False
    
    return True

def block_user(user_id: int, current_time: float):
    """Block user for specified duration"""
    blocked_users[user_id] = current_time + BLOCK_DURATION
    logger.warning(f"User {user_id} blocked for rate limiting")

def cleanup_rate_limits(current_time: float):
    """Clean up old rate limit entries"""
    users_to_remove = []
    for user_id, limits in rate_limits.items():
        limits['minute'] = [t for t in limits['minute'] if current_time - t < 60]
        limits['hour'] = [t for t in limits['hour'] if current_time - t < 3600]
        
        if not limits['minute'] and not limits['hour']:
            users_to_remove.append(user_id)
    
    for user_id in users_to_remove:
        del rate_limits[user_id]

def validate_webhook_request(token: str, signature: str = None) -> bool:
    """Validate webhook request authenticity"""
    if not token:
        return False
    
    # Check if token matches bot token
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        return False
    
    return token == bot_token

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input"""
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    text = text.strip()
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    return text

def is_spam_message(text: str) -> bool:
    """Check if message appears to be spam"""
    if not text:
        return False
    
    spam_indicators = [
        'http://', 'https://', 'www.',  # URLs
        '@everyone', '@here',  # Mass mentions
        'FREE', 'WIN', 'WINNER',  # Common spam words
        '🎉🎉🎉', '💰💰💰',  # Excessive emojis
    ]
    
    text_upper = text.upper()
    spam_count = sum(1 for indicator in spam_indicators if indicator.upper() in text_upper)
    
    # Consider spam if multiple indicators or excessive length
    return spam_count >= 2 or len(text) > 2000

def log_security_event(event_type: str, user_id: int, details: str = ""):
    """Log security-related events"""
    logger.warning(f"Security event: {event_type} - User: {user_id} - Details: {details}")