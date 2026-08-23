Telegram Bot with FastAPI
A production-ready Telegram bot built with FastAPI using layered architecture, colored inline buttons, and comprehensive logging.

Table of Contents
Features

Project Structure

Architecture Overview

Core Components

Menu System

Subscription Plans

Installation & Setup

Configuration

Running the Bot

Deployment

Logging

API Endpoints

Troubleshooting

Security Best Practices

Contributing

Support

License

Features
✅ Layered Architecture: Clean separation of concerns (Presentation, Business Logic, Data layers)

✅ Colored Inline Buttons: Modern Telegram inline keyboard with color-coded buttons (Blue, Green, Red) using Telegram Bot API v9.4+

✅ Comprehensive Logging: Detailed logs for debugging and monitoring (console + file with rotation)

✅ Environment Configuration: All sensitive data stored in .env file

✅ Modular Design: Fully modular and maintainable codebase

✅ Docker Support: Easy deployment with Docker and Docker Compose

✅ Error Handling: Graceful error handling with user-friendly messages

✅ Health Checks: Built-in health check endpoint for monitoring

✅ API Documentation: Auto-generated OpenAPI documentation

✅ User Management: Registration, status tracking, and subordinate management

✅ Subscription System: Multiple plans with different durations (1-4 months) and volumes (10-200GB)

✅ Webhook Support: Real-time updates via Telegram webhooks

✅ Async Processing: Fully asynchronous for optimal performance

Project Structure
text
telegram_bot/
│
├── api/                           # Presentation Layer
│   ├── handlers/                  # Business logic handlers
│   │   ├── keyboard_builder.py    # Builds inline keyboards with colors
│   │   └── message_handler.py     # Handles messages and callbacks
│   └── routes/                    # API endpoints
│       └── webhook.py             # Webhook route and application setup
│
├── core/                          # Core Infrastructure
│   ├── config.py                  # Environment configuration
│   ├── exceptions.py              # Custom exceptions
│   └── logging.py                 # Logging configuration
│
├── models/                        # Data Models
│   ├── user.py                    # User and UserStatus models
│   └── subscription.py            # Subscription models
│
├── services/                      # Business Logic Layer
│   ├── user_service.py            # User management operations
│   └── subscription_service.py    # Subscription management
│
├── utils/                         # Utility Functions
│   └── validators.py              # Input validation utilities
│
├── main.py                        # Application entry point
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker configuration
├── docker-compose.yml             # Docker Compose configuration
├── .env                           # Environment variables
├── bot.log                        # Application log file
└── README.md                      # Project documentation
Architecture Overview
Layered Architecture Diagram
text
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  (API Routes - Webhook endpoints, FastAPI application)     │
├─────────────────────────────────────────────────────────────┤
│                    Handler Layer                            │
│  (Message Handler, Callback Handler, Keyboard Builder)     │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                            │
│  (User Service, Subscription Service - Business Logic)     │
├─────────────────────────────────────────────────────────────┤
│                    Model Layer                              │
│  (User, Subscription - Data Models)                        │
├─────────────────────────────────────────────────────────────┤
│                    Core Layer                               │
│  (Configuration, Logging, Exceptions)                      │
└─────────────────────────────────────────────────────────────┘
Architecture Principles
Principle	Description
Separation of Concerns	Each layer has a specific responsibility
Dependency Injection	Services are injected into handlers
Single Responsibility	Each class/module does one thing
Open/Closed Principle	Extensible without modifying existing code
DRY	Common functionality is centralized
Data Flow
User Registration Flow:

text
User sends /start → handle_start() → user_service.register_user() → User created → Main menu displayed
Purchase Flow:

text
User clicks "خرید سرویس جدید" → handle_buy_service() → Duration menu → Select duration → Plan menu → Select plan → Confirm purchase → Subscription created
Status Check Flow:

text
User clicks "وضعیت من" → handle_status() → user_service.get_user_status() → Status displayed
Core Components
1. Core Layer (core/)
config.py - Configuration Management
Manages all configuration settings from environment variables with Pydantic validation.

Setting	Description
TELEGRAM_BOT_TOKEN	Bot token from @BotFather
TELEGRAM_WEBHOOK_URL	Public webhook URL
DATABASE_URL	Database connection string
SECRET_KEY	Security key for encryption
DEBUG	Debug mode flag
logging.py - Logging Configuration
Configures comprehensive logging with console output and rotating file logs (10MB max, 5 backups).

exceptions.py - Custom Exceptions
Exception	Purpose
TelegramBotError	Base exception for all bot errors
ConfigurationError	Configuration-related errors
UserNotFoundError	User lookup failures
SubscriptionError	Subscription operation failures
2. Models Layer (models/)
user.py - User Models
User: User data with timestamps and status

UserStatus: User status response with subscription info

subscription.py - Subscription Models
SubscriptionType: BASIC, PREMIUM, BUSINESS, TEST

SubscriptionStatus: ACTIVE, EXPIRED, CANCELLED, PENDING

Subscription: Complete subscription data model

