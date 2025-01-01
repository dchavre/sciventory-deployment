import csv

import os
import requests
from flask import Flask, session, abort, redirect, request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
from requests_oauthlib import OAuth2Session
import google.auth.transport.requests
from flask import Flask, render_template, request, jsonify, session, abort, redirect, url_for
from functools import wraps


import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time
from datetime import datetime



app = Flask(__name__)
app.secret_key = os.environ.get('app.secret_key')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

client_secrets_file = 'client_secret.json'

os.environ['NO_PROXY'] = 'oauth2.googleapis.com'

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri='https://sciventory.onrender.com/callback'
)     

CSV_FILE = 'data/data.csv'
GHS_CSV_FILE = 'data/ghs_data.csv'
SDS_LINK_FILE = 'data/sds_link.csv'
ROOM_CHECK_FILE = 'data/room_check.csv'

admin_access = os.environ.get('admin_access')
table_access = os.environ.get('table_access')

# Load data from the CSV file
def load_csv(file):
    try:
        with open(file, newline='') as csvfile:
            reader = csv.reader(csvfile)
            return list(reader)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return []
    
# Load data for room check

if not os.path.exists(ROOM_CHECK_FILE):
    with open(ROOM_CHECK_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Room', 'Gas Shutoff', 'Power Shutoff', 'Eye Wash', 'Fire Extinguisher', 'Fire Blanket', 'Chemical PPE', 'Fume Hood', 'Emergency Spill Kits', 'Gas Burners'])

def load_data():
    with open(ROOM_CHECK_FILE, 'r') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]

