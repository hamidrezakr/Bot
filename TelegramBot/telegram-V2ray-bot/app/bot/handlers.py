# app/bot/handlers.py
import json
import secrets
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.services.xui_client import XUIClient
from app.utils.helpers import detect_operator, get_operator_status_message
from app.models.database import (
    get_all_services, get_help_settings, get_warning_message, get_all_panels,
    get_active_users_count, create_purchase, get_service_by_id, get_panel_by_id,
    get_payment_links_by_service, get_payment_link_by_id, create_receipt, get_all_payment_links
)
from app.config import ZARINPAL_MERCHANT_ID, WEBHOOK_URL
from datetime import datetime

# Main menu keyboard
async def get_main_menu_keyboard():
    """Create main menu inline keyboard"""
    from app.models.database import get_help_settings
    help_settings = await get_help_settings()
    support_link = help_settings.get('link', 'https://t.me/SpaceGate_Support')

    keyboard = [
        [
            InlineKeyboardButton("🌍 لیست سرورها", callback_data="menu_services"),
            InlineKeyboardButton("🛍️ خرید سرویس", callback_data="menu_buy")
        ],
        [
            InlineKeyboardButton("📊 وضعیت من", callback_data="menu_my_status"),
            InlineKeyboardButton("🔄 تمدید سرویس", callback_data="menu_renew")
        ],
        [
            InlineKeyboardButton("📚 راهنما", callback_data="menu_help"),
            InlineKeyboardButton("🔧 پشتیبانی", url=support_link)

        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Show welcome message with menu"""
    warning_message = await get_warning_message()
    
    welcome_text = f"""
👋 **به بات Space Gate  خوش آمدید!**

🔹 **سرویس‌های پرسرعت** در سرورهای اروپا
🔹 **پشتیبانی ۲۴ ساعته** از طریق همین بات
🔹 **قیمت مناسب** با کیفیت بالا

📱 **قبل از خرید توجه کنید:**
{warning_message}

لطفاً از دکمه‌های زیر استفاده کنید:
"""
    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message
    
    await message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=await get_main_menu_keyboard())

async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /services command - Show available servers from selected inbounds"""
    await update.message.reply_text("📡 در حال دریافت لیست سرورها... ⏳")
    
    try:
        panels = await get_all_panels()
        
        if not panels:
            await update.message.reply_text(
                "❌ هیچ سروری در پنل پیدا نشد.",
                reply_markup=await get_main_menu_keyboard()
            )
            return
        
        message = "🌍 **لیست سرورهای موجود:**\n\n"
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
                        message += f"{status_icon} **{inbound.remark}** ({panel['name']})\n"
                        found_any = True
            except Exception as e:
                print(f"Error with panel {panel['name']}: {e}")
                continue
        
        if not found_any:
            await update.message.reply_text(
                "❌ هیچ سرور فعالی در پنل پیدا نشد.",
                reply_markup=await get_main_menu_keyboard()
            )
            return
        
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=await get_main_menu_keyboard())
        
    except Exception as e:
        print(f"Services error: {e}")
        await update.message.reply_text(
            f"❌ خطا در دریافت اطلاعات",
            reply_markup=await get_main_menu_keyboard()
        )

async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /check command - Check user status"""
    if not context.args:
        await update.message.reply_text(
            "❌ **نحوه استفاده:**\n"
            "`/check email@example.com`\n\n"
            "مثال: `/check acc123`\n\n"
            "💡 از منوی زیر نیز می‌توانید استفاده کنید:",
            parse_mode="Markdown",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    email = context.args[0]
    await update.message.reply_text(f"🔍 در حال بررسی کاربر `{email}`... ⏳", parse_mode="Markdown")
    
    panels = await get_all_panels()
    found_client = None
    
    for panel in panels:
        try:
            client = XUIClient(panel['url'], panel['username'], panel['password'])
            inbounds = await client.get_inbounds()
            if inbounds:
                for inbound in inbounds:
                    for client_obj in inbound.clients:
                        if client_obj.email.lower() == email.lower():
                            found_client = client_obj
                            break
                    if found_client:
                        break
            if found_client:
                break
        except Exception:
            continue
    
    if found_client is None:
        await update.message.reply_text(
            f"❌ **کاربری با مشخصات `{email}` در پنل پیدا نشد!**\n\n"
            "📌 **نکات مهم:**\n"
            "• لطفاً یوزرنیم خود را به درستی وارد کنید\n"
            "• فرمت صحیح: `acc` به همراه اعداد (مثال: `acc123`)\n"
            "• به حروف بزرگ و کوچک حساس نیست\n\n"
            "برای تلاش مجدد از /mystatus یا /check استفاده کنید.",
            parse_mode="Markdown",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    operator = detect_operator(found_client.email)
    operator_message = get_operator_status_message(operator)
    
    if found_client.totalGB == 0:
        traffic_text = "نامحدود"
        usage_bar = "∞"
        usage_percent = 0
    else:
        used_gb = found_client.usedGB
        total_gb = found_client.totalGB
        remaining = total_gb - used_gb
        if remaining < 0:
            remaining = 0
        usage_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0
        
        bar_length = 15
        filled = int(bar_length * usage_percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        usage_bar = f"{bar} {usage_percent:.1f}%"
        traffic_text = f"{used_gb:,} GB / {total_gb:,} GB"
    
    if found_client.is_expired:
        expiry_text = "❌ **منقضی شده**"
    elif found_client.expiry_date:
        days_left = (found_client.expiry_date - datetime.now()).days
        if days_left < 0:
            expiry_text = "❌ **منقضی شده**"
        elif days_left <= 3:
            expiry_text = f"⚠️ {found_client.expiry_date.strftime('%Y-%m-%d')} ({days_left} روز باقی - به زودی منقضی می‌شود!)"
        else:
            expiry_text = f"📅 {found_client.expiry_date.strftime('%Y-%m-%d')} ({days_left} روز باقی مانده)"
    else:
        expiry_text = "♾️ نامحدود"
    
    status_text = "✅ فعال" if found_client.enable else "❌ غیرفعال"
    
    message = f"""
📊 **اطلاعات کاربر:** `{found_client.email}`

━━━━━━━━━━━━━━━━━━━
📡 **وضعیت سرویس:**
┣ 📱 اپراتور: {operator}
┣ {operator_message}
┣ 🔌 وضعیت: {status_text}
━━━━━━━━━━━━━━━━━━━
💾 **مصرف ترافیک:**
┣ 📊 {usage_bar}
┣ 📥 مصرف شده: {traffic_text}
┗ 📤 حجم باقی‌مانده: {found_client.remaining_gb if found_client.remaining_gb != float('inf') else '∞'} GB
━━━━━━━━━━━━━━━━━━━
⏰ **تاریخ انقضا:**
┗ {expiry_text}
━━━━━━━━━━━━━━━━━━━
"""
    
    if operator in ["ایرانسل", "رایتل"]:
        message += f"\n⚠️ **هشدار:** {operator_message}"
        message += "\n💡 پیشنهاد: از سرویس همراه اول یا اینترنت ثابت استفاده کنید."
    
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=await get_main_menu_keyboard())

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buy command - Direct to manual payment"""
    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message
    
    await buy_manual(update, context)

async def buy_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available services for manual payment with panel and inbound names"""
    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message
    
    # دریافت همه لینک‌های پرداخت
    all_payment_links = await get_all_payment_links()
    
    if not all_payment_links:
        await message.reply_text("❌ هیچ لینک پرداختی برای سرویس‌ها تعریف نشده است.\nلطفاً با پشتیبانی تماس بگیرید.", reply_markup=await get_main_menu_keyboard())
        return
    
    # دریافت همه سرویس‌ها برای مرتب‌سازی
    services = await get_all_services()
    
    # ایجاد دیکشنری برای نگهداری sort_order هر سرویس
    service_order = {s['id']: s.get('sort_order', 0) for s in services}
    
    # مرتب‌سازی لینک‌های پرداخت بر اساس sort_order سرویس و سپس id
    sorted_links = sorted(all_payment_links, key=lambda x: (service_order.get(x['service_id'], 0), x['id']))
    
    keyboard = []
    for link in sorted_links:
        if not link.get('is_active'):
            continue
        
        service = await get_service_by_id(link['service_id'])
        if not service:
            continue
        
        panel = await get_panel_by_id(link['panel_id'])
        panel_name = panel.get('name', f"پنل {link['panel_id']}") if panel else f"پنل {link['panel_id']}"
        
        inbound_name = f"اینباند {link['inbound_id']}"
        try:
            if panel:
                client = XUIClient(panel['url'], panel['username'], panel['password'])
                inbounds = await client.get_inbounds()
                for ib in inbounds:
                    if ib.id == link['inbound_id']:
                        inbound_name = ib.remark
                        break
        except:
            pass
        
        button_text = f"💰 {service['name']} - {service['traffic_gb']}GB - {link['price_toman']:,} تومان"
        button_text += f"\n   📡 {panel_name} | {inbound_name}"
        
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"manual_pay_{link['id']}"
        )])
    
    if not keyboard:
        await message.reply_text("❌ هیچ لینک پرداختی فعالی برای سرویس‌ها تعریف نشده است.", reply_markup=await get_main_menu_keyboard())
        return
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text("🛍️ لطفاً سرویس مورد نظر خود را انتخاب کنید:", reply_markup=reply_markup)

async def manual_pay_selected(update: Update, context: ContextTypes.DEFAULT_TYPE, link_id: int):
    """Show payment link to user and ask for receipt"""
    query = update.callback_query
    payment_link = await get_payment_link_by_id(link_id)
    
    if not payment_link or not payment_link.get('is_active'):
        await query.message.reply_text("❌ این لینک پرداخت دیگر فعال نیست.", reply_markup=await get_main_menu_keyboard())
        return
    
    service = await get_service_by_id(payment_link['service_id'])
    
    context.user_data['payment_link_id'] = link_id
    context.user_data['waiting_for_receipt'] = True
    
    message = f"""
🛍️ **سرویس انتخابی:** {service['name']}
📊 **حجم:** {service['traffic_gb']} GB
⏰ **مدت اعتبار:** {service['expiry_days']} روز
💰 **مبلغ:** {payment_link['price_toman']:,} تومان

🔗 **لینک پرداخت:** 
{payment_link['link']}

📌 **مراحل بعد:**
1. روی لینک کلیک کنید و پرداخت را انجام دهید
2. بعد از پرداخت، رسید خود را در همین چت ارسال کنید
3. پس از تأیید رسید توسط ادمین، اکانت شما ساخته می‌شود

📝 **نمونه رسید:** 
لطفاً رسید پرداخت خود را به صورت  تصویر ارسال کنید.


⚠️ لطفاً رسید پرداخت خود را به صورت  تصویر ارسال کنید.
"""
    await query.message.edit_text(message, parse_mode="Markdown", reply_markup=await get_main_menu_keyboard())

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive receipt from user after manual payment"""
    if not context.user_data.get('waiting_for_receipt'):
        return
    
    payment_link_id = context.user_data.get('payment_link_id')
    if not payment_link_id:
        await update.message.reply_text("❌ خطا. لطفاً دوباره از /buy یا /renew استفاده کنید.", reply_markup=await get_main_menu_keyboard())
        context.user_data['waiting_for_receipt'] = False
        return
    
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name
    
    receipt_text = update.message.text or ""
    
    receipt_image = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        receipt_image = file_id
        receipt_text = "تصویر رسید ارسال شده است."
    
    # Check if this is a renewal
    is_renewal = context.user_data.get('is_renewal', False)
    
    if is_renewal:
        # For renewal, store renewal info in receipt
        renewal_info = context.user_data.get('renewal_info', {})
        service_name = f"تمدید - {renewal_info.get('email', '')}"
        service_traffic = 0
        service_price = renewal_info.get('amount', 0)
        service_expiry = 0
        panel_name = renewal_info.get('panel_name', '') 
        inbound_name = renewal_info.get('inbound_name', '')
    else:
        # Normal purchase
        payment_link = await get_payment_link_by_id(payment_link_id)
        
        service_name = ""
        service_traffic = 0
        service_price = 0
        service_expiry = 0
        panel_name = ""
        inbound_name = ""
        
        if payment_link:
            service = await get_service_by_id(payment_link['service_id'])
            panel = await get_panel_by_id(payment_link['panel_id'])
            
            if service:
                service_name = service.get('name', '')
                service_traffic = service.get('traffic_gb', 0)
                service_price = payment_link.get('price_toman', 0)
                service_expiry = service.get('expiry_days', 0)
            
            if panel:
                panel_name = panel.get('name', '')
                inbound_name = f"اینباند {payment_link.get('inbound_id', '')}"
    
    await create_receipt(
        user_id=user_id,
        username=username,
        payment_link_id=payment_link_id,
        receipt_text=receipt_text,
        receipt_image=receipt_image,
        service_name=service_name,
        service_traffic=service_traffic,
        service_price=service_price,
        service_expiry=service_expiry,
        panel_name=panel_name,
        inbound_name=inbound_name
    )
    
    # Store renewal flag in receipt for admin approval
    if is_renewal:
        context.user_data['pending_renewal'] = context.user_data.get('renewal_info', {})
    
    context.user_data['waiting_for_receipt'] = False
    context.user_data['payment_link_id'] = None
    context.user_data['is_renewal'] = False
    context.user_data['renewal_info'] = None
    
    await update.message.reply_text(
        "✅ رسید شما با موفقیت ثبت شد!\n\n"
        "پس از تأیید توسط ادمین، اکانت شما ساخته می‌شود و به شما اطلاع داده می‌شود.",
        reply_markup=await get_main_menu_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command - Show full help from database"""
    help_settings = await get_help_settings()
    
    help_text = f"""
📚 **راهنمای کامل بات**

{help_settings.get('description', 'راهنمای نصب و استفاده از سرویس')}

🔹 **/services** - مشاهده لیست سرورها و سرویس‌های موجود
🔹 **/check [یوزرنیم]** - بررسی وضعیت کاربر با وارد کردن یوزرنیم
🔹 **/mystatus** - بررسی وضعیت من (بدون نیاز به نوشتن یوزرنیم)
🔹 **/buy** - خرید سرویس جدید از فروشگاه
🔹 **/menu** - نمایش منوی اصلی
🔹 **/help** - نمایش همین راهنما

📱 **پشتیبانی:** {help_settings.get('link', 'https://t.me/SpaceGate_Support')}
"""
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=await get_main_menu_keyboard())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command - Show main menu"""
    await update.message.reply_text(
        "📱 **منوی اصلی:**\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=await get_main_menu_keyboard()
    )

async def my_status_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mystatus command - Ask user for their username"""
    context.user_data['attempt_count'] = 0
    context.user_data['waiting_for_email'] = True
    
    await update.message.reply_text(
        "🔍 **بررسی وضعیت من**\n\n"
        "لطفاً **یوزرنیم** خود را وارد کنید.\n\n"
        "📌 **نحوه ورود:**\n"
        "• اگر از طریق پنل قبلی اکانت دارید: `acc` به همراه اعداد\n"
        "  مثال: `acc123` یا `acc456`\n"
        "• اگر از طریق بات خرید کرده‌اید: `bot` به همراه اعداد\n"
        "  مثال: `bot1` یا `bot2`\n\n"
        "⚠️ **توجه:**\n"
        "• حروف بزرگ و کوچک مهم نیست (به طور خودکار اصلاح می‌شود)\n"
        "• فقط عدد و حروف مجاز است\n\n"
        "شما **3 بار** فرصت دارید.\n"
        "برای انصراف /cancel را وارد کنید.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages - check for waiting states"""
    
    # First check if waiting for renewal email
    if context.user_data.get('waiting_for_renew_email'):
        await receive_renew_email(update, context)
        return
    
    # Then check if waiting for status email
    if context.user_data.get('waiting_for_email'):
        user_input = update.message.text.strip()
        
        if 'attempt_count' not in context.user_data:
            context.user_data['attempt_count'] = 0
        
        if user_input.lower() == '/cancel':
            context.user_data['waiting_for_email'] = False
            context.user_data['attempt_count'] = 0
            await update.message.reply_text(
                "❌ عملیات بررسی لغو شد.\n"
                "برای شروع مجدد از /mystatus استفاده کنید.",
                reply_markup=await get_main_menu_keyboard()
            )
            return
        
        normalized_email = user_input.lower().strip()
        
        if not re.match(r'^[a-z0-9@._-]+$', normalized_email):
            await update.message.reply_text(
                "❌ **فرمت وارد شده صحیح نیست!**\n\n"
                "لطفاً فقط از حروف کوچک انگلیسی، اعداد و کاراکترهای `@._-` استفاده کنید.\n\n"
                f"🔢 تلاش باقی‌مانده: {2 - context.user_data['attempt_count']}\n\n"
                "برای انصراف /cancel را وارد کنید.",
                parse_mode="Markdown"
            )
            return
        
        loading_msg = await update.message.reply_text(f"🔍 در حال بررسی کاربر `{normalized_email}`... ⏳", parse_mode="Markdown")
        
        panels = await get_all_panels()
        
        # پیدا کردن همه پنل‌هایی که این کاربر در آنها وجود دارد
        panels_list = []
        for panel in panels:
            try:
                client = XUIClient(panel['url'], panel['username'], panel['password'])
                inbounds = await client.get_inbounds()
                if inbounds:
                    for inbound in inbounds:
                        for client_obj in inbound.clients:
                            if client_obj.email.lower() == normalized_email:
                                panels_list.append({
                                    "panel_name": panel.get('name', 'نامشخص'),
                                    "inbound_name": inbound.remark,
                                    "client": client_obj
                                })
                                break
                        if any(p["client"].email.lower() == normalized_email for p in panels_list):
                            break
                if any(p["client"].email.lower() == normalized_email for p in panels_list):
                    break
            except Exception:
                continue
        
        if not panels_list:
            context.user_data['attempt_count'] += 1
            remaining_attempts = 3 - context.user_data['attempt_count']
            
            if remaining_attempts > 0:
                await loading_msg.delete()
                await update.message.reply_text(
                    f"❌ **کاربری با مشخصات `{normalized_email}` پیدا نشد!**\n\n"
                    f"🔢 **{remaining_attempts}** بار دیگر می‌توانید تلاش کنید.\n\n"
                    "لطفاً یوزرنیم صحیح را وارد کنید یا برای انصراف /cancel را بزنید.",
                    parse_mode="Markdown"
                )
                return
            else:
                context.user_data['waiting_for_email'] = False
                context.user_data['attempt_count'] = 0
                await loading_msg.delete()
                await update.message.reply_text(
                    "❌ **شما 3 بار تلاش ناموفق داشتید!**\n\n"
                    "برای شروع مجدد از دستور /mystatus استفاده کنید.",
                    parse_mode="Markdown",
                    reply_markup=await get_main_menu_keyboard()
                )
                return
        
        context.user_data['waiting_for_email'] = False
        context.user_data['attempt_count'] = 0
        await loading_msg.delete()
        
        # ساخت پیام برای هر پنل
        if len(panels_list) == 1:
            p = panels_list[0]
            client_data = p["client"]
            
            if client_data.totalGB == 0:
                traffic_text = "نامحدود"
                usage_bar = "∞"
                usage_percent = 0
            else:
                used_gb = client_data.usedGB
                total_gb = client_data.totalGB
                remaining = total_gb - used_gb
                if remaining < 0:
                    remaining = 0
                usage_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0
                
                bar_length = 15
                filled = int(bar_length * usage_percent / 100)
                bar = "█" * filled + "░" * (bar_length - filled)
                usage_bar = f"{bar} {usage_percent:.1f}%"
                traffic_text = f"{used_gb:,} GB / {total_gb:,} GB"
            
            if client_data.is_expired:
                expiry_text = "❌ **منقضی شده**"
            elif client_data.expiry_date:
                days_left = (client_data.expiry_date - datetime.now()).days
                if days_left < 0:
                    expiry_text = "❌ **منقضی شده**"
                elif days_left <= 3:
                    expiry_text = f"⚠️ {client_data.expiry_date.strftime('%Y-%m-%d')} ({days_left} روز باقی - به زودی منقضی می‌شود!)"
                else:
                    expiry_text = f"📅 {client_data.expiry_date.strftime('%Y-%m-%d')} ({days_left} روز باقی مانده)"
            else:
                expiry_text = "♾️ نامحدود"
            
            status_text = "✅ فعال" if client_data.enable else "❌ غیرفعال"
            
            message = f"""
                        📊 **اطلاعات کاربر:** `{client_data.email}`

                        ━━━━━━━━━━━━━━━━━━━
                        📡 **وضعیت سرویس:**
                        ┣ 🖥️ کشور: {p['panel_name']} - {p['inbound_name']}
                        ┣ 🔌 وضعیت: {status_text}
                        ━━━━━━━━━━━━━━━━━━━
                        💾 **مصرف ترافیک:**
                        ┣ 📊 {usage_bar}
                        ┣ 📥 مصرف شده: {traffic_text}
                        ┗ 📤 حجم باقی‌مانده: {client_data.remaining_gb if client_data.remaining_gb != float('inf') else '∞'} GB
                        ━━━━━━━━━━━━━━━━━━━
                        ⏰ **تاریخ انقضا:**
                        ┗ {expiry_text}
                        ━━━━━━━━━━━━━━━━━━━
                        """
        else:
            message = f"📊 **اطلاعات کاربر:** `{normalized_email}`\n\n"
            message += "━━━━━━━━━━━━━━━━━━━\n"
            message += "📡 **سرویس‌های فعال در پنل‌های مختلف:**\n\n"
            
            for idx, p in enumerate(panels_list, 1):
                client_data = p["client"]
                
                if client_data.totalGB == 0:
                    traffic_text = "نامحدود"
                else:
                    used_gb = client_data.usedGB
                    total_gb = client_data.totalGB
                    traffic_text = f"{used_gb:,} GB / {total_gb:,} GB"
                
                if client_data.is_expired:
                    expiry_text = "منقضی شده"
                elif client_data.expiry_date:
                    days_left = (client_data.expiry_date - datetime.now()).days
                    if days_left < 0:
                        expiry_text = "منقضی شده"
                    else:
                        expiry_text = f"{client_data.expiry_date.strftime('%Y-%m-%d')} ({days_left} روز)"
                else:
                    expiry_text = "نامحدود"
                
                status_text = "فعال" if client_data.enable else "غیرفعال"
                
                message += f"**{idx} - {p['panel_name']}**\n"
                message += f"   ┣ 🔌 اینباند: {p['inbound_name']}\n"
                message += f"   ┣ 🔌 وضعیت: {status_text}\n"
                message += f"   ┣ 📊 مصرف: {traffic_text}\n"
                message += f"   ┗ ⏰ انقضا: {expiry_text}\n\n"
            
            message += "━━━━━━━━━━━━━━━━━━━"
        
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=await get_main_menu_keyboard())
    
    else:
        # If not waiting for anything, just ignore
        pass
# ============================================================
# Renew Functions
# ============================================================

async def renew_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /renew command - Ask user for their username"""
    # بررسی اینکه درخواست از نوع callback است یا message
    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message
    
    context.user_data['renew_attempt_count'] = 0
    context.user_data['waiting_for_renew_email'] = True
    
    await message.reply_text(
        "🔄 **تمدید سرویس**\n\n"
        "لطفاً **یوزرنیم** خود را وارد کنید.\n\n"
        "📌 **نحوه ورود:**\n"
        "• اگر از طریق پنل قبلی اکانت دارید: `acc` به همراه اعداد\n"
        "  مثال: `acc123` یا `acc456`\n"
        "• اگر از طریق بات خرید کرده‌اید: `bot` به همراه اعداد\n"
        "  مثال: `bot1` یا `bot2`\n\n"
        "⚠️ **توجه:**\n"
        "• حروف بزرگ و کوچک مهم نیست (به طور خودکار اصلاح می‌شود)\n"
        "• فقط عدد و حروف مجاز است\n\n"
        "شما **3 بار** فرصت دارید.\n"
        "برای انصراف /cancel را وارد کنید.",
        parse_mode="Markdown"
    )

async def receive_renew_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive username for renewal and show service info"""
    if not context.user_data.get('waiting_for_renew_email'):
        return
    
    user_input = update.message.text.strip()
    
    if 'renew_attempt_count' not in context.user_data:
        context.user_data['renew_attempt_count'] = 0
    
    if user_input.lower() == '/cancel':
        context.user_data['waiting_for_renew_email'] = False
        context.user_data['renew_attempt_count'] = 0
        await update.message.reply_text(
            "❌ عملیات تمدید لغو شد.\n"
            "برای شروع مجدد از /renew استفاده کنید.",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    normalized_email = user_input.lower().strip()
    
    if not re.match(r'^[a-z0-9@._-]+$', normalized_email):
        await update.message.reply_text(
            "❌ **فرمت وارد شده صحیح نیست!**\n\n"
            "لطفاً فقط از حروف کوچک انگلیسی، اعداد و کاراکترهای `@._-` استفاده کنید.\n\n"
            f"🔢 تلاش باقی‌مانده: {2 - context.user_data['renew_attempt_count']}\n\n"
            "برای انصراف /cancel را وارد کنید.",
            parse_mode="Markdown"
        )
        return
    
    loading_msg = await update.message.reply_text(f"🔍 در حال بررسی کاربر `{normalized_email}`... ⏳", parse_mode="Markdown")
    
    panels = await get_all_panels()
    found_service = None
    found_panel = None
    found_inbound = None
    
    for panel in panels:
        try:
            client = XUIClient(panel['url'], panel['username'], panel['password'])
            inbounds = await client.get_inbounds()
            if inbounds:
                for inbound in inbounds:
                    for client_obj in inbound.clients:
                        if client_obj.email.lower() == normalized_email:
                            found_service = client_obj
                            found_panel = panel
                            found_inbound = inbound
                            break
                    if found_service:
                        break
            if found_service:
                break
        except Exception:
            continue
    
    if found_service is None:
        context.user_data['renew_attempt_count'] += 1
        remaining_attempts = 3 - context.user_data['renew_attempt_count']
        
        if remaining_attempts > 0:
            await loading_msg.delete()
            await update.message.reply_text(
                f"❌ **کاربری با مشخصات `{normalized_email}` پیدا نشد!**\n\n"
                f"🔢 **{remaining_attempts}** بار دیگر می‌توانید تلاش کنید.\n\n"
                "لطفاً یوزرنیم صحیح را وارد کنید یا برای انصراف /cancel را بزنید.",
                parse_mode="Markdown"
            )
            return
        else:
            context.user_data['waiting_for_renew_email'] = False
            context.user_data['renew_attempt_count'] = 0
            await loading_msg.delete()
            await update.message.reply_text(
                "❌ **شما 3 بار تلاش ناموفق داشتید!**\n\n"
                "برای شروع مجدد از دستور /renew استفاده کنید.",
                parse_mode="Markdown",
                reply_markup=await get_main_menu_keyboard()
            )
            return
    
    context.user_data['waiting_for_renew_email'] = False
    context.user_data['renew_attempt_count'] = 0
    await loading_msg.delete()
    
    # Store service info for renewal
    context.user_data['renew_service'] = {
        "panel_id": found_panel['id'],
        "panel_name": found_panel['name'],
        "inbound_name": found_inbound.remark,
        "inbound_id": found_inbound.id,
        "email": found_service.email,
        "uuid": found_service.uuid if hasattr(found_service, 'uuid') else None,
        "totalGB": found_service.totalGB,
        "usedGB": found_service.usedGB,
        "expiryTime": found_service.expiryTime,
        "enable": found_service.enable,
        "is_expired": found_service.is_expired
    }
    
    # Calculate and display service info
    client_data = found_service
    
    if client_data.totalGB == 0:
        traffic_text = "نامحدود"
        usage_bar = "∞"
        usage_percent = 0
        remaining_gb = float('inf')
    else:
        used_gb = client_data.usedGB
        total_gb = client_data.totalGB
        remaining_bytes = total_gb - used_gb
        if remaining_bytes < 0:
            remaining_bytes = 0
        remaining_gb = remaining_bytes / (1024**3)
        usage_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0
        
        bar_length = 15
        filled = int(bar_length * usage_percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        usage_bar = f"{bar} {usage_percent:.1f}%"
        traffic_text = f"{used_gb:,} GB / {total_gb:,} GB"
    
    if client_data.is_expired:
        expiry_text = "❌ **منقضی شده**"
    elif client_data.expiry_date:
        days_left = (client_data.expiry_date - datetime.now()).days
        if days_left < 0:
            expiry_text = "❌ **منقضی شده**"
        else:
            expiry_text = f"📅 {client_data.expiry_date.strftime('%Y-%m-%d')} ({days_left} روز باقی مانده)"
    else:
        expiry_text = "♾️ نامحدود"
    
    status_text = "✅ فعال" if client_data.enable and not client_data.is_expired else "❌ غیرفعال یا منقضی"
    
    message = f"""
📊 **اطلاعات سرویس:** `{client_data.email}`

━━━━━━━━━━━━━━━━━━━
📡 **اطلاعات پنل:**
┣ 🖥️ پنل: {found_panel['name']}
┣ 🔌 اینباند: {found_inbound.remark}
┣ 🔌 وضعیت: {status_text}
━━━━━━━━━━━━━━━━━━━
💾 **مصرف ترافیک:**
┣ 📊 {usage_bar}
┣ 📥 مصرف شده: {traffic_text}
┗ 📤 حجم باقی‌مانده: {remaining_gb:.1f} GB 
━━━━━━━━━━━━━━━━━━━
⏰ **تاریخ انقضا:**
┗ {expiry_text}
━━━━━━━━━━━━━━━━━━━
"""
    
    keyboard = [[InlineKeyboardButton("🔄 تمدید این سرویس", callback_data="renew_confirm")]]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def renew_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show packages for renewal"""
    query = update.callback_query
    await query.answer()
    
    selected_service = context.user_data.get('renew_service')
    if not selected_service:
        await query.message.reply_text(
            "❌ خطا در انتخاب سرویس. لطفاً دوباره از /renew استفاده کنید.",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    # Get available packages for renewal
    services = await get_all_services()
    
    if not services:
        await query.message.reply_text("❌ هیچ پکیجی برای تمدید وجود ندارد.", reply_markup=await get_main_menu_keyboard())
        return
    
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(
            f"📦 {service['name']} - {service['traffic_gb']}GB - {service['expiry_days']} روز - {service['price_toman']:,} تومان",
            callback_data=f"renew_package_{service['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        f"🔄 **تمدید سرویس**\n\n"
        f"📡 پنل: {selected_service['panel_name']}\n"
        f"🔌 اینباند: {selected_service['inbound_name']}\n"
        f"📧 ایمیل: {selected_service['email']}\n\n"
        f"لطفاً پکیج تمدید را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def renew_create_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, package_id: int):
    """Create payment for renewal"""
    query = update.callback_query
    await query.answer()
    
    selected_service = context.user_data.get('renew_service')
    package = await get_service_by_id(package_id)
    
    if not selected_service or not package:
        await query.message.reply_text("❌ خطا در انتخاب سرویس یا پکیج.", reply_markup=await get_main_menu_keyboard())
        return
    
    panel = await get_panel_by_id(selected_service['panel_id'])
    if not panel:
        await query.message.reply_text("❌ پنل مورد نظر یافت نشد.", reply_markup=await get_main_menu_keyboard())
        return
    
    user_id = str(update.effective_user.id)
    amount = package['price_toman']
    
    # Store renewal info for later
    context.user_data['renewal_info'] = {
        "panel_id": selected_service['panel_id'],
        "panel_name": selected_service['panel_name'],
        "inbound_name": selected_service['inbound_name'],
        "inbound_id": selected_service['inbound_id'],
        "service_id": package_id,
        "email": selected_service['email'],
        "uuid": selected_service['uuid'],
        "amount": amount,
        "current_total": selected_service['totalGB'],
        "current_used": selected_service['usedGB'],
        "current_expiry": selected_service['expiryTime'],
        "is_active": selected_service['enable'] and not selected_service['is_expired']
    }
    
    # Get payment link for this package
    payment_links = await get_payment_links_by_service(package_id)
    if payment_links:
        link = payment_links[0]['link']
        
        context.user_data['is_renewal'] = True
        context.user_data['payment_link_id'] = payment_links[0]['id']
        context.user_data['waiting_for_receipt'] = True
        
        await query.message.edit_text(
            f"🔄 **تمدید سرویس**\n\n"
            f"📡 پنل: {selected_service['panel_name']}\n"
            f"📧 ایمیل: {selected_service['email']}\n"
            f"📦 پکیج: {package['name']}\n"
            f"📊 حجم اضافه: {package['traffic_gb']} GB\n"
            f"⏰ مدت اضافه: {package['expiry_days']} روز\n"
            f"💰 مبلغ: {amount:,} تومان\n\n"
            f"🔗 **لینک پرداخت:**\n{link}\n\n"
            f"📌 **مراحل بعد:**\n"
            f"1. روی لینک کلیک کنید و پرداخت را انجام دهید\n"
            f"2. بعد از پرداخت، رسید خود را در همین چت ارسال کنید\n"
            f"3. پس از تأیید رسید توسط ادمین، سرویس شما تمدید می‌شود\n\n"
            f"⚠️ لطفاً رسید پرداخت خود را به صورت  تصویر ارسال کنید.",
            parse_mode="Markdown",
            reply_markup=await get_main_menu_keyboard()
        )
    else:
        await query.message.reply_text(
            "❌ خطا در ایجاد لینک پرداخت. لطفاً با پشتیبانی تماس بگیرید.",
            reply_markup=await get_main_menu_keyboard()
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel waiting for email"""
    context.user_data['waiting_for_email'] = False
    context.user_data['attempt_count'] = 0
    await update.message.reply_text(
        "❌ عملیات لغو شد.",
        reply_markup=await get_main_menu_keyboard()
    )
