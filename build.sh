python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()

username = "admin"
email = "info@medburgmedical.com"
password = "MCRM@2026"

if not User.objects.filter(username=username).exists():
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True

    # OPTIONAL (if your model has role field)
    if hasattr(user, "role"):
        user.role = "admin"

    user.save()
    print("Superuser created properly")
else:
    print("User already exists")
END