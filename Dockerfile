# Base Environment: Python + Playwright
FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libgconf-2-4 \
    libx11-dev \
    libxcomposite1 \
    libxrandr2 \
    libasound2 \
    libxtst6 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    fonts-liberation \
    libappindicator3-1 \
    libnspr4 \
    libnss3 \
    lsb-release \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Set up a working directory in the container
WORKDIR /app

# Install Python dependencies and Playwright
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install playwright
RUN playwright install

# Copy the rest of the application code
COPY . /app/

# Expose port 5000 for Flask app
EXPOSE 5000

# Run the Flask app with Gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000"]