3. Services Layer (services/)
user_service.py - User Management
Method	Description
register_user()	Register or update a user
get_user_status()	Get user's current status
get_subordinates()	Get list of subordinate users
add_subordinate()	Add a subordinate user
subscription_service.py - Subscription Management
Method	Description
create_subscription()	Create a new subscription
get_subscription()	Get subscription by ID
get_user_subscriptions()	Get all subscriptions for a user
get_active_subscription()	Get active subscription
renew_subscription()	Renew an existing subscription
cancel_subscription()	Cancel a subscription
check_subscription_status()	Check user's subscription status
create_test_subscription()	Create a 24-hour test subscription
4. Handler Layer (api/handlers/)
keyboard_builder.py - Keyboard Builder
Creates inline keyboards with colored buttons using Telegram Bot API v9.4+.

Available Styles:

Style	Color	Usage
primary	🔵 Blue	Main actions
success	🟢 Green	Confirmations, purchases
danger	🔴 Red	Destructive actions
Methods:

Method	Description
create_main_menu()	Main menu with 4 rows
create_buy_menu()	Purchase menu with durations
create_plan_selection_menu()	Plan selection for specific duration
create_service_menu()	Service menu (test, wallet, guide, support)
create_sub_menu()	Sub-menu with back button
message_handler.py - Message Handler
Handles all incoming messages and callback queries with proper routing.

Key Handlers:

Handler	Callback Data	Description
handle_start()	/start	Registers user and shows main menu
handle_status()	status	Shows user status
handle_buy_service()	buy_service	Opens purchase menu
handle_duration_selection()	duration_*	Handles duration selection
handle_plan_selection()	plan_*	Handles plan selection
handle_confirm_purchase()	confirm_purchase_*	Confirms purchase
handle_test_account()	test_account	Handles test account request
handle_subordinates()	subordinates	Shows subordinate list
handle_wallet()	wallet	Shows wallet information
handle_connection_guide()	connection_guide	Shows connection guide
show_main_menu()	main_menu	Returns to main menu
5. API Routes (api/routes/)
webhook.py - Webhook Endpoints
Endpoint	Method	Description
/webhook	POST	Receives Telegram updates
/set_webhook	POST	Sets the webhook URL
/delete_webhook	POST	Deletes the webhook
/health	GET	Health check endpoint
Menu System
Main Menu (4 Rows with Colored Buttons)
text
┌─────────────────────────────────────────────────────────────┐
│ 🔵 📊 وضعیت من                                            │
├─────────────────────────────────────────────────────────────┤
│ 🟢 🛒 خرید سرویس جدید    │  🟢 🔄 تمدید سرویس           │
├─────────────────────────────────────────────────────────────┤
│ 🔴 🧪 اکانت تست          │  🔴 👥 زیر مجموعه ها          │
├─────────────────────────────────────────────────────────────┤
│ 🔵 ❓ راهنما              │  🔵 🆘 پشتیبانی              │
└─────────────────────────────────────────────────────────────┘
Buy Menu (Duration Selection)
text
┌─────────────────────────────────────────────────────────────┐
│ 📅 1 ماه  │  📅 2 ماه  │  📅 3 ماه  │  📅 4 ماه          │
├─────────────────────────────────────────────────────────────┤
│ 💾 10GB - 82,000 تومان  │  💾 20GB - 151,000 تومان       │
├─────────────────────────────────────────────────────────────┤
│ 💾 30GB - 218,000 تومان  │  💾 50GB - 348,000 تومان       │
├─────────────────────────────────────────────────────────────┤
│ 💾 100GB - 641,000 تومان  │  💾 200GB - 1,272,000 تومان   │
├─────────────────────────────────────────────────────────────┤
│ 🔴 🔙 بازگشت به منو                                       │
└─────────────────────────────────────────────────────────────┘
Service Menu
text
┌─────────────────────────────────────────────────────────────┐
│ 🔴 🧪 دریافت اکانت تست  │  🔵 💰 کیف پول                │
├─────────────────────────────────────────────────────────────┤
│ 🔵 📖 راهنمای اتصال      │  🔴 🆘 پشتیبانی              │
├─────────────────────────────────────────────────────────────┤
│ 🔵 🔙 بازگشت به منو                                       │
└─────────────────────────────────────────────────────────────┘
Subscription Plans
Pricing Table (Toman)
Duration	10GB	20GB	30GB	50GB	100GB	200GB
1 Month	82,000	151,000	218,000	348,000	641,000	1,272,000
2 Months	151,000	278,000	401,000	640,000	1,179,000	2,340,000
3 Months	218,000	401,000	578,000	923,000	1,700,000	3,370,000
4 Months	282,000	519,000	748,000	1,195,000	2,200,000	4,360,000
Installation & Setup
Prerequisites
Python 3.10 or higher

pip (Python package manager)

Telegram Bot Token (from @BotFather)

Public URL for webhook (or ngrok for development)

