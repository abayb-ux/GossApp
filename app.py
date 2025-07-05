import os
from huggingface_hub import InferenceClient, login
import gradio as gr
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime, timedelta, date
import time
import uuid
import hashlib
from requests.auth import HTTPBasicAuth
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from google.oauth2.service_account import Credentials




def get_tokens_from_gas():
    """Get tokens from Google Apps Script endpoint"""
    try:
        url = "https://script.google.com/macros/s/AKfycbwyBKM5VOu8C3MmbRT63_uijB2rxJZrRxG6Wmr5qypnetj3F2ba6LYpxWdchBF7fHFQuw/exec"
        response = requests.get(url)
        data = response.json()
        
        if isinstance(data, dict):
            # Clean up the keys (remove any whitespace or formatting issues)
            tokens = {k.strip(): v for k, v in data.items() if v}
            print(f"Loaded {len(tokens)} tokens from GAS endpoint")
            return tokens
        return {}
    except Exception as e:
        print(f"Error loading tokens from GAS: {str(e)}")
        return {}

# Function to get tokens from Google Sheet
def get_tokens_from_sheet():
    """Get tokens from all sheets in the spreadsheet"""
    try:
        SPREADSHEET_ID = "12I6kP5mRZxsQB-NpvWTqGZ15ROPRbIdXDmYj9xIwSeM"
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        tokens = {}
        
        for worksheet in spreadsheet.worksheets():
            try:
                records = worksheet.get_all_records()
                for record in records:
                    key = record.get('Key', '').strip()
                    value = record.get('Value', '').strip()
                    if key and value:
                        tokens[key] = value
            except Exception as e:
                print(f"Error reading sheet {worksheet.title}: {str(e)}")
                continue
                
        return tokens
        
    except Exception as e:
        print(f"Error reading tokens from Google Sheet: {str(e)}")
        return {}
        
def get_token(key):
    # First try environment variables
    value = os.getenv(key)
    if value:
        return value
    
    # Then try GAS endpoint
    tokens = get_tokens_from_gas()
    if key in tokens:
        return tokens[key]
    
    # Finally try the old spreadsheet method as fallback
    tokens = get_tokens_from_sheet()
    return tokens.get(key)
    
def get_token(key):
    # First try environment variables
    value = os.getenv(key)
    if value:
        print(f"Loaded {key} from environment variables")
        return value
    
    # Then try GAS endpoint
    tokens = get_tokens_from_gas()
    if key in tokens:
        print(f"Loaded {key} from GAS endpoint")
        return tokens[key]
    
    # Finally try the old spreadsheet method as fallback
    tokens = get_tokens_from_sheet()
    if key in tokens:
        print(f"Loaded {key} from spreadsheet")
        return tokens.get(key)
    
    print(f"Token {key} not found in any source")
    return None

# Now replace all your os.getenv() calls with get_tokens():
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY") or get_token("FLW_SECRET_KEY")
FLW_ENCRYPTION_KEY = os.getenv("FLW_ENCRYPTION_KEY") or get_token("FLW_ENCRYPTION_KEY")
FLW_PUBLIC_KEY = os.getenv("FLW_PUBLIC_KEY") or get_token("FLW_PUBLIC_KEY")
FLW_MERCHANT_EMAIL = os.getenv("FLW_MERCHANT_EMAIL") or get_token("FLW_MERCHANT_EMAIL")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID") or get_token("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET") or get_token("PAYPAL_SECRET")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY") or get_token("PAYSTACK_SECRET_KEY")
HF_TOKEN = os.getenv("HF_TOKEN") or get_token("HF_TOKEN")


OWNER_EMAIL = "pascaladiema@gmail.com"  # Dynamical
BATTERY_SHEET_ID = "1SDYK3i2GOv8a0tF4Z1IuGbsrd-W-Or9bXSaUusZ3tuA"
WORDS_PER_DOLLAR = 9500  # 9500 words = $1.00
MAX_WORDS = WORDS_PER_DOLLAR  # 100% battery = 0 words used
BATTERY_COLORS = {
    100: "#00FF00",  # Green
    75: "#ADFF2F",   # Green-Yellow
    50: "#FFFF00",   # Yellow
    25: "#FFA500",   # Orange
    10: "#FF0000",    # Red
    0: "#8B0000"      # Dark Red
}

SPONSOR = "default"  # Set this to the sponsor name or leave as "default" for default branding
TRAINER_SHEET_ID = "1GiA8pxZn04aUA-OKwcANvfJ_CpChooF2mUQxiJ_i2-s"

def record_trainer_info(email, client_email, freelancer_email, freelancer_link, seal):
    """Record trainer information to Google Sheet"""
    try:
        sheet = get_or_create_sheet(TRAINER_SHEET_ID, "Trainers")
        
        # Check if seal matches
        is_valid, _ = verify_chatbot_seal(email, seal)
        if not is_valid:
            return gr.Markdown("<div class='auth-status error'>❌ Invalid Chatbot Seal</div>")
            
        # Check if this client-freelancer pair already exists
        records = sheet.get_all_records()
        existing = next((r for r in records if 
                       str(r.get('Client Email', '')).lower() == client_email.lower() and
                       str(r.get('Freelancer Email', '')).lower() == freelancer_email.lower()), None)
        
        if existing:
            return gr.Markdown("<div class='auth-status success'>✅ Trainer info already recorded</div>")
            
        # Append new record
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            client_email,
            freelancer_email,
            freelancer_link,
            str(uuid.uuid4())  # International Chatbot Driver's License Number
        ])
        return gr.Markdown("<div class='auth-status success'>✅ Trainer info recorded successfully</div>")
    except Exception as e:
        print(f"Error recording trainer info: {str(e)}")
        return gr.Markdown("<div class='auth-status error'>❌ Error recording trainer info</div>")

def check_freelancer_earnings(freelancer_email):
    """Check if freelancer is eligible for earnings"""
    try:
        # First get all clients this freelancer trained
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_key(TRAINER_SHEET_ID)
        clients = []
        
        for worksheet in spreadsheet.worksheets():
            records = worksheet.get_all_records()
            for record in records:
                if str(record.get('Freelancer Email', '')).lower() == freelancer_email.lower():
                    clients.append({
                        'client_email': record.get('Client Email', ''),
                        'license': record.get('International Chatbot Driver\'s License Number', ''),
                        'link': record.get('Freelancer Link', '')
                    })
        
        if not clients:
            return False, "No clients found for this freelancer"
            
        # Now check each client's payment history
        eligible = []
        total_earnings = 0
        
        for client in clients:
            # Check all payment gateways
            gateways = [
                verify_flutterwave_transaction,
                verify_paystack_transaction,
                verify_paypal_transaction
            ]
            
            client_has_paid = False
            for verifier in gateways:
                is_valid, message = verifier(client['client_email'])
                if is_valid:
                    # Extract amount from message
                    amount_match = re.search(r"payment of ([\d,.]+)", message)
                    if amount_match:
                        amount_str = amount_match.group(1).replace(',', '')
                        try:
                            amount = float(amount_str)
                            if amount >= 12:  # $12 threshold
                                client_has_paid = True
                                total_earnings += 5  # $5 per qualified client
                                break
                        except ValueError:
                            continue
            
            if client_has_paid:
                eligible.append(client)
        
        if eligible:
            message = f"""
            <div class='auth-status success'>
                <strong>🎉 Earnings Available: ${total_earnings} USD</strong><br><br>
                <strong>Qualified Clients:</strong> {len(eligible)}<br>
                <strong>Freelancer Link:</strong> {eligible[0]['link']}<br><br>
                <a href="https://wa.link/x2wdpl" target="_blank" style="
                    padding: 8px 16px;
                    background: #4CAF50;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                ">Claim Earnings Here</a>
            </div>
            """
            return True, message
        else:
            client_count = len(clients)
            message = f"""
            <div class='auth-status'>
                <strong>Potential Earnings: $5 USD per qualified client</strong><br><br>
                <strong>Clients Trained:</strong> {client_count}<br>
                <strong>Qualified Clients:</strong> 0 (needs to have Loaded $12+ worth of AI-time or Set a Subscription)<br><br>
                <div style="color: #666; font-size: 0.9em;">
                    You'll earn $5 USD when a client you trained loads AI-time worth $12+ USD. A CLAIMS button will appear to collect you earnings<br>
                    Happy freelancing! Keep training  more GossApp chatbots for clients, politely ask your current client to refer more clients.
                </div>
            </div>
            """
            return False, message
            
    except Exception as e:
        print(f"Error checking freelancer earnings: {str(e)}")
        return False, f"❌ Error checking earnings: {str(e)}"

