FROM python:3.11-buster

# Install apt-utils to avoid warnings
RUN apt-get update && apt-get install -y apt-utils

# Install system dependencies required for Playwright
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
    libwoff1 \
    libwoff2 \
    fonts-liberation \
    xdg-utils \
    ca-certificates \
    libssl-dev \
    libcurl4-openssl-dev \
    libxml2 \
    libxss1 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright and necessary browsers
RUN pip install playwright && playwright install --with-deps

# Install your application requirements
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt

# Expose port and start the app
EXPOSE 5000
CMD ["python", "app.py"]
