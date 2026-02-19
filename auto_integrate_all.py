#!/usr/bin/env python3
"""
Automatic Integration Script - Updates ALL files with authentication and portfolio
Run this script in your project folder to automatically update everything.

Usage: python auto_integrate_all.py
"""

import os
import sys
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create backup of existing file"""
    if os.path.exists(filepath):
        backup = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(filepath, backup)
        print(f"  ✓ Backup created: {backup}")
        return True
    return False

def update_stock_backend():
    """Update stock_backend.py with authentication and portfolio"""
    
    print("\n" + "="*70)
    print("UPDATING stock_backend.py")
    print("="*70)
    
    if not os.path.exists('stock_backend.py'):
        print("  ❌ stock_backend.py not found!")
        return False
    
    backup_file('stock_backend.py')
    
    with open('stock_backend.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Update Flask imports
    old_flask_import = 'from flask import Flask, jsonify, request'
    new_flask_import = 'from flask import Flask, jsonify, request, send_file'
    
    if old_flask_import in content and 'send_file' not in content:
        content = content.replace(old_flask_import, new_flask_import)
        print("  ✓ Updated Flask imports")
    
    # 2. Add authentication imports after other imports
    auth_imports = '''from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from auth import (init_db, create_user, verify_user, get_user_by_id, 
                  update_last_login, get_user_watchlist, add_to_watchlist, 
                  remove_from_watchlist, get_user_portfolio, add_to_portfolio,
                  update_portfolio_holding, remove_from_portfolio)
'''
    
    if 'from flask_login import' not in content:
        # Find position after flask_cors import
        cors_pos = content.find('from flask_cors import CORS')
        if cors_pos != -1:
            next_line = content.find('\n', cors_pos) + 1
            content = content[:next_line] + auth_imports + '\n' + content[next_line:]
            print("  ✓ Added authentication imports")
    
    # 3. Add Flask-Login setup after app = Flask(__name__)
    flask_login_setup = '''
# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

# Initialize database
init_db()

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))

# Serve HTML pages
@app.route('/')
def home():
    return send_file('login.html')

@app.route('/login.html')
def login_page():
    return send_file('login.html')

@app.route('/stock_tracker.html')
def stock_tracker_page():
    return send_file('stock_tracker.html')

'''
    
    if 'login_manager = LoginManager()' not in content:
        app_init = 'CORS(app)'
        app_pos = content.find(app_init)
        if app_pos != -1:
            next_line = content.find('\n', app_pos) + 1
            content = content[:next_line] + flask_login_setup + content[next_line:]
            print("  ✓ Added Flask-Login setup")
    
    # 4. Add authentication routes before first @app.route
    auth_routes = '''
# ══════════════════════════════════════════════════════════════════════
# AUTHENTICATION ROUTES
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not username or not email or not password:
            return jsonify({'success': False, 'message': 'All fields required'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
        
        user_id = create_user(username, email, password)
        if user_id:
            return jsonify({'success': True, 'message': 'User created successfully'})
        return jsonify({'success': False, 'message': 'Username or email already exists'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password required'}), 400
        
        user = verify_user(username, password)
        if user:
            login_user(user)
            update_last_login(user.id)
            return jsonify({'success': True, 'username': user.username, 'user_id': user.id})
        
        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    logout_user()
    return jsonify({'success': True})

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check if user is authenticated"""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True, 
            'username': current_user.username,
            'user_id': current_user.id
        })
    return jsonify({'authenticated': False})

# ══════════════════════════════════════════════════════════════════════
# WATCHLIST ROUTES
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/watchlist', methods=['GET'])
@login_required
def get_user_watchlist_api():
    """Get current user's watchlist with live prices"""
    try:
        watchlist = get_user_watchlist(current_user.id)
        for stock in watchlist:
            symbol = stock['symbol']
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.info
                stock['price'] = data.get('currentPrice', 0)
                stock['change'] = data.get('regularMarketChange', 0)
                stock['changePercent'] = data.get('regularMarketChangePercent', 0)
            except:
                stock['price'] = 0
                stock['change'] = 0
                stock['changePercent'] = 0
        return jsonify(watchlist)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist/add', methods=['POST'])
