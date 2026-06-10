FROM python:3.11-slim

WORKDIR /app

# Install system deps for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
RUN pip install --no-cache-dir \
    fastapi uvicorn jinja2 python-multipart \
    pdfplumber python-docx pytesseract pillow pymupdf \
    aiofiles aiosqlite httpx openpyxl

# Copy app
COPY app.py config.py parser.py llm_client.py models.py import_products.py product_data.xlsx ./
COPY templates/ ./templates/
COPY static/ ./static/

RUN mkdir -p uploads

EXPOSE 8880
CMD ["python3", "app.py"]
