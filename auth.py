"""
Authentication module with PostgreSQL support
Automatically uses PostgreSQL if DATABASE_URL is set, otherwise falls back to SQLite
"""

import os
import hashlib
from datetime import datetime
from flask_login import UserMixin

# Check if PostgreSQL is available
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    print("✓ Using PostgreSQL database")
else:
    import sqlite3
    print("⚠ Using SQLite database (data will be lost on restart)")

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

def get_db_connection():
    """Get database connection (PostgreSQL or SQLite)"""
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect('users.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        # PostgreSQL schema
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(256) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS watchlists (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                name VARCHAR(200) NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, symbol)
            )
        ''')
        # Add order_index column if it doesn't exist (for existing databases)
        try:
            c.execute('ALTER TABLE watchlists ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0')
        except Exception:
            pass  # Column already exists
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                name VARCHAR(200) NOT NULL,
                quantity REAL NOT NULL,
                buy_price REAL NOT NULL,
                buy_date VARCHAR(20),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
    else:
        # SQLite schema
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
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, symbol)
            )
        ''')
        # Add order_index column if it doesn't exist (for existing databases)
        try:
            c.execute('ALTER TABLE watchlists ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0')
        except Exception:
            pass  # Column already exists
        
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
    print("✓ Database tables initialized")

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, email, password):
    """Create a new user"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        password_hash = hash_password(password)
        
        if USE_POSTGRES:
            c.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
                (username, email, password_hash)
            )
            user_id = c.fetchone()['id']
        else:
            c.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                (username, email, password_hash)
            )
            user_id = c.lastrowid
        
        conn.commit()
        conn.close()
        return user_id
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def verify_user(username, password):
    """Verify user credentials and return User object"""
    conn = get_db_connection()
    c = conn.cursor()
    password_hash = hash_password(password)
    
    if USE_POSTGRES:
        c.execute(
            'SELECT * FROM users WHERE username = %s AND password_hash = %s',
            (username, password_hash)
        )
    else:
        c.execute(
            'SELECT * FROM users WHERE username = ? AND password_hash = ?',
            (username, password_hash)
        )
    
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['email'])
    return None

def get_user_by_id(user_id):
    """Get user by ID"""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    else:
        c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['email'])
    return None

def update_last_login(user_id):
    """Update user's last login time"""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s', (user_id,))
    else:
        c.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
    
    conn.commit()
    conn.close()

# Watchlist functions
def get_user_watchlist(user_id):
    """Get user's watchlist ordered by user-defined order"""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute(
            'SELECT id, symbol, name, order_index, added_at FROM watchlists WHERE user_id = %s ORDER BY order_index ASC, added_at ASC',
            (user_id,)
        )
    else:
        c.execute(
            'SELECT id, symbol, name, order_index, added_at FROM watchlists WHERE user_id = ? ORDER BY order_index ASC, added_at ASC',
            (user_id,)
        )
    
    watchlist = c.fetchall()
    conn.close()
    return [dict(w) for w in watchlist]

def add_to_watchlist(user_id, symbol, name):
    """Add stock to user's watchlist"""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        # Get the next order_index (append to end)
        if USE_POSTGRES:
            c.execute('SELECT COALESCE(MAX(order_index), -1) + 1 FROM watchlists WHERE user_id = %s', (user_id,))
        else:
            c.execute('SELECT COALESCE(MAX(order_index), -1) + 1 FROM watchlists WHERE user_id = ?', (user_id,))
        next_index = c.fetchone()[0]

        if USE_POSTGRES:
            c.execute(
                'INSERT INTO watchlists (user_id, symbol, name, order_index) VALUES (%s, %s, %s, %s)',
                (user_id, symbol, name, next_index)
            )
        else:
            c.execute(
                'INSERT INTO watchlists (user_id, symbol, name, order_index) VALUES (?, ?, ?, ?)',
                (user_id, symbol, name, next_index)
            )

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding to watchlist: {e}")
        return False


def reorder_watchlist(user_id, symbols_in_order):
    """Save the user's watchlist order. symbols_in_order is a list of symbols top-to-bottom."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        for idx, symbol in enumerate(symbols_in_order):
            if USE_POSTGRES:
                c.execute(
                    'UPDATE watchlists SET order_index = %s WHERE user_id = %s AND symbol = %s',
                    (idx, user_id, symbol)
                )
            else:
                c.execute(
                    'UPDATE watchlists SET order_index = ? WHERE user_id = ? AND symbol = ?',
                    (idx, user_id, symbol)
                )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error reordering watchlist: {e}")
        return False

def remove_from_watchlist(user_id, symbol):
    """Remove stock from user's watchlist"""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('DELETE FROM watchlists WHERE user_id = %s AND symbol = %s', (user_id, symbol))
    else:
        c.execute('DELETE FROM watchlists WHERE user_id = ? AND symbol = ?', (user_id, symbol))
    
    conn.commit()
    conn.close()

# Portfolio functions
def get_user_portfolio(user_id):
    """Get user's portfolio holdings"""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('''
            SELECT id, symbol, name, quantity, buy_price, buy_date, added_at 
            FROM portfolio
            WHERE user_id = %s
            ORDER BY added_at DESC
        ''', (user_id,))
    else:
        c.execute('''
            SELECT id, symbol, name, quantity, buy_price, buy_date, added_at 
            FROM portfolio
            WHERE user_id = ?
            ORDER BY added_at DESC
        ''', (user_id,))
    
    portfolio = c.fetchall()
    conn.close()
    
    return [dict(p) for p in portfolio]

def add_to_portfolio(user_id, symbol, name, quantity, buy_price, buy_date=None):
    """Add holding to user's portfolio"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if USE_POSTGRES:
            c.execute('''
                INSERT INTO portfolio (user_id, symbol, name, quantity, buy_price, buy_date)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (user_id, symbol, name, quantity, buy_price, buy_date))
            holding_id = c.fetchone()['id']
        else:
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
        conn = get_db_connection()
        c = conn.cursor()
        
        if USE_POSTGRES:
            c.execute('''
                UPDATE portfolio 
                SET quantity = %s, buy_price = %s
                WHERE id = %s AND user_id = %s
            ''', (quantity, buy_price, holding_id, user_id))
        else:
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
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('DELETE FROM portfolio WHERE id = %s AND user_id = %s', (holding_id, user_id))
    else:
        c.execute('DELETE FROM portfolio WHERE id = ? AND user_id = ?', (holding_id, user_id))
    
    conn.commit()
    conn.close()
