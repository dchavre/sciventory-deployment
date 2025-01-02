# Use the Playwright Python image as the base
FROM mcr.microsoft.com/playwright/python:v1.30.0-focal

# Set the working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps

# Copy the application code into the container
COPY . /app

# Expose port and start the Flask application
EXPOSE 5000
CMD ["python", "app.py"]
