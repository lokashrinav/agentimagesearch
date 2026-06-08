FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[api,ddgs]"

CMD ["uvicorn", "imgfind.api:app", "--host", "0.0.0.0", "--port", "8000"]
