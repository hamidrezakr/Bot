"""
Custom exceptions for the application.
"""

class TelegramBotError(Exception):
    """Base exception for Telegram bot errors."""
    pass


class ConfigurationError(TelegramBotError):
    """Raised when configuration is invalid."""
    pass


class UserNotFoundError(TelegramBotError):
    """Raised when a user is not found."""
    pass


class SubscriptionError(TelegramBotError):
    """Raised when subscription operations fail."""
    pass


class ServiceError(TelegramBotError):
    """Raised when service operations fail."""
    pass

# ==============================================
# Panel Related Exceptions 
# ==============================================

class PanelError(TelegramBotError):
    """
    Raised when panel operations fail.
    Used for: panel creation, update, deletion, health checks, API calls.
    """
    pass


class PanelNotFoundError(PanelError):
    """Raised when a panel is not found in the database."""
    pass


class PanelConnectionError(PanelError):
    """Raised when connection to panel API fails."""
    pass


class PanelAuthenticationError(PanelError):
    """Raised when panel API authentication fails."""
    pass


class PanelValidationError(PanelError):
    """Raised when panel data validation fails."""
    pass


class InboundNotFoundError(PanelError):
    """Raised when an inbound is not found on the panel."""
    pass


# ==============================================
# Service Related Exceptions
# ==============================================

class ServiceNotFoundError(ServiceError):
    """Raised when a service is not found."""
    pass


class ServiceValidationError(ServiceError):
    """Raised when service data validation fails."""
    pass


# ==============================================
# Category Related Exceptions
# ==============================================

class CategoryNotFoundError(TelegramBotError):
    """Raised when a category is not found."""
    pass


class CategoryValidationError(TelegramBotError):
    """Raised when category data validation fails."""
    pass




class ServiceNotFoundError(TelegramBotError):
    """Raised when a service is not found."""
    pass


class CategoryNotFoundError(TelegramBotError):
    """Raised when a category is not found."""
    pass


class PanelFullError(TelegramBotError):
    """Raised when a panel is full."""
    pass
