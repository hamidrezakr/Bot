"""
Keyboard builder module for creating Telegram inline keyboards with colored buttons.
Uses standard InlineKeyboardButton and InlineKeyboardMarkup from python-telegram-bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional


class KeyboardBuilder:
    """
    Builds inline keyboards with colored buttons for Telegram.
    Note: Colored buttons (style parameter) are supported in Telegram Bot API v9.4+
    but python-telegram-bot may not fully support it yet.
    The colors will appear automatically in newer Telegram clients.
    """
    
    @staticmethod
    def create_colored_button(
        text: str,
        callback_data: str
    ) -> InlineKeyboardButton:
        """
        Create an inline keyboard button.
        
        Args:
            text: Button text
            callback_data: Callback data for the button
        
        Returns:
            InlineKeyboardButton: Configured button
        """
        return InlineKeyboardButton(
            text=text,
            callback_data=callback_data
        )
    
    @staticmethod
    def create_main_menu() -> InlineKeyboardMarkup:
        """
        Create the main menu with buttons in 4 rows.
        
        Returns:
            InlineKeyboardMarkup: Main menu keyboard
        """
        keyboard = [
            # Row 1: Status
            [
                InlineKeyboardButton(
                    "📊 وضعیت من",
                    callback_data="status",
                    style="primary"
                )
            ],
            # Row 2: Buy and Renew
            [
                InlineKeyboardButton(
                    "🛒 خرید سرویس جدید",
                    callback_data="buy_service",
                    style="success"
                ),
                InlineKeyboardButton(
                    "🔄 تمدید سرویس",
                    callback_data="renew_service",
                    style="success"
                )
            ],
            # Row 3: Test Account and Subordinates
            [
                InlineKeyboardButton(
                    "🧪 اکانت تست",
                    callback_data="test_account",
                    style="danger"
                ),
                InlineKeyboardButton(
                    "👥 زیر مجموعه ها",
                    callback_data="subordinates",
                    style="danger"
                )
            ],
            # Row 4: Help and Support
            [
                InlineKeyboardButton(
                    "❓ راهنما",
                    callback_data="help"
                ),
                InlineKeyboardButton(
                    "🆘 پشتیبانی",
                    callback_data="support"
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_buy_menu() -> InlineKeyboardMarkup:
        """
        Create the buy service menu with duration and plan selection.
        
        Returns:
            InlineKeyboardMarkup: Buy menu keyboard
        """
        keyboard = [
            # Row 1: Duration selection
            [
                InlineKeyboardButton("📅 1 ماه", callback_data="duration_1"),
                InlineKeyboardButton("📅 2 ماه", callback_data="duration_2"),
                InlineKeyboardButton("📅 3 ماه", callback_data="duration_3"),
                InlineKeyboardButton("📅 4 ماه", callback_data="duration_4")
            ],
            # Row 2: Plans with prices
            [
                InlineKeyboardButton(
                    "💾 10GB - 82,000 تومان",
                    callback_data="plan_1m_10gb",
                    style="primary"
                ),
                InlineKeyboardButton(
                    "💾 20GB - 151,000 تومان",
                    callback_data="plan_1m_20gb",
                    style="primary"
                )
            ],
            [
                InlineKeyboardButton(
                    "💾 30GB - 218,000 تومان",
                    callback_data="plan_1m_30gb",
                    style="primary"
                ),
                InlineKeyboardButton(
                    "💾 50GB - 348,000 تومان",
                    callback_data="plan_1m_50gb",
                    style="primary"
                )
            ],
            [
                InlineKeyboardButton(
                    "💾 100GB - 641,000 تومان",
                    callback_data="plan_1m_100gb",
                    style="primary"
                ),
                InlineKeyboardButton(
                    "💾 200GB - 1,272,000 تومان",
                    callback_data="plan_1m_200gb",
                    style="primary"
                )
            ],
            # Row 8: Back button
            [
                InlineKeyboardButton(
                    "🔙 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_plan_selection_menu(duration_months: int = 1) -> InlineKeyboardMarkup:
        """
        Create a plan selection menu for a specific duration.
        
        Args:
            duration_months: Number of months (1, 2, 3, 4)
        
        Returns:
            InlineKeyboardMarkup: Plan selection keyboard
        """
        # Prices for different durations
        prices = {
            1: {"10": 82000, "20": 151000, "30": 218000, "50": 348000, "100": 641000, "200": 1272000},
            2: {"10": 151000, "20": 278000, "30": 401000, "50": 640000, "100": 1179000, "200": 2340000},
            3: {"10": 218000, "20": 401000, "30": 578000, "50": 923000, "100": 1700000, "200": 3370000},
            4: {"10": 282000, "20": 519000, "30": 748000, "50": 1195000, "100": 2200000, "200": 4360000}
        }
        
        duration_prices = prices.get(duration_months, prices[1])
        
        keyboard = [
            # Header
            [
                InlineKeyboardButton(
                    f"📅 انتخاب پلن - {duration_months} ماهه",
                    callback_data="noop"
                )
            ],
        ]
        
        # Add plan buttons (2 per row)
        plan_buttons = []
        for gb, price in duration_prices.items():
            plan_buttons.append(
                InlineKeyboardButton(
                    f"💾 {gb}GB - {price:,} تومان",
                    callback_data=f"plan_{duration_months}m_{gb}gb"
                )
            )
        
        # Group into rows of 2
        for i in range(0, len(plan_buttons), 2):
            row = plan_buttons[i:i+2]
            keyboard.append(row)
        
        # Back and Change buttons
        keyboard.append([
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="back_to_durations",
                style="danger"
            ),
            InlineKeyboardButton(
                "🔄 تغییر مدت",
                callback_data="change_duration"
            )
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_service_menu() -> InlineKeyboardMarkup:
        """
        Create the service menu with Test Account, Wallet, Guide, Support.
        
        Returns:
            InlineKeyboardMarkup: Service menu keyboard
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    "🧪 دریافت اکانت تست",
                    callback_data="get_test_account"
                ),
                InlineKeyboardButton(
                    "💰 کیف پول",
                    callback_data="wallet"
                )
            ],
            [
                InlineKeyboardButton(
                    "📖 راهنمای اتصال",
                    callback_data="connection_guide"
                ),
                InlineKeyboardButton(
                    "🆘 پشتیبانی",
                    callback_data="support"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_sub_menu() -> InlineKeyboardMarkup:
        """
        Create a sub-menu with back button.
        
        Returns:
            InlineKeyboardMarkup: Sub-menu keyboard
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔙 بازگشت به منو",
                    callback_data="main_menu"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
