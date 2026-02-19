"""
Flask Backend for Stock Tracker
Run: python stock_backend.py
Then open stock_tracker.html in your browser
"""

import subprocess, sys, os, re
from datetime import datetime

# ── auto-install ──────────────────────────────────────────────────────────────
for pkg, imp in [('flask','flask'),('flask-cors','flask_cors'),
                 ('yfinance','yfinance'),('requests','requests')]:
    try:
        __import__(imp)
    except ImportError:
        print(f"Installing {pkg}…")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from auth import (init_db, create_user, verify_user, get_user_by_id, 
                  update_last_login, get_user_watchlist, add_to_watchlist, 
                  remove_from_watchlist, get_user_portfolio, add_to_portfolio,
                  update_portfolio_holding, remove_from_portfolio)

import yfinance as yf
import requests as req

app = Flask(__name__)
CORS(app)

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


# ── helpers ───────────────────────────────────────────────────────────────────
def make_proxies(host, port):
    if host and port:
        # Use host exactly as provided - if it already has http://, use as-is
        if host.startswith('http://') or host.startswith('https://'):
            url = f"{host}:{port}"
        else:
            url = f"http://{host}:{port}"
        return {'http': url, 'https': url}
    return None

DATE_FORMATS = [
    '%d-%b-%Y %H:%M:%S',
    '%d-%b-%Y %H:%M',
    '%d-%b-%Y',
    '%d/%m/%Y %H:%M:%S',
    '%d/%m/%Y',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d',
]

def parse_date(s):
    if not s:
        return None
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    m = re.search(r'(\d{1,2}-[A-Za-z]{3}-\d{4})', s)
    if m:
        try:
            return datetime.strptime(m.group(1), '%d-%b-%Y')
        except ValueError:
            pass
    print(f"  [warn] unparseable date: '{s}'")
    return None


