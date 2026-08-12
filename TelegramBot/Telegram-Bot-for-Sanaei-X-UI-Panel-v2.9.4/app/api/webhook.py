# app/api/webhook.py
from fastapi import APIRouter, Request
import requests
import asyncio
from app.models.database import get_purchase_by_authority, update_purchase_status, get_panel_by_id, get_service_by_id
from app.services.xui_client import XUIClient
from app.config import ZARINPAL_MERCHANT_ID, BOT_TOKEN

router = APIRouter()

@router.get("/webhook/zarinpal")
async def payment_callback(request: Request):
    params = dict(request.query_params)
    authority = params.get('Authority')
    status = params.get('Status')
    
    if status != 'OK' or not authority:
        return "<h1>❌ پرداخت لغو شد</h1><p>در صورت کسر مبلغ، طی 72 ساعت به حساب شما بازگردانده می‌شود.</p>"
    
    purchase = await get_purchase_by_authority(authority)
    if not purchase:
        return "<h1>❌ خطا</h1><p>سفارش یافت نشد.</p>"
    
    if purchase['status'] == 'completed':
        return "<h1>✅ پرداخت قبلاً انجام شده است</h1>"
    
    # Verify payment with Zarinpal
    verify_url = "https://api.zarinpal.com/pg/v4/payment/verify.json"
    payload = {
        "merchant_id": ZARINPAL_MERCHANT_ID,
        "amount": purchase['amount'],
        "authority": authority
    }
    
    try:
        response = requests.post(verify_url, json=payload)
        result = response.json()
        
        if result.get("data", {}).get("code") == 100:
            ref_id = result["data"]["ref_id"]
            await update_purchase_status(authority, "completed", ref_id)
            
            # Create VPN account
            panel = await get_panel_by_id(purchase['panel_id'])
            service = await get_service_by_id(purchase['service_id'])
            
            if panel and service:
                client = XUIClient(panel['url'], panel['username'], panel['password'])
                success = await client.add_client(
                    inbound_id=purchase['inbound_id'],
                    email=purchase['email'],
                    total_gb=service['traffic_gb'],
                    expiry_days=service['expiry_days']
                )
                
                if success:
                    # Send success message to user
                    bot_token = BOT_TOKEN
                    user_id = purchase['user_id']
                    
                    message = f"✅ پرداخت شما با موفقیت انجام شد!\n\n📧 ایمیل: {purchase['email']}\n📦 حجم: {service['traffic_gb']} GB\n⏰ اعتبار: {service['expiry_days']} روز\n\n🔧 از دستور /mystatus برای مشاهده وضعیت استفاده کنید."
                    
                    import httpx
                    async with httpx.AsyncClient() as client:
                        await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": user_id, "text": message})
                    
                    return f"<h1>✅ پرداخت موفق</h1><p>کد رهگیری: {ref_id}</p><p>اطلاعات اکانت برای شما در تلگرام ارسال شد.</p>"
        
        return "<h1>❌ پرداخت ناموفق</h1>"
        
    except Exception as e:
        print(f"Verification error: {e}")
        return "<h1>❌ خطا در تایید پرداخت</h1>"