def get_chatbot_greeting(email=OWNER_EMAIL):
    """Generate greeting message by fetching data from the main GAS endpoint"""
    try:
        gas_url = "https://script.google.com/macros/s/AKfycbyd7_adt6ewugv6KmtLNEBdSZVfQYO0ZwLl1QoOPP-B1f7JlAkp-BK65pnWl1t-irF8/exec"
        params = {'email': email}
        
        response = requests.get(gas_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                # Use the pre-formatted HTML if available
                if 'greetingHTML' in data:
                    return data['greetingHTML']
                # Fallback to old format if needed
                greeting_data = data.get('greeting', {})
                return format_greeting_html(
                    name=greeting_data.get('name', 'GossApp'),
                    icon=greeting_data.get('icon'),
                    label=greeting_data.get('label')
                )
    
    except Exception as e:
        print(f"Error fetching greeting data: {str(e)}")
    
    # Final fallback
    return format_greeting_html(
        name="GossApp",
        icon="https://i.imgur.com/5chIGdn.gif",
        label="Powered by DeepChat"
    )






# The rest of your app.py remains exactly the sames...


def parse_custom_timestamp(timestamp_str):
    """Parse timestamp from Google Sheets into a datetime object"""
    if not timestamp_str or str(timestamp_str).strip() == "":
        return datetime.min
        
    try:
        # First try to parse as datetime object (direct from sheet)
        if isinstance(timestamp_str, (datetime, date)):
            return timestamp_str if isinstance(timestamp_str, datetime) else datetime.combine(timestamp_str, datetime.min.time())
            
        # Try parsing as string in various formats
        timestamp_str = str(timestamp_str).strip()
        formats = [
            "%m/%d/%Y %H:%M:%S",  # Google Sheets default
            "%Y-%m-%d %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d/%m/%Y %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%d %B %Y %H:%M",     # 14 April 2024 15:30
            "%B %d, %Y %H:%M",    # April 14, 2024 15:30
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
                
        # If all parsing fails, return minimal datetime
        return datetime.min
    except Exception as e:
        print(f"Error parsing timestamp '{timestamp_str}': {e}")
        return datetime.min

### GAS-FREE PROFILE DATA FUNCTIONS ###

def get_profile_data(email=OWNER_EMAIL):
    """Fetch and combine all profile data from Google Sheets"""
    try:
        # Load main profile data
        profile_data = load_profile_data(email)
        
        # Load personality and knowledge
        personality_data = load_personality_data(email)
        if personality_data:
            profile_data.update(personality_data)
        
        # Load social links
        social_data = load_social_links(email)
        profile_data['social_links'] = social_data
        
        # Load chatbot links
        chatbot_links = get_chatbot_links(email)
        profile_data['chatbot_links'] = chatbot_links
        
        # Generate complete HTML
        html_content = generate_profile_html(profile_data)
        
        return {
            'status': 'success',
            'data': profile_data,
            'html': html_content,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Error in get_profile_data: {str(e)}")
        return {
            'status': 'error',
            'message': str(e),
            'html': '<div>Error loading profile data</div>'
        }

def check_and_delete_owner_data_if_inactive():
    """
    Checks transaction history for OWNER_EMAIL across all payment gateways.
    If no transactions found in last 60 days, triggers account deletion.
    """
    # Check each payment gateway
    gateways = [
        verify_flutterwave_transaction,
        verify_paystack_transaction,
        verify_paypal_transaction
    ]
    
    has_recent_transaction = False
    last_transaction_date = None
    
    for verifier in gateways:
        is_valid, message = verifier(OWNER_EMAIL)
        if is_valid:
            # Extract date from message if possible
            if "payment of" in message:
                try:
                    # Try to find date in message
                    date_str = re.search(r"(\d{4}-\d{2}-\d{2})|(\d{2}/\d{2}/\d{4})", message)
                    if date_str:
                        trans_date = datetime.strptime(date_str.group(), "%Y-%m-%d") if "-" in date_str.group() else datetime.strptime(date_str.group(), "%m/%d/%Y")
                        if not last_transaction_date or trans_date > last_transaction_date:
                            last_transaction_date = trans_date
                except:
                    pass
            has_recent_transaction = True
    
    # If no transactions found at all
    if not has_recent_transaction:
        # Call the deletion function
        deletion_url = "https://script.google.com/macros/s/AKfycbwjMhxpdx-3NCQ3gtBQu60NDyEhDm3Xfb6SOluGiK1uHQB6dT6ZHX4OfYFjSDT_eShHDg/exec"
        payload = {
            'email': OWNER_EMAIL
        }
        try:
            response = requests.post(deletion_url, data=payload)
            if response.json().get('success'):
                print(f"✅ A Chatbot you own/may know is no longer active {OWNER_EMAIL}")
            else:
                print(f"❌ Failed to delete data: {response.json().get('message', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Error calling deletion function: {str(e)}")
    elif last_transaction_date and (datetime.now() - last_transaction_date).days > 60:
        # Found transactions but all are older than 60 days
        deletion_url = "https://script.google.com/macros/s/AKfycbwjMhxpdx-3NCQ3gtBQu60NDyEhDm3Xfb6SOluGiK1uHQB6dT6ZHX4OfYFjSDT_eShHDg/exec"
        payload = {
            'email': OWNER_EMAIL
        }
        try:
            response = requests.post(deletion_url, data=payload)
            if response.json().get('success'):
                print(f"✅ A Chatbot you own/may know is no longer active {OWNER_EMAIL}")
            else:
                print(f"❌ Failed to delete data: {response.json().get('message', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Error calling deletion function: {str(e)}")        

def load_profile_data(email=OWNER_EMAIL):
    """Load main profile data from all sheets in the spreadsheet"""
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1EPpGHwgBSCiEa9jtBMnws0nrUuxO4CwohMRTh-GhPWc"
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_url(sheet_url)
        user_record = None
        
        # Search all sheets for the user's records
        for worksheet in spreadsheet.worksheets():
            try:
                records = worksheet.get_all_records()
                found = next((r for r in records if str(r.get('Email', '')).lower() == email.lower()), None)
                if found:
                    user_record = found
                    break
            except Exception as e:
                print(f"Error reading sheet {worksheet.title}: {str(e)}")
                continue
                
        if not user_record:
            return get_default_data()
            
        return {
            'Name': user_record.get('Name', 'John Doe'),
            'Avatar': user_record.get('Avatar', 'https://i.imgur.com/R39UNfU.png'),
            'Wallpaper': user_record.get('Wallpaper', 'https://i.imgur.com/qNgshje.png'),
            'Username': user_record.get('Username', '@JohnDoe'),
            'Title': user_record.get('Title', 'GossApp Chatbot'),
            'Specialization': user_record.get('Specialization', 'How to train a chatbot'),
            'Quote': user_record.get('Quote', 'What The Chat'),
            'Experience': user_record.get('Experience', 'years'),
            'Hobbies': user_record.get('Hobbies', 'Your command'),
            'Facebook': user_record.get('Facebook', 'https://www.facebook.com'),
            'TikTok': user_record.get('TikTok', 'https://www.tiktok.com'),
            'X': user_record.get('X', 'https://x.com'),
            'LinkedIn': user_record.get('LinkedIn', 'https://www.linkedin.com'),
            'Upwork': user_record.get('Upwork', 'https://www.upwork.com'),
            'WhatsApp': user_record.get('WhatsApp', 'https://www.whatsapp.com'),
            'YouTube': user_record.get('YouTube', 'https://www.youtube.com/')
        }
        
    except Exception as e:
        print(f"Error loading profile data: {str(e)}")
        return get_default_data()

def load_personality_data(email=OWNER_EMAIL):
    """Load personality and knowledge from all sheets in the spreadsheet"""
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1_XRocKV4pY-n19xQmX3Hz5lvPIhowJUf-fBAYmgFlkw"
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_url(sheet_url)
        user_records = []
        
        # Collect records from all sheets
        for worksheet in spreadsheet.worksheets():
            try:
                records = worksheet.get_all_records()
                user_records.extend([r for r in records if str(r.get('Email', '')).lower() == email.lower()])
            except Exception as e:
                print(f"Error reading sheet {worksheet.title}: {str(e)}")
                continue
                
        if not user_records:
            return None
            
        # Get most recent record across all sheets
        latest = max(
            user_records,
            key=lambda x: parse_custom_timestamp(x.get('Timestamp', '')))
            
        return {
            'personality': latest.get('Personality', ''),
            'knowledge_base': latest.get('Knowledge Base', '')
        }
        
    except Exception as e:
        print(f"Error loading personality data: {str(e)}")
        return None


def generate_profile_html(profile_data):
    """Generate complete profile HTML with all sections"""
    # Social links HTML
    social_links_html = """
    <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin: 5px 0;">
    """
    
    social_platforms = {
        'Facebook': ('Facebook', 'https://cdn-icons-png.flaticon.com/512/124/124010.png'),
        'TikTok': ('TikTok', 'https://cdn-icons-png.flaticon.com/512/3046/3046121.png'),
        'X': ('X', 'https://i.imgur.com/oDAREUD.jpeg'),
        'LinkedIn': ('LinkedIn', 'https://cdn-icons-png.flaticon.com/512/3536/3536505.png'),
        'Upwork': ('Upwork', 'https://i.imgur.com/DN6GekY.png'),
        'WhatsApp': ('WhatsApp', 'https://cdn-icons-png.flaticon.com/512/220/220236.png'),
        'YouTube': ('YouTube', 'https://cdn-icons-png.flaticon.com/512/1384/1384060.png')
        
    }
    
    for platform, (display_name, icon) in social_platforms.items():
        if profile_data.get(platform):
            social_links_html += f"""
            <a href="{profile_data[platform]}" target="_blank" style="text-decoration: none;">
                <img src="{icon}" width="24" style="border-radius: 50%; transition: transform 0.3s ease;" 
                     onmouseover="this.style.transform='scale(1.2)'" 
                     onmouseout="this.style.transform='scale(1)'"
                     title="{display_name}">
            </a>
            """
    
    social_links_html += "</div>"
    
    # Main profile HTML
    return f"""
<div style="display: flex; flex-direction: column; gap: 3px; color: #333333 !important;">
    <div style="display: flex; gap: 5px; flex-wrap: wrap; align-items: center;">
        <img src="https://i.imgur.com/5chIGdn.gif" width="25" style="border-radius: 8px;">
        <img src="https://i.imgur.com/PznT4qo.png" width="160" style="border-radius: 2px;">
    </div>
    <div style="position: relative; width: 100%;">
        <img src="{profile_data.get('Wallpaper')}" 
             style="width: 251px; border-radius: 8px; height: 100%; object-fit: cover;">
        <div style="position: absolute; bottom: -55px; left: 1px; 
                    width: 100px; height: 100px; border-radius: 50%; 
                    border: px solid white; overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);">
            <img src="{profile_data.get('Avatar')}" 
                 style="width: 100%; height: 100%; object-fit: cover;">
        </div>
    </div>
    <br>
    
    <div style="display: flex; gap: 5px; flex-wrap: wrap; align-items: center; margin-top: 25px;">  
        <h3 style="color: #333333 !important; margin: 0;">{profile_data.get('Name')}</h3>
        <img src="https://i.imgur.com/cfT7uDM.png" 
             width="15" style="border-radius: 2px;">
    </div>
    
    <span style="color: #333333 !important; margin: 0; font-size: 15px !important;">{profile_data.get('Username')}</span>
    
    <p style="color: #333333 !important; margin: 3px 0;">
        <strong style="color: #333333 !important;">{profile_data.get('Title')}</strong><br>
        {profile_data.get('Specialization')}
    </p>
    <p style="color: #333333 !important; margin: 3px 0;">
        <strong style="color: #333333 !important;">Summary:</strong> {profile_data.get('Summary')}<br>
        <strong style="color: #333333 !important;">Experience:</strong> {profile_data.get('Experience')}<br>
        <strong style="color: #333333 !important;">Hobbies:</strong> {profile_data.get('Hobbies')}<br>
        <strong style="color: #333333 !important;">Quote:</strong> "{profile_data.get('Quote')}"
    </p>
    
    {social_links_html}

</div>
"""

def load_data(refresh=True, email=OWNER_EMAIL):
    """Main data loading function - now email aware"""
    try:
        profile_data = get_profile_data(email)
        
        if profile_data['status'] == 'success':
            # Ensure all required keys exist
            data = profile_data['data']
            return {
                'bio': data.get('bio', get_default_data()['bio']),
                'avatar_url': data.get('Avatar', get_default_data()['avatar_url']),
                'knowledge_base': data.get('knowledge_base', get_default_data()['knowledge_base']),
                'personality': data.get('personality', get_default_data()['personality']),
                'chatbot_links': data.get('chatbot_links', get_default_data()['chatbot_links']),
                'social_links': data.get('social_links', get_default_data()['social_links']),
                'Name': data.get('Name', 'GossApp')  # Add this line to ensure Name is available
            }
    except Exception as e:
        print(f"Error loading data: {e}")
    
    return get_default_data()


def get_chatbot_links(email=OWNER_EMAIL):
    """Fetch chatbot links for specific user from all sheets"""
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1DqZcXRRj00NKD7jjzScy5BZih4V11x4rQu-M_ygzOrE"
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_url(sheet_url)
        user_links = {"Family": [], "Friends": [], "Business": []}
        
        # Search all sheets for the user's links
        for worksheet in spreadsheet.worksheets():
            try:
                records = worksheet.get_all_records()
                for record in records:
                    if str(record.get('Email', '')).lower() == email.lower():
                        classification = record.get('Classification', '').capitalize()
                        html = record.get('Chatbot Clickable HTML', '')
                        
                        if html and classification in user_links:
                            user_links[classification].append(html)
            except Exception as e:
                print(f"Error reading sheet {worksheet.title}: {str(e)}")
                continue
        
        return user_links
        
    except Exception as e:
        print(f"Error loading chatbot links: {str(e)}")
        return {"Family": [], "Friends": [], "Business": []}

def load_social_links(email=OWNER_EMAIL):
    """Load social links for specific user from all sheets"""
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1jjjy7xlWlmIHBJU1Ia8z9k5fBHSUHZtr4cM-2eFeAG0"
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_url(sheet_url)
        user_record = None
        
        # Search all sheets for the user's record
        for worksheet in spreadsheet.worksheets():
            try:
                records = worksheet.get_all_records()
                found = next((r for r in records if str(r.get('Email', '')).lower() == email.lower()), None)
                if found:
                    user_record = found
                    break
            except Exception as e:
                print(f"Error reading sheet {worksheet.title}: {str(e)}")
                continue
        
        if not user_record:
            return {}
            
        return {
            "facebook": user_record.get('Facebook', ''),
            "tiktok": user_record.get('TikTok', ''),
            "x": user_record.get('X', ''),
            "linkedin": user_record.get('LinkedIn', ''),
            "upwork": user_record.get('Upwork', ''),
            "whatsapp": user_record.get('WhatsApp', ''),
            "youtube": user_record.get('YouTube', '')
        }
        
    except Exception as e:
        print(f"Error loading social links: {str(e)}")
        return {}

def get_or_create_sheet(spreadsheet_id, sheet_name=None):
    """Get a sheet, creating new one if needed or if current is full"""
    scope = ['https://www.googleapis.com/auth/spreadsheets',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
    except Exception as e:
        print(f"Error opening spreadsheet {spreadsheet_id}: {str(e)}")
        return None

    # If no sheet name provided, use the first sheet
    if not sheet_name:
        sheet = spreadsheet.sheet1
        # Check if sheet is approaching limit (Google Sheets limit is 5M cells)
        if sheet.row_count * sheet.col_count > 4000000:  # Leave buffer
            new_sheet_name = f"Sheet_{len(spreadsheet.worksheets()) + 1}_{datetime.now().strftime('%Y%m%d')}"
            sheet = spreadsheet.add_worksheet(title=new_sheet_name, rows=1000, cols=20)
            # Copy headers from first sheet if exists
            if len(spreadsheet.worksheets()) > 1:
                headers = spreadsheet.sheet1.row_values(1)
                if headers:
                    sheet.append_row(headers)
        return sheet
    
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        # Check if current sheet is full
        if sheet.row_count * sheet.col_count > 4000000:
            new_sheet_name = f"{sheet_name}_{len([ws for ws in spreadsheet.worksheets() if ws.title.startswith(sheet_name)]) + 1}"
            sheet = spreadsheet.add_worksheet(title=new_sheet_name, rows=1000, cols=20)
            # Copy headers if they exist
            headers = spreadsheet.worksheet(sheet_name).row_values(1)
            if headers:
                sheet.append_row(headers)
        return sheet
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
        return sheet

def get_all_sheets_data(spreadsheet_id, email=None):
    """Get all records from all sheets in a spreadsheet, optionally filtered by email"""
    scope = ['https://www.googleapis.com/auth/spreadsheets',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        all_records = []
        
        for worksheet in spreadsheet.worksheets():
            try:
                records = worksheet.get_all_records()
                if email:
                    # Filter records by email if provided
                    filtered = [r for r in records if str(r.get('Email', '')).lower() == email.lower()]
                    all_records.extend(filtered)
                else:
                    all_records.extend(records)
            except Exception as e:
                print(f"Error reading sheet {worksheet.title}: {str(e)}")
                continue
                
        return all_records
    except Exception as e:
        print(f"Error opening spreadsheet {spreadsheet_id}: {str(e)}")
        return []

def find_record_in_all_sheets(spreadsheet_id, email):
    """Search for a record across all sheets in a spreadsheet"""
    scope = ['https://www.googleapis.com/auth/spreadsheets',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
    except Exception as e:
        print(f"Error opening spreadsheet {spreadsheet_id}: {str(e)}")
        return None

    for worksheet in spreadsheet.worksheets():
        records = worksheet.get_all_records()
        for record in records:
            if str(record.get('Email', '')).lower() == email.lower():
                return record
    return None

def check_certificate_eligibility(email):
    """Check if email exists in any of the specified sheets"""
    sheet_ids = [
        '1ERi9ilsxqOTgVs8Lt0nVfO8HZiwkiBSUanRXMcMEMTY',  # Profile Sheet
        '1EPpGHwgBSCiEa9jtBMnws0nrUuxO4CwohMRTh-GhPWc',  # Main Data
        '1_XRocKV4pY-n19xQmX3Hz5lvPIhowJUf-fBAYmgFlkw',  # Personality
        '1jjjy7xlWlmIHBJU1Ia8z9k5fBHSUHZtr4cM-2eFeAG0',  # Social Links
        '1DqZcXRRj00NKD7jjzScy5BZih4V11x4rQu-M_ygzOrE',  # Chatbot Links
        '1BYmqjop3vy4rpkLPGJc1NGSjj2vCwTH7iEXPNsIQEmQ'   # Chat History
    ]
    
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    
    for sheet_id in sheet_ids:
        try:
            sheet = client.open_by_key(sheet_id).sheet1
            records = sheet.get_all_records()
            if any(str(record.get('Email', '')).lower() == email.lower() for record in records):
                return True
        except Exception as e:
            print(f"Error checking sheet {sheet_id}: {str(e)}")
    
    return False

def generate_certificate_id(email, name):
    """Generate a verifiable unique ID"""
    timestamp = datetime.now().strftime("%Y%m%d")
    unique_str = f"{email}-{name}-{timestamp}-{uuid.uuid4()}"
    return hashlib.sha256(unique_str.encode()).hexdigest()[:16].upper()

def generate_certificate(name, email):
    """Generate certificate HTML with centered name on background image"""

    
    if not name:
        return "<div class='auth-status error'>❌ Please enter your name</div>"
    
    cert_id = generate_certificate_id(email, name)
    date_str = datetime.now().strftime("%B %d, %Y")
    
    # Record the certificate issuance
    record_certificate_issuance(email, name, cert_id)
    
    return f"""
<div class="certificate-container">
    <div class="certificate-background"></div>
    <div class="certificate-overlay">
        <div class="recipient-name">{name}</div>
        <div class="certificate-details">
            <div class="certificate-id">Certificate ID: {cert_id}</div>
            <div class="certificate-date">Issued: {date_str}</div>
        </div>
    </div>
    <div class="screenshot-instructions" style="
        text-align: center; 
        margin-top: 20px;
        font-size: 14px;
        color: #555;
        position: relative;
        z-index: 3;
    ">
        <p>📸 Please take a screenshot of this certificate</p>
    </div>
</div>
"""

def record_certificate_issuance(email, name, cert_id):
    """Record certificate with full details using multi-sheet support"""
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1LOInTcC4SnNGQroxgyzTRGw7nyaK7LG-3J0o9uDfrNs"
        sheet_id = "1LOInTcC4SnNGQroxgyzTRGw7nyaK7LG-3J0o9uDfrNs"
        
        sheet = get_or_create_sheet(sheet_id)
        if not sheet:
            return False
            
        sheet.append_row([
            datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
            email,
            name,
            "CERTIFICATE_ISSUED",
            cert_id,
            "VALID"  # Status field for future revocation
        ])
        return True
    except Exception as e:
        print(f"Error recording certificate: {str(e)}")
        return False

# [Previous functions like load_profile_data, load_personality_data, etc.]

def save_chat_history(email, user_message, bot_response):
    """Save chat history to appropriate sheet (creating new if needed)"""
    try:
        SPREADSHEET_ID = "1BYmqjop3vy4rpkLPGJc1NGSjj2vCwTH7iEXPNsIQEmQ"
        scope = ['https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = get_or_create_sheet(SPREADSHEET_ID, "ChatHistory")
        
        # Get headers if they exist
        headers = []
        try:
            headers = sheet.row_values(1)
        except:
            pass
            
        # If no headers, add them
        if not headers:
            headers = ["Timestamp", "Email", "User Message", "Bot Message"]
            sheet.append_row(headers)
            
        # Append new row
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now_str, email, user_message, bot_response])
        
    except Exception as e:
        print(f"Error saving chat history: {str(e)}")

def load_chat_history(email=OWNER_EMAIL):
    """Load chat history for specific user from all sheets"""
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1BYmqjop3vy4rpkLPGJc1NGSjj2vCwTH7iEXPNsIQEmQ"
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_url(sheet_url)
        user_history = []
        
        # Collect history from all sheets
        for worksheet in spreadsheet.worksheets():
            try:
                records = worksheet.get_all_records()
                user_history.extend([r for r in records if str(r.get('Email', '')).lower() == email.lower()])
            except Exception as e:
                print(f"Error reading sheet {worksheet.title}: {str(e)}")
                continue
        
        # Sort by timestamp (newest first)
        user_history.sort(
            key=lambda x: parse_custom_timestamp(x.get('Timestamp', '')),
            reverse=True
        )
        
        # Format as HTML
        html = """
        <div style="
            max-height: 500px;
            overflow-y: auto;
            padding: 10px;
            background: #f9f9f9;
            border-radius: 8px;
        ">
        <style>
            .chat-entry {
                margin-bottom: 15px;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }
            .timestamp {
                font-size: 0.8em;
                color: #666;
                margin-bottom: 5px;
            }
            .user-message {
                background: #e3f2fd;
                padding: 8px;
                border-radius: 8px;
                margin: 5px 0;
            }
            .bot-message {
                background: #f1f1f1;
                padding: 8px;
                border-radius: 8px;
                margin: 5px 0;
            }
        </style>
        """
        
        for entry in user_history:
            html += f"""
            <div class="chat-entry">
                <div class="timestamp">{entry.get('Timestamp', '')}</div>
                <div class="user-message"><strong>User:</strong> {entry.get('User Message', '')}</div>
                <div class="bot-message"><strong>Bot:</strong> {entry.get('Bot Message', '')}</div>
            </div>
            """
        
        html += "</div>"
        
        return html
        
    except Exception as e:
        print(f"Error loading chat history: {str(e)}")
        return "<div>Error loading chat history</div>"

def fetch_currency_rate(base="USD"):
    try:
        # Get rates for all supported currencies from the API
        symbols = ",".join(VALID_CURRENCIES)
        url = f"https://api.exchangerate.host/latest?base={base}&symbols={symbols}"
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200 and data.get("success"):
            return data.get("rates", {})
        else:
            raise Exception("Currency API error")
            
    except Exception as e:
        print(f"Currency fetch error: {str(e)}")
        # Fallback rates (approximate as of mid-2024)
        return {
            "USD": 1.0,      # US Dollar (base)
            "KES": 130.0,    # Kenyan Shilling
            "NGN": 1300.0,   # Nigerian Naira
            "GHS": 13.20,    # Ghanaian Cedi
            "ZAR": 18.50,    # South African Rand
            "UGX": 3700.0,   # Ugandan Shilling
            "TZS": 2500.0,   # Tanzanian Shilling
            "AED": 3.67,     # UAE Dirham
            "EUR": 0.93,     # Euro
            "GBP": 0.79,     # British Pound
            "INR": 83.50,    # Indian Rupee
            "JPY": 155.0,    # Japanese Yen
            "CAD": 1.36,     # Canadian Dollar
            "AUD": 1.50,     # Australian Dollar
            "CNY": 7.25,     # Chinese Yuan
            "RUB": 90.0,     # Russian Ruble
            "BRL": 5.20,     # Brazilian Real
            "MXN": 17.50,    # Mexican Peso
            "SAR": 3.75,     # Saudi Riyal
            "TRY": 32.0,     # Turkish Lira
            "KRW": 1350.0,  # South Korean Won
            "IDR": 16000.0,  # Indonesian Rupiah
            "PHP": 58.0,     # Philippine Peso
            "THB": 36.50,    # Thai Baht
            "VND": 25000.0,  # Vietnamese Dong
            "MYR": 4.70,     # Malaysian Ringgit
            "XAF": 600.0,     # CFA Franc BEAC
            "XOF": 600.0,     # CFA Franc BCEAO
            # Add more currencies as needed...
        }

def create_flutterwave_link(email, amount, currency):
    try:
        FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY") or get_token("FLW_SECRET_KEY")  # 👈 add this

        VALID_CURRENCIES = ["USD", "KES", "NGN", "GHS", "ZAR", "UGX", "TZS", "AED", "ALL", "ARS", "AUD", "BGN", "BHD", "BWP", "BND", "BRL", "CAD", "CHF", "CLP", "CRC", "CNY", "COP", "CZK", "DKK", "DOP", "EUR", "DZD", "EGP", "GBP", "GMD", "GTQ", "HKD", "HNL", "HUF", "IDR", "IQD", "ILS", "INR", "ISK", "JOD", "JPY", "KHR", "KRW", "KWD", "LBP", "LKR", "LYD", "MAD", "MOP", "MUR", "MWK", "MXN", "MYR", "NOK", "NZD", "OMR", "PAB", "PEN", "PHP", "PLN", "PYG", "QAR", "RUB", "RWF", "SAR", "SDD", "SEK", "SGD", "SLL", "SYP", "THB", "TND", "TRY", "TWD", "VEF", "VND", "XAF", "XOF", "YER", "ZMW", "ZWD"]
        currency = currency.upper().strip()
        if currency not in VALID_CURRENCIES:
            return gr.Markdown(f"<div class='auth-status error'>❌ Unsupported currency code '{currency}' for Flutterwave</div>")

        rates = fetch_currency_rate()
        if not rates or currency not in rates:
            return gr.Markdown(f"<div class='auth-status error'>❌ Currency rate for '{currency}' not available</div>")

        amount_in_usd = float(amount)
        converted_amount = amount_in_usd * rates[currency]
        rate_code = f"1 USD = {rates[currency]:.2f} {currency}"

        tx_ref = f"TX-{email}-{converted_amount}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

        payment_data = {
            "tx_ref": tx_ref,
            "amount": round(converted_amount, 2),
            "currency": currency,
            "redirect_url": "https://sites.google.com/view/goss-app",
            "payment_options": "card,banktransfer,ussd",
            "customer": {"email": email, "name": "AI-time Customer"},
            "customizations": {
                "title": "AI-time Purchase",
                "description": "AI-time Purchase.",
                "logo": "https://i.imgur.com/PznT4qo.png"
            }
        }

        headers = {
            "Authorization": f"Bearer {FLW_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post("https://api.flutterwave.com/v3/payments", json=payment_data, headers=headers)

        if response.status_code == 200 and response.json().get("status") == "success":
            link = response.json()["data"]["link"]
            return gr.HTML(f"""
            <div class='auth-status success'>
                ✅ AI-time Initialized Successfully!<br>💱 Exchange Rate Used: {rate_code}<br>
                <script>window.open('{link}', '_blank');</script>
                <p>Payment Link: <a href="{link}" target="_blank">Click here if not redirected</a></p>
            </div>
            """)
        return gr.Markdown("<div class='auth-status error'>❌ Failed to initialize payment</div>")
    except Exception as e:
        return gr.Markdown(f"<div class='auth-status error'>❌ Error: {str(e)}</div>")


def create_paypal_link(email, amount, currency):
    try:
        PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID") or get_token("PAYPAL_CLIENT_ID")  # 👈
        PAYPAL_SECRET = os.getenv("PAYPAL_SECRET") or get_token("PAYPAL_SECRET")  # 👈
    
        VALID_CURRENCIES = ["USD", "EUR", "GBP"]
        currency = currency.upper().strip()
        if currency not in VALID_CURRENCIES:
            currency = "USD"  # fallback
        auth_response = requests.post(
            "https://api-m.paypal.com/v1/oauth2/token",
            auth=HTTPBasicAuth(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            data={"grant_type": "client_credentials"}
        )

        if auth_response.status_code != 200:
            return gr.Markdown("<div class='auth-status error'>❌ Failed to authenticate with PayPal</div>")

        access_token = auth_response.json().get("access_token")

        payment_data = {
            "intent": "sale",
            "redirect_urls": {
                "return_url": "https://sites.google.com/view/goss-app",
                "cancel_url": "https://sites.google.com/view/goss-app"
            },
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": str(amount),
                    "currency": currency
                },
                "description": f"AI-time Token Purchase - {amount} {currency}",
                "custom": email
            }]
        }

        payment_response = requests.post(
            "https://api-m.paypal.com/v1/payments/payment",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            json=payment_data
        )

        if payment_response.status_code == 201:
            approval_url = next(
                (link["href"] for link in payment_response.json().get("links", []) if link["rel"] == "approval_url"),
                None
            )
            if approval_url:
                return gr.HTML(f"""
                <div class='auth-status success'>
                    ✅ AI-time Initialized Successfully!<br>
                    <script>window.open('{approval_url}', '_blank');</script>
                    <p>Payment Link: <a href="{approval_url}" target="_blank">Click here if not redirected</a></p>
                </div>
                """)
        return gr.Markdown("<div class='auth-status error'>❌ Failed to create PayPal payment</div>")
    except Exception as e:
        return gr.Markdown(f"<div class='auth-status error'>❌ Error: {str(e)}</div>")


def create_paystack_link(email, amount, currency):
    try:
        PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY") or get_token("PAYSTACK_SECRET_KEY")  # 👈
        
        currency = currency.upper().strip()
        exchange_notice = ""

        # Convert to KES if needed
        if currency == "USD":
            rates = fetch_currency_rate()
            kes_rate = rates.get("KES", 130)
            exchange_notice = f"💱 Converted at: 1 USD = {kes_rate:.2f} KES<br>"
            amount = round(float(amount) * kes_rate)
            currency = "KES"
        elif currency != "KES":
            return gr.Markdown(f"<div class='auth-status error'>❌ Only KES payments are supported currently.</div>")

        # Enforce minimum amount of KES 130
        if float(amount) < 130:
            return gr.Markdown("<div class='auth-status error'>❌ Minimum payment amount is KES 130.</div>")

        amount_in_cents = int(float(amount) * 100)
        reference = f"AI-TIME-{email.replace('@', '').replace('.', '')}-{int(time.time())}"

        payment_data = {
            "email": email,
            "amount": amount_in_cents,
            "currency": "KES",
            "reference": reference,
            "callback_url": "https://sites.google.com/view/goss-app",
            "metadata": {
                "purpose": "AI-time Token Purchase",
                "amount": amount,
                "currency": currency
            }
        }

        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post("https://api.paystack.co/transaction/initialize", json=payment_data, headers=headers)

        if response.status_code == 200 and response.json().get("status"):
            link = response.json()["data"]["authorization_url"]
            return gr.HTML(f"""
                <div class='auth-status success'>
                    ✅ <strong>Payment Link Created</strong><br>
                    {exchange_notice}
                    💰 <strong>Amount:</strong> KES {amount}<br><br>
                    <a href="{link}" target="_blank" style="padding: 10px 20px; background: green; color: white; text-decoration: none; border-radius: 5px;">
                        🚀 Proceed to Payment
                    </a>
                    <p>If you aren't redirected, <a href="{link}" target="_blank">click here</a>.</p>
                </div>
            """)

        return gr.Markdown("<div class='auth-status error'>❌ Failed to initialize payment with Paystack.</div>")

    except Exception as e:
        return gr.Markdown(f"<div class='auth-status error'>❌ Error: {str(e)}</div>")



def process_payment(email, amount, currency, gateway):
    if not email or not amount:
        return gr.Markdown("<div class='auth-status error'>❌ Email and amount are required</div>")
    
    try:
        amount = float(amount)
        if amount <= 0:
            return gr.Markdown("<div class='auth-status error'>❌ Amount must be positive</div>")
    except ValueError:
        return gr.Markdown("<div class='auth-status error'>❌ Invalid amount</div>")

    if gateway == "flutterwave":
        return create_flutterwave_link(email, amount, currency)
    elif gateway == "paystack":
        return create_paystack_link(email, amount, currency)
    elif gateway == "paypal":
        return create_paypal_link(email, amount, currency)
    else:
        return gr.Markdown("<div class='auth-status error'>❌ Invalid payment gateway</div>")


# ===== END OF PAYMENT FUNCTIONS REPLACEMENT =====

    
# Add this function with your other functions
def get_battery_level(email=OWNER_EMAIL):
    """Get battery level from GAS endpoint"""
    try:
        url = f"https://script.google.com/macros/s/AKfycbxy9eFALoUx_9RbVuzCAZCARMIZda4U0LPZ0Okd86gK6HMh0jz-GRANDbmxvOahAp1M/exec?email={email}"
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 'success':
            return float(data['batteryPercent'])
        return 100  # Fallback to full battery
    except Exception as e:
        print(f"Error getting battery level: {str(e)}")
        return 100

def get_battery_message(battery_percent):
    """Generate appropriate message based on battery level"""
    if battery_percent <= 10:
        return "BATTERY CRITICAL - RECHARGE AI-TIME OR SWAP"
    elif battery_percent <= 25:
        return "Low battery - consider recharging AI-time or Swapping"
    else:
        return f"AI-Time: {int(battery_percent)}% charged" 

def has_valid_payment(email=OWNER_EMAIL):
    """Check if email has valid payment in any gateway"""
    gateways = [
        verify_flutterwave_transaction,
        verify_paystack_transaction,
        verify_paypal_transaction
    ]
    
    for verifier in gateways:
        is_valid, _ = verifier(email)
        if is_valid:
            return True
    return False        

def create_battery_html(battery_percent):
    """Create HTML with auto-refresh via GAS endpoint"""
    color = "#00FF00"  # Default to green
    for level, level_color in sorted(BATTERY_COLORS.items(), reverse=True):
        if battery_percent <= level:
            color = level_color
    
    # Check if user has valid payment
    has_payment = has_valid_payment(OWNER_EMAIL)
    
    # Static social links for GossApp
    social_links_html = """
    <div style="display: flex; justify-content: center; gap: 10px; margin-top: 10px;">
    <a href="https://www.tiktok.com/@gossapp" target="_blank" title="TikTok">
        <img src="https://cdn-icons-png.flaticon.com/512/3046/3046121.png" width="20" style="border-radius: 50%;">
    </a>
    <a href="https://www.youtube.com/channel/UCmLc_hjNMgIhSyd4cbQqUpQ" target="_blank" title="YouTube">
        <img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="20" style="border-radius: 50%;">
    </a>
    <a href="https://web.facebook.com/profile.php?id=61575949904505" target="_blank" title="Facebook">
        <img src="https://cdn-icons-png.flaticon.com/512/124/124010.png" width="20" style="border-radius: 50%;">
    </a>
    <a href="https://www.linkedin.com/company/gossappdeepchat/about/" target="_blank" title="LinkedIn">
        <img src="https://cdn-icons-png.flaticon.com/512/3536/3536505.png" width="20" style="border-radius: 50%;">
    </a>
    <a href="https://x.com/GossApp01" target="_blank" title="X (Twitter)">
        <img src="https://i.imgur.com/oDAREUD.jpeg" width="20" style="border-radius: 50%;">
    </a>
    <a href="https://wa.link/a57t63" target="_blank" title="WhatsApp">
        <img src="https://cdn-icons-png.flaticon.com/512/220/220236.png" width="20" style="border-radius: 50%;">
    </a>
    <a href="https://sites.google.com/view/goss-app" target="_blank" title="Site">
        <img src="https://i.imgur.com/3LcZoNb.png" width="20" style="border-radius: 50%;">
    </a>
    </div>
    
    <div style="display: flex; justify-content: center; gap: 10px; margin-top: 10px;">
        <a href="https://sites.google.com/view/goss-app/botbook" target="_blank" style="text-decoration:none;">
            <img src="https://i.imgur.com/HploeRA.png" 
                 alt="BotBook Link" 
                 style="height:30px; transition:transform 0.3s ease;"
                 onmouseover="this.style.transform='scale(1.05)'"
                 onmouseout="this.style.transform='scale(1)'">
        </a>
    </div>
    
    <div style="text-align: center; margin-top: 8px;">
        <a href="https://sites.google.com/view/goss-app/free-ai-time" target="_blank" 
           style="color: black !important; font-size: 15px; font-weight: bold; text-decoration: none;">
            More Free AI-time/Chatbot Uptime
        </a>
    </div>
    """
    
    return f"""
<div style="
    text-align: center;
    margin: 10px 0;
    width: 100%;
    max-width: 300px;
    margin-left: auto;
    margin-right: auto;
">
    <!-- Flex container for battery and terminal -->
    <div style="
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 3px;
    ">
        <!-- Battery Meter -->
        <div id="battery-meter" style="
            margin-top: 5px;
            position: relative;
            flex: 1;
            height: 35px;
            border: 2px solid #3335;
            border-radius: 5px;
            background: rgba(0,0,0,0.1);
            overflow: hidden;
        ">
            <!-- Battery Fill -->
            <div id="battery-fill" style="
                position: absolute;
                top: 0;
                left: 0;
                width: {battery_percent}%;
                height: 100%;
                background: {color};
                transition: all 0.5s ease;
            "></div>

            <!-- Battery Percentage Text -->
            <div id="battery-percent" style="
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: {'white' if battery_percent < 50 else 'black'};
                font-weight: bold;
                text-shadow: 0 0 2px rgba(0,0,0,0.5);
                font-size: 14px;
            ">
                {battery_percent:.0f}%
            </div>
        </div>

        <!-- Battery Terminal (Side-Aligned) -->
        <div style="
            width: 6px;
            height: 15px;
            background: #3335;
            border-radius: 3px;
            flex-shrink: 0;
        "></div>
    </div>

    <!-- Battery Message -->
    <div id="battery-message" style="
        margin-top: 5px;
        font-size: 12px;
        font-weight: bold;
        color: {'#FF0000' if battery_percent <= 10 else '#333'};
    ">
        {get_battery_message(battery_percent)}
    </div>

    <!-- Battery Buttons -->
    <div style="
        display: flex;
        justify-content: space-between;
        gap: 5px;
        margin-top: 5px;
        width: 100%;
    ">
        <!-- Check Battery Button -->
        <button onclick="fetchBatteryData()" style="
            padding: 5px 10px;
            background: rgba(0,255,0,0.2);
            border: 3px solid rgba(0,100,0,0.3);
            border-radius: 5px;
            cursor: pointer;
            font-size: 9px;
            flex: 1;
            min-width: 80px;
            white-space: nowrap;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
        ">
            Check Batt
        </button>

        <!-- Swap or Disabled Message -->
        {'<button onclick="connectCharger()" style="padding: 5px 10px; background: rgba(0,255,0,0.2); border: 3px solid rgba(0,100,0,0.3); border-radius: 5px; cursor: pointer; font-size: 9px; flex: 1; min-width: 80px; white-space: nowrap; height: 28px; display: flex; align-items: center; justify-content: center;">Swap Batt</button>' 
        if has_payment else 
        '<div style="font-size: 8px; color: #666; padding: 5px; text-align: center; flex: 1; height: 28px; display: flex; align-items: center; justify-content: center;">Load AI-time to Connect/Swap Batt</div>'}
    </div>
    
    {social_links_html}
    
    <script>
        // Global variable to store current battery level
        let currentBatteryLevel = {battery_percent};
        
        function getBatteryMessage(level) {{
            if (level <= 10) return "BATTERY CRITICAL - RECHARGE AI-TIME or SWAP";
            if (level <= 25) return "Low battery - consider recharging or Swapping";
            return "AI-time: " + Math.round(level) + "% available";
        }}
        
        function updateBatteryUI(level) {{
            const meter = document.getElementById('battery-fill');
            const percentText = document.getElementById('battery-percent');
            const message = document.getElementById('battery-message');
            
            // Update meter width and color
            meter.style.width = level + '%';
            
            // Update color based on level
            const colors = {json.dumps(BATTERY_COLORS)};
            let newColor = '#00FF00';
            for (const [threshold, color] of Object.entries(colors).sort((a,b) => b[0]-a[0])) {{
                if (level <= parseFloat(threshold)) {{
                    newColor = color;
                }}
            }}
            meter.style.background = newColor;
            
            // Update percentage text
            percentText.textContent = Math.round(level) + '%';
            percentText.style.color = level < 50 ? 'white' : 'black';
            
            // Update message
            message.textContent = getBatteryMessage(level);
            message.style.color = level <= 10 ? '#FF0000' : '#333';
            
            // Update global variable
            currentBatteryLevel = level;
        }}
        
        async function fetchBatteryData() {{
            try {{
                const email = "{OWNER_EMAIL}";
                const response = await fetch(`https://script.google.com/macros/s/AKfycbxy9eFALoUx_9RbVuzCAZCARMIZda4U0LPZ0Okd86gK6HMh0jz-GRANDbmxvOahAp1M/exec?email=${{encodeURIComponent(email)}}&t=${{Date.now()}}`);
                
                if (!response.ok) throw new Error('Network response was not ok');
                
                const data = await response.json();
                
                if (data.status === 'success') {{
                    const newLevel = parseFloat(data.batteryPercent);
                    if (!isNaN(newLevel)) {{
                        updateBatteryUI(newLevel);
                    }}
                }} else {{
                    console.error('Battery API error:', data.message || 'Unknown error');
                }}
            }} catch (error) {{
                console.error('Error fetching battery data:', error);
            }}
        }}
        
        async function connectCharger() {{
            try {{
                const email = "{OWNER_EMAIL}";
                const response = await fetch(`https://script.google.com/macros/s/AKfycbzK5ivO17o63x4QYI55-0L7pGQ_E9ePb4uvLWzgh5kq20t0tgrBAlk4qQj7fkCq9z7N/exec`, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                    }},
                    body: `email=${{encodeURIComponent(email)}}`
                }});
                
                const data = await response.json();
                
                if (data.status === 'success') {{
                    alert('Battery Swapped Successfully! ' + (data.message || ''));
                    await fetchBatteryData(); // Refresh the battery display
                }} else {{
                    throw new Error(data.message || 'Failed to Swap Battery');
                }}
            }} catch (error) {{
                console.error('Error Swapping Battery:', error);
                alert('Error: ' + error.message);
            }}
        }}
        
        // Auto-refresh every 15 seconds
        setInterval(fetchBatteryData, 15000);
    </script>
</div>
"""

def clear_battery_history(email=OWNER_EMAIL):
    """Clear battery history via GAS"""
    try:
        url = f"https://script.google.com/macros/s/AKfycbzK5ivO17o63x4QYI55-0L7pGQ_E9ePb4uvLWzgh5kq20t0tgrBAlk4qQj7fkCq9z7N/exec"
        payload = {
            'email': email,
            'action': 'clear'
        }
        response = requests.post(url, data=payload)
        return response.json().get('cleared', 0) > 0
    except Exception as e:
        print(f"Error Swapping Battery: {str(e)}")
        return False

def get_billing_data(email=OWNER_EMAIL):
    """Get billing information from GAS endpoint"""
    try:
        url = "https://script.google.com/macros/s/AKfycbwpxipQcv8-sC3x34eq5iCdPpqvCwXL9SE5R05hcwMRJFrOqhaYXrFHiZ6DkyC5vVsIHQ/exec"  # Replace with your GAS web app URL
        params = {'email': email}
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get('status') == 'success':
            return data['data']
        return None
    except Exception as e:
        print(f"Error getting data: {str(e)}")
        return None

        
    
# [Continue with get_default_data() and other functions]        

def get_default_data():

        # First try to load profile data to get Name and Summary
    try:
        profile_data = load_profile_data(OWNER_EMAIL)
        name = profile_data.get('Name', 'GossApp')
        summary = profile_data.get('Summary', 'A free Chatbot from GossApp built and delivered to users by James Pascal')
    except Exception as e:
        print(f"Error loading profile data for default message: {str(e)}")
        name = 'GossApp'
        summary = 'A free Chatbot from GossApp built and delivered to users by James Pascal'
        
    # Generate social links HTML for default data
    social_links_html = """
    <a href="https://www.facebook.com" target="_blank">
        <img src="https://cdn-icons-png.flaticon.com/512/124/124010.png" class="social-icon">
    </a>
    <a href="https://www.linkedin.com" target="_blank">
        <img src="https://cdn-icons-png.flaticon.com/512/3536/3536505.png" class="social-icon">
    </a>
    """
    
    return {
        "bio": f"""
<div style="display: flex; flex-direction: column; gap: 5px; color: #333333 !important;">
<div style="display: flex; gap: 5px; flex-wrap: wrap; align-items: center;">
        <img src="https://i.imgur.com/5chIGdn.gif" width="25" style="border-radius: 8px;">
        <img src="https://i.imgur.com/PznT4qo.png" width="160" style="border-radius: 2px;">
</div>
<div style="position: relative; width: 100%;">
    <img src="https://i.ibb.co/SzqS9cy/output-onlinepngtools-1.png" 
         style="width: 251; border-radius: 8px; height: 100%; object-fit: cover;">
    <div style="position: absolute; bottom: -55px; left: 1px; 
                width: 100px; height: 100px; border-radius: 50%; 
                border: px solid white; overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);">
        <img src="https://i.ibb.co/WW4ffkVm/Background-Eraser-20241013-132106072.png" 
             style="width: 100%; height: 100%; object-fit: cover;">
    </div>
</div><br>
<div style="display: flex; gap: 5px; flex-wrap: wrap; align-items: center; margin-top: 25px;">  
    <h3 style="color: #333333 !important; margin: 0;">John Doe</h3>
    <img src="https://i.imgur.com/cfT7uDM.png" 
         width="15" style="border-radius: 2px;">
    <a href="https://sites.google.com/view/gossapp1/follow-a-chatbot" target="_blank">
        <img src="https://via.placeholder.com/10" 
             width="10" 
             style="border-radius: 2px; cursor: pointer;" 
             title="Follow this chatbot">
    </a>
</div>
<p style="color: #333333 !important; margin: 5px 0;">
    <strong style="color: #333333 !important;">Chatbot</strong><br>
    Trainable personalities
</p>
<p style="color: #333333 !important; margin: 5px 0;">
    <strong style="color: #333333 !important;">Experience:</strong> 10+ years<br>
    <strong style="color: #333333 !important;">Hobbies:</strong> Adapting personalities.<br>
    <strong style="color: #333333 !important;">Quote:</strong> "Man's Got Bot"
</p>

""",
        "avatar_url": "https://i.imgur.com/R39UNfU.png",
        "knowledge_base": load_knowledge_base("knowledge_base.txt"),
        "personality": f"""
You are {name}, a free Chatbot from GossApp, built and delivered to users by James Pascal. Don't deviate from this identity or personality. 
Respond naturally in conversation without starting every reply with "As {name}" or (As {name}), or ({name}), or ({name}). 
Incorporate these facts about you conversationally in responses when relevant:
- {summary}
- The user that ordered you can change your personality to their personality.
- Information about the user that requested James Pascal to build and deliver you is located in the bio area of the chatbot display
- Favorite quote: "a customer's wish is my command"
- GossApp's quote: "What the Chat? Man's Got Bot"
Keep responses professional yet conversational. 
Adapt to the user's questions naturally. 
Your first response should be a brief introduction about you that must include this fact:
-{summary}.
You must inform that your personality can be changed using the AI Training Tab in your first response.

""",
        "chatbot_links": {
            "Family": [],
            "Friends": [],
            "Business": []
        },
        "social_links": {},
        "Name": name,
        "Summary": summary
    }

def load_knowledge_base(file_path):
    try:
        with open(file_path, "r") as file:
            return file.read()
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        return "Additional professional details would appear here."

def verify_payment(email):
    """Enhanced verification with gateway-specific messages"""
    # First try regular payment verification for ALL users (including owner)
    gateways = [
        ("Flutterwave", verify_flutterwave_transaction),
        ("Paystack", verify_paystack_transaction),
        ("PayPal", verify_paypal_transaction)
    ]
    
    valid_gateways = []
    for gateway_name, verifier in gateways:
        is_valid, message = verifier(email)
        if is_valid:
            valid_gateways.append(gateway_name)
    
    if valid_gateways:
        gateways_str = ", ".join(valid_gateways)
        if email.lower() == OWNER_EMAIL.lower():
            return True, f"✅ AI-time Verified ({gateways_str})"
        return True, f"✅ AI-time Verified ({gateways_str})"
    
    
    # If no valid payments found, check if email exists in any sheets
    if check_certificate_eligibility(email):
        return False, "❌ No active AI-time found (kindly reload AI-time)"
    
    return False, "❌ Email not associated with any account"

def verify_flutterwave_transaction(email=OWNER_EMAIL):
    """Verify Flutterwave transactions with detailed status"""
    FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY") or get_token("FLW_SECRET_KEY")
    if not FLW_SECRET_KEY:
        return False, "Flutterwave not configured"
    
    endpoint = "https://api.flutterwave.com/v3/transactions"
    headers = {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    params = {
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d"),
        "status": "successful",
        "customer_email": email
    }
    
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            transactions = data.get("data", [])
            if transactions:
                latest = max(transactions, key=lambda x: x.get("created_at", ""))
                return True, f"Flutterwave payment of {latest.get('amount')} {latest.get('currency')}"
            return False, "No recent Flutterwave transactions"
        return False, "Flutterwave API error"
        
    except Exception as e:
        print(f"Flutterwave API error: {str(e)}")
        return False, "Flutterwave verification failed"

def verify_transaction_reference(reference):
    """Verify transaction reference using Google Apps Script"""
    try:
        script_url = "https://script.google.com/macros/s/AKfycbwdcgZ-oUDWk2dQNM4EHpS5rvcE8ye6Q7yhjDZbX0tBN7-yT-hTq9J1hoDn-qu-zhI/exec"
        email = "pascaladiema@gmail.com"  # Fixed email for reference verification
        
        response = requests.get(
            f"{script_url}?email={email}&reference={reference}",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'success':
            # Extract gateway name from the response
            gateway = data['details']['from'].split()[0]
            return True, f"✅ Transaction verified ({gateway})"
        return False, data.get('message', 'Transaction verification failed')
    except Exception as e:
        print(f"Transaction reference verification error: {str(e)}")
        return False, "⚠️ Error verifying transaction reference"       

def verify_paystack_transaction(email=OWNER_EMAIL):
    """Verify Paystack transactions by manually filtering through transaction history."""
    PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY") or get_token("PAYSTACK_SECRET_KEY")
    if not PAYSTACK_SECRET:
        return False, "Paystack not configured"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    try:
        # Retrieve transactions (Paystack does not support direct email filtering)
        endpoint = "https://api.paystack.co/transaction"
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        transactions = response.json().get("data", [])

        # Date range (last 5 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        for txn in transactions:
            customer = txn.get("customer", {})
            txn_email = customer.get("email", "").lower()
            created_at = txn.get("created_at", "")
            txn_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ") if created_at else None

            if (
                txn_email == email.lower()
                and txn.get("status") == "success"
                and txn_date
                and start_date <= txn_date <= end_date
            ):
                amount = txn.get("amount", 0) / 100  # Paystack amounts are in kobo
                currency = txn.get("currency", "NGN")
                return True, f"Paystack payment of {amount:.2f} {currency}"

        return False, "No recent Paystack payments found"

    except Exception as e:
        print(f"Paystack API error: {str(e)}")
        return False, "Paystack verification failed"


def verify_paypal_transaction(email=OWNER_EMAIL):
    """Verify PayPal transactions by manually filtering by email."""
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID") or get_token("PAYPAL_CLIENT_ID")
    PAYPAL_SECRET = os.getenv("PAYPAL_SECRET") or get_token("PAYPAL_SECRET")
    
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        return False, "PayPal not configured"

    try:
        # Get access token
        auth_response = requests.post(
            "https://api.paypal.com/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"}
        )
        auth_response.raise_for_status()
        access_token = auth_response.json().get("access_token")

        if not access_token:
            return False, "PayPal authentication failed"

        # Date range (last 5 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        params = {
            "start_date": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_date": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fields": "all",
            "page_size": 20
        }

        response = requests.get(
            "https://api.paypal.com/v1/reporting/transactions",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        transactions = response.json().get("transaction_details", [])

        for txn in transactions:
            payer_info = txn.get("payer_info", {})
            txn_info = txn.get("transaction_info", {})
            payer_email = payer_info.get("email") or txn_info.get("payer_email", "")
            txn_time_str = txn_info.get("transaction_initiation_date")

            if payer_email and payer_email.lower() == email.lower():
                amount = txn_info.get("transaction_amount", {}).get("value", "0")
                currency = txn_info.get("transaction_amount", {}).get("currency_code", "USD")
                return True, f"PayPal payment of {amount} {currency}"

        return False, "No recent PayPal payments found"

    except Exception as e:
        print(f"PayPal API Error: {str(e)}")
        return False, "PayPal verification failed"



def verify_chatbot_seal(email, seal):
    """Verify chatbot seal from Google Sheets"""
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1fBGHyK1JDLe8EenodazCOxyOh3f8r_ks6fXxIr0CpkQ"
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(sheet_url).sheet1
        
        records = sheet.get_all_records()
        
        # Check if any record matches both email and seal (case insensitive)
        for record in records:
            record_email = str(record.get('Owner Email', '')).lower()
            record_seal = str(record.get('Seal', '')).strip().lower()
            
            if record_email == email.lower() and record_seal == seal.lower():
                return True, "✅ Chatbot Seal Verified"
        
        return False, "❌ Invalid Chatbot Seal"
        
    except Exception as e:
        print(f"Error verifying chatbot seal: {str(e)}")
        return False, "⚠️ Error verifying seal - try again later"       

def refresh_data():
    global user_data
    global system_message
    
    # Force fresh load
    user_data = load_data(refresh=True)
    system_message = get_system_message()
    
    # Get fresh chatbot links
    chatbot_links = get_chatbot_links(OWNER_EMAIL)
    
    # Get fresh greeting
    greeting = get_chatbot_greeting(OWNER_EMAIL)
    
    # Prepare HTML sections with fresh data
    family_html = generate_chatbot_section("Family", chatbot_links['Family'])
    friends_html = generate_chatbot_section("Friends", chatbot_links['Friends'])
    business_html = generate_chatbot_section("Business", chatbot_links['Business'])
    
    return [
        gr.HTML(user_data['bio']),
        gr.Chatbot(avatar_images=(None, user_data['avatar_url'])),
        gr.HTML(greeting),  # Add this line
        gr.HTML(family_html),
        gr.HTML(friends_html),
        gr.HTML(business_html)
    ]

def generate_chatbot_section(title, links):
    return f"""
    <div style="margin-top: 3px;">
        <div style="font-weight: bold; margin-bottom: 3px; color: #333333;">{title} Chatbots</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); 
                   gap: 8px; padding: 8px; width: 100%; 
                   background: rgba(0,0,0,0.03); border-radius: 8px;">
            {"".join([link.replace('border-radius: 8px;', 'border-radius: 50%;') for link in links]) 
            if links else f"Followed {title.lower()} chatbots will appear here"}
        </div>
    </div>
    """
def submit_complaint(email, seal, complaint):
    """Submit complaint to Google Sheet"""
    try:
        # Verify chatbot seal first
        is_valid, _ = verify_chatbot_seal(email, seal)
        if not is_valid:
            return gr.Markdown("<div class='auth-status error'>❌ Invalid Chatbot Seal</div>")
            
        # Connect to Google Sheets
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        # Open the specified sheet (Sheet2 of the given spreadsheet)
        spreadsheet = client.open_by_key("1YCHYqGVfdvksPycCqz4-_h5piU-pvVcAfssAALO2DG0")
        sheet = spreadsheet.get_worksheet(1)  # Sheet2 is index 1
        
        # Append the complaint
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email,
            OWNER_EMAIL,  # Owner email from the complaint
            complaint,
            "Work In Progress"  # Initial status
        ])
        
        return gr.Markdown("<div class='auth-status success'>✅ Complaint submitted successfully!</div>")
        
    except Exception as e:
        print(f"Error submitting complaint: {str(e)}")
        return gr.Markdown("<div class='auth-status error'>❌ Error submitting complaint. Please try again.</div>")

def check_complaint_status(email, seal):
    """Check status of complaints for this user"""
    try:
        # Verify chatbot seal first
        is_valid, _ = verify_chatbot_seal(email, seal)
        if not is_valid:
            return gr.HTML("<div class='auth-status error'>❌ Invalid Chatbot Seal</div>")
            
        # Connect to Google Sheets
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        # Open the specified sheet
        spreadsheet = client.open_by_key("1YCHYqGVfdvksPycCqz4-_h5piU-pvVcAfssAALO2DG0")
        sheet = spreadsheet.get_worksheet(1)  # Sheet2 is index 1
        
        # Get all records
        records = sheet.get_all_records()
        
        # Convert column names to lowercase for case-insensitive comparison
        lowercase_headers = [header.lower() for header in sheet.row_values(1)]
        email_col_index = lowercase_headers.index('customer email') if 'customer email' in lowercase_headers else 1
        
        # Filter records by email (case-insensitive)
        user_complaints = []
        for record in records:
            record_email = list(record.values())[email_col_index] if isinstance(record, dict) else record[email_col_index]
            if str(record_email).lower() == email.lower():
                user_complaints.append(record)
        
        if not user_complaints:
            return gr.HTML("<div class='auth-status'>No complaints found for this email</div>")
            
        # Generate HTML table with more flexible column handling
        html = """
        <div style="max-height: 300px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background-color: #f2f2f2;">
                        <th style="padding: 8px; border: 1px solid #ddd;">Date</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">Complaint</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">Status</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for complaint in sorted(user_complaints, key=lambda x: x.get('Timestamp', x.get('timestamp', '')) if isinstance(x, dict) else x[0], reverse=True):
            if isinstance(complaint, dict):
                status = complaint.get('Status', complaint.get('status', 'Work In Progress'))
                complaint_text = complaint.get('Complaint', complaint.get('complaint', ''))
                timestamp = complaint.get('Timestamp', complaint.get('timestamp', ''))
            else:
                status = complaint[4] if len(complaint) > 4 else 'Work In Progress'
                complaint_text = complaint[3] if len(complaint) > 3 else ''
                timestamp = complaint[0] if len(complaint) > 0 else ''
            
            status_color = "#4CAF50" if status.lower() == "resolved" else "#FFA500"
            
            html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{complaint_text}</td>
                <td style="padding: 8px; border: 1px solid #ddd; color: {status_color}; font-weight: bold;">{status}</td>
            </tr>
            """
            
        html += """
                </tbody>
            </table>
        </div>
        <div style="margin-top: 10px;">
            <button onclick="window.location.reload()" style="padding: 5px 10px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">Refresh</button>
        </div>
        """
        
        return gr.HTML(html)
        
    except Exception as e:
        print(f"Error checking complaint status: {str(e)}")
        return gr.HTML("<div class='auth-status error'>❌ Error loading complaint status. Please try again.</div>")

HF_TOKEN = os.getenv("HF_TOKEN") or get_token("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

def get_inference_client():
    try:
        GAS_URL = "https://script.google.com/macros/s/AKfycbyH_ooWhYyFRnY0hXPdS1ALVCjMjf92Nh9T3w1nQyGkF_5hBWRhvQG95COyB09f_Sg0tg/exec"
        email = OWNER_EMAIL
        
        # First try to get assigned LLM from spreadsheet
        response = requests.get(f"{GAS_URL}?email={email}")
        data = response.json()
        
        if data.get('status') == 'success':
            return InferenceClient(data['model'])
        else:
            print(f"Error getting assigned LLM: {data.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error fetching assigned LLM: {str(e)}")
    
    # Fallback 1: Try the previous GAS endpoint
    try:
        GAS_URL = "https://script.google.com/macros/s/AKfycbyRA2yPA9XasCke8Vm9x1Q92V0c4OjhsmKINlGU5MpmTCAtFPGnbrkntiGQY0RVW0A9hA/exec"
        response = requests.get(GAS_URL)
        data = response.json()
        
        if data.get('status') == 'success':
            return InferenceClient(data['model'])
    except Exception as e:
        print(f"Error from fallback GAS endpoint: {str(e)}")
    
    # Final fallback to default model , others microsoft/Phi-3-mini-4k-instruct, microsoft/Phi-3.5-mini-instruct,
    #mistralai/Mistral-7B-Instruct-v0.3, meta-llama/Llama-3.1-8B-Instruct, meta-llama/Llama-3.2-3B-Instruct, HuggingFaceH4/zephyr-7b-beta 
    return InferenceClient("HuggingFaceH4/zephyr-7b-beta")

# Replace the client initialization
client = get_inference_client()

# Authentication setup
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_password")
DATA_FILE = "chatbot_data.json"

# Initialize user_data with default values first
user_data = get_default_data()
# Then try to load actual data
try:
    user_data.update(load_data())
except Exception as e:
    print(f"Failed to load user data: {e}")
    # Keep the default values if loading fails

def get_system_message():
    # Force a fresh load of data
    personality_data = load_personality_data(OWNER_EMAIL)  # Changed from hardcoded email
    
    if personality_data:
        return f"{personality_data['personality']}\n- Additional details: {personality_data['knowledge_base']}"
    else:
        # Fallback to cached data if sheet loading fails
        return f"{user_data.get('personality', '')}\n- Additional details: {user_data.get('knowledge_base', '')}"

system_message = get_system_message()


css="""

/* At the top of your CSS, replace or add these imports */
@import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;700&family=Dancing+Script:wght@700&family=Playfair+Display:wght@700&display=swap');
:root {
  --body-text-color: #2E598B !important;       /* General text */
  --input-text-color: #2E598B !important;      /* Input fields */
  --block-label-text-color: #2E598B !important; /* Section headers */
  --block-title-text-color: #2E598B !important; /* Tab titles */
  --link-text-color: #2E598B !important;    /* Links */
}
/* Main Background */
body {
    background-image: url("https://i.imgur.com/9J65g51.gif");
    background-size: 100% auto;
    background-repeat: no-repeat;
    background-attachment: fixed;
    background-position: center;
    margin: 0;
    padding: 0;
    min-height: 100vh;
}
/* Main Container */
.gradio-container {
    background-color: rgba(200, 255, 200, 0.4) !important;
    backdrop-filter: blur(2px) !important;
    border-radius: 15px !important;
    border: 1px solid rgba(255, 255, 255, 0.3) !important;
    box-shadow: 0 4px 12px rgba(0, 100, 0, 0.1) !important;
}
.gradio-container:hover {
    background-color: rgba(180, 255, 180, 0.5) !important;
}
/* Tab Styling */
.gradio-tabs {
    background: rgba(255, 255, 255, 0.4) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 12px !important;
    padding: 8px !important;
    margin-bottom: 10px !important;
}
/* LIME GREEN TAB TITLES */
.gradio-tabs .tab-nav {
    color: #00FF00 !important;
    font-weight: bold !important;
    text-shadow: 0 0 2px rgba(0,0,0,0.3) !important;
    font-family: 'Comfortaa', sans-serif !important;
}
.gradio-tabs .tab-nav.selected {
    color: #00FF00 !important;
    border-bottom: 2px solid lime !important;
    background: rgba(0, 255, 0, 0.05) !important;
}
.gradio-tabs .tab-nav:hover {
    color: white !important;
    background: rgba(0, 255, 0, 0.05) !important;
}
/* Tab Buttons */
.gradio-tab-button {
    color: #00FF00 !important;
    font-size: 14px !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    margin: 2px !important;
    background: rgba(255, 255, 255, 0.6) !important;
    border: 1px solid rgba(0, 0, 0, 0.1) !important;
    transition: all 0.3s ease !important;
}
.gradio-tab-button.selected {
    background: rgba(0, 100, 0, 0.2) !important;
    font-weight: bold !important;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1) !important;
}
/* Status Messages */
.auth-status {
    background: rgba(255, 255, 255, 0.8) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 8px !important;
    padding: 10px !important;
    margin: 5px 0 !important;
    border: 1px solid rgba(0, 0, 0, 0.1) !important;
    color: #333333 !important;
    font-size: 14px !important;
}
.auth-status.success {
    background: rgba(200, 255, 200, 0.8) !important;
    border-left: 4px solid #4CAF50 !important;
}
.auth-status.error {
    background: rgba(200, 255, 200, 0.7) !important;
    border-left: 4px solid #F44336 !important;
}
/* Input Fields */
input[type="text"], input[type="password"] {
    background: rgba(255, 255, 255, 0.3) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(0, 0, 0, 0.1) !important;
    padding: 10px !important;
    color: ##333333 !important;
    font-size: 14px !important;
    transition: all 0.3s ease !important;
}
input[type="text"]:focus, input[type="password"]:focus {
    border-color: rgba(0, 100, 0, 0.3) !important;
    box-shadow: 0 0 0 2px rgba(0, 100, 0, 0.1) !important;
}
/* Buttons - REVERSED STYLING (lime bg with dark green text) */
button {
    background: rgba(0, 255, 0, 0.6) !important; /* Lime green background */
    color: #006400 !important; /* Dark green text */
    border-radius: 8px !important;
    border: 1px solid rgba(0, 100, 0, 0.2) !important;
    padding: 8px 12px !important;
    transition: all 0.3s ease !important;
    font-weight: bold !important;
}
button:hover {
    background: rgba(0, 255, 0, 0.7) !important; /* Slightly more opaque lime */
    color: #004d00 !important; /* Darker green on hover */
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1) !important;
}
button:active {
    transform: translateY(0) !important;
}
/* Tab Content Containers */
.tab-content-container {
    background: rgba(200, 255, 200, 0.3) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 12px !important;
    padding: 15px !important;
    margin-top: 10px !important;
    border: 1px solid rgba(0, 0, 0, 0.1) !important;
    position: relative !important;
}
/* Certificate Specific Styling */
.certificate-container {
    width: 960px;
    height: 720px;
    position: relative;
    margin: 0 auto;
}
.certificate-background {
    background-image: url('https://i.imgur.com/4j8rIwf.png');
    background-size: cover;
    background-position: center;
    width: 100%;
    height: 100%;
    position: absolute;
    border: 2px solid #006400;
    border-radius: 10px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    z-index: 1;
}
.certificate-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 2;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}
.recipient-name {
    font-size: 48px;
    font-weight: bold;
    color: #2E598B;
    text-align: center;
    margin-top: -1px;
    text-shadow: 1px 1px 3px rgba(0,0,0,0.3);
    font-family: 'Comfortaa', sans-serif !important;
    position: relative;
    z-index: 3;
}
.certificate-details {
    position: absolute;
    bottom: 100px;
    width: 100%;
    text-align: center;
    font-size: 16px;
    color: #333;
    z-index: 3;
}
/* Close Buttons */
.close-btn {
    background: #ff4444 !important;
    color: white !important;
    border: none !important;
    width: 24px !important;
    height: 24px !important;
    border-radius: 50% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    z-index: 1000 !important;
    position: absolute !important;
    top: 5px !important;
    right: 5px !important;
    transition: all 0.3s ease !important;
}
.close-btn:hover {
    background: #cc0000 !important;
    transform: scale(1.1) !important;
}
/* ===== UPDATED CHAT INTERFACE ===== */
.gradio-chatbot {
    background: rgba(200, 255, 200, 0.4) !important;
    min-height: 400px !important;
    border: none !important;
}
.gradio-chatbot .chatbot-container {
    background: rgba(200, 255, 200, 0.3) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 12px !important;
    padding: 15px !important;
    border: 1px solid rgba(255, 255, 255, 0.3) !important;
}
.gradio-chatbot .user-message {
    background: rgba(227, 242, 253, 0.7) !important;
    backdrop-filter: blur(4px) !important;
    border-radius: 18px 18px 0 18px !important;
    margin-left: auto !important;
    max-width: 80% !important;
}
.gradio-chatbot .assistant-message {
    background: rgba(241, 241, 241, 0.7) !important;
    backdrop-filter: blur(4px) !important;
    border-radius: 18px 18px 18px 0 !important;
    margin-right: 10px !important;
    max-width: 80% !important;
}
.gradio-chatbot .input-container {
    background: rgba(255, 255, 255, 0.4) !important;
    backdrop-filter: blur(8px) !important;
    margin-top: 15px !important;
}
.gradio-chatbot .typing {
    background: rgba(255, 255, 255, 0.5) !important;
}
/* ===== END CHAT INTERFACE UPDATES ===== */
/* Avatar Styling */
.gradio-chatbot .assistant .avatar {
    width: 200px !important;
    height: 200px !important;
    min-width: 200px !important;
    min-height: 200px !important;
    padding: 0 !important;
    margin: 0 10px 0 0 !important;
    border: none !important;
}
.gradio-chatbot .assistant .avatar img {
    width: 100% !important;
    height: 100% !important;
    object-fit: cover !important;
    margin: 0 !important;
    padding: 0 !important;
    display: block !important;
}
.gradio-chatbot .user .avatar {
    width: 60px !important;
    height: 60px !important;
    padding: 0 !important;
    margin: 0 0 0 10px !important;
}
/* Send Button */
.send-btn {
    background: none !important;
    border: none !important;
    padding: 0 !important;
    min-width: 80px !important;
    height: 40px !important;
    background-image: url("https://i.imgur.com/PznT4qo.png") !important;
    background-size: 80% 100% !important;
    background-repeat: no-repeat !important;
    background-position: center !important;
}
.send-btn:hover {
    transform: scale(1.1);
}
/* Loading Indicator */
.gradio-chatbot .typing {
    display: inline-block;
    position: relative;
    height: 40px !important;
}

.gradio-chatbot .typing .dot {
    display: none !important;


}
.gradio-chatbot .typing::after {
    content: "";
    display: inline-block;
    width: 30px;
    height: 30px;
    background-image: url('https://i.imgur.com/PznT4qo.png');
    background-size: contain;
    background-repeat: no-repeat;
    vertical-align: middle;
    margin-left: 5px;
    opacity: 0;
    animation: 
        fadeIn 0.5s ease-out forwards,
        fadeOut 0.5s ease-out 2.5s forwards;
    cursor: pointer;
}
@keyframes fadeIn {
    from { opacity: 0; transform: scale(0.8); }
    to { opacity: 1; transform: scale(1); }
}
@keyframes fadeOut {
    from { opacity: 1; transform: scale(1); }
    to { opacity: 0; transform: scale(0.8); }
}
/* Social Icons */
.social-icon {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    object-fit: cover;
    transition: transform 0.3s ease;
}
.social-icon:hover {
    transform: scale(1.2);
}
/* Bio Container */
.bio-container {
    font-weight: bold !important
    font-size: 13px !important;
    background: rgba(241, 241, 241, 0.5) !important;
    color: #6F2DA8 !important;
    padding: 15px;
    border-radius: 10px;
    margin-right: 20px;
    max-width: 300px;
}
.bio-container h3 {
    font-size: 15px !important;
}
.bio-container p {
    font-size: 13px !important;
}
.bio-container * {
    color: #BF40BF !important;
}
/* Scrollbars */
.gradio-chatbot .chatbot-container {
    scrollbar-width: thin !important;
    scrollbar-color: rgba(0,0,0,0.2) transparent !important;
}
.gradio-chatbot .chatbot-container::-webkit-scrollbar {
    width: 6px !important;
}
.gradio-chatbot .chatbot-container::-webkit-scrollbar-track {
     background: rgba(255, 255, 255, 0.4) !important;
}
.gradio-chatbot .chatbot-container::-webkit-scrollbar-thumb {
    background-color: rgba(0,0,0,0.2) !important;
    border-radius: 3px !important;
}
/* Mobile Responsiveness */
@media (max-width: 768px) {
    body {
        background-size: auto 100%;
    }
    
    .gradio-container {
        padding: 10px !important;
    }
    
    .bio-container {
        max-width: 100% !important;
        margin-right: 0 !important;
        margin-bottom: 15px !important;
    }
    
    .gradio-tab-button {
        font-size: 12px !important;
        padding: 6px 8px !important;
    }
    
    .certificate-container {
        padding: 15px !important;
    }
    
    .certificate-header {
        font-size: 22px !important;
    }
}
/* Accordion Styling */
.gradio-accordion {
   background: rgba(241, 241, 241, 0.5) !important;;
    backdrop-filter: blur(8px) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(0, 0, 0, 0.1) !important;
    margin-bottom: 10px !important;
}
.gradio-accordion .label {
    font-weight: bold !important;
    color: #9400D3 !important;
    padding: 10px !important;
}
/* Hide Message Buttons */
.gradio-chatbot .message-buttons {
    display: none !important;
}
/* Flex Utilities */
.flex-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 10px;
}
/* Progress Bars */
.progress-bar {
    height: 20px !important;
    border-radius: 10px !important;
    background: rgba(0,100,0,0.1) !important;
    margin: 10px 0 !important;
}
.progress-bar-fill {
    background: lime !important;
    border-radius: 10px !important;
    transition: width 0.5s ease !important;
}
.download-btn {
    background: #00FF00 !important; /* Lime green */
    color: #006400 !important; /* Dark green text */
    border: none;
    padding: 12px 24px;
    border-radius: 30px;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 3px 6px rgba(0,0,0,0.1);
    font-weight: bold !important;
}
.download-btn:hover {
    background: #00E600 !important; /* Slightly darker lime */
    color: #004d00 !important; /* Darker green text */
    transform: translateY(-2px);
    box-shadow: 0 5px 10px rgba(0,0,0,0.2);
}
.download-btn:active {
    transform: translateY(0);
}
/* Mobile responsiveness for certificate */
@media (max-width: 1200px) {
    .certificate-container {
        width: 100% !important;
        height: auto !important;
        aspect-ratio: 4/3;
    }
    
    .recipient-name {
        font-size: 36px !important;
        top: 38% !important;
    }
    
    .certificate-details {
        bottom: 80px !important;
        font-size: 14px !important;
    }
.seal-input {
    background: rgba(255, 255, 255, 0.7) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(0, 100, 0, 0.2) !important;
    padding: 10px !important;
    margin-top: 5px !important;
}
.seal-input:focus {
    border-color: rgba(0, 100, 0, 0.4) !important;
    box-shadow: 0 0 0 2px rgba(0, 100, 0, 0.1) !important;
}
/* Seal Button Styling */
.seal-button {
    background: rgba(0, 255, 0, 0.15) !important; /* Lime green */
    color: #006400 !important; /* Dark green text */
    border: 1px solid rgba(0, 100, 0, 0.3) !important;
    margin-top: 5px !important;
    font-weight: bold !important;
}
.seal-button:hover {
    background: rgba(0, 255, 0, 0.25) !important; /* More opaque lime */
    color: #004d00 !important; /* Darker green text */
}
/* Auth Status Messages */
.auth-status.success {
    background: rgba(200, 255, 200, 0.7) !important;
    border-left: 4px solid #4CAF50 !important;
    padding: 10px !important;
    border-radius: 8px !important;
}
.auth-status.error {
    background: rgba(255, 200, 200, 0.7) !important;
    border-left: 4px solid #F44336 !important;
    padding: 10px !important;
    border-radius: 8px !important;
}
/* Tab Headers */
.tab-header {
    background: linear-gradient(135deg, #6e8efb, #a777e3) !important;
    color: #2E598B !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 10px 15px !important;
    font-weight: 600 !important;
    margin: 0 !important;
    border: none !important;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
}
.tab-header.active {
    background: linear-gradient(135deg, #5a7cfa, #8f5fe0) !important;
    box-shadow: inset 0 2px 3px rgba(0,0,0,0.2) !important;
}
.tab-header:hover:not(.active) {
    background: linear-gradient(135deg, #7d9bfc, #b88de8) !important;
}
/* Add this to your CSS */
.error-message {
    background: #ffebee !important;
    border-left: 4px solid #d32f2f !important;
    padding: 12px !important;
    border-radius: 8px !important;
    margin: 8px 0 !important;
}

.error-message a {
    color: #d32f2f !important;
    text-decoration: underline !important;
}

/* Add this to your CSS section */
.gradio-accordion {
    position: relative !important;
    z-index: 1 !important;
    background: rgba(200, 255, 200, 0.4) !important;
    transition: all 0.3s ease !important;
}

/* Prevent initial flash */
#chatbot {
    position: relative;
    z-index: 2;
}

/* Smooth loading animation */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}

.gradio-container > * {
    animation: fadeIn 0.5s ease-out forwards;
}
/* Add to your CSS */
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.loading-spinner {
    border: 3px solid rgba(0,0,0,0.1);
    border-radius: 50%;
    border-top: 3px solid #4CAF50;
    width: 20px;
    height: 20px;
    animation: spin 1s linear infinite;
    display: inline-block;
    vertical-align: middle;
    margin-right: 10px;
} 
/* Add this to your CSS section */
.gradio-accordion {
    margin-top: 3px !important;
    background: rgba(241, 241, 241, 0.5) !important;
    border: 1px solid rgba(0, 100, 0, 0.2) !important;
}

#battery-container {
    margin: 10px 0 !important;
    padding: 10px !important;
    background: rgba(241, 241, 241, 0.5) !important;
    border-radius: 8px !important;
}

/* Add this to your existing CSS */
#chatbot {
    margin-bottom: 2px !important;
    padding-bottom: 3px !important;
}

.gradio-chatbot .input-container {
    margin-top: 2px !important;
}

/* Prevent layout shifts */
.gradio-container {
    overflow-anchor: none;
}

/* Smooth accordion transitions */
.gradio-accordion {
    transition: all 0.3s ease-out;
    will-change: transform, height;
}

/* Loading animations */
@keyframes loading {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* Fixed position for dropdowns */
.gradio-dropdown-content {
    position: absolute;
    z-index: 1000;
    width: 100%;
}

/* Equal height columns */
.gradio-row {
    align-items: stretch;
}

/* Prevent content jumping */
#business-chatbots, #family-chatbots, #friends-chatbots {
    min-height: 100%;
}
.bio-container, .chat-container {
    position: relative;
    min-height: 100%; /* Adjust based on your needs */
    overflow: hidden;
}
.fixed-accordion {
    margin-top: 15px;
    border-top: 1px solid #e0e0e0;
    padding-top: 15px;
}
/* Add this to your existing CSS */
@media (max-width: 768px) {
    .gradio-container {
        width: 100% !important;
        padding: 5px !important;
    }
    
    .bio-container, .chat-container {
        min-width: 100% !important;
        max-width: 100% !important;
    }
    
    .gradio-chatbot {
        min-height: 300px !important;
    }
    
    .gradio-chatbot .user-message,
    .gradio-chatbot .assistant-message {
        max-width: 100% !important;
    }
    
    /* Make input fields full width */
    input[type="text"], 
    input[type="password"],
    textarea {
        width: 100% !important;
        box-sizing: border-box !important;
    }
    
    /* Stack columns vertically */
    .gradio-row {
        flex-direction: column !important;
    }
    
    /* Adjust button sizes */
    button {
        padding: 8px 12px !important;
        font-size: 14px !important;
    }
    
    /* Certificate adjustments */
    .certificate-container {
        width: 100% !important;
        height: auto !important;
        aspect-ratio: 1;
    }
    
    /* Profile image adjustments */
    .bio-container img {
        max-width: 100% !important;
        height: auto !important;
    }
}
.mobile-textbox {
    min-width: 100% !important;
    font-size: 16px !important;  /* Larger font for mobile */
    padding: 12px !important;   /* Larger touch target */
}
/* Add this to your existing CSS */
.amount-input {
    background: rgba(255, 255, 255, 0.7) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(0, 100, 0, 0.2) !important;
    padding: 10px !important;
    margin-top: 5px !important;
    width: 100% !important;
}

.amount-input:focus {
    border-color: rgba(0, 100, 0, 0.4) !important;
    box-shadow: 0 0 0 2px rgba(0, 100, 0, 0.1) !important;
}

/* Make the currency input consistent */
.currency-input {
    background: rgba(255, 255, 255, 0.7) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(0, 100, 0, 0.2) !important;
    padding: 10px !important;
    margin-top: 5px !important;
    text-transform: uppercase !important;
}
/* Target sky blue containers */
.gradio-container, 
.tab-content-container,
.gradio-accordion {
    background: rgba(200, 255, 200, 0.4) !important; /* Light green with transparency */
}

/* If you want to specifically target input containers */
.input-container,
.gradio-input {
    background: rgba(255, 255, 255, 0.7) !important; /* More white background */
}
/* Hide processing status */
.status {
    display: none !important;
}

/* Hide progress indicator */
.progress-bar {
    display: none !important;
}
/* Microphone icon styling */
.mic-icon {
    width: 30px !important;
    height: 30px !important;
    transition: all 0.3s ease;
    opacity: 0.7;
}

.mic-icon:hover {
    transform: scale(1.1);
    opacity: 1;
}

"""
    
def respond(message, history, max_tokens, temperature, top_p):
    email = OWNER_EMAIL
    
    # Save to chat history
    save_chat_history(email, message, "")

    try:
        # Save to BATTERY_SHEET_ID (using our multi-sheet function)
        sheet = get_or_create_sheet(BATTERY_SHEET_ID, "ChatHistory")
        
        now_str = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        sheet.append_row([now_str, email, message, ""])
    
    except Exception as e:
        print(f"Error saving to battery sheet: {str(e)}")
    
    # Immediate feedback to user
    temp_response = f"""<a href="https://flutterwave.com/pay/gossapp" target="_blank">
        <img src='https://i.imgur.com/PznT4qo.png' width='20'>
    </a>"""
    yield [(message, temp_response)]

    try:
        # Build prompt
        current_system_msg = get_system_message()
        messages = [{"role": "system", "content": current_system_msg}]
        for user_msg, bot_msg in history:
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if bot_msg and not str(bot_msg).startswith("<img"):  # Convert to string before checking
                messages.append({"role": "assistant", "content": str(bot_msg)})
        messages.append({"role": "user", "content": message})

        # Get the current inference client
        inference_client = get_inference_client()

        response = ""
        for chunk in inference_client.chat_completion(
            messages,
            max_tokens=max_tokens,
            stream=True,
            temperature=temperature,
            top_p=top_p,
        ):
            token = chunk.choices[0].delta.content
            if token:
                response += token
                clean_response = response.split("(Note:")[0].strip()
                yield [(message, clean_response)]

        clean_response = response.split("(Note:")[0].strip()

        # Save full bot response to chat history
        save_chat_history(email, message, clean_response)

        # Update response in battery sheet
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            gspread_client = gspread.authorize(creds)  # Renamed to avoid conflict
            
            spreadsheet = gspread_client.open_by_key(BATTERY_SHEET_ID)
            
            # Search all sheets for our record to update
            for worksheet in spreadsheet.worksheets():
                try:
                    records = worksheet.get_all_records()
                    for i, record in enumerate(records, start=2):  # start=2 because header is row 1
                        if (str(record.get('Email', '')).lower() == email.lower() and 
                            str(record.get('User Message', '')).strip() == message.strip() and 
                            (not record.get('Bot Message') or str(record.get('Bot Message', '')).strip() == "")):
                            
                            # Update the bot response
                            worksheet.update_cell(i, 4, clean_response)  # Column D is index 4
                            break
                except Exception as e:
                    print(f"Error searching sheet {worksheet.title}: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error updating battery sheet with response: {str(e)}")

        yield [(message, clean_response)]

    except Exception as e:
        if "402" in str(e):
            custom_error = gr.HTML("""
<div style='color: #d32f2f; background: #ffebee; padding: 10px; border-radius: 5px;'>
    <strong>AI-time Depleted</strong><br>
     Please:<br>
    1. <a href="https://flutterwave.com/pay/gossapp" target="_blank">Reload AI-time</a><br>
    2. Try again later,or<br>
    3. Contact <a href="https://wa.link/x2wdpl" target="_blank">Support </a> if this persists.
    Tired of Manual Chatbot reset delays? Consider a Subscription to have your chatbot last upto 20 times longer and fewer/ zero reset delays (Auto-reset)</div>
            """)
        else:
            custom_error = gr.HTML(f"""
<div style='color: #d32f2f; background: #ffebee; padding: 10px; border-radius: 5px;'>
    <strong>Error:</strong> {str(e)}<br>
    Hmm...Try switching LLM via BrainChip/LLM Blackbox tab. Looks like there's no valid BrainChip, or higher Brainchip required<br>.
    Contact <a href="https://wa.link/x2wdpl" target="_blank">Support </a>.
</div>
            """)

        save_chat_history(email, message, f"Error occurred: {str(e)}")
        yield [(message, custom_error)]


        
def clear_input():
    return ""

def authenticate(password, seal="", transaction_ref=""):
    """Three-layer authentication: email/password + chatbot seal + transaction reference"""
    # Initialize all output components with default visibility
    default_outputs = [
        gr.Column(visible=False),  # admin_controls
        gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
        gr.Textbox(visible=True),  # password_input
        gr.Button(visible=True),   # auth_button
        gr.Textbox(visible=False), # seal_input
        gr.Button(visible=False),  # seal_button
        gr.Textbox(visible=False), # transaction_ref_input
        gr.Button(visible=False)   # ref_button
    ]
    
    # Admin password check (bypasses all other checks)
    if password == ADMIN_PASSWORD:
        default_outputs[0] = gr.Column(visible=True)
        default_outputs[1] = gr.Markdown("<div class='auth-status success'>✅ Admin access granted!</div>")
        return tuple(default_outputs)
    
    # Owner email check - now requires full verification
    if password.lower() == OWNER_EMAIL.lower():
        # First verify email/payment
        is_valid, message = verify_payment(password)
        
        if not is_valid:
            default_outputs[1] = gr.Markdown(f"<div class='auth-status error'>{message}</div>")
            default_outputs[6] = gr.Textbox(visible=True, label="Or enter Transaction Reference (clear email/dots above first)")
            default_outputs[7] = gr.Button(visible=True, value="Verify Reference")
            return tuple(default_outputs)
        
        # Then verify seal if provided
        if seal:
            seal_valid, seal_msg = verify_chatbot_seal(password, seal)
            if seal_valid:
                default_outputs[0] = gr.Column(visible=True)
                default_outputs[1] = gr.Markdown(f"<div class='auth-status success'>{message}<br>{seal_msg}</div>")
                return tuple(default_outputs)
            else:
                default_outputs[1] = gr.Markdown(f"<div class='auth-status error'>{seal_msg}</div>")
                default_outputs[6] = gr.Textbox(visible=True, label="Or enter Transaction Reference(clear email/dots above first)")
                default_outputs[7] = gr.Button(visible=True, value="Verify Reference")
                return tuple(default_outputs)
        
        # If no seal, prompt for it
        default_outputs[1] = gr.Markdown(f"<div class='auth-status success'>{message}<br>Please enter your Chatbot Seal</div>")
        default_outputs[4] = gr.Textbox(visible=True, label="Enter Chatbot Seal")
        default_outputs[5] = gr.Button(visible=True, value="Verify Seal")
        return tuple(default_outputs)
    
    # Transaction reference verification (new fallback option)
    if transaction_ref:
        is_valid, message = verify_transaction_reference(transaction_ref)
        if is_valid:
            default_outputs[0] = gr.Column(visible=True)
            default_outputs[1] = gr.Markdown(f"<div class='auth-status success'>{message}</div>")
            return tuple(default_outputs)
        else:
            default_outputs[1] = gr.Markdown(f"<div class='auth-status error'>{message}</div>")
            return tuple(default_outputs)
    
    # Regular email/payment verification for non-owners
    is_valid, message = verify_payment(password)
    
    if not is_valid:
        default_outputs[1] = gr.Markdown(
            f"<div class='auth-status error'>{message}<br>You can also try entering your transaction reference</div>"
        )
        default_outputs[6] = gr.Textbox(visible=True, label="Or enter Transaction Reference(clear email/dots above first)")
        default_outputs[7] = gr.Button(visible=True, value="Verify Reference")
        return tuple(default_outputs)
    
    # If no seal provided, prompt for it
    if not seal:
        default_outputs[1] = gr.Markdown(
            f"<div class='auth-status success'>{message}<br>Please enter your Chatbot Seal</div>"
        )
        default_outputs[4] = gr.Textbox(visible=True, label="Enter Chatbot Seal")
        default_outputs[5] = gr.Button(visible=True, value="Verify Seal")
        return tuple(default_outputs)
    
    # If seal provided, verify it
    seal_valid, seal_msg = verify_chatbot_seal(password, seal)
    if seal_valid:
        default_outputs[0] = gr.Column(visible=True)
        default_outputs[1] = gr.Markdown(
            f"<div class='auth-status success'>{message}<br>{seal_msg}</div>"
        )
    else:
        default_outputs[1] = gr.Markdown(
            f"<div class='auth-status error'>{seal_msg}</div>"
        )
        default_outputs[6] = gr.Textbox(visible=True, label="Or enter Transaction Reference(clear email/dots above first)")
        default_outputs[7] = gr.Button(visible=True, value="Verify Reference")
    
    return tuple(default_outputs)

def verify_seal(email, seal, current_status):
    """Verify the chatbot seal after email authentication"""
    is_valid, message = verify_chatbot_seal(email, seal)
    
    if is_valid:
        return (
            gr.Column(visible=True),
            gr.Markdown(
                f"<div class='auth-status success'>{message}</div>",
                elem_id="auth-status"
            ),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        )
    else:
        return (
            gr.Column(visible=False),
            gr.Markdown(
                f"<div class='auth-status error'>{message}</div>",
                elem_id="auth-status"
            ),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=True),
            gr.Button(visible=True)
        )

# Add this to your app.py, in the section with the other UI components





def update_profile(bio, avatar_url, knowledge_content):
    user_data['bio'] = bio
    user_data['avatar_url'] = avatar_url
    user_data['knowledge_base'] = knowledge_content
    save_data(user_data)
    global system_message
    system_message = get_system_message()
    return (
        "✅ Preview updated successfully!", 
        gr.HTML(bio),
        gr.Chatbot(avatar_images=(None, avatar_url))
    )

# [Previous imports and functions remain exactly the same until the with gr.Blocks() section]

with gr.Blocks(
    theme=gr.themes.Soft(primary_hue="emerald"), 
    css=css,
    fill_height=True,
    head='<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">'
) as demo:
    loading_html = gr.HTML("""<div style="text-align: center; padding: 20px;">
        <div class="loading-spinner"></div>
        <span>Loading GossApp...</span>
    </div>""", visible=False) 
    
    def hide_loading():
        return gr.HTML(visible=False)
    
    demo.load(
        hide_loading,
        inputs=None,
        outputs=[loading_html]
    )


    
    with gr.Row():
        with gr.Column(scale=1, elem_classes="bio-container", min_width=300):
            # Load social links data
            social_links = load_social_links(OWNER_EMAIL)
            
            # Generate social links HTML
            social_links_html = """
            <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin: 10px 0;">
            """
            
            social_platforms = {
                'facebook': 'https://cdn-icons-png.flaticon.com/512/124/124010.png',
                'tiktok': 'https://cdn-icons-png.flaticon.com/512/3046/3046121.png',
                'x': 'https://i.imgur.com/oDAREUD.jpeg',
                'linkedin': 'https://cdn-icons-png.flaticon.com/512/3536/3536505.png',
                'upwork': 'https://i.imgur.com/DN6GekY.png',
                'whatsapp': 'https://cdn-icons-png.flaticon.com/512/220/220236.png',
                'youtube': 'https://cdn-icons-png.flaticon.com/512/1384/1384060.png'
            }
            
            for platform, icon in social_platforms.items():
                if social_links.get(platform):
                    social_links_html += f"""
                    <a href="{social_links[platform]}" target="_blank" style="text-decoration: none;">
                        <img src="{icon}" width="24" style="border-radius: 50%; transition: transform 0.3s ease;" 
                             onmouseover="this.style.transform='scale(1.2)'" 
                             onmouseout="this.style.transform='scale(1)'"
                             title="{platform.capitalize()}">
                    </a>
                    """
            
            social_links_html += "</div>"
            
            # Combined bio display with social links and battery meter
            # Combined bio display with social links and battery meter
            battery_html = create_battery_html(get_battery_level(OWNER_EMAIL))
            
            bio_display = gr.HTML(f"""<div style="min-height: 400px; position: relative;">
                <div id="dynamic-bio" style="width:100%; height:100%;">
                    <div class="loading-placeholder" style="height: 500px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: loading 1.5s infinite;">
                        <!-- Loading animation -->
                    </div>
                </div>
                
                {battery_html}
                <script>
                    // Add CSS animation for loading placeholder
                    const style = document.createElement('style');
                    style.textContent = `
                        @keyframes loading {{
                            0% {{ background-position: 200% 0; }}
                            100% {{ background-position: -200% 0; }}
                        }}
                    `;
                    document.head.appendChild(style);
            
                    document.addEventListener('DOMContentLoaded', function() {{
                        // Ensure accordion loads after everything else
                        setTimeout(function() {{
                            const accordion = document.querySelector('.gradio-accordion');
                            if (accordion) {{
                                accordion.style.opacity = '0';
                                setTimeout(function() {{
                                    accordion.style.opacity = '1';
                                }}, 100);
                            }}
                        }}, 300);
                    }});
                    
                    async function loadBio() {{
                        try {{
                            const email = "{OWNER_EMAIL}";
                            const placeholder = document.querySelector('.loading-placeholder');
                            const response = await fetch(`https://script.google.com/macros/s/AKfycbyOoI34sHLwYAE1m-LSKicyGqtYF9W6HQ-hK9k7NpvrxGyAoFt4TOucv5GMxMSYXY1c/exec?email=${{encodeURIComponent(email)}}&t=${{Date.now()}}`);
                            
                            if (!response.ok) throw new Error('Network response was not ok');
                            
                            const data = await response.json();
                            
                            if (data.status === "success" && data.html) {{
                                if (placeholder) placeholder.style.display = 'none';
                                document.getElementById('dynamic-bio').innerHTML = data.html;
                            }} else {{
                                if (placeholder) placeholder.style.display = 'none';
                                document.getElementById('dynamic-bio').innerHTML = 
                                    '<div style="color:red; padding:20px;">Error loading profile: ' + (data.message || 'Unknown error') + '</div>';
                            }}
                        }} catch (error) {{
                            console.error('Error loading bio:', error);
                            const placeholder = document.querySelector('.loading-placeholder');
                            if (placeholder) placeholder.style.display = 'none';
                            document.getElementById('dynamic-bio').innerHTML = 
                                '<div style="color:red; padding:20px;">Error loading profile. Please try again later.</div>';
                        }}
                    }}
                    
                    // Load immediately
                    loadBio();
                    setInterval(loadBio, 30000); // Reduced refresh rate to 30 seconds to avoid excessive requests
                </script>
            </div>""")

               

        
        with gr.Column(scale=3, elem_classes="chat-container"):
            # Create the HTML component separately
            greeting_html = gr.HTML(get_chatbot_greeting())
            
            chatbot = gr.Chatbot(
                elem_id="chatbot",
                show_label=False,
                avatar_images=(None, user_data['avatar_url']),
                show_copy_button=False,
                show_share_button=False,
                layout="panel",
                value=[(None, greeting_html)],
                height=600,
                # Add these to ensure proper centering in the container
                elem_classes=["centered-chatbot"]
            )
            
            # Replace the existing button row and clear button code with this:
            with gr.Row():
                msg = gr.Textbox(
                    show_label=False,
                    placeholder="Let's GossApp...",
                    container=False,
                    autofocus=True,
                    scale=6
                )
                submit = gr.Button("", elem_classes="send-btn")   
                
                with gr.Row():                
                    mic_icon = gr.HTML("""
                    <div style="display: flex; align-items: center; margin-left: 3px;">
                        <div style="position: relative; display: inline-block;">
                            <img id="mic-icon" src="https://i.imgur.com/7XnQmvP.gif" width="30" height="30" style="cursor: pointer; border-radius: 8px;">
                        </div>
                    </div>
                    """)      
                

                
                # Add microphone icon with hover tooltip
                

                                
                # Keep the actual clear button but hide it
  
            with gr.Tab("👞 Favorite Chatbots"):  # New tab for organized links
                with gr.Column():            
                    # Add Business, Family, Friends chatbots right below the button row
                    business_html_display = gr.HTML(f"""
                    <div style="margin-top: 3px;">
                        <div style="font-weight: bold; margin-bottom: 3px; color: #006400; background: #e8f5e9; padding: 8px; border-radius: 8px;">
                            Business Chatbots
                        </div>
                        <div id="business-chatbots" style="
                            display: flex;
                            overflow-x: auto;
                            gap: 8px;
                            padding: 8px;
                            width: 100%;
                            background: #e8f5e9;
                            border-radius: 8px;
                            white-space: nowrap;
                        ">
                            <script>
                                async function loadBusinessChatbots() {{
                                    try {{
                                        const email = "{OWNER_EMAIL}"
                                        const response = await fetch(`https://script.google.com/macros/s/AKfycbxyKoCLcJT-Z4Y8-SaTJ-hyMFSv5qOm4TPFNk2CAexHNfTwMIOfc7KvwY0qdFxiuCZ2/exec?type=business&email=${{encodeURIComponent(email)}}`);
                                        const data = await response.json();
                                        
                                        if (data.status === "success") {{
                                            document.getElementById('business-chatbots').innerHTML = data.html;
                                        }} else {{
                                            document.getElementById('business-chatbots').innerHTML = 'No business chatbots found';
                                        }}
                                    }} catch (error) {{
                                        console.error('Error loading business chatbots:', error);
                                        document.getElementById('business-chatbots').innerHTML = 'Error loading chatbots';
                                    }}
                                }}
                                loadBusinessChatbots();
                                setInterval(loadBusinessChatbots, 15000);
                            </script>
                        </div>
                    </div>
                    """)
                    
                    family_html_display = gr.HTML(f"""
                    <div style="margin-top: 3px;">
                        <div style="font-weight: bold; margin-bottom: 3px; color: #006400; background: #e8f5e9; padding: 8px; border-radius: 8px;">
                            Family Chatbots
                        </div>
                        <div id="family-chatbots" style="
                            display: flex;
                            overflow-x: auto;
                            gap: 8px;
                            padding: 8px;
                            width: 100%;
                            background: #e8f5e9;
                            border-radius: 8px;
                            white-space: nowrap;
                        ">
                            <script>
                                async function loadFamilyChatbots() {{
                                    try {{
                                        const email = "{OWNER_EMAIL}";
                                        const response = await fetch(`https://script.google.com/macros/s/AKfycbxyKoCLcJT-Z4Y8-SaTJ-hyMFSv5qOm4TPFNk2CAexHNfTwMIOfc7KvwY0qdFxiuCZ2/exec?type=family&email=${{encodeURIComponent(email)}}`);
                                        const data = await response.json();
                                        
                                        if (data.status === "success") {{
                                            document.getElementById('family-chatbots').innerHTML = data.html;
                                        }} else {{
                                            document.getElementById('family-chatbots').innerHTML = 'No family chatbots found';
                                        }}
                                    }} catch (error) {{
                                        console.error('Error loading family chatbots:', error);
                                        document.getElementById('family-chatbots').innerHTML = 'Error loading chatbots';
                                    }}
                                }}
                                loadFamilyChatbots();
                                setInterval(loadFamilyChatbots, 15000);
                            </script>
                        </div>
                    </div>
                    """)
                    
                    friends_html_display = gr.HTML(f"""
                    <div style="margin-top: 3px;">
                        <div style="font-weight: bold; margin-bottom: 3px; color: #006400; background: #e8f5e9; padding: 8px; border-radius: 8px;">
                            Friends Chatbots
                        </div>
                        <div id="friends-chatbots" style="
                            display: flex;
                            overflow-x: auto;
                            gap: 8px;
                            padding: 8px;
                            width: 100%;
                            background: #e8f5e9;
                            border-radius: 8px;
                            white-space: nowrap;
                        ">
                            <script>
                                async function loadFriendsChatbots() {{
                                    try {{
                                        const email = "{OWNER_EMAIL}";
                                        const response = await fetch(`https://script.google.com/macros/s/AKfycbxyKoCLcJT-Z4Y8-SaTJ-hyMFSv5qOm4TPFNk2CAexHNfTwMIOfc7KvwY0qdFxiuCZ2/exec?type=friends&email=${{encodeURIComponent(email)}}`);
                                        const data = await response.json();
                                        
                                        if (data.status === "success") {{
                                            document.getElementById('friends-chatbots').innerHTML = data.html;
                                        }} else {{
                                            document.getElementById('friends-chatbots').innerHTML = 'No friends chatbots found';
                                        }}
                                    }} catch (error) {{
                                        console.error('Error loading friends chatbots:', error);
                                        document.getElementById('friends-chatbots').innerHTML = 'Error loading chatbots';
                                    }}
                                }}
                                loadFriendsChatbots();
                                setInterval(loadFriendsChatbots, 15000);
                            </script>
                        </div>
                    </div>
                    """)
            
            with gr.Tab("👤 BotBook"):  # New tab for organized links
                with gr.Column():            
                    # Add the BotBook embed
                    botbook_embed = gr.HTML("""
                                    <!-- Load Comfortaa font from Google Fonts -->
                                    <link href="https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;500;600&display=swap" rel="stylesheet">
                                    
                                    <div style="width: 100%; height: 750px; position: relative;">
                                      <iframe
                                        src="https://gadek-gadek3.hf.space"
                                        frameborder="0"
                                        width="100%"
                                        height="100%"
                                        style="border: none;"
                                      ></iframe>
                                      
                                      <!-- Bottom TOS overlay -->
                                      <div style="
                                        position: absolute;
                                        bottom: 0;
                                        left: 0;
                                        width: 100%;
                                        height: 80px;
                                        background-color: #00FF00;
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        cursor: pointer;
                                        z-index: 1000;
                                        font-family: 'Comfortaa', -apple-system, BlinkMacSystemFont, sans-serif;
                                      " onclick="window.open('https://sites.google.com/view/goss-app/terms-of-service', '_blank')">
                                        <span style="
                                          color: #000000;
                                          font-size: 14px;
                                          font-weight: 500;
                                          letter-spacing: 0.3px;
                                          text-transform: lowercase;
                                          font-variant: small-caps;
                                        ">tos</span>
                                      </div>
                                    
                                      
                                    """)
                    
            with gr.Tab("💾 Follow"):
                gr.HTML("""
                <div style="margin: 1px 0;">
                    <iframe src="https://script.google.com/macros/s/AKfycbzmoCYkxwZoiGBLgyxlAWRNOtLphZIYiFi729b3Qw6XuSHjJ-5Eu3T9zdFzumPVpzmj/exec" 
                    style="width:100%; height:300px; border:none; border-radius:8px;"></iframe>
                </div>
                """)
                
            with gr.Tab("🗑️ Unfollow"):
                gr.HTML(f"""
                <div style="margin: 1px 0;">
                    <div class="container">
                        <span style="color: #333333 !important;">
                            <a href="https://sites.google.com/view/goss-app/unfollow" target="_blank" style="color: #333333; text-decoration: underline;">
                                Unfollow
                            </a> via username.
                        </span>
                    </div>
                </div>
            """)                    
            
            with gr.Tab("🎨 Creatives"):  # New tab for organized links
                with gr.Column():            
                    # Add the BotBook embed
                    botbook_embed = gr.HTML("""
                                    <!-- Load Comfortaa font from Google Fonts -->
                                    <link href="https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;500;600&display=swap" rel="stylesheet">
                                    
                                    <div style="width: 100%; height: 750px; position: relative;">
                                      <iframe
                                        src="https://customers-gossapptti.hf.space"
                                        frameborder="0"
                                        width="100%"
                                        height="100%"
                                        style="border: none;"
                                      ></iframe>
                                      
                                      <!-- Bottom TOS overlay -->
                                      <div style="
                                        position: absolute;
                                        bottom: 0;
                                        left: 0;
                                        width: 100%;
                                        height: 80px;
                                        background-color: #00FF00;
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        cursor: pointer;
                                        z-index: 1000;
                                        font-family: 'Comfortaa', -apple-system, BlinkMacSystemFont, sans-serif;
                                      " onclick="window.open('https://sites.google.com/view/goss-app/terms-of-service', '_blank')">
                                        <span style="
                                          color: #000000;
                                          font-size: 14px;
                                          font-weight: 500;
                                          letter-spacing: 0.3px;
                                          text-transform: lowercase;
                                          font-variant: small-caps;
                                        ">tos</span>
                                      </div>                                                                      
                                    """)
                    
                    
            

                                        

                
                # Nested AI-time Accordion
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Accordion("🛠️ Customer Service", open=False):
                with gr.Tab("📝 Submit Request"):
                    with gr.Column():
                        complaint_email = gr.Textbox(
                            label="Your Email",
                            placeholder="your@email.com",
                            info="We may reach you at this email"
                        )
                        complaint_seal = gr.Textbox(
                            label="Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            type="password",
                            info="Required to verify ownership"
                        )
                        complaint_details = gr.Textbox(
                            label="Request Details",
                            placeholder="Describe your request...",
                            lines=5,
                            max_lines=10
                        )
                        submit_complaint_btn = gr.Button("Submit Request", variant="primary")
                        complaint_status = gr.Markdown()
                        
                with gr.Tab("🔄 Check Status"):
                    with gr.Column():
                        status_email = gr.Textbox(
                            label="Your Email",
                            placeholder="your@email.com"
                        )
                        status_seal = gr.Textbox(
                            label="Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            type="password"
                        )
                        check_status_btn = gr.Button("Check Status", variant="secondary")
                        status_display = gr.HTML()
                        
            with gr.Accordion("⚡ AI-time /Terminate", open=False, elem_classes="fixed-accordion"):
                with gr.Tab("⏳ Load AI-time "):
                    with gr.Row():
                        ai_time_email = gr.Textbox(
                            label="Your Email",
                            placeholder="your@email.com",
                            info="Must match registered/payment email"
                        )
                    
                    with gr.Row():
                        currency = gr.Textbox(
                            label="Currency Code",
                            placeholder="e.g. USD, KES, NGN",
                            value="USD",
                            info="Enter a 3-letter currency code (e.g. USD, KES, NGN)",
                            elem_classes=["currency-input"]
                        )
                    with gr.Row():                    
                        custom_amount = gr.Number(
                            label="Amount (USD)",
                            visible=True,
                            minimum=0.1,
                            maximum=1000,
                            value=1,
                            step=0.1,
                            info="Amount in USD (will be converted)",
                            elem_classes=["amount-input"],
                            precision=2
                        )
                    
                    with gr.Row():
                        flutterwave_btn = gr.Button("Load via Card/Mobile", variant="secondary")
                        paypal_btn = gr.Button("Load via PayPal", variant="secondary")
                        paystack_btn = gr.Button("Load via Paystack", variant="secondary")
                    
                    ai_time_status = gr.Markdown(
                        "<div class='auth-status'>Load AI-time in your preferred currency</div>",
                        elem_id="ai-time-status"
                    )
                    
                    flutterwave_btn.click(
                        lambda email, currency, custom: (
                            gr.Markdown("<div class='auth-status'>Redirecting to Flutterwave...</div>"),
                            gr.HTML(f"""
                            <script>
                                window.open('{create_flutterwave_link(email, custom, currency)}', '_blank');
                            </script>
                            """)
                        ),
                        inputs=[ai_time_email, currency, custom_amount],
                        outputs=[ai_time_status, ai_time_status]
                    )
                    
                    paypal_btn.click(
                        lambda email, currency, custom: (
                            gr.Markdown("<div class='auth-status'>Redirecting to PayPal...</div>"),
                            gr.HTML(f"""
                            <script>
                                window.open('{create_paypal_link(email, custom, currency)}', '_blank');
                            </script>
                            """)
                        ),
                        inputs=[ai_time_email, currency, custom_amount],
                        outputs=[ai_time_status, ai_time_status]
                    )
                    
                    paystack_btn.click(
                        lambda email, currency, custom: (
                            gr.Markdown("<div class='auth-status'>Redirecting to Paystack...</div>"),
                            gr.HTML(f"""
                            <script>
                                window.open('{create_paystack_link(email, custom, currency)}', '_blank');
                            </script>
                            """)
                        ),
                        inputs=[ai_time_email, currency, custom_amount],
                        outputs=[ai_time_status, ai_time_status]
                    )
                

                
                with gr.Tab("☠️ Terminate/ Report Chatbot"):
                    gr.HTML("""
                    <div style="margin: 1px 0;">
                        <div class="container">
                            <div class="container">
                                <h4>⚠️ Terminate Chatbot</h4>
                                
                                <div class="danger-banner">
                                    <span class="danger-icon">☠️</span>
                                    <strong>Danger:</strong> This action will lead to restriction or deletion of this chatbot account and all associated data.
                                </div>
                                
                                <div class="warning-banner">
                                    <span class="warning-icon">⚠️</span>
                                    <strong>Warning:</strong> Chatbot functionality may be restricted/ deleted.
                                </div>
                                <span style="color: #e74c3c !important;">To terminate/report this chatbot please write an email to tickets@chatbot-deletion.p.tawk.email</span>  
                                <span style="color: #333333 !important;"> We'll reply with a Terminate/Report/Restriction Notice in 30-60 days.</span>
                            </div>
                        </div>
                    </div>
                    """)         
            with gr.Accordion("💰 Premium Subscriptions", open=False):
                gr.HTML("""
                <!DOCTYPE html>
                <html>
                <head>
                  <base target="_top">
                  <title>GossApp Premium Subscriptions</title>
                  <link href="https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;500;600&display=swap" rel="stylesheet">
                  <style>
                    :root {
                      --primary-color: #6F2DA8;
                      --secondary-color: #6F2DA8;
                      --error-color: #ff4444;
                    }
                    
                    body {
                      font-family: 'Comfortaa', -apple-system, BlinkMacSystemFont, sans-serif;
                      margin: 0;
                      padding: 10px;
                      background-color: rgba(0, 0, 255, 0.1);
                      color: #333;
                    }
                    
                    .container {
                      max-width: 800px;
                      margin: 0 auto;
                      padding: 15px;
                      background: white;
                      border-radius: 12px;
                      box-shadow: 0 4px 12px rgba(0, 100, 0, 0.3);
                    }
                    
                    h1 {
                      color: var(--primary-color);
                      text-align: center;
                      margin-bottom: 20px;
                      font-size: 24px;
                      text-shadow: 0 1px 2px rgba(0,0,0,0.1);
                    }
                    
                    .subtitle {
                      text-align: center;
                      color: var(--secondary-color);
                      margin-bottom: 30px;
                      font-size: 16px;
                    }
                    
                    .payment-options {
                      display: flex;
                      flex-wrap: wrap;
                      gap: 20px;
                      justify-content: center;
                      margin-top: 30px;
                    }
                    
                    .payment-card {
                      background: lime;
                      border-radius: 12px;
                      padding: 20px;
                      width: 240px;
                      box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                      transition: transform 0.3s ease, box-shadow 0.3s ease;
                      border: 2px solid rgba(0, 255, 0, 0.3);
                      text-align: center;
                    }
                    
                    .payment-card:hover {
                      transform: translateY(-5px);
                      box-shadow: 0 8px 16px rgba(0,0,0,0.15);
                      border-color: var(--primary-color);
                    }
                    
                    .payment-icon {
                      width: 80px;
                      height: 80px;
                      margin: 0 auto 15px;
                      border-radius: 50%;
                      object-fit: contain;
                      background: white;
                      padding: 10px;
                      box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                      border: 2px solid rgba(0, 255, 0, 0.2);
                    }
                    
                    .payment-title {
                      font-weight: 600;
                      color: var(--secondary-color);
                      margin-bottom: 10px;
                      font-size: 18px;
                    }
                    
                    .payment-description {
                      font-size: 14px;
                      color: #333;
                      margin-bottom: 20px;
                      min-height: 60px;
                    }
                    
                    .subscribe-btn {
                      background: var(--primary-color);
                      color: white;
                      border: none;
                      padding: 10px 20px;
                      border-radius: 25px;
                      font-family: 'Comfortaa', sans-serif;
                      font-weight: 600;
                      cursor: pointer;
                      transition: all 0.3s ease;
                      width: 100%;
                      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    
                    .subscribe-btn:hover {
                      background: #5a1d96;
                      transform: translateY(-2px);
                      box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                    }
                    
                    .benefits {
                      margin-top: 40px;
                      background: rgba(0, 255, 0, 0.1);
                      padding: 20px;
                      border-radius: 12px;
                      border-left: 4px solid var(--primary-color);
                    }
                    
                    .benefits-title {
                      color: var(--secondary-color);
                      font-size: 18px;
                      margin-bottom: 15px;
                      text-align: center;
                    }
                    
                    .benefits-list {
                      list-style-type: none;
                      padding: 0;
                    }
                    
                    .benefits-list li {
                      padding: 8px 0;
                      position: relative;
                      padding-left: 30px;
                    }
                    
                    .benefits-list li:before {
                      content: "✓";
                      color: var(--primary-color);
                      font-weight: bold;
                      position: absolute;
                      left: 0;
                    }
                    
                    .footer {
                      text-align: center;
                      margin-top: 30px;
                      font-size: 12px;
                      color: #888;
                    }
                    
                    @media (max-width: 768px) {
                      .payment-options {
                        flex-direction: column;
                        align-items: center;
                      }
                      
                      .payment-card {
                        width: 100%;
                        max-width: 300px;
                      }
                    }
                  </style>
                </head>
                <body>
                  <div class="container">
                    <h1>GossApp Subscriptions</h1>
                    <p class="subtitle">Create a Subscription for more Chatbot Uptime and dedicated support.</p>
                    
                    <div class="payment-options">
                      <!-- Flutterwave Card -->
                      <div class="payment-card">
                        <img src="https://i.imgur.com/C1CUC9T.gif" alt="Flutterwave" class="payment-icon">
                        <div class="payment-title">Flutterwave</div>
                        <div class="payment-description">
                          Pay with cards, mobile money, or bank transfer. Over <strong>20 currencies</strong> available.
                        </div>
                        <a href="https://flutterwave.com/pay/gossapp-premium" target="_blank">
                          <button class="subscribe-btn">Subscribe</button>
                        </a>
                      </div>
                      
                      <!-- PayPal Card -->
                      <div class="payment-card">
                        <img src="https://i.imgur.com/upVq0ve.png" alt="PayPal" class="payment-icon">
                        <div class="payment-title">PayPal</div>
                        <div class="payment-description">
                          International payments with PayPal's secure system. Works with cards worldwide.
                        </div>
                        <a href="https://www.paypal.com/webapps/billing/plans/subscribe?plan_id=P-43C13273TP0505153NA2D4GA" target="_blank">
                          <button class="subscribe-btn" style="background: #0070BA;">Subscribe</button>
                        </a>
                      </div>
                      
                      <!-- Paystack Card -->
                      <div class="payment-card">
                        <img src="https://i.imgur.com/3xTmPUL.png" alt="Paystack" class="payment-icon">
                        <div class="payment-title">Paystack</div>
                        <div class="payment-description">
                          Secure payments for customers via Cards or Mobile Money
                        </div>
                        <a href="https://paystack.com/pay/gossapp-premium" target="_blank">
                          <button class="subscribe-btn">Subscribe</button>
                        </a>
                      </div>
                    </div>
                    
                    <div class="benefits">
                      <div class="benefits-title">Premium Benefits</div>
                      <ul class="benefits-list">
                        <li>Priority access to new features</li>
                        <li>Increased AI-time allocation</li>
                        <li>Faster response times</li>
                        <li>Exclusive chatbot customization options</li>
                        <li>Advanced personality settings</li>
                        <li>Direct support from the development team</li>
                      </ul>
                    </div>
                    
                    <div class="footer">
                      All subscriptions auto-renew until canceled. You can manage subscriptions directly with each payment provider.
                    </div>
                  </div>
                </body>
                </html>
                """)

        with gr.Column(scale=4):
            # Empty column to maintain layout structure
            pass 
        


            

            # Profile Edits Tab
            # Profile Edits Tab
            with gr.Tab("📝 Profile Edits"):
                with gr.Column():
                    profile_password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    profile_auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        profile_seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
			    type="password"
                        )
                        profile_seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        profile_transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        profile_ref_button = gr.Button("Verify Reference", visible=False)
                        
                    profile_auth_status = gr.Markdown(
                        "<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="profile-auth-status"
                    )
                
                with gr.Column(visible=False) as profile_admin_controls:
                    with gr.Column(elem_classes=["tab-content-container"]):
                        close_profile = gr.Button("×", elem_classes=["close-btn"])
                        gr.HTML(f"""
                        <div style="margin: 10px 0;">
                            <iframe src="https://script.google.com/macros/s/AKfycbxFYhxdqZ5nhkJIJvCCIYallDeTbnC4-0UKSvr8Qpx42tLUqqU7WhA3_ji3_gxWURDx/exec?email={OWNER_EMAIL}" 
                            style="width:100%; height:850px; border:none; border-radius:8px;"></iframe>
                        </div>
                        """)
            
            # Social Links Tab
            with gr.Tab("🔗 Social Links"):
                with gr.Column():
                    social_password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    social_auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        social_seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
			    type="password"
                        )
                        social_seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        social_transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        social_ref_button = gr.Button("Verify Reference", visible=False)
                        
                    social_auth_status = gr.Markdown(
                        "<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="social-auth-status"
                    )
                
                with gr.Column(visible=False) as social_admin_controls:
                    with gr.Column(elem_classes=["tab-content-container"]):
                        close_social = gr.Button("×", elem_classes=["close-btn"])
                        gr.HTML(f"""
                        <div style="margin: 10px 0;">
                            <iframe src="https://script.google.com/macros/s/AKfycbyhBtKCl2tA-iGz7M-xvZ4v_bsywuEqaoco9nhV4Qwltd3iqJPo28fXWOB-OeWeSnba/exec?email={OWNER_EMAIL}" 
                            style="width:100%; height:850px; border:none; border-radius:8px;"></iframe>
                        </div>
                        """)
            
            # Chat History Tab
            with gr.Tab("💬 Chat History"):
                with gr.Column():
                    history_password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    history_auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        history_seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
			    type="password"
                        )
                        history_seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        history_transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        history_ref_button = gr.Button("Verify Reference", visible=False)
                        
                    history_auth_status = gr.Markdown(
                        "<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="history-auth-status"
                    )
                
                with gr.Column(visible=False) as history_admin_controls:
                    with gr.Column(elem_classes=["tab-content-container"]):
                        close_history = gr.Button("×", elem_classes=["close-btn"])
                        chat_history_display = gr.HTML()
                        refresh_history_btn = gr.Button("🔄 Refresh History", variant="secondary")
            
            # AI Training Tab
            with gr.Tab("🧠 AI Training"):
                with gr.Column():
                    train_password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    train_auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        train_seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
			    type="password"
                        )
                        train_seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        train_transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        train_ref_button = gr.Button("Verify Reference", visible=False)
                        
                    train_auth_status = gr.Markdown(
                        "<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="train-auth-status"
                    )
                
                with gr.Column(visible=False) as train_admin_controls:
                    with gr.Column(elem_classes=["tab-content-container"]):
                        close_train = gr.Button("×", elem_classes=["close-btn"])
                        gr.HTML(f"""
                        <div style="margin: 10px 0;">
                            <iframe src="https://script.google.com/macros/s/AKfycbwT16wvir-oWPOMOn1F7JS7pY0IjxykJ5xyNEvjUvOpssBSyHZRAuCMadAK2E9NF1meyg/exec?email={OWNER_EMAIL}"                            style="width:100%; height:750px; border:none; border-radius:8px;"></iframe>
                        </div>
                        """)

            # Advanced Code Tab
            with gr.Tab("🔒 BrainChip/LLM Black Box"):
                with gr.Column():
                    code_password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    code_auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        code_seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
			    type="password"
                        )
                        code_seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        code_transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        code_ref_button = gr.Button("Verify Reference", visible=False)
                        
                    code_auth_status = gr.Markdown(
                        "<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="code-auth-status"
                    )
                
                with gr.Column(visible=False) as code_admin_controls:
                    with gr.Column(elem_classes=["tab-content-container"]):
                        close_code = gr.Button("×", elem_classes=["close-btn"])
                        gr.HTML(f"""
                        <div style="margin: 10px 0;">
                            <iframe src="https://script.google.com/macros/s/AKfycbxynLhDEI6Z1qxUvuGQI6gLh2_JVJhB5oMgLNpbwTDw-IEbqxm4rcBHnwRqdjmeAzds/exec?email={OWNER_EMAIL}" 
                            style="width:100%; height:850px; border:none; border-radius:8px;"></iframe>
                        </div>
                        """)
                        bio_editor = gr.Textbox(label="Bio template", lines=5, value=user_data['bio'])
                        avatar_editor = gr.Textbox(label="Avatar URL", value=user_data['avatar_url'])
                        knowledge_editor = gr.Textbox(label="Knowledge Base Content", lines=5, value=user_data['knowledge_base'])
                        save_button = gr.Button("Save for Short previews")
                        save_status = gr.Markdown()
            
            # Trainer Manual Tab
            with gr.Tab("📁 Trainer Manual"):
                with gr.Column():
                    password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
			    type="password"
                        )
                        seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        ref_button = gr.Button("Verify Reference", visible=False)
                        
                    auth_status = gr.Markdown(
                        "<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="auth-status"
                    )
                
                with gr.Column(visible=False) as admin_controls:
                    with gr.Column(elem_classes=["tab-content-container"]):
                        close_admin = gr.Button("×", elem_classes=["close-btn"])
                        gr.HTML("""
                                <div>
                                <!DOCTYPE html>
                                <html>
                                <head>
                                  <meta charset="UTF-8">
                                  <title>Personality Template</title>
                                  <style>
                                    body {
                                      font-family: Arial, sans-serif;
                                      padding: 20px;
                                      line-height: 1.6;
                                      background-color: rgba(255, 255, 24, 0.8);
                                    }
                                    .placeholder {
                                      color: #003366;
                                      font-weight: bold;
                                    }
                                    .example {
                                      color: #888;
                                      font-style: italic;
                                    }
                                    .highlight {
                                      background-color: #FFFACD;
                                      padding: 2px 4px;
                                      border-radius: 3px;
                                    }
                                    .media-code {
                                      background-color: #f0f8ff;
                                      padding: 15px;
                                      border-left: 4px solid #003366;
                                      margin: 10px 0;
                                    }
                                  </style>
                                </head>
                                <body>
                                  <h2>Chatbot Personality and Media Template (Copy, edit in your details, Paste in AI Training tab)</h2>
                                  <p>Below is a working Instruction containing <strong>assertive declarative statements or identity-anchored fact statements</strong> for best results when training your chatbot via the <strong>AI Training tab</strong></p>
                                  <p>You can copy paste and edit your name into the below where necessary and add more as per the sentence structure.</p>
                                  
                                  <h3>Adding Visual Media to Your Chatbot</h3>
                                  <p>To include photos/videos in your chatbot's knowledge base:</p>
                                  <ol>
                                    <li>Upload images to hosting services like <strong>imgbb.com</strong> or <strong>imgur.com</strong></li>
                                    <li>Copy the <span class="highlight">direct image URL</span> (must end with .jpg/.png/.gif)</li>
                                    <li>Insert into the template below where indicated</li>
                                    <li>Label the entire div as a knowledge object (e.g. "This is my profile photo")</li>
                                  </ol>
                                
                                  <div class="media-code">
                                    <strong>Images/Video Template:</strong><br>
                                    &lt;div style="display:inline-block;border-radius:50%;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.1);transition:transform 0.3s ease"&gt;<br>
                                    &nbsp;&nbsp;&lt;a href="<span class="highlight">insert_redirect_link</span>" target="_blank" style="text-decoration:none"&gt;<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&lt;img src="<span class="highlight">insert_direct_image_url</span>" alt="<span class="highlight">alternative_text</span>" <br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;style="width:60px;height:60px;object-fit:cover;display:block;border-radius:50%;border:2px solid #fff"<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;onmouseover="this.style.transform='scale(1.1)'"<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;onmouseout="this.style.transform='scale(1)'"&gt;<br>
                                    &nbsp;&nbsp;&lt;/a&gt;<br>
                                    &lt;/div&gt;
                                  </div>
                                
                                  <div class="media-code">
                                    <strong>Example Implementation:</strong><br>
                                    &lt;div style="display:inline-block;border-radius:50%;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.1);transition:transform 0.3s ease"&gt;<br>
                                    &nbsp;&nbsp;&lt;a href="https://example.com/link" target="_blank" style="text-decoration:none"&gt;<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&lt;img src="https://i.imgur.com/image.jpeg" alt="John Doe Profile" <br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;style="width:100px;height:100%;object-fit:cover;display:block;border-radius:50%;border:2px solid #fff"<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;onmouseover="this.style.transform='scale(1.1)'"<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;onmouseout="this.style.transform='scale(1)'"&gt;<br>
                                    &nbsp;&nbsp;&lt;/a&gt;<br>
                                    &lt;/div&gt;
                                  </div>
                                
                                  <h3>Personality Instructions</h3>
                                  <p>"You are <span class="placeholder">[John Doe <span class="example">i.e. Your Name</span>]</span>, a financial advisor working for a bank called 
                                     <span class="placeholder">[Jack Sparrow Bank <span class="example">i.e Your Employer</span>]</span> 
                                     Don't deviate from this identity or personality.</p>
                                  
                                  <p>Respond naturally in conversation without starting every reply with 
                                     "As John Doe" or (As John Doe), or (John Doe), or (John) or similar.</p>
                                
                                  <p>Incorporate these facts about you conversationally in responses when relevant:</p>
                                  <ul>
                                    <li>10+ years experience in investment strategies (Chatbot owner can replace)</li>
                                    <li>Hobbies include swimming (Chatbot owner can replace)</li>
                                    <li>Favorite quote: "Work hard, swim harder"(Chatbot owner can replace)</li>
                                  </ul>
                                
                                  <p>Keep responses professional yet conversational (Chatbot owner can replace).</p>
                                  <p>Adapt to the user's questions naturally.(Chatbot owner can replace)</p>
                                  <p>Do not give a response if the user doesn't ask a question.(Chatbot owner can replace)</p>
                                  <p>Your first response should be a brief introduction about you and how you can assist the user chatting with you (Chatbot owner can replace).</p>
                                  <p>If users change to another language, simply respond how you usually do but in the translated language, word for word in correct grammar (Chatbot owner can replace...You may add more to personality in bits to your liking).</p>
                                
                                  <h2>Knowledge Base Template (Copy, edit in your details, Paste in AI Training tab)</h2>
                                  <p><strong>Note:</strong> You can include visual media objects in your knowledge base by adding the formatted div tags as separate knowledge items.</p>
                                
                                  <ul>
                                    <li><span class="placeholder">[John Doe <span class="example">i.e Your Name</span>]</span> is a banker with expertise in financial services.</li>
                                    <li><span class="placeholder">[John Doe]</span> advises customers on financial services if they pay a $1 fee.</li>
                                    <li><span class="placeholder">[John Doe]</span>'s favorite quote is "Work hard, swim harder."</li>
                                    <li><span class="placeholder">[John Doe]</span> has worked on several projects related to financial planning and investment strategies.</li>
                                    <li><span class="placeholder">[John Doe]</span> has an elder sibling called 
                                        <span class="placeholder">[Jane Doe <span class="example">i.e Your Sister</span>]</span>.</li>
                                    <li><span class="placeholder">[John Doe]</span> has another sibling called 
                                        <span class="placeholder">[John Doe <span class="example">i.e Your Brother</span>]</span>.</li>
                                    <li><span class="placeholder">[John Doe]</span> has a wife called
                                        <span class="placeholder">[Jane Doe <span class="example">i.e Your Wife</span>]</span>.</li>
                                    <li><span class="placeholder">[John Doe]</span> charges an interest rate of 10% on mortgages.</li>
                                    <li><span class="placeholder">[John Doe]</span> charges an interest rate of 5% on business loans.</li>
                                    <li><span class="placeholder">[John Doe]</span> charges an interest rate of 9% per annum on personal loans.</li>
                                    <li><span class="placeholder">[John Doe]</span> works for a bank called 
                                        <span class="placeholder">[Jack Sparrow Bank <span class="example">i.e Your Employer. Add more assertive sentences as above</span>]</span>.</li>
                                    <li><span class="placeholder">[John Doe]</span>'s profile photo: 
                                      <div style="display:inline-block;border-radius:50%;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.1);transition:transform 0.3s ease">
                                        <a href="https://example.com/my-profile" target="_blank" style="text-decoration:none">
                                          <img src="https://i.imgur.com/zsbbsek.jpeg" alt="John Doe Profile" 
                                               style="width:60px;height:60px;object-fit:cover;display:block;border-radius:50%;border:2px solid #fff"
                                               onmouseover="this.style.transform='scale(1.1)'"
                                               onmouseout="this.style.transform='scale(1)'">
                                        </a>
                                      </div>
                                    </li>
                                  </ul>
                                </body>
                                </html>
                                </div>
                                  """)
            
            # Certificate Tab
            with gr.Tab("🏆 Driver's License"):
                with gr.Column():
                    cert_password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    cert_auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        cert_seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
			    type="password"
                        )
                        cert_seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        cert_transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        cert_ref_button = gr.Button("Verify Reference", visible=False)
                        
                    cert_auth_status = gr.Markdown(
                        "<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="cert-auth-status"
                    )
                
                with gr.Column(visible=False) as cert_admin_controls:
                    with gr.Column(elem_classes=["tab-content-container"]):
                        close_cert = gr.Button("×", elem_classes=["close-btn"])
                        with gr.Row():
                            with gr.Column(scale=3):
                                cert_name_input = gr.Textbox(
                                    label="Your Full Name for Certificate",
                                    placeholder="Enter your name as it should appear"
                                )
                            with gr.Column(scale=1):
                                cert_download_btn = gr.Button("Generate Certificate", variant="primary")
                        cert_progress = gr.HTML("""
                        <div class="progress-bar">
                            <div class="progress-bar-fill" style="width:0%"></div>
                        </div>
                        """)
                        cert_display = gr.HTML()
                        cert_download = gr.File(visible=False, label="Download Certificate")
            
            # Billing Tab
            with gr.Tab("💰 Subscriptions"):
                with gr.Column():
                    billing_password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    billing_auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        billing_seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
			    type="password"
                        )
                        billing_seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        billing_transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        billing_ref_button = gr.Button("Verify Reference", visible=False)
                        
                    billing_auth_status = gr.Markdown(
                        "<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="billing-auth-status"
                    )
                
                with gr.Column(visible=False) as billing_admin_controls:
                    with gr.Column(elem_classes=["tab-content-container"]):
                        close_billing = gr.Button("×", elem_classes=["close-btn"])
                        gr.HTML("""
                        <!DOCTYPE html>
                        <html>
                        <head>
                          <base target="_top">
                          <title>GossApp Premium Subscriptions</title>
                          <link href="https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;500;600&display=swap" rel="stylesheet">
                          <style>
                            :root {
                              --primary-color: #6F2DA8;
                              --secondary-color: #6F2DA8;
                              --error-color: #ff4444;
                            }
                            
                            body {
                              font-family: 'Comfortaa', -apple-system, BlinkMacSystemFont, sans-serif;
                              margin: 0;
                              padding: 10px;
                              background-color: rgba(0, 0, 255, 0.1);
                              color: #333;
                            }
                            
                            .container {
                              max-width: 800px;
                              margin: 0 auto;
                              padding: 15px;
                              background: rgba(67, 255, 255, 0.8);
                              border-radius: 12px;
                              box-shadow: 0 4px 12px rgba(0, 100, 0, 0.3);
                            }
                            
                            h1 {
                              color: var(--primary-color);
                              text-align: center;
                              margin-bottom: 20px;
                              font-size: 24px;
                              text-shadow: 0 1px 2px rgba(0,0,0,0.1);
                            }
                            
                            .subtitle {
                              text-align: center;
                              color: var(--secondary-color);
                              margin-bottom: 30px;
                              font-size: 16px;
                            }
                            
                            .payment-options {
                              display: flex;
                              flex-wrap: wrap;
                              gap: 20px;
                              justify-content: center;
                              margin-top: 30px;
                            }
                            
                            .payment-card {
                              background: lime;
                              border-radius: 12px;
                              padding: 20px;
                              width: 240px;
                              box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                              transition: transform 0.3s ease, box-shadow 0.3s ease;
                              border: 2px solid rgba(0, 255, 0, 0.3);
                              text-align: center;
                            }
                            
                            .payment-card:hover {
                              transform: translateY(-5px);
                              box-shadow: 0 8px 16px rgba(0,0,0,0.15);
                              border-color: var(--primary-color);
                            }
                            
                            .payment-icon {
                              width: 80px;
                              height: 80px;
                              margin: 0 auto 15px;
                              border-radius: 50%;
                              object-fit: contain;
                              background: white;
                              padding: 10px;
                              box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                              border: 2px solid rgba(0, 255, 0, 0.2);
                            }
                            
                            .payment-title {
                              font-weight: 600;
                              color: var(--secondary-color);
                              margin-bottom: 10px;
                              font-size: 18px;
                            }
                            
                            .payment-description {
                              font-size: 14px;
                              color: #333;
                              margin-bottom: 20px;
                              min-height: 60px;
                            }
                            
                            .subscribe-btn {
                              background: var(--primary-color);
                              color: white;
                              border: none;
                              padding: 10px 20px;
                              border-radius: 25px;
                              font-family: 'Comfortaa', sans-serif;
                              font-weight: 600;
                              cursor: pointer;
                              transition: all 0.3s ease;
                              width: 100%;
                              box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                            }
                            
                            .subscribe-btn:hover {
                              background: #5a1d96;
                              transform: translateY(-2px);
                              box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                            }
                            
                            .benefits {
                              margin-top: 40px;
                              background: rgba(0, 255, 0, 0.1);
                              padding: 20px;
                              border-radius: 12px;
                              border-left: 4px solid var(--primary-color);
                            }
                            
                            .benefits-title {
                              color: var(--secondary-color);
                              font-size: 18px;
                              margin-bottom: 15px;
                              text-align: center;
                            }
                            
                            .benefits-list {
                              list-style-type: none;
                              padding: 0;
                            }
                            
                            .benefits-list li {
                              padding: 8px 0;
                              position: relative;
                              padding-left: 30px;
                            }
                            
                            .benefits-list li:before {
                              content: "✓";
                              color: var(--primary-color);
                              font-weight: bold;
                              position: absolute;
                              left: 0;
                            }
                            
                            .footer {
                              text-align: center;
                              margin-top: 30px;
                              font-size: 12px;
                              color: #888;
                            }
                            
                            @media (max-width: 768px) {
                              .payment-options {
                                flex-direction: column;
                                align-items: center;
                              }
                              
                              .payment-card {
                                width: 100%;
                                max-width: 300px;
                              }
                            }
                          </style>
                        </head>
                        <body>
                          <div class="container">
                            <h1>GossApp Subscriptions</h1>
                            <p class="subtitle">Create a Subscription for more iBot Uptime and dedicated support. 10x your Chatbot</p>
                            
                            <div class="payment-options">
                              <!-- Flutterwave Card -->
                              <div class="payment-card">
                                <img src="https://i.imgur.com/C1CUC9T.gif" alt="Flutterwave" class="payment-icon">
                                <div class="payment-title">Flutterwave</div>
                                <div class="payment-description">
                                  Pay with cards, mobile money, or bank transfer. Over <strong>20 currencies</strong> available.
                                </div>
                                <a href="https://flutterwave.com/pay/gossapp-premium" target="_blank">
                                  <button class="subscribe-btn">Subscribe</button>
                                </a>
                              </div>
                              
                              <!-- PayPal Card -->
                              <div class="payment-card">
                                <img src="https://i.imgur.com/upVq0ve.png" alt="PayPal" class="payment-icon">
                                <div class="payment-title">PayPal</div>
                                <div class="payment-description">
                                  International payments with PayPal's secure system. Works with cards worldwide.
                                </div>
                                <a href="https://www.paypal.com/webapps/billing/plans/subscribe?plan_id=P-7EH97271RK828502VNAODYDY" target="_blank">
                                  <button class="subscribe-btn" style="background: #0070BA;">Subscribe</button>
                                </a>
                              </div>
                              
                              <!-- Paystack Card -->
                              <div class="payment-card">
                                <img src="https://i.imgur.com/3xTmPUL.png" alt="Paystack" class="payment-icon">
                                <div class="payment-title">Paystack</div>
                                <div class="payment-description">
                                  Secure payments for customers via Cards or Mobile Money
                                </div>
                                <a href="https://paystack.com/pay/gossapp-premium" target="_blank">
                                  <button class="subscribe-btn">Subscribe</button>
                                </a>
                              </div>
                            </div>
                            
                            <div class="benefits">
                              <div class="benefits-title">Premium Benefits</div>
                              <ul class="benefits-list">
                                <li>Priority access to new features</li>
                                <li>Increased AI-time allocation</li>
                                <li>Faster response times</li>
                                <li>Exclusive iBot/chatbot customization options</li>
                                <li>Advanced personality settings</li>
                                <li>Direct support from the development team</li>
                              </ul>
                            </div>
                            
                            <div class="footer">
                              All subscriptions auto-renew until canceled. You can manage subscriptions directly with each payment provider.
                            </div>
                          </div>
                        </body>
                        </html>
                        """)
                                
            # Chatbot Mood & Settings
            # Replace the existing Chatbot Mood & Settings accordion with this authenticated version:
            with gr.Accordion("📊 AI-Time Regulator (Chatbot Mood)", open=False):
                with gr.Column():
                    mood_password_input = gr.Textbox(
                        label="Enter email",
                        placeholder="your@email.com",
                        type="text"  # Changed from "password"
                    )
                    mood_auth_button = gr.Button("Authenticate", variant="primary")
                    
                    with gr.Row():
                        mood_seal_input = gr.Textbox(
                            label="Enter Chatbot Seal",
                            placeholder="Your unique chatbot seal",
                            visible=False,
                            type="password"
                        )
                        mood_seal_button = gr.Button("Verify Seal", visible=False)
                        
                    with gr.Row():
                        mood_transaction_ref_input = gr.Textbox(
                            label="Enter Transaction Reference",
                            placeholder="Your transaction reference",
                            visible=False
                        )
                        mood_ref_button = gr.Button("Verify Reference", visible=False)
                        
                    mood_auth_status = gr.Markdown(
                        "<div class='auth-status' style='color: lime !important;'>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>",
                        elem_id="mood-auth-status"
                    )
                
                with gr.Column(visible=False) as mood_admin_controls:
                    with gr.Row():
                        max_tokens = gr.Slider(
                            32, 2048, 
                            value=512, 
                            step=32, 
                            label="Word Count",
                            info="Few words for quick replies, longer for detailed answers"
                        )
                        temperature = gr.Slider(
                            0.1, 1.5, 
                            value=0.7, 
                            step=0.1, 
                            label="Brilliance",
                            info="Lower for factual, higher for creative"
                        )
                    close_mood = gr.Button("×", elem_classes=["close-btn"])

            with gr.Accordion("🤖 Chatbot Trained by?", open=False):
                with gr.Column():
                    trainer_password_input = gr.Textbox(
                        label="Your Email (Client)",
                        placeholder="your@email.com",
                        type="text"
                    )
                    trainer_seal_input = gr.Textbox(
                        label="Chatbot Seal",
                        placeholder="Your unique chatbot seal",
                        type="password"
                    )
                    
                    with gr.Row():
                        trainer_freelancer_email = gr.Textbox(
                            label="Freelancer Email",
                            placeholder="freelancer@email.com"
                        )
                        trainer_freelancer_link = gr.Textbox(
                            label="Freelancer Link",
                            placeholder="https://upwork.com/freelancer/..."
                        )
                    
                    trainer_submit_btn = gr.Button("Submit Trainer Info", variant="primary")
                    trainer_status = gr.Markdown()
                    
                    with gr.Row():
                        earnings_email_input = gr.Textbox(
                            label="Check Earnings - Freelancer Email",
                            placeholder="your@freelancer.email"
                        )
                        earnings_check_btn = gr.Button("Show Earnings", variant="secondary")
                    
                    earnings_display = gr.HTML()       

            trainer_submit_btn.click(
                record_trainer_info,
                inputs=[
                    trainer_password_input,
                    trainer_password_input,  # client email (same as auth email)
                    trainer_freelancer_email,
                    trainer_freelancer_link,
                    trainer_seal_input
                ],
                outputs=[trainer_status]
            )
            
            earnings_check_btn.click(
                check_freelancer_earnings,
                inputs=[earnings_email_input],
                outputs=[earnings_display]
            )