# Save data to the CSV file
def save_csv(data):
    with open(CSV_FILE, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(data)
        
def save_data(data):
    with open(ROOM_CHECK_FILE, 'w', newline='') as f:
        if data:  # Only write the header and rows if there is data
            writer = csv.DictWriter(f, fieldnames=data[0].keys())  # Ensure fieldnames are correct
            writer.writeheader()  # Write header
            writer.writerows(data)  # Write rows
        else:
            # Optionally write only the header if you want an empty file after deletion
            writer = csv.DictWriter(f, fieldnames=['Date', 'Room', 'Gas Shutoff', 'Power Shutoff', 'Eye Wash', 'Fire Extinguisher', 'Fire Blanket', 'Chemical PPE', 'Fume Hood', 'Emergency Spill Kits', 'Gas Burners'])
            writer.writeheader()  # Write header for an empty file


def get_chemical(data):   
    return [row[1] for row in data]

def get_name_ghs_sds(data):
    return [row[0] for row in data]

def login_is_required_table(function):
    def wrapper_1(*args, **kwargs):
        if 'google_id' not in session:
            return abort(401)
        elif session["gmail"] in table_access or session["gmail"] in admin_access:
            return function()
        else:
            return abort(404, "You do not have access to this page")
    return wrapper_1

def login_is_required_admin(function):
    def wrapper_2(*args, **kwargs):
        if 'google_id' not in session:
            return abort(401)
        elif session["gmail"] in admin_access:
            return function()
        else:
            return abort(404, "You do not have access to this page")
    return wrapper_2

def login_is_required_room_view(function):
    def wrapper_3(*args, **kwargs):
        if 'google_id' not in session:
            return abort(401)
        elif session["gmail"] in table_access or session["gmail"] in admin_access:
            return function()
        else:
            return abort(404, "You do not have access to this page")
    return wrapper_3

def login_is_required_room_admin(f):
    @wraps(f)
    def wrapper_4(*args, **kwargs):
        if 'google_id' not in session:
            return abort(401)
        if session["gmail"] not in admin_access:
            return redirect(url_for('home'))  # Or any other non-admin route
        return f(*args, **kwargs)
    return wrapper_4

# Load GHS data cache
def load_ghs_cache():
    ghs_cache = {}
    if os.path.exists(GHS_CSV_FILE):
        with open(GHS_CSV_FILE, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:  # Avoid empty rows
                    ghs_cache[row[0]] = row[1].split(",")  # Split image names into a list
    return ghs_cache

def load_sds_cache():
    sds_cache = {}
    if os.path.exists(SDS_LINK_FILE):
        with open(SDS_LINK_FILE, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:  # Avoid empty rows
                    sds_cache[row[0]] = row[1].split(",")  # Split image names into a list
    return sds_cache


# Save new GHS data to the cache
def save_ghs_cache(chemical_name, ghs_images):
    with open(GHS_CSV_FILE, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([chemical_name, ",".join(ghs_images)])
        
def save_sds_cache(chemical_name, sds_link):
    with open(SDS_LINK_FILE, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([chemical_name, ",".join(sds_link)])

def setup_driver():
    service = Service()
    # Configure Chrome options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Initialize WebDriver
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def scrape_chemical(chemical_name):
    try:
        if not chemical_name:
            raise ValueError("Chemical name is required.")

        # Set up the Selenium WebDriver
        driver = setup_driver()

        # Navigate to the target website
        target_url = "https://chemicalsafety.com/sds-search/"
        driver.get(target_url)
        print("Navigated to target URL")
        
        cookies_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "CybotCookiebotDialogBodyButtonAccept"))
        )
        cookies_box.click()

        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'please enter product name (or synonym)')]"))
        )
        
        print("Search box found")

        # Enter the chemical name and submit the search
        search_box.send_keys(chemical_name)
        search_box.send_keys(Keys.RETURN)
        print("Search submitted")
        
        time.sleep(2)
        
        original_window = driver.current_window_handle

        # Wait for the results to load and find the specific link
        try:
            pdf_link = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'https://www.chemicalsafety.com/sds1/sdsviewer.php')]"))
        )   
        except selenium.common.exceptions.TimeoutException:
            print("PDF link not found")
            return(["error.png"], "")
        driver.execute_script("arguments[0].scrollIntoView(true);", pdf_link)
        try:
            pdf_link.click()
        except selenium.common.exceptions.ElementClickInterceptedException:
            print("Element click intercepted, trying again")
            pdf_link.click()
        print("PDF link found")
        
        time.sleep(2)

        p = driver.current_window_handle
        chwd = driver.window_handles
        
        for w in chwd:
            if(w!=p):
                driver.switch_to.window(w)
        
        try:
            WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//img[contains(@src, 'img/ghs0')]"))
        )
        except selenium.common.exceptions.TimeoutException:
            print("No image found")
            page_html = driver.page_source
            sds_link = re.findall(r'href=["\']([^"\']*sds\.chemicalsafety\.com/sds[^"\']*)["\']', page_html)
            print(sds_link)
            return([], sds_link)
        
        
        print("Chemical details page loaded")

        # Get the HTML content of the page
        page_html = driver.page_source
        

        # Extract all instances of "ghs0#.png"
        ghs_matches = re.findall(r'ghs0\d+\.png', page_html)
        print(ghs_matches)
        
        sds_link = re.findall(r'href=["\']([^"\']*sds\.chemicalsafety\.com/sds[^"\']*)["\']', page_html)
        print(sds_link)
        
        # Close the WebDriver
        driver.quit()

        return ghs_matches, sds_link

    except Exception as e:
        if 'driver' in locals():
            driver.quit()
        print(f"Error: {e}")
        raise e

def get_info(data, ghs_data, sds_data):
    chemical_names = get_chemical(data)
    chemical_names_ghs = get_name_ghs_sds(ghs_data)
    chemical_names_sds = get_name_ghs_sds(sds_data)
    
    print(chemical_names==chemical_names_ghs==chemical_names_sds)
    
    ghs_cache = load_ghs_cache()
    sds_cache = load_sds_cache()
    ghs_images = {}
    sds_links = {}

    for chemical_name in chemical_names:
        if chemical_name in ghs_cache and chemical_name in sds_cache:
            # Retrieve cached GHS images
            print(f"Using cached data for: {chemical_name}")
            ghs_images[chemical_name] = ghs_cache[chemical_name]
            sds_links[chemical_name] = sds_cache[chemical_name]
        else:
            # Scrape data if not in cache
            print(f"Scraping data for: {chemical_name}")
            scraped_images, sds_link = scrape_chemical(chemical_name)
            ghs_images[chemical_name] = scraped_images
            sds_links[chemical_name] = sds_link
            # Save to cache
            save_ghs_cache(chemical_name, scraped_images)
            save_sds_cache(chemical_name, sds_link)

    return ghs_images, sds_links

