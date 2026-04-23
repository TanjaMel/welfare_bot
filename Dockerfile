FROM node:20-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY welfare-bot-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY welfare-bot-backend/ .

# Copy built frontend into backend static folder
COPY --from=frontend-builder /frontend/dist ./static

# Expose port
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]