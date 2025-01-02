FROM python:3.10-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER=/usr/bin/chromium-driver

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Expose port
EXPOSE 5000

# Start the app with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
