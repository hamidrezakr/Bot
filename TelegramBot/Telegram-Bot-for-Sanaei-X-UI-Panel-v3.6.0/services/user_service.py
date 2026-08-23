"""
User service module for managing Telegram users.
"""

import logging
from typing import Optional, List
from datetime import datetime

from core.logging import logger
from models.user import User, UserStatus  # این باید کار کند
from core.exceptions import UserNotFoundError


class UserService:
    """
    Service for managing user operations.
    """
    
    def __init__(self):
        """Initialize user service."""
        # In production, this would use a database
        self._users = {}
        self._subordinates = {}
    
    async def register_user(
        self,
        user_id: int,
        username: Optional[str],
        first_name: str,
        last_name: Optional[str] = None
    ) -> User:
        """
        Register or update a user in the system.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            last_name: User's last name (optional)
        
        Returns:
            User: Registered user object
        """
        try:
            if user_id in self._users:
                # Update existing user
                user = self._users[user_id]
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.last_seen = datetime.now()
                logger.info(f"User updated: {user_id}")
            else:
                # Create new user
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    created_at=datetime.now(),
                    last_seen=datetime.now(),
                    is_active=True
                )
                self._users[user_id] = user
                logger.info(f"User registered: {user_id}")
            
            return user
            
        except Exception as e:
            logger.error(f"Error registering user {user_id}: {str(e)}")
            raise
    
    async def get_user_status(self, user_id: int) -> UserStatus:
        """
        Get the status of a user.
        
        Args:
            user_id: User ID to get status for
        
        Returns:
            UserStatus: User status information
        
        Raises:
            UserNotFoundError: If user is not found
        """
        try:
            user = self._users.get(user_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")
            
            # Get subscription status
            subscription = await self._get_user_subscription(user_id)
            
            status_text = "فعال" if user.is_active else "غیرفعال"
            
            return UserStatus(
                user_id=user.user_id,
                username=user.username,
                status=status_text,
                subscription_expiry=subscription.get("end_date") if subscription else None,
                subscription_type=subscription.get("type") if subscription else None,
                remaining_days=subscription.get("remaining_days") if subscription else None
            )
            
        except Exception as e:
            logger.error(f"Error getting user status for {user_id}: {str(e)}")
            raise
    
    async def get_subordinates(self, user_id: int) -> List[User]:
        """
        Get list of subordinates for a user.
        
        Args:
            user_id: User ID to get subordinates for
        
        Returns:
            List[User]: List of subordinate users
        """
        try:
            subordinates = self._subordinates.get(user_id, [])
            users = [self._users[sub_id] for sub_id in subordinates if sub_id in self._users]
            logger.info(f"Found {len(users)} subordinates for user {user_id}")
            return users
            
        except Exception as e:
            logger.error(f"Error getting subordinates for {user_id}: {str(e)}")
            return []
    
    async def _get_user_subscription(self, user_id: int) -> Optional[dict]:
        """
        Get user's subscription information.
        
        Args:
            user_id: User ID
        
        Returns:
            Optional[dict]: Subscription information or None
        """
        # Mock subscription data
        # In production, this would query the database
        if user_id in self._users:
            return {
                "type": "premium",
                "end_date": datetime.now().replace(year=datetime.now().year + 1),
                "remaining_days": 365
            }
        return None
    
    async def add_subordinate(self, user_id: int, subordinate_id: int) -> bool:
        """
        Add a subordinate to a user.
        
        Args:
            user_id: Parent user ID
            subordinate_id: Subordinate user ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if user_id not in self._subordinates:
                self._subordinates[user_id] = []
            
            if subordinate_id not in self._subordinates[user_id]:
                self._subordinates[user_id].append(subordinate_id)
                logger.info(f"Subordinate {subordinate_id} added to user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error adding subordinate: {str(e)}")
            return False
