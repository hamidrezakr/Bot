# app/bot/callbacks.py
import json
import re
from telegram import Update
from telegram.ext import ContextTypes
from app.bot.handlers import get_main_menu_keyboard, buy, buy_manual, manual_pay_selected, start, renew_start, renew_confirm, renew_create_payment
from app.services.xui_client import XUIClient
from app.models.database import get_all_panels

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button callbacks"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "menu_services":
        panels = await get_all_panels()

        if not panels:
            await query.message.reply_text(
                "❌ هیچ سروری در پنل پیدا نشد.",
                reply_markup=await get_main_menu_keyboard()
            )
            return

        message = "🌍 لیست سرورهای موجود:\n\n"
        found_any = False

        for panel in panels:
            if not panel.get('show_in_bot', True):
                continue

            try:
                client = XUIClient(panel['url'], panel['username'], panel['password'])
                inbounds = await client.get_inbounds()

                if inbounds:
                    selected_ids = json.loads(panel.get('selected_inbounds', '[]'))

                    for inbound in inbounds:
                        if selected_ids and inbound.id not in selected_ids:
                            continue

                        status_icon = "🟢" if inbound.enable else "🔴"
                        message += f"{status_icon} {inbound.remark} ({panel['name']})\n"
                        found_any = True
            except Exception as e:
                print(f"Error with panel {panel['name']}: {e}")
                continue

        if not found_any:
            await query.message.reply_text(
                "❌ هیچ سرور فعالی در پنل پیدا نشد.",
                reply_markup=await get_main_menu_keyboard()
            )
            return

        await query.message.reply_text(message, reply_markup=await get_main_menu_keyboard())

    elif data == "menu_buy":
        await buy(update, context)

    elif data == "menu_my_status":
        context.user_data['waiting_for_email'] = True

        await query.message.reply_text(
            "🔍 بررسی وضعیت من\n\n"
            "لطفاً یوزرنیم خود را وارد کنید.\n\n"
            "📌 نحوه ورود:\n"
            "• اگر از طریق پنل قبلی اکانت دارید: acc به همراه اعداد\n"
            "  مثال: acc123 یا acc456\n"
            "• اگر از طریق بات خرید کرده‌اید: bot به همراه اعداد\n"
            "  مثال: bot1 یا bot2\n\n"
            "⚠️ توجه:\n"
            "• حروف بزرگ و کوچک مهم نیست (به طور خودکار اصلاح می‌شود)\n"
            "• فقط عدد و حروف مجاز است\n\n"
            "برای شروع، یوزرنیم خود را در پیام بعدی وارد کنید.\n"
            "می‌توانید با دستور /cancel انصراف دهید.",
            reply_markup=await get_main_menu_keyboard()
        )

    elif data == "menu_help":
        from app.models.database import get_help_settings
        help_settings = await get_help_settings()

        description = help_settings.get('description', 'راهنمای نصب و استفاده از سرویس')
        support_link = help_settings.get('link', 'https://t.me/SpaceGate_Support')
        install_link = help_settings.get('install_link', '')

        help_text = f"""
📚 راهنمای کامل بات

{description}

🔹 /services - مشاهده لیست سرورها و سرویس‌های موجود
🔹 /mystatus - بررسی وضعیت من (بدون نیاز به نوشتن یوزرنیم)
🔹 /buy - خرید سرویس جدید از فروشگاه
🔹 /renew - تمدید سرویس موجود
🔹 /menu - نمایش منوی اصلی
🔹 /help - نمایش همین راهنما

📱 پشتیبانی: {support_link}
"""
        if install_link:
            help_text += f"\n\n📖 راهنمای نصب: {install_link}"

        await query.message.reply_text(help_text, reply_markup=await get_main_menu_keyboard())

    elif data.startswith("manual_pay_"):
        link_id = int(data.split("_")[2])
        await manual_pay_selected(update, context, link_id)

    elif data == "menu_main":
        await start(update, context)

    elif data == "menu_renew":
        await renew_start(update, context)

    elif data == "renew_confirm":
        await renew_confirm(update, context)

    elif data.startswith("renew_package_"):
        package_id = int(data.split("_")[2])
        await renew_create_payment(update, context, package_id)
