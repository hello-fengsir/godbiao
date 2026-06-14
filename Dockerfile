FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi uvicorn jinja2 python-multipart \
    pdfplumber python-docx pytesseract pillow pymupdf \
    aiofiles aiosqlite httpx openpyxl

COPY app.py config.py parser.py llm_client.py models.py bid_api.py import_products.py product_data.xlsx ./
COPY templates/ ./templates/
COPY static/ ./static/

RUN mkdir -p uploads

EXPOSE 8880
CMD ["python3", "app.py"]