def clean_links(sds_link):
    for chemical_name in sds_link:
        sds_link[chemical_name][0] = re.sub(r'(?i)\bHTTP\b', 'https', sds_link[chemical_name][0])
        sds_link[chemical_name][0] = sds_link[chemical_name][0].replace('&amp;', '&')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    session["gmail"] = id_info.get("email")
    return redirect("/table")
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/table')
@login_is_required_table
def table():
    data = load_csv(CSV_FILE)
    ghs = load_csv(GHS_CSV_FILE)
    sds = load_csv(SDS_LINK_FILE)
    
    ghs_data, sds_links = get_info(data, ghs, sds)
    print("GHS Data:", ghs_data)
    print("SDS Link:", sds_links)
    clean_links(sds_links)
    print(sds_links)
    return render_template('table.html', data=data, ghs_data=ghs_data, sds_links=sds_links)

@app.route('/room-table')
@login_is_required_room_admin
def room_table():
    data = load_data()
    return render_template('room_table.html', data=data)

@app.route('/room-view')
@login_is_required_room_view
def room_view():
    data = load_data()
    return render_template('room_view.html', data=data)

@app.route('/add', methods=['POST'])
def add_entry():
    date = request.form['date']
    room = request.form['room']
    
    # Debugging: print the form data to the console
    print(f"Received form data: Date={date}, Room={room}")
    
    # Capture checkbox values (they are sent as 'on' if checked)
    equipment_checks = {
        'Gas Shutoff': 'on' if request.form.get('gas_shutoff') else '',
        'Power Shutoff': 'on' if request.form.get('power_shutoff') else '',
        'Eye Wash': 'on' if request.form.get('eye_wash') else '',
        'Fire Extinguisher': 'on' if request.form.get('fire_extinguisher') else '',
        'Fire Blanket': 'on' if request.form.get('fire_blanket') else '',
        'Chemical PPE': 'on' if request.form.get('chemical_ppe') else '',
        'Fume Hood': 'on' if request.form.get('fume_hood') else '',
        'Emergency Spill Kits': 'on' if request.form.get('spill_kits') else '',
        'Gas Burners': 'on' if request.form.get('gas_burners') else '',
    }
    
    # Debugging: print the equipment checks to verify checkbox values
    print(f"Checkbox values: {equipment_checks}")
    
    # Create a new entry with the provided date, room, and equipment data
    new_entry = {'Date': date, 'Room': room, **equipment_checks}
    
    # Load current data and append the new entry
    data = load_data()
    data.append(new_entry)
    
    # Debugging: print data before saving to verify new entry
    print(f"Data before saving: {data}")
    
    # Save the updated data back to the CSV
    save_data(data)
    
    return redirect(url_for('room_table'))

@app.route('/delete', methods=['POST'])
def delete_entry():
    # Get the date and room from the form (ensure they're passed correctly)
    date = request.form['date']
    room = request.form['room']
    
    # Read data from the CSV
    data = load_data()

    # Remove the entry where the date and room match
    new_data = [entry for entry in data if not (entry['Date'] == date and entry['Room'] == room)]
    
    # Only save if there are remaining entries after deletion
    if new_data:
        save_data(new_data)
    else:
        # If there are no entries left, save an empty CSV or a new blank row
        save_data([])  # This will create an empty CSV file

    return redirect(url_for('room_table'))


@app.route('/admin')
@login_is_required_admin
def admin():
    data = load_csv(CSV_FILE)
    return render_template('admin.html', data=data)

@app.route('/update', methods=['POST'])
def update():
    updated_data = request.json['data']
    save_csv(updated_data)
    return jsonify({"message": "Table updated successfully!"})

if __name__ == '__main__':
    # Ensure the CSV files exist
    for file in [CSV_FILE, GHS_CSV_FILE]:
        try:
            open(file, 'x').close()
        except FileExistsError:
            pass
    app.run(debug=True)
