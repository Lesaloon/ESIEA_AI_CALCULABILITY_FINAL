FROM python:3.13-slim

WORKDIR /app
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent/ ./agent/
COPY contracts/ ./contracts/
ENV HTTP_HOST=0.0.0.0 HTTP_PORT=8001
EXPOSE 8001
CMD ["python", "-m", "agent.main"]
