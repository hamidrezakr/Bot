"""
Subscription service module for managing user subscriptions.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from core.logging import logger
from models.subscription import Subscription, SubscriptionType, SubscriptionStatus
from core.exceptions import SubscriptionError


class SubscriptionService:
    """
    Service for managing subscription operations.
    """
    
    def __init__(self):
        """Initialize subscription service."""
        # In production, this would use a database
        self._subscriptions: Dict[str, Subscription] = {}
        self._user_subscriptions: Dict[int, List[str]] = {}
    
    async def create_subscription(
        self,
        user_id: int,
        service_type: SubscriptionType,
        duration_days: int = 30,
        is_test: bool = False
    ) -> Subscription:
        """
        Create a new subscription for a user.
        
        Args:
            user_id: User ID
            service_type: Type of service (basic, premium, business)
            duration_days: Duration in days
            is_test: Whether this is a test subscription
        
        Returns:
            Subscription: Created subscription object
        
        Raises:
            SubscriptionError: If subscription creation fails
        """
        try:
            subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
            
            subscription = Subscription(
                subscription_id=subscription_id,
                user_id=user_id,
                service_type=service_type,
                status=SubscriptionStatus.ACTIVE,
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=duration_days),
                is_test=is_test
            )
            
            self._subscriptions[subscription_id] = subscription
            
            # Add to user's subscriptions list
            if user_id not in self._user_subscriptions:
                self._user_subscriptions[user_id] = []
            self._user_subscriptions[user_id].append(subscription_id)
            
            logger.info(f"Subscription created: {subscription_id} for user {user_id}")
            return subscription
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            raise SubscriptionError(f"Failed to create subscription: {str(e)}")
    
    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """
        Get a subscription by ID.
        
        Args:
            subscription_id: Subscription ID
        
        Returns:
            Optional[Subscription]: Subscription object or None
        """
        return self._subscriptions.get(subscription_id)
    
    async def get_user_subscriptions(self, user_id: int) -> List[Subscription]:
        """
        Get all subscriptions for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            List[Subscription]: List of user's subscriptions
        """
        subscription_ids = self._user_subscriptions.get(user_id, [])
        subscriptions = []
        
        for sub_id in subscription_ids:
            sub = self._subscriptions.get(sub_id)
            if sub:
                subscriptions.append(sub)
        
        return subscriptions
    
    async def get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """
        Get the active subscription for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Optional[Subscription]: Active subscription or None
        """
        subscriptions = await self.get_user_subscriptions(user_id)
        
        for sub in subscriptions:
            if sub.status == SubscriptionStatus.ACTIVE and sub.end_date > datetime.now():
                return sub
        
        return None
    
    async def renew_subscription(
        self,
        subscription_id: str,
        duration_days: int = 30
    ) -> Subscription:
        """
        Renew an existing subscription.
        
        Args:
            subscription_id: Subscription ID
            duration_days: Additional days to extend
        
        Returns:
            Subscription: Renewed subscription
        
        Raises:
            SubscriptionError: If subscription not found
        """
        subscription = self._subscriptions.get(subscription_id)
        
        if not subscription:
            raise SubscriptionError(f"Subscription {subscription_id} not found")
        
        # Extend end date
        subscription.end_date = subscription.end_date + timedelta(days=duration_days)
        subscription.status = SubscriptionStatus.ACTIVE
        
        logger.info(f"Subscription renewed: {subscription_id} for user {subscription.user_id}")
        return subscription
    
    async def cancel_subscription(self, subscription_id: str) -> bool:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Subscription ID
        
        Returns:
            bool: True if cancelled successfully
        
        Raises:
            SubscriptionError: If subscription not found
        """
        subscription = self._subscriptions.get(subscription_id)
        
        if not subscription:
            raise SubscriptionError(f"Subscription {subscription_id} not found")
        
        subscription.status = SubscriptionStatus.CANCELLED
        logger.info(f"Subscription cancelled: {subscription_id}")
        return True
    
    async def check_subscription_status(self, user_id: int) -> Dict[str, any]:
        """
        Check the status of a user's subscription.
        
        Args:
            user_id: User ID
        
        Returns:
            Dict: Subscription status information
        """
        active_sub = await self.get_active_subscription(user_id)
        
        if active_sub:
            remaining_days = (active_sub.end_date - datetime.now()).days
            return {
                "has_subscription": True,
                "is_active": True,
                "type": active_sub.service_type.value,
                "expires_at": active_sub.end_date,
                "remaining_days": max(0, remaining_days),
                "is_test": active_sub.is_test
            }
        else:
            return {
                "has_subscription": False,
                "is_active": False,
                "type": None,
                "expires_at": None,
                "remaining_days": 0,
                "is_test": False
            }
    
    async def create_test_subscription(self, user_id: int) -> Subscription:
        """
        Create a 24-hour test subscription.
        
        Args:
            user_id: User ID
        
        Returns:
            Subscription: Test subscription
        """
        logger.info(f"Creating test subscription for user {user_id}")
        return await self.create_subscription(
            user_id=user_id,
            service_type=SubscriptionType.TEST,
            duration_days=1,  # 1 day
            is_test=True
        )
