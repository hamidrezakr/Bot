# app/services/renewal/renewal_service.py
import logging
import time
import json
import httpx
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


async def find_user_in_panels(email: str, panels: list) -> Tuple[Optional[dict], Optional[int], Optional[str], Optional[str], int, int, int]:
    """
    Find user across all panels and extract UUID, subId and current data
    Returns: (found_panel, found_inbound_id, found_uuid, found_sub_id, current_total, current_used, current_expiry)
    """
    for panel in panels:
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Login
                login_url = f"{panel['url']}/login"
                login_data = {"username": panel['username'], "password": panel['password']}
                await client.post(login_url, json=login_data)

                # Get inbounds list
                list_url = f"{panel['url']}/panel/api/inbounds/list"
                resp = await client.get(list_url)

                if resp.status_code != 200:
                    continue

                data = resp.json()
                if not data.get("success") or not data.get("obj"):
                    continue

                for inbound in data["obj"]:
                    for client_stat in inbound.get("clientStats", []):
                        if client_stat.get("email", "").lower() == email.lower():
                            found_uuid = client_stat.get("uuid") or client_stat.get("id", "")
                            found_sub_id = client_stat.get("subId", "")
                            
                            logger.info(f"Found user {email} in panel {panel['name']} with UUID: {found_uuid}, subId: {found_sub_id}")
                            
                            return (
                                panel,
                                inbound.get("id"),
                                str(found_uuid) if found_uuid else "",
                                found_sub_id,
                                client_stat.get("total", 0),
                                client_stat.get("up", 0) + client_stat.get("down", 0),
                                client_stat.get("expiryTime", 0)
                            )
        except Exception as e:
            logger.error(f"Error searching in panel {panel.get('name', 'unknown')}: {e}")
            continue

    logger.error(f"User {email} not found in any panel")
    return None, None, None, None, 0, 0, 0


def calculate_renewal_values(current_total: int, current_used: int, current_expiry: int,
                             new_traffic_gb: int, new_expiry_days: int) -> Tuple[int, int]:
    """
    Calculate new total bytes and expiry time for renewal
    Returns: (new_total_bytes, new_expiry_time_ms)
    """
    now_ms = int(time.time() * 1000)

    # Calculate remaining bytes
    remaining_bytes = max(0, current_total - current_used)

    # Calculate remaining days
    remaining_time_ms = max(0, current_expiry - now_ms) if current_expiry > 0 else 0
    remaining_days = remaining_time_ms / (86400 * 1000)

    # Add new package values
    new_total_bytes = int(remaining_bytes + (new_traffic_gb * 1024 * 1024 * 1024))
    new_expiry_time = int(now_ms + (remaining_days + new_expiry_days) * 86400 * 1000) if new_expiry_days > 0 else 0

    logger.info(f"Renewal calculation: remaining_bytes={remaining_bytes}, remaining_days={remaining_days:.2f}, "
                f"new_total_bytes={new_total_bytes}, new_expiry_time={new_expiry_time}")

    return new_total_bytes, new_expiry_time


async def update_client_in_panel(panel_url: str, panel_username: str, panel_password: str,
                                   inbound_id: int, user_uuid: str, email: str, sub_id: str,
                                   new_total_bytes: int, new_expiry_time: int) -> bool:
    """
    Update client in panel using the exact format from browser
    """
    try:
        # Build client data exactly like browser
        client_data = {
            "clients": [{
                "id": user_uuid,
                "email": email,
                "totalGB": new_total_bytes,
                "expiryTime": new_expiry_time,
                "limitIp": 1,
                "enable": True,
                "subId": sub_id
            }]
        }

        settings_json = json.dumps(client_data)
        data_body = f"id={inbound_id}&settings={settings_json}"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

        async with httpx.AsyncClient(verify=False) as client:
            # Login
            login_url = f"{panel_url}/login"
            login_data = {"username": panel_username, "password": panel_password}
            await client.post(login_url, json=login_data)

            # Update client
            update_url = f"{panel_url}/panel/api/inbounds/updateClient/{user_uuid}"
            logger.info(f"Update URL: {update_url}")
            
            resp = await client.post(update_url, content=data_body, headers=headers)

            logger.info(f"Update response status: {resp.status_code}")
            logger.info(f"Update response body: {resp.text[:500]}")

            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    logger.info(f"Successfully renewed user {email}")
                    return True
                else:
                    logger.error(f"Update API returned error: {result.get('msg')}")
                    return False
            else:
                logger.error(f"Update failed with status {resp.status_code}")
                return False

    except Exception as e:
        logger.error(f"Error updating client: {e}")
        return False


async def process_renewal(email: str, panels: list,
                          service_traffic_gb: int, service_expiry_days: int,
                          user_id: str = None, user_username: str = None, 
                          amount: int = None, package_name: str = None,
                          admin_message: str = None) -> Dict[str, Any]:

    """
    Main renewal process
    """
    logger.info(f"Starting renewal process for email: {email}")

    # Step 1: Find user in panels (get uuid and subId)
    panel, inbound_id, user_uuid, sub_id, current_total, current_used, current_expiry = await find_user_in_panels(email, panels)

    if not panel:
        return {"success": False, "message": f"User {email} not found in any panel"}

    if not user_uuid:
        return {"success": False, "message": f"Cannot find UUID for user {email}"}

    logger.info(f"Found user: panel={panel['name']}, uuid={user_uuid}, subId={sub_id}")

    # Step 2: Calculate new values
    new_total_bytes, new_expiry_time = calculate_renewal_values(
        current_total, current_used, current_expiry,
        service_traffic_gb, service_expiry_days
    )

    # Step 3: Update client in panel (preserving subId)
    success = await update_client_in_panel(
        panel['url'], panel['username'], panel['password'],
        inbound_id, user_uuid, email, sub_id,
        new_total_bytes, new_expiry_time
    )

    if not success:
        return {"success": False, "message": "Failed to update client in panel"}
    
     # Step 3.5: Reset traffic usage for the client
    from app.services.xui_client import XUIClient
    xui_client = XUIClient(panel['url'], panel['username'], panel['password'])
    reset_success = await xui_client.reset_client_traffic(email)

    if reset_success:
        logger.info(f"Traffic reset successfully for {email}")
    else:
        logger.warning(f"Could not reset traffic for {email}, but renewal completed")

    # Step 4: Generate subscription link using subId and panel's sub_url
    if sub_id:
        # از sub_url ذخیره شده در پنل استفاده کن
        sub_url = panel.get('sub_url', '')
        if not sub_url:
            # اگر sub_url ذخیره نشده بود، از آدرس پیش‌فرض پنل استفاده کن
            sub_url = f"{panel['url']}/sub/"
        sub_link = f"{sub_url.rstrip('/')}/{sub_id}"
    else:
        sub_link = f"{panel['url']}/sub/{email}"

    logger.info(f"Generated subscription link: {sub_link}")


    # Step 5: Add transaction record to database (if user info provided)
    if user_id and amount and package_name:
        from app.models.database import add_transaction
        await add_transaction(
            user_id=user_id,
            user_username=user_username or '',
            trans_type='renewal',
            status='approved',
            amount=amount,
            package_name=package_name,
            panel_name=panel['name'],
            email=email,
            admin_message=admin_message or ''
        )
        logger.info(f"Transaction recorded for renewal of {email}")



    return {
        "success": True,
        "message": "Renewal completed successfully",
        "sub_link": sub_link,
        "panel_name": panel['name'],
        "email": email,
        "traffic_gb": service_traffic_gb,
        "expiry_days": service_expiry_days
    }
