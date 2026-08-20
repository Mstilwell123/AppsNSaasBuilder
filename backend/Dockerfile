FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Expose port
EXPOSE 8001

# Run the server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
