#!/usr/bin/env bash

echo "Running migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating superuser (if not exists)..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "mail.saanthanuprasad@gmail.com", "admin123")
    print("Superuser created")
else:
    print("Superuser already exists")
END