# Authentication Integration Guide

## What I've Created

1. **auth.py** - Complete authentication system
2. **requirements.txt** - All dependencies for deployment
3. **Procfile** - For hosting on Render/Heroku
4. **DEPLOYMENT.md** - Complete deployment guide
5. **.gitignore** - Prevents sensitive files from being committed

## Next Steps to Add Login

### Backend Changes Needed (stock_backend.py):

Add at the top:
```python
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from auth import init_db, create_user, verify_user, get_user_by_id, update_last_login
from auth import get_user_watchlist, add_to_watchlist, remove_from_watchlist
import os

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize database
init_db()

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))
```

Add login/register endpoints:
```python
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    user_id = create_user(username, email, password)
    if user_id:
        return jsonify({'success': True, 'message': 'User created'})
    return jsonify({'success': False, 'message': 'Username/email already exists'}), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = verify_user(username, password)
    if user:
        login_user(user)
        update_last_login(user.id)
        return jsonify({'success': True, 'username': user.username})
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True, 'username': current_user.username})
    return jsonify({'authenticated': False})
```

Modify watchlist endpoints to use user-specific data:
```python
@app.route('/api/watchlist', methods=['GET'])
@login_required
def get_watchlist_endpoint():
    watchlist = get_user_watchlist(current_user.id)
    # Fetch current prices for each stock
    # ... existing price fetching logic
    return jsonify(watchlist)

@app.route('/api/watchlist/add', methods=['POST'])
@login_required
def add_watchlist_endpoint():
    data = request.get_json()
    symbol = data.get('symbol')
    name = data.get('name')
    
    if add_to_watchlist(current_user.id, symbol, name):
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Already in watchlist'}), 400
```

### Frontend Changes (create new login.html):

```html
<!DOCTYPE html>
<html>
<head>
    <title>Stock Tracker - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            padding: 3rem;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 400px;
        }
        h1 { color: #333; margin-bottom: 2rem; text-align: center; }
        .form-group { margin-bottom: 1.5rem; }
        label { display: block; margin-bottom: 0.5rem; color: #666; font-weight: 500; }
        input {
            width: 100%;
            padding: 0.8rem;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1rem;
            transition: border 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            width: 100%;
            padding: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover { transform: translateY(-2px); }
        .toggle-form {
            text-align: center;
            margin-top: 1rem;
            color: #666;
        }
        .toggle-form a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        .error { color: red; margin-top: 1rem; text-align: center; }
        .success { color: green; margin-top: 1rem; text-align: center; }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>📈 Stock Tracker</h1>
        
        <form id="authForm">
            <div id="emailGroup" class="form-group" style="display:none;">
                <label>Email</label>
                <input type="email" id="email" placeholder="you@example.com">
            </div>
            
            <div class="form-group">
                <label>Username</label>
                <input type="text" id="username" placeholder="Enter username" required>
            </div>
            
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="password" placeholder="Enter password" required>
            </div>
            
            <button type="submit" id="submitBtn">Login</button>
        </form>
        
        <div class="toggle-form">
            <span id="toggleText">Don't have an account? </span>
            <a href="#" id="toggleLink">Sign Up</a>
        </div>
        
        <div id="message"></div>
    </div>

    <script>
        const API_URL = window.location.origin;
        let isRegisterMode = false;

        document.getElementById('toggleLink').addEventListener('click', (e) => {
            e.preventDefault();
            isRegisterMode = !isRegisterMode;
            
            document.getElementById('emailGroup').style.display = isRegisterMode ? 'block' : 'none';
            document.getElementById('submitBtn').textContent = isRegisterMode ? 'Sign Up' : 'Login';
            document.getElementById('toggleText').textContent = isRegisterMode ? 
                'Already have an account? ' : "Don't have an account? ";
            document.getElementById('toggleLink').textContent = isRegisterMode ? 'Login' : 'Sign Up';
            document.getElementById('message').innerHTML = '';
        });

        document.getElementById('authForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const email = document.getElementById('email').value;
            
            const endpoint = isRegisterMode ? '/api/auth/register' : '/api/auth/login';
            const payload = isRegisterMode ? 
                { username, email, password } : 
                { username, password };
            
            try {
                const response = await fetch(API_URL + endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    credentials: 'include'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    if (isRegisterMode) {
                        document.getElementById('message').innerHTML = 
                            '<div class="success">Account created! Please login.</div>';
                        // Switch to login mode
                        document.getElementById('toggleLink').click();
                    } else {
                        // Redirect to main app
                        window.location.href = '/stock_tracker.html';
                    }
                } else {
                    document.getElementById('message').innerHTML = 
                        `<div class="error">${data.message}</div>`;
                }
            } catch (error) {
                document.getElementById('message').innerHTML = 
                    '<div class="error">Connection error. Please try again.</div>';
            }
        });
    </script>
</body>
</html>
```

## Deployment Steps

1. **Add gunicorn to requirements.txt**:
   ```
   gunicorn==21.2.0
   ```

2. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit with authentication"
   git branch -M main
   git remote add origin your-repo-url
   git push -u origin main
   ```

3. **Deploy on Render.com** (Recommended):
   - Go to https://render.com
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - Name: stock-tracker
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `gunicorn stock_backend:app`
   - Add Environment Variables:
     - `GEMINI_API_KEY`: your_api_key
     - `SECRET_KEY`: generate with `python -c "import secrets; print(secrets.token_hex(32))"`
   - Click "Create Web Service"

4. **Your app will be live at**: `https://stock-tracker-xxxx.onrender.com`

## Security Notes

- Change SECRET_KEY in production
- Use HTTPS (automatic on Render/Railway)
- Consider adding rate limiting
- Add email verification (optional)
- Add password reset functionality (optional)

Would you like me to integrate these changes into your existing files?
