FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching — only rebuilds if requirements change)
COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt

# Copy app code
COPY . .

# Copy ML artifacts to where model.py expects them
COPY models/ /app/models/
COPY processed/ /app/processed/

# Run with uvicorn, hot reload enabled for dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