# ── routes ────────────────────────────────────────────────────────────────────


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


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/search')
def search_stocks():
    query      = request.args.get('q', '')
    proxy_host = request.args.get('proxy_host', '').strip()
    proxy_port = request.args.get('proxy_port', '').strip()

    if not query:
        return jsonify({'error': 'No query'}), 400

    proxies = make_proxies(proxy_host, proxy_port)
    if proxies:
        os.environ['HTTP_PROXY']  = proxies['http']
        os.environ['HTTPS_PROXY'] = proxies['https']
    else:
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)

    try:
        try:
            quotes = yf.Search(query, max_results=20).quotes
        except Exception:
            from urllib.parse import quote as _quote
            url  = (f"https://query2.finance.yahoo.com/v1/finance/search"
                    f"?q={_quote(query)}&quotesCount=20&lang=en-US")
            resp = req.get(url, timeout=8,
                           headers={'User-Agent': 'Mozilla/5.0'},
                           proxies=proxies)
            quotes = resp.json().get('quotes', [])

        results, seen = [], set()
        for q in quotes:
            sym  = q.get('symbol', '')
            name = q.get('longname') or q.get('shortname') or sym
            if sym in seen or not (sym.endswith('.NS') or sym.endswith('.BO')):
                continue
            seen.add(sym)
            results.append({'symbol': sym, 'name': name,
                             'exchange': 'NSE' if sym.endswith('.NS') else 'BSE'})
            if len(results) >= 10:
                break

        return jsonify({'results': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/quote')
def get_quote():
    symbol     = request.args.get('symbol', '')
    proxy_host = request.args.get('proxy_host', '').strip()
    proxy_port = request.args.get('proxy_port', '').strip()

    if not symbol:
        return jsonify({'error': 'No symbol'}), 400

    proxies = make_proxies(proxy_host, proxy_port)
    if proxies:
        os.environ['HTTP_PROXY']  = proxies['http']
        os.environ['HTTPS_PROXY'] = proxies['https']
    else:
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)

    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info
        hist   = ticker.history(period='1d')

        if hist.empty:
            return jsonify({'error': 'No data'}), 404

        price  = float(hist['Close'].iloc[-1])
        prev   = float(info.get('previousClose') or price)
        chg    = price - prev
        chg_pc = (chg / prev * 100) if prev else 0

        return jsonify({
            'symbol':        symbol,
            'name':          info.get('longName') or info.get('shortName') or symbol,
            'price':         round(price,  2),
            'change':        round(chg,    2),
            'changePercent': round(chg_pc, 4),
            'volume':        int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0,
            'previousClose': round(prev,   2),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/announcements', methods=['POST'])
def get_announcements():
    """
    Fetch corporate announcements for watchlist symbols from BSE (primary) + NSE (fallback).
    BSE API is the most reliable — no cookie needed, just correct headers.
    """
    req_data   = request.get_json() or {}
    symbols    = req_data.get('symbols', [])
    proxy_host = req_data.get('proxy_host', '').strip()
    proxy_port = req_data.get('proxy_port', '').strip()

    if not symbols:
        return jsonify({'announcements': []})

    proxies = make_proxies(proxy_host, proxy_port)
    print(f"\n[announcements] {len(symbols)} symbols, proxy={proxies.get('http','none') if proxies else 'none'}")

    import datetime

    # BSE needs Origin + sec-fetch headers to avoid 403
    BSE_HDR = {
        'User-Agent':        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept':            'application/json, text/plain, */*',
        'Accept-Language':   'en-US,en;q=0.9',
        'Origin':            'https://www.bseindia.com',
        'Referer':           'https://www.bseindia.com/',
        'sec-fetch-site':    'same-site',
        'sec-fetch-mode':    'cors',
        'sec-fetch-dest':    'empty',
    }
    NSE_HDR = {
        'User-Agent':        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept':            'application/json, text/plain, */*',
        'Accept-Language':   'en-US,en;q=0.9',
        'Referer':           'https://www.nseindia.com/',
    }

    def safe_get(url, hdrs, sess=None, timeout=12):
        try:
            fn = sess.get if sess else req.get
            r  = fn(url, headers=hdrs, timeout=timeout, proxies=proxies, allow_redirects=True)
            print(f"  HTTP {r.status_code}  {url[-80:]}")
            return r if r.ok else None
        except Exception as e:
            print(f"  FAIL {url[-70:]}: {e}")
            return None

    def bse_att_url(news_id, att, raw_dt=''):
        """
        BSE attachment URL logic:
        - newsid page always works (opens the BSE filing detail page with PDF link)
        - Direct PDF: AttachLive = recent (last 30 days), AttachHis = older
        According to screener.in behavior:
          Annual reports → AttachHis (filed once a year, become historical quickly)
          Recent concalls/announcements → AttachLive (filed within last month)
        """
        if news_id:
            return f"https://www.bseindia.com/corporates/ann.html?newsid={news_id}"
        if att:
            # Determine folder based on filing date
            dt = parse_date(raw_dt) if raw_dt else None
            if dt:
                import datetime
                days_ago = (datetime.datetime.now() - dt).days
                folder = 'AttachLive' if days_ago <= 30 else 'AttachHis'
            else:
                # No date → assume AttachHis (safer for older documents)
                folder = 'AttachHis'
            return f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{att}"
        return ''

    def parse_items(items, symbol, base, exchange):
        out = []
        for item in items:
            if exchange == 'BSE':
                news_id = str(item.get('NEWSID') or '').strip()
                att     = (item.get('ATTACHMENTNAME') or '').strip()
                title   = (item.get('HEADLINE') or item.get('NEWSSUB') or '').strip()
                raw_dt  = (item.get('NEWS_DT') or item.get('DT_TM') or '').strip()
                company = (item.get('SLONGNAME') or item.get('COMPANYNAME') or base)
                cat     = (item.get('CATEGORYNAME') or item.get('NEWSCATNAME') or 'General')
                att_url = bse_att_url(news_id, att, raw_dt)
            else:
                news_id = ''
                att     = (item.get('attchmntFile') or '').strip()
                title   = (item.get('desc') or item.get('subject') or '').strip()
                raw_dt  = (item.get('an_dt') or item.get('date') or '').strip()
                company = (item.get('comp') or item.get('company') or base)
                cat     = (item.get('smIndustry') or item.get('category') or 'General')
                att_url = (att if att.startswith('http')
                           else f"https://nsearchives.nseindia.com/corporate/{att}") if att else ''
            dt = parse_date(raw_dt)
            ts = dt.timestamp() if dt else 0
            out.append({
                'symbol': symbol, 'company': company,
                'title':  title or 'Corporate Announcement',
                'date':   raw_dt, 'date_ts': ts,
                'category':       cat,
                'exchange':       exchange,
                'attachment_url': att_url,
            })
        return out

    # ── Step 1: resolve BSE scrip codes for all symbols ───────────────────────
    bse_codes = {}   # base → numeric BSE scrip code string

    # Try bse pip package first (most reliable)
    try:
        from bse import BSE as BsePkg
        import tempfile
        with BsePkg(download_folder=tempfile.gettempdir()) as bpkg:
            for sym in symbols:
                base = sym.replace('.NS','').replace('.BO','')
                try:
                    r = bpkg.lookup(base)
                    if r and r.get('bse_code'):
                        bse_codes[base] = str(r['bse_code'])
                except Exception:
                    pass
        print(f"  BSE pkg codes: {bse_codes}")
    except Exception as e:
        print(f"  BSE pkg not available: {e}")

    # fetchComp for any still missing
    for sym in symbols:
        base = sym.replace('.NS','').replace('.BO','')
        if base in bse_codes:
            continue
        r = safe_get(
            f"https://api.bseindia.com/BseIndiaAPI/api/fetchComp/w"
            f"?companySortOrder=A&industry=&issuerType=C&turnover=&companyType="
            f"&mktcap=&segment=&status=Active&indexType=&pageno=1&pagesize=25&search={base}",
            BSE_HDR, timeout=8)
        if r:
            try:
                for item in r.json().get('Table', []):
                    sym_val = (item.get('nsesymbol') or item.get('NSESymbol') or '').upper()
                    if sym_val == base:
                        code = str(item.get('scripcode') or item.get('Scripcode') or '')
                        if code:
                            bse_codes[base] = code
                            print(f"  fetchComp: {base} → {code}")
                        break
            except Exception:
                pass

    print(f"  Resolved codes: {bse_codes}")

    # ── Step 2: NSE session (built once for fallback) ─────────────────────────
    nse_sess = req.Session()
    try:
        nse_sess.get('https://www.nseindia.com',
                     headers={**NSE_HDR, 'Accept': 'text/html,application/xhtml+xml,*/*'},
                     timeout=12, proxies=proxies)
        print(f"  NSE cookies: {list(nse_sess.cookies.keys())}")
    except Exception as e:
        print(f"  NSE session: {e}")

    # ── Step 3: fetch per symbol ──────────────────────────────────────────────
    all_ann = []

    for symbol in symbols:
        base     = symbol.replace('.NS','').replace('.BO','')
        bse_code = bse_codes.get(base, '')
        got      = False
        print(f"\n--- {base} (BSE code: {bse_code or 'unknown'}) ---")

        # ── BSE AnnGetData: most recent filings, per scrip code ───────────────
        if bse_code:
            r = safe_get(
                f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
                f"?strCat=-1&strPrevDate=&strScrip={bse_code}&strSearch=P&strToDate=&strType=C",
                BSE_HDR, timeout=15)
            if r:
                try:
                    payload = r.json()
                    items = payload if isinstance(payload, list) else \
                            payload.get('Table', payload.get('Data', []))
                    print(f"  BSE AnnGetData: {len(items)} items")
                    parsed = parse_items(items, symbol, base, 'BSE')
                    all_ann.extend(parsed)
                    got = bool(parsed)
                    for a in parsed[:3]:
                        print(f"    [{a['date'][:10]}] {a['title'][:60]}")
                except Exception as e:
                    print(f"  BSE AnnGetData parse error: {e}")

        # ── BSE AnnSubCategoryGetData: date-range search, scrip code required ─
        if not got and bse_code:
            today    = datetime.date.today()
            week_ago = today - datetime.timedelta(days=7)
            # This API uses DD/MM/YYYY format (URL-encoded)
            from_dt  = week_ago.strftime('%d%%2F%m%%2F%Y')   # 10%2F02%2F2026
            to_dt    = today.strftime('%d%%2F%m%%2F%Y')
            r = safe_get(
                f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
                f"?pageno=1&strCat=-1&strPrevDate={from_dt}&strScrip={bse_code}"
                f"&strSearch=C&strToDate={to_dt}&strType=C&subcategory=-1",
                BSE_HDR, timeout=15)
            if r:
                try:
                    payload = r.json()
                    items = payload if isinstance(payload, list) else payload.get('Table', [])
                    print(f"  BSE AnnSubCat: {len(items)} items")
                    parsed = parse_items(items, symbol, base, 'BSE')
                    all_ann.extend(parsed)
                    got = bool(parsed)
                except Exception as e:
                    print(f"  BSE AnnSubCat parse error: {e}")

        # ── BSE Msource search: works with NSE symbol directly (no scrip code) ─
        if not got:
            r = safe_get(
                f"https://api.bseindia.com/Msource/1D/getQouteSearch.aspx?Type=EQ&text={base}&flag=site",
                {**BSE_HDR, 'Accept': 'application/json, text/plain, */*'}, timeout=8)
            if r:
                try:
                    hits = r.json()
                    if isinstance(hits, list) and hits:
                        code = str(hits[0].get('scripcode',''))
                        if code and code not in bse_codes.values():
                            bse_codes[base] = code
                            bse_code = code
                            print(f"  Msource found code: {code}")
                except Exception:
                    pass

        # ── NSE fallback ──────────────────────────────────────────────────────
        if not got:
            for url in [
                f"https://www.nseindia.com/api/corporate-announcements?symbol={base}",
                f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={base}",
            ]:
                r = safe_get(url, NSE_HDR, sess=nse_sess, timeout=12)
                if r:
                    try:
                        d = r.json()
                        items = d if isinstance(d, list) else d.get('data', d.get('announcements', []))
                        if items:
                            print(f"  NSE: {len(items)} items")
                            parsed = parse_items(items[:15], symbol, base, 'NSE')
                            all_ann.extend(parsed)
                            got = bool(parsed)
                            break
                    except Exception as e:
                        print(f"  NSE parse error: {e}")

        if not got:
            print(f"  !! No announcements found for {base}")

    # ── Sort, dedup, return ───────────────────────────────────────────────────
    all_ann.sort(key=lambda x: x['date_ts'], reverse=True)
    seen, deduped = set(), []
    for a in all_ann:
        key = (a['symbol'], a['title'][:50], a['date'][:10])
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    print(f"\n[done] {len(deduped)} unique announcements from {len(symbols)} symbols")
    for a in deduped[:6]:
        print(f"  [{a['exchange']}] {a['date'][:10]}  {a['company']}: {a['title'][:55]}")

    for a in deduped:
        del a['date_ts']

    return jsonify({'announcements': deduped[:60]})


@app.route('/api/deepdive/fetch', methods=['POST'])
def deepdive_fetch():
    """
    Priority: BSE filing API → NSE annual-reports API → NSE announcements API
    All return direct PDF links from bseindia.com or nseindia.com.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'beautifulsoup4'])
        from bs4 import BeautifulSoup

    data        = request.get_json() or {}
    base_symbol = data.get('base_symbol', '').upper().strip()
    company     = data.get('company', '').strip()
    source_type = data.get('source_type', '')
    year        = data.get('year')
    quarter     = data.get('quarter', '')
    proxy_host  = data.get('proxy_host', '').strip()
    proxy_port  = data.get('proxy_port', '').strip()

    proxies = make_proxies(proxy_host, proxy_port)

    HTML_HDR = {
        'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept':          'text/html,application/xhtml+xml,*/*;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    JSON_HDR = {**HTML_HDR, 'Accept': 'application/json, text/plain, */*'}
    BSE_HDR  = {
        **JSON_HDR,
        'Origin':         'https://www.bseindia.com',
        'Referer':        'https://www.bseindia.com/',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
    }
    NSE_HDR  = {**JSON_HDR, 'Referer': 'https://www.nseindia.com/'}

    extracted_text = ''
    source_url     = ''
    all_docs       = []

    def safe_get(url, hdrs, timeout=12):
        try:
            r = req.get(url, headers=hdrs, timeout=timeout,
                        proxies=proxies, allow_redirects=True)
            if r.ok:
                return r
            print(f"  HTTP {r.status_code}: {url[:70]}")
        except Exception as e:
            print(f"  FAIL {url[:70]}: {e}")
        return None

    # ── BSE: get scrip code ───────────────────────────────────────────────────
    # BSE scrip codes are numeric e.g. 532540=TCS, 500180=HDFCBANK, 544218=IEX
    # The 'bse' pip package has a verified lookup. Fall back to direct API calls.
    bse_code = ''

    # Method 1: 'bse' pip package — most reliable, wraps the correct BSE API
    try:
        try:
            from bse import BSE as BsePkg
        except ImportError:
            print(f"  Installing bse package...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'bse',
                                   '--break-system-packages', '-q'])
            from bse import BSE as BsePkg
        import tempfile
        with BsePkg(download_folder=tempfile.gettempdir()) as bse_pkg:
            result = bse_pkg.lookup(base_symbol)
            if result and result.get('bse_code'):
                bse_code = str(result['bse_code'])
                print(f"  BSE code (bse pkg): {bse_code} — {result.get('company_name','')}")
    except Exception as e:
        print(f"  BSE pkg lookup error: {e}")

    # Method 2: BSE fetchComp search API
    if not bse_code:
        try:
            r = safe_get(
                f"https://api.bseindia.com/BseIndiaAPI/api/fetchComp/w"
                f"?companySortOrder=A&industry=&issuerType=C&turnover="
                f"&companyType=&mktcap=&segment=&status=Active"
                f"&indexType=&pageno=1&pagesize=25&search={base_symbol}",
                BSE_HDR, timeout=8)
            if r:
                items = r.json().get('Table', [])
                for item in items:
                    sym = (item.get('nsesymbol') or item.get('NSESymbol') or '').upper()
                    if sym == base_symbol:
                        bse_code = str(item.get('scripcode') or item.get('Scripcode') or '')
                        print(f"  BSE code (fetchComp): {bse_code}")
                        break
        except Exception as e:
            print(f"  BSE fetchComp error: {e}")

    # Method 3: BSE text search
    if not bse_code:
        try:
            r = safe_get(
                f"https://api.bseindia.com/BseIndiaAPI/api/Search/w?str={base_symbol}&type=D",
                BSE_HDR, timeout=8)
            if r:
                results = r.json()
                items = results if isinstance(results, list) else results.get('Table', [])
                for item in items:
                    sym = (item.get('NSESYMBOL') or item.get('nsesymbol') or '').upper()
                    if sym == base_symbol:
                        bse_code = str(item.get('SCRIP_CD') or item.get('scripcode') or '')
                        print(f"  BSE code (Search): {bse_code}")
                        break
        except Exception as e:
            print(f"  BSE Search error: {e}")

    print(f"  BSE code for {base_symbol}: '{bse_code}'")

    # ── BSE filings helper ────────────────────────────────────────────────────
    def bse_filings(category):
        if not bse_code:
            print(f"  No BSE code — skipping: {category}")
            return []
        docs = []
        try:
            from urllib.parse import quote as _uq
            params = (f"strCat={_uq(category)}&strPrevDate=&strScrip={bse_code}"
                      f"&strSearch=P&strToDate=&strType=C")
            url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?{params}"
            r = safe_get(url, BSE_HDR, timeout=15)
            if not r:
                return []
            try:
                payload = r.json()
            except Exception:
                print(f"  BSE non-JSON for {category}")
                return []
            items = payload if isinstance(payload, list) else \
                    payload.get('Table', payload.get('Data', []))
            print(f"  BSE '{category}': {len(items)} items")
            for item in items:
                att     = (item.get('ATTACHMENTNAME') or item.get('Filename') or '').strip()
                news_id = str(item.get('NEWSID') or item.get('NewsId') or '').strip()
                title   = (item.get('HEADLINE') or item.get('NEWSSUB') or
                           item.get('News_Sub') or '').strip()
                date    = (item.get('NEWS_DT') or item.get('DT_TM') or '').strip()[:10]

                # Smart folder selection based on filing age
                dt = parse_date(date) if date else None
                if dt:
                    import datetime
                    days_ago = (datetime.datetime.now() - dt).days
                    folder = 'AttachLive' if days_ago <= 30 else 'AttachHis'
                else:
                    folder = 'AttachHis'  # default to historical if no date

                # Build URLs - newsid page is always reliable
                if news_id:
                    pdf_url = f"https://www.bseindia.com/corporates/ann.html?newsid={news_id}"
                    alt_urls = [f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{att}"] if att else []
                elif att:
                    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{att}"
                    alt_urls = []
                else:
                    continue

                docs.append({
                    'title':    title,
                    'url':      pdf_url,
                    'alt_urls': alt_urls if news_id else [],
                    'date':     date,
                    'source':   'BSE',
                    'news_id':  news_id,
                    'att':      att,
                })
        except Exception as e:
            print(f"  BSE filings error: {e}")
        return docs

    # ── Shared NSE session (get cookies once) ────────────────────────────────
    _nse_session = None
    def get_nse_session():
        nonlocal _nse_session
        if _nse_session:
            return _nse_session
        sess = req.Session()
        try:
            sess.get('https://www.nseindia.com', headers=HTML_HDR,
                     timeout=12, proxies=proxies)
            print(f"  NSE session cookies: {list(sess.cookies.keys())}")
        except Exception as e:
            print(f"  NSE session error: {e}")
        _nse_session = sess
        return sess

    def nse_get(path):
        """
        Try both URL formats NSE uses:
          1. ?symbol=IEX                    (newer format you confirmed)
          2. ?index=equities&symbol=IEX     (older format)
        Returns parsed JSON list or None.
        """
        sess = get_nse_session()
        urls = [
            f"https://www.nseindia.com/api/{path}?symbol={base_symbol}",
            f"https://www.nseindia.com/api/{path}?index=equities&symbol={base_symbol}",
        ]
        for url in urls:
            try:
                r = sess.get(url, headers=NSE_HDR, timeout=12, proxies=proxies)
                print(f"  NSE {url[-60:]} → {r.status_code}")
                if r.ok:
                    data = r.json()
                    # Unwrap if dict
                    if isinstance(data, dict):
                        data = (data.get('data') or data.get('Table') or
                                data.get('announcements') or [])
                    if isinstance(data, list):
                        print(f"  NSE returned {len(data)} items")
                        return data
            except Exception as e:
                print(f"  NSE GET error {url[-50:]}: {e}")
        return None

    # ── NSE annual reports dedicated API ─────────────────────────────────────
    def nse_annual_reports():
        docs = []
        items = nse_get('annual-reports')
        if not items:
            return docs
        for item in items:
            att   = (item.get('fileName') or item.get('attchmntFile') or
                     item.get('attachment') or '').strip()
            date  = (item.get('date') or item.get('an_dt') or '').strip()[:10]
            title = (item.get('name') or item.get('desc') or
                     f"Annual Report {date[:4]}").strip()
            if att:
                pdf_url = att if att.startswith('http') \
                          else f"https://nsearchives.nseindia.com/corporate/{att}"
                docs.append({'title': title, 'url': pdf_url,
                             'date': date, 'source': 'NSE'})
        return docs

    # ── NSE announcements filtered ────────────────────────────────────────────
    def nse_announcements(filter_kws):
        docs = []
        items = nse_get('corporate-announcements')
        if not items:
            return docs
        print(f"  NSE announcements total: {len(items)}")
        for item in items:
            title = (item.get('desc') or '').strip()
            att   = (item.get('attchmntFile') or '').strip()
            date  = (item.get('an_dt') or '').strip()[:10]
            if not att:
                continue
            if any(kw in title.lower() for kw in filter_kws):
                pdf_url = att if att.startswith('http') \
                          else f"https://nsearchives.nseindia.com/corporate/{att}"
                docs.append({'title': title, 'url': pdf_url,
                             'date': date, 'source': 'NSE'})
        print(f"  NSE filtered to {len(docs)} matching docs")
        return docs

    # ── Year matcher (Indian FY) ──────────────────────────────────────────────
    # Indian FY: "Annual Report 2024-25" covers Apr 2024 - Mar 2025 → year=2025
    # Patterns for year=2025: "2024-25", "24-25", "fy25", "fy2025"
    # STRICT: never guess — return None if no clear match, show full list to user
    def best_year(docs, yr):
        if not docs:
            return None

        yr_str  = str(yr)           # "2025"
        yr_s    = yr_str[-2:]       # "25"
        prev    = str(int(yr) - 1)  # "2024"
        prev_s  = prev[-2:]         # "24"

        # Most specific to least specific — search title and date only, NOT url
        # (URL paths often contain arbitrary years)
        patterns = [
            (f"{prev}-{yr_s}",   10),   # 2024-25
            (f"{prev}-{yr_str}", 10),   # 2024-2025
            (f"{prev_s}-{yr_s}", 9),    # 24-25
            (f"fy{yr_s}",        8),    # fy25
            (f"fy {yr_s}",       8),    # fy 25
            (f"fy{yr_str}",      7),    # fy2025
        ]

        scored = []
        for doc in docs:
            # Only search title and date — not URL (too noisy)
            t = (doc['title'] + ' ' + doc['date']).lower()
            best_s = 0
            for pat, pts in patterns:
                if pat in t:
                    best_s = max(best_s, pts)
            # Loose fallback: 4-digit year in title
            if not best_s and yr_str in doc['title']:
                best_s = 3
            if not best_s and yr_str in doc['date']:
                best_s = 2
            scored.append((best_s, doc))
            print(f"    yr_score={best_s:2d} [{doc['date']}] {doc['title'][:70]}")

        scored.sort(key=lambda x: -x[0])
        best_score, best_doc = scored[0]
        print(f"  Year '{yr}': best score={best_score} → {best_doc['title'][:60]}")

        if best_score >= 2:
            return best_doc
        print(f"  No confident year match for {yr}")
        return None

    # ── Quarter scorer (Indian FY) ────────────────────────────────────────────
    # Q3FY26 = Oct-Dec 2025 quarter (Indian FY starts April)
    # Results are filed Jan-Mar 2026, so filing date is in 2026
    # Title patterns: "Q3FY26", "Q3 FY26", "October-December 2025", "Dec 2025 Quarter"
    def best_quarter(docs, qtr):
        if not docs:
            return None

        q        = qtr.upper()               # Q3FY26
        qn       = q[:2]                     # Q3
        qn_lo    = qn.lower()                # q3
        fy       = q[2:].replace('FY', '')   # 26
        fy_full  = '20' + fy                 # 2026
        cal_yr   = str(int(fy_full) - 1)     # 2025 (calendar year of Q3 end for Q3FY26)

        # Calendar months that fall in each quarter (Indian FY)
        q_cal_months = {
            'Q1': ['april', 'may', 'june'],
            'Q2': ['july', 'august', 'september'],
            'Q3': ['october', 'november', 'december'],
            'Q4': ['january', 'february', 'march'],
        }
        months = q_cal_months.get(qn, [])

        scored = []
        for doc in docs:
            t = (doc['title'] + ' ' + doc['date']).lower()
            s = 0

            # Exact combined pattern — highest confidence
            for combo in [f"{qn_lo}fy{fy}", f"{qn_lo} fy{fy}",
                          f"{qn_lo}fy {fy}", f"{qn_lo}-fy{fy}"]:
                if combo in t:
                    s += 10
                    break

            # Quarter number alone
            if f" {qn_lo} " in f" {t} ":     s += 5
            elif f"{qn_lo}" in t:            s += 3

            # FY year — must be the right FY
            if f"fy{fy}" in t or f"fy {fy}" in t:  s += 6
            elif fy_full in t:                       s += 5
            # Calendar year of quarter (e.g. Dec 2025 for Q3FY26)
            elif cal_yr in t:                        s += 3

            # Month name match (only if in right quarter)
            if any(m in t for m in months):          s += 3

            scored.append((s, doc))
            print(f"    q_score={s:2d} [{doc['date']}] {doc['title'][:70]}")

        scored.sort(key=lambda x: -x[0])
        best_score, best_doc = scored[0]
        print(f"  Quarter '{qtr}': best score={best_score} → {best_doc['title'][:60]}")

        if best_score >= 5:
            return best_doc
        print(f"  Low confidence ({best_score}) for {qtr} — returning None")
        return None

    def list_docs(docs, n=8):
        return '\n'.join(
            f"  [{d['date']}] ({d['source']}) {d['title'][:80]}"
            for d in docs[:n])

    # ── Main logic ────────────────────────────────────────────────────────────
    try:
        if source_type == 'annual':
            print(f"\n[Annual Report {year} – {base_symbol}]")
            all_docs  = bse_filings('Annual Report')
            if not all_docs:
                all_docs = nse_annual_reports()
            if not all_docs:
                all_docs = nse_announcements(
                    ['annual report', 'annual-report', 'integrated annual'])
            print(f"  Total: {len(all_docs)}")

            matched = best_year(all_docs, year)
            if matched:
                source_url = matched['url']
                extracted_text = (
                    f"[Annual Report {year} – {base_symbol}]\n"
                    f"Title:  {matched['title']}\n"
                    f"Date:   {matched['date']}\n"
                    f"Source: {matched['source']}\n"
                    f"URL:    {matched['url']}\n\n"
                    f"All annual reports found ({len(all_docs)}):\n"
                    + list_docs(all_docs))
            else:
                # No confident match — show ALL available reports so user can identify correct one
                fallback = (f"https://www.bseindia.com/corporates/ann.html?scripcd={bse_code}"
                            if bse_code else
                            f"https://www.nseindia.com/companies-listing/corporate-filings-annual-reports?symbol={base_symbol}")
                source_url = all_docs[0]['url'] if all_docs else fallback
                extracted_text = (
                    f"[Annual Report {year} – {base_symbol}]\n"
                    f"⚠ Could not confidently identify Annual Report for {year}.\n"
                    f"BSE code: {bse_code or 'not resolved'}\n\n"
                    + (f"All {len(all_docs)} reports found — please identify the correct one:\n"
                       + list_docs(all_docs, n=10)
                       if all_docs else
                       f"No reports found. Check manually:\n{fallback}"))

        elif source_type == 'transcript':
            print(f"\n[Concall {quarter} – {base_symbol}]")
            all_docs = bse_filings(
                'Analysts/Institutional Investor Meet/Con. Call Updates')
            if not all_docs:
                all_docs = bse_filings('Analysts/Institutional Investor Meet')
            if not all_docs:
                all_docs = nse_announcements([
                    'concall','con call','conference call','earnings call',
                    'analyst meet','institutional investor','transcript',
                    'investor meet','con-call','earnings transcript'])
            print(f"  Total: {len(all_docs)}")

            matched = best_quarter(all_docs, quarter)
            if matched:
                source_url = matched['url']
                extracted_text = (
                    f"[{quarter} Concall – {base_symbol}]\n"
                    f"Title:  {matched['title']}\n"
                    f"Date:   {matched['date']}\n"
                    f"Source: {matched['source']}\n"
                    f"URL:    {matched['url']}\n\n"
                    f"All concall docs ({len(all_docs)}):\n"
                    + list_docs(all_docs))
            else:
                fallback = (f"https://www.bseindia.com/corporates/ann.html?scripcd={bse_code}"
                            if bse_code else
                            f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={base_symbol}")
                source_url = all_docs[0]['url'] if all_docs else fallback
                extracted_text = (
                    f"[{quarter} Concall – {base_symbol}]\n"
                    f"⚠ Could not confidently identify concall for {quarter}.\n\n"
                    + (f"All {len(all_docs)} concall docs found — please identify the correct one:\n"
                       + list_docs(all_docs, n=10)
                       if all_docs else
                       f"No concall docs found. Check manually:\n{fallback}"))

        elif source_type == 'presentation':
            print(f"\n[Presentation – {base_symbol}]")
            all_docs = bse_filings('Investor Presentation')
            if not all_docs:
                all_docs = nse_announcements([
                    'investor presentation','presentation','corporate presentation',
                    'analyst day','investor day'])
            print(f"  Total: {len(all_docs)}")

            if all_docs:
                source_url = all_docs[0]['url']
                extracted_text = (
                    f"[Investor Presentations – {base_symbol}]\n"
                    f"Latest: {all_docs[0]['title']}\n"
                    f"Date:   {all_docs[0]['date']}\n"
                    f"Source: {all_docs[0]['source']}\n"
                    f"URL:    {all_docs[0]['url']}\n\n"
                    f"All ({len(all_docs)}):\n"
                    + list_docs(all_docs))
            else:
                source_url = (
                    f"https://www.bseindia.com/corporates/ann.html?scripcd={bse_code}"
                    if bse_code else
                    f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={base_symbol}")
                extracted_text = (
                    f"[Investor Presentation – {base_symbol}]\n"
                    f"No presentations found.\nCheck: {source_url}")

        print(f"  Result: {len(all_docs)} docs, url={source_url[:80]}")
        return jsonify({
            'text':       extracted_text,
            'source_url': source_url,
            'all_docs':   [{'title':d['title'],'url':d['url'],
                            'alt_urls': d.get('alt_urls',[]),
                            'date':d['date'],'source':d.get('source','')}
                           for d in all_docs[:10]],
            'chars':      len(extracted_text),
        })

    except Exception as e:
        print(f"  deepdive error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'text':'','source_url':'','all_docs':[],'error':str(e)})


@app.route('/api/deepdive/alldocs', methods=['POST'])
def deepdive_alldocs():
    """
    Fetch ALL annual reports, concalls, and presentations in ONE call.
    Returns structured dict so frontend can assign one doc per year/quarter slot.
    This avoids re-fetching the same list 10 times.
    """
    try:
        data        = request.get_json() or {}
        base_symbol = data.get('base_symbol', '').upper().strip()
        company     = data.get('company', '').strip()
        proxy_host  = data.get('proxy_host', '').strip()
        proxy_port  = data.get('proxy_port', '').strip()
        proxies     = make_proxies(proxy_host, proxy_port)

        HTML_HDR = {
            'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept':          'text/html,application/xhtml+xml,*/*;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        JSON_HDR = {**HTML_HDR, 'Accept': 'application/json, text/plain, */*'}
        BSE_HDR  = {
            **JSON_HDR,
            'Origin':         'https://www.bseindia.com',
            'Referer':        'https://www.bseindia.com/',
            'sec-fetch-site': 'same-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
        }
        NSE_HDR  = {**JSON_HDR, 'Referer': 'https://www.nseindia.com/'}

        def safe_get(url, hdrs, timeout=12):
            try:
                r = req.get(url, headers=hdrs, timeout=timeout, proxies=proxies, allow_redirects=True)
                if r.ok: return r
                print(f"  HTTP {r.status_code}: {url[:70]}")
            except Exception as e:
                print(f"  FAIL {url[:70]}: {e}")
            return None

        # ── Get BSE code ──────────────────────────────────────────────────────
        bse_code = ''
        try:
            from bse import BSE as BsePkg
            import tempfile
            with BsePkg(download_folder=tempfile.gettempdir()) as bpkg:
                result = bpkg.lookup(base_symbol)
                if result and result.get('bse_code'):
                    bse_code = str(result['bse_code'])
                    print(f"  BSE code: {bse_code}")
        except Exception as e:
            print(f"  BSE pkg: {e}")

        if not bse_code:
            try:
                r = safe_get(
                    f"https://api.bseindia.com/BseIndiaAPI/api/fetchComp/w"
                    f"?companySortOrder=A&industry=&issuerType=C&turnover=&companyType="
                    f"&mktcap=&segment=&status=Active&indexType=&pageno=1&pagesize=25&search={base_symbol}",
                    BSE_HDR, timeout=8)
                if r:
                    for item in r.json().get('Table', []):
                        if (item.get('nsesymbol') or item.get('NSESymbol','') ).upper() == base_symbol:
                            bse_code = str(item.get('scripcode') or item.get('Scripcode',''))
                            break
            except Exception as e:
                print(f"  BSE fetchComp: {e}")

        print(f"  BSE code: '{bse_code}'")

        # ── Fetch from BSE ────────────────────────────────────────────────────
        def bse_fetch(category):
            if not bse_code:
                print(f"  BSE '{category}': skipped (no bse_code)")
                return []
            docs = []
            try:
                from urllib.parse import quote as url_quote
                import datetime
                params = (f"strCat={url_quote(category)}&strPrevDate=&strScrip={bse_code}"
                          f"&strSearch=P&strToDate=&strType=C")
                url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?{params}"
                print(f"  BSE URL: {url[:120]}...")
                r = safe_get(url, BSE_HDR, timeout=15)
                if not r:
                    print(f"  BSE '{category}': safe_get returned None")
                    return []
                print(f"  BSE response status: {r.status_code}, length: {len(r.text)}")
                try:
                    payload = r.json()
                except Exception as je:
                    print(f"  BSE JSON parse error: {je}")
                    print(f"  BSE response text: {r.text[:200]}")
                    return []
                items = payload if isinstance(payload, list) else \
                        payload.get('Table', payload.get('Data', []))
                print(f"  BSE '{category}': {len(items)} items")
                if len(items) == 0:
                    print(f"  BSE empty response: {payload}")
                for item in items:
                    att     = (item.get('ATTACHMENTNAME') or item.get('Filename') or '').strip()
                    news_id = str(item.get('NEWSID') or item.get('NewsId') or '').strip()
                    title   = (item.get('HEADLINE') or item.get('NEWSSUB') or item.get('News_Sub') or '').strip()
                    date    = (item.get('NEWS_DT') or item.get('DT_TM') or '').strip()[:10]

                    # Smart folder selection: AttachLive for recent, AttachHis for older
                    dt = parse_date(date) if date else None
                    days_ago = (datetime.datetime.now() - dt).days if dt else 999
                    folder = 'AttachLive' if days_ago <= 30 else 'AttachHis'

                    if news_id:
                        url = f"https://www.bseindia.com/corporates/ann.html?newsid={news_id}"
                        alt = [f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{att}"]
                    elif att:
                        url = f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{att}"
                        alt = []
                    else:
                        continue
                    docs.append({'title': title, 'url': url, 'alt_urls': alt,
                                 'date': date, 'source': 'BSE'})
            except Exception as e:
                print(f"  BSE fetch error: {e}")
            return docs

        # ── NSE session (shared) ──────────────────────────────────────────────
        nse_sess = req.Session()
        try:
            nse_sess.get('https://www.nseindia.com', headers=HTML_HDR, timeout=10, proxies=proxies)
        except: pass

        def nse_fetch(path, filter_kws=None):
            docs = []
            for url in [
                f"https://www.nseindia.com/api/{path}?symbol={base_symbol}",
                f"https://www.nseindia.com/api/{path}?index=equities&symbol={base_symbol}",
            ]:
                try:
                    r = nse_sess.get(url, headers=NSE_HDR, timeout=12, proxies=proxies)
                    print(f"  NSE {url[-55:]} → {r.status_code}")
                    if r.ok:
                        data = r.json()
                        if isinstance(data, dict):
                            data = data.get('data') or data.get('Table') or []
                        if not isinstance(data, list) or not data:
                            continue
                        print(f"  NSE {path}: {len(data)} items")
                        if data and len(data) > 0:
                            print(f"  NSE first item keys: {list(data[0].keys())}")
                        for item in data:
                            att   = (item.get('fileName') or item.get('attchmntFile') or
                                     item.get('attachment') or '').strip()
                            
                            # NSE annual-reports uses different field names than corporate-announcements
                            if 'fromYr' in item and 'toYr' in item:
                                # annual-reports API format
                                from_yr = str(item.get('fromYr', ''))
                                to_yr   = str(item.get('toYr', ''))
                                title   = f"Annual Report {from_yr}-{to_yr[-2:]}" if from_yr and to_yr else \
                                          (item.get('companyName', '') or 'Annual Report')
                                # disseminationDateTime format: "04-JUL-2025 12:00:00" or timestamp
                                raw_dt = (item.get('disseminationDateTime', '') or 
                                         item.get('broadcast_dttm', ''))
                                # Extract just the date part (first 11 chars: "04-JUL-2025")
                                date = raw_dt[:11].strip() if raw_dt else ''
                                # Convert to sortable format if possible
                                if date and '-' in date:
                                    try:
                                        import datetime as dt_mod
                                        parsed = dt_mod.datetime.strptime(date, '%d-%b-%Y')
                                        date = parsed.strftime('%Y-%m-%d')  # YYYY-MM-DD for sorting
                                    except:
                                        pass  # keep original format
                            else:
                                # corporate-announcements API format
                                title = (item.get('desc') or item.get('name') or '').strip()
                                raw_dt = (item.get('an_dt') or item.get('date') or '').strip()
                                # an_dt format: "16-Nov-2024" or "13-Feb-2026"
                                # Convert to YYYY-MM-DD for consistency
                                if raw_dt and '-' in raw_dt:
                                    try:
                                        import datetime as dt_mod
                                        parsed = dt_mod.datetime.strptime(raw_dt, '%d-%b-%Y')
                                        date = parsed.strftime('%Y-%m-%d')
                                    except:
                                        date = raw_dt[:10]  # fallback
                                else:
                                    date = raw_dt[:10]
                            
                            if not att: continue
                            if filter_kws and not any(k in title.lower() for k in filter_kws):
                                continue
                            pdf_url = att if att.startswith('http') \
                                      else f"https://nsearchives.nseindia.com/corporate/{att}"
                            docs.append({'title': title, 'url': pdf_url, 'alt_urls': [],
                                         'date': date, 'source': 'NSE'})
                        if docs: break
                except Exception as e:
                    print(f"  NSE error: {e}")
            return docs

        # ── Fetch all categories ──────────────────────────────────────────────
        print(f"\n[alldocs] {base_symbol}")

        annual_docs = bse_fetch('Annual Report')
        if not annual_docs:
            annual_docs = nse_fetch('annual-reports')
            # Debug: show all items before sorting
            print(f"  Before sort: {len(annual_docs)} items")
            for d in annual_docs[:5]:
                print(f"    date={d.get('date','NO_DATE')!r} title={d['title'][:50]}")
            # Sort by year extracted from title (more reliable than date field)
            def extract_year(doc):
                title = doc['title']
                # Extract "YYYY-YY" or "YYYY" from title
                import re
                match = re.search(r'(\d{4})-(\d{2,4})', title)
                if match:
                    return int(match.group(1))  # return first year (2024 from "2024-25")
                match = re.search(r'(\d{4})', title)
                if match:
                    return int(match.group(1))
                return 0
            annual_docs = sorted(annual_docs, key=extract_year, reverse=True)[:4]  # Get 4 years
            print(f"  After sort (top 4):")
            for d in annual_docs:
                # Extract just "Financial Year YYYY" from title
                title = d['title']
                year_match = re.search(r'(\d{4})', title)
                if year_match:
                    d['clean_title'] = f"Financial Year {year_match.group(1)}"
                else:
                    d['clean_title'] = title
                print(f"    [{d.get('date','')}] {d['clean_title']}")
        if not annual_docs:
            annual_docs = nse_fetch('corporate-announcements',
                                    filter_kws=['annual report','annual-report','integrated annual'])
        print(f"  Annual reports: {len(annual_docs)}")
        for d in annual_docs:
            print(f"    [{d['date']}] {d['title'][:70]}")

        concall_docs = bse_fetch('Analysts/Institutional Investor Meet/Con. Call Updates')
        if not concall_docs:
            concall_docs = bse_fetch('Analysts/Institutional Investor Meet')
        if not concall_docs:
            # Get all concall-related announcements from NSE
            all_concalls = nse_fetch('corporate-announcements', filter_kws=[
                'concall','con call','conference call','earnings call',
                'analyst meet','transcript','investor meet','con-call'])
            # Transcripts only — strictly filter by "transcript" in title
            transcripts = [d for d in all_concalls if 'transcript' in d['title'].lower()]

            # Extract quarter from date for transcripts
            import datetime, re
            for doc in transcripts:
                dt_str = doc.get('date', '')
                if dt_str:
                    try:
                        dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
                        # Indian FY: Apr-Jun=Q1, Jul-Sep=Q2, Oct-Dec=Q3, Jan-Mar=Q4
                        month = dt.month
                        year = dt.year
                        if month >= 4:  # Apr onwards = current FY
                            fy_year = year + 1
                        else:  # Jan-Mar = previous FY
                            fy_year = year
                        if month in [4,5,6]:
                            quarter = 'Q1'
                        elif month in [7,8,9]:
                            quarter = 'Q2'
                        elif month in [10,11,12]:
                            quarter = 'Q3'
                        else:
                            quarter = 'Q4'
                        doc['quarter'] = f"{quarter}FY{str(fy_year)[-2:]}"
                    except:
                        pass
            
            # Transcripts only
            concall_docs = transcripts[:8]  # Get 8 quarters (2 years)

        # Deduplicate by URL only — remove exact duplicate documents
        seen_urls, deduped_concalls = set(), []
        for d in concall_docs:
            url = d.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                # Improve quarter format: "Q1 FY25" -> "Q1 2025"
                quarter = d.get('quarter', '')
                if quarter and 'FY' in quarter:
                    import re
                    match = re.search(r'Q(\d)\s+FY(\d{2})', quarter)
                    if match:
                        q_num = match.group(1)
                        fy_short = match.group(2)
                        year = f"20{fy_short}"
                        d['quarter'] = f"Q{q_num} {year}"
                deduped_concalls.append(d)
        concall_docs = deduped_concalls
        print(f"  Concall docs: {len(concall_docs)}")
        for d in concall_docs:
            qtr = d.get('quarter', '')
            print(f"    [{d['date']}] {qtr:8s} {d['title'][:60]}")

        pres_docs = bse_fetch('Investor Presentation')
        if not pres_docs:
            pres_docs = nse_fetch('corporate-announcements', filter_kws=[
                'investor presentation','presentation','corporate presentation'])
        print(f"  Presentations: {len(pres_docs)}")

        def to_list(docs):
            return [{'title': d.get('clean_title', d['title']),  # Use clean_title if available
                     'url': d['url'], 
                     'alt_urls': d.get('alt_urls', []),
                     'date': d['date'], 
                     'source': d['source'],
                     'quarter': d.get('quarter', '')}  # Add quarter for concalls
                    for d in docs]

        result = {
            'annual':       to_list(annual_docs),
            'concall':      to_list(concall_docs),
            'presentation': to_list(pres_docs),
            'bse_code':     bse_code,
        }
        
        print(f"\n[alldocs response]")
        print(f"  annual: {len(result['annual'])} items")
        print(f"  concall: {len(result['concall'])} items") 
        print(f"  presentation: {len(result['presentation'])} items")
        
        return jsonify(result)

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'annual':[], 'concall':[], 'presentation':[], 'error':str(e)})



def deepdive_ask():
    """Send question + context to Claude API and return answer"""
    data       = request.get_json() or {}
    system_msg = data.get('system', '')
    messages   = data.get('messages', [])
    proxy_host = data.get('proxy_host', '').strip()
    proxy_port = data.get('proxy_port', '').strip()

    proxies = make_proxies(proxy_host, proxy_port)

    try:
        claude_headers = {
            'Content-Type':      'application/json',
            'anthropic-version': '2023-06-01',
            'x-api-key':         os.environ.get('ANTHROPIC_API_KEY', ''),
        }

        # Truncate messages to avoid token limits
        trimmed_messages = messages[-10:] if len(messages) > 10 else messages

        payload = {
            'model':      'claude-sonnet-4-5-20250929',
            'max_tokens': 2048,
            'system':     system_msg[:90000],   # cap context
            'messages':   trimmed_messages,
        }

        resp = req.post(
            'https://api.anthropic.com/v1/messages',
            headers=claude_headers,
            json=payload,
            timeout=60,
            proxies=proxies
        )

        if resp.ok:
            result = resp.json()
            answer = result['content'][0]['text']
            return jsonify({'answer': answer})
        else:
            print(f"  Claude API error: {resp.status_code} {resp.text[:300]}")
            return jsonify({'error': resp.text, 'answer': f'API error {resp.status_code}: {resp.text[:200]}'}), 500

    except Exception as e:
        print(f"  deepdive ask error: {e}")
        return jsonify({'error': str(e), 'answer': f'Error: {str(e)}'}), 500


@app.route('/api/deepdive/screener', methods=['POST'])
def deepdive_screener():
    """
    Fetch Deep Dive documents from screener.in (primary) + BSE (fallback).
    Screener.in structure:
      - Annual reports: main page id="annual-reports" section
      - Concall transcripts: main page id="documents" section  (NOT /documents/ — that 404s)
      - Also try: screener.in/api/company/?q=SYMBOL for JSON data
    BSE fallback uses multiple category strings for concalls.
    """
    import re as _re
    import datetime as _dt

    try:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'beautifulsoup4',
                                   '--break-system-packages', '-q'])
            from bs4 import BeautifulSoup

        data        = request.get_json() or {}
        base_symbol = data.get('base_symbol', '').upper().strip()
        company     = data.get('company', '').strip()
        proxy_host  = data.get('proxy_host', '').strip()
        proxy_port  = data.get('proxy_port', '').strip()

        if not base_symbol:
            return jsonify({'error': 'No symbol provided'}), 400

        proxies = make_proxies(proxy_host, proxy_port)

        SCREENER_HDR = {
            'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer':         'https://www.screener.in/',
        }
        SCREENER_API_HDR = {
            **SCREENER_HDR,
            'Accept':  'application/json, text/plain, */*',
            'X-Requested-With': 'XMLHttpRequest',
        }

        print(f"\n[Screener Deep Dive] {base_symbol}")

        screener_url = f"https://www.screener.in/company/{base_symbol}/"
        annual_reports = []
        concalls       = []

        # ══════════════════════════════════════════════════════════════════════
        # STEP 1: Scrape screener.in main company page
        # The page has:
        #   id="annual-reports" → annual report PDFs
        #   id="documents"      → concall transcripts, investor presentations
        # ══════════════════════════════════════════════════════════════════════
        soup = None
        screener_docs_json = []
        try:
            r = req.get(screener_url, headers=SCREENER_HDR, timeout=20, proxies=proxies)
            print(f"  Screener main page: HTTP {r.status_code}, {len(r.content)} bytes")
            if r.ok:
                soup = BeautifulSoup(r.text, 'html.parser')
        except Exception as e:
            print(f"  Screener main page error: {e}")

        # Fetch Screener documents API — returns JSON with type labels including "Investor Presentation"
        try:
            docs_api_url = f"https://www.screener.in/api/company/{base_symbol}/documents/"
            rd = req.get(docs_api_url, headers=SCREENER_API_HDR, timeout=15, proxies=proxies)
            print(f"  Screener docs API: HTTP {rd.status_code}")
            if rd.ok:
                screener_docs_json = rd.json() if isinstance(rd.json(), list) else rd.json().get('documents', rd.json().get('results', []))
                print(f"  Screener docs API: {len(screener_docs_json)} items")
                for d in screener_docs_json[:5]:
                    print(f"    type={d.get('type','?')} title={str(d.get('title',''))[:50]}")
        except Exception as e:
            print(f"  Screener docs API error: {e}")

        def make_absolute(href):
            if not href:
                return ''
            if href.startswith('http'):
                return href
            if href.startswith('/'):
                return 'https://www.screener.in' + href
            return href

        def quarter_from_title(title):
            """Extract quarter label like Q3FY26 from a document title."""
            q_m  = _re.search(r'Q([1-4])', title, _re.IGNORECASE)
            fy_m = _re.search(r'FY\s*(\d{2,4})', title, _re.IGNORECASE)
            yr_m = _re.search(r'(\d{4})', title)
            if q_m and fy_m:
                fy = fy_m.group(1)
                if len(fy) == 4: fy = fy[-2:]
                return f"Q{q_m.group(1)}FY{fy}"
            if q_m and yr_m:
                yr = yr_m.group(1)
                return f"Q{q_m.group(1)}FY{yr[-2:]}"
            return ''  # let date-based quarter assignment handle it

        if soup:
            # ── Annual Reports section ────────────────────────────────────────
            # Screener uses id="annual-reports" with <li> items containing <a> links
            ar_sec = soup.find(id='annual-reports')
            if not ar_sec:
                # fallback: look for heading
                for h in soup.find_all(['h2','h3','h4','h5']):
                    if 'annual report' in h.get_text(strip=True).lower():
                        ar_sec = h.find_parent(['section','div','ul'])
                        break
            if ar_sec:
                for a in ar_sec.find_all('a', href=True):
                    href  = make_absolute(a['href'])
                    title = a.get_text(strip=True)
                    if not href or not title:
                        continue
                    # Skip navigation links
                    if href.endswith('/') and 'screener.in/company' in href:
                        continue
                    yr_m = _re.search(r'(\d{4})', title)
                    year = yr_m.group(1) if yr_m else ''
                    annual_reports.append({
                        'title':  title,
                        'url':    href,
                        'year':   year,
                        'date':   year,
                        'source': 'Screener',
                    })
                annual_reports = annual_reports[:3]
                print(f"  Annual reports (id=annual-reports): {len(annual_reports)}")
                for d in annual_reports:
                    print(f"    [{d['year']}] {d['title'][:60]} → {d['url'][:80]}")

            # ── Documents/Concalls section ────────────────────────────────────
            # Screener uses id="documents" on the SAME main page for concalls
            # Each item has a type badge (e.g. "Concall", "Annual Report") and a link
            docs_sec = soup.find(id='documents')
            if not docs_sec:
                # Try alternate IDs screener has used
                for alt_id in ['concalls', 'investor-presentations', 'transcripts']:
                    docs_sec = soup.find(id=alt_id)
                    if docs_sec:
                        break
            if not docs_sec:
                # Heading-based fallback
                for h in soup.find_all(['h2','h3','h4','h5']):
                    txt = h.get_text(strip=True).lower()
                    if any(kw in txt for kw in ['document', 'concall', 'transcript', 'earnings']):
                        docs_sec = h.find_parent(['section','div'])
                        break

            screener_presentations = []  # populated from #documents section

            # ── Try Screener docs API first (has explicit type labels) ────────
            if screener_docs_json:
                PRES_TYPES = ['investor presentation', 'corporate presentation',
                              'analyst presentation', 'earnings presentation',
                              'investor day', 'analyst meet']
                for doc in screener_docs_json:
                    doc_type  = str(doc.get('type', '') or doc.get('category', '') or '').lower()
                    doc_title = str(doc.get('title', '') or doc.get('name', '') or '').strip()
                    doc_url   = str(doc.get('url', '') or doc.get('attachment', '') or '').strip()
                    doc_date  = str(doc.get('date', '') or '')[:10]
                    if not doc_url:
                        continue
                    if any(kw in doc_type for kw in PRES_TYPES) or \
                       any(kw in doc_title.lower() for kw in PRES_TYPES):
                        if not doc_url.startswith('http'):
                            doc_url = 'https://www.screener.in' + doc_url
                        screener_presentations.append({
                            'title':  doc_title if doc_title else 'Investor Presentation',
                            'url':    doc_url,
                            'date':   doc_date,
                            'source': 'Screener',
                        })
                        print(f"  Presentation from Screener API: {doc_title[:60]}")
                        break

            if docs_sec:
                print(f"  Found documents section (id={docs_sec.get('id','?')})")
                CONCALL_KWS = ['transcript', 'earnings transcript']
                PRES_KWS_SCREENER = ['investor presentation', 'corporate presentation',
                                     'investor relations presentation', 'analyst presentation',
                                     'earnings presentation', 'results presentation',
                                     'investor day', 'analyst day', 'analyst meet presentation']

                all_links = docs_sec.find_all('a', href=True)

                # ── Pass 1: concall transcripts ───────────────────────────────
                for a in all_links:
                    href  = make_absolute(a['href'])
                    title = a.get_text(strip=True)
                    if not href or not title:
                        continue
                    if href.endswith('/') and 'screener.in/company' in href:
                        continue
                    # Only match on title/href — not parent text, to avoid false positives
                    text_lo = (title + ' ' + href).lower()
                    if any(kw in text_lo for kw in CONCALL_KWS) and 'recording' not in text_lo:
                        # Try parent for date/quarter context only
                        parent_text = ''
                        for par in [a.parent, a.parent.parent if a.parent else None]:
                            if par:
                                parent_text = par.get_text(separator=' ', strip=True)
                                break
                        date_m   = _re.search(r'(\w+ \d{4}|\d{2}[-/]\d{2}[-/]\d{4}|\d{4}-\d{2}-\d{2})', parent_text)
                        yr_m     = _re.search(r'(\d{4})', parent_text)
                        quarter  = quarter_from_title(parent_text) or quarter_from_title(title)
                        date_str = date_m.group(1) if date_m else (yr_m.group(1) if yr_m else '')
                        concalls.append({
                            'title':   title,
                            'url':     href,
                            'quarter': quarter,
                            'date':    date_str,
                            'source':  'Screener',
                        })
                        if len(concalls) >= 5:
                            break

                # ── Pass 2: investor presentation (first match only) ───────────
                # Screener shows document type as a badge in the parent <li>
                # e.g. "Investor Presentation", "Corporate Presentation"
                for a in all_links:
                    href  = make_absolute(a['href'])
                    title = a.get_text(strip=True)
                    if not href or not title:
                        continue
                    if href.endswith('/') and 'screener.in/company' in href:
                        continue
                    # Skip anything already identified as a transcript
                    if any(kw in (title + ' ' + href).lower() for kw in CONCALL_KWS):
                        continue
                    # Check parent badge text strictly for presentation label
                    parent_text = ''
                    for par in [a.parent, a.parent.parent if a.parent else None]:
                        if par:
                            parent_text = par.get_text(separator=' ', strip=True)
                            break
                    parent_lo = parent_text.lower()
                    if any(kw in parent_lo for kw in PRES_KWS_SCREENER):
                        yr_m = _re.search(r'(\d{4})', parent_text)
                        screener_presentations.append({
                            'title':  title if len(title) > 5 else 'Investor Presentation',
                            'url':    href,
                            'date':   yr_m.group(1) if yr_m else '',
                            'source': 'Screener',
                        })
                        break  # only need one

                print(f"  Concalls (id=documents): {len(concalls)}")
                for d in concalls:
                    print(f"    [{d['quarter']}] {d['title'][:60]}")
                print(f"  Presentations (id=documents): {len(screener_presentations)}")
                
                # ── Fallback: if no presentations found, look for PPT buttons on entire page ──
                if not screener_presentations:
                    print(f"  Scanning entire page for PPT buttons...")
                    
                    ppt_links = []
                    for a in soup.find_all('a', href=True):
                        href = make_absolute(a['href'])
                        
                        # Accept PDFs from BSE OR company websites
                        is_bse = 'bseindia.com/xml-data/corpfiling' in href
                        is_pdf = href.lower().endswith('.pdf')
                        
                        if not (is_bse or is_pdf):
                            continue
                        
                        # Get EXACT link text (the button label)
                        link_text = a.get_text(strip=True)
                        
                        # Look for links with text exactly "PPT" (case insensitive)
                        if link_text.upper().strip() == 'PPT':
                            # Get parent context for date/quarter info
                            parent = a.parent
                            context = ''
                            if parent:
                                context = parent.get_text(separator=' ', strip=True)
                            
                            print(f"    Found PPT button: {href[:100]}")
                            print(f"      Context: {context[:100]}")
                            
                            # Extract date from context (e.g., "Feb 2026", "Jan 2026")
                            date_match = _re.search(r'(\w+)\s+(\d{4})', context)
                            if date_match:
                                month_str = date_match.group(1)
                                year_str = date_match.group(2)
                                date_str = f"{month_str} {year_str}"
                                
                                # Parse to timestamp for sorting
                                try:
                                    from datetime import datetime
                                    months = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
                                             'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
                                    month_num = months.get(month_str[:3].lower(), 1)
                                    sort_ts = datetime(int(year_str), month_num, 1).timestamp()
                                    print(f"      Parsed date: {date_str} -> timestamp {sort_ts}")
                                except Exception as e:
                                    sort_ts = 0
                                    print(f"      Date parse error: {e}")
                            else:
                                date_str = ''
                                sort_ts = 0
                                print(f"      No date found in context")
                            
                            # Determine source
                            if 'bseindia.com' in href:
                                source = 'BSE'
                            else:
                                source = 'Company Website'
                            
                            ppt_links.append({
                                'title': f"Investor Presentation - {date_str}" if date_str else 'Investor Presentation',
                                'url': href,
                                'date': date_str,
                                'sort_ts': sort_ts,
                                'source': source,
                                'context': context
                            })
                    
                    if ppt_links:
                        # Sort by date descending (latest first)
                        ppt_links.sort(key=lambda x: x['sort_ts'], reverse=True)
                        
                        # Show all found AFTER sorting
                        print(f"    Found {len(ppt_links)} PPT buttons (sorted by date):")
                        for i, p in enumerate(ppt_links):
                            print(f"      [{i+1}] {p['date']} (ts:{p['sort_ts']}) [{p['source']}]")
                            print(f"          {p['url'][:100]}")
                        
                        # Take the LATEST (first after sorting)
                        pres = ppt_links[0]
                        screener_presentations.append(pres)
                        print(f"    ✓ Taking latest: {pres['title']} from {pres['source']}")
                        print(f"      URL: {pres['url']}")
                    else:
                        print(f"    No PPT buttons found")
            else:
                print(f"  No documents section found on main page")

            # ── Fallback: scan ALL links on page for concall keywords ─────────
            if not concalls:
                print(f"  Scanning all page links for concall keywords...")
                CONCALL_KWS2 = ['transcript', 'earnings transcript']
                for a in soup.find_all('a', href=True):
                    href  = make_absolute(a['href'])
                    title = a.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    if href.endswith('/') and 'screener.in' in href:
                        continue
                    text_lo = (title + ' ' + href).lower()
                    if any(kw in text_lo for kw in CONCALL_KWS2) and 'recording' not in text_lo:
                        yr_m = _re.search(r'(\d{4})', title)
                        concalls.append({
                            'title':   title,
                            'url':     href,
                            'quarter': quarter_from_title(title),
                            'date':    yr_m.group(1) if yr_m else '',
                            'source':  'Screener',
                        })
                        if len(concalls) >= 5:
                            break
                print(f"  Concalls (page-wide scan): {len(concalls)}")

        bse_code = ''  # resolved inside BSE fallback block if needed
        BSE_HDR_PRES = {
            'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept':          'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin':          'https://www.bseindia.com',
            'Referer':         'https://www.bseindia.com/',
        }

        def bse_fetch_cat_outer(category, bse_code_val, limit=25):
            """BSE category fetch - always available."""
            if not bse_code_val:
                return []
            from urllib.parse import quote as _uq2
            docs = []
            try:
                url = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
                       f"?strCat={_uq2(category)}&strPrevDate=&strScrip={bse_code_val}"
                       f"&strSearch=P&strToDate=&strType=C")
                rb = req.get(url, headers=BSE_HDR_PRES, timeout=15, proxies=proxies)
                if rb.ok:
                    payload = rb.json()
                    items = payload if isinstance(payload, list) else payload.get('Table', payload.get('Data', []))
                    for item in items[:limit]:
                        att     = (item.get('ATTACHMENTNAME') or '').strip()
                        news_id = str(item.get('NEWSID') or '').strip()
                        title   = (item.get('HEADLINE') or item.get('NEWSSUB') or '').strip()
                        date    = (item.get('NEWS_DT') or item.get('DT_TM') or '').strip()[:10]
                        if not att:
                            continue
                        # Always try AttachLive first (most recent), AttachHis as fallback
                        url2 = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{att}"
                        alt  = f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{att}"
                        docs.append({'title': title, 'url': url2, 'alt_url': alt,
                                     'date': date, 'source': 'BSE'})
            except Exception as fe:
                print(f"  BSE fetch error ({category[:30]}): {fe}")
            return docs

        # ══════════════════════════════════════════════════════════════════════
        # STEP 1b: Fetch investor presentation from BSE (only if not found on Screener)
        # ══════════════════════════════════════════════════════════════════════
        if not screener_presentations:  # Only fetch from BSE if Screener didn't have it
            _BSE_HDR = {
                'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept':          'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin':          'https://www.bseindia.com',
                'Referer':         'https://www.bseindia.com/',
                'sec-fetch-site':  'same-site',
                'sec-fetch-mode':  'cors',
                'sec-fetch-dest':  'empty',
            }
            _bse_code = bse_code  # use already-resolved code if available

            if not _bse_code:
                try:
                    from bse import BSE as BsePkg
                    import tempfile
                    with BsePkg(download_folder=tempfile.gettempdir()) as bpkg:
                        res = bpkg.lookup(base_symbol)
                        if res and res.get('bse_code'):
                            _bse_code = str(res['bse_code'])
                            print(f"  BSE code for pres: {_bse_code}")
                except Exception: pass

            if not _bse_code:
                try:
                    from urllib.parse import quote as _uqp
                    rb = req.get(
                        f"https://api.bseindia.com/BseIndiaAPI/api/fetchComp/w"
                        f"?companySortOrder=A&industry=&issuerType=C&turnover=&companyType="
                        f"&mktcap=&segment=&status=Active&indexType=&pageno=1&pagesize=25&search={base_symbol}",
                        headers=_BSE_HDR, timeout=10, proxies=proxies)
                    if rb.ok:
                        for item in rb.json().get('Table', []):
                            if (item.get('nsesymbol') or item.get('NSESymbol', '')).upper() == base_symbol:
                                _bse_code = str(item.get('scripcode') or item.get('Scripcode', ''))
                                print(f"  BSE code for pres (fetchComp): {_bse_code}")
                                break
                except Exception: pass

            if _bse_code:
                from urllib.parse import quote as _uqp2
                # Try many category variations - BSE naming is inconsistent
                categories = [
                    'Investor Presentation',
                    'Investor Relations',
                    'Investor / Analyst Presentation',
                    'Corporate Presentation',
                    'Presentation',
                    'Investor Meet',
                    'Investor / Analyst Meet',
                ]
                
                for cat in categories:
                    try:
                        pres_url = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
                                    f"?strCat={_uqp2(cat)}&strPrevDate=&strScrip={_bse_code}"
                                    f"&strSearch=P&strToDate=&strType=C")
                        rp = req.get(pres_url, headers=_BSE_HDR, timeout=15, proxies=proxies)
                        if rp.ok:
                            payload = rp.json()
                            items = payload if isinstance(payload, list) else \
                                    payload.get('Table', payload.get('Data', []))
                            print(f"  BSE cat '{cat}': {len(items)} items")
                            
                            # Filter out transcripts
                            pres_items = []
                            for item in items[:10]:
                                title = (item.get('HEADLINE') or item.get('NEWSSUB') or '').lower()
                                if 'transcript' not in title and 'concall' not in title and 'con call' not in title:
                                    pres_items.append(item)
                            
                            print(f"    After excluding transcripts: {len(pres_items)} items")
                            
                            for item in pres_items[:1]:  # Take first non-transcript
                                att   = (item.get('ATTACHMENTNAME') or '').strip()
                                title = (item.get('HEADLINE') or item.get('NEWSSUB') or '').strip()
                                date  = (item.get('NEWS_DT') or item.get('DT_TM') or '').strip()[:10]
                                
                                if att:
                                    # Determine folder (AttachLive vs AttachHis)
                                    try:
                                        from datetime import datetime
                                        dt = datetime.strptime(date, '%d/%m/%Y')
                                        days_ago = (datetime.now() - dt).days
                                        folder = 'AttachLive' if days_ago <= 30 else 'AttachHis'
                                    except:
                                        folder = 'AttachHis'
                                    
                                    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{att}"
                                    screener_presentations = [{'title': title or 'Investor Presentation',
                                                               'url': pdf_url, 'date': date, 'source': 'BSE'}]
                                    print(f"    ✓ Found: {title[:60]}")
                                    print(f"      URL: {pdf_url}")
                                    break
                            
                            if screener_presentations:
                                break
                    except Exception as pe:
                        print(f"  BSE cat '{cat}' error: {pe}")
            bse_code = _bse_code or bse_code  # propagate resolved code

        # ══════════════════════════════════════════════════════════════════════
        # STEP 2: BSE fallback for concalls (and annual if still missing)
        # Uses multiple category strings since BSE naming varies
        # ══════════════════════════════════════════════════════════════════════
        if not concalls or not annual_reports:
            print(f"  BSE fallback needed (annual={len(annual_reports)}, concall={len(concalls)})")
            BSE_HDR = {
                'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept':          'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin':          'https://www.bseindia.com',
                'Referer':         'https://www.bseindia.com/',
                'sec-fetch-site':  'same-site',
                'sec-fetch-mode':  'cors',
                'sec-fetch-dest':  'empty',
            }

            # Resolve BSE scrip code
            bse_code = ''
            try:
                from bse import BSE as BsePkg
                import tempfile
                with BsePkg(download_folder=tempfile.gettempdir()) as bpkg:
                    result = bpkg.lookup(base_symbol)
                    if result and result.get('bse_code'):
                        bse_code = str(result['bse_code'])
                        print(f"  BSE code (pkg): {bse_code}")
            except Exception as be:
                print(f"  BSE pkg: {be}")

            if not bse_code:
                try:
                    rb = req.get(
                        f"https://api.bseindia.com/BseIndiaAPI/api/fetchComp/w"
                        f"?companySortOrder=A&industry=&issuerType=C&turnover=&companyType="
                        f"&mktcap=&segment=&status=Active&indexType=&pageno=1&pagesize=25&search={base_symbol}",
                        headers=BSE_HDR, timeout=10, proxies=proxies)
                    if rb.ok:
                        for item in rb.json().get('Table', []):
                            if (item.get('nsesymbol') or item.get('NSESymbol', '')).upper() == base_symbol:
                                bse_code = str(item.get('scripcode') or item.get('Scripcode', ''))
                                print(f"  BSE code (fetchComp): {bse_code}")
                                break
                except Exception as be2:
                    print(f"  BSE fetchComp: {be2}")

            if bse_code:
                from urllib.parse import quote as _uq

                def bse_fetch_cat(category, limit=25):
                    """Fetch filings from BSE AnnGetData for a given category."""
                    docs = []
                    try:
                        url = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
                               f"?strCat={_uq(category)}&strPrevDate=&strScrip={bse_code}"
                               f"&strSearch=P&strToDate=&strType=C")
                        rb = req.get(url, headers=BSE_HDR, timeout=15, proxies=proxies)
                        print(f"  BSE '{category[:40]}': HTTP {rb.status_code}")
                        if rb.ok:
                            payload = rb.json()
                            items   = payload if isinstance(payload, list) else \
                                      payload.get('Table', payload.get('Data', []))
                            print(f"    → {len(items)} items")
                            for item in items[:limit]:
                                att     = (item.get('ATTACHMENTNAME') or '').strip()
                                news_id = str(item.get('NEWSID') or '').strip()
                                title   = (item.get('HEADLINE') or item.get('NEWSSUB') or '').strip()
                                date    = (item.get('NEWS_DT') or item.get('DT_TM') or '').strip()[:10]
                                dt_obj  = parse_date(date) if date else None
                                days_ago = (_dt.datetime.now() - dt_obj).days if dt_obj else 999
                                folder  = 'AttachLive' if days_ago <= 30 else 'AttachHis'
                                if news_id:
                                    url2 = f"https://www.bseindia.com/corporates/ann.html?newsid={news_id}"
                                elif att:
                                    url2 = f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{att}"
                                else:
                                    continue
                                docs.append({'title': title, 'url': url2,
                                             'date': date, 'source': 'BSE'})
                    except Exception as fe:
                        print(f"  BSE fetch error ({category[:30]}): {fe}")
                    return docs

                # Annual reports fallback
                if not annual_reports:
                    bse_annual = bse_fetch_cat('Annual Report', limit=5)
                    for d in bse_annual:
                        yr_m = _re.search(r'(\d{4})', d['title'] + ' ' + d['date'])
                        d['year'] = yr_m.group(1) if yr_m else ''
                    annual_reports = bse_annual[:3]
                    print(f"  BSE annual fallback: {len(annual_reports)}")

                # Concall fallback — try MULTIPLE BSE category strings
                if not concalls:
                    bse_cc_all = []
                    for cat in [
                        'Analysts/Institutional Investor Meet/Con. Call Updates',
                        'Analysts/Institutional Investor Meet',
                        'Analyst/Investor Meet',
                        'Conference Call',
                        'Earnings Call',
                    ]:
                        cat_docs = bse_fetch_cat(cat, limit=25)
                        if cat_docs:
                            bse_cc_all.extend(cat_docs)
                            break  # use first category that returns results

                    # Also try category -1 (all) and filter by keyword
                    if not bse_cc_all:
                        print(f"  Trying BSE category=-1 (all) and filtering...")
                        try:
                            url = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
                                   f"?strCat=-1&strPrevDate=&strScrip={bse_code}"
                                   f"&strSearch=P&strToDate=&strType=C")
                            rb = req.get(url, headers=BSE_HDR, timeout=15, proxies=proxies)
                            print(f"  BSE all-categories: HTTP {rb.status_code}")
                            if rb.ok:
                                payload = rb.json()
                                items   = payload if isinstance(payload, list) else \
                                          payload.get('Table', payload.get('Data', []))
                                print(f"    → {len(items)} total items")
                                CC_KWS = ['transcript', 'earnings transcript']
                                for item in items:
                                    title = (item.get('HEADLINE') or item.get('NEWSSUB') or '').strip()
                                    if any(kw in title.lower() for kw in CC_KWS):
                                        att     = (item.get('ATTACHMENTNAME') or '').strip()
                                        news_id = str(item.get('NEWSID') or '').strip()
                                        date    = (item.get('NEWS_DT') or item.get('DT_TM') or '').strip()[:10]
                                        dt_obj  = parse_date(date) if date else None
                                        days_ago = (_dt.datetime.now() - dt_obj).days if dt_obj else 999
                                        folder  = 'AttachLive' if days_ago <= 30 else 'AttachHis'
                                        if news_id:
                                            url2 = f"https://www.bseindia.com/corporates/ann.html?newsid={news_id}"
                                        elif att:
                                            url2 = f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{att}"
                                        else:
                                            continue
                                        bse_cc_all.append({'title': title, 'url': url2,
                                                           'date': date, 'source': 'BSE'})
                                print(f"    Filtered to {len(bse_cc_all)} concall-related items")
                        except Exception as ae:
                            print(f"  BSE all-cat error: {ae}")

                    # Transcripts only
                    merged = [d for d in bse_cc_all if 'transcript' in d['title'].lower()][:5] 

                    # Attach quarter labels from filing date in "Q1 2025" format
                    for d in merged:
                        dt_obj = parse_date(d['date']) if d['date'] else None
                        if dt_obj:
                            month = dt_obj.month
                            year_val = dt_obj.year
                            # Determine fiscal year and quarter
                            if month >= 4:  # Apr-Dec (Q1-Q3 of current FY)
                                fy = year_val + 1
                            else:  # Jan-Mar (Q4 of previous FY)
                                fy = year_val
                            
                            q = ('Q1' if month in [4,5,6] else
                                 'Q2' if month in [7,8,9] else
                                 'Q3' if month in [10,11,12] else 'Q4')
                            d['quarter'] = f"{q} {fy}"
                        else:
                            d['quarter'] = quarter_from_title(d['title'])
                    concalls = merged
                    print(f"  BSE concall fallback: {len(concalls)}")
                    for d in concalls:
                        print(f"    [{d['quarter']}] {d['title'][:60]}")

        # ══════════════════════════════════════════════════════════════════════
        # STEP 3: NSE fallback (last resort for concalls)
        # ══════════════════════════════════════════════════════════════════════
        if not concalls:
            print(f"  NSE fallback for concalls...")
            NSE_HDR = {
                'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept':          'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer':         'https://www.nseindia.com/',
            }
            try:
                nse_sess = req.Session()
                nse_sess.get('https://www.nseindia.com', headers={**NSE_HDR,
                             'Accept': 'text/html,application/xhtml+xml,*/*'},
                             timeout=12, proxies=proxies)
                CC_KWS = ['transcript', 'earnings transcript']
                for url in [
                    f"https://www.nseindia.com/api/corporate-announcements?symbol={base_symbol}",
                    f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={base_symbol}",
                ]:
                    rn = nse_sess.get(url, headers=NSE_HDR, timeout=12, proxies=proxies)
                    print(f"  NSE {url[-55:]}: HTTP {rn.status_code}")
                    if rn.ok:
                        data_n = rn.json()
                        if isinstance(data_n, dict):
                            data_n = data_n.get('data') or data_n.get('Table') or []
                        if isinstance(data_n, list) and data_n:
                            print(f"    → {len(data_n)} total announcements")
                            for item in data_n:
                                title = (item.get('desc') or '').strip()
                                att   = (item.get('attchmntFile') or '').strip()
                                date  = (item.get('an_dt') or '').strip()[:10]
                                if not att or not any(kw in title.lower() for kw in CC_KWS):
                                    continue
                                pdf_url = att if att.startswith('http') \
                                          else f"https://nsearchives.nseindia.com/corporate/{att}"
                                dt_obj  = parse_date(date) if date else None
                                if dt_obj:
                                    month = dt_obj.month
                                    fy    = (dt_obj.year + 1) if month >= 4 else dt_obj.year
                                    q     = ('Q1' if month in [4,5,6] else
                                             'Q2' if month in [7,8,9] else
                                             'Q3' if month in [10,11,12] else 'Q4')
                                    quarter_label = f"{q}FY{str(fy)[-2:]}"
                                else:
                                    quarter_label = quarter_from_title(title)
                                concalls.append({
                                    'title':   title,
                                    'url':     pdf_url,
                                    'quarter': quarter_label,
                                    'date':    date,
                                    'source':  'NSE',
                                })
                                if len(concalls) >= 5:
                                    break
                            if concalls:
                                break
            except Exception as ne:
                print(f"  NSE fallback error: {ne}")
            print(f"  NSE concall fallback: {len(concalls)}")

        fallback_links = {
            'screener':          screener_url,
            'screener_docs':     screener_url + '#documents',
            'nse_annual':        f"https://www.nseindia.com/companies-listing/corporate-filings-annual-reports?symbol={base_symbol}",
            'nse_announcements': f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={base_symbol}",
        }

        # Deduplicate concalls by URL only — remove exact duplicate documents
        seen_urls, deduped = set(), []
        for d in concalls:
            url = d.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(d)
        concalls = deduped

        # STEP 4: presentations already fetched in STEP 1b
        presentations = screener_presentations[:1] if screener_presentations else []
        if presentations:
            print(f"  Presentation: {presentations[0]['url']}")

        print(f"  Presentations: {len(presentations)}")
        for p in presentations:
            print(f"    [{p['date']}] {p['title'][:60]}")

        print(f"  ✓ Final: {len(annual_reports)} annual reports, {len(concalls)} concalls, {len(presentations)} presentations")
        return jsonify({
            'annual_reports':  annual_reports,
            'concalls':        concalls,
            'presentations':   presentations,
            'fallback_links':  fallback_links,
            'symbol':          base_symbol,
            'company':         company,
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e), 'annual_reports': [], 'concalls': [], 'presentations': []}), 500


# ═══════════════════════════════════════════════════════════
# DEEP DIVE - FETCH AND READ DOCUMENTS
# ═══════════════════════════════════════════════════════════

def extract_text_from_pdf(pdf_url, proxies=None, max_pages=15):
    """
    Fetch PDF from URL and extract text.
    Limited to first 15 pages to fit within API token limits.
    Returns: (text_content, error_msg)
    """
    try:
        # Install pypdf if needed
        try:
            import pypdf
        except ImportError:
            print("  Installing pypdf...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pypdf', '--break-system-packages', '-q'])
            import pypdf
        
        print(f"  Fetching PDF: {pdf_url[:80]}...")
        
        # Fetch PDF - use BSE headers if it's a BSE URL
        if 'bseindia.com' in pdf_url:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Origin': 'https://www.bseindia.com',
                'Referer': 'https://www.bseindia.com/',
                'sec-fetch-site': 'same-site',
                'sec-fetch-mode': 'cors',
                'sec-fetch-dest': 'empty',
            }
        else:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        resp = req.get(pdf_url, headers=headers, timeout=30, proxies=proxies, stream=True)
        
        if not resp.ok:
            return '', f'HTTP {resp.status_code}'
        
        print(f"  Downloaded {len(resp.content)} bytes, extracting text...")
        
        # Extract text from PDF
        import io
        pdf_file = io.BytesIO(resp.content)
        
        try:
            reader = pypdf.PdfReader(pdf_file)
        except Exception as e:
            error_msg = str(e)
            # Check if it's not a PDF
            if 'invalid pdf header' in error_msg.lower():
                return '', 'Not a PDF file (might be HTML, audio, or other format)'
            return '', f'PDF read error: {error_msg[:100]}'
        
        total_pages = len(reader.pages)
        pages_to_read = min(total_pages, max_pages)
        
        text_parts = []
        for i in range(pages_to_read):
            try:
                page = reader.pages[i]
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            except:
                pass
        
        full_text = '\n\n'.join(text_parts)
        print(f"  Extracted {len(full_text)} characters from {pages_to_read}/{total_pages} pages")
        
        return full_text, None
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return '', str(e)


@app.route('/api/deepdive/fetch-docs', methods=['POST'])
def deepdive_fetch_docs():
    """
    Fetch and extract text from documents.
    Expects: {docs: [{url, title, type}], proxy_host, proxy_port}
    Returns: {docs: [{url, title, type, text, error}]}
    """
    try:
        data = request.get_json() or {}
        docs = data.get('docs', [])
        proxy_host = data.get('proxy_host', '').strip()
        proxy_port = data.get('proxy_port', '').strip()
        
        proxies = make_proxies(proxy_host, proxy_port)
        
        print(f"\n[Fetch Docs] Processing {len(docs)} documents")
        
        results = []
        for doc in docs:
            url = doc.get('url', '')
            title = doc.get('title', '')
            doc_type = doc.get('type', '')
            
            print(f"\n  [{doc_type}] {title}")
            
            # Extract text from PDF
            text, error = extract_text_from_pdf(url, proxies)
            
            results.append({
                'url': url,
                'title': title,
                'type': doc_type,
                'text': text,
                'error': error,
                'length': len(text)
            })
        
        return jsonify({'docs': results})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'docs': []}), 500


@app.route('/api/deepdive/ask', methods=['POST'])
def deepdive_ask():
    """
    Ask ChatGPT a question with document context.
    Expects: {question, context, messages, proxy_host, proxy_port}
    Returns: {answer}
    """
    try:
        data = request.get_json() or {}
        question = data.get('question', '').strip()
        context = data.get('context', '')  # Document text
        messages = data.get('messages', [])  # Chat history
        proxy_host = data.get('proxy_host', '').strip()
        proxy_port = data.get('proxy_port', '').strip()
        
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        proxies = make_proxies(proxy_host, proxy_port)
        
        print(f"\n[Deep Dive Ask] Question: {question[:100]}")
        print(f"  Context length: {len(context)} chars")
        print(f"  Chat history: {len(messages)} messages")
        
        # Build system prompt with context
        system_prompt = """You are a financial analysis AI assistant. You have access to company documents including annual reports, earnings call transcripts, and investor presentations.

Answer questions based on the provided documents. Be specific and cite which document you're referencing. If the information is not in the documents, say so clearly.

Use a professional but conversational tone. Format your responses with:
- **Bold** for key metrics and numbers
- Bullet points for lists
- Clear section headers when appropriate

Document context:
""" + context[:100000]  # Gemini has 1M token context window!
        
        # Get API key
        api_key = os.environ.get('GEMINI_API_KEY', '').strip()
        
        if not api_key:
            return jsonify({'error': 'GEMINI_API_KEY environment variable not set. Get free key at https://aistudio.google.com/apikey', 'answer': ''}), 500
        
        print(f"  Gemini API key: {api_key[:20]}...{api_key[-10:]}")
        
        # Call Google Gemini API (using v1beta)
        # Using gemini-2.5-flash-lite for better free tier limits
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
        
        # Build messages - Gemini uses different format
        # Combine system prompt and chat history
        conversation_text = system_prompt + "\n\n"
        
        # Add chat history
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                conversation_text += f"User: {content}\n\n"
            elif role == 'assistant':
                conversation_text += f"Assistant: {content}\n\n"
        
        # Add current question
        conversation_text += f"User: {question}\n\nAssistant:"
        
        payload = {
            'contents': [{
                'parts': [{
                    'text': conversation_text
                }]
            }],
            'generationConfig': {
                'temperature': 0.7,
                'maxOutputTokens': 8192,
                'topP': 0.95,
            }
        }
        
        print(f"  Calling Gemini API (gemini-2.5-flash-lite)...")
        
        # Retry logic for rate limits
        max_retries = 3
        for attempt in range(max_retries):
            resp = req.post(api_url, json=payload, timeout=60, proxies=proxies)
            
            if resp.ok:
                break  # Success
            
            # Check if it's a rate limit error
            if resp.status_code == 429:
                if attempt < max_retries - 1:
                    # Extract retry time from error message
                    import re, time
                    retry_match = re.search(r'retry in ([\d.]+)s', resp.text)
                    wait_time = float(retry_match.group(1)) if retry_match else 5
                    print(f"  Rate limited. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    # Last attempt failed
                    return jsonify({
                        'error': 'Gemini API rate limit exceeded. Please wait a moment and try again.',
                        'answer': ''
                    }), 429
            else:
                # Other error
                error_detail = resp.text[:500]
                return jsonify({'error': f'Gemini API error: HTTP {resp.status_code} - {error_detail}', 'answer': ''}), 500
        
        if not resp.ok:
            return jsonify({'error': 'Failed after retries', 'answer': ''}), 500
        
        result = resp.json()
        
        # Extract answer from Gemini response
        answer = ''
        try:
            candidates = result.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts:
                    answer = parts[0].get('text', '')
        except Exception as e:
            print(f"  Error parsing Gemini response: {e}")
            answer = ''
        
        if not answer:
            return jsonify({'error': 'No response from Gemini', 'answer': ''}), 500
        
        print(f"  Response length: {len(answer)} chars")
        
        return jsonify({'answer': answer})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'answer': ''}), 500
        
        print(f"  Response length: {len(answer)} chars")
        
        return jsonify({'answer': answer})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'answer': ''}), 500


if __name__ == '__main__':
    print("=" * 55)
    print("  Stock Tracker Backend  –  http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, port=5000, host='0.0.0.0')


@app.route('/api/debug/bse', methods=['POST'])
def debug_bse():
    """Debug endpoint to test BSE API calls with full logging"""
    data = request.get_json() or {}
    symbol = data.get('symbol', 'NLAB').upper()
    
    results = {'symbol': symbol, 'steps': []}
    
    # Headers
    BSE_HDR = {
        'User-Agent':        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept':            'application/json, text/plain, */*',
        'Accept-Language':   'en-US,en;q=0.9',
        'Origin':            'https://www.bseindia.com',
        'Referer':           'https://www.bseindia.com/',
        'sec-fetch-site':    'same-site',
        'sec-fetch-mode':    'cors',
        'sec-fetch-dest':    'empty',
    }
    
    # Step 1: Resolve BSE code
    results['steps'].append('=== STEP 1: Resolve BSE Code ===')
    bse_code = ''
    
    # Try bse package
    try:
        from bse import BSE as BsePkg
        import tempfile
        with BsePkg(download_folder=tempfile.gettempdir()) as bpkg:
            result = bpkg.lookup(symbol)
            if result:
                bse_code = str(result.get('bse_code', ''))
                results['steps'].append(f"✓ bse pkg: {bse_code}")
                results['bse_code'] = bse_code
    except Exception as e:
        results['steps'].append(f"✗ bse pkg error: {str(e)}")
    
    # Try fetchComp if still no code
    if not bse_code:
        try:
            url = (f"https://api.bseindia.com/BseIndiaAPI/api/fetchComp/w"
                   f"?companySortOrder=A&industry=&issuerType=C&turnover=&companyType="
                   f"&mktcap=&segment=&status=Active&indexType=&pageno=1&pagesize=25&search={symbol}")
            results['steps'].append(f"Trying fetchComp: {url[:100]}...")
            r = req.get(url, headers=BSE_HDR, timeout=10)
            results['steps'].append(f"  HTTP {r.status_code}")
            if r.ok:
                data = r.json()
                results['fetchComp_response'] = data
                for item in data.get('Table', []):
                    sym = (item.get('nsesymbol') or item.get('NSESymbol', '')).upper()
                    if sym == symbol:
                        bse_code = str(item.get('scripcode') or item.get('Scripcode', ''))
                        results['steps'].append(f"✓ fetchComp match: {bse_code}")
                        results['bse_code'] = bse_code
                        break
                if not bse_code:
                    results['steps'].append(f"✗ No match in {len(data.get('Table',[]))} results")
        except Exception as e:
            results['steps'].append(f"✗ fetchComp error: {str(e)}")
    
    if not bse_code:
        results['steps'].append("!! FAILED to resolve BSE code")
        return jsonify(results)
    
    # Step 2: Fetch Annual Reports
    results['steps'].append('\n=== STEP 2: Fetch Annual Reports ===')
    try:
        from urllib.parse import quote as _quote
        category = 'Annual Report'
        url = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
               f"?strCat={_quote(category)}&strPrevDate=&strScrip={bse_code}"
               f"&strSearch=P&strToDate=&strType=C")
        results['steps'].append(f"URL: {url}")
        r = req.get(url, headers=BSE_HDR, timeout=15)
        results['steps'].append(f"HTTP {r.status_code}")
        
        if r.ok:
            payload = r.json()
            items = payload if isinstance(payload, list) else \
                    payload.get('Table', payload.get('Data', []))
            results['steps'].append(f"✓ Got {len(items)} items")
            results['annual_reports'] = []
            for item in items[:10]:
                doc = {
                    'title': item.get('HEADLINE', item.get('NEWSSUB', '')),
                    'date': item.get('NEWS_DT', item.get('DT_TM', ''))[:10],
                    'newsid': item.get('NEWSID', ''),
                    'attachment': item.get('ATTACHMENTNAME', ''),
                }
                results['annual_reports'].append(doc)
                results['steps'].append(f"  [{doc['date']}] {doc['title'][:60]}")
        else:
            results['steps'].append(f"✗ HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        results['steps'].append(f"✗ Error: {str(e)}")
        import traceback
        results['steps'].append(traceback.format_exc())
    
    return jsonify(results)


# ═══════════════════════════════════════════════════════════
# CLEAN DEEP DIVE BACKEND - Simple & Reliable
# Fetches exactly: 3 annual reports + 4 quarterly concall transcripts
# ═══════════════════════════════════════════════════════════

@app.route('/api/deepdive/simple', methods=['POST'])
def deepdive_simple():
    """
    Fetch documents for Deep Dive using BSE API.
    Returns: 3 latest annual reports + 4 latest quarterly concalls with direct PDF URLs
    """
    try:
        data = request.get_json() or {}
        base_symbol = data.get('base_symbol', '').upper().strip()
        company = data.get('company', '').strip()
        proxy_host = data.get('proxy_host', '').strip()
        proxy_port = data.get('proxy_port', '').strip()
        
        if not base_symbol:
            return jsonify({'error': 'No symbol provided'}), 400
        
        proxies = make_proxies(proxy_host, proxy_port)
        
        print(f"\n[Deep Dive BSE] {base_symbol}")
        
        # ═══════════════════════════════════════════════════════════
        # GET BSE CODE
        # ═══════════════════════════════════════════════════════════
        bse_code = None
        
        # Method 1: bse package
        try:
            from bse import BSE as BsePkg
            import tempfile
            with BsePkg(download_folder=tempfile.gettempdir()) as bpkg:
                result = bpkg.lookup(base_symbol)
                if result and result.get('bse_code'):
                    bse_code = str(result['bse_code'])
                    print(f"  BSE code (pkg): {bse_code}")
        except Exception as e:
            print(f"  BSE pkg error: {e}")
        
        # Method 2: fetchComp API
        if not bse_code:
            try:
                hdr = {'User-Agent': 'Mozilla/5.0'}
                url = f"https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w?quotetype=EQ&scripcode=&seriesid="
                r = req.get(url, headers=hdr, timeout=10, proxies=proxies)
                if r.ok:
                    data = r.json()
                    if 'Table' in data and len(data['Table']) > 0:
                        for item in data['Table']:
                            if item.get('scrip_cd'):
                                bse_code = str(item['scrip_cd'])
                                print(f"  BSE code (fetchComp): {bse_code}")
                                break
            except Exception as e:
                print(f"  fetchComp error: {e}")
        
        if not bse_code:
            return jsonify({
                'error': f'Could not find BSE code for {base_symbol}',
                'annual_reports': [],
                'concalls': [],
                'fallback_links': {
                    'nse_annual': f"https://www.nseindia.com/companies-listing/corporate-filings-annual-reports?symbol={base_symbol}",
                    'nse_announcements': f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={base_symbol}",
                    'screener': f"https://www.screener.in/company/{base_symbol}/",
                }
            }), 200
        
        # ═══════════════════════════════════════════════════════════
        # BSE HEADERS (CRITICAL)
        # ═══════════════════════════════════════════════════════════
        BSE_HDR = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.bseindia.com',
            'Referer': 'https://www.bseindia.com/',
            'sec-fetch-site': 'same-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
        }
        
        # ═══════════════════════════════════════════════════════════
        # FETCH ANNUAL REPORTS (latest 3)
        # ═══════════════════════════════════════════════════════════
        annual_reports = []
        try:
            from urllib.parse import quote as _uq
            category = _uq('Annual Report')
            url = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
                  f"?strCat={category}&strPrevDate=&strScrip={bse_code}&strSearch=P&strToDate=&strType=C")
            
            print(f"  Fetching Annual Reports from BSE...")
            r = req.get(url, headers=BSE_HDR, timeout=15, proxies=proxies)
            print(f"  HTTP {r.status_code}, {len(r.content)} bytes")
            
            if r.ok:
                data = r.json()
                items = data.get('Table', [])
                print(f"  Found {len(items)} annual reports")
                
                for item in items[:10]:  # Process top 10, take 3 later
                    news_id = item.get('NEWSID', '')
                    attachment = item.get('ATTACHMENTNAME', '')
                    news_dt = item.get('NEWS_DT', '')
                    headline = item.get('HEADLINE', '') or item.get('SLONGNAME', '')
                    
                    if not attachment:
                        continue
                    
                    # Parse year from headline/date
                    import re
                    from datetime import datetime
                    
                    # Try to parse year from headline (e.g., "Annual Report 2024-25")
                    title = headline if headline else "Annual Report"
                    year_match = re.search(r'(\d{4})-?(\d{2,4})', title)
                    if year_match:
                        to_year = year_match.group(2)
                        if len(to_year) == 2:
                            to_year = '20' + to_year
                        sort_year = int(to_year)
                    else:
                        # Fallback to date year
                        try:
                            dt = datetime.strptime(news_dt[:10], '%d/%m/%Y')
                            sort_year = dt.year
                        except:
                            sort_year = 0
                    
                    # Determine folder based on filing age
                    try:
                        dt = datetime.strptime(news_dt[:10], '%d/%m/%Y')
                        days_ago = (datetime.now() - dt).days
                        folder = 'AttachLive' if days_ago <= 30 else 'AttachHis'
                    except:
                        folder = 'AttachHis'  # Default to historical
                    
                    # Construct PDF URL
                    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{attachment}"
                    
                    # Construct page URL
                    page_url = f"https://www.bseindia.com/corporates/ann.html?newsid={news_id}" if news_id else pdf_url
                    
                    annual_reports.append({
                        'title': title,
                        'url': pdf_url,
                        'page_url': page_url,
                        'year': str(sort_year) if sort_year > 0 else '',
                        'sort_year': sort_year,
                        'source': 'BSE',
                        'date': news_dt[:10] if news_dt else ''
                    })
                
                # Sort by year descending, take top 3
                annual_reports.sort(key=lambda x: x['sort_year'], reverse=True)
                annual_reports = annual_reports[:3]
                
                print(f"  Selected top 3:")
                for ar in annual_reports:
                    print(f"    [{ar['year']}] {ar['title']}")
                    print(f"      PDF: {ar['url']}")
        
        except Exception as e:
            import traceback
            print(f"  Annual reports error: {e}")
            traceback.print_exc()
        
        # ═══════════════════════════════════════════════════════════
        # FETCH CONCALL TRANSCRIPTS (latest 4)
        # ═══════════════════════════════════════════════════════════
        concalls = []
        try:
            from urllib.parse import quote as _uq
            category = _uq('Analysts/Institutional Investor Meet/Con. Call Updates')
            url = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
                  f"?strCat={category}&strPrevDate=&strScrip={bse_code}&strSearch=P&strToDate=&strType=C")
            
            print(f"  Fetching Concalls from BSE...")
            r = req.get(url, headers=BSE_HDR, timeout=15, proxies=proxies)
            print(f"  HTTP {r.status_code}, {len(r.content)} bytes")
            
            if r.ok:
                data = r.json()
                items = data.get('Table', [])
                print(f"  Found {len(items)} concall announcements")
                
                # Filter for transcripts only
                transcript_items = []
                for item in items:
                    headline = (item.get('HEADLINE', '') or item.get('SLONGNAME', '')).lower()
                    if 'transcript' in headline:
                        transcript_items.append(item)
                
                print(f"  Filtered to {len(transcript_items)} transcripts")
                
                for item in transcript_items[:10]:  # Process top 10, take 4 later
                    news_id = item.get('NEWSID', '')
                    attachment = item.get('ATTACHMENTNAME', '')
                    news_dt = item.get('NEWS_DT', '')
                    headline = item.get('HEADLINE', '') or item.get('SLONGNAME', '')
                    
                    if not attachment:
                        continue
                    
                    # Parse date and determine quarter
                    from datetime import datetime
                    try:
                        dt = datetime.strptime(news_dt[:10], '%d/%m/%Y')
                        date_str = dt.strftime('%d %b %Y')
                        sort_ts = dt.timestamp()
                        
                        # Determine quarter (Indian FY: Apr-Mar)
                        month = dt.month
                        year = dt.year
                        if month >= 4:  # Apr onwards = current FY
                            fy_year = year + 1
                        else:  # Jan-Mar = previous FY
                            fy_year = year
                        
                        if month in [4,5,6]:
                            quarter = 'Q1'
                        elif month in [7,8,9]:
                            quarter = 'Q2'
                        elif month in [10,11,12]:
                            quarter = 'Q3'
                        else:
                            quarter = 'Q4'
                        
                        quarter_label = f"{quarter} FY{str(fy_year)[-2:]}"
                        
                        # Determine folder based on filing age
                        days_ago = (datetime.now() - dt).days
                        folder = 'AttachLive' if days_ago <= 30 else 'AttachHis'
                    except:
                        date_str = news_dt[:10] if news_dt else ''
                        sort_ts = 0
                        quarter_label = ''
                        folder = 'AttachHis'
                    
                    # Construct PDF URL
                    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{attachment}"
                    
                    # Construct page URL
                    page_url = f"https://www.bseindia.com/corporates/ann.html?newsid={news_id}" if news_id else pdf_url
                    
                    concalls.append({
                        'title': headline,
                        'url': pdf_url,
                        'page_url': page_url,
                        'date': date_str,
                        'quarter': quarter_label,
                        'sort_ts': sort_ts,
                        'source': 'BSE'
                    })
                
                # Sort by date descending, take top 5
                concalls.sort(key=lambda x: x['sort_ts'], reverse=True)
                concalls = concalls[:5]
                
                print(f"  Selected top 5:")
                for cc in concalls:
                    print(f"    [{cc['quarter']}] {cc['date']} - {cc['title'][:50]}")
                    print(f"      PDF: {cc['url']}")
        
        except Exception as e:
            import traceback
            print(f"  Concalls error: {e}")
            traceback.print_exc()
        
        # ═══════════════════════════════════════════════════════════
        # FETCH INVESTOR PRESENTATIONS (latest 1)
        # ═══════════════════════════════════════════════════════════
        presentations = []
        
        # Try BSE first with multiple category names
        try:
            from urllib.parse import quote as _uq
            
            # Try different category variations
            categories = [
                'Investor Presentation',
                'Investor/Analyst Presentation',
                'Presentation',
                'Corporate Presentation'
            ]
            
            for category_name in categories:
                category = _uq(category_name)
                url = (f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
                      f"?strCat={category}&strPrevDate=&strScrip={bse_code}&strSearch=P&strToDate=&strType=C")
                
                print(f"  Trying BSE category: {category_name}")
                r = req.get(url, headers=BSE_HDR, timeout=15, proxies=proxies)
                
                if r.ok:
                    data = r.json()
                    items = data.get('Table', [])
                    print(f"    Found {len(items)} items")
                    
                    if len(items) > 0:
                        # Found presentations, process them
                        for item in items[:5]:
                            news_id = item.get('NEWSID', '')
                            attachment = item.get('ATTACHMENTNAME', '')
                            news_dt = item.get('NEWS_DT', '')
                            headline = item.get('HEADLINE', '') or item.get('SLONGNAME', '')
                            
                            if not attachment:
                                continue
                            
                            # Parse date
                            from datetime import datetime
                            try:
                                dt = datetime.strptime(news_dt[:10], '%d/%m/%Y')
                                date_str = dt.strftime('%d %b %Y')
                                sort_ts = dt.timestamp()
                                
                                # Determine folder based on filing age
                                days_ago = (datetime.now() - dt).days
                                folder = 'AttachLive' if days_ago <= 30 else 'AttachHis'
                            except:
                                date_str = news_dt[:10] if news_dt else ''
                                sort_ts = 0
                                folder = 'AttachHis'
                            
                            # Construct PDF URL
                            pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/{folder}/{attachment}"
                            
                            # Construct page URL
                            page_url = f"https://www.bseindia.com/corporates/ann.html?newsid={news_id}" if news_id else pdf_url
                            
                            title = headline if headline else "Investor Presentation"
                            
                            presentations.append({
                                'title': title,
                                'url': pdf_url,
                                'page_url': page_url,
                                'date': date_str,
                                'sort_ts': sort_ts,
                                'source': 'BSE'
                            })
                        
                        break  # Found presentations, stop trying other categories
        
        except Exception as e:
            print(f"  BSE presentations error: {e}")
        
        # If no presentations from BSE, try NSE
        if not presentations:
            print(f"  No presentations from BSE, trying NSE...")
            try:
                # NSE session
                NSE_HDR = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json, text/plain, */*',
                    'Referer': 'https://www.nseindia.com/',
                }
                
                sess = req.Session()
                try:
                    sess.get('https://www.nseindia.com', headers={**NSE_HDR, 'Accept': 'text/html'}, 
                            timeout=10, proxies=proxies)
                except:
                    pass
                
                # Search in corporate announcements for presentations
                url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={base_symbol}"
                r = sess.get(url, headers=NSE_HDR, timeout=15, proxies=proxies)
                
                if r.ok:
                    data = r.json()
                    items = data if isinstance(data, list) else data.get('data', [])
                    
                    # Filter for presentations
                    pres_items = []
                    for item in items:
                        desc = (item.get('desc') or '').lower()
                        if 'presentation' in desc or 'investor' in desc:
                            pres_items.append(item)
                    
                    print(f"  Found {len(pres_items)} presentations on NSE")
                    
                    for item in pres_items[:5]:
                        filename = item.get('attchmntFile', '')
                        if not filename:
                            continue
                        
                        # Parse date
                        from datetime import datetime
                        an_dt = item.get('an_dt', '')
                        try:
                            dt = datetime.strptime(an_dt, '%d-%b-%Y')
                            date_str = dt.strftime('%d %b %Y')
                            sort_ts = dt.timestamp()
                        except:
                            date_str = an_dt
                            sort_ts = 0
                        
                        url = f"https://nsearchives.nseindia.com/corporate/{filename}"
                        title = item.get('desc', 'Investor Presentation')
                        
                        presentations.append({
                            'title': title,
                            'url': url,
                            'page_url': url,
                            'date': date_str,
                            'sort_ts': sort_ts,
                            'source': 'NSE'
                        })
            
            except Exception as e:
                print(f"  NSE presentations error: {e}")
        
        # Sort by date descending, take only the latest 1
        if presentations:
            presentations.sort(key=lambda x: x['sort_ts'], reverse=True)
            presentations = presentations[:1]
            
            pres = presentations[0]
            print(f"  Latest presentation: {pres['date']} - {pres['title'][:50]}")
            print(f"    PDF: {pres['url']}")
        else:
            print(f"  No presentations found for {base_symbol}")
        
        # ═══════════════════════════════════════════════════════════
        # RETURN RESULTS
        # ═══════════════════════════════════════════════════════════
        return jsonify({
            'annual_reports': annual_reports,
            'concalls': concalls,
            'presentations': presentations,
            'fallback_links': {
                'nse_annual': f"https://www.nseindia.com/companies-listing/corporate-filings-annual-reports?symbol={base_symbol}",
                'nse_announcements': f"https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol={base_symbol}",
                'screener': f"https://www.screener.in/company/{base_symbol}/",
                'bse': f"https://www.bseindia.com/corporates/ann.html?scripcode={bse_code}" if bse_code else None
            },
            'symbol': base_symbol,
            'company': company,
            'bse_code': bse_code
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
