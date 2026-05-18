# Use official Python image
FROM python:3.12-slim

# Prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Show logs instantly
ENV PYTHONUNBUFFERED=1

# Use production settings
ENV DJANGO_SETTINGS_MODULE=medburg_crm.settings.production

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose app port
EXPOSE 8000

# Run app using Gunicorn
CMD ["gunicorn", "medburg_crm.wsgi:application", "--bind", "0.0.0.0:8000"]