FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source code
COPY backend /app/backend
COPY frontend /app/frontend

EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
