web: gunicorn stock_backend:app --bind 0.0.0.0:$PORT --workers 1 --worker-class gevent --worker-connections 50 --timeout 120 --max-requests 500 --max-requests-jitter 50
