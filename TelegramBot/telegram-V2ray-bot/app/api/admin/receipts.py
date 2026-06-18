# app/api/admin/receipts.py
import json
import time
import uuid
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.models.database import (
    get_pending_receipts, update_receipt_status, get_receipt_by_id,
    get_payment_link_by_id, get_service_by_id, get_all_panels,
    get_panel_by_id, get_next_user_number, add_transaction, get_help_settings
)
from app.services.xui_client import XUIClient
from app.services.renewal import process_renewal
from app.api.admin.helpers import generate_subid
from app.config import BOT_TOKEN


router = APIRouter()

class ReceiptApprove(BaseModel):
    receipt_id: int
    status: str
    message: str


@router.get("/admin/api/receipts/pending")
async def api_get_pending_receipts():
    return await get_pending_receipts()

@router.post("/admin/api/receipts/approve")
async def api_approve_receipt(data: ReceiptApprove):
    receipt = await get_receipt_by_id(data.receipt_id)
    if not receipt:
        return {"success": False, "error": "Receipt not found"}
    
    if data.status == "rejected":
        await update_receipt_status(data.receipt_id, "rejected", data.message)

        user_message = f"❌ رسید شما رد شد!\n\nدلیل: {data.message}\n\nلطفاً مجدد تلاش کنید."

        async with httpx.AsyncClient() as http_client:
            await http_client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": receipt['user_id'], "text": user_message}
            )

        return {"success": True}

    if data.status != "approved":
        return {"success": False, "error": "Invalid status"}

    is_renewal = receipt.get('service_name', '').startswith('تمدید -')

    if is_renewal:
        from app.services.renewal import process_renewal
        
        service_name = receipt.get('service_name', '')
        email = service_name.replace('تمدید -', '').strip()

        payment_link = await get_payment_link_by_id(receipt['payment_link_id'])
        if not payment_link:
            return {"success": False, "error": "Payment link not found"}

        service = await get_service_by_id(payment_link['service_id'])
        if not service:
            return {"success": False, "error": "Service not found"}

        panels = await get_all_panels()

        result = await process_renewal(
            email=email,
            panels=panels,
            service_traffic_gb=service['traffic_gb'],
            service_expiry_days=service['expiry_days'],
            user_id=receipt['user_id'],
            user_username=receipt.get('username', ''),
            amount=service['price_toman'],
            package_name=service['name'],
            admin_message=data.message
        )

        if result["success"]:
            await update_receipt_status(data.receipt_id, "approved", data.message)

            user_message = f"""✅ **تمدید سرویس شما انجام شد!**

📧 **یوزرنیم (ایمیل):** `{result['email']}`
📦 **حجم اضافه شده:** {result['traffic_gb']} GB
⏰ **مدت اضافه شده:** {result['expiry_days']} روز

🔗 **لینک سابسکریپشن:**
`{result['sub_link']}`

📱 سرویس شما با موفقیت تمدید شد."""

            async with httpx.AsyncClient() as http_client:
                await http_client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": receipt['user_id'], "text": user_message, "parse_mode": "Markdown"}
                )

            return {"success": True}
        else:
            return {"success": False, "error": result['message']}
    
    else:
        # NEW PURCHASE LOGIC
        payment_link = await get_payment_link_by_id(receipt['payment_link_id'])
        if not payment_link:
            return {"success": False, "error": "Payment link not found"}

        panel = await get_panel_by_id(payment_link['panel_id'])
        service = await get_service_by_id(payment_link['service_id'])

        if not panel or not service:
            return {"success": False, "error": "Panel or service not found"}

        from app.api.admin.helpers import generate_subid
        from app.models.database import get_next_user_number, add_transaction, get_help_settings
        
        base_url = panel['url'].rstrip('/')
        new_number = await get_next_user_number()
        email = f"bot{new_number}"
        client_uuid = str(uuid.uuid4())
        sub_id = generate_subid()

        total_bytes = service['traffic_gb'] * 1024 * 1024 * 1024
        expiry_time = int((time.time() + service['expiry_days'] * 86400) * 1000) if service['expiry_days'] > 0 else -2592000000

        async with httpx.AsyncClient(verify=False) as http_client:
            login_url = f"{base_url}/login"
            await http_client.post(login_url, json={"username": panel['username'], "password": panel['password']})

            client_data = {"clients": [{"id": client_uuid, "email": email, "totalGB": total_bytes, "expiryTime": expiry_time, "limitIp": 1, "enable": True, "subId": sub_id}]}
            settings_json = json.dumps(client_data)
            data_body = f"id={payment_link['inbound_id']}&settings={settings_json}"
            headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"}

            add_url = f"{base_url}/panel/api/inbounds/addClient"
            resp = await http_client.post(add_url, content=data_body, headers=headers)
            result = resp.json()

            if result.get("success"):
                await update_receipt_status(data.receipt_id, "approved", data.message)

                await add_transaction(
                    user_id=receipt['user_id'],
                    user_username=receipt.get('username', ''),
                    trans_type='purchase',
                    status='approved',
                    amount=service['price_toman'],
                    package_name=service['name'],
                    panel_name=panel['name'],
                    email=email,
                    admin_message=data.message
                )

                sub_url = panel.get('sub_url', '')
                sub_link = f"{sub_url.rstrip('/')}/{sub_id}" if sub_url else f"{base_url}/sub/{sub_id}"

                help_settings = await get_help_settings()
                install_link = help_settings.get('install_link', '')

                user_message = f"""✅ پرداخت شما تأیید شد!

📧 یوزرنیم (ایمیل): {email}
📦 حجم: {service['traffic_gb']} GB
⏰ مدت اعتبار: {service['expiry_days']} روز

🔗 لینک سابسکریپشن: 
{sub_link}

📱 نحوه استفاده:
1. لینک سابسکریپشن را در اپلیکیشن خود وارد کنید
2. یا از دستور /mystatus برای مشاهده وضعیت استفاده کنید

📖 راهنمای نصب: 
{install_link if install_link else 'https://t.me/SpaceGate_Support'}

⚠️ لطفاً یوزرنیم خود را برای استفاده از دستور /mystatus ذخیره کنید."""

                async with httpx.AsyncClient() as http_client:
                    await http_client.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": receipt['user_id'], "text": user_message}
                    )

                return {"success": True}
            else:
                return {"success": False, "error": f"API error: {result.get('msg')}"}

@router.get("/admin/api/receipts/image/{receipt_id}")
async def api_get_receipt_image(receipt_id: int):
    receipt = await get_receipt_by_id(receipt_id)
    if not receipt or not receipt.get('receipt_image'):
        raise HTTPException(status_code=404, detail="Image not found")

    file_id = receipt['receipt_image']

    try:
        async with httpx.AsyncClient() as client:
            file_info_res = await client.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
                params={"file_id": file_id}
            )
            file_info = file_info_res.json()

            if file_info.get("ok"):
                file_path = file_info["result"]["file_path"]
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                img_res = await client.get(file_url)
                return Response(content=img_res.content, media_type="image/jpeg")
            else:
                return {"error": "Could not get file info", "file_id": file_id}
    except Exception as e:
        return {"error": str(e), "file_id": file_id}