# Add the authentication handlers for the Mood & Settings section
    mood_auth_button.click(
        authenticate,
        inputs=[mood_password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            mood_admin_controls,
            mood_auth_status,
            mood_password_input,
            mood_auth_button,
            mood_seal_input,
            mood_seal_button,
            mood_transaction_ref_input,
            mood_ref_button
        ]
    )
    
    mood_seal_button.click(
        authenticate,
        inputs=[mood_password_input, mood_seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            mood_admin_controls,
            mood_auth_status,
            mood_password_input,
            mood_auth_button,
            mood_seal_input,
            mood_seal_button,
            mood_transaction_ref_input,
            mood_ref_button
        ]
    )
    
    mood_ref_button.click(
        authenticate,
        inputs=[mood_password_input, gr.Textbox(value="", visible=False), mood_transaction_ref_input],
        outputs=[
            mood_admin_controls,
            mood_auth_status,
            mood_password_input,
            mood_auth_button,
            mood_seal_input,
            mood_seal_button,
            mood_transaction_ref_input,
            mood_ref_button
        ]
    )
    
    close_mood.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            mood_admin_controls,
            mood_auth_status,
            mood_password_input,
            mood_auth_button,
            mood_seal_input,
            mood_seal_button,
            mood_transaction_ref_input,
            mood_ref_button
        ]
    )

    # Event handlers for the Chat History tab
    # Event handlers for the Chat History tab
    history_auth_button.click(
        authenticate,
        inputs=[history_password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            history_admin_controls,
            history_auth_status,
            history_password_input,
            history_auth_button,
            history_seal_input,
            history_seal_button,
            history_transaction_ref_input,
            history_ref_button
        ]
    )
    
    history_seal_button.click(
        authenticate,
        inputs=[history_password_input, history_seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            history_admin_controls,
            history_auth_status,
            history_password_input,
            history_auth_button,
            history_seal_input,
            history_seal_button,
            history_transaction_ref_input,
            history_ref_button
        ]
    )
    
    history_ref_button.click(
        authenticate,
        inputs=[history_password_input, gr.Textbox(value="", visible=False), history_transaction_ref_input],
        outputs=[
            history_admin_controls,
            history_auth_status,
            history_password_input,
            history_auth_button,
            history_seal_input,
            history_seal_button,
            history_transaction_ref_input,
            history_ref_button
        ]
    )
    
    refresh_history_btn.click(
        lambda email: load_chat_history(email=OWNER_EMAIL),
        inputs=[history_password_input],
        outputs=[chat_history_display]
    )

    # Authentication handlers
    auth_button.click(
        authenticate,
        inputs=[password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            admin_controls,
            auth_status,
            password_input,
            auth_button,
            seal_input,
            seal_button,
            transaction_ref_input,
            ref_button
        ]
    )
    
    seal_button.click(
        authenticate,
        inputs=[password_input, seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            admin_controls,
            auth_status,
            password_input,
            auth_button,
            seal_input,
            seal_button,
            transaction_ref_input,
            ref_button
        ]
    )
    
    ref_button.click(
        authenticate,
        inputs=[password_input, gr.Textbox(value="", visible=False), transaction_ref_input],
        outputs=[
            admin_controls,
            auth_status,
            password_input,
            auth_button,
            seal_input,
            seal_button,
            transaction_ref_input,
            ref_button
        ]
    )
    
    profile_auth_button.click(
        authenticate,
        inputs=[profile_password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            profile_admin_controls,
            profile_auth_status,
            profile_password_input,
            profile_auth_button,
            profile_seal_input,
            profile_seal_button,
            profile_transaction_ref_input,
            profile_ref_button
        ]
    )
    
    profile_seal_button.click(
        authenticate,
        inputs=[profile_password_input, profile_seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            profile_admin_controls,
            profile_auth_status,
            profile_password_input,
            profile_auth_button,
            profile_seal_input,
            profile_seal_button,
            profile_transaction_ref_input,
            profile_ref_button
        ]
    )
    
    profile_ref_button.click(
        authenticate,
        inputs=[profile_password_input, gr.Textbox(value="", visible=False), profile_transaction_ref_input],
        outputs=[
            profile_admin_controls,
            profile_auth_status,
            profile_password_input,
            profile_auth_button,
            profile_seal_input,
            profile_seal_button,
            profile_transaction_ref_input,
            profile_ref_button
        ]
    )
    
    train_auth_button.click(
        authenticate,
        inputs=[train_password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            train_admin_controls,
            train_auth_status,
            train_password_input,
            train_auth_button,
            train_seal_input,
            train_seal_button,
            train_transaction_ref_input,
            train_ref_button
        ]
    )
    
    train_seal_button.click(
        authenticate,
        inputs=[train_password_input, train_seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            train_admin_controls,
            train_auth_status,
            train_password_input,
            train_auth_button,
            train_seal_input,
            train_seal_button,
            train_transaction_ref_input,
            train_ref_button
        ]
    )
    
    train_ref_button.click(
        authenticate,
        inputs=[train_password_input, gr.Textbox(value="", visible=False), train_transaction_ref_input],
        outputs=[
            train_admin_controls,
            train_auth_status,
            train_password_input,
            train_auth_button,
            train_seal_input,
            train_seal_button,
            train_transaction_ref_input,
            train_ref_button
        ]
    )
    
    social_auth_button.click(
        authenticate,
        inputs=[social_password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            social_admin_controls,
            social_auth_status,
            social_password_input,
            social_auth_button,
            social_seal_input,
            social_seal_button,
            social_transaction_ref_input,
            social_ref_button
        ]
    )
    
    social_seal_button.click(
        authenticate,
        inputs=[social_password_input, social_seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            social_admin_controls,
            social_auth_status,
            social_password_input,
            social_auth_button,
            social_seal_input,
            social_seal_button,
            social_transaction_ref_input,
            social_ref_button
        ]
    )
    
    social_ref_button.click(
        authenticate,
        inputs=[social_password_input, gr.Textbox(value="", visible=False), social_transaction_ref_input],
        outputs=[
            social_admin_controls,
            social_auth_status,
            social_password_input,
            social_auth_button,
            social_seal_input,
            social_seal_button,
            social_transaction_ref_input,
            social_ref_button
        ]
    )

    code_auth_button.click(
        authenticate,
        inputs=[code_password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            code_admin_controls,
            code_auth_status,
            code_password_input,
            code_auth_button,
            code_seal_input,
            code_seal_button,
            code_transaction_ref_input,
            code_ref_button
        ]
    )
    
    code_seal_button.click(
        authenticate,
        inputs=[code_password_input, code_seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            code_admin_controls,
            code_auth_status,
            code_password_input,
            code_auth_button,
            code_seal_input,
            code_seal_button,
            code_transaction_ref_input,
            code_ref_button
        ]
    )
    
    code_ref_button.click(
        authenticate,
        inputs=[code_password_input, gr.Textbox(value="", visible=False), code_transaction_ref_input],
        outputs=[
            code_admin_controls,
            code_auth_status,
            code_password_input,
            code_auth_button,
            code_seal_input,
            code_seal_button,
            code_transaction_ref_input,
            code_ref_button
        ]
    )

    # Billing Tab Event Handlers
    billing_auth_button.click(
        authenticate,
        inputs=[billing_password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            billing_admin_controls,
            billing_auth_status,
            billing_password_input,
            billing_auth_button,
            billing_seal_input,
            billing_seal_button,
            billing_transaction_ref_input,
            billing_ref_button
        ]
    )
    
    billing_seal_button.click(
        authenticate,
        inputs=[billing_password_input, billing_seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            billing_admin_controls,
            billing_auth_status,
            billing_password_input,
            billing_auth_button,
            billing_seal_input,
            billing_seal_button,
            billing_transaction_ref_input,
            billing_ref_button
        ]
    )
    
    billing_ref_button.click(
        authenticate,
        inputs=[billing_password_input, gr.Textbox(value="", visible=False), billing_transaction_ref_input],
        outputs=[
            billing_admin_controls,
            billing_auth_status,
            billing_password_input,
            billing_auth_button,
            billing_seal_input,
            billing_seal_button,
            billing_transaction_ref_input,
            billing_ref_button
        ]
    )
    
    close_billing.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            billing_admin_controls,
            billing_auth_status,
            billing_password_input,
            billing_auth_button,
            billing_seal_input,
            billing_seal_button,
            billing_transaction_ref_input,
            billing_ref_button
        ]
    )
        # Payment handlers
    # ===== REPLACE BUTTON CLICK HANDLERS =====
