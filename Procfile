web: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 4 --threads 2 --worker-class gevent --timeout 120 --keep-alive 5 --log-level info --access-logfile - --error-logfile -
worker: celery -A app.celery worker --loglevel=info --concurrency=2
beat: celery -A app.celery beat --loglevel=info
release: python init_db.py && python scripts/create_indexes.py
