FROM python:3.10-bullseye

# Add Debian Bullseye repository (explicitly set sources if needed)
RUN echo "deb http://deb.debian.org/debian bullseye main" > /etc/apt/sources.list.d/bullseye.list

# Install basic system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt requirements.txt

# Remove macOS-specific dependencies like mitmproxy-macos from the requirements.txt
RUN sed -i '/mitmproxy-macos/d' requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Expose port and run app
EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
