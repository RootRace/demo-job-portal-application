FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt && python -m spacy download en_core_web_sm
CMD ["gunicorn", "app:create_app()", "--workers=1", "--threads=2", "--timeout=120", "--bind", "0.0.0.0:8000"]
