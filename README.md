# Ban Hammer - XRP Blacklist Tracker

A Python-based tool that monitors XRP transactions for "Task ID: Blacklist" in transaction memos, helping maintain a record of blacklisted addresses.

## Features

- 🔍 Monitors XRP transactions for specific addresses
- 📝 Detects "Task ID: Blacklist" in transaction memos
- 🏷️ Tracks blacklist task IDs
- 💾 Stores blacklisted addresses with full transaction details
- 🤖 Automated daily checks via GitHub Actions
- 📢 Discord webhook integration for notifications

## Setup

1. Clone the repository:
```bash
git clone https://github.com/sqryxz/ban-hammer.git
cd ban-hammer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Add your Discord webhook URL:
```bash
DISCORD_WEBHOOK_URL=your_webhook_url_here
```

## Configuration

- `TARGET_ADDRESS`: XRP address to monitor
- `HOURS_TO_CHECK`: Time period to check for transactions (default: 24 hours)
- `DISCORD_UPDATE_INTERVAL`: How often to send Discord updates (default: 1 hour)

## GitHub Actions

The repository includes a GitHub Action that:
- Runs daily at 00:00 UTC
- Checks for new blacklisted addresses
- Sends updates to Discord
- Stores results as artifacts

To set up GitHub Actions:
1. Go to repository Settings > Secrets
2. Add `DISCORD_WEBHOOK_URL` as a secret
3. The action will run automatically daily

## Output Format

Blacklisted addresses are stored in `blacklisted_addresses.json` with the following information:
- Blacklisted address
- Task ID
- Original memo content
- Transaction hash
- Timestamp

## Discord Notifications

Updates are sent to Discord with:
- Address details
- Task ID
- Memo content
- Transaction hash
- Timestamp

## License

MIT License 