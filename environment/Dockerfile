FROM python:3.13-slim

WORKDIR /app

COPY environment/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY environment/ ./environment/
COPY contracts/ ./contracts/

ENV HTTP_HOST=0.0.0.0 HTTP_PORT=8000
EXPOSE 8000 50051

CMD ["python", "-m", "environment.main"]