@login_required
def add_to_watchlist_api():
    """Add stock to current user's watchlist"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').strip()
        name = data.get('name', '').strip()
        
        if not symbol or not name:
            return jsonify({'success': False, 'message': 'Symbol and name required'}), 400
        
        if add_to_watchlist(current_user.id, symbol, name):
            return jsonify({'success': True, 'message': 'Added to watchlist'})
        return jsonify({'success': False, 'message': 'Already in watchlist'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/watchlist/remove', methods=['POST'])
@login_required
def remove_from_watchlist_api():
    """Remove stock from current user's watchlist"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').strip()
        
        if not symbol:
            return jsonify({'success': False, 'message': 'Symbol required'}), 400
        
        remove_from_watchlist(current_user.id, symbol)
        return jsonify({'success': True, 'message': 'Removed from watchlist'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ══════════════════════════════════════════════════════════════════════
# PORTFOLIO ROUTES
# ══════════════════════════════════════════════════════════════════════

@app.route('/api/portfolio', methods=['GET'])
@login_required
def get_user_portfolio_api():
    """Get current user's portfolio with current values"""
    try:
        portfolio = get_user_portfolio(current_user.id)
        
        for holding in portfolio:
            symbol = holding['symbol']
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.info
                current_price = data.get('currentPrice', 0)
                
                holding['current_price'] = current_price
                holding['current_value'] = current_price * holding['quantity']
                holding['invested_value'] = holding['buy_price'] * holding['quantity']
                holding['profit_loss'] = holding['current_value'] - holding['invested_value']
                holding['profit_loss_percent'] = (
                    (holding['profit_loss'] / holding['invested_value'] * 100) 
                    if holding['invested_value'] > 0 else 0
                )
            except Exception as e:
                holding['current_price'] = 0
                holding['current_value'] = 0
                holding['invested_value'] = holding['buy_price'] * holding['quantity']
                holding['profit_loss'] = 0
                holding['profit_loss_percent'] = 0
        
        return jsonify(portfolio)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/add', methods=['POST'])
@login_required
def add_to_portfolio_api():
    """Add stock to current user's portfolio"""
    try:
        data = request.get_json()
        
        symbol = data.get('symbol', '').strip()
        name = data.get('name', '').strip()
        quantity = float(data.get('quantity', 0))
        buy_price = float(data.get('buy_price', 0))
        buy_date = data.get('buy_date', '')
        
        if not symbol or not name:
            return jsonify({'success': False, 'message': 'Symbol and name required'}), 400
        
        if quantity <= 0 or buy_price <= 0:
            return jsonify({'success': False, 'message': 'Invalid quantity or price'}), 400
        
        holding_id = add_to_portfolio(current_user.id, symbol, name, quantity, buy_price, buy_date)
        
        if holding_id:
            return jsonify({'success': True, 'message': 'Added to portfolio', 'holding_id': holding_id})
        return jsonify({'success': False, 'message': 'Failed to add to portfolio'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/portfolio/update', methods=['POST'])
@login_required
def update_portfolio_api():
    """Update an existing portfolio holding"""
    try:
        data = request.get_json()
        
        holding_id = int(data.get('holding_id', 0))
        quantity = float(data.get('quantity', 0))
        buy_price = float(data.get('buy_price', 0))
        
        if holding_id <= 0:
            return jsonify({'success': False, 'message': 'Invalid holding ID'}), 400
        
        if quantity <= 0 or buy_price <= 0:
            return jsonify({'success': False, 'message': 'Invalid quantity or price'}), 400
        
        if update_portfolio_holding(current_user.id, holding_id, quantity, buy_price):
            return jsonify({'success': True, 'message': 'Portfolio updated'})
        return jsonify({'success': False, 'message': 'Failed to update portfolio'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/portfolio/remove', methods=['POST'])
@login_required
def remove_from_portfolio_api():
    """Remove holding from current user's portfolio"""
    try:
        data = request.get_json()
        
        holding_id = int(data.get('holding_id', 0))
        
        if holding_id <= 0:
            return jsonify({'success': False, 'message': 'Invalid holding ID'}), 400
        
        remove_from_portfolio(current_user.id, holding_id)
        return jsonify({'success': True, 'message': 'Removed from portfolio'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/portfolio/summary', methods=['GET'])
@login_required  
def get_portfolio_summary_api():
    """Get portfolio summary with total invested, current value, and P&L"""
    try:
        portfolio = get_user_portfolio(current_user.id)
        
        total_invested = 0
        total_current = 0
        
        for holding in portfolio:
            symbol = holding['symbol']
            quantity = holding['quantity']
            buy_price = holding['buy_price']
            
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.info
                current_price = data.get('currentPrice', 0)
            except:
                current_price = 0
            
            total_invested += buy_price * quantity
            total_current += current_price * quantity
        
        total_pl = total_current - total_invested
        total_pl_percent = (total_pl / total_invested * 100) if total_invested > 0 else 0
        
        return jsonify({
            'total_invested': round(total_invested, 2),
            'total_current': round(total_current, 2),
            'total_profit_loss': round(total_pl, 2),
            'total_profit_loss_percent': round(total_pl_percent, 2),
            'holdings_count': len(portfolio)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

'''
    
    if '/api/auth/register' not in content:
        # Find first existing @app.route
        first_route = content.find('@app.route(\'/api/')
        if first_route != -1:
            content = content[:first_route] + auth_routes + '\n' + content[first_route:]
            print("  ✓ Added authentication and portfolio routes")
    
    # Save updated file
    with open('stock_backend.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("  ✅ stock_backend.py updated successfully!")
    return True

def update_stock_tracker_html():
    """Update stock_tracker.html with authentication check"""
    
    print("\n" + "="*70)
    print("UPDATING stock_tracker.html")
    print("="*70)
    
    if not os.path.exists('stock_tracker.html'):
        print("  ❌ stock_tracker.html not found!")
        return False
    
    backup_file('stock_tracker.html')
    
    with open('stock_tracker.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update API_URL to use window.location.origin
    if "const API_URL = 'http://localhost:5000/api'" in content:
        content = content.replace(
            "const API_URL = 'http://localhost:5000/api'",
            "const API_URL = window.location.origin + '/api'"
        )
        print("  ✓ Updated API_URL to use dynamic origin")
    
    # Add authentication check at the beginning of JavaScript
    auth_check_code = '''
        // ══════════════════════════════════════════════════════════════════════
        // AUTHENTICATION CHECK
        // ══════════════════════════════════════════════════════════════════════
        
        async function checkAuth() {
            try {
                const response = await fetch(API_URL + '/auth/check', {
                    credentials: 'include'
                });
                const data = await response.json();
                
                if (!data.authenticated) {
                    window.location.href = '/login.html';
                    return false;
                }
                
                displayUsername(data.username);
                return true;
            } catch (error) {
                console.error('Auth check failed:', error);
                window.location.href = '/login.html';
                return false;
            }
        }

        function displayUsername(username) {
            const header = document.querySelector('.header') || document.querySelector('header') || document.body.firstElementChild;
            if (header && !document.getElementById('userInfo')) {
                const userInfo = document.createElement('div');
                userInfo.id = 'userInfo';
                userInfo.style.cssText = 'position:absolute;top:1rem;right:1rem;display:flex;align-items:center;gap:1rem;z-index:1000;';
                userInfo.innerHTML = `
                    <span style="color:var(--text-secondary);font-weight:500;">👤 ${username}</span>
                    <button onclick="logout()" style="padding:0.5rem 1rem;background:#ff4444;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:500;">
                        Logout
                    </button>
                `;
                header.style.position = 'relative';
                header.appendChild(userInfo);
            }
        }

        async function logout() {
            try {
                await fetch(API_URL + '/auth/logout', {
                    method: 'POST',
                    credentials: 'include'
                });
            } catch (error) {
                console.error('Logout error:', error);
            }
            window.location.href = '/login.html';
        }

        // Run auth check on page load
        (async function() {
            const isAuthenticated = await checkAuth();
            if (!isAuthenticated) return;
            
            // Your existing initialization code continues here
        })();

'''
    
    if 'async function checkAuth()' not in content:
        # Find the first <script> tag with JavaScript
        script_pos = content.find('<script>')
        if script_pos != -1:
            insert_pos = content.find('\n', script_pos) + 1
            content = content[:insert_pos] + auth_check_code + content[insert_pos:]
            print("  ✓ Added authentication check")
    
    # Add credentials: 'include' to all fetch calls
    import re
    
    # Find all fetch calls without credentials
    fetch_pattern = r"fetch\(([^)]+)\)"
    matches = list(re.finditer(fetch_pattern, content))
    
    replacements_made = 0
    for match in reversed(matches):  # Reverse to maintain positions
        fetch_call = match.group(0)
        if 'credentials' not in fetch_call and 'API_URL' in fetch_call:
            # This is an API call without credentials
            url_part = match.group(1)
            if '{' not in fetch_call:  # Simple fetch without options
                new_fetch = f"fetch({url_part}, {{ credentials: 'include' }})"
                content = content[:match.start()] + new_fetch + content[match.end():]
                replacements_made += 1
    
    if replacements_made > 0:
        print(f"  ✓ Added credentials to {replacements_made} fetch calls")
    
    # Save updated file
    with open('stock_tracker.html', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("  ✅ stock_tracker.html updated successfully!")
    return True

def update_requirements_txt():
    """Update requirements.txt with Flask-Login"""
    
    print("\n" + "="*70)
    print("UPDATING requirements.txt")
    print("="*70)
    
    if not os.path.exists('requirements.txt'):
        print("  ⚠️  requirements.txt not found, creating new one")
    
    requirements = [
        'Flask==3.0.0',
        'Flask-Login==0.6.3',
        'Flask-CORS==4.0.0',
        'requests==2.31.0',
        'beautifulsoup4==4.12.2',
        'lxml==5.1.0',
        'yfinance==0.2.33',
        'pypdf==4.0.1',
        'Werkzeug==3.0.1',
        'gunicorn==21.2.0'
    ]
    
    with open('requirements.txt', 'w') as f:
        f.write('\n'.join(requirements) + '\n')
    
    print("  ✅ requirements.txt updated successfully!")
    return True

def main():
    """Main function to update all files"""
    
    print("\n" + "="*70)
    print("AUTOMATIC INTEGRATION SCRIPT")
    print("Adding Authentication + Watchlist + Portfolio to Database")
    print("="*70)
    
    # Check if required files exist
    required_files = ['auth.py', 'login.html']
    missing_files = []
    
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("\n❌ ERROR: Missing required files:")
        for file in missing_files:
            print(f"  - {file}")
        print("\nPlease make sure these files are in the same directory.")
        return False
    
    # Update all files
    success = True
    
    success &= update_requirements_txt()
    success &= update_stock_backend()
    success &= update_stock_tracker_html()
    
    if success:
        print("\n" + "="*70)
        print("✅ ALL FILES UPDATED SUCCESSFULLY!")
        print("="*70)
        print("\nNext steps:")
        print("1. Review the updated files")
        print("2. Set SECRET_KEY environment variable in Render")
        print("3. Push to GitHub:")
        print("   git add .")
        print("   git commit -m 'Add authentication with watchlist and portfolio'")
        print("   git push")
        print("\n4. Wait for Render to deploy (3-5 minutes)")
        print("5. Visit your app and create an account!")
        print("\n" + "="*70)
        return True
    else:
        print("\n" + "="*70)
        print("❌ INTEGRATION FAILED")
        print("="*70)
        print("\nPlease check the errors above and try again.")
        print("Your original files are backed up with timestamps.")
        return False

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
