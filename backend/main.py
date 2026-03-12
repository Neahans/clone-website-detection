import os
from flask import Flask, request, jsonify, session, send_from_directory
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import pickle
import traceback
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend'), 
            template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend'))

# Configure CORS to allow requests from Chrome extension
CORS(app, supports_credentials=True, origins=[
    "chrome-extension://*",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "https://replica-453220.el.r.appspot.com"
])

# Add CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Better to use environment variable
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/url_checker')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-jwt-secret-key')  # JWT secret key

mongo = PyMongo(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# Load models
model_path = 'model/xgboost_model.pkl'
vectorizer_path = 'model/vectorizer.pkl'

try:
    if os.path.exists(model_path) and os.path.exists(vectorizer_path):
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        with open(vectorizer_path, 'rb') as f:
            vectorizer = pickle.load(f)
        logger.info("Models loaded successfully")
    else:
        model, vectorizer = None, None
        logger.warning("Models not found at paths: %s, %s", model_path, vectorizer_path)
except Exception as e:
    logger.error("Error loading models: %s", str(e))
    model, vectorizer = None, None

# Known phishing URLs mapping to legitimate sites
url_mapping = {
    
}

@app.route('/')
def first_page():
    return send_from_directory(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend'), 'index.html')

@app.route('/<path:filename>')
def serve_frontend(filename):
    if filename != 'index.html':
        return send_from_directory(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend'), filename)
    else:
        return first_page()

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not all([username, email, password]):
            return jsonify({'error': 'Missing required fields'}), 400

        if mongo.db.users.find_one({'email': email}):
            return jsonify({'error': 'Email already exists'}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        mongo.db.users.insert_one({
            'username': username, 
            'email': email, 
            'password': hashed_password,
            'enable': True  # Default to enabled
        })
        logger.info(f"New user registered: {email}")
        return jsonify({'message': 'User registered successfully'})
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        email = data.get('email')
        password = data.get('password')
        
        if not all([email, password]):
            return jsonify({'error': 'Missing email or password'}), 400

        user = mongo.db.users.find_one({'email': email})
        if user and bcrypt.check_password_hash(user['password'], password):
            session['user'] = {'username': user['username'], 'email': user['email']}
            logger.info(f"User logged in: {email}")
            return jsonify({
                'message': 'Login successful', 
                'user': {
                    'username': user['username'],
                    'email': user['email'],
                    'enable': user.get('enable', False)
                }
            })
        else:
            return jsonify({'error': 'Invalid email or password'}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/token', methods=['POST'])
def get_token():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        email = data.get('email')
        password = data.get('password')
        
        if not all([email, password]):
            return jsonify({'error': 'Missing email or password'}), 400

        user = mongo.db.users.find_one({'email': email})
        if user and bcrypt.check_password_hash(user['password'], password):
            # Create token instead of session
            access_token = create_access_token(identity=email)
            logger.info(f"Token generated for user: {email}")
            return jsonify({
                'message': 'Login successful', 
                'token': access_token,
                'user': {
                    'username': user['username'],
                    'email': user['email'],
                    'enable': user.get('enable', False)
                }
            })
        else:
            return jsonify({'error': 'Invalid email or password'}), 401
    except Exception as e:
        logger.error(f"Token generation error: {str(e)}")
        return jsonify({'error': 'Authentication failed'}), 500

@app.route('/user', methods=['GET'])
def get_user():
    try:
        # First try to get user from session
        if 'user' in session:
            user = mongo.db.users.find_one({'email': session['user']['email']})
            if user:
                return jsonify({
                    'user': {
                        'username': user['username'],
                        'email': user['email'],
                        'enable': user.get('enable', False)
                    }
                })
        
        # If no session, try JWT token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                # Verify and decode the token
                from flask_jwt_extended import decode_token
                decoded = decode_token(token)
                current_user = decoded['sub']  # 'sub' is where the identity is stored
                
                user = mongo.db.users.find_one({'email': current_user})
                if user:
                    return jsonify({
                        'user': {
                            'username': user['username'],
                            'email': user['email'],
                            'enable': user.get('enable', False)
                        }
                    })
            except Exception as e:
                logger.error(f"JWT token error: {str(e)}")
                return jsonify({'error': 'Invalid token'}), 401
                
        return jsonify({'user': None})
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        return jsonify({'error': 'Failed to get user info'}), 500

@app.route('/enable', methods=['POST'])
def enable_option():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        email = data.get('email')
        enable_status = data.get('enable')
        
        if email is None or enable_status is None:
            return jsonify({'error': 'Missing email or enable status'}), 400

        result = mongo.db.users.update_one(
            {'email': email}, 
            {'$set': {'enable': enable_status}}
        )
        
        if result.matched_count == 0:
            return jsonify({'error': 'User not found'}), 404
            
        logger.info(f"Enable option updated for {email}: {enable_status}")
        return jsonify({'message': 'Enable option updated'})
    except Exception as e:
        logger.error(f"Error updating enable option: {str(e)}")
        return jsonify({'error': 'Failed to update enable option'}), 500

@app.route('/check_url', methods=['GET'])
def check_url():
    try:
        url = request.args.get('url', '')
        
        if not url:
            return jsonify({'error': 'URL parameter is required'}), 400
        
        logger.info(f"Checking URL: {url}")
        
        # Check if URL is in our known mapping (this should happen regardless of login state)
        if url in url_mapping:
            # Log to MongoDB
            log_url_check(url, 'fake', None)
            
            return jsonify({
                'status': 'fake',
                'message': f'This appears to be a phishing site mimicking a legitimate website. Redirecting you to the real site.',
                'redirect': url_mapping[url]
            })
        
        # Get user authentication info - only for logging/analytics purposes, not to determine whether to check
        user_email = None
        if 'user' in session:
            user_email = session['user']['email']
        
        if not user_email:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    from flask_jwt_extended import decode_token
                    decoded = decode_token(token)
                    user_email = decoded['sub']
                except Exception as e:
                    logger.error(f"JWT token error in check_url: {str(e)}")
        
        # Log to MongoDB
        status = 'legitimate'  # Default status
        log_url_check(url, status, user_email)
        
        # Use ML model for additional checking (if available)
        # For now, just return a default response that the site is legitimate
        return jsonify({
            'status': status,
            'message': 'This website appears to be legitimate.',
            'url': url
        })
        
    except Exception as e:
        logger.error(f"Error in check_url: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def log_url_check(url, status, user_email):
    """Log URL check to MongoDB history collection"""
    try:
        mongo.db.history.insert_one({
            'url': url,
            'status': status,
            'safe': status == 'legitimate',
            'user_email': user_email,
            'timestamp': datetime.utcnow()
        })
        logger.info(f"URL check logged to MongoDB: {url}, status: {status}, user: {user_email}")
    except Exception as e:
        logger.error(f"Error logging URL check to MongoDB: {str(e)}")

@app.route('/history', methods=['GET'])
def get_history():
    try:
        # Get user email from either session or JWT
        user_email = None
        
        if 'user' in session:
            user_email = session['user']['email']
        else:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    from flask_jwt_extended import decode_token
                    decoded = decode_token(token)
                    user_email = decoded['sub']
                except Exception as e:
                    logger.error(f"JWT token error in get_history: {str(e)}")
                    return jsonify({'error': 'Invalid token'}), 401
        
        # If no user is authenticated, return empty history
        if not user_email:
            return jsonify({'history': []})
        
        # Get history for the user
        history_cursor = mongo.db.history.find(
            {'user_email': user_email},
            {'_id': 0}  # Exclude MongoDB _id field
        ).sort('timestamp', -1)  # Sort by timestamp descending (newest first)
        
        # Convert cursor to list and format timestamp
        history = []
        for entry in history_cursor:
            if 'timestamp' in entry:
                entry['timestamp'] = entry['timestamp'].isoformat()
            history.append(entry)
        
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}")
        return jsonify({'error': 'Failed to get history'}), 500

@app.route('/clear_history', methods=['POST'])
def clear_history():
    try:
        # Get user email from either session or JWT
        user_email = None
        
        if 'user' in session:
            user_email = session['user']['email']
        else:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    from flask_jwt_extended import decode_token
                    decoded = decode_token(token)
                    user_email = decoded['sub']
                except Exception as e:
                    logger.error(f"JWT token error in clear_history: {str(e)}")
                    return jsonify({'error': 'Invalid token'}), 401
        
        # If no user is authenticated, return error
        if not user_email:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Delete history for the user
        result = mongo.db.history.delete_many({'user_email': user_email})
        
        logger.info(f"Cleared history for user {user_email}. Deleted {result.deleted_count} records.")
        return jsonify({'message': f'History cleared. Deleted {result.deleted_count} records.'})
    except Exception as e:
        logger.error(f"Error clearing history: {str(e)}")
        return jsonify({'error': 'Failed to clear history'}), 500

@app.route('/logout', methods=['GET'])
def logout():
    try:
        if 'user' in session:
            logger.info(f"User logged out: {session['user']['email']}")
            session.pop('user', None)
        return jsonify({'message': 'Logged out'})
    except Exception as e:
        logger.error(f"Error logging out: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@app.route('/options', methods=['OPTIONS'])
def options():
    return '', 200

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    traceback.print_exc()
    return jsonify({'error': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    try:
        # For HTTPS support in development (optional)
        # You'll need to generate a self-signed certificate:
        # openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
        
        # Uncomment below for HTTPS:
        # if os.path.exists('cert.pem') and os.path.exists('key.pem'):
        #     app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=('cert.pem', 'key.pem'))
        # else:
        #     logger.warning("SSL certificates not found, running in HTTP mode")
        #     app.run(host='0.0.0.0', port=5000, debug=True)
        
        # For HTTP:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.critical(f"Failed to start server: {str(e)}")
        traceback.print_exc()