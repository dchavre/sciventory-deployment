#!/bin/bash

# Update and install Chromium and ChromeDriver
apt-get update && apt-get install -y chromium chromium-driver

# Install Python dependencies from requirements.txt
pip install --no-cache-dir -r requirements.txt