Step-by-Step Installation
1. Clone the Repository
bash
git clone https://github.com/yourusername/telegram-bot.git
cd telegram-bot
2. Create Virtual Environment
bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
3. Install Dependencies
bash
pip install -r requirements.txt
4. Configure Environment
bash
cp .env.example .env
nano .env  # Edit with your values
5. Run the Application
bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
6. Set Webhook
bash
curl -X POST http://localhost:8000/set_webhook
Configuration
Environment Variables (.env)
env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook

# Database Configuration
DATABASE_URL=sqlite:///./telegram_bot.db

# Security
SECRET_KEY=your_secret_key_here

# Application Settings
DEBUG=False

# Server Settings (optional)
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
LOG_FILE=bot.log
Configuration Loading Flow
text
Application starts → load_dotenv() reads .env → Settings validates variables → Global config available
Running the Bot
Option 1: Direct Execution
bash
python main.py
Option 2: Using Uvicorn (Development)
bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Option 3: Using Uvicorn (Production)
bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Option 4: Using Docker
bash
docker-compose up -d
Deployment
Docker Deployment
1. Build the Image:

bash
docker-compose build
2. Run the Container:

bash
docker-compose up -d
3. View Logs:

bash
docker-compose logs -f
4. Stop the Container:

bash
docker-compose down
Manual Production Deployment
1. Set Production Environment:

bash
export DEBUG=False
export TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
2. Run with Gunicorn:

bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Deployment Checklist
□ Set DEBUG=False in production
□ Use HTTPS for webhook URL
□ Set up SSL certificate
□ Configure proper logging rotation
□ Set up monitoring and alerting
□ Implement rate limiting
□ Regular database backups
□ Security headers enabled
Logging
Log Levels
Level	Description
DEBUG	Detailed debugging information
INFO	General operational messages
WARNING	Warning messages
ERROR	Error messages
CRITICAL	Critical system errors
Log Locations
Console: Real-time logs with colors

File: bot.log with rotation (10MB max, 5 backups)

Log Format
text
2026-08-20 15:52:10 - telegram_bot - INFO - User started the bot: 123456 - johndoe
Viewing Logs
bash
# View real-time logs
tail -f bot.log

# View last 100 lines
tail -n 100 bot.log

# Search for errors
grep "ERROR" bot.log
API Endpoints
Endpoint	Method	Description
/	GET	Welcome message
/health	GET	Health check
/webhook	POST	Telegram updates
/set_webhook	POST	Set webhook
/delete_webhook	POST	Delete webhook
/docs	GET	Swagger UI
/redoc	GET	ReDoc UI
Troubleshooting
Common Issues and Solutions
1. Bot Not Responding

bash
# Check if webhook is set correctly
curl http://localhost:8000/health

# Verify webhook URL is accessible
curl https://your-domain.com/webhook

# Check logs for errors
tail -f bot.log
2. Colored Buttons Not Showing

bash
# Update python-telegram-bot
pip install --upgrade python-telegram-bot

# Ensure users have Telegram v9.4+
3. Webhook Errors

bash
# Re-set webhook
curl -X POST http://localhost:8000/delete_webhook
curl -X POST http://localhost:8000/set_webhook

# Check if port 8000 is open
netstat -tulpn | grep 8000
4. Import Errors

bash
# Verify all files exist
tree

# Reinstall dependencies
pip install --upgrade -r requirements.txt
5. Database Errors

bash
# Check file permissions
chmod 644 telegram_bot.db

# Verify DATABASE_URL in .env
echo $DATABASE_URL
6. Callback Query Expired

The bot automatically handles expired queries

Users should click buttons again if they get a timeout error

Security Best Practices
Implemented Security
Environment Variables: All sensitive data in .env

Input Validation: All user inputs validated

Error Handling: No sensitive data in error messages

HTTPS: Required for production webhook

Logging: No sensitive data logged

Secret Key: Used for encryption/signing

Recommendations
Regular Updates: Keep dependencies updated

Token Rotation: Regularly rotate bot tokens

Access Control: Implement user permissions

Audit Logging: Track important operations

Backup: Regular data backups

Monitoring: Set up alerts for suspicious activity

SSL: Use valid SSL certificates

Contributing
Fork the repository

Create a feature branch (git checkout -b feature/AmazingFeature)

Commit your changes (git commit -m 'Add some AmazingFeature')

Push to the branch (git push origin feature/AmazingFeature)

Open a Pull Request

Code Style
Follow PEP 8 guidelines

Add docstrings for all functions

Write comprehensive comments

Update documentation for new features

Support
📧 Email: support@example.com

💬 Telegram: @SupportBot

🌐 Website: example.com/support

⏰ Hours: 9:00 AM - 12:00 AM

License
This project is licensed under the MIT License - see the LICENSE file for details.

Acknowledgments
python-telegram-bot - Telegram Bot API wrapper

FastAPI - Modern web framework

Telegram Bot API - Official Telegram Bot API

Pydantic - Data validation

Version History
Version	Date	Changes
1.0.0	August 2026	Initial release with complete features
Made with ❤️ for the Telegram community
