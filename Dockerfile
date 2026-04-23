FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webapp.py .
COPY whisperx_processor.py .
COPY .env .

RUN mkdir -p uploads outputs

EXPOSE 5000

CMD ["python", "webapp.py"]