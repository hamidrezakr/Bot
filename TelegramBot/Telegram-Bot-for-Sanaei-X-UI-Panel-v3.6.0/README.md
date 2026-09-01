# 🚀 SpaceGate - Telegram VPN Bot

A production-ready Telegram bot for managing X-UI VPN panel (Sanaei v3.6.0) with FastAPI, featuring sales, subscriptions, referral system, and admin panel.

## ✨ Features

### Telegram Bot
- ✅ **Purchase Services**: Buy VPN services with online payment (Zarinpal) or card-to-card
- ✅ **Renew Services**: Renew existing services with automatic expiry calculation
- ✅ **Test Accounts**: Free test accounts with configurable limits (2 per week)
- ✅ **Referral System**: Referral links, discounts, and sub-affiliate management
- ✅ **Sales Partnership**: Bulk purchase with weekly settlement
- ✅ **Channel Membership**: Forced channel membership for bot usage
- ✅ **User Status**: Check service status (volume, expiry, usage)
- ✅ **Gift Accounts**: Scheduled gift account posting to channel
- ✅ **Broadcast**: Send messages/photos to all users

### Admin Panel
- ✅ **Dashboard**: Real-time stats, sales chart, recent activities
- ✅ **Panel Management**: Manage X-UI panels (add/edit/delete/check status)
- ✅ **Service Management**: CRUD for services and categories
- ✅ **Receipt Management**: Approve/reject payment receipts
- ✅ **Reports**: Financial reports with date filters
- ✅ **Staff Management**: Sales partner requests and management
- ✅ **Settings**: All bot settings editable from UI
- ✅ **Message Settings**: Edit welcome/help/support messages
- ✅ **Authentication**: Admin login with captcha and rate limiting

### Payment
- ✅ **Zarinpal**: Online payment gateway integration
- ✅ **Card-to-Card**: Manual receipt upload
- ✅ **Discount System**: Referral discounts + accumulated credit

### Docker
- ✅ **Multi-stage Build**: Optimized image size
- ✅ **Docker Compose**: Easy deployment
- ✅ **Persistent Data**: Database, receipts, logs

## 🏗️ Project Structure


```
├── admin/
│ ├── routes/
│ │ ├── admin_routes.py # Admin API endpoints
│ │ └── auth_routes.py # Authentication
│ ├── static/
│ │ ├── css/admin.css # Admin panel styles
│ │ └── js/admin.js # Admin panel scripts
│ └── templates/ # HTML templates
├── api/
│ ├── handlers/
│ │ ├── message_handler.py # Telegram message handler
│ │ └── keyboard_builder.py # Telegram keyboard builder
│ └── routes/
│ └── webhook.py # Telegram webhook
├── core/
│ ├── config.py # Configuration
│ ├── logging.py # Logging setup
│ └── exceptions.py # Custom exceptions
├── models/ # SQLAlchemy models
├── services/ # Business logic
├── receipts/ # Uploaded receipts
├── broadcast_photos/ # Broadcast photos
├── .env.example # Environment variables example
├── Dockerfile # Docker build
├── docker-compose.yml # Docker Compose
├── requirements.txt # Python dependencies
└── main.py # Application entry point
```




## 🚀 Quick Start

### Prerequisitess
- Python 3.12+
- Docker (optional)

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/yourusername/spacegate-bot.git
cd spacegate-bot

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy .env.example to .env
cp .env.example .env

# 5. Edit .env with your values
nano .env

# 6. Run
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

```




### Docker Deployment

```
# 1. Create .env
cp .env.example .env
nano .env

# 2. Create data directories
mkdir -p /data/receipts /data/broadcast_photos
touch /data/telegram_bot.db /data/bot.log

# 3. Build and run
docker compose up -d --build

# 4. View logs
docker compose logs -f

# 5. Stop
docker compose down
```


⚙️ Environment Variables

Variable	Description
TELEGRAM_BOT_TOKEN	Bot token from @BotFather
TELEGRAM_WEBHOOK_URL	Webhook URL (HTTPS required)
ADMIN_USERNAME	Admin panel username
ADMIN_PASSWORD	Admin panel password
ADMIN_SECRET_KEY	Secret key for sessions
DATABASE_URL	SQLite database path
API_BASE_URL	Internal API URL
HOST	Server host
PORT	Server port
DEBUG	Debug mode
LOG_LEVEL	Logging level
LOG_FILE	Log file path
📚 Key Features Documentation
Referral System
Each user gets a unique referral link: https://t.me/BotUsername?start=ref_USER_ID

First purchase discount: 10% (configurable)

Recurring discount for referrer: 5% (configurable)

Accumulated credit for discounts

Sales Partnership
Apply for partnership via bot

Admin approves with custom limits and discount

Partner purchases without upfront payment

Weekly settlement with online payment

Gift Accounts
Scheduled gift account creation

Post to channel automatically

Auto-delete after configurable duration

Panel rotation support

Test Accounts
Free test accounts with limits

Configurable volume and duration

Weekly limit per user

🔒 Security
✅ Admin login with captcha

✅ Rate limiting (5 attempts → 15 min lockout)

✅ Session cookies

✅ HTTPS webhook

✅ Environment variables for secrets

📊 Monitoring
✅ Health check endpoint

✅ Docker healthcheck

✅ Comprehensive logging

✅ Dashboard real-time stats

🛠️ Tech Stack
Backend: FastAPI, Uvicorn

Bot: python-telegram-bot

Database: SQLite, SQLAlchemy

Payments: Zarinpal API

Templates: Jinja2

Frontend: Bootstrap 5, Chart.js

Deployment: Docker, Docker Compose

📝 License
MIT License

🤝 Support
For support, contact @HamidrezaKR on Telegram.
