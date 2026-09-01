Modular Architecture Documentation
Complete Project Structure with Descriptions
text
telegram_bot/
│
├── api/                                    # Presentation Layer - Handles all API-related functionality
│   ├── handlers/                           # Business Logic Handlers
│   │   ├── keyboard_builder.py             # Keyboard Builder - Builds inline keyboards with colored buttons using Telegram Bot API v9.4+
│   │   ├── message_handler.py              # Message Handler - Processes all incoming Telegram messages, commands, and callback queries
│   │   └── __pycache__/                    # Python Cache - Stores compiled Python bytecode
│   └── routes/                             # API Routes
│       ├── webhook.py                      # Webhook Route - Handles Telegram webhook updates and provides health checks
│       └── __pycache__/                    # Python Cache - Stores compiled Python bytecode
│
├── core/                                   # Core Infrastructure - Essential system components
│   ├── config.py                           # Configuration Manager - Manages environment variables with Pydantic validation
│   ├── exceptions.py                       # Custom Exceptions - Defines application-specific exception classes
│   ├── logging.py                          # Logging Configuration - Configures comprehensive logging with rotating files
│   └── __pycache__/                        # Python Cache - Stores compiled Python bytecode
│
├── models/                                 # Data Models Layer - Defines all data structures
│   ├── user.py                             # User Model - Defines User and UserStatus data models
│   ├── subscription.py                     # Subscription Model - Defines Subscription, SubscriptionType, and SubscriptionStatus
│   └── __pycache__/                        # Python Cache - Stores compiled Python bytecode
│
├── services/                               # Business Logic Layer - All service implementations
│   ├── __init__.py                         # Service Initializer - Initializes the services package
│   ├── user_service.py                     # User Service - Handles user registration, status tracking, and subordinate management
│   ├── subscription_service.py             # Subscription Service - Manages subscription creation, renewal, and cancellation
│   └── __pycache__/                        # Python Cache - Stores compiled Python bytecode
│
├── utils/                                  # Utility Functions - Helper functions and reusable utilities
│   └── validators.py                       # Validators - Input validation and data sanitization
│
├── main.py                                 # Application Entry Point - Initializes FastAPI application
├── bot.log                                 # Application Log File - Stores logs for debugging
├── README.md                               # Documentation - Project documentation with setup instructions
├── requirements.txt                        # Dependencies - Lists all Python package dependencies
├── Dockerfile                              # Docker Configuration - Defines Docker image build instructions
├── docker-compose.yml                      # Docker Compose - Defines multi-container Docker application
├── .env                                    # Environment Variables - Stores sensitive configuration data
└── __pycache__/                            # Python Cache - Stores compiled Python bytecode
Layer Descriptions
Layer	Directory	Purpose	Key Files
Presentation Layer	api/	Handles HTTP requests, webhooks, and response formatting	webhook.py
Handler Layer	api/handlers/	Processes messages, builds keyboards, and routes callbacks	message_handler.py, keyboard_builder.py
Service Layer	services/	Implements business logic and data operations	user_service.py, subscription_service.py
Model Layer	models/	Defines data structures and validation rules	user.py, subscription.py
Core Layer	core/	Provides configuration, logging, and exception handling	config.py, logging.py, exceptions.py
Utility Layer	utils/	Provides helper functions and utilities	validators.py
Key Components Description
text
services/
├── user_service.py                         # User Service - Handles user registration, authentication, profile management
│                                           # Methods: register_user(), get_user_status(), get_subordinates()
│                                           # Dependencies: models/user.py, core/config.py, core/logging.py
│
└── subscription_service.py                 # Subscription Service - Manages subscription lifecycle and billing
                                            # Methods: create_subscription(), renew_subscription(), cancel_subscription()
                                            # Dependencies: models/subscription.py, models/user.py, core/logging.py
Dependencies Flow Diagram
text
┌──────────────────────────────────────────────────────────────┐
│                        main.py                               │
│              (Application Entry Point)                       │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                    api/routes/webhook.py                     │
│              (Webhook Endpoints)                             │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                api/handlers/message_handler.py               │
│              (Message & Callback Processing)                 │
└──────────┬─────────────────────────┬────────────────────────┘
           │                         │
┌──────────▼──────────┐   ┌──────────▼────────────────────────┐
│  keyboard_builder.py │   │      services/user_service.py     │
│   (UI Builder)       │   │      (User Management)            │
└──────────────────────┘   └──────────┬────────────────────────┘
                                      │
                           ┌──────────▼────────────────────────┐
                           │  services/subscription_service.py │
                           │     (Subscription Management)     │
                           └──────────┬────────────────────────┘
                                      │
                           ┌──────────▼────────────────────────┐
                           │        models/user.py             │
                           │      (User Data Models)           │
                           └───────────────────────────────────┘
Module Independence Matrix
Module	Independent	Modifiable Without Affecting Others	Dependencies
keyboard_builder.py	✅ Yes	✅ Yes	None
message_handler.py	✅ Yes	✅ Yes	Services Layer
user_service.py	✅ Yes	✅ Yes	Models, Core
subscription_service.py	✅ Yes	✅ Yes	Models, Core
user.py	✅ Yes	✅ Yes	Core
subscription.py	✅ Yes	✅ Yes	Core
config.py	✅ Yes	✅ Yes	None
logging.py	✅ Yes	✅ Yes	None
exceptions.py	✅ Yes	✅ Yes	None
webhook.py	✅ Yes	✅ Yes	Handlers
File Responsibilities
File	Responsibility	Methods/Functions
user_service.py	User management operations	register_user(), get_user_status(), get_subordinates(), add_subordinate()
subscription_service.py	Subscription lifecycle management	create_subscription(), renew_subscription(), cancel_subscription(), check_subscription_status()
keyboard_builder.py	UI keyboard construction	create_main_menu(), create_buy_menu(), create_plan_selection_menu(), create_service_menu()
message_handler.py	Message and callback processing	handle_start(), handle_callback_query(), handle_status(), handle_buy_service()
webhook.py	HTTP endpoint handling	webhook(), set_webhook(), delete_webhook(), health_check()
config.py	Configuration management	validate_settings(), Settings class
logging.py	Logging setup	setup_logging(), logger instance
exceptions.py	Error definitions	Custom exception classes
user.py	User data models	User, UserStatus classes
subscription.py	Subscription data models	Subscription, SubscriptionType, SubscriptionStatus classes
Benefits of This Architecture
Benefit	Description
Separation of Concerns	Each layer has a single, well-defined responsibility
Loose Coupling	Components interact through clear interfaces, not implementation details
High Cohesion	Related functionality is grouped together in the same module
Single Responsibility	Each class/file does one thing and does it well
Maintainability	Easy to modify, debug, and extend individual components
Testability	Each module can be tested independently in isolation
Scalability	New features can be added without affecting existing code
Reusability	Services and utilities can be reused across different parts of the application
