# <<< CHANGE START >>>
# Added more specific error types inheriting from DatabaseError and APIError
# <<< CHANGE END >>>
"""
Custom exception classes for the Discord betting bot.
Provides specific error types for different failure scenarios.
"""
import discord
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BettingBotError(Exception):
    """Base exception class for all betting bot errors."""
    def __init__(self, message: str = "An error occurred in the betting bot", user_message: Optional[str] = None):
        self.message = message
        # <<< CHANGE START >>>
        # Default user message changed for the base error
        self.user_message = user_message or "An unexpected error occurred. Please contact support if this persists."
        # <<< CHANGE END >>>
        super().__init__(self.message)
        # <<< CHANGE START >>>
        # Log the specific subclass name as well for better tracking
        logger.error(f"{self.__class__.__name__}: {self.message}")
        # <<< CHANGE END >>>

class ValidationError(BettingBotError):
    """Raised when input validation fails."""
    def __init__(self, message: str = "Invalid input provided", user_message: Optional[str] = None):
        super().__init__(message, user_message or "Invalid input. Please check your entries and try again.")

# <<< CHANGE START >>>
class DatabaseError(BettingBotError):
    """Base class for database-related errors."""
    def __init__(self, message: str = "Database operation failed", user_message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.original_exception = original_exception
        super().__init__(message, user_message or "A database error occurred. Please try again later or contact support.")

class DatabaseConnectionError(DatabaseError):
    """Raised when unable to connect to the database."""
    def __init__(self, message: str = "Failed to connect to the database", user_message: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__(message, user_message or "Could not connect to the database. Please contact support.", original_exception)

class DatabaseQueryError(DatabaseError):
    """Raised when a specific database query fails."""
    def __init__(self, message: str = "Database query failed", query: Optional[str] = None, user_message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.query = query
        full_message = f"{message}{f' | Query: {query}' if query else ''}"
        super().__init__(full_message, user_message or "A database error occurred while processing your request. Please try again.", original_exception)

class APIError(BettingBotError):
    """Base class for API-related errors."""
    def __init__(self, message: str = "API request failed", user_message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.original_exception = original_exception
        super().__init__(message, user_message or "An error occurred while communicating with the sports API. Please try again later.")

class APIConnectionError(APIError):
    """Raised when unable to connect to the API."""
    def __init__(self, message: str = "Failed to connect to the API", url: Optional[str] = None, user_message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.url = url
        full_message = f"{message}{f' | URL: {url}' if url else ''}"
        super().__init__(full_message, user_message or "Could not connect to the sports API. Please check status or try again later.", original_exception)

class APITimeoutError(APIError):
    """Raised when an API request times out."""
    def __init__(self, message: str = "API request timed out", url: Optional[str] = None, user_message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.url = url
        full_message = f"{message}{f' | URL: {url}' if url else ''}"
        super().__init__(full_message, user_message or "The request to the sports API timed out. Please try again.", original_exception)

class APIResponseError(APIError):
    """Raised when the API returns an unexpected or error status."""
    def __init__(self, message: str = "Invalid API response", status_code: Optional[int] = None, url: Optional[str] = None, user_message: Optional[str] = None, original_exception: Optional[Exception] = None):
        self.status_code = status_code
        self.url = url
        full_message = f"{message}{f' | Status: {status_code}' if status_code else ''}{f' | URL: {url}' if url else ''}"
        super().__init__(full_message, user_message or "Received an unexpected response from the sports API. Please try again later.", original_exception)
# <<< CHANGE END >>>

class PermissionError(BettingBotError):
    """Raised when the bot lacks required permissions."""
    def __init__(self, message: str = "Permission denied", user_message: Optional[str] = None):
        super().__init__(message, user_message or "I don’t have the necessary permissions to perform this action.")

class AuthenticationError(BettingBotError):
    """Raised when web authentication fails."""
    def __init__(self, message: str = "Authentication failed", user_message: Optional[str] = None):
        super().__init__(message, user_message or "Invalid or missing authentication token.")