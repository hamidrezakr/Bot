# 🚀 Telegram VPN Management Bot

A comprehensive Telegram bot for managing VPN services with multi-server support, manual payment system, and admin dashboard.

## ✨ Features

- **Multi-Server Management**: Connect multiple X-UI / 3x-UI panels
- **User Management**: Create, renew, and manage user accounts
- **Payment System**: Manual payment with receipt verification
- **Admin Dashboard**: Web-based admin panel with statistics and reports
- **Auto-Renewal**: Automatic account renewal with traffic and expiry calculation
- **Docker Support**: Easy deployment with Docker Compose
- **Telegram Bot**: User-friendly interface with inline keyboards

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Bot Framework**: Python-Telegram-Bot (v20+)
- **Database**: SQLite (with aiosqlite)
- **Deployment**: Docker & Docker Compose
- **Frontend**: HTML + CSS + Chart.js

## 📁 Project Structure
```

telegram-V2ray-bot/
├── app/
│ ├── api/ # FastAPI endpoints
│ │ ├── admin/ # Admin panel APIs
│ │ ├── health.py # Health check
│ │ └── webhook.py # Payment webhooks
│ ├── bot/ # Telegram bot handlers
│ ├── models/ # Database models
│ ├── services/ # Business logic
│ ├── templates/ # HTML templates
│ └── utils/ # Helper functions
├── admin_panel.info # Admin credentials
├── requirements.txt # Python dependencies
├── Dockerfile # Docker build file
└── docker-compose.yml # Docker Compose configuration
```


## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Docker & Docker Compose (optional)

### Local Development
```bash
# Clone the repository
git clone https://github.com/hamidrezakr/Bot.git
cd Bot/TelegramBot/telegram-V2ray-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your tokens and credentials

# Run the bot
python -m app.main

# Build and run with Docker Compose
docker compose up -d

# Check logs
docker compose logs -f

# Stop the container
docker compose down


📊 Admin Panel
Access the admin panel at: http://your-server-ip:8000/admin

Default credentials are stored in admin_panel.info.

🔧 Configuration
Create a .env file with the following variables:

BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=your_telegram_user_id

ZARINPAL_MERCHANT_ID=your_merchant_id
WEBHOOK_URL=https://your-domain.com

📸 Screenshots
Admin Dashboard
Panel management

Service configuration

Payment link management

Receipt verification

Sales statistics and reports

Telegram Bot Features
User registration and authentication

Service purchase

Account renewal

Status checking

Payment receipt submission

🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

📄 License
MIT License - See LICENSE for details.

📬 Support
Telegram: @HamidrezaKR

GitHub Issues: Create an issue

