# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies for Playwright and other necessary tools
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

# Install Playwright and other dependencies
RUN pip install --no-cache-dir playwright
RUN playwright install --with-deps  # Make sure browsers are installed

# Copy the current directory contents into the container at /app
COPY . /app

# Install any dependencies from requirements.txt
RUN pip install -r requirements.txt

# Expose port 5000 for the app
EXPOSE 5000

# Start the application using Gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000"]
