FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Внутри контейнера слушаем на 8003, наружу торчим как 8004 через docker-compose
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]