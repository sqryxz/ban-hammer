import json
import time
import os
import requests
from datetime import datetime, timedelta, timezone
from xrpl.clients import JsonRpcClient
from xrpl.models import AccountTx
from xrpl.utils import hex_to_str, ripple_time_to_datetime
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# XRP address to monitor
TARGET_ADDRESS = "r4yc85M1hwsegVGZ1pawpZPwj65SVs8PzD"

# Time period to check (in hours)
HOURS_TO_CHECK = 24

# Discord webhook URL (set as environment variable)
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
if not DISCORD_WEBHOOK_URL:
    logging.warning("DISCORD_WEBHOOK_URL environment variable not set. Discord updates will be disabled.")

# Update frequency for Discord (in seconds)
DISCORD_UPDATE_INTERVAL = 3600  # 1 hour in seconds
DISCORD_RETRY_INTERVAL = 300    # 5 minutes in seconds
DISCORD_MAX_MESSAGE_LENGTH = 1900  # Leave some buffer for Discord's 2000 char limit

# XRPL nodes to try (in order)
XRPL_NODES = [
    "https://s1.ripple.com:51234/",  # Ripple node
    "https://s2.ripple.com:51234/",  # Ripple node backup
    "https://xrplcluster.com",       # Public cluster
]

def send_discord_summary():
    """
    Send a summary of blacklisted addresses to Discord.
    Returns True if successful, False otherwise.
    """
    if not DISCORD_WEBHOOK_URL:
        logging.info("Discord updates disabled - webhook URL not set")
        return False

    try:
        # Load blacklisted addresses from the last period
        period_start = datetime.now(timezone.utc) - timedelta(hours=HOURS_TO_CHECK)
        recent_addresses = []
        
        try:
            with open('blacklisted_addresses.json', 'r') as f:
                addresses = json.load(f)
                for addr in addresses:
                    timestamp = datetime.fromisoformat(addr['timestamp'])
                    if timestamp >= period_start:
                        recent_addresses.append(addr)
        except FileNotFoundError:
            logging.warning("No blacklisted addresses file found")
            return False
        except json.JSONDecodeError:
            logging.error("Error reading blacklisted addresses file")
            return False

        logging.info(f"Found {len(recent_addresses)} blacklisted addresses in the last {HOURS_TO_CHECK} hours")
        
        if not recent_addresses:
            logging.info("No new blacklisted addresses to report")
            return True

        # Prepare messages (split into chunks if needed)
        messages = []
        current_message = f"**XRP Blacklist Update (Last {HOURS_TO_CHECK} Hours)**\n\n"
        
        for addr in recent_addresses:
            # Prepare entry for this address
            memo_text = addr.get('memo', '')[:100]  # Shorter memo limit
            if len(addr.get('memo', '')) > 100:
                memo_text += "..."
            
            entry = (
                f"🚫 Address: `{addr['blacklisted_address']}`\n"
                f"🏷️ Task ID: `{addr.get('task_id', 'Unknown')}`\n"
                f"📝 Memo: {memo_text}\n"
                f"🔗 TX Hash: `{addr.get('transaction_hash', 'N/A')}`\n"
                f"⏰ Time: {addr['timestamp']}\n\n"
            )
            
            # Check if adding this entry would exceed Discord's limit
            if len(current_message) + len(entry) > DISCORD_MAX_MESSAGE_LENGTH:
                messages.append(current_message)
                current_message = f"**XRP Blacklist Update (Continued)**\n\n{entry}"
            else:
                current_message += entry
        
        # Add the last message if not empty
        if current_message:
            messages.append(current_message)

        # Send all messages to Discord
        success = True
        for message in messages:
            try:
                response = requests.post(
                    DISCORD_WEBHOOK_URL,
                    json={"content": message},
                    timeout=10
                )
                
                if response.status_code == 204:
                    logging.info("Discord message sent successfully")
                else:
                    logging.error(f"Discord webhook failed with status {response.status_code}: {response.text}")
                    success = False
                    
                # Add a small delay between messages to avoid rate limits
                time.sleep(1)
                    
            except requests.exceptions.RequestException as e:
                logging.error(f"Error sending Discord webhook: {str(e)}")
                success = False
        
        return success
            
    except Exception as e:
        logging.error(f"Unexpected error in send_discord_summary: {str(e)}")
        return False

