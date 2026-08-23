"""
Message handler module for processing Telegram messages.
"""

import logging
from typing import Optional
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

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
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /start command.
        
        Args:
            update: Telegram update object
            context: Telegram context object
        """
        try:
            user = update.effective_user
            logger.info(f"User started the bot: {user.id} - {user.username}")
            
            # Register or update user
            await self.user_service.register_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            
            welcome_text = (
                f"👋 سلام {user.first_name} عزیز!\n"
                f"به ربات مدیریت سرویس‌ها خوش آمدید.\n\n"
                f"لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
            )
            
            # Send main menu
            await update.message.reply_text(
                text=welcome_text,
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            
            logger.info(f"Main menu sent to user: {user.id}")
            
        except Exception as e:
            logger.error(f"Error in handle_start: {str(e)}")
            await update.message.reply_text(
                "❌ متأسفانه خطایی رخ داد. لطفاً مجدداً تلاش کنید."
            )
    
    # ============================================================
    # handle_callback_query 
    # ============================================================

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle callback queries from inline keyboards.
        Routes callbacks to appropriate handlers based on callback data.
        
        Args:
            update: Telegram update object
            context: Telegram context object
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
            
            # ============================================================
            # MAIN MENU ITEMS
            # ============================================================
            elif callback_data == "status":
                await self.handle_status(query)
            
            elif callback_data == "renew_service":
                await self.handle_renew_service(query)
            
            elif callback_data == "test_account":
                await self.handle_test_account(query)
            
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
                
    
    async def handle_status(self, query) -> None:
        """
        Handle status request.
        
        Args:
            query: Callback query object
        """
        user_id = query.from_user.id
        logger.info(f"Status requested for user: {user_id}")
        
        try:
            user_status = await self.user_service.get_user_status(user_id)
            
            status_text = (
                f"📊 **وضعیت کاربری شما**\n\n"
                f"🆔 شناسه: {user_status.user_id}\n"
                f"👤 نام کاربری: @{user_status.username or 'ندارد'}\n"
                f"📈 وضعیت: {user_status.status}\n"
                f"📅 اعتبار اشتراک: {user_status.remaining_days or 'نامشخص'} روز\n"
                f"🎯 نوع سرویس: {user_status.subscription_type or 'ندارد'}"
            )
            
            try:
                await query.edit_message_text(
                    text=status_text,
                    parse_mode="Markdown",
                    reply_markup=self.keyboard_builder.create_sub_menu()
                )
            except BadRequest:
                await query.message.reply_text(
                    text=status_text,
                    parse_mode="Markdown",
                    reply_markup=self.keyboard_builder.create_sub_menu()
                )
            
            logger.info(f"Status shown to user: {user_id}")
            
        except Exception as e:
            logger.error(f"Error in handle_status: {str(e)}")
            try:
                await query.message.reply_text(
                    "❌ خطا در دریافت وضعیت. لطفاً مجدداً تلاش کنید."
                )
            except Exception:
                pass
    
    async def handle_buy_service(self, query) -> None:
        """
        Handle buy service - show categories.
        """
        user_id = query.from_user.id
        logger.info(f"Buy service requested by user: {user_id}")
        
        try:
            # Get categories from API
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.API_BASE_URL}/admin/api/public/categories")
                data = response.json()
            
            if data.get("status") == "success" and data.get("data"):
                categories = data.get("data", [])
                
                # Build keyboard with categories
                keyboard = []
                for cat in categories:
                    keyboard.append([
                        InlineKeyboardButton(
                            text=f"📂 {cat['name']}",
                            callback_data=f"category_{cat['id']}"
                        )
                    ])
                
                # Add back button
                keyboard.append([
                    InlineKeyboardButton(
                        text="🔙 بازگشت به منو",
                        callback_data="main_menu"
                    )
                ])
                
                await query.edit_message_text(
                    text="📋 **دسته‌بندی سرویس‌ها**\n\nلطفاً یک دسته‌بندی را انتخاب کنید:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(
                    text="❌ در حال حاضر هیچ سرویسی موجود نیست.\nلطفاً بعداً تلاش کنید.",
                    reply_markup=self.keyboard_builder.create_sub_menu()
                )
                
        except Exception as e:
            logger.error(f"Error in handle_buy_service: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در دریافت سرویس‌ها. لطفاً مجدداً تلاش کنید.",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )


    async def handle_category_selection(self, query, category_id: int) -> None:
        """
        Handle category selection - show services in that category.
        """
        user_id = query.from_user.id
        logger.info(f"Category {category_id} selected by user {user_id}")
        
        try:
            # Get services by category
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/public/services?category_id={category_id}"
                )
                data = response.json()
            
            if data.get("status") == "success" and data.get("data"):
                services = data.get("data", [])
                
                if not services:
                    await query.edit_message_text(
                        text="📭 **هیچ سرویسی در این دسته‌بندی وجود ندارد**\n\nلطفاً دسته‌بندی دیگری را انتخاب کنید.",
                        parse_mode="Markdown",
                        reply_markup=self._get_back_to_categories_keyboard()
                    )
                    return
                
                # Build keyboard with services
                keyboard = []
                for service in services:
                    price_text = f"{service['price']:,}" if service['price'] else "تماس بگیرید"
                    volume_text = service['volume'] if service['volume'] else "نامحدود"
                    duration_text = f"{service['duration']} ماه" if service['duration'] else "متغیر"
                    
                    button_text = f"📦 {service['name']} | {volume_text}GB | {duration_text} | {price_text} تومان"
                    keyboard.append([
                        InlineKeyboardButton(
                            text=button_text[:60],  # Telegram limit
                            callback_data=f"service_{service['id']}"
                        )
                    ])
                
                # Add back button
                keyboard.append([
                    InlineKeyboardButton(
                        text="🔙 بازگشت به دسته‌بندی‌ها",
                        callback_data="buy_service"
                    )
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        text="🏠 بازگشت به منو",
                        callback_data="main_menu"
                    )
                ])
                
                # Get category name
                category_name = "دسته‌بندی"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{settings.API_BASE_URL}/admin/api/public/categories")
                    cats = resp.json()
                    if cats.get("status") == "success":
                        for cat in cats.get("data", []):
                            if cat["id"] == category_id:
                                category_name = cat["name"]
                                break
                
                await query.edit_message_text(
                    text=f"📂 **{category_name}**\n\nلطفاً یکی از سرویس‌های زیر را انتخاب کنید:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(
                    text="❌ خطا در دریافت سرویس‌ها. لطفاً مجدداً تلاش کنید.",
                    reply_markup=self._get_back_to_categories_keyboard()
                )
                
        except Exception as e:
            logger.error(f"Error in handle_category_selection: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در دریافت سرویس‌ها. لطفاً مجدداً تلاش کنید.",
                reply_markup=self._get_back_to_categories_keyboard()
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
                    f"{settings.API_BASE_URL}/admin/api/public/services?category_id=0"
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
            
            # Build service detail message
            price_text = f"{service['price']:,} تومان" if service['price'] else "تماس بگیرید"
            volume_text = f"{service['volume']} GB" if service['volume'] else "نامحدود"
            duration_text = f"{service['duration']} ماه" if service['duration'] else "متغیر"
            users_text = f"{service['users']} کاربر" if service['users'] else "نامحدود"
            
            message = (
                f"📦 **{service['name']}**\n\n"
                f"📊 **حجم:** {volume_text}\n"
                f"⏱️ **مدت:** {duration_text}\n"
                f"👥 **تعداد کاربر:** {users_text}\n"
                f"💰 **قیمت:** {price_text}\n"
                f"🖥️ **پنل:** {service['panel_name'] or 'نامشخص'}\n\n"
                f"برای خرید این سرویس، روی دکمه زیر کلیک کنید:"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🛒 خرید این سرویس",
                        callback_data=f"purchase_{service_id}"
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
                        callback_data="main_menu"
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


    def _get_back_to_categories_keyboard(self) -> InlineKeyboardMarkup:
        """
        Create keyboard to go back to categories.
        """
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
                    callback_data="main_menu"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)    
    async def handle_buy_service(self, query) -> None:
        """
        Handle new service purchase - show duration and plan selection.
        
        Args:
            query: Callback query object
        """
        user_id = query.from_user.id
        logger.info(f"Buy service requested by user: {user_id}")
        
        text = (
            "🛒 **خرید سرویس جدید**\n\n"
            "لطفاً مدت زمان و سپس پلن مورد نظر خود را انتخاب کنید:\n\n"
            "📅 **مدت زمان:**\n"
            "• 1 ماه - 2 ماه - 3 ماه - 4 ماه\n\n"
            "💾 **پلن‌های موجود:**\n"
            "• 10GB - 20GB - 30GB - 50GB - 100GB - 200GB"
        )
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_buy_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_buy_menu()
            )
    
    async def handle_duration_selection(self, query) -> None:
        """
        Handle duration selection from buy menu.
        
        Args:
            query: Callback query object
        """
        user_id = query.from_user.id
        callback_data = query.data
        
        # Extract duration from callback (e.g., "duration_1" -> 1)
        duration = int(callback_data.split("_")[1])
        
        logger.info(f"User {user_id} selected {duration} month(s)")
        
        text = (
            f"📅 **انتخاب پلن - {duration} ماهه**\n\n"
            f"لطفاً یکی از پلن‌های زیر را انتخاب کنید:\n\n"
            f"🔹 قیمت‌ها به تومان می‌باشند\n"
            f"🔹 حجم به گیگابایت محاسبه می‌شود"
        )
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_plan_selection_menu(duration)
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_plan_selection_menu(duration)
            )
    
    async def handle_plan_selection(self, query) -> None:
        """
        Handle plan selection from buy menu.
        
        Args:
            query: Callback query object
        """
        user_id = query.from_user.id
        callback_data = query.data
        
        # Parse callback data: plan_1m_10gb
        parts = callback_data.split("_")
        duration = int(parts[1].replace("m", ""))
        gb = parts[2].replace("gb", "")
        
        # Get price from dictionary
        prices = {
            "1": {"10": 82000, "20": 151000, "30": 218000, "50": 348000, "100": 641000, "200": 1272000},
            "2": {"10": 151000, "20": 278000, "30": 401000, "50": 640000, "100": 1179000, "200": 2340000},
            "3": {"10": 218000, "20": 401000, "30": 578000, "50": 923000, "100": 1700000, "200": 3370000},
            "4": {"10": 282000, "20": 519000, "30": 748000, "50": 1195000, "100": 2200000, "200": 4360000}
        }
        
        price = prices[str(duration)][gb]
        
        logger.info(f"User {user_id} selected: {duration} month, {gb}GB - {price} Toman")
        
        text = (
            f"✅ **انتخاب شما:**\n\n"
            f"📅 مدت زمان: **{duration} ماه**\n"
            f"💾 حجم: **{gb} گیگابایت**\n"
            f"💰 قیمت: **{price:,} تومان**\n\n"
            f"برای تأیید خرید، روی دکمه زیر کلیک کنید:"
        )
        
        keyboard = [
            [
                self.keyboard_builder.create_colored_button(
                    f"✅ خرید {gb}GB - {duration} ماهه",
                    f"confirm_purchase_{duration}m_{gb}gb",
                    self.keyboard_builder.STYLE_SUCCESS
                )
            ],
            [
                self.keyboard_builder.create_colored_button(
                    "🔙 بازگشت به انتخاب مدت",
                    "back_to_durations",
                    self.keyboard_builder.STYLE_DANGER
                )
            ]
        ]
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    async def handle_confirm_purchase(self, query) -> None:
        """
        Handle purchase confirmation.
        
        Args:
            query: Callback query object
        """
        user_id = query.from_user.id
        callback_data = query.data
        
        # Parse: confirm_purchase_1m_10gb
        parts = callback_data.split("_")
        duration = int(parts[2].replace("m", ""))
        gb = parts[3].replace("gb", "")
        
        logger.info(f"Purchase confirmed by user {user_id}: {duration}m, {gb}GB")
        
        text = (
            "✅ **خرید انجام شد!**\n\n"
            f"📅 مدت زمان: **{duration} ماه**\n"
            f"💾 حجم: **{gb} گیگابایت**\n\n"
            "🔑 اطلاعات سرویس به زودی برای شما ارسال خواهد شد.\n"
            "جهت دریافت اطلاعات اتصال، از بخش 'وضعیت من' استفاده کنید."
        )
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_service_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_service_menu()
            )
    
    async def handle_renew_service(self, query) -> None:
        """Handle service renewal."""
        user_id = query.from_user.id
        logger.info(f"Renew service requested by user: {user_id}")
        
        text = "🔄 **تمدید سرویس**\n\nبرای تمدید سرویس خود، لطفاً با پشتیبانی تماس بگیرید.\nهمچنین می‌توانید از طریق دکمه پشتیبانی با ما در ارتباط باشید."
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
    
    async def handle_test_account(self, query) -> None:
        """Handle test account request."""
        user_id = query.from_user.id
        logger.info(f"Test account requested by user: {user_id}")
        
        text = "🧪 **اکانت تست**\n\nبرای دریافت اکانت تست، لطفاً با پشتیبانی تماس بگیرید.\nاکانت تست به مدت 24 ساعت فعال خواهد بود."
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_service_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_service_menu()
            )
    
    async def handle_subordinates(self, query) -> None:
        """Handle subordinates list request."""
        user_id = query.from_user.id
        logger.info(f"Subordinates requested by user: {user_id}")
        
        subordinates = await self.user_service.get_subordinates(user_id)
        
        if subordinates:
            text = "👥 **لیست زیر مجموعه‌ها**\n\n"
            for sub in subordinates[:10]:
                text += f"• {sub.username or 'ناشناس'} (ID: {sub.user_id})\n"
        else:
            text = "👥 **زیر مجموعه‌ها**\n\nشما هنوز زیر مجموعه‌ای ندارید."
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
    
    async def handle_help(self, query) -> None:
        """Handle help request."""
        user_id = query.from_user.id
        logger.info(f"Help requested by user: {user_id}")
        
        help_text = (
            "❓ **راهنما**\n\n"
            "🔹 **وضعیت من**: نمایش وضعیت حساب و اشتراک شما\n"
            "🔹 **خرید سرویس جدید**: خرید سرویس جدید\n"
            "🔹 **تمدید سرویس**: تمدید سرویس فعلی\n"
            "🔹 **اکانت تست**: دریافت اکانت تست 24 ساعته\n"
            "🔹 **زیر مجموعه‌ها**: مشاهده کاربرانی که با لینک شما ثبت‌نام کرده‌اند\n"
            "🔹 **پشتیبانی**: ارتباط با تیم پشتیبانی\n\n"
            "💡 برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
        )
        
        try:
            await query.edit_message_text(
                text=help_text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=help_text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
    
    async def handle_support(self, query) -> None:
        """Handle support request."""
        user_id = query.from_user.id
        logger.info(f"Support requested by user: {user_id}")
        
        support_text = (
            "🆘 **پشتیبانی**\n\n"
            "برای ارتباط با تیم پشتیبانی، از طریق یکی از روش‌های زیر اقدام کنید:\n\n"
            "📧 ایمیل: support@example.com\n"
            "💬 تلگرام: @SupportBot\n"
            "🌐 وب‌سایت: example.com/support\n\n"
            "⏰ ساعات پاسخگویی: ۹ صبح تا ۱۲ شب"
        )
        
        try:
            await query.edit_message_text(
                text=support_text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=support_text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )
    
    async def show_main_menu(self, query) -> None:
        """Show main menu."""
        user_id = query.from_user.id
        logger.info(f"Main menu shown to user: {user_id}")
        
        text = "📋 **منوی اصلی**\n\nلطفاً یکی از گزینه‌ها را انتخاب کنید:"
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_main_menu()
            )
    
    async def handle_wallet(self, query) -> None:
        """Handle wallet request."""
        user_id = query.from_user.id
        logger.info(f"Wallet requested by user: {user_id}")
        
        text = (
            "💰 **کیف پول**\n\n"
            "موجودی کیف پول شما: **0 تومان**\n\n"
            "برای شارژ کیف پول، از طریق پشتیبانی اقدام کنید."
        )
        
        try:
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_service_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_service_menu()
            )
    
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
            await query.edit_message_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_service_menu()
            )
        except BadRequest:
            await query.message.reply_text(
                text=text,
                parse_mode="Markdown",
                reply_markup=self.keyboard_builder.create_service_menu()
            )

    # ============================================================
    # BUY SERVICE - NEW HANDLERS
    # ============================================================

    async def handle_buy_service(self, query) -> None:
        """
        Handle buy service - show categories from admin panel.
        
        Args:
            query: Callback query object
        """
        user_id = query.from_user.id
        logger.info(f"Buy service requested by user: {user_id}")
        
        try:
            # Get categories from API
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.API_BASE_URL}/admin/api/public/categories")
                data = response.json()
            
            if data.get("status") == "success" and data.get("data"):
                categories = data.get("data", [])
                
                if not categories:
                    await query.edit_message_text(
                        text="📭 **هیچ دسته‌بندی موجود نیست**\n\nلطفاً بعداً تلاش کنید.",
                        parse_mode="Markdown",
                        reply_markup=self.keyboard_builder.create_sub_menu()
                    )
                    return
                
                # Build keyboard with categories
                keyboard = []
                for cat in categories:
                    keyboard.append([
                        InlineKeyboardButton(
                            text=f"📂 {cat['name']}",
                            callback_data=f"category_{cat['id']}"
                        )
                    ])
                
                # Add back button
                keyboard.append([
                    InlineKeyboardButton(
                        text="🔙 بازگشت به منو",
                        callback_data="main_menu"
                    )
                ])
                
                await query.edit_message_text(
                    text="📋 **دسته‌بندی سرویس‌ها**\n\nلطفاً یک دسته‌بندی را انتخاب کنید:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(
                    text="❌ در حال حاضر هیچ سرویسی موجود نیست.\nلطفاً بعداً تلاش کنید.",
                    reply_markup=self.keyboard_builder.create_sub_menu()
                )
                
        except Exception as e:
            logger.error(f"Error in handle_buy_service: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در دریافت سرویس‌ها. لطفاً مجدداً تلاش کنید.",
                reply_markup=self.keyboard_builder.create_sub_menu()
            )


    async def handle_category_selection(self, query, category_id: int) -> None:
        """
        Handle category selection - show services in that category.
        
        Args:
            query: Callback query object
            category_id: Selected category ID
        """
        user_id = query.from_user.id
        logger.info(f"Category {category_id} selected by user {user_id}")
        
        try:
            # Get services by category
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.API_BASE_URL}/admin/api/public/services?category_id={category_id}"
                )
                data = response.json()
            
            if data.get("status") == "success" and data.get("data"):
                services = data.get("data", [])
                
                if not services:
                    await query.edit_message_text(
                        text="📭 **هیچ سرویسی در این دسته‌بندی وجود ندارد**\n\nلطفاً دسته‌بندی دیگری را انتخاب کنید.",
                        parse_mode="Markdown",
                        reply_markup=await self._get_back_to_categories_keyboard()
                    )
                    return
                
                # Build keyboard with services
                keyboard = []
                for service in services:
                    price_text = f"{service['price']:,}" if service['price'] else "تماس بگیرید"
                    volume_text = service['volume'] if service['volume'] else "نامحدود"
                    duration_text = f"{service['duration']} ماه" if service['duration'] else "متغیر"
                    
                    button_text = f"📦 {service['name']} | {volume_text}GB | {duration_text} | {price_text} تومان"
                    keyboard.append([
                        InlineKeyboardButton(
                            text=button_text[:60],  # Telegram limit
                            callback_data=f"service_{service['id']}"
                        )
                    ])
                
                # Add back buttons
                keyboard.append([
                    InlineKeyboardButton(
                        text="🔙 بازگشت به دسته‌بندی‌ها",
                        callback_data="buy_service"
                    )
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        text="🏠 بازگشت به منو",
                        callback_data="main_menu"
                    )
                ])
                
                # Get category name
                category_name = "دسته‌بندی"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{settings.API_BASE_URL}/admin/api/public/categories")
                    cats = resp.json()
                    if cats.get("status") == "success":
                        for cat in cats.get("data", []):
                            if cat["id"] == category_id:
                                category_name = cat["name"]
                                break
                
                await query.edit_message_text(
                    text=f"📂 **{category_name}**\n\nلطفاً یکی از سرویس‌های زیر را انتخاب کنید:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(
                    text="❌ خطا در دریافت سرویس‌ها. لطفاً مجدداً تلاش کنید.",
                    reply_markup=await self._get_back_to_categories_keyboard()
                )
                
        except Exception as e:
            logger.error(f"Error in handle_category_selection: {str(e)}")
            await query.edit_message_text(
                text="❌ خطا در دریافت سرویس‌ها. لطفاً مجدداً تلاش کنید.",
                reply_markup=await self._get_back_to_categories_keyboard()
            )


    async def handle_service_selection(self, query, service_id: int) -> None:
        """
        Handle service selection - show service details and buy option.
        
        Args:
            query: Callback query object
            service_id: Selected service ID
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
                    reply_markup=await self._get_back_to_categories_keyboard()
                )
                return
            
            # Build service detail message
            price_text = f"{service['price']:,} تومان" if service['price'] else "تماس بگیرید"
            volume_text = f"{service['volume']} GB" if service['volume'] else "نامحدود"
            duration_text = f"{service['duration']} ماه" if service['duration'] else "متغیر"
            users_text = f"{service['users']} کاربر" if service['users'] else "نامحدود"
            
            message = (
                f"📦 **{service['name']}**\n\n"
                f"📊 **حجم:** {volume_text}\n"
                f"⏱️ **مدت:** {duration_text}\n"
                f"👥 **تعداد کاربر:** {users_text}\n"
                f"💰 **قیمت:** {price_text}\n"
                f"🖥️ **پنل:** {service.get('panel_name', 'نامشخص')}\n\n"
                f"برای خرید این سرویس، روی دکمه زیر کلیک کنید:"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🛒 خرید این سرویس",
                        callback_data=f"purchase_{service_id}"
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
                        callback_data="main_menu"
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
                reply_markup=await self._get_back_to_categories_keyboard()
            )


    async def handle_purchase(self, query, service_id: int) -> None:
        """
        Handle purchase of a service.
        
        Args:
            query: Callback query object
            service_id: Service ID to purchase
        """
        user_id = query.from_user.id
        logger.info(f"Purchase requested by user {user_id} for service {service_id}")
        
        # TODO: Implement purchase logic
        # 1. Check if panel has capacity
        # 2. Create client in panel
        # 3. Save subscription in database
        # 4. Send connection details to user
        
        await query.edit_message_text(
            text="🛒 **در حال پردازش خرید...**\n\n"
                 "لطفاً صبر کنید تا اطلاعات سرویس شما آماده شود.\n\n"
                 "⚠️ این بخش در حال تکمیل است.",
            parse_mode="Markdown",
            reply_markup=self.keyboard_builder.create_sub_menu()
        )


    async def _get_back_to_categories_keyboard(self) -> InlineKeyboardMarkup:
        """
        Create keyboard to go back to categories.
        
        Returns:
            InlineKeyboardMarkup: Keyboard with back buttons
        """
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
                    callback_data="main_menu"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)


