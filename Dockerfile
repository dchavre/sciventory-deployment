FROM python:3.11-buster

FROM --platform=linux/amd64 python:3.7-alpine

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    libnss3 \
    libgdk-pixbuf2.0-0 \
    libatk1.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxrandr2 \
    libasound2 \
    libatk-bridge2.0-0 \
    libpangocairo-1.0-0 \
    libgbm1 \
    libnspr4 \
    libxshmfence1 \
    libxtst6 \
    libappindicator3-1 \
    libsecret-1-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir playwright
RUN playwright install --with-deps  # Make sure browsers are installed

COPY . /app

RUN pip install -r requirements.txt

EXPOSE 5000

CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000"]
