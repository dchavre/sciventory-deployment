import csv
import os
import requests
import json
import re

from flask import Flask, session, abort, redirect, request, render_template, jsonify, url_for, send_from_directory

import google.auth.transport.requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from pip._vendor import cachecontrol
from functools import wraps
from playwright.sync_api import sync_playwright

app = Flask(__name__)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

client_secrets_file = 'client_secret.json'

os.environ['NO_PROXY'] = 'oauth2.googleapis.com'

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri='https://sciventory-hhs.onrender.com/callback'
)     
            

CSV_FILE = 'data/data.csv'
GHS_CSV_FILE = 'data/ghs_data.csv'
SDS_LINK_FILE = 'data/sds_link.csv'
ROOM_CHECK_FILE = 'data/room_check.csv'


admin_access = os.environ.get("admin_access")
table_access = os.environ.get("table_access")

admin_access = admin_access.replace(" ", ",").split(",")
table_access = table_access.replace(" ", ",").split(",")

app.secret_key = os.environ.get('app.secret_key')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')

with open(client_secrets_file, 'r') as file:
    secrets = json.load(file)
    
GOOGLE_CLIENT_ID = secrets['web']['client_id']
app.secret_key = secrets['web']['client_secret']

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

def login_is_required_table(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'google_id' not in session:
            return abort(401, "Unauthorized: Please log in to access this page.")
        user_email = session.get("gmail")
        if user_email in table_access or user_email in admin_access:
            return f(*args, **kwargs)
        return abort(403, "Forbidden: You do not have permission to access this table.")
    return wrapper

def login_is_required_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'google_id' not in session:
            return abort(401, "Unauthorized: Please log in to access admin features.")
        user_email = session.get("gmail")
        if user_email in admin_access:
            return f(*args, **kwargs)
        return abort(403, "Forbidden: Admin access is required to view this page.")
    return wrapper

def login_is_required_room_view(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'google_id' not in session:
            return abort(401, "Unauthorized: Please log in to access this page.")
        user_email = session.get("gmail")
        if user_email in table_access or user_email in admin_access:
            return f(*args, **kwargs)
        return abort(403, "Forbidden: You do not have permission to view this page.")
    return wrapper

def login_is_required_room_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'google_id' not in session:
            return abort(401, "Unauthorized: Please log in to access admin features.")
        user_email = session.get("gmail")
        if user_email in admin_access:
            return f(*args, **kwargs)
        return abort(403, "Forbidden: Admin access is required for this action.")
    return wrapper

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
                    sds_cache[row[0]] = row[1]
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


def scrape_link(chemical_name):
    # The URL to send the POST request to
    search_url = 'https://chemicalsafety.com/sds1/sds_retriever.php?action=search'


    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',  # or any other relevant headers for the API you're calling
        'Content-Type': 'application/json'
    }

    # Your request payload (the data you are sending)
    payload = {
        "IsContains": False,
        "IncludeSynonyms": False,
        "SearchSdsServer": False,
        "Criteria": [f"name|{chemical_name}"],
        "HostName": "sfs website",
        "Remote": "146.115.118.194",
        "Bee": "stevia",
        "Action": "search",
        "SearchUrl": "",
        "ResultColumns": ["revision_date"]
    }

    # Send the POST request using the .pem certificate for SSL verification
    search_response = requests.post(search_url, json=payload, headers=headers)

    # Check the response
    print(search_response.status_code)

    parsed_data = json.loads(search_response.text)
    first_row = parsed_data['rows'][0]

    id = first_row[0]
    name = first_row[1]
    
    viewer_url = f'https://www.chemicalsafety.com/sds1/sdsviewer.php?id={id}&amp;name={name}' # link to the GHS and SDS information
    
    print(viewer_url)
    
    return viewer_url

def clean_link(sds_links):
    sds_links[0] = re.sub(r'(?i)\bHTTP\b', 'https', sds_links[0])
    sds_links[0] = sds_links[0].replace('&amp;', '&')
    print(sds_links[0])
    return [sds_links[0]]

def scrape_info(viewer_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(viewer_url, wait_until="networkidle")
        page_content = page.content()
        browser.close()
    ghs_matches = re.findall(r'ghs0\d+\.png', page_content)
    sds_links = re.findall(r'href=["\']([^"\']*sds\.chemicalsafety\.com/sds[^"\']*)["\']', page_content)
    sds_link = clean_link(sds_links)
    return ghs_matches, sds_link
    
def scraper(data, ghs_data, sds_data):
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
            try:
                viewer_url = scrape_link(chemical_name)
                ghs_matches, sds_link = scrape_info(viewer_url)
            except IndexError:
                print("Link not found")
                ghs_matches = ['error.png']
                sds_link = ''
                
            ghs_images[chemical_name] = ghs_matches
            sds_links[chemical_name] = sds_link
            
            # Save to cache
            save_ghs_cache(chemical_name, ghs_matches)
            save_sds_cache(chemical_name, sds_link)
    
    return ghs_images, sds_links


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
    
    ghs_data, sds_links = scraper(data, ghs, sds)
    print("GHS Data:", ghs_data)
    print("SDS Link:", sds_links)
    return render_template('table.html', data=data, ghs_data=ghs_data, sds_links=sds_links)

@app.route('/download/raw-csv')
def download_raw():
    try:
        filename = "data.csv" 
        return send_from_directory("data/", filename, as_attachment=True)
    except FileNotFoundError:
        return "File not found!", 404

@app.route('/download/ghs-csv')
def download_ghs():
    try:
        filename = "ghs_data.csv" 
        return send_from_directory("data/", filename, as_attachment=True)
    except FileNotFoundError:
        return "File not found!", 404

@app.route('/download/sds-csv')
def download_sds():
    try:
        filename = "sds_link.csv" 
        return send_from_directory("data/", filename, as_attachment=True)
    except FileNotFoundError:
        return "File not found!", 404

@app.route('/download/room-csv')
def download_room():
    try:
        filename = "room_check.csv" 
        return send_from_directory("data/", filename, as_attachment=True)
    except FileNotFoundError:
        return "File not found!", 404

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
        'Gas Shutoff': 'yes' if request.form.get('gas_shutoff') else '',
        'Power Shutoff': 'yes' if request.form.get('power_shutoff') else '',
        'Eye Wash': 'yes' if request.form.get('eye_wash') else '',
        'Fire Extinguisher': 'yes' if request.form.get('fire_extinguisher') else '',
        'Fire Blanket': 'yes' if request.form.get('fire_blanket') else '',
        'Chemical PPE': 'yes' if request.form.get('chemical_ppe') else '',
        'Fume Hood': 'yes' if request.form.get('fume_hood') else '',
        'Emergency Spill Kits': 'yes' if request.form.get('spill_kits') else '',
        'Gas Burners': 'yes' if request.form.get('gas_burners') else '',
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
    app.run(host='0.0.0.0', port=5000)
