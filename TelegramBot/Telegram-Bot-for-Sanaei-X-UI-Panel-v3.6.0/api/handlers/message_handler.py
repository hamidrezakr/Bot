"""
Message handler module for processing Telegram messages.
"""

import logging
import httpx
from datetime import datetime  # ← اضافه شد
from typing import Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import BadRequest
import asyncio
from core.config import settings
from core.logging import logger
from api.handlers.keyboard_builder import KeyboardBuilder
from services.user_service import UserService
from services.subscription_service import SubscriptionService


class MessageHandler:
    """
    Handles incoming Telegram messages and commands.
    """

    def __init__(self):
        """Initialize message handler with services."""
        self.user_service = UserService()
        self.subscription_service = SubscriptionService()
        self.keyboard_builder = KeyboardBuilder()
        self._pending_purchases = {}
        self._pending_receipts = {}
        self._status_checking_users = set()
        self._status_attempts = {}
        self._renewing_users = set()
        self._renew_attempts = {}
        self._discount_state = {}

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command."""
        try:
            user = update.effective_user
            logger.info(f"User started the bot: {user.id} - {user.username}")
            
            await self.user_service.register_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
           # ====== Register user in database for broadcast ======
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{settings.API_BASE_URL}/admin/api/users/register",
                        json={
                            "user_id": user.id,
                            "username": user.username,
                            "first_name": user.first_name,
                            "last_name": user.last_name
                        }
                    )
                    logger.info(f"User registered in DB: {user.id}")
            except Exception as e:
                logger.error(f"Error registering user in DB: {str(e)}") 
            # ====== Check channel membership ======
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/check-membership/{user.id}"
                )
                membership_data = response.json()
            
            if membership_data.get("status") == "success":
                data = membership_data.get("data", {})
                is_member = data.get("is_member", True)
                channel_settings = data.get("channel_settings")
                
                if not is_member and channel_settings:
                    # کاربر عضو نیست - باید عضو بشه
                    channel_url = channel_settings.get("channel_url", "")
                    channel_username = channel_settings.get("channel_username", "")
                    
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                text="📢 عضویت در کانال",
                                url=channel_url if channel_url else f"https://t.me/{channel_username}"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="✅ عضو شدم",
                                callback_data="check_membership"
                            )
                        ]
                    ]
                    
                    await update.message.reply_text(
                        f"👋 سلام {user.first_name} عزیز!\n\n"
                        f"⚠️ **برای استفاده از ربات، ابتدا باید در کانال ما عضو شوید.**\n\n"
                        f"📢 روی دکمه زیر کلیک کنید و عضو کانال شوید.\n"
                        f"سپس روی '✅ عضو شدم' بزنید.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
            
            # ====== Check for referral code ======
            referral_message = None
            
            if context.args and len(context.args) > 0:
                arg = context.args[0]
                if arg.startswith("ref_"):
                    try:
                        referrer_id = int(arg.replace("ref_", ""))
                        logger.info(f"🔗 Referral code detected: {referrer_id}")
                        
                        # Register referral
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            response = await client.post(
                                f"{settings.API_BASE_URL}/admin/api/referrals/register",
                                json={
                                    "referrer_id": referrer_id,
                                    "referred_id": user.id
                                }
                            )
                            result = response.json()
                            
                            if result.get("status") == "success":
                                logger.info(f"✅ Referral registered: {referrer_id} -> {user.id}")
                                referral_message = (
                                    f"🎁 **کد معرف شما ثبت شد!**\n"
                                    f"شما 10% تخفیف برای اولین خرید خود دریافت می‌کنید.\n\n"
                                )
                            else:
                                logger.warning(f"❌ Referral registration failed: {result.get('message')}")
                                referral_message = (
                                    f"⚠️ **هر کاربر فقط یک بار می‌تواند از کد رفرال استفاده کند.**\n"
                                    f"شما قبلاً از کد رفرال استفاده کرده‌اید.\n\n"
                                    f"💡 **اما می‌توانید با زیرمجموعه‌گیری از تخفیف‌های بیشتری بهره‌مند شوید!**\n"
                                    f"از دکمه 'زیرمجموعه‌ها' در منوی اصلی لینک دعوت خود را دریافت کنید.\n\n"
                                )
                    except Exception as e:
                        logger.error(f"Error processing referral code: {str(e)}")
            
            # ====== ساخت پیام خوش‌آمد ======
                        # ====== ✅ Get welcome message from settings ======
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.API_BASE_URL}/admin/api/settings/messages")
                msg_settings = response.json().get("data", {})
            
            welcome_template = msg_settings.get("welcome_message", 
                "👋 سلام {first_name} عزیز!\nبه ربات مدیریت سرویس‌ها خوش آمدید.\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:")
            
            if referral_message:
                welcome_text = welcome_template.replace("{first_name}", user.first_name or "کاربر")
                welcome_text += f"\n\n{referral_message}"
            else:
                welcome_text = welcome_template.replace("{first_name}", user.first_name or "کاربر")


            await update.message.reply_text(
                text=welcome_text,
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            logger.info(f"Main menu sent to user: {user.id}")
            
        except Exception as e:
            logger.error(f"Error in handle_start: {str(e)}")
            await update.message.reply_text("❌ متأسفانه خطایی رخ داد. لطفاً مجدداً تلاش کنید.")
            
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo messages - receive receipt images."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"
        logger.info(f"📸 Photo received from user {user_id}")

        if not hasattr(self, '_pending_receipts') or user_id not in self._pending_receipts:
            await update.message.reply_text(
                "❌ شما درخواست ارسال رسید نداشته‌اید.\n"
                "لطفاً ابتدا یک سرویس را انتخاب کرده و روی دکمه 'ارسال رسید پرداخت' کلیک کنید."
            )
            return

        pending_data = self._pending_receipts[user_id]
        service_id = pending_data.get('service_id')
        is_renewal = pending_data.get('is_renewal', False)
        user_info = pending_data.get('user_info')

        service_data = {}
        if is_renewal:
            if hasattr(self, '_renew_pending_purchases') and user_id in self._renew_pending_purchases:
                renewal_data = self._renew_pending_purchases[user_id]
                service_data = {
                    "service_name": renewal_data.get('service_name', ''),
                    "service_details": renewal_data.get('service_details', {})
                }
        else:
            if hasattr(self, '_pending_purchases') and user_id in self._pending_purchases:
                service_data = self._pending_purchases.get(user_id, {})

        if not service_data:
            await update.message.reply_text(
                "❌ اطلاعات سرویس یافت نشد.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            if user_id in self._pending_receipts:
                del self._pending_receipts[user_id]
            return

        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            import os
            filename = f"receipt_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_path = f"data/receipts/{filename}"
            os.makedirs("data/receipts", exist_ok=True)
            await file.download_to_drive(file_path)

            user_info_serializable = None
            if is_renewal and user_info:
                client = user_info.get('client', {})
                user_info_serializable = {
                    "email": user_info.get('email'),
                    "panel": user_info.get('panel', {}),
                    "client": {
                        "email": client.get('email'),
                        "totalGB": client.get('totalGB', 0),
                        "usedGB": client.get('usedGB', 0),
                        "enable": client.get('enable', False),
                        "expiryTime": client.get('expiryTime', 0),
                        "limitIp": client.get('limitIp', 0),
                        "subId": client.get('subId', ''),
                        "tgId": client.get('tgId', 0)
                    }
                }

            receipt_data = {
                "user_id": user_id,
                "username": username,
                "service_id": service_id,
                "service_name": service_data.get("service_name", ""),
                "service_details": service_data.get("service_details", {}),
                "image_path": file_path,
                "image_filename": filename,
                "status": "pending",
                "is_renewal": is_renewal
            }

            if is_renewal and user_info_serializable:
                receipt_data["renew_user_info"] = user_info_serializable

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.API_BASE_URL}/admin/api/receipts",
                    json=receipt_data
                )
                if response.status_code != 200:
                    raise Exception(f"API returned {response.status_code}")

            if user_id in self._pending_receipts:
                del self._pending_receipts[user_id]

            renewal_text = "تمدید" if is_renewal else "خرید"
            await update.message.reply_text(
                f"✅ **رسید شما با موفقیت ثبت شد!**\n\n"
                f"رسید {renewal_text} شما در حال بررسی است.",
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_main_menu()
            )

        except Exception as e:
            logger.error(f"❌ Error handling receipt: {str(e)}")
            await update.message.reply_text(
                "❌ خطا در دریافت رسید. لطفاً مجدداً تلاش کنید.",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
                
    async def handle_all_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle all messages - check if photo or text.
        This is the main entry point for all non-command messages.
        """
        # Check for photo first
        if update.message and update.message.photo:
            await self.handle_photo(update, context)
            return

        # Check for text messages
        if update.message and update.message.text:
            user_id = update.effective_user.id
           
            if hasattr(self, '_sales_renewal_users') and user_id in self._sales_renewal_users:
                await self.handle_sales_renew_username(update, context)
                return

            # Check if user is in status check mode
            if hasattr(self, '_status_checking_users') and user_id in self._status_checking_users:
                await self.handle_status_username(update, context)
                return
            
            # Check if user is in renewal mode
            if hasattr(self, '_renewing_users') and user_id in self._renewing_users:
                await self.handle_renew_username(update, context)
                return
           
            # Check if user is in sales status check mode
            if hasattr(self, '_sales_status_check_users') and user_id in self._sales_status_check_users:
                await self.handle_sales_status_username(update, context)
                return

             # Check if user is in sales deactivate mode
            if hasattr(self, '_sales_deactivate_users') and user_id in self._sales_deactivate_users:
                await self.handle_sales_deactivate_username(update, context)
                return
            
            # Check if user is in sales activate mode
            if hasattr(self, '_sales_activate_users') and user_id in self._sales_activate_users:
                await self.handle_sales_activate_username(update, context)
                return

            # Check if waiting for receipt
            if context.user_data.get('waiting_for_receipt'):
                pass
            
            return

    async def _notify_admin_receipt(self, user_id: int, service_id: int) -> None:
        """
        Notify admin about new receipt via admin panel.
        """
        logger.info(f"New receipt from user {user_id} for service {service_id}")

    # ============================================================
    # handle_callback_query
    # ============================================================

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle callback queries from inline keyboards.
        Routes callbacks to appropriate handlers based on callback data.
        """
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data

        logger.info(f"Callback received from user {user_id}: {callback_data}")

        try:
            # Answer callback immediately to prevent timeout
            try:
                await query.answer()
            except BadRequest as e:
                logger.warning(f"Could not answer callback: {str(e)}")

            # ============================================================
            # BUY SERVICE - Categories & Services
            # ============================================================
            if callback_data == "buy_service":
                await self.handle_buy_service(query)

            elif callback_data.startswith("category_"):
                category_id = int(callback_data.split("_")[1])
                await self.handle_category_selection(query, category_id)

            elif callback_data.startswith("service_"):
                service_id = int(callback_data.split("_")[1])
                await self.handle_service_selection(query, service_id)

            elif callback_data.startswith("purchase_"):
                service_id = int(callback_data.split("_")[1])
                await self.handle_purchase(query, service_id)

            elif callback_data.startswith("duration_"):
                parts = callback_data.split("_")
                category_id = int(parts[1])
                duration = int(parts[2])
                await self._handle_duration_selection(query, category_id, duration)

            elif callback_data.startswith("send_receipt_"):
                service_id = int(callback_data.split("_")[2])
                await self.handle_receipt_upload(query, service_id, is_renewal=False)

            # ============================================================
            # RENEWAL SERVICE - New Handlers
            # ============================================================
            elif callback_data.startswith("renew_service_"):
                service_id = int(callback_data.split("_")[2])
                await self.handle_renew_service_selection(query, service_id)

            elif callback_data == "renew_back_to_services":
                if hasattr(self, '_renew_user_info') and user_id in self._renew_user_info:
                    user_info = self._renew_user_info[user_id]
                    await self._show_renew_services(query.message, user_info)
                else:
                    await query.edit_message_text(
                        "❌ خطا. لطفاً دوباره از دکمه تمدید استفاده کنید.",
                        reply_markup=self.keyboard_builder.create_main_menu()
                    )

            elif callback_data.startswith("renew_purchase_"):
                service_id = int(callback_data.split("_")[2])
                await self.handle_renew_purchase(query, service_id)

            elif callback_data.startswith("renew_send_receipt_"):
                service_id = int(callback_data.split("_")[3])
                await self.handle_receipt_upload(query, service_id, is_renewal=True)

            # ============================================================
            # ONLINE PAYMENT
            # ============================================================
            elif callback_data.startswith("online_pay_"):
                service_id = int(callback_data.split("_")[2])
                await self.handle_online_payment(query, service_id, is_renewal=False)

            elif callback_data.startswith("renew_online_pay_"):
                service_id = int(callback_data.split("_")[3])
                await self.handle_online_payment(query, service_id, is_renewal=True)

            # ============================================================
            # MAIN MENU ITEMS
            # ============================================================
            elif callback_data == "status":
                await self.handle_status(query)

            elif callback_data == "renew_service":
                await self.handle_renew_service(query)

            elif callback_data == "test_account":
                await self.handle_test_account(query)

            elif callback_data == "get_test_account":
                await self.handle_get_test_account(query)

            elif callback_data.startswith("test_category_"):
                category_id = int(callback_data.split("_")[2])
                await self.handle_test_category_selection(query, category_id)

            elif callback_data.startswith("test_panel_"):
                panel_id = int(callback_data.split("_")[2])
                await self.handle_test_panel_selection(query, panel_id)
                
            elif callback_data == "subordinates":
                await self.handle_subordinates(query)

            elif callback_data == "help":
                await self.handle_help(query)

            elif callback_data == "support":
                await self.handle_support(query)

            elif callback_data == "wallet":
                await self.handle_wallet(query)

            elif callback_data == "connection_guide":
                await self.handle_connection_guide(query)

            elif callback_data == "main_menu":
                await self.show_main_menu(query)

            elif callback_data == "back_to_durations":
                await self.handle_buy_service(query)

            elif callback_data == "change_duration":
                await self.handle_buy_service(query)

            elif callback_data.startswith("toggle_discount_"):
                parts = callback_data.split("_")
                service_id = int(parts[2])
                is_renewal = parts[3] == "True"
                await self.handle_toggle_discount(query, service_id, is_renewal)

            elif callback_data == "check_membership":
                await self.handle_check_membership(query)

                        # ============================================================
            # SALES PARTNER
            # ============================================================
            elif callback_data == "sales_partner":
                await self.handle_sales_partner(query)

            elif callback_data == "sales_register_request":
                await self.handle_sales_register_request(query)

            elif callback_data == "sales_send_to_support":
                await self.handle_sales_send_to_support(query)

            elif callback_data == "sales_purchase":
                await self.handle_sales_purchase(query)

            elif callback_data == "sales_renew":
                await self.handle_sales_renew(query)

            elif callback_data == "sales_status_check":
                await self.handle_sales_status_check(query)

            elif callback_data == "sales_list_accounts":
                await self.handle_sales_list_accounts(query)

            elif callback_data == "sales_deactivate":
                await self.handle_sales_deactivate(query)

            elif callback_data == "sales_activate":
                await self.handle_sales_activate(query)

            elif callback_data == "sales_settlement":
                await self.handle_sales_settlement(query)

            elif callback_data.startswith("sales_renew_service_"):
                service_id = int(callback_data.split("_")[3])
                await self.handle_sales_renew_service_selection(query, service_id)
            
            elif callback_data.startswith("sales_settle_pay_"):
                amount = int(callback_data.split("_")[3])
                await self.handle_sales_settle_payment(query, amount)
            # ============================================================
            # Default / Unknown
            # ============================================================
            else:
                await query.edit_message_text(
                    text="❌ گزینه نامعتبر. لطفاً از منو انتخاب کنید.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )

        except BadRequest as e:
            if "Query is too old" in str(e) or "query id is invalid" in str(e):
                logger.warning(f"Callback query expired for user {user_id}: {str(e)}")
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="⏳ زمان پاسخگویی به دکمه منقضی شد. لطفاً دوباره تلاش کنید.",
                        reply_markup=self.keyboard_builder.create_main_menu()
                    )
                except Exception as send_error:
                    logger.error(f"Failed to send timeout message: {str(send_error)}")
            else:
                logger.error(f"BadRequest error: {str(e)}")

        except Exception as e:
            logger.error(f"Error handling callback {callback_data}: {str(e)}")
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ خطا در پردازش درخواست. لطفاً مجدداً تلاش کنید."
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {str(send_error)}")
                
    # ============================================================
    # Helper Methods
    # ============================================================

    async def _get_category_name(self, category_id: int) -> str:
        """Fetch category name by ID."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.API_BASE_URL}/admin/api/public/categories")
                data = response.json()
                if data.get("status") == "success":
                    for category in data.get("data", []):
                        if category["id"] == category_id:
                            return category["name"]
                return "دسته‌بندی"
        except Exception:
            return "دسته‌بندی"

    async def _get_back_to_categories_keyboard(self) -> InlineKeyboardMarkup:
        """Create keyboard to go back to categories."""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="📋 بازگشت به دسته‌بندی‌ها",
                    callback_data="buy_service"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def _handle_duration_selection(self, query, category_id: int, duration: int) -> None:
        """Handle duration selection - filter services by duration."""
        category_name = await self._get_category_name(category_id)
        await self._show_duration_menu(query, category_id, category_name, duration)

    # ============================================================
    # Main Handlers
    # ============================================================
    
    async def handle_status(self, query) -> None:
        """
        Handle status request - ask user for username.
        """
        user_id = query.from_user.id
        logger.info(f"Status requested by user: {user_id}")

        # Initialize attempts counter
        if not hasattr(self, '_status_attempts'):
            self._status_attempts = {}
        self._status_attempts[user_id] = 0

        # Mark that user is in status check mode
        if not hasattr(self, '_status_checking_users'):
            self._status_checking_users = set()
        self._status_checking_users.add(user_id)

        message = (
            "📊 **وضعیت من**\n\n"
            "لطفاً یوزرنیم خود را وارد کنید.\n\n"
            "📌 **نحوه ورود:**\n"
            "• اگر از طریق پنل قبلی اکانت دارید: `acc` به همراه اعداد\n"
            "  مثال: `acc123` یا `acc456`\n"
            "• اگر از طریق بات خرید کرده‌اید: `bot` به همراه اعداد\n"
            "  مثال: `bot1` یا `bot2`\n\n"
            "⚠️ **توجه:**\n"
            "• حروف بزرگ و کوچک مهم نیست (به طور خودکار اصلاح می‌شود)\n"
            "• فقط عدد و حروف مجاز است\n\n"
            "شما **3 بار** فرصت دارید.\n"
        )

        try:
            await query.edit_message_text(
                text=message,
                parse_mode="Markdown",
                reply_markup=None
            )
        except BadRequest:
            await query.message.reply_text(
                text=message,
                parse_mode="Markdown",
                reply_markup=None
            )
            
    async def handle_status_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Process username input for status check.
        """
        user_id = update.effective_user.id
        username_input = update.message.text.strip()

        # Check if user is in status check mode
        if not hasattr(self, '_status_checking_users') or user_id not in self._status_checking_users:
            return


        # Initialize attempts
        if not hasattr(self, '_status_attempts'):
            self._status_attempts = {}
        if user_id not in self._status_attempts:
            self._status_attempts[user_id] = 0

        # Validate input
        if not username_input or len(username_input) < 2:
            self._status_attempts[user_id] += 1
            remaining = 3 - self._status_attempts[user_id]

            if remaining <= 0:
                self._status_checking_users.remove(user_id)
                await update.message.reply_text(
                    "❌ شما 3 بار تلاش ناموفق داشتید!\n\n"
                    "برای شروع مجدد از منوی اصلی استفاده کنید.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return

            await update.message.reply_text(
                f"❌ **یوزرنیم وارد شده معتبر نیست!**\n\n"
                f"لطفاً یوزرنیم صحیح را وارد کنید.\n\n"
                f"🔢 تلاش باقی‌مانده: {remaining}\n\n",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu", style="danger")]
                ])
            )
            return

        # Search for user
        normalized_username = username_input.strip()
        logger.info(f"🔍 Searching for user '{normalized_username}' for status check")

        user_info = await self._find_user_in_panels(normalized_username)

        if not user_info:
            self._status_attempts[user_id] += 1
            remaining = 3 - self._status_attempts[user_id]

            if remaining <= 0:
                self._status_checking_users.remove(user_id)
                await update.message.reply_text(
                    "❌ شما 3 بار تلاش ناموفق داشتید!\n\n"
                    "کاربر مورد نظر پیدا نشد.\n"
                    "برای شروع مجدد از منوی اصلی استفاده کنید.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return

            await update.message.reply_text(
                f"❌ **یوزرنیم `{username_input}` پیدا نشد!**\n\n"
                f"🔢 تلاش باقی‌مانده: {remaining}\n\n",
                parse_mode="Markdown"
            )
            return

        # ====== Success - User found ======
        self._status_checking_users.remove(user_id)

        # Show user status
        await self._show_user_status(update, user_info)


    async def _show_user_status(self, update: Update, user_info: dict) -> None:
        """
        Show detailed user status information.
        """
        from datetime import datetime

        username = user_info.get('email', 'N/A')
        client = user_info.get('client', {})
        panel = user_info.get('panel', {})

        # ====== اطلاعات حجم ======
        total_bytes = client.get('totalGB', 0)
        used_bytes = client.get('usedGB', 0)
        
        # اگر usedGB نداریم، از usedTraffic استفاده کن
        if used_bytes == 0:
            used_bytes = client.get('usedTraffic', 0)
        
        remaining_bytes = client.get('remainingGB', 0)
        if remaining_bytes == 0 and total_bytes > 0:
            remaining_bytes = max(0, total_bytes - used_bytes)

        is_unlimited = total_bytes == 0

        # ====== اطلاعات زمان ======
        expiry_time = client.get('expiryTime', 0)
        expiry_date = None
        remaining_days = None
        
        if expiry_time and expiry_time > 0:
            expiry_date = datetime.fromtimestamp(expiry_time / 1000)
            remaining_days = (expiry_date - datetime.now()).days

        # ====== ساخت پیام ======
        message_lines = [
            "📊 **وضعیت سرویس شما**",
            "",
            f"📧 **یوزرنیم:** `{username}`",
            f"🖥️ **پنل:** {panel.get('name', 'نامشخص')}",
            "",
            "─" * 30,
            "",
        ]

        # وضعیت فعال/غیرفعال
        if client.get('enable', False):
            message_lines.append("✅ **وضعیت:** فعال")
        else:
            message_lines.append("❌ **وضعیت:** غیرفعال")

        message_lines.append("")

        # اطلاعات حجم
        if is_unlimited:
            message_lines.append("📊 **حجم:** ♾️ نامحدود")
        else:
            total_gb = total_bytes / 1073741824
            used_gb = used_bytes / 1073741824
            remaining_gb = remaining_bytes / 1073741824
            
            # درصد مصرف
            usage_percent = (used_gb / total_gb * 100) if total_gb > 0 else 0
            
            message_lines.append(f"📊 **اطلاعات حجم:**")
            message_lines.append(f"   • حجم کل: `{total_gb:.2f} GB`")
            message_lines.append(f"   • حجم مصرفی: `{used_gb:.2f} GB`")
            message_lines.append(f"   • حجم باقی‌مانده: `{remaining_gb:.2f} GB`")
            message_lines.append(f"   • درصد مصرف: `{usage_percent:.1f}%`")
        
        message_lines.append("")

        # اطلاعات زمان
        if expiry_date:
            message_lines.append(f"📅 **اطلاعات زمان:**")
            message_lines.append(f"   • تاریخ انقضا: `{expiry_date.strftime('%Y-%m-%d')}`")
            
            if remaining_days is not None:
                if remaining_days > 0:
                    message_lines.append(f"   • روزهای باقی‌مانده: `{remaining_days} روز` ✅")
                elif remaining_days == 0:
                    message_lines.append(f"   • امروز آخرین روز است! ⚠️")
                else:
                    message_lines.append(f"   • منقضی شده ({abs(remaining_days)} روز پیش) ❌")
        else:
            message_lines.append(f"📅 **زمان:** ♾️ نامحدود")
        
        # اطلاعات اضافی
        if client.get('limitIp', 0) > 0:
            message_lines.append("")
            message_lines.append(f"👥 **محدودیت IP:** {client.get('limitIp')} دستگاه")

        message_lines.append("")
        message_lines.append("💡 برای تمدید سرویس از دکمه 'تمدید سرویس' استفاده کنید.")

        message = "\n".join(message_lines)

        # ساخت کیبورد
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🔄 تمدید سرویس",
                    callback_data="renew_service",
                    style="success"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ]
        ]

        await update.message.reply_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        
    async def handle_buy_service(self, query) -> None:
        """Handle buy service - show categories from admin panel."""
        user_id = query.from_user.id
        logger.info(f"Buy service requested by user: {user_id}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.API_BASE_URL}/admin/api/public/categories")
                data = response.json()

            if data.get("status") != "success":
                logger.error(f"API error in handle_buy_service: {data}")
                await query.edit_message_text(
                    text="❌ خطا در دریافت دسته‌بندی‌ها. لطفاً مجدداً تلاش کنید.",
                    reply_markup=self.keyboard_builder.create_sub_menu()
                )
                return

            categories = data.get("data", [])

            if not categories:
                await query.edit_message_text(
                    text="📭 **هیچ دسته‌بندی موجود نیست**\n\n"
                         "در حال حاضر هیچ سرویسی ارائه نمی‌شود.\n"
                         "لطفاً با پشتیبانی در تماس باشید.",
                    parse_mode="Markdown",
                    reply_markup=self.keyboard_builder.create_sub_menu()
                )
                return

            keyboard = []
            for cat in categories:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"📂 {cat['name']}",
                        callback_data=f"category_{cat['id']}"
                    )
                ])

            keyboard.append([
                InlineKeyboardButton(
                    text="🔙 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ])

            await query.edit_message_text(
                text="📋 **دسته‌بندی سرویس‌ها**\n\nلطفاً یک دسته‌بندی را انتخاب کنید:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except httpx.TimeoutException:
            await query.edit_message_text(
                text="⏳ زمان ارتباط با سرور به پایان رسید. لطفاً مجدداً تلاش کنید.",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
        except Exception as e:
            logger.error(f"Error in handle_buy_service: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در دریافت سرویس‌ها. لطفاً مجدداً تلاش کنید.",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )

    async def handle_category_selection(self, query, category_id: int) -> None:
        """Handle category selection - show duration menu with default minimum duration."""
        user_id = query.from_user.id
        logger.info(f"Category {category_id} selected by user {user_id}")

        try:
            category_name = await self._get_category_name(category_id)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/public/services?category_id={category_id}"
                )
                data = response.json()

            services = data.get("data", []) if data.get("status") == "success" else []

            durations = sorted(set(
                s.get("duration") for s in services
                if s.get("duration") is not None
            ))

            if not durations:
                await self._show_services_list(query, services, category_name)
                return

            default_duration = durations[0]
            await self._show_duration_menu(query, category_id, category_name, default_duration)

        except Exception as e:
            logger.error(f"Error in handle_category_selection: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در دریافت سرویس‌ها. لطفاً مجدداً تلاش کنید.",
                reply_markup=await self._get_back_to_categories_keyboard()
            )

    async def _show_duration_menu(self, query, category_id: int, category_name: str, selected_duration: int = None) -> None:
        """Show duration menu with services filtered by duration."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/admin/api/public/services?category_id={category_id}"
            )
            data = response.json()

        services = data.get("data", []) if data.get("status") == "success" else []

        durations = sorted(set(
            s.get("duration") for s in services
            if s.get("duration") is not None
        ))

        if not durations:
            await self._show_services_list(query, services, category_name)
            return

        if selected_duration is None:
            selected_duration = durations[0]

        filtered_services = [s for s in services if s.get("duration") == selected_duration]

        duration_buttons = []
        for d in durations:
            if d == selected_duration:
                button_text = f"🚀 {d} ماه"
                style = "success"
            else:
                button_text = f"📅 {d} ماه"
                style = None
            duration_buttons.append(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"duration_{category_id}_{d}",
                    style=style
                )
            )

        keyboard = []
        for i in range(0, len(duration_buttons), 4):
            keyboard.append(duration_buttons[i:i+4])

        if filtered_services:
            for service in filtered_services:
                service_name = service.get('name', 'نامشخص')
                
                panel_name = service.get('panel_name', 'نامشخص')
                
                users = service.get('users', 'نامحدود')
                if users and users != "unlimited":
                    users_display = users
                else:
                    users_display = "♾️"
                
                price = service.get('price')
                if price:
                    price_display = f"{int(price):,}"
                else:
                    price_display = "تماس"
                
                button_text = f"📦 {service_name} | {panel_name} | 👥{users_display} | 💰{price_display}"
                
                keyboard.append([
                    InlineKeyboardButton(
                        text=button_text[:60], 
                        callback_data=f"service_{service['id']}",
                        style="primary"
                    )
                ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    text="📭 هیچ سرویسی برای این مدت وجود ندارد",
                    callback_data="noop",
                    style="danger"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                text="🔙 بازگشت به دسته‌بندی‌ها",
                callback_data="buy_service"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text="🏠 بازگشت به منو",
                callback_data="main_menu",
                style="danger"
            )
        ])

        duration_text = f" (مدت: {selected_duration} ماه)" if selected_duration else ""
        await query.edit_message_text(
            text=f"📂 **{category_name}**{duration_text}\n\n"
                 f"لطفاً مدت زمان مورد نظر را انتخاب کنید، سپس سرویس مورد نظر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_services_list(self, query, services: list, category_name: str) -> None:
        """Show services list without duration filtering."""
        keyboard = []

        for service in services:
            service_name = service.get('name', 'نامشخص')
            
            panel_name = service.get('panel_name', 'نامشخص')
            
            users = service.get('users', 'نامحدود')
            if users and users != "unlimited":
                users_display = users
            else:
                users_display = "♾️"
            
            price = service.get('price')
            if price:
                price_display = f"{int(price):,}"
            else:
                price_display = "تماس"
            
            button_text = f"📦 {service_name} | {panel_name} | 👥{users_display} | 💰{price_display}"
            
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text[:60],
                    callback_data=f"service_{service['id']}",
                    style="primary"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                text="🔙 بازگشت به دسته‌بندی‌ها",
                callback_data="buy_service"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text="🏠 بازگشت به منو",
                callback_data="main_menu",
                style="danger"
            )
        ])

        await query.edit_message_text(
            text=f"📂 **{category_name}**\n\nلطفاً یکی از سرویس‌های زیر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        ) 
    async def handle_service_selection(self, query, service_id: int) -> None:
        """
        Handle service selection - show service details and buy option.
        """
        user_id = query.from_user.id
        logger.info(f"Service {service_id} selected by user {user_id}")

        try:
            # Get service details
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/public/services"
                )
                data = response.json()

            service = None
            if data.get("status") == "success":
                for s in data.get("data", []):
                    if s["id"] == service_id:
                        service = s
                        break

            if not service:
                await query.edit_message_text(
                    text="❌ سرویس مورد نظر پیدا نشد.",
                    reply_markup=self._get_back_to_categories_keyboard()
                )
                return

            service_name = service.get('name', 'نامشخص')
            
            panel_name = service.get('panel_name', 'نامشخص')
            
            users = service.get('users', 'نامحدود')
            if users and users != "unlimited":
                users_display = f"{users} کاربر"
            else:
                users_display = "♾️ نامحدود"
            
            price = service.get('price')
            if price:
                price_display = f"{int(price):,} تومان"
            else:
                price_display = "تماس بگیرید"

            message = (
                f"📦 **{service_name}**\n\n"
                f"🖥️ **پنل:** {panel_name}\n"
                f"👥 **تعداد کاربر:** {users_display}\n"
                f"💰 **قیمت:** {price_display}\n\n"
                f"برای خرید این سرویس، روی دکمه زیر کلیک کنید:"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🛒 خرید این سرویس",
                        callback_data=f"purchase_{service_id}",
                        style="success"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت به سرویس‌ها",
                        callback_data=f"category_{service['category_id']}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 بازگشت به منو",
                        callback_data="main_menu",
                        style="danger"
                    )
                ]
            ]

            await query.edit_message_text(
                text=message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in handle_service_selection: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در دریافت اطلاعات سرویس. لطفاً مجدداً تلاش کنید.",
                reply_markup=self._get_back_to_categories_keyboard()
            )
    # ============================================================
    # PURCHASE HANDLERS
    # ============================================================

    async def handle_receipt_upload(self, query, service_id: int, is_renewal: bool = False) -> None:
        """
        Handle receipt upload - instruct user to send image.
        
        Args:
            query: Callback query object
            service_id: Service ID
            is_renewal: Whether this is a renewal
        """
        user_id = query.from_user.id
        logger.info(f"Receipt upload requested by user {user_id} for service {service_id} (renewal: {is_renewal})")
        
        # Store service_id, renewal flag, and user_info for this user
        if not hasattr(self, '_pending_receipts'):
            self._pending_receipts = {}
        
        # Get user_info from renewal data if it's a renewal
        user_info = None
        if is_renewal and hasattr(self, '_renew_pending_purchases') and user_id in self._renew_pending_purchases:
            user_info = self._renew_pending_purchases[user_id].get('user_info')
        
        self._pending_receipts[user_id] = {
            "service_id": service_id,
            "is_renewal": is_renewal,
            "user_info": user_info  # Save user_info for renewal
        }
        
        keyboard = [
            [
                InlineKeyboardButton(
                    text="📋 بازگشت به دسته‌بندی‌ها",
                    callback_data="buy_service"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ]
        ]
        
        renewal_text = "تمدید" if is_renewal else "خرید"
        
        await query.edit_message_text(
            text=f"📤 **ارسال رسید پرداخت ({renewal_text})**\n\n"
                 f"لطفاً **اسکرین شات** رسید پرداخت خود را در همین چت ارسال کنید.\n\n"
                 f"📌 **نکات:**\n"
                 f"• تصویر باید خوانا باشد\n"
                 f"• مبلغ و تاریخ پرداخت مشخص باشد\n"
                 f"• پس از ارسال، رسید شما بررسی خواهد شد\n\n"
                 f"⏳ پس از تأیید، **همان سرویس شما {'تمدید' if is_renewal else 'ساخته'} می‌شود.**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ============================================================
    # Renew Service Handlers
    # ============================================================

    async def handle_renew_service(self, query) -> None:
        """
        Handle service renewal - ask user for username.
        """
        user_id = query.from_user.id
        logger.info(f"Renew service requested by user: {user_id}")
        
        # Initialize renewal attempts counter
        if not hasattr(self, '_renew_attempts'):
            self._renew_attempts = {}
        self._renew_attempts[user_id] = 0
        
        # Mark that user is in renewal mode
        if not hasattr(self, '_renewing_users'):
            self._renewing_users = set()
        self._renewing_users.add(user_id)
        
        message = (
            "🔄 **تمدید سرویس**\n\n"
            "لطفاً یوزرنیم خود را وارد کنید.\n\n"
            "📌 **نحوه ورود:**\n"
            "• اگر از طریق پنل قبلی اکانت دارید: `acc` به همراه اعداد\n"
            "  مثال: `acc123` یا `acc456`\n"
            "• اگر از طریق بات خرید کرده‌اید: `bot` به همراه اعداد\n"
            "  مثال: `bot1` یا `bot2`\n\n"
            "⚠️ **توجه:**\n"
            "• حروف بزرگ و کوچک مهم نیست (به طور خودکار اصلاح می‌شود)\n"
            "• فقط عدد و حروف مجاز است\n\n"
            "شما **3 بار** فرصت دارید.\n"
        )
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=None
        )
       
    async def handle_renew_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Process username input for renewal.
        """
        user_id = update.effective_user.id
        username_input = update.message.text.strip()
        
        if not hasattr(self, '_renewing_users') or user_id not in self._renewing_users:
            return
        
        
        if not hasattr(self, '_renew_attempts'):
            self._renew_attempts = {}
        if user_id not in self._renew_attempts:
            self._renew_attempts[user_id] = 0
        
        if not username_input or len(username_input) < 2:
            self._renew_attempts[user_id] += 1
            remaining = 3 - self._renew_attempts[user_id]
            
            if remaining <= 0:
                self._renewing_users.remove(user_id)
                await update.message.reply_text(
                    "❌ شما 3 بار تلاش ناموفق داشتید!\n\n"
                    "برای شروع مجدد از منوی اصلی استفاده کنید.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return
            
            await update.message.reply_text(
                f"❌ **یوزرنیم وارد شده معتبر نیست!**\n\n"
                f"لطفاً یوزرنیم صحیح را وارد کنید.\n\n"
                f"🔢 تلاش باقی‌مانده: {remaining}\n\n",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu", style="danger")]
                ])
            )
            return
        
        normalized_username = username_input.strip()
        user_info = await self._find_user_in_panels(normalized_username)
        
        if not user_info:
            self._renew_attempts[user_id] += 1
            remaining = 3 - self._renew_attempts[user_id]
            
            if remaining <= 0:
                self._renewing_users.remove(user_id)
                await update.message.reply_text(
                    "❌ شما 3 بار تلاش ناموفق داشتید!\n\n"
                    "کاربر مورد نظر پیدا نشد.\n"
                    "برای شروع مجدد از منوی اصلی استفاده کنید.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return
            
            await update.message.reply_text(
                f"❌ **یوزرنیم `{username_input}` پیدا نشد!**\n\n"
                f"🔢 تلاش باقی‌مانده: {remaining}\n\n",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu", style="danger")]
                ])
            )
            return
        
        # ====== موفقیت ======
        self._renewing_users.remove(user_id)
        
        # ====== نمایش سرویس‌های قابل تمدید ======
        await self._show_renew_services(update.message, user_info)


    async def _show_renew_services(self, query_or_message, user_info: dict) -> None:
        """
        Show available services for renewal based on user type and panel.
        Works with both query (callback) and message (reply).
        """
        # Check if it's a query or message
        if hasattr(query_or_message, 'edit_message_text'):
            is_query = True
            query = query_or_message
            user_id = query.from_user.id
        else:
            is_query = False
            message = query_or_message
            user_id = message.chat.id
        
        username = user_info.get('email')
        client = user_info.get('client', {})
        panel = user_info.get('panel', {})
        
        # ====== تشخیص دسته سرویس ======
        is_unlimited = client.get('is_unlimited', False)
        total_bytes = client.get('totalGB', 0)
        if 'is_unlimited' not in client:
            is_unlimited = total_bytes == 0
        
        panel_id = panel.get('id')
        if not panel_id:
            if is_query:
                await query.edit_message_text(
                    "❌ اطلاعات پنل یافت نشد.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
            else:
                await message.reply_text(
                    "❌ اطلاعات پنل یافت نشد.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
            return
        
        # ====== دریافت لیست سرویس‌ها ======
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/admin/api/services"
            )
            data = response.json()
        
        if data.get("status") != "success":
            if is_query:
                await query.edit_message_text(
                    "❌ خطا در دریافت لیست سرویس‌ها.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
            else:
                await message.reply_text(
                    "❌ خطا در دریافت لیست سرویس‌ها.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
            return
        
        services = data.get("data", [])
        
        # ====== فیلتر سرویس‌ها ======
        filtered_services = []
        for service in services:
            if not service.get('is_active'):
                continue
            if service.get('panel_id') != panel_id:
                continue
            
            service_volume = service.get('volume')
            service_is_unlimited = service_volume is None or service_volume == "unlimited"
            
            if is_unlimited and service_is_unlimited:
                filtered_services.append(service)
            elif not is_unlimited and not service_is_unlimited:
                filtered_services.append(service)
        
        if not filtered_services:
            error_text = (
                "❌ **هیچ سرویسی برای تمدید یافت نشد.**\n\n"
                f"سرویس شما {'نامحدود' if is_unlimited else 'حجمی'} است.\n"
                f"پنل: {panel.get('name', 'نامشخص')}\n\n"
                "لطفاً با پشتیبانی تماس بگیرید."
            )
            if is_query:
                await query.edit_message_text(
                    error_text,
                    parse_mode="Markdown",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
            else:
                await message.reply_text(
                    error_text,
                    parse_mode="Markdown",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
            return
        
        # ====== ساخت دکمه‌ها ======
        keyboard = []
        for service in filtered_services:
            service_name = service.get('name', 'نامشخص')
            panel_name = service.get('panel_name', 'نامشخص')
            
            users = service.get('users', 'نامحدود')
            users_display = users if users and users != "unlimited" else "♾️"
            
            price = service.get('price')
            price_display = f"{int(price):,}" if price else "تماس"
            
            button_text = f"📦 {service_name} | {panel_name} | 👥{users_display} | 💰{price_display}"
            
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text[:60],
                    callback_data=f"renew_service_{service['id']}",
                    style="primary"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                text="🔙 بازگشت به منو",
                callback_data="main_menu",
                style="danger"
            )
        ])
        
        # ====== ذخیره اطلاعات ======
        if not hasattr(self, '_renew_user_info'):
            self._renew_user_info = {}
        self._renew_user_info[user_id] = user_info
        
        # ====== ارسال پیام ======
        message_text = (
            f"🔄 **تمدید سرویس**\n\n"
            f"👤 کاربر: `{username}`\n"
            f"📡 پنل: {panel.get('name', 'نامشخص')}\n"
            f"📊 نوع: {'♾️ نامحدود' if is_unlimited else '📦 حجمی'}\n\n"
            f"لطفاً سرویس مورد نظر برای تمدید را انتخاب کنید:"
        )
        
        if is_query:
            await query.edit_message_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await message.reply_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
    async def handle_renew_service_selection(self, query, service_id: int) -> None:
        """
        Handle service selection for renewal.
        
        Args:
            query: Callback query object
            service_id: Selected service ID
        """
        user_id = query.from_user.id
        logger.info(f"Renew service {service_id} selected by user {user_id}")
        
        try:
            # Get user info
            if not hasattr(self, '_renew_user_info') or user_id not in self._renew_user_info:
                await query.edit_message_text(
                    "❌ خطا در اطلاعات کاربر. لطفاً دوباره از دکمه تمدید استفاده کنید.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return
            
            user_info = self._renew_user_info[user_id]
            username = user_info.get('email')
            
            # Get service details
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/services"
                )
                data = response.json()
            
            service = None
            if data.get("status") == "success":
                for s in data.get("data", []):
                    if s["id"] == service_id:
                        service = s
                        break
            
            if not service:
                await query.edit_message_text(
                    text="❌ سرویس مورد نظر پیدا نشد.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return
            
            # Store selected service for renewal
            if not hasattr(self, '_renew_selected_service'):
                self._renew_selected_service = {}
            self._renew_selected_service[user_id] = {
                "service": service,
                "user_info": user_info
            }
            
            # Show service details
            price = service.get('price')
            price_text = f"{int(price):,} تومان" if price else "تماس بگیرید"
            volume = service.get('volume') or "نامحدود"
            duration = service.get('duration', 1)
            panel_name = service.get('panel_name', 'نامشخص')
            
            message = (
                f"🔄 **تمدید سرویس**\n\n"
                f"👤 کاربر: `{username}`\n"
                f"📦 **سرویس:** {service['name']}\n"
                f"📊 **حجم:** {volume} GB\n"
                f"⏱️ **مدت:** {duration} ماه\n"
                f"💰 **قیمت:** {price_text}\n"
                f"🖥️ **پنل:** {panel_name}\n\n"
                f"برای تمدید این سرویس، روی دکمه زیر کلیک کنید:"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🛒 تمدید این سرویس",
                        callback_data=f"renew_purchase_{service_id}",
                        style="success"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت به لیست سرویس‌ها",
                        callback_data="renew_back_to_services"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 بازگشت به منو",
                        callback_data="main_menu",
                        style="danger"
                    )
                ]
            ]
            
            await query.edit_message_text(
                text=message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Error in handle_renew_service_selection: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در دریافت اطلاعات سرویس. لطفاً مجدداً تلاش کنید.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )


    async def handle_renew_purchase(self, query, service_id: int) -> None:
        """Handle renewal purchase - show payment instructions for renewal."""
        user_id = query.from_user.id
        logger.info(f"Renew purchase requested by user {user_id} for service {service_id}")

        try:
            # Get selected service and user info
            if not hasattr(self, '_renew_selected_service') or user_id not in self._renew_selected_service:
                await query.edit_message_text(
                    "❌ خطا در اطلاعات سرویس. لطفاً دوباره تلاش کنید.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return

            renewal_data = self._renew_selected_service[user_id]
            service = renewal_data.get('service')
            user_info = renewal_data.get('user_info')
            username = user_info.get('email')

            if not service:
                await query.edit_message_text(
                    "❌ سرویس مورد نظر پیدا نشد.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return

            # ====== ✅ FIRST: Get payment settings ======
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.API_BASE_URL}/admin/api/settings/payment")
                payment_settings = response.json().get("data", {})

            # ====== ✅ SECOND: Build card numbers text ======
            card_numbers = payment_settings.get("card_numbers", [])
            cards_text = ""
            if card_numbers:
                cards_text = "\n".join([
                    f"   • {card.get('number', '')} | {card.get('holder', '')}"
                    for card in card_numbers
                ])

            # ====== ✅ THEN: Build payment message ======
            price = service.get('price')
            price_text = f"{int(price):,} تومان" if price else "تماس بگیرید"
            volume = service.get('volume') or "نامحدود"
            duration = service.get('duration', 1)
            panel_name = service.get('panel_name', 'نامشخص')

            payment_message = (
                f"🔄 **تمدید سرویس**\n\n"
                f"👤 کاربر: `{username}`\n"
                f"📦 **سرویس:** {service['name']}\n"
                f"📊 **حجم:** {volume} GB\n"
                f"⏱️ **مدت:** {duration} ماه\n"
                f"💰 **قیمت:** {price_text}\n"
                f"🖥️ **پنل:** {panel_name}\n\n"
                f"---\n\n"
            )

            # Add card numbers if receipt enabled
            if payment_settings.get("receipt_payment_enabled") and cards_text:
                payment_message += (
                    f"📌 **مراحل تمدید:**\n\n"
                    f"1️⃣ مبلغ را کارت به کارت کنید.\n"
                    f"2️⃣ اسکرین شات رسید را ارسال کنید.\n"
                    f"3️⃣ پس از تأیید، سرویس تمدید می‌شود.\n\n"
                    f"💳 **شماره کارت:**\n"
                    f"{cards_text}\n\n"
                    f"📌 مبلغ را کارت به کارت کنید و رسید را ارسال کنید.\n\n"
                )

            payment_message += "پس از پرداخت، روی دکمه زیر کلیک کنید:"

            # Build keyboard
            keyboard = []

            if payment_settings.get("online_payment_enabled"):
                keyboard.append([
                    InlineKeyboardButton(
                        text="💳 پرداخت آنلاین",
                        callback_data=f"renew_online_pay_{service_id}",
                        style="success"
                    )
                ])

            if payment_settings.get("receipt_payment_enabled"):
                keyboard.append([
                    InlineKeyboardButton(
                        text="📤 ارسال رسید پرداخت",
                        callback_data=f"renew_send_receipt_{service_id}"
                    )
                ])

            # Check user's accumulated discount
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/referrals/stats/{user_id}"
                )
                referral_stats = response.json().get("data", {})

            discount_info = referral_stats.get("discount", {})
            remaining_percent = discount_info.get("remaining_percent", 0)

            self._discount_state[user_id] = {
                "service_id": service_id,
                "is_renewal": True,
                "discount_applied": False,
                "original_price": price,
                "accumulated_discount": remaining_percent,
                "referral_discount": 0
            }

            if remaining_percent > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"🎁 استفاده از تخفیف ({remaining_percent}%)",
                        callback_data=f"toggle_discount_{service_id}_True",
                        style="success"
                    )
                ])

            keyboard.append([
                InlineKeyboardButton("🔙 بازگشت به سرویس‌ها", callback_data="renew_back_to_services")
            ])
            keyboard.append([
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data="main_menu", style="danger")
            ])

            if not hasattr(self, '_renew_pending_purchases'):
                self._renew_pending_purchases = {}
            self._renew_pending_purchases[user_id] = {
                "service_id": service_id,
                "service_name": service.get('name'),
                "service_details": {
                    "volume": volume,
                    "duration": duration,
                    "price": price,
                    "panel_name": panel_name,
                    "panel_id": service.get('panel_id'),
                    "inbound_id": service.get('inbound_id')
                },
                "user_info": user_info,
                "is_renewal": True
            }

            await query.edit_message_text(
                text=payment_message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in handle_renew_purchase: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در پردازش تمدید. لطفاً مجدداً تلاش کنید.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            
    async def _process_renewal(self, update: Update, user_info: dict, service_id: int = None) -> None:
        """
        Process renewal for found user.
        
        Args:
            update: Telegram update object
            user_info: Dict containing user information
            service_id: Selected service ID for renewal
        """
        from datetime import datetime, timedelta
        import asyncio
        import httpx
        
        user_id = update.effective_user.id
        username = user_info.get('email')
        panel = user_info.get('panel', {})
        client = user_info.get('client', {})
        
        # Extract client data
        expiry_time = client.get('expiryTime', 0)
        total_bytes = client.get('totalGB', 0)
        used_bytes = client.get('usedGB', 0)
        sub_id = client.get('subId', '')
        limit_ip = client.get('limitIp', 0)
        
        # Calculate expiry date
        expiry_date = None
        if expiry_time and expiry_time > 0:
            expiry_date = datetime.fromtimestamp(expiry_time / 1000)
        
        # Calculate remaining days
        remaining_days = 0
        if expiry_date:
            remaining_days = (expiry_date - datetime.now()).days
            if remaining_days < 0:
                remaining_days = 0
        
        # Calculate remaining traffic
        total_gb = total_bytes / 1073741824 if total_bytes > 0 else 0
        used_gb = used_bytes / 1073741824 if total_bytes > 0 else 0
        remaining_gb = total_gb - used_gb if total_bytes > 0 else 0
        if remaining_gb < 0:
            remaining_gb = 0
        
        is_unlimited = total_bytes == 0
        
        # Get service details if service_id is provided
        service_duration = 30  # Default
        service_volume = None
        if service_id:
            try:
                import httpx as http_client
                resp = await http_client.AsyncClient(timeout=10.0).get(
                    f"{settings.API_BASE_URL}/admin/api/services"
                )
                data = resp.json()
                if data.get("status") == "success":
                    for s in data.get("data", []):
                        if s["id"] == service_id:
                            service_duration = s.get("duration", 30)
                            service_volume = s.get("volume")
                            break
            except Exception as e:
                logger.error(f"Error fetching service details: {str(e)}")
        
        # Build message for user
        message_lines = [
            f"📊 **اطلاعات سرویس:** `{username}`",
            "",
            f"🖥️ **پنل:** {panel.get('name', 'نامشخص')}",
            "",
            f"📅 **روزهای باقی‌مانده:** {remaining_days} روز"
        ]
        
        if is_unlimited:
            message_lines.append(f"📊 **حجم:** ♾️ نامحدود")
        else:
            message_lines.append(f"📊 **حجم باقی‌مانده:** {remaining_gb:.1f} GB")
        
        message_lines.append("")
        message_lines.append("⏳ لطفاً منتظر بمانید...")
        
        message = "\n".join(message_lines)
        
        loading_msg = await update.message.reply_text(
            message,
            parse_mode="Markdown"
        )
        
        try:
            panel_url = panel.get('url', '').rstrip('/')
            api_token = panel.get('api_token', '')
            
            if not panel_url or not api_token:
                await loading_msg.edit_text(
                    "❌ **خطا در تمدید سرویس**\n\n"
                    "اطلاعات پنل کامل نیست. لطفاً با پشتیبانی تماس بگیرید.",
                    parse_mode="Markdown",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return
            
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
                # Step 1: Get inbound IDs for this user
                inbounds_resp = await http_client.get(
                    f"{panel_url}/panel/api/inbounds/list",
                    headers=headers
                )
                
                inbound_ids = []
                if inbounds_resp.status_code == 200:
                    inbounds_data = inbounds_resp.json()
                    if inbounds_data.get("success") and inbounds_data.get("obj"):
                        for inbound in inbounds_data.get("obj", []):
                            for client_obj in inbound.get("clientStats", []):
                                if client_obj.get("email") == username:
                                    inbound_ids.append(inbound.get("id"))
                                    break
                            if inbound_ids:
                                break
                
                if not inbound_ids:
                    await loading_msg.edit_text(
                        "❌ **خطا در تمدید سرویس**\n\n"
                        "اینباند کاربر پیدا نشد. لطفاً با پشتیبانی تماس بگیرید.",
                        parse_mode="Markdown",
                        reply_markup=self.keyboard_builder.create_main_menu()
                    )
                    return
                
                # Step 2: Reset traffic
                reset_resp = await http_client.post(
                    f"{panel_url}/panel/api/clients/resetTraffic/{username}",
                    headers=headers
                )
                
                if reset_resp.status_code != 200:
                    await loading_msg.edit_text(
                        f"❌ **خطا در ریست ترافیک**\n\n"
                        f"کد خطا: {reset_resp.status_code}\n"
                        f"لطفاً با پشتیبانی تماس بگیرید.",
                        parse_mode="Markdown",
                        reply_markup=self.keyboard_builder.create_main_menu()
                    )
                    return
                
                # Step 3: Calculate new expiry time
                # Add service duration to current time
                new_expiry_time = int((datetime.now() + timedelta(days=service_duration)).timestamp() * 1000)
                
                # Step 4: Prepare update data (KEEP EXISTING USER DATA)
                update_data = {
                    "email": username,
                    "totalGB": total_bytes if not is_unlimited else 0,
                    "expiryTime": new_expiry_time,
                    "tgId": client.get('tgId', user_id),
                    "limitIp": limit_ip,
                    "enable": True,
                    "subId": sub_id
                }
                
                # Step 5: Update existing user (NOT create new)
                update_resp = await http_client.post(
                    f"{panel_url}/panel/api/clients/update/{username}",
                    headers=headers,
                    json=update_data
                )
                
                if update_resp.status_code != 200:
                    await loading_msg.edit_text(
                        f"❌ **خطا در تمدید سرویس**\n\n"
                        f"کد خطا: {update_resp.status_code}\n"
                        f"لطفاً با پشتیبانی تماس بگیرید.",
                        parse_mode="Markdown",
                        reply_markup=self.keyboard_builder.create_main_menu()
                    )
                    return
                
                update_result = update_resp.json()
                if not update_result.get("success"):
                    await loading_msg.edit_text(
                        f"❌ **خطا در تمدید سرویس**\n\n"
                        f"{update_result.get('msg', 'خطای ناشناخته')}\n"
                        f"لطفاً با پشتیبانی تماس بگیرید.",
                        parse_mode="Markdown",
                        reply_markup=self.keyboard_builder.create_main_menu()
                    )
                    return
                
                # Success
                new_expiry_date = datetime.now() + timedelta(days=service_duration)
                await loading_msg.edit_text(
                    "✅ **تمدید با موفقیت انجام شد!**\n\n"
                    f"📧 **یوزرنیم:** `{username}`\n"
                    f"📅 **تاریخ انقضای جدید:** {new_expiry_date.strftime('%Y-%m-%d')}\n"
                    f"📊 **حجم:** {'♾️ نامحدود' if is_unlimited else f'{total_gb:.1f} GB'}\n\n"
                    "💡 برای مشاهده اطلاعات جدید از بخش 'وضعیت من' استفاده کنید.",
                    parse_mode="Markdown",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                
        except Exception as e:
            logger.error(f"Error in renewal process: {str(e)}")
            await loading_msg.edit_text(
                "❌ **خطا در تمدید سرویس**\n\n"
                f"خطا: {str(e)}\n"
                "لطفاً با پشتیبانی تماس بگیرید.",
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_main_menu()
            )

    async def _find_user_in_panels(self, username: str) -> Optional[dict]:
        """
        Find user in panels by email.
        """
        try:
            import httpx
            from datetime import datetime
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            # ====== دریافت مستقیم از دیتابیس ======
            engine = create_engine(settings.DATABASE_URL)
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            
            # دریافت پنل‌ها با توکن کامل
            from admin.routes.admin_routes import PanelDB
            panels_db = db.query(PanelDB).all()
            
            # تبدیل به دیکشنری با توکن کامل
            panels = []
            for p in panels_db:
                panels.append({
                    "id": p.id,
                    "name": p.name,
                    "url": p.url,
                    "api_token": p.api_token,  # ✅ توکن کامل
                    "sub_url": p.sub_url,
                    "is_active": p.is_active
                })
            
            db.close()
            
            logger.info(f"Searching for user '{username}' in {len(panels)} panels")

            for panel in panels:
                try:
                    panel_url = panel.get("url", "").rstrip("/")
                    api_token = panel.get("api_token", "")

                    if not panel_url or not api_token:
                        logger.warning(f"Panel {panel.get('name')} has missing URL or API token")
                        continue

                    logger.info(f"Checking panel: {panel.get('name')} (ID: {panel.get('id')})")
                    logger.info(f"   URL: {panel_url}")
                    logger.info(f"   Token: {api_token[:10]}...{api_token[-5:]}")

                    headers = {
                        "accept": "application/json",
                        "Authorization": f"Bearer {api_token}",
                        "User-Agent": "curl/7.81.0"
                    }

                    clients_url = f"{panel_url}/panel/api/clients/list"

                    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                        resp = await client.get(clients_url, headers=headers)

                        if resp.status_code != 200:
                            logger.warning(f"Panel {panel.get('name')} returned status {resp.status_code}")
                            logger.warning(f"   Response: {resp.text[:200]}")
                            continue

                        result_data = resp.json()

                        clients = []
                        if isinstance(result_data, dict):
                            if result_data.get("success") and result_data.get("obj"):
                                clients = result_data.get("obj", [])
                            elif result_data.get("clients"):
                                clients = result_data.get("clients", [])

                        logger.info(f"Found {len(clients)} clients in panel {panel.get('name')}")

                        for client_obj in clients:
                            client_email = client_obj.get("email", "")

                            if client_email and client_email.lower() == username.lower():
                                logger.info(f"✅ Found user '{username}' in panel {panel.get('name')}")

                                # ====== اطلاعات اصلی کاربر ======
                                client_id = client_obj.get("id")
                                client_uuid = client_obj.get("uuid")
                                sub_id = client_obj.get("subId")
                                enable = client_obj.get("enable", False)
                                limit_ip = client_obj.get("limitIp", 0)
                                tg_id = client_obj.get("tgId", 0)
                                created_at = client_obj.get("createdAt", 0)

                                # ====== اطلاعات ترافیک ======
                                traffic = client_obj.get("traffic", {})
                                
                                # حجم کل
                                total_bytes = client_obj.get("totalGB", 0)
                                if total_bytes == 0:
                                    total_bytes = traffic.get("total", 0)
                                
                                # حجم مصرفی
                                used_bytes = client_obj.get("usedTraffic", 0)
                                if used_bytes == 0:
                                    up = traffic.get("up", 0)
                                    down = traffic.get("down", 0)
                                    used_bytes = up + down
                                
                                # تاریخ انقضا
                                expiry_time = client_obj.get("expiryTime", 0)
                                if expiry_time == 0:
                                    expiry_time = traffic.get("expiryTime", 0)
                                
                                expiry_date = None
                                if expiry_time and expiry_time > 0:
                                    expiry_date = datetime.fromtimestamp(expiry_time / 1000)
                                
                                # تشخیص نامحدود
                                is_unlimited = total_bytes == 0
                                
                                # محاسبه حجم باقی‌مانده
                                remaining_bytes = 0
                                if total_bytes > 0:
                                    remaining_bytes = max(0, total_bytes - used_bytes)

                                client_dict = {
                                    "email": client_email,
                                    "totalGB": total_bytes,
                                    "usedGB": used_bytes,
                                    "usedTraffic": used_bytes,
                                    "remainingGB": remaining_bytes,
                                    "enable": enable,
                                    "expiryTime": expiry_time,
                                    "expiry_date": expiry_date,
                                    "used_gb": used_bytes / 1073741824 if total_bytes > 0 else 0,
                                    "total_gb": total_bytes / 1073741824 if total_bytes > 0 else 0,
                                    "remaining_gb": remaining_bytes / 1073741824 if total_bytes > 0 else 0,
                                    "subId": sub_id,
                                    "uuid": client_uuid or client_id,
                                    "limitIp": limit_ip,
                                    "tgId": tg_id,
                                    "is_unlimited": is_unlimited,
                                    "created_at": created_at
                                }

                                logger.info(f"📊 User data extracted:")
                                logger.info(f"   Email: {client_email}")
                                logger.info(f"   Total: {total_bytes} bytes ({total_bytes/1073741824:.2f} GB)")
                                logger.info(f"   Used: {used_bytes} bytes ({used_bytes/1073741824:.2f} GB)")
                                logger.info(f"   Remaining: {remaining_bytes} bytes ({remaining_bytes/1073741824:.2f} GB)")
                                logger.info(f"   Expiry: {expiry_date}")
                                logger.info(f"   Unlimited: {is_unlimited}")

                                return {
                                    "email": client_email,
                                    "panel": panel,
                                    "client": client_dict,
                                    "is_unlimited": is_unlimited
                                }

                except Exception as e:
                    logger.error(f"Error checking panel {panel.get('name')}: {str(e)}")
                    continue

            logger.warning(f"User '{username}' not found in any panel")
            return None

        except Exception as e:
            logger.error(f"Error finding user: {str(e)}")
            return None
        
    # ============================================================
    # OTHER HANDLERS
    # ============================================================
    async def handle_test_account(self, query) -> None:
        """Handle test account menu."""
        user_id = query.from_user.id
        logger.info(f"Test account menu requested by user: {user_id}")
        
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🧪 دریافت اکانت تست",
                    callback_data="get_test_account",
                    style="primary"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 راهنمای اتصال",
                    callback_data="connection_guide"
                ),
                InlineKeyboardButton(
                    text="🆘 پشتیبانی",
                    callback_data="support"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ]
        ]
        
        await query.edit_message_text(
            text="🧪 **اکانت تست**\n\nلطفاً یکی از گزینه‌ها را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_get_test_account(self, query) -> None:
        """Handle get test account - show categories."""
        user_id = query.from_user.id
        logger.info(f"Get test account requested by user: {user_id}")

        # بررسی محدودیت
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/admin/api/test-accounts/check/{user_id}"
            )
            check_data = response.json()

        if check_data.get("status") == "success":
            data = check_data.get("data", {})
            if not data.get("can_get"):
                if data.get("reason") == "disabled":
                    await query.edit_message_text(
                        "❌ **اکانت تست غیرفعال است**\n\n"
                        "لطفاً با پشتیبانی تماس بگیرید.",
                        parse_mode="Markdown",
                        reply_markup=self.keyboard_builder.create_main_menu()
                    )
                    return
                else:
                    await query.edit_message_text(
                        f"❌ **شما به سقف مجاز اکانت تست رسیده‌اید!**\n\n"
                        f"📊 تعداد مجاز: {data.get('total')} بار در هفته\n"
                        f"📅 شروع هفته: {data.get('week_start')}\n\n"
                        f"لطفاً هفته آینده مجدداً تلاش کنید.",
                        parse_mode="Markdown",
                        reply_markup=self.keyboard_builder.create_main_menu()
                    )
                    return

        # نمایش دسته‌بندی‌ها
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/public/categories")
            data = response.json()

        if data.get("status") != "success":
            await query.edit_message_text(
                "❌ خطا در دریافت دسته‌بندی‌ها.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return

        categories = data.get("data", [])

        keyboard = []
        for cat in categories:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"📂 {cat['name']}",
                    callback_data=f"test_category_{cat['id']}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                text="🔙 بازگشت",
                callback_data="test_account",
                style="danger"
            )
        ])

        await query.edit_message_text(
            text="🧪 **دریافت اکانت تست**\n\n"
                 "لطفاً یک دسته‌بندی را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    async def handle_test_category_selection(self, query, category_id: int) -> None:
        """Handle test category selection - show panels."""
        user_id = query.from_user.id
        logger.info(f"Test category {category_id} selected by user {user_id}")

        # دریافت سرویس‌های این دسته برای پیدا کردن پنل‌ها
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/admin/api/public/services?category_id={category_id}"
            )
            data = response.json()

        services = data.get("data", []) if data.get("status") == "success" else []

        # استخراج پنل‌های یکتا
        panels_dict = {}
        for service in services:
            if service.get('panel_id') and service.get('panel_name'):
                panels_dict[service['panel_id']] = service['panel_name']

        if not panels_dict:
            await query.edit_message_text(
                "❌ هیچ پنلی برای این دسته‌بندی یافت نشد.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return

        keyboard = []
        for panel_id, panel_name in panels_dict.items():
            keyboard.append([
                InlineKeyboardButton(
                    text=f"🖥️ {panel_name}",
                    callback_data=f"test_panel_{panel_id}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                text="🔙 بازگشت",
                callback_data="get_test_account",
                style="danger"
            )
        ])

        await query.edit_message_text(
            text="🖥️ **انتخاب پنل**\n\n"
                 "لطفاً پنل مورد نظر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    async def handle_test_panel_selection(self, query, panel_id: int) -> None:
        """Handle test panel selection - create test account."""
        user_id = query.from_user.id
        username = query.from_user.username or "unknown"
        logger.info(f"Test panel {panel_id} selected by user {user_id}")

        # ساخت اکانت تست
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.API_BASE_URL}/admin/api/test-accounts/create",
                json={
                    "user_id": user_id,
                    "username": username,
                    "panel_id": panel_id
                }
            )
            data = response.json()

        if data.get("status") != "success":
            await query.edit_message_text(
                f"❌ {data.get('message', 'خطا در ساخت اکانت تست')}",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return

        test_data = data.get("data", {})

        message = (
            f"🎉 **اکانت تست شما آماده است!**\n\n"
            f"📧 **یوزرنیم:** `{test_data['client_email']}`\n"
            f"🖥️ **پنل:** {test_data['panel_name']}\n"
            f"📊 **حجم:** {test_data['volume_mb']} MB\n"
            f"⏰ **مدت:** {test_data['duration_days']} روز\n\n"
            f"🔗 **لینک سابسکریپشن:**\n"
            f"`{test_data['sub_url']}`\n\n"
            f"⚠️ **توجه:** این یک اکانت تست است!"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    text="🏠 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ]
        ]

        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_subordinates(self, query) -> None:
        """Handle subordinates list request - show referral info."""
        user_id = query.from_user.id
        logger.info(f"Subordinates requested by user: {user_id}")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/referrals/stats/{user_id}"
                )
                data = response.json()
            
            if data.get("status") != "success":
                await query.edit_message_text(
                    "❌ خطا در دریافت اطلاعات رفرال.",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
                return
            
            stats = data.get("data", {})
            referral_link = stats.get("referral_link", "")
            total_referrals = stats.get("total_referrals", 0)
            active_count = stats.get("active_count", 0)
            active_users = stats.get("active_users", [])
            discount = stats.get("discount", {})
            total_percent = discount.get("total_percent", 0)
            used_percent = discount.get("used_percent", 0)
            remaining_percent = discount.get("remaining_percent", 0)
            min_redeem_percent = stats.get("min_redeem_percent", 100)
            
            message_lines = [
                "👥 **زیرمجموعه‌های شما**",
                "",
                f"🔗 **لینک دعوت شما:**",
                f"`{referral_link}`",
                "",
                "─" * 30,
                "",
                "📊 **آمار:**",
                f"   • تعداد کل معرفی: `{total_referrals} نفر`",
                f"   • کاربران فعال: `{active_count} نفر`",
                "",
                "🎁 **اعتبار تخفیف:**",
                f"   • جمع کل: `{total_percent}%`",
                f"   • استفاده شده: `{used_percent}%`",
                f"   • باقی‌مانده: `{remaining_percent}%`",
                f"   • حداقل برای استفاده: `{min_redeem_percent}%`",
                "",
            ]
            
            if remaining_percent >= min_redeem_percent:
                message_lines.append(f"✅ شما می‌توانید از تخفیف خود استفاده کنید!")
            else:
                message_lines.append(f"⚠️ برای استفاده از تخفیف، باید حداقل {min_redeem_percent}% اعتبار داشته باشید.")
            
            message_lines.append("")
            
            if active_users:
                message_lines.append("📋 **لیست کاربران فعال:**")
                for i, active_user in enumerate(active_users[:10]):
                    user_id_str = active_user.get("user_id", "نامشخص")
                    message_lines.append(f"   {i+1}. کاربر {user_id_str} - ✅ فعال")
            else:
                message_lines.append("📋 **لیست کاربران فعال:**")
                message_lines.append("   هنوز کاربر فعالی ندارید.")
            
            message = "\n".join(message_lines)
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="📋 کپی لینک دعوت",
                        copy_text={"text": referral_link},
                        style="primary"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📤 اشتراک‌گذاری",
                        switch_inline_query=referral_link,
                        style="success"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 بازگشت به منو",
                        callback_data="main_menu",
                        style="danger"
                    )
                ]
            ]
            
            await query.edit_message_text(
                text=message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Error in handle_subordinates: {str(e)}")
            await query.edit_message_text(
                "❌ خطا در دریافت اطلاعات.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            
            
    async def handle_help(self, query) -> None:
        """Handle help request."""
        user_id = query.from_user.id
        logger.info(f"Help requested by user: {user_id}")
        
        # ====== ✅ Get help message from settings ======
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/settings/messages")
            msg_settings = response.json().get("data", {})
        
        help_text = msg_settings.get("help_message", "❓ **راهنما**")

        try:
            await query.edit_message_text(text=help_text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())
        except BadRequest:
            await query.message.reply_text(text=help_text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())

    async def handle_support(self, query) -> None:
        """Handle support request."""
        user_id = query.from_user.id
        logger.info(f"Support requested by user: {user_id}")
        # ====== ✅ Get support message from settings ======
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/settings/messages")
            msg_settings = response.json().get("data", {})
        
        support_text = msg_settings.get("support_message", "🆘 **پشتیبانی**")
        try:
            await query.edit_message_text(text=support_text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())
        except BadRequest:
            await query.message.reply_text(text=support_text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())

    async def show_main_menu(self, query) -> None:
        """Show main menu."""
        user_id = query.from_user.id
        logger.info(f"Main menu shown to user: {user_id}")
        text = "📋 **منوی اصلی**\n\nلطفاً یکی از گزینه‌ها را انتخاب کنید:"
        try:
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_main_menu())
        except BadRequest:
            await query.message.reply_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_main_menu())

    async def handle_wallet(self, query) -> None:
        """Handle wallet request."""
        user_id = query.from_user.id
        logger.info(f"Wallet requested by user: {user_id}")
        text = "💰 **کیف پول**\n\nموجودی کیف پول شما: **0 تومان**\n\nبرای شارژ کیف پول، از طریق پشتیبانی اقدام کنید."
        try:
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_service_menu())
        except BadRequest:
            await query.message.reply_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_service_menu())

    async def handle_connection_guide(self, query) -> None:
        """Handle connection guide request."""
        user_id = query.from_user.id
        logger.info(f"Connection guide requested by user: {user_id}")
        text = (
            "📖 **راهنمای اتصال**\n\n"
            "1️⃣ ابتدا سرویس مورد نظر را خریداری کنید\n"
            "2️⃣ از بخش 'وضعیت من' اطلاعات اتصال را دریافت کنید\n"
            "3️⃣ از نرم‌افزارهای زیر استفاده کنید:\n"
            "   • Windows: v2rayN / Nekoray\n"
            "   • Android: V2RayNG\n"
            "   • iOS: Shadowrocket\n"
            "   • macOS: V2RayX / Nekoray\n\n"
            "🔗 لینک‌های دانلود:\n"
            "• v2rayNG: [لینک]\n"
            "• Shadowrocket: [لینک]"
        )
        try:
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_service_menu())
        except BadRequest:
            await query.message.reply_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_service_menu())


    async def handle_online_payment(self, query, service_id: int, is_renewal: bool = False):
        """Handle online payment for service."""
        user_id = query.from_user.id

        # دریافت اطلاعات سرویس
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/services")
            data = response.json()

        service = None
        if data.get("status") == "success":
            for s in data.get("data", []):
                if s["id"] == service_id:
                    service = s
                    break

        if not service:
            await query.edit_message_text(
                "❌ سرویس پیدا نشد.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return

        # ====== دریافت قیمت نهایی از discount_state ======
        amount = service.get("price", 0)
        discount_percent = 0
        
        if user_id in self._discount_state:
            discount_state = self._discount_state[user_id]
            if discount_state.get("discount_applied"):
                amount = discount_state.get("final_price", service.get("price", 0))
                discount_percent = discount_state.get("accumulated_discount", 0)
            else:
                amount = discount_state.get("original_price", service.get("price", 0))
        elif not is_renewal and hasattr(self, '_pending_purchases') and user_id in self._pending_purchases:
            pending_data = self._pending_purchases[user_id]
            service_details = pending_data.get('service_details', {})
            amount = service_details.get('price', service.get('price', 0))
            discount_percent = service_details.get('discount_percent', 0)

        # ====== برای تمدید، اطلاعات کاربر رو بگیر ======
        renewal_info = None
        if is_renewal:
            if hasattr(self, '_renew_selected_service') and user_id in self._renew_selected_service:
                renewal_data = self._renew_selected_service[user_id]
                user_info = renewal_data.get('user_info')
                if user_info:
                    client_data = user_info.get('client', {})
                    expiry_date = client_data.get('expiry_date')
                    
                    if expiry_date:
                        if isinstance(expiry_date, datetime):
                            client_data['expiry_date'] = expiry_date.isoformat()
                        elif hasattr(expiry_date, 'isoformat'):
                            client_data['expiry_date'] = expiry_date.isoformat()
                        else:
                            client_data['expiry_date'] = str(expiry_date)
                    
                    renewal_info = {
                        "email": user_info.get('email'),
                        "panel": user_info.get('panel', {}),
                        "client": client_data
                    }

        # ساخت پرداخت
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.API_BASE_URL}/admin/api/payment/create",
                json={
                    "user_id": user_id,
                    "service_id": service_id,
                    "amount": amount,
                    "payment_type": "renewal" if is_renewal else "new_purchase",
                    "is_renewal": is_renewal,
                    "renewal_info": renewal_info
                }
            )
            payment_result = response.json()

        if payment_result.get("status") != "success":
            await query.edit_message_text(
                f"❌ {payment_result.get('message', 'خطا در ساخت پرداخت')}",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return
        
                # ====== Apply recurring discount for referrer ======
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.API_BASE_URL}/admin/api/referrals/apply-recurring",
                json={"user_id": user_id}
            )
            
        payment_url = payment_result["data"]["payment_url"]

        keyboard = [
            [
                InlineKeyboardButton(
                    text="💳 رفتن به درگاه پرداخت",
                    url=payment_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ]
        ]

        # پیام با اطلاعات تخفیف
        if discount_percent > 0:
            message_text = (
                f"💳 **پرداخت آنلاین**\n\n"
                f"🎁 **تخفیف اعمال شده:** {discount_percent}%\n"
                f"💰 **مبلغ نهایی:** {amount:,} تومان\n\n"
                f"برای پرداخت روی دکمه زیر کلیک کنید:"
            )
        else:
            message_text = (
                f"💳 **پرداخت آنلاین**\n\n"
                f"مبلغ: {amount:,} تومان\n\n"
                f"برای پرداخت روی دکمه زیر کلیک کنید:"
            )

        await query.edit_message_text(
            text=message_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        
    async def handle_purchase(self, query, service_id: int) -> None:
        """Handle purchase of a service - show payment options with discount toggle."""
        user_id = query.from_user.id
        logger.info(f"Purchase requested by user {user_id} for service {service_id}")
        
        # ====== Check if user is a sales partner ======
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/check/{user_id}")
            partner_data = response.json().get("data", {})
        
        if partner_data.get("is_partner"):
            # Partner - direct purchase without payment
            await self.handle_partner_purchase(query, service_id, partner_data)
            return
        

        try:
            # Get service details
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/public/services"
                )
                data = response.json()

            service = None
            if data.get("status") == "success":
                for s in data.get("data", []):
                    if s["id"] == service_id:
                        service = s
                        break

            if not service:
                await query.edit_message_text(
                    text="❌ سرویس مورد نظر پیدا نشد.",
                    reply_markup=self._get_back_to_categories_keyboard()
                )
                return

            # ====== Check for referral discount (just check, don't auto-apply) ======
            referral_discount = 0
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Check if user has unused referral
                response = await client.post(
                    f"{settings.API_BASE_URL}/admin/api/referrals/check",
                    json={"user_id": user_id}
                )
                check_data = response.json()
                if check_data.get("status") == "success":
                    referral_discount = check_data.get("data", {}).get("discount_percent", 0)

            # ====== Get user's accumulated discount credit ======
            accumulated_discount = 0
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/referrals/stats/{user_id}"
                )
                stats_data = response.json().get("data", {})
                accumulated_discount = stats_data.get("discount", {}).get("remaining_percent", 0)

            # Calculate total available discount
            total_available_discount = referral_discount + accumulated_discount
            
            # Original price
            original_price = service.get('price', 0)

            # Store state
            self._discount_state[user_id] = {
                "service_id": service_id,
                "is_renewal": False,
                "discount_applied": False,
                "original_price": original_price,
                "accumulated_discount": total_available_discount,  # جمع هر دو تخفیف
                "referral_discount": referral_discount,
                "accumulated_only": accumulated_discount
            }

            # Get payment settings
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.API_BASE_URL}/admin/api/settings/payment")
                payment_settings = response.json().get("data", {})

            # Build message
            card_numbers = payment_settings.get("card_numbers", [])
            cards_text = ""
            if card_numbers:
                cards_text = "\n".join([
                    f"   • {card.get('number', '')} | {card.get('holder', '')}"
                    for card in card_numbers
                ])

            price_text = f"{original_price:,} تومان" if original_price else "تماس بگیرید"
            volume_text = f"{service['volume']} GB" if service['volume'] else "نامحدود"
            duration_text = f"{service['duration']} ماه" if service['duration'] else "متغیر"

            message_lines = [
                f"🛒 **تأیید خرید سرویس**",
                "",
                f"📦 **{service['name']}**",
                f"📊 **حجم:** {volume_text}",
                f"⏱️ **مدت:** {duration_text}",
                f"💰 **قیمت:** {price_text}",
                f"🖥️ **پنل:** {service.get('panel_name', 'نامشخص')}",
                "",
                "---",
                "",
                "لطفاً یکی از روش‌های پرداخت را انتخاب کنید:"
            ]
            
            if payment_settings.get("receipt_payment_enabled") and cards_text:
                message_lines.append("")
                message_lines.append("💳 **شماره کارت:**")
                message_lines.append(cards_text)
                message_lines.append("")
                message_lines.append("📌 مبلغ را کارت به کارت کنید و رسید را ارسال کنید.")


            payment_message = "\n".join(message_lines)

            # Build keyboard
            keyboard = []

            # Discount toggle button
            if total_available_discount > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"🎁 استفاده از تخفیف ({total_available_discount}%)",
                        callback_data=f"toggle_discount_{service_id}_False",
                        style="success"
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        text="🎁 تخفیف ندارید",
                        callback_data="noop"
                    )
                ])

            if payment_settings.get("online_payment_enabled"):
                keyboard.append([
                    InlineKeyboardButton(
                        text="💳 پرداخت آنلاین",
                        callback_data=f"online_pay_{service_id}",
                        style="primary"
                    )
                ])

            if payment_settings.get("receipt_payment_enabled"):
                keyboard.append([
                    InlineKeyboardButton(
                        text="📤 ارسال رسید پرداخت",
                        callback_data=f"send_receipt_{service_id}"
                    )
                ])

            keyboard.append([
                InlineKeyboardButton(
                    text="🔙 بازگشت به سرویس‌ها",
                    callback_data=f"category_{service['category_id']}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    text="🏠 بازگشت به منو",
                    callback_data="main_menu",
                    style="danger"
                )
            ])

            # Store purchase context
            context_data = {
                "service_id": service_id,
                "service_name": service['name'],
                "service_details": {
                    "volume": service.get('volume'),
                    "duration": service.get('duration'),
                    "price": original_price,  # قیمت اصلی - تخفیف بعداً اعمال میشه
                    "original_price": original_price,
                    "discount_percent": total_available_discount,
                    "panel_name": service.get('panel_name'),
                    "panel_id": service.get('panel_id'),
                    "inbound_id": service.get('inbound_id')
                }
            }

            self._pending_purchases[user_id] = context_data

            await query.edit_message_text(
                text=payment_message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in handle_purchase: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در پردازش خرید. لطفاً مجدداً تلاش کنید.",
                reply_markup=self._get_back_to_categories_keyboard()
            )
            

    async def handle_toggle_discount(self, query, service_id: int, is_renewal: bool) -> None:
        """Handle toggling discount on/off."""
        user_id = query.from_user.id
        logger.info(f"Toggle discount requested by user {user_id} for service {service_id} (renewal: {is_renewal})")
        
        if user_id not in self._discount_state:
            await query.answer("خطا در اطلاعات تخفیف", show_alert=True)
            return
        
        discount_state = self._discount_state[user_id]
        
        discount_state["discount_applied"] = not discount_state["discount_applied"]
       
        if discount_state["discount_applied"] and not is_renewal:
            # Apply referral discount (mark as used)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.API_BASE_URL}/admin/api/referrals/apply",
                    json={"user_id": user_id}
                )
                apply_result = response.json()
                logger.info(f"Apply referral result: {apply_result}")

        original_price = discount_state.get("original_price", 0)
        accumulated_discount = discount_state.get("accumulated_discount", 0)
        referral_discount = discount_state.get("referral_discount", 0)
        
        if is_renewal:
            service = None
            if hasattr(self, '_renew_selected_service') and user_id in self._renew_selected_service:
                service = self._renew_selected_service[user_id].get('service')
            
            if not service:
                await query.answer("خطا در اطلاعات سرویس", show_alert=True)
                return
            
            username = self._renew_selected_service[user_id].get('user_info', {}).get('email', '')
            volume = service.get('volume') or "نامحدود"
            duration = service.get('duration', 1)
            panel_name = service.get('panel_name', 'نامشخص')
            
            if discount_state["discount_applied"]:
                final_price = int(original_price * (100 - accumulated_discount) / 100)
                
                message_lines = [
                    f"🔄 **تمدید سرویس**",
                    "",
                    f"👤 کاربر: `{username}`",
                    f"📦 **سرویس:** {service['name']}",
                    f"📊 **حجم:** {volume} GB",
                    f"⏱️ **مدت:** {duration} ماه",
                    f"💰 **قیمت اصلی:** {original_price:,} تومان",
                    f"🎁 **تخفیف:** {accumulated_discount}%",
                    f"💰 **قیمت نهایی:** {final_price:,} تومان ✅",
                    f"🖥️ **پنل:** {panel_name}",
                    "",
                    f"---",
                    f"",
                    f"لطفاً یکی از روش‌های پرداخت را انتخاب کنید:"
                ]
            else:
                message_lines = [
                    f"🔄 **تمدید سرویس**",
                    "",
                    f"👤 کاربر: `{username}`",
                    f"📦 **سرویس:** {service['name']}",
                    f"📊 **حجم:** {volume} GB",
                    f"⏱️ **مدت:** {duration} ماه",
                    f"💰 **قیمت:** {original_price:,} تومان",
                    f"🖥️ **پنل:** {panel_name}",
                    "",
                    f"---",
                    f"",
                    f"لطفاً یکی از روش‌های پرداخت را انتخاب کنید:"
                ]
        else:
            # برای خرید جدید
            service = None
            if user_id in self._pending_purchases:
                pending_data = self._pending_purchases[user_id]
                service_name = pending_data.get('service_name', '')
                service_details = pending_data.get('service_details', {})
                volume = service_details.get('volume') or "نامحدود"
                duration = service_details.get('duration', 1)
                panel_name = service_details.get('panel_name', 'نامشخص')
                original_price_full = service_details.get('original_price', original_price)
                referral_discount = service_details.get('discount_percent', 0)
                
                if discount_state["discount_applied"]:
                    final_price = int(original_price * (100 - accumulated_discount) / 100)
                    
                    message_lines = [
                        f"🛒 **تأیید خرید سرویس**",
                        "",
                        f"📦 **{service_name}**",
                        f"📊 **حجم:** {volume}",
                        f"⏱️ **مدت:** {duration} ماه",
                    ]
                    
                    message_lines.append(f"💰 **قیمت اصلی:** {original_price:,} تومان")
                    message_lines.append(f"🎁 **تخفیف:** {discount_state['accumulated_discount']}%")
                    message_lines.append(f"💰 **قیمت نهایی:** {final_price:,} تومان ✅")
                    
                    message_lines.append(f"🖥️ **پنل:** {panel_name}")
                    message_lines.append("")
                    message_lines.append("---")
                    message_lines.append("")
                    message_lines.append("لطفاً یکی از روش‌های پرداخت را انتخاب کنید:")
                else:
                    message_lines = [
                        f"🛒 **تأیید خرید سرویس**",
                        "",
                        f"📦 **{service_name}**",
                        f"📊 **حجم:** {volume}",
                        f"⏱️ **مدت:** {duration} ماه",
                    ]
                    
                    message_lines.append(f"💰 **قیمت:** {original_price:,} تومان")
                    message_lines.append(f"🖥️ **پنل:** {panel_name}")
                    message_lines.append("")
                    message_lines.append("---")
                    message_lines.append("")
                    message_lines.append("لطفاً یکی از روش‌های پرداخت را انتخاب کنید:")
        
        message = "\n".join(message_lines)
        
        # دریافت تنظیمات پرداخت
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/settings/payment")
            payment_settings = response.json().get("data", {})
        
        # ساخت کیبورد
        keyboard = []
        
        # دکمه تخفیف
        if discount_state["discount_applied"]:
            keyboard.append([
                InlineKeyboardButton(
                    text="❌ لغو تخفیف",
                    callback_data=f"toggle_discount_{service_id}_{is_renewal}",
                    style="danger"
                )
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"🎁 استفاده از تخفیف ({accumulated_discount}%)",
                    callback_data=f"toggle_discount_{service_id}_{is_renewal}",
                    style="success"
                )
            ])
        
        # دکمه پرداخت آنلاین با قیمت نهایی
        if payment_settings.get("online_payment_enabled"):
            if discount_state["discount_applied"]:
                final_price = int(original_price * (100 - accumulated_discount) / 100)
                button_text = f"💳 پرداخت آنلاین ({final_price:,} تومان)"
            else:
                button_text = f"💳 پرداخت آنلاین ({original_price:,} تومان)"
            
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"online_pay_{service_id}" if not is_renewal else f"renew_online_pay_{service_id}",
                    style="primary"
                )
            ])
        
        # دکمه ارسال رسید
        if payment_settings.get("receipt_payment_enabled"):
            keyboard.append([
                InlineKeyboardButton(
                    text="📤 ارسال رسید پرداخت",
                    callback_data=f"send_receipt_{service_id}" if not is_renewal else f"renew_send_receipt_{service_id}"
                )
            ])
        
        # دکمه بازگشت
        if is_renewal:
            keyboard.append([
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="renew_back_to_services"
                )
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="main_menu"
                )
            ])
        
        # ذخیره قیمت نهایی در state
        if discount_state["discount_applied"]:
            final_price = int(original_price * (100 - accumulated_discount) / 100)
            discount_state["final_price"] = final_price
        else:
            discount_state["final_price"] = original_price
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    async def handle_check_membership(self, query) -> None:
        """Handle check membership button."""
        user_id = query.from_user.id

        # چک عضویت
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/admin/api/check-membership/{user_id}"
            )
            membership_data = response.json()

        if membership_data.get("status") == "success":
            data = membership_data.get("data", {})
            is_member = data.get("is_member", False)

            if is_member:
                # ✅ عضو شده - نمایش منوی اصلی
                user = query.from_user
                await query.edit_message_text(
                    f"✅ **عضویت شما تأیید شد!**\n\n"
                    f"👋 سلام {user.first_name} عزیز!\n"
                    f"به ربات مدیریت سرویس‌ها خوش آمدید.\n\n"
                    f"لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                    parse_mode="Markdown",
                    reply_markup=self.keyboard_builder.create_main_menu()
                )
            else:
                # ❌ هنوز عضو نشده
                await query.answer(
                    "❌ هنوز عضو نشده‌اید! لطفاً عضو کانال شوید.",
                    show_alert=True
                )
        else:
            await query.answer("خطا در بررسی عضویت", show_alert=True)


    async def handle_sales_partner(self, query) -> None:
        """Handle sales partner button."""
        user_id = query.from_user.id
        logger.info(f"Sales partner requested by user: {user_id}")
        
        # Check if user is a partner
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/admin/api/sales/check/{user_id}"
            )
            data = response.json()
        
        if data.get("status") == "success" and data.get("data", {}).get("is_partner"):
            # Already a partner - show partner panel
            partner_data = data["data"]
            
            message = (
                f"🤝 **پنل همکاری در فروش**\n\n"
                f"📊 **وضعیت:**\n"
                f"   • محدودیت: {partner_data['max_purchases']} اکانت\n"
                f"   • استفاده شده: {partner_data['used_purchases']}\n"
                f"   • باقی‌مانده: {partner_data['remaining_purchases']}\n"
                f"   • تخفیف: {partner_data['discount_percent']}%\n\n"
                f"یکی از گزینه‌های زیر را انتخاب کنید:"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("🛒 خرید سرویس", callback_data="sales_purchase", style="success"),
                    InlineKeyboardButton("🔄 تمدید سرویس", callback_data="sales_renew", style="success")
                ],
                [
                    InlineKeyboardButton("📊 وضعیت کاربر", callback_data="sales_status_check"),
                    InlineKeyboardButton("📋 لیست اکانت‌ها", callback_data="sales_list_accounts")
                ],
                [
                    InlineKeyboardButton("⛔ غیرفعال‌سازی", callback_data="sales_deactivate", style="danger"),
                    InlineKeyboardButton("✅ فعال‌سازی", callback_data="sales_activate", style="success")
                ],
                [
                    InlineKeyboardButton("💰 تسویه حساب", callback_data="sales_settlement", style="primary")
                ],
                [
                    InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")
                ]
            ]
            
            await query.edit_message_text(
                text=message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Not a partner - show info and register button
            message = (
                f"🤝 **همکاری در فروش**\n\n"
                f"📋 **شرایط همکاری:**\n"
                f"• مناسب برای خرید عمده\n"
                f"• تسویه حساب به صورت هفتگی\n"
                f"• تخفیف ویژه برای همکاران\n"
                f"• محدودیت تعداد اکانت توسط ادمین تعیین می‌شود\n\n"
                f"برای ثبت درخواست روی دکمه زیر کلیک کنید:"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📝 ثبت درخواست",
                        callback_data="sales_register_request",
                        style="primary"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت به منو",
                        callback_data="main_menu"
                    )
                ]
            ]
            
            await query.edit_message_text(
                text=message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


    async def handle_sales_register_request(self, query) -> None:
        """Handle sales partner registration request."""
        user_id = query.from_user.id
        user = query.from_user
        username = user.username or "نامشخص"
        first_name = user.first_name or "کاربر"
        
        # Create request
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.API_BASE_URL}/admin/api/sales/request",
                json={
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name
                }
            )
            result = response.json()
        
        if result.get("status") != "success":
            await query.edit_message_text(
                f"❌ {result.get('message', 'خطا در ثبت درخواست')}",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return
        
        message = (
            f"📝 **درخواست همکاری در فروش**\n\n"
            f"👤 **اطلاعات شما:**\n"
            f"   • ID تلگرام: `{user_id}`\n"
            f"   • نام کاربری: @{username}\n"
            f"   • نام: {first_name}\n\n"
            f"📋 **درخواست:** همراهی در فروش\n\n"
            f"برای تکمیل درخواست، روی دکمه زیر کلیک کنید:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "📤 ارسال به پشتیبانی",
                    callback_data="sales_send_to_support",
                    style="primary"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="sales_partner"
                )
            ]
        ]
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_sales_send_to_support(self, query) -> None:
        """Send sales request to support."""
        user_id = query.from_user.id
        user = query.from_user
        username = user.username or "نامشخص"
        first_name = user.first_name or "کاربر"
        
        # Send message to support
        support_message = (
            f"📝 **درخواست همکاری در فروش**\n\n"
            f"👤 ID: `{user_id}`\n"
            f"📧 Username: @{username}\n"
            f"📋 Name: {first_name}\n"
            f"🤝 درخواست همراهی در فروش"
        )
        
        try:
            from api.routes.webhook import application
            # Send to support chat (you need to set support_chat_id)
            support_chat_id = "-1001882797591"  # کانال یا ادمین
            await application.bot.send_message(
                chat_id=support_chat_id,
                text=support_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error sending to support: {str(e)}")
        
        await query.edit_message_text(
            f"✅ **درخواست شما ارسال شد!**\n\n"
            f"اطلاعات شما برای پشتیبانی ارسال شد.\n"
            f"برای ادامه گفتگو به پشتیبانی مراجعه کنید:\n\n"
            f"🆘 @shell_man",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🆘 رفتن به پشتیبانی", url="https://t.me/shell_man")
                ],
                [
                    InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")
                ]
            ])
        )

    async def handle_sales_purchase(self, query) -> None:
        """Handle sales partner purchase - show categories."""
        user_id = query.from_user.id
        logger.info(f"Sales purchase requested by user: {user_id}")
        
        # Check remaining purchases
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/check/{user_id}")
            data = response.json()
        
        partner_data = data.get("data", {})
        remaining = partner_data.get("remaining_purchases", 0)
        
        if remaining <= 0:
            await query.edit_message_text(
                "❌ **سقف خرید شما تکمیل شده است**\n\n"
                "لطفاً با پشتیبانی تماس بگیرید.",
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return
        
        # Show categories (same as normal purchase)
        await self.handle_buy_service(query)

       
    async def handle_sales_list_accounts(self, query) -> None:
        """Show partner's accounts list."""
        user_id = query.from_user.id
        logger.info(f"Sales list accounts requested by user: {user_id}")
        
        # Get transactions
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/transactions/{user_id}")
            data = response.json()
        
        # Get partner info
        async with httpx.AsyncClient(timeout=10.0) as client:
            response2 = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/check/{user_id}")
            partner_data = response2.json().get("data", {})
        
        transactions = data.get("data", [])
        
        message_lines = [
            "📋 **لیست اکانت‌های شما**",
            "",
            f"📊 محدودیت: {partner_data.get('max_purchases', 0)} | استفاده شده: {partner_data.get('used_purchases', 0)} | باقی‌مانده: {partner_data.get('remaining_purchases', 0)}",
            "",
        ]
        
        if not transactions:
            message_lines.append("هنوز اکانتی خریداری نکرده‌اید.")
        else:
            for i, t in enumerate(transactions):
                type_icon = "🛒" if t["transaction_type"] == "purchase" else "🔄"
                type_text = "خرید" if t["transaction_type"] == "purchase" else "تمدید"
                settled = "✅" if t["is_settled"] else "⏳"
                message_lines.append(
                    f"{i+1}. {type_icon} `{t['client_email']}` | {t['service_name']} | {type_text} | {settled}"
                )
        
        message = "\n".join(message_lines)
        
        keyboard = [
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")
            ]
        ]
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        

    async def handle_sales_settlement(self, query) -> None:
        """Show settlement summary with payment button."""
        user_id = query.from_user.id
        logger.info(f"Settlement requested by user: {user_id}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/settlement/{user_id}")
            data = response.json()
        
        settlement = data.get("data", {})
        purchases = settlement.get("purchases", [])
        renewals = settlement.get("renewals", [])
        total = settlement.get("total_amount", 0)
        
        if total == 0:
            await query.edit_message_text(
                "💰 **تسویه حساب**\n\n"
                "✅ هیچ بدهی ندارید!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
            return
        
        message_lines = [
            "💰 **فاکتور تسویه حساب**",
            "",
        ]
        
        if purchases:
            message_lines.append("🛒 **خریدها:**")
            for p in purchases:
                message_lines.append(f"   • `{p['client_email']}` | {p['service_name']} | {p['price']:,} تومان")
        
        if renewals:
            message_lines.append("")
            message_lines.append("🔄 **تمدیدها:**")
            for r in renewals:
                message_lines.append(f"   • `{r['client_email']}` | {r['service_name']} | {r['price']:,} تومان")
        
        message_lines.append("")
        message_lines.append(f"📊 **جمع کل: {total:,} تومان**")
        
        message = "\n".join(message_lines)
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "💳 پرداخت آنلاین",
                    callback_data=f"sales_settle_pay_{total}",
                    style="primary"
                )
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")
            ]
        ]
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        

    async def handle_partner_purchase(self, query, service_id: int, partner_data: dict) -> None:
        """Direct purchase for sales partner."""
        user_id = query.from_user.id
        
        # Check remaining purchases
        remaining = partner_data.get("remaining_purchases", 0)
        
        if remaining <= 0:
            await query.edit_message_text(
                "❌ **سقف خرید شما تکمیل شده است**\n\n"
                "برای ادامه، ابتدا باید تسویه حساب کنید.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 تسویه حساب", callback_data="sales_settlement")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
            return
        
        # Get service details
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/public/services")
            data = response.json()
        
        service = None
        if data.get("status") == "success":
            for s in data.get("data", []):
                if s["id"] == service_id:
                    service = s
                    break
        
        if not service:
            await query.edit_message_text("❌ سرویس پیدا نشد", reply_markup=self.keyboard_builder.create_main_menu())
            return
        
        # Calculate discounted price
        original_price = service.get('price', 0)
        discount_percent = partner_data.get("discount_percent", 0)
        final_price = int(original_price * (100 - discount_percent) / 100) if discount_percent > 0 else original_price
        
        # Get panel info
        panel_id = service.get('panel_id')
        
        # Create user in panel directly
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.API_BASE_URL}/admin/api/sales/create-account",
                json={
                    "partner_user_id": user_id,
                    "service_id": service_id,
                    "price": final_price,
                    "original_price": original_price,
                    "discount_percent": discount_percent,
                    "transaction_type": "purchase"
                }
            )
            result = response.json()
        
        if result.get("status") != "success":
            await query.edit_message_text(
                f"❌ {result.get('message', 'خطا در ساخت اکانت')}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
            return
        
        # Show success
        account_data = result.get("data", {})
        
        message = (
            f"🎉 **اکانت با موفقیت ساخته شد!**\n\n"
            f"📧 **یوزرنیم:** `{account_data.get('client_email')}`\n"
            f"🖥️ **پنل:** {account_data.get('panel_name')}\n"
            f"📦 **سرویس:** {service.get('name')}\n"
            f"💰 **قیمت اصلی:** {original_price:,} تومان\n"
            f"🎁 **تخفیف:** {discount_percent}%\n"
            f"💰 **قیمت نهایی:** {final_price:,} تومان\n\n"
            f"📊 **محدودیت باقی‌مانده:** {account_data.get('remaining_purchases')}\n\n"
            f"🔗 **لینک سابسکریپشن:**\n`{account_data.get('sub_url')}`"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت به پنل همکاری", callback_data="sales_partner")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
           )


    async def handle_sales_renew(self, query) -> None:
        """Handle sales partner renewal - ask for username."""
        user_id = query.from_user.id
        logger.info(f"Sales renew requested by user: {user_id}")
        
        # Check remaining purchases
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/check/{user_id}")
            partner_data = response.json().get("data", {})
        
        remaining = partner_data.get("remaining_purchases", 0)
        
        if remaining <= 0:
            await query.edit_message_text(
                "❌ **سقف خرید شما تکمیل شده است**\n\n"
                "برای ادامه، ابتدا باید تسویه حساب کنید.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 تسویه حساب", callback_data="sales_settlement")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
            return
        
        # Mark user in renewal mode
        if not hasattr(self, '_renewing_users'):
            self._renewing_users = set()
        self._renewing_users.add(user_id)
        
        # Mark as sales partner renewal
        if not hasattr(self, '_sales_renewal_users'):
            self._sales_renewal_users = set()
        self._sales_renewal_users.add(user_id)
        
        message = (
            "🔄 **تمدید سرویس - همکاری**\n\n"
            "لطفاً یوزرنیم خود را وارد کنید.\n\n"
            "📌 **نحوه ورود:**\n"
            "• اگر از طریق پنل قبلی اکانت دارید: `acc` به همراه اعداد\n"
            "• اگر از طریق بات خرید کرده‌اید: `bot` به همراه اعداد\n\n"
        )
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=None
        )


    async def handle_sales_renew_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process username input for sales partner renewal."""
        user_id = update.effective_user.id
        username_input = update.message.text.strip()
        
        if not hasattr(self, '_sales_renewal_users') or user_id not in self._sales_renewal_users:
            return
        
        # ====== ✅ Check ownership first ======
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/transactions/{user_id}")
            transactions = response.json().get("data", [])
        
        # Check if this username belongs to partner
        owns_account = any(
            t.get("client_email", "").lower() == username_input.lower() 
            for t in transactions
        )
        
        if not owns_account:
            await update.message.reply_text(
                f"❌ **یوزرنیم `{username_input}` در لیست شما نیست!**\n\n"
                f"فقط می‌توانید اکانت‌هایی که خودتان خریده‌اید را تمدید کنید.\n\n",
                parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu", style="danger")]
                ])
            )
            return
        
        # ====== ✅ Find user in panels ======
        normalized_username = username_input.strip()
        user_info = await self._find_user_in_panels(normalized_username)
        
        if not user_info:
            await update.message.reply_text(
                f"❌ **یوزرنیم `{username_input}` پیدا نشد!**",
                parse_mode="Markdown"
            )
            return
        
        # User found - show services
        self._sales_renewal_users.remove(user_id)
        
        await self._show_sales_renew_services(update, user_info)
        

    async def _show_sales_renew_services(self, update: Update, user_info: dict) -> None:
        """Show services for sales partner renewal."""
        user_id = update.effective_user.id
        username = user_info.get('email')
        client = user_info.get('client', {})
        panel = user_info.get('panel', {})

        is_unlimited = client.get('is_unlimited', False)
        total_bytes = client.get('totalGB', 0)
        if 'is_unlimited' not in client:
            is_unlimited = total_bytes == 0

        panel_id = panel.get('id')

        # Get services
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            response = await client_http.get(f"{settings.API_BASE_URL}/admin/api/services")
            data = response.json()

        services = data.get("data", []) if data.get("status") == "success" else []

        # Filter services
        filtered_services = []
        for service in services:
            if not service.get('is_active'):
                continue
            if service.get('panel_id') != panel_id:
                continue

            service_volume = service.get('volume')
            service_is_unlimited = service_volume is None or service_volume == "unlimited"

            if is_unlimited and service_is_unlimited:
                filtered_services.append(service)
            elif not is_unlimited and not service_is_unlimited:
                filtered_services.append(service)

        if not filtered_services:
            await update.message.reply_text(
                "❌ سرویسی برای تمدید یافت نشد.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return

        # Store user info for renewal
        if not hasattr(self, '_sales_renew_user_info'):
            self._sales_renew_user_info = {}
        self._sales_renew_user_info[user_id] = user_info

        # Build keyboard
        keyboard = []
        for service in filtered_services:
            service_name = service.get('name', 'نامشخص')
            panel_name = service.get('panel_name', 'نامشخص')
            price = service.get('price')
            price_display = f"{int(price):,}" if price else "تماس"

            button_text = f"📦 {service_name} | {panel_name} | 💰{price_display}"

            keyboard.append([
                InlineKeyboardButton(
                    text=button_text[:60],
                    callback_data=f"sales_renew_service_{service['id']}",
                    style="primary"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")
        ])

        await update.message.reply_text(
            f"🔄 **تمدید سرویس - همکاری**\n\n"
            f"👤 کاربر: `{username}`\n"
            f"📡 پنل: {panel.get('name', 'نامشخص')}\n\n"
            f"لطفاً سرویس مورد نظر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    async def handle_sales_renew_service_selection(self, query, service_id: int) -> None:
        """Handle service selection for sales partner renewal - DIRECT renewal."""
        user_id = query.from_user.id
        
        if not hasattr(self, '_sales_renew_user_info') or user_id not in self._sales_renew_user_info:
            await query.edit_message_text(
                "❌ خطا در اطلاعات کاربر.",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            return
        
        user_info = self._sales_renew_user_info[user_id]
        
        # ====== Convert datetime to string ======
        client_data = user_info.get('client', {})
        expiry_date = client_data.get('expiry_date')
        
        if expiry_date:
            if isinstance(expiry_date, datetime):
                client_data['expiry_date'] = expiry_date.isoformat()
            elif hasattr(expiry_date, 'isoformat'):
                client_data['expiry_date'] = expiry_date.isoformat()
            else:
                client_data['expiry_date'] = str(expiry_date)
        
        # Get partner discount
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/check/{user_id}")
            partner_data = response.json().get("data", {})
        
        discount_percent = partner_data.get("discount_percent", 0)
        
        # Check remaining
        remaining = partner_data.get("remaining_purchases", 0)
        if remaining <= 0:
            await query.edit_message_text(
                "❌ **سقف خرید شما تکمیل شده است**\n\n"
                "برای ادامه، ابتدا باید تسویه حساب کنید.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 تسویه حساب", callback_data="sales_settlement")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
            return
        
        # Get service
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/services")
            data = response.json()
        
        service = None
        if data.get("status") == "success":
            for s in data.get("data", []):
                if s["id"] == service_id:
                    service = s
                    break
        
        if not service:
            await query.edit_message_text("❌ سرویس پیدا نشد")
            return
        
        # Calculate price
        original_price = service.get('price', 0)
        final_price = int(original_price * (100 - discount_percent) / 100) if discount_percent > 0 else original_price
        
        # ====== ✅ Show loading message ======
        await query.edit_message_text(
            f"⏳ **در حال تمدید سرویس...**\n\n"
            f"👤 کاربر: `{user_info.get('email')}`\n"
            f"📦 سرویس: {service.get('name')}\n"
            f"💰 قیمت: {final_price:,} تومان",
            parse_mode="Markdown"
        )
        
        # ====== ✅ Direct renewal via API ======
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.API_BASE_URL}/admin/api/sales/renew-account",
                json={
                    "partner_user_id": user_id,
                    "service_id": service_id,
                    "price": final_price,
                    "original_price": original_price,
                    "discount_percent": discount_percent,
                    "user_info": {
                        "email": user_info.get('email'),
                        "panel": user_info.get('panel', {}),
                        "client": client_data
                    }
                }
            )
            result = response.json()
        
        if result.get("status") != "success":
            await query.edit_message_text(
                f"❌ {result.get('message', 'خطا در تمدید')}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
            return
        
        account_data = result.get("data", {})
        
        # ====== ✅ Show success directly ======
        message = (
            f"🎉 **تمدید با موفقیت انجام شد!**\n\n"
            f"📧 **یوزرنیم:** `{account_data.get('client_email')}`\n"
            f"📦 **سرویس:** {service.get('name')}\n"
            f"💰 **قیمت اصلی:** {original_price:,} تومان\n"
            f"🎁 **تخفیف:** {discount_percent}%\n"
            f"💰 **قیمت نهایی:** {final_price:,} تومان\n\n"
            f"📊 **محدودیت باقی‌مانده:** {account_data.get('remaining_purchases')}\n\n"
            f"⏳ این مبلغ به فاکتور تسویه شما اضافه شد."
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت به پنل همکاری", callback_data="sales_partner")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


    async def handle_sales_status_check(self, query) -> None:
        """Handle sales partner status check - ask for username."""
        user_id = query.from_user.id
        logger.info(f"Sales status check requested by user: {user_id}")
        
        # Mark user in status check mode
        if not hasattr(self, '_sales_status_check_users'):
            self._sales_status_check_users = set()
        self._sales_status_check_users.add(user_id)
        
        message = (
            "📊 **وضعیت کاربر - همکاری**\n\n"
            "لطفاً یوزرنیم را وارد کنید:"
        )
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner", style="danger")]
            ])
        )


    async def handle_sales_status_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process username for sales partner status check."""
        user_id = update.effective_user.id
        username_input = update.message.text.strip()
        
        if not hasattr(self, '_sales_status_check_users') or user_id not in self._sales_status_check_users:
            return
        
        # Check ownership
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/transactions/{user_id}")
            transactions = response.json().get("data", [])
        
        owns_account = any(
            t.get("client_email", "").lower() == username_input.lower() 
            for t in transactions
        )
        
        if not owns_account:
            await update.message.reply_text(
                f"❌ **یوزرنیم `{username_input}` در لیست شما نیست!**\n\n"
                f"فقط می‌توانید وضعیت اکانت‌هایی که خودتان خریده‌اید را ببینید.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner", style="danger")]
                ])
            )
            return
        
        # Find user in panels
        user_info = await self._find_user_in_panels(username_input)
        
        if not user_info:
            await update.message.reply_text(
                f"❌ **یوزرنیم `{username_input}` پیدا نشد!**",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner", style="danger")]
                ])
            )
            return
        
        # Show status (same as _show_user_status but with back button)
        self._sales_status_check_users.remove(user_id)
        
        # Reuse _show_user_status but with different back button
        await self._show_user_status(update, user_info)


    async def handle_sales_deactivate(self, query) -> None:
        """Handle sales partner deactivate account."""
        user_id = query.from_user.id
        logger.info(f"Sales deactivate requested by user: {user_id}")

        # Mark user in deactivate mode
        if not hasattr(self, '_sales_deactivate_users'):
            self._sales_deactivate_users = set()
        self._sales_deactivate_users.add(user_id)

        message = (
            "⛔ **غیرفعال‌سازی کاربر**\n\n"
            "لطفاً یوزرنیم را وارد کنید:"
        )

        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner", style="danger")]
            ])
        )


    async def handle_sales_deactivate_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process username for deactivation."""
        user_id = update.effective_user.id
        username_input = update.message.text.strip()

        if not hasattr(self, '_sales_deactivate_users') or user_id not in self._sales_deactivate_users:
            return

        # Check ownership
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/transactions/{user_id}")
            transactions = response.json().get("data", [])

        owns_account = any(
            t.get("client_email", "").lower() == username_input.lower()
            for t in transactions
        )

        if not owns_account:
            await update.message.reply_text(
                f"❌ **یوزرنیم `{username_input}` در لیست شما نیست!**",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner", style="danger")]
                ])
            )
            return

        # Deactivate via API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.API_BASE_URL}/admin/api/sales/toggle-account",
                json={
                    "partner_user_id": user_id,
                    "client_email": username_input,
                    "enable": False
                }
            )
            result = response.json()

        self._sales_deactivate_users.remove(user_id)

        if result.get("status") == "success":
            await update.message.reply_text(
                f"✅ **کاربر `{username_input}` غیرفعال شد.**",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
        else:
            await update.message.reply_text(
                f"❌ {result.get('message', 'خطا')}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )






    async def handle_sales_activate(self, query) -> None:
        """Handle sales partner activate account."""
        user_id = query.from_user.id
        logger.info(f"Sales activate requested by user: {user_id}")

        if not hasattr(self, '_sales_activate_users'):
            self._sales_activate_users = set()
        self._sales_activate_users.add(user_id)

        message = (
            "✅ **فعال‌سازی مجدد کاربر**\n\n"
            "لطفاً یوزرنیم را وارد کنید:"
        )

        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner", style="danger")]
            ])
        )


    async def handle_sales_activate_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process username for activation."""
        user_id = update.effective_user.id
        username_input = update.message.text.strip()

        if not hasattr(self, '_sales_activate_users') or user_id not in self._sales_activate_users:
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.API_BASE_URL}/admin/api/sales/transactions/{user_id}")
            transactions = response.json().get("data", [])

        owns_account = any(
            t.get("client_email", "").lower() == username_input.lower()
            for t in transactions
        )

        if not owns_account:
            await update.message.reply_text(
                f"❌ **یوزرنیم `{username_input}` در لیست شما نیست!**",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner", style="danger")]
                ])
            )
            return

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.API_BASE_URL}/admin/api/sales/toggle-account",
                json={
                    "partner_user_id": user_id,
                    "client_email": username_input,
                    "enable": True
                }
            )
            result = response.json()

        self._sales_activate_users.remove(user_id)

        if result.get("status") == "success":
            await update.message.reply_text(
                f"✅ **کاربر `{username_input}` فعال شد.**",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
        else:
            await update.message.reply_text(
                f"❌ {result.get('message', 'خطا')}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])

           )

    async def handle_sales_settle_payment(self, query, amount: int) -> None:
        """Handle settlement payment."""
        user_id = query.from_user.id
        
        # Create payment
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.API_BASE_URL}/admin/api/payment/create",
                json={
                    "user_id": user_id,
                    "service_id": 0,  # settlement
                    "amount": amount,
                    "payment_type": "settlement"
                }
            )
            payment_result = response.json()
        
        if payment_result.get("status") != "success":
            await query.edit_message_text(
                f"❌ {payment_result.get('message', 'خطا در ساخت پرداخت')}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")]
                ])
            )
            return
        
        payment_url = payment_result["data"]["payment_url"]
        
        keyboard = [
            [
                InlineKeyboardButton("💳 رفتن به درگاه پرداخت", url=payment_url)
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="sales_partner")
            ]
        ]
        
        await query.edit_message_text(
            f"💳 **پرداخت تسویه**\n\n"
            f"مبلغ: {amount:,} تومان\n\n"
            f"پس از پرداخت، محدودیت شما بازنشانی می‌شود.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