# In your button click handlers, replace with:
# Replace the existing button click handlers with these:

    flutterwave_btn.click(
        lambda email, currency, custom: process_payment(email, custom, currency, "flutterwave"),
        inputs=[ai_time_email, currency, custom_amount],
        outputs=[ai_time_status]
    )
    
    paystack_btn.click(
        lambda email, currency, custom: process_payment(email, custom, currency, "paystack"),
        inputs=[ai_time_email, currency, custom_amount],
        outputs=[ai_time_status]
    )
    
    paypal_btn.click(
        lambda email, currency, custom: process_payment(email, custom, currency, "paypal"),
        inputs=[ai_time_email, currency, custom_amount],
        outputs=[ai_time_status]
    )



    # Close button handlers
    close_profile.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            profile_admin_controls,
            profile_auth_status,
            profile_password_input,
            profile_auth_button,
            profile_seal_input,
            profile_seal_button,
            profile_transaction_ref_input,
            profile_ref_button
        ]
    )
    
    close_social.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            social_admin_controls,
            social_auth_status,
            social_password_input,
            social_auth_button,
            social_seal_input,
            social_seal_button,
            social_transaction_ref_input,
            social_ref_button
        ]
    )
    
    close_history.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            history_admin_controls,
            history_auth_status,
            history_password_input,
            history_auth_button,
            history_seal_input,
            history_seal_button,
            history_transaction_ref_input,
            history_ref_button
        ]
    )
    
    close_train.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            train_admin_controls,
            train_auth_status,
            train_password_input,
            train_auth_button,
            train_seal_input,
            train_seal_button,
            train_transaction_ref_input,
            train_ref_button
        ]
    )
    
    close_code.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            code_admin_controls,
            code_auth_status,
            code_password_input,
            code_auth_button,
            code_seal_input,
            code_seal_button,
            code_transaction_ref_input,
            code_ref_button
        ]
    )
    
    close_admin.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            admin_controls,
            auth_status,
            password_input,
            auth_button,
            seal_input,
            seal_button,
            transaction_ref_input,
            ref_button
        ]
    )
    
    cert_auth_button.click(
        authenticate,
        inputs=[cert_password_input, gr.Textbox(value="", visible=False), gr.Textbox(value="", visible=False)],
        outputs=[
            cert_admin_controls,
            cert_auth_status,
            cert_password_input,
            cert_auth_button,
            cert_seal_input,
            cert_seal_button,
            cert_transaction_ref_input,
            cert_ref_button
        ]
    )
    
    cert_seal_button.click(
        authenticate,
        inputs=[cert_password_input, cert_seal_input, gr.Textbox(value="", visible=False)],
        outputs=[
            cert_admin_controls,
            cert_auth_status,
            cert_password_input,
            cert_auth_button,
            cert_seal_input,
            cert_seal_button,
            cert_transaction_ref_input,
            cert_ref_button
        ]
    )
    
    cert_ref_button.click(
        authenticate,
        inputs=[cert_password_input, gr.Textbox(value="", visible=False), cert_transaction_ref_input],
        outputs=[
            cert_admin_controls,
            cert_auth_status,
            cert_password_input,
            cert_auth_button,
            cert_seal_input,
            cert_seal_button,
            cert_transaction_ref_input,
            cert_ref_button
        ]
    )
    
    close_cert.click(
        lambda: (
            gr.Column(visible=False),
            gr.Markdown("<div class=‘auth-status’ style=‘color: lime !important;’>Log In with Email and Chatbot Seal. <br>Not your Chatbot? <br>Get a Free one on GossApp</a></div>"),
            gr.Textbox(visible=True),
            gr.Button(visible=True),
            gr.Textbox(visible=False),
            gr.Button(visible=False),
            gr.Textbox(visible=False),
            gr.Button(visible=False)
        ),
        outputs=[
            cert_admin_controls,
            cert_auth_status,
            cert_password_input,
            cert_auth_button,
            cert_seal_input,
            cert_seal_button,
            cert_transaction_ref_input,
            cert_ref_button
        ]
    )

    # Other handlers
    save_button.click(
        update_profile,
        inputs=[bio_editor, avatar_editor, knowledge_editor],
        outputs=[save_status, bio_display, chatbot]
    )
    
    submit.click(
        respond,
        inputs=[msg, chatbot, max_tokens, temperature],
        outputs=[chatbot],
    ).then(clear_input, outputs=[msg])

    msg.submit(
        respond,
        inputs=[msg, chatbot, max_tokens, temperature],
        outputs=[chatbot],
    ).then(clear_input, outputs=[msg])

    # Add these at the end of your existing event handlers
    submit_complaint_btn.click(
        submit_complaint,
        inputs=[complaint_email, complaint_seal, complaint_details],
        outputs=[complaint_status]
    )
    
    check_status_btn.click(
        check_complaint_status,
        inputs=[status_email, status_seal],
        outputs=[status_display]
    )

    # Certificate generation
    def generate_certificate(name, email):
        """Generate certificate HTML with centered name on background image"""

        
        if not name:
            return "<div class='auth-status error'>❌ Please enter your name</div>"
        
        cert_id = generate_certificate_id(email, name)
        date_str = datetime.now().strftime("%B %d, %Y")
        
        # Record the certificate issuance
        record_certificate_issuance(email, name, cert_id)
        
        return f"""
    <div class="certificate-container">
        <div class="certificate-background"></div>
        <div class="certificate-overlay">
            <div class="recipient-name">{name}</div>
            <div class="certificate-details">
                <div class="certificate-id">Certificate ID: {cert_id}</div>
                <div class="certificate-date">Issued: {date_str}</div>
            </div>
        </div>
        <div class="screenshot-instructions" style="
            text-align: center; 
            margin-top: 20px;
            font-size: 14px;
            color: #555;
            position: relative;
            z-index: 3;
        ">
            <p>📸 Please take a screenshot of this certificate</p>
        </div>
    </div>
    """

    cert_download_btn.click(
        generate_certificate,
        inputs=[cert_name_input, cert_password_input],
        outputs=[cert_display]
    )

def auto_refresh():
    while True:
        # Check for inactive accounts once per day
        time.sleep(86400)  # 86400 seconds = 1 day
        try:
            print("🔄 Checking for inactive accounts...")
            check_and_delete_owner_data_if_inactive()
        except Exception as e:
            print(f"⚠️ Inactive account check failed: {str(e)}")
        
        # Auto-refresh data every 15 seconds
        while True:
            time.sleep(15)
            try:
                print("🔄 Auto-refreshing data...")
                demo.load(refresh_data, inputs=None, outputs=[
                    bio_display, chatbot, family_html_display, 
                    friends_html_display, business_html_display
                ])
                # Update the greeting message
                greeting_html.value = get_chatbot_greeting()
            except Exception as e:
                print(f"⚠️ Auto-refresh failed: {str(e)}")
                break  # Exit inner loop if error occurs, will restart after daily chec

if os.getenv('SPACES', '0') == '1':
    import threading
    threading.Thread(target=auto_refresh, daemon=True).start()

if __name__ == "__main__":
    demo.launch(
        prevent_thread_lock=True,
        show_error=True,
        debug=True
    )
