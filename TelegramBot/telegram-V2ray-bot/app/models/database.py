# app/models/database.py
import os
import aiosqlite
import json
from typing import List, Dict, Optional
from datetime import datetime

#DB_PATH = "bot_data.db"
DB_PATH = os.environ.get("DB_PATH", "/app/data/bot_data.db")

async def init_db():
    """Initialize database tables"""
    async with aiosqlite.connect(DB_PATH) as db:
        
        # Transactions history table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_username TEXT,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                amount INTEGER NOT NULL,
                package_name TEXT,
                panel_name TEXT,
                email TEXT,
                admin_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Daily stats table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                total_sales INTEGER DEFAULT 0,
                total_amount INTEGER DEFAULT 0,
                renewals_count INTEGER DEFAULT 0,
                new_users_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Panels table with capacity fields and sub_url
        await db.execute('''
            CREATE TABLE IF NOT EXISTS panels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                show_in_bot BOOLEAN DEFAULT 1,
                selected_inbounds TEXT DEFAULT '[]',
                max_slots INTEGER DEFAULT 0,
                sub_url TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if columns exist and add if not
        cursor = await db.execute("PRAGMA table_info(panels)")
        columns = [col[1] for col in await cursor.fetchall()]
        
        if 'show_in_bot' not in columns:
            await db.execute("ALTER TABLE panels ADD COLUMN show_in_bot BOOLEAN DEFAULT 1")
        if 'selected_inbounds' not in columns:
            await db.execute("ALTER TABLE panels ADD COLUMN selected_inbounds TEXT DEFAULT '[]'")
        if 'max_slots' not in columns:
            await db.execute("ALTER TABLE panels ADD COLUMN max_slots INTEGER DEFAULT 0")
        if 'sub_url' not in columns:
            await db.execute("ALTER TABLE panels ADD COLUMN sub_url TEXT DEFAULT ''")
        
        # Services table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                traffic_gb INTEGER NOT NULL,
                price_toman INTEGER NOT NULL,
                expiry_days INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Purchases table for tracking online orders
        await db.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                panel_id INTEGER NOT NULL,
                inbound_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                amount INTEGER NOT NULL,
                authority TEXT,
                ref_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Payment links table (manual payment)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS payment_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                panel_id INTEGER NOT NULL,
                inbound_id INTEGER NOT NULL,
                link TEXT NOT NULL,
                price_toman INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Payment receipts table with all fields
        await db.execute('''
            CREATE TABLE IF NOT EXISTS payment_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                username TEXT,
                payment_link_id INTEGER NOT NULL,
                receipt_text TEXT,
                receipt_image TEXT,
                service_name TEXT,
                service_traffic INTEGER,
                service_price INTEGER,
                service_expiry INTEGER,
                panel_name TEXT,
                inbound_name TEXT,
                status TEXT DEFAULT 'pending',
                admin_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Help settings table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS help_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT,
                link TEXT,
                install_link TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Warning message table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS warning_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User counter table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_counter (
                id INTEGER PRIMARY KEY,
                last_number INTEGER DEFAULT 0
            )
        ''')
        await db.execute("INSERT OR IGNORE INTO user_counter (id, last_number) VALUES (1, 0)")
        
        # برای دیتابیس‌های قدیمی - اضافه کردن ستون‌های جدید به payment_receipts
        cursor = await db.execute("PRAGMA table_info(payment_receipts)")
        columns = [col[1] for col in await cursor.fetchall()]
        
        if 'username' not in columns:
            await db.execute("ALTER TABLE payment_receipts ADD COLUMN username TEXT")
        if 'service_name' not in columns:
            await db.execute("ALTER TABLE payment_receipts ADD COLUMN service_name TEXT")
        if 'service_traffic' not in columns:
            await db.execute("ALTER TABLE payment_receipts ADD COLUMN service_traffic INTEGER")
        if 'service_price' not in columns:
            await db.execute("ALTER TABLE payment_receipts ADD COLUMN service_price INTEGER")
        if 'service_expiry' not in columns:
            await db.execute("ALTER TABLE payment_receipts ADD COLUMN service_expiry INTEGER")
        if 'panel_name' not in columns:
            await db.execute("ALTER TABLE payment_receipts ADD COLUMN panel_name TEXT")
        if 'inbound_name' not in columns:
            await db.execute("ALTER TABLE payment_receipts ADD COLUMN inbound_name TEXT")
        
        await db.commit()
        await init_default_data()

async def init_default_data():
    """Insert default data if tables are empty"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if services table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM services")
        count = (await cursor.fetchone())[0]
        
        if count == 0:
            default_services = [
                ("پایه", 10, 50000, 30, 1, 1),
                ("استاندارد", 30, 100000, 60, 1, 2),
                ("پیشرفته", 100, 200000, 90, 1, 3),
            ]
            await db.executemany(
                "INSERT INTO services (name, traffic_gb, price_toman, expiry_days, is_active, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                default_services
            )
        
        # Check if help settings is empty
        cursor = await db.execute("SELECT COUNT(*) FROM help_settings")
        count = (await cursor.fetchone())[0]
        
        if count == 0:
            await db.execute(
                "INSERT INTO help_settings (description, link, install_link) VALUES (?, ?, ?)",
                ("راهنمای نصب و استفاده از سرویس", "https://t.me/SpaceGate_Support", "")
            )
        
        # Check if warning messages is empty
        cursor = await db.execute("SELECT COUNT(*) FROM warning_messages")
        count = (await cursor.fetchone())[0]
        
        if count == 0:
            default_warning = "⚠️ هشدار مهم: اپراتورهای ایرانسل و رایتل در حال حاضر اختلال دارند. اپراتور همراه اول و اینترنت ثابت پایدار هستند."
            await db.execute(
                "INSERT INTO warning_messages (message) VALUES (?)",
                (default_warning,)
            )
        
        await db.commit()

# ============================================================
# Panel CRUD operations
# ============================================================

async def get_all_panels() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM panels WHERE is_active = 1 ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_panel_by_id(panel_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM panels WHERE id = ?", (panel_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_panel_inbounds(panel_id: int) -> List[Dict]:
    panel = await get_panel_by_id(panel_id)
    if not panel:
        return []
    
    from app.services.xui_client import XUIClient
    client = XUIClient(panel['url'], panel['username'], panel['password'])
    inbounds = await client.get_inbounds()
    if inbounds:
        return [{"id": ib.id, "remark": ib.remark, "protocol": ib.protocol, "port": ib.port} for ib in inbounds]
    return []

async def add_panel(name: str, url: str, username: str, password: str, show_in_bot: bool = True, selected_inbounds: str = '[]', max_slots: int = 0, sub_url: str = '') -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO panels (name, url, username, password, show_in_bot, selected_inbounds, max_slots, sub_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, url, username, password, show_in_bot, selected_inbounds, max_slots, sub_url)
        )
        await db.commit()
        return cursor.lastrowid

async def delete_panel(panel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM panels WHERE id = ?", (panel_id,))
        await db.commit()

async def update_panel_show_status(panel_id: int, show_in_bot: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE panels SET show_in_bot = ? WHERE id = ?", (show_in_bot, panel_id))
        await db.commit()

async def update_panel_inbounds(panel_id: int, selected_inbounds: List[int]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE panels SET selected_inbounds = ? WHERE id = ?",
            (json.dumps(selected_inbounds), panel_id)
        )
        await db.commit()

async def update_panel_max_slots(panel_id: int, max_slots: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE panels SET max_slots = ? WHERE id = ?", (max_slots, panel_id))
        await db.commit()

async def get_active_users_count(panel_id: int, inbound_id: int) -> int:
    panel = await get_panel_by_id(panel_id)
    if not panel:
        return 0
    
    from app.services.xui_client import XUIClient
    client = XUIClient(panel['url'], panel['username'], panel['password'])
    inbounds = await client.get_inbounds()
    
    if not inbounds:
        return 0
    
    for inbound in inbounds:
        if inbound.id == inbound_id:
            active_count = 0
            for client_obj in inbound.clients:
                if not client_obj.is_expired and client_obj.enable:
                    active_count += 1
            return active_count
    
    return 0

# ============================================================
# Services CRUD operations
# ============================================================

async def get_all_services() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM services WHERE is_active = 1 ORDER BY sort_order")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_service_by_id(service_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def add_service(name: str, traffic_gb: int, price_toman: int, expiry_days: int, sort_order: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO services (name, traffic_gb, price_toman, expiry_days, sort_order) VALUES (?, ?, ?, ?, ?)",
            (name, traffic_gb, price_toman, expiry_days, sort_order)
        )
        await db.commit()
        return cursor.lastrowid

async def delete_service(service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM services WHERE id = ?", (service_id,))
        await db.commit()

# ============================================================
# Payment Links operations
# ============================================================

async def get_all_payment_links() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM payment_links ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_payment_links_by_service(service_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM payment_links WHERE service_id = ? AND is_active = 1", (service_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_payment_link_by_id(link_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM payment_links WHERE id = ?", (link_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def add_payment_link(service_id: int, service_name: str, panel_id: int, inbound_id: int, link: str, price_toman: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO payment_links (service_id, service_name, panel_id, inbound_id, link, price_toman) VALUES (?, ?, ?, ?, ?, ?)",
            (service_id, service_name, panel_id, inbound_id, link, price_toman)
        )
        await db.commit()
        return cursor.lastrowid

async def delete_payment_link(link_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM payment_links WHERE id = ?", (link_id,))
        await db.commit()

async def update_payment_link_status(link_id: int, is_active: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payment_links SET is_active = ? WHERE id = ?", (is_active, link_id))
        await db.commit()

# ============================================================
# Receipts operations
# ============================================================

async def create_receipt(user_id: str, username: str, payment_link_id: int, receipt_text: str, receipt_image: str = None, 
                         service_name: str = "", service_traffic: int = 0, service_price: int = 0, service_expiry: int = 0,
                         panel_name: str = "", inbound_name: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO payment_receipts 
            (user_id, username, payment_link_id, receipt_text, receipt_image, 
             service_name, service_traffic, service_price, service_expiry, panel_name, inbound_name, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (user_id, username, payment_link_id, receipt_text, receipt_image, 
             service_name, service_traffic, service_price, service_expiry, panel_name, inbound_name)
        )
        await db.commit()
        return cursor.lastrowid

async def get_pending_receipts() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM payment_receipts WHERE status = 'pending' ORDER BY created_at")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_receipt_by_id(receipt_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM payment_receipts WHERE id = ?", (receipt_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def update_receipt_status(receipt_id: int, status: str, admin_message: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if admin_message:
            await db.execute(
                "UPDATE payment_receipts SET status = ?, admin_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, admin_message, receipt_id)
            )
        else:
            await db.execute(
                "UPDATE payment_receipts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, receipt_id)
            )
        await db.commit()

# ============================================================
# Help and Warning operations
# ============================================================

async def get_help_settings() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM help_settings ORDER BY id DESC LIMIT 1")
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return {"description": "", "link": "", "install_link": ""}

async def update_help_settings(description: str, link: str, install_link: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO help_settings (id, description, link, install_link, updated_at) VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)",
            (description, link, install_link)
        )
        await db.commit()

async def get_warning_message() -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT message FROM warning_messages ORDER BY id DESC LIMIT 1")
        row = await cursor.fetchone()
        return row[0] if row else ""

async def update_warning_message(message: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO warning_messages (id, message, updated_at) VALUES (1, ?, CURRENT_TIMESTAMP)",
            (message,)
        )
        await db.commit()

# ============================================================
# User Counter operations
# ============================================================

async def get_next_user_number() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS user_counter (id INTEGER PRIMARY KEY, last_number INTEGER DEFAULT 0)")
        await db.execute("INSERT OR IGNORE INTO user_counter (id, last_number) VALUES (1, 0)")
        
        cursor = await db.execute("SELECT last_number FROM user_counter WHERE id = 1")
        result = await cursor.fetchone()
        current = result[0] if result else 0
        new_number = current + 1
        await db.execute("UPDATE user_counter SET last_number = ? WHERE id = 1", (new_number,))
        await db.commit()
        return new_number

# ============================================================
# Purchase operations (for online payment)
# ============================================================

async def create_purchase(user_id: str, panel_id: int, inbound_id: int, service_id: int, email: str, amount: int, authority: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO purchases (user_id, panel_id, inbound_id, service_id, email, amount, authority, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
            (user_id, panel_id, inbound_id, service_id, email, amount, authority)
        )
        await db.commit()
        return cursor.lastrowid

async def update_purchase_status(authority: str, status: str, ref_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if ref_id:
            await db.execute(
                "UPDATE purchases SET status = ?, ref_id = ?, updated_at = CURRENT_TIMESTAMP WHERE authority = ?",
                (status, ref_id, authority)
            )
        else:
            await db.execute(
                "UPDATE purchases SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE authority = ?",
                (status, authority)
            )
        await db.commit()

async def get_purchase_by_authority(authority: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM purchases WHERE authority = ?", (authority,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ============================================================
# Transaction and Stats functions
# ============================================================

async def add_transaction(user_id: str, user_username: str, trans_type: str, status: str, 
                          amount: int, package_name: str = "", panel_name: str = "", 
                          email: str = "", admin_message: str = "") -> int:
    """Add a transaction record"""
    import jdatetime 
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO transactions 
            (user_id, user_username, type, status, amount, package_name, panel_name, email, admin_message) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, user_username, trans_type, status, amount, package_name, panel_name, email, admin_message)
        )
        await db.commit()
        
        # Update daily stats
        today = jdatetime.datetime.now().strftime('%Y-%m-%d')
        
        # Check if today's stats exist
        cursor = await db.execute("SELECT id FROM daily_stats WHERE date = ?", (today,))
        row = await cursor.fetchone()
        
        if row:
            if trans_type == 'purchase' and status == 'approved':
                await db.execute(
                    "UPDATE daily_stats SET total_sales = total_sales + 1, total_amount = total_amount + ?, new_users_count = new_users_count + 1 WHERE date = ?",
                    (amount, today)
                )
            elif trans_type == 'renewal' and status == 'approved':
                await db.execute(
                    "UPDATE daily_stats SET total_sales = total_sales + 1, total_amount = total_amount + ?, renewals_count = renewals_count + 1 WHERE date = ?",
                    (amount, today)
                )
        else:
            if trans_type == 'purchase' and status == 'approved':
                await db.execute(
                    "INSERT INTO daily_stats (date, total_sales, total_amount, new_users_count) VALUES (?, 1, ?, 1)",
                    (today, amount)
                )
            elif trans_type == 'renewal' and status == 'approved':
                await db.execute(
                    "INSERT INTO daily_stats (date, total_sales, total_amount, renewals_count) VALUES (?, 1, ?, 1)",
                    (today, amount)
                )
            else:
                await db.execute(
                    "INSERT INTO daily_stats (date, total_sales, total_amount) VALUES (?, 0, 0)",
                    (today,)
                )
        
        return cursor.lastrowid

async def get_transactions(limit: int = 100, offset: int = 0, status: str = None, trans_type: str = None) -> List[Dict]:
    """Get transaction history"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM transactions"
        params = []
        
        conditions = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if trans_type:
            conditions.append("type = ?")
            params.append(trans_type)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_transactions_count(status: str = None, trans_type: str = None) -> int:
    """Get total count of transactions"""
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT COUNT(*) FROM transactions"
        params = []
        
        conditions = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if trans_type:
            conditions.append("type = ?")
            params.append(trans_type)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        cursor = await db.execute(query, params)
        result = await cursor.fetchone()
        return result[0] if result else 0

async def get_stats(period: str = "daily") -> Dict:
    """Get statistics for dashboard"""
    import jdatetime
    import calendar

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Get total stats from transactions table
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total_transactions,
                SUM(amount) as total_amount,
                SUM(CASE WHEN type='purchase' THEN 1 ELSE 0 END) as total_purchases,
                SUM(CASE WHEN type='purchase' THEN amount ELSE 0 END) as total_purchase_amount,
                SUM(CASE WHEN type='renewal' THEN 1 ELSE 0 END) as total_renewals,
                SUM(CASE WHEN type='renewal' THEN amount ELSE 0 END) as total_renewal_amount
            FROM transactions WHERE status='approved'
        """)
        total_stats = await cursor.fetchone()

        now = jdatetime.datetime.now()
        stats = []

        if period == "daily":
            # Last 30 days (using solar date directly)
            for i in range(30):
                date = (now - jdatetime.timedelta(days=i)).strftime('%Y-%m-%d')

                # Query daily_stats with solar date
                cursor = await db.execute(
                    "SELECT total_sales, total_amount, renewals_count, new_users_count FROM daily_stats WHERE date = ?",
                    (date,)
                )
                row = await cursor.fetchone()

                if row:
                    stats.append({
                        "date": date,
                        "sales": row["total_sales"] or 0,
                        "amount": row["total_amount"] or 0,
                        "renewals": row["renewals_count"] or 0,
                        "new_users": row["new_users_count"] or 0
                    })
                else:
                    # If no daily_stats, calculate from transactions
                    # Convert solar date to Gregorian for transaction query
                    try:
                        year, month, day = map(int, date.split('-'))
                        gregorian_date = jdatetime.date(year, month, day).togregorian()
                        greg_date_str = gregorian_date.strftime('%Y-%m-%d')

                        cursor2 = await db.execute("""
                            SELECT
                                COUNT(*) as sales,
                                SUM(amount) as amount,
                                SUM(CASE WHEN type='renewal' THEN 1 ELSE 0 END) as renewals
                            FROM transactions
                            WHERE status='approved' AND date(created_at) = date(?)
                        """, (greg_date_str,))
                        row2 = await cursor2.fetchone()

                        stats.append({
                            "date": date,
                            "sales": row2["sales"] or 0 if row2 else 0,
                            "amount": row2["amount"] or 0 if row2 else 0,
                            "renewals": row2["renewals"] or 0 if row2 else 0,
                            "new_users": row2["sales"] or 0 if row2 else 0
                        })
                    except:
                        stats.append({
                            "date": date,
                            "sales": 0,
                            "amount": 0,
                            "renewals": 0,
                            "new_users": 0
                        })
            stats.reverse()

        elif period == "monthly":
            # Last 12 months
            for i in range(12):
                year = now.year
                month = now.month - i
                if month <= 0:
                    month += 12
                    year -= 1
                month_name = calendar.month_name[month]
                month_str = f"{year}-{month:02d}"

                # Query daily_stats with solar date pattern
                cursor = await db.execute("""
                    SELECT
                        SUM(total_sales) as sales,
                        SUM(total_amount) as amount,
                        SUM(renewals_count) as renewals,
                        SUM(new_users_count) as new_users
                    FROM daily_stats WHERE date LIKE ?
                """, (f"{month_str}%",))
                row = await cursor.fetchone()

                if row and (row["sales"] or 0) > 0:
                    stats.append({
                        "date": f"{month_name} {year}",
                        "sales": row["sales"] or 0,
                        "amount": row["amount"] or 0,
                        "renewals": row["renewals"] or 0,
                        "new_users": row["new_users"] or 0
                    })
                else:
                    stats.append({
                        "date": f"{month_name} {year}",
                        "sales": 0,
                        "amount": 0,
                        "renewals": 0,
                        "new_users": 0
                    })
            stats.reverse()

        else:  # yearly
            # Last 5 years
            for i in range(5):
                year = now.year - i

                cursor = await db.execute("""
                    SELECT
                        SUM(total_sales) as sales,
                        SUM(total_amount) as amount,
                        SUM(renewals_count) as renewals,
                        SUM(new_users_count) as new_users
                    FROM daily_stats WHERE date LIKE ?
                """, (f"{year}%",))
                row = await cursor.fetchone()

                if row and (row["sales"] or 0) > 0:
                    stats.append({
                        "date": str(year),
                        "sales": row["sales"] or 0,
                        "amount": row["amount"] or 0,
                        "renewals": row["renewals"] or 0,
                        "new_users": row["new_users"] or 0
                    })
                else:
                    stats.append({
                        "date": str(year),
                        "sales": 0,
                        "amount": 0,
                        "renewals": 0,
                        "new_users": 0
                    })
            stats.reverse()

        return {
            "total": {
                "transactions": total_stats["total_transactions"] or 0,
                "amount": total_stats["total_amount"] or 0,
                "purchases": total_stats["total_purchases"] or 0,
                "renewals": total_stats["total_renewals"] or 0
            },
            "stats": stats
        }