def get_working_client():
    """Try to connect to different XRPL nodes until one works"""
    for node_url in XRPL_NODES:
        try:
            client = JsonRpcClient(node_url)
            # Test the connection with a simple request
            request = AccountTx(
                account=TARGET_ADDRESS,
                limit=1
            )
            response = client.request(request)
            if response.is_successful():
                print(f"✅ Successfully connected to {node_url}")
                # Debug: Show initial response
                print(f"🔍 Test response status: {response.status}")
                print(f"🔍 Test response contains transactions: {'transactions' in response.result}")
                if 'transactions' in response.result:
                    print(f"🔍 Number of test transactions: {len(response.result['transactions'])}")
                return client
        except Exception as e:
            print(f"⚠️  Failed to connect to {node_url}: {e}")
            continue
    
    raise Exception("❌ Could not connect to any XRPL node")

def save_blacklisted_address(address, memo, tx_hash):
    """Save blacklisted address to a file with timestamp and transaction details"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Extract Task ID if present
    task_id = "Unknown"
    if isinstance(memo, str) and "Task ID:" in memo:
        try:
            task_id = memo.split("Task ID:")[1].strip().split()[0]
        except:
            pass
    
    entry = {
        "blacklisted_address": address,
        "memo": memo,
        "task_id": task_id,
        "transaction_hash": tx_hash,
        "timestamp": timestamp
    }
    
    try:
        with open("blacklisted_addresses.json", "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    
    data.append(entry)
    
    with open("blacklisted_addresses.json", "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"⛔ New blacklisted address saved: {address} (Task ID: {task_id})")

def decode_memo_data(memo_data):
    """Safely decode memo data from hex to string"""
    try:
        return hex_to_str(memo_data)
    except Exception as e:
        print(f"   ⚠️  Error decoding memo: {e}")
        print(f"   🔍 Raw memo data: {memo_data}")
        return None

def check_memo_for_blacklist(memo):
    """Check if a memo contains Task ID: Blacklist"""
    # Get all memo fields
    memo_type = memo.get("MemoType", "")
    memo_format = memo.get("MemoFormat", "")
    memo_data = memo.get("MemoData", "")
    
    # Decode the fields
    decoded_type = decode_memo_data(memo_type) if memo_type else ""
    decoded_format = decode_memo_data(memo_format) if memo_format else ""
    decoded_data = decode_memo_data(memo_data) if memo_data else ""
    
    # Check for "Task ID: Blacklist" in any of the decoded fields
    fields_to_check = [
        decoded_type,
        decoded_format,
        decoded_data
    ]
    
    # Look specifically for "Task ID: Blacklist"
    for field in fields_to_check:
        if field and isinstance(field, str):
            if "Task ID: Blacklist" in field:
                return True, field
    
    return False, None

def get_transaction_date(tx_info):
    """Extract transaction date from either tx_json or meta data"""
    # Try to get date from close_time_iso first (most reliable)
    if "close_time_iso" in tx_info:
        try:
            return datetime.fromisoformat(tx_info["close_time_iso"].replace("Z", "+00:00"))
        except ValueError:
            pass

    # Try tx_json date
    tx = tx_info.get("tx_json", {})
    if "date" in tx:
        return ripple_time_to_datetime(tx["date"])
    
    # Try meta data
    meta = tx_info.get("meta", {})
    if "TransactionIndex" in meta:
        return ripple_time_to_datetime(meta["TransactionIndex"])
    
    # If no date found, return None
    return None

def process_transaction(tx_info, start_time):
    """Process a single transaction and check for Task ID: Blacklist in memo"""
    # Debug: Print raw transaction info
    print("\n🔍 Processing transaction:")
    print(f"Raw tx_info keys: {list(tx_info.keys())}")
    
    tx = tx_info.get("tx_json", {})
    meta = tx_info.get("meta", {})
    
    if not tx:
        print("⚠️  No transaction data found")
        return True

    # Get transaction date
    tx_time = get_transaction_date(tx_info)
    if not tx_time:
        print("⚠️  Could not determine transaction date")
        return True

    # Skip if transaction is older than the specified time period
    if tx_time < start_time:
        print(f"⏰ Skipping transaction from {tx_time} (before {start_time})")
        return False

    tx_type = tx.get("TransactionType", "Unknown")
    tx_hash = tx_info.get("hash", tx.get("hash", "Unknown"))
    source = tx.get("Account", "Unknown")
    destination = tx.get("Destination", "Unknown")
    
    # Handle different amount formats
    amount = tx.get("Amount", "Unknown")
    if isinstance(amount, str):
        try:
            # Convert drops to XRP
            amount = f"{float(amount) / 1000000:.6f} XRP"
        except (ValueError, TypeError):
            amount = f"{amount} (raw value)"
    
    print(f"\n{'='*50}")
    print(f"📎 Transaction Details:")
    print(f"   Type: {tx_type}")
    print(f"   Hash: {tx_hash}")
    print(f"   Time: {tx_time}")
    print(f"   From: {source}")
    if destination != "Unknown":
        print(f"   To: {destination}")
    print(f"   Amount: {amount}")
    
    # Detailed memo processing
    print("\n   📝 Memo Information:")
    if "Memos" in tx:
        print(f"   Found {len(tx['Memos'])} memo(s) in transaction")
        for idx, memo_wrapper in enumerate(tx["Memos"], 1):
            print(f"\n   Memo #{idx}:")
            memo = memo_wrapper.get("Memo", {})
            
            # Check for Task ID: Blacklist
            is_blacklist, matching_content = check_memo_for_blacklist(memo)
            
            # Show all memo fields
            for field in ["MemoType", "MemoFormat", "MemoData"]:
                if field in memo:
                    print(f"   - {field}: {memo[field]}")
                    if field == "MemoData":
                        decoded_memo = decode_memo_data(memo[field])
                        if decoded_memo:
                            print(f"   - Decoded Memo: {decoded_memo}")
            
            if is_blacklist:
                print(f"   🚨 BLACKLIST TASK ID FOUND: {matching_content}")
                if destination != "Unknown":
                    save_blacklisted_address(destination, matching_content, tx_hash)
    else:
        print("   No memos in this transaction")
    
    print(f"{'='*50}\n")
    return True

def monitor_transactions():
    """Monitor transactions for the target address from the past few hours"""
    print(f"🔍 Starting to monitor transactions for address: {TARGET_ADDRESS}")
    print(f"📅 Tracking transactions from the past {HOURS_TO_CHECK} hours...")
    
    # Calculate start time (in UTC)
    start_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_TO_CHECK)
    print(f"⏰ Start time (UTC): {start_time}")
    
    try:
        # Initial connection
        client = get_working_client()
        
        # Keep track of the last transaction we've seen
        marker = None
        continue_processing = True
        transactions_processed = 0
        transactions_with_memos = 0
        consecutive_errors = 0
        last_discord_update = 0
        
        while continue_processing:
            try:
                current_time = time.time()
                
                # Check if it's time for Discord update
                if current_time - last_discord_update >= DISCORD_UPDATE_INTERVAL:
                    if send_discord_summary():
                        last_discord_update = current_time
                    else:
                        # If update fails, retry in 5 minutes
                        last_discord_update = current_time - (DISCORD_UPDATE_INTERVAL - DISCORD_RETRY_INTERVAL)
                
                # Request account transactions
                request = AccountTx(
                    account=TARGET_ADDRESS,
                    limit=100,
                    marker=marker
                )
                
                print("\n🔄 Requesting transactions...")
                response = client.request(request)
                
                if response.is_successful():
                    print("✅ API request successful")
                    print(f"🔍 Response status: {response.status}")
                    
                    consecutive_errors = 0  # Reset error counter on success
                    transactions = response.result.get("transactions", [])
                    print(f"📊 Retrieved {len(transactions)} transactions in this batch")
                    
                    for tx_info in transactions:
                        # If process_transaction returns False, we've reached transactions older than our time period
                        if not process_transaction(tx_info, start_time):
                            continue_processing = False
                            break
                        transactions_processed += 1
                        if "Memos" in tx_info.get("tx_json", {}):
                            transactions_with_memos += 1
                    
                    # Update marker for pagination if available and we should continue
                    if continue_processing and response.result.get("marker"):
                        marker = response.result.get("marker")
                        print(f"📑 Moving to next page with marker: {marker}")
                    else:
                        print(f"\n📊 Summary:")
                        print(f"   ✅ Processed {transactions_processed} total transactions")
                        print(f"   📝 Found {transactions_with_memos} transactions with memos")
                        print(f"   ⏰ Time period: Past {HOURS_TO_CHECK} hours")
                        break
                else:
                    print(f"❌ API request failed with status: {response.status}")
                    print(f"Error details: {response.result}")
            
            except Exception as e:
                print(f"❌ Error: {e}")
                consecutive_errors += 1
                
                # If we get too many consecutive errors, try to reconnect
                if consecutive_errors >= 3:
                    print("🔄 Too many errors, attempting to reconnect...")
                    try:
                        client = get_working_client()
                        consecutive_errors = 0
                    except Exception as e:
                        print(f"❌ Failed to reconnect: {e}")
                        print("⏹️  Stopping due to connection issues.")
                        break
                
                time.sleep(5)  # Wait before retrying
    
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return

if __name__ == "__main__":
    # Send initial Discord summary
    send_discord_summary()
    # Start monitoring
    monitor_transactions() 