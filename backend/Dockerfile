FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run database migrations and start server
CMD ["sh", "-c", "alembic upgrade head && fastapi run app/main.py --port 8000 --host 0.0.0.0"]
