# app/api/admin/helpers.py
import random
import string
import time

def generate_subid():
    """Generate unique subId with timestamp + random chars"""
    timestamp_part = hex(int(time.time() * 1000))[2:]
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{timestamp_part}{random_part}"[:16]
