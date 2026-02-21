# Stock Tracker - Deployment Guide

## Quick Deploy Options

### Option 1: Render.com (Recommended - Free Tier Available)

1. **Create Account**: Go to https://render.com
2. **Create New Web Service**
3. **Connect GitHub**: Push your code to GitHub first
4. **Configure**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn stock_backend:app`
   - Environment Variables:
     - `GEMINI_API_KEY`: Your Gemini API key
     - `SECRET_KEY`: Generate random string (e.g., `python -c "import secrets; print(secrets.token_hex(32))"`)
     - `FLASK_ENV`: production

5. **Deploy**: Click "Create Web Service"

### Option 2: Railway.app (Easy Deploy)

1. **Create Account**: https://railway.app
2. **New Project** → Deploy from GitHub
3. **Add Environment Variables**:
   - `GEMINI_API_KEY`
   - `SECRET_KEY`
4. Railway auto-detects Python and deploys

### Option 3: PythonAnywhere (Free for small projects)

1. **Create Account**: https://www.pythonanywhere.com
2. **Upload Files**: Upload all your files
3. **Create Web App**: Python → Flask
4. **Configure**:
   - Set working directory
   - Set WSGI file to point to `stock_backend:app`
   - Add environment variables in web tab

### Option 4: Heroku

1. **Create Heroku Account**
2. **Install Heroku CLI**
3. **Deploy**:
   ```bash
   heroku create your-app-name
   git push heroku main
   heroku config:set GEMINI_API_KEY=your_key
   heroku config:set SECRET_KEY=your_secret
   ```

## Required Files

### 1. requirements.txt
```
Flask==3.0.0
Flask-Login==0.6.3
Flask-CORS==4.0.0
requests==2.31.0
beautifulsoup4==4.12.2
lxml==5.1.0
yfinance==0.2.33
pypdf==4.0.1
Werkzeug==3.0.1
gunicorn==21.2.0
```

### 2. Procfile (for Heroku/Render)
```
web: gunicorn stock_backend:app
```

### 3. runtime.txt (optional - specify Python version)
```
python-3.11.7
```

### 4. .env (for local development - DON'T commit to Git)
```
GEMINI_API_KEY=your_gemini_api_key
SECRET_KEY=your_secret_key_here
FLASK_ENV=development
```

## Environment Variables

Set these in your hosting platform:

- `GEMINI_API_KEY`: Your Google Gemini API key
- `SECRET_KEY`: Random secret for session encryption
- `FLASK_ENV`: Set to `production`

## Database

The app uses SQLite (`users.db`) which works for small deployments.

For production at scale, consider:
- PostgreSQL (Render provides free PostgreSQL)
- MySQL
- MongoDB

## Security Checklist

- [x] HTTPS enabled (automatic on Render/Railway/Heroku)
- [x] Password hashing (SHA256)
- [x] Session management (Flask-Login)
- [x] CORS configured
- [ ] Rate limiting (add if needed)
- [ ] Input validation (already implemented)

## Custom Domain

Most platforms allow custom domains:
- Render: Settings → Custom Domain
- Railway: Settings → Domains
- Heroku: Settings → Domains

## Monitoring

Free monitoring options:
- UptimeRobot: Check if site is up
- LogDNA: Log management
- Sentry: Error tracking

## Scaling

For high traffic:
1. Switch from SQLite to PostgreSQL
2. Add Redis for session storage
3. Enable caching
4. Use CDN for static files

## Cost Estimates

- **Render Free**: Good for personal use, sleeps after inactivity
- **Render Paid**: $7/month - always on
- **Railway**: $5/month free tier
- **PythonAnywhere**: Free tier available
- **Heroku**: $7/month (hobby tier)

## Support

If you need help:
1. Check platform documentation
2. Community forums
3. Platform support tickets
