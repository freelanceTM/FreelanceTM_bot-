import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Global in-memory database variables (for serverless compatibility)
users_db = {}
orders_db = {}
responses_db = {}
reviews_db = {}
counters = {"user_id": 1, "order_id": 1}

# Check if we're in serverless environment
IS_SERVERLESS = os.environ.get('VERCEL') or os.environ.get('LAMBDA_TASK_ROOT')

def init_database():
    """Initialize database"""
    global users_db, orders_db, responses_db, reviews_db, counters
    
    if IS_SERVERLESS:
        # In serverless environment, use in-memory storage
        logger.info("Serverless environment detected - using in-memory storage")
        users_db = {}
        orders_db = {}
        responses_db = {}
        reviews_db = {}
        counters = {"user_id": 1, "order_id": 1}
    else:
        # Local development - try to load from files
        try:
            from pathlib import Path
            DATA_DIR = "data"
            Path(DATA_DIR).mkdir(exist_ok=True)
            
            users_db = load_json(f"{DATA_DIR}/users.json", {})
            orders_db = load_json(f"{DATA_DIR}/orders.json", {})
            responses_db = load_json(f"{DATA_DIR}/responses.json", {})
            reviews_db = load_json(f"{DATA_DIR}/reviews.json", {})
            counters = load_json(f"{DATA_DIR}/counters.json", {"user_id": 1, "order_id": 1})
        except Exception as e:
            logger.warning(f"Failed to load from files, using in-memory storage: {e}")
            users_db = {}
            orders_db = {}
            responses_db = {}
            reviews_db = {}
            counters = {"user_id": 1, "order_id": 1}
    
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
    if IS_SERVERLESS:
        # In serverless environment, we can't persist to files
        logger.debug("Serverless environment - data not persisted to files")
        return
    
    try:
        DATA_DIR = "data"
        save_json(f"{DATA_DIR}/users.json", users_db)
        save_json(f"{DATA_DIR}/orders.json", orders_db)
        save_json(f"{DATA_DIR}/responses.json", responses_db)
        save_json(f"{DATA_DIR}/reviews.json", reviews_db)
        save_json(f"{DATA_DIR}/counters.json", counters)
    except Exception as e:
        logger.warning(f"Failed to save data to files: {e}")

# User operations
def get_user(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    return users_db.get(str(user_id))

def create_user(user_id: int, user_data: Dict) -> Dict:
    """Create new user"""
    user_data['id'] = user_id
    user_data['created_at'] = datetime.now().isoformat()
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
