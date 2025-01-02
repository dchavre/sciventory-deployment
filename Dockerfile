FROM python:3.11-buster
FROM mcr.microsoft.com/playwright/python:v1.30.0-focal

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Install Playwright and necessary browsers
RUN pip install playwright && playwright install --with-deps

# Install your application requirements
COPY . /app
RUN pip install -r requirements.txt

# Expose port and start the app
EXPOSE 5000
CMD ["python", "app.py"]
