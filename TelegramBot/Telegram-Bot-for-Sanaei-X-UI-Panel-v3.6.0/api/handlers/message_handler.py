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
            welcome_text = (
                f"👋 سلام {user.first_name} عزیز!\n"
                f"به ربات مدیریت سرویس‌ها خوش آمدید.\n\n"
                f"لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
            )
            await update.message.reply_text(
                text=welcome_text,
                reply_markup=self.keyboard_builder.create_main_menu()
            )
            logger.info(f"Main menu sent to user: {user.id}")
        except Exception as e:
            logger.error(f"Error in handle_start: {str(e)}")
            await update.message.reply_text("❌ متأسفانه خطایی رخ داد. لطفاً مجدداً تلاش کنید.")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle photo messages - receive receipt images.
        """
        user_id = update.effective_user.id
        logger.info(f"📸 Photo received from user {user_id}")

        if user_id not in self._pending_receipts:
            await update.message.reply_text(
                "❌ شما درخواست ارسال رسید نداشته‌اید.\n"
                "لطفاً ابتدا یک سرویس را انتخاب کرده و روی دکمه 'ارسال رسید پرداخت' کلیک کنید."
            )
            return

        service_id = self._pending_receipts[user_id]
        service_data = self._pending_purchases.get(user_id, {})
        logger.info(f"📸 Processing receipt for service {service_id}")

        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            logger.info(f"📸 File ID: {photo.file_id}")

            import os
            from datetime import datetime

            filename = f"receipt_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_path = f"receipts/{filename}"
            os.makedirs("receipts", exist_ok=True)

            logger.info(f"📸 Saving image to: {file_path}")
            await file.download_to_drive(file_path)

            logger.info(f"📸 Saving receipt to database for user {user_id}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.API_BASE_URL}/admin/api/receipts",
                    json={
                        "user_id": user_id,
                        "username": update.effective_user.username or "unknown",  # ← مهم
                        "service_id": service_id,
                        "service_name": service_data.get("service_name", ""),
                        "service_details": service_data.get("service_details", {}),
                        "image_path": file_path,
                        "image_filename": filename,
                        "status": "pending"
                    }
                )
                logger.info(f"📸 API response: {response.status_code} - {response.text}")

            del self._pending_receipts[user_id]

            await update.message.reply_text(
                "✅ **رسید شما با موفقیت ثبت شد!**\n\n"
                "پس از تأیید توسط ادمین، اکانت شما ساخته می‌شود و به شما اطلاع داده می‌شود.",
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
        if update.message and update.message.photo:
            await self.handle_photo(update, context)
            return
        
        if update.message and update.message.text:
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
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data

        logger.info(f"Callback received from user {user_id}: {callback_data}")

        try:
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
                await self.handle_receipt_upload(query, service_id)

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
        """Handle status request."""
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
                await query.message.reply_text("❌ خطا در دریافت وضعیت. لطفاً مجدداً تلاش کنید.")
            except Exception:
                pass

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
                price_text = f"{service['price']:,}" if service['price'] else "تماس بگیرید"
                volume_text = service['volume'] if service['volume'] else "نامحدود"
                duration_text = f"{service['duration']} ماه" if service['duration'] else "متغیر"
                button_text = f"📦 {service['name']} | {volume_text}GB | {duration_text} | {price_text} تومان"
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
            price_text = f"{service['price']:,}" if service['price'] else "تماس بگیرید"
            volume_text = service['volume'] if service['volume'] else "نامحدود"
            duration_text = f"{service['duration']} ماه" if service['duration'] else "متغیر"
            button_text = f"📦 {service['name']} | {volume_text}GB | {duration_text} | {price_text} تومان"
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
        """Handle service selection - show service details and buy option."""
        user_id = query.from_user.id
        logger.info(f"Service {service_id} selected by user {user_id}")

        try:
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

    async def handle_purchase(self, query, service_id: int) -> None:
        """Handle purchase of a service - show payment instructions."""
        user_id = query.from_user.id
        logger.info(f"Purchase requested by user {user_id} for service {service_id}")

        try:
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

            price_text = f"{service['price']:,} تومان" if service['price'] else "تماس بگیرید"
            volume_text = f"{service['volume']} GB" if service['volume'] else "نامحدود"
            duration_text = f"{service['duration']} ماه" if service['duration'] else "متغیر"

            payment_message = (
                f"🛒 **تأیید خرید سرویس**\n\n"
                f"📦 **{service['name']}**\n"
                f"📊 **حجم:** {volume_text}\n"
                f"⏱️ **مدت:** {duration_text}\n"
                f"💰 **قیمت:** {price_text}\n"
                f"🖥️ **پنل:** {service.get('panel_name', 'نامشخص')}\n\n"
                f"---\n\n"
                f"📌 **مراحل خرید:**\n\n"
                f"1️⃣ روی لینک زیر کلیک کنید و پرداخت را انجام دهید.\n"
                f"2️⃣ بعد از پرداخت، **رسید خود را در همین چت ارسال کنید.**\n"
                f"3️⃣ پس از تأیید رسید توسط ادمین، اکانت شما ساخته می‌شود.\n\n"
                f"⚠️ لطفاً از رسید پرداخت خود **اسکرین شات** بگیرید و در همین چت ارسال کنید.\n\n"
                f"🔗 **لینک پرداخت:**\n"
                f"{service.get('payment_link', 'https://example.com/pay')}\n\n"
                f"پس از پرداخت، روی دکمه زیر کلیک کنید تا رسید خود را ارسال کنید:"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        text="📤 ارسال رسید پرداخت",
                        callback_data=f"send_receipt_{service_id}"
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

            context_data = {
                "service_id": service_id,
                "service_name": service['name'],
                "service_details": {
                    "volume": service.get('volume'),
                    "duration": service.get('duration'),
                    "price": service.get('price'),
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

    async def handle_receipt_upload(self, query, service_id: int) -> None:
        """
        Handle receipt upload - instruct user to send image.
        """
        user_id = query.from_user.id
        logger.info(f"Receipt upload requested by user {user_id} for service {service_id}")

        # Store service_id for this user
        self._pending_receipts[user_id] = service_id

        # ====== اصلاح: استفاده از keyboard builder به جای await ======
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

        await query.edit_message_text(
            text="📤 **ارسال رسید پرداخت**\n\n"
                 "لطفاً **اسکرین شات** رسید پرداخت خود را در همین چت ارسال کنید.\n\n"
                 "📌 **نکات:**\n"
                 "• تصویر باید清晰 و خوانا باشد\n"
                 "• مبلغ و تاریخ پرداخت مشخص باشد\n"
                 "• پس از ارسال، رسید شما بررسی خواهد شد\n\n"
                 "⏳ پس از تأیید، اکانت شما ساخته می‌شود.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    # ============================================================
    # OTHER HANDLERS
    # ============================================================

    async def handle_renew_service(self, query) -> None:
        """Handle service renewal."""
        user_id = query.from_user.id
        logger.info(f"Renew service requested by user: {user_id}")
        text = "🔄 **تمدید سرویس**\n\nبرای تمدید سرویس خود، لطفاً با پشتیبانی تماس بگیرید.\nهمچنین می‌توانید از طریق دکمه پشتیبانی با ما در ارتباط باشید."
        try:
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())
        except BadRequest:
            await query.message.reply_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())

    async def handle_test_account(self, query) -> None:
        """Handle test account request."""
        user_id = query.from_user.id
        logger.info(f"Test account requested by user: {user_id}")
        text = "🧪 **اکانت تست**\n\nبرای دریافت اکانت تست، لطفاً با پشتیبانی تماس بگیرید.\nاکانت تست به مدت 24 ساعت فعال خواهد بود."
        try:
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_service_menu())
        except BadRequest:
            await query.message.reply_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_service_menu())

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
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())
        except BadRequest:
            await query.message.reply_text(text=text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())

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
            await query.edit_message_text(text=help_text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())
        except BadRequest:
            await query.message.reply_text(text=help_text, parse_mode="Markdown", reply_markup=self.keyboard_builder.create_sub_menu())

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
