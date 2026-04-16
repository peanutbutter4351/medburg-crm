#!/usr/bin/env bash

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Running migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating/fixing admin user..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()

user = User.objects.filter(username="admin").first()

if not user:
    user = User.objects.create_user(
        username="admin",
        email="info@medburgmedical.com",
        password="MCRM@2026"
    )

user.is_staff = True
user.is_superuser = True
user.is_active = True

if hasattr(user, "role"):
    user.role = "admin"

user.save()

print("Admin user ready")
END