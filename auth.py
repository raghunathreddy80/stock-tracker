"""
Authentication Module for Stock Tracker
Handles user registration, login, and session management
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime
from flask_login import UserMixin

# Database initialization
def init_db():
    """Initialize the user database"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Watchlists table (user-specific)
    c.execute('''
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, symbol)
        )
    ''')
    
    # Portfolio table (user-specific holdings)
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity REAL NOT NULL,
            buy_price REAL NOT NULL,
            buy_date TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

# Helper functions
def hash_password(password):
    """Hash password with SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, email, password):
    """Create a new user"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        password_hash = hash_password(password)
        
        c.execute('''
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        ''', (username, email, password_hash))
        
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        
        return user_id
    except sqlite3.IntegrityError:
        return None  # User already exists

def verify_user(username, password):
    """Verify user credentials"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    password_hash = hash_password(password)
    
    c.execute('''
        SELECT id, username, email FROM users
        WHERE username = ? AND password_hash = ?
    ''', (username, password_hash))
    
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data[0], user_data[1], user_data[2])
    return None

def get_user_by_id(user_id):
    """Get user by ID (for Flask-Login)"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute('SELECT id, username, email FROM users WHERE id = ?', (user_id,))
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data[0], user_data[1], user_data[2])
    return None

def update_last_login(user_id):
    """Update user's last login timestamp"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE users SET last_login = ? WHERE id = ?', 
              (datetime.now(), user_id))
    conn.commit()
    conn.close()

# Watchlist functions
def get_user_watchlist(user_id):
    """Get user's watchlist"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT symbol, name, added_at FROM watchlists
        WHERE user_id = ?
        ORDER BY added_at DESC
    ''', (user_id,))
    
    watchlist = c.fetchall()
    conn.close()
    
    return [{'symbol': w[0], 'name': w[1], 'added_at': w[2]} for w in watchlist]

def add_to_watchlist(user_id, symbol, name):
    """Add stock to user's watchlist"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO watchlists (user_id, symbol, name)
            VALUES (?, ?, ?)
        ''', (user_id, symbol, name))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False  # Already in watchlist

def remove_from_watchlist(user_id, symbol):
    """Remove stock from user's watchlist"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute('DELETE FROM watchlists WHERE user_id = ? AND symbol = ?', 
              (user_id, symbol))
    
    conn.commit()
    conn.close()

# Portfolio functions
def get_user_portfolio(user_id):
    """Get user's portfolio holdings"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, symbol, name, quantity, buy_price, buy_date, added_at 
        FROM portfolio
        WHERE user_id = ?
        ORDER BY added_at DESC
    ''', (user_id,))
    
    portfolio = c.fetchall()
    conn.close()
    
    return [{
        'id': p[0],
        'symbol': p[1], 
        'name': p[2], 
        'quantity': p[3],
        'buy_price': p[4],
        'buy_date': p[5],
        'added_at': p[6]
    } for p in portfolio]

def add_to_portfolio(user_id, symbol, name, quantity, buy_price, buy_date=None):
    """Add holding to user's portfolio"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO portfolio (user_id, symbol, name, quantity, buy_price, buy_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, symbol, name, quantity, buy_price, buy_date))
        
        holding_id = c.lastrowid
        conn.commit()
        conn.close()
        return holding_id
    except Exception as e:
        print(f"Error adding to portfolio: {e}")
        return None

def update_portfolio_holding(user_id, holding_id, quantity, buy_price):
    """Update an existing portfolio holding"""
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute('''
            UPDATE portfolio 
            SET quantity = ?, buy_price = ?
            WHERE id = ? AND user_id = ?
        ''', (quantity, buy_price, holding_id, user_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating portfolio: {e}")
        return False

def remove_from_portfolio(user_id, holding_id):
    """Remove holding from user's portfolio"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute('DELETE FROM portfolio WHERE id = ? AND user_id = ?', 
              (holding_id, user_id))
    
    conn.commit()
    conn.close()
