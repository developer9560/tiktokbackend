FROM python:3.12

# Prevent Python from creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Enable logs immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /backend

# Install dependencies first
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Set working directory to the 'app' folder where main.py lives
WORKDIR /backend/app

EXPOSE 8000

# Run uvicorn exactly like you do locally
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]