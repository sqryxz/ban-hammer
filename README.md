# XRP Blacklist Tracker

Monitors an XRP address for transactions containing "Blacklist" in their memos and tracks the blacklisted addresses.

## Features

- Monitors transactions for the past 24 hours
- Identifies and saves blacklisted addresses
- Sends daily summaries to Discord via webhook
- Tracks total number of blacklisted addresses
- Handles timezone-aware datetime comparisons
- Provides detailed transaction logging

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Discord webhook:
   - Create a webhook in your Discord server
   - Copy the webhook URL
   - Create a `.env` file from `.env.example`
   - Replace the webhook URL with your actual URL

3. Run the script:
```bash
python3 xrp_blacklist_tracker.py
```

## Discord Reports

The script sends daily reports to Discord containing:
- Total number of blacklisted addresses
- New addresses blacklisted in the last 24 hours
- Details for each newly blacklisted address including:
  - The address
  - Reason for blacklisting
  - Timestamp

## Output Files

- `blacklisted_addresses.json`: Contains all blacklisted addresses with timestamps and reasons

## How it works

- The script monitors the XRP address: `r4yc85M1hwsegVGZ1pawpZPwj65SVs8PzD`
- When a transaction with a memo containing "Blacklist" is found, it saves the recipient address to `blacklisted_addresses.json`
- Each entry in the JSON file includes:
  - The blacklisted address
  - The original memo text
  - The transaction hash
  - Timestamp of when it was recorded

## Output

The script creates a `blacklisted_addresses.json` file that stores all found addresses. Each entry looks like:

```json
{
  "blacklisted_address": "rXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  "memo": "Original memo text",
  "transaction_hash": "Transaction hash",
  "timestamp": "2024-XX-XX:XX:XX:XX.XXXXXX"
}
``` 