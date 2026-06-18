# app/utils/helpers.py
import re
from typing import Tuple

def detect_operator(email: str) -> str:
    """
    Detect mobile operator from email address
    Returns: 'ایرانسل', 'رایتل', 'همراه اول', or 'نامشخص'
    """
    email_lower = email.lower()
    
    irancell_keywords = ['irancell', 'mci', 'همراه', 'hamrah']
    rightel_keywords = ['rightel', 'رایتل']
    hamrah_keywords = ['hamrah', 'mcc', 'همراه اول']
    
    for keyword in irancell_keywords:
        if keyword in email_lower:
            return "ایرانسل"
    
    for keyword in rightel_keywords:
        if keyword in email_lower:
            return "رایتل"
    
    for keyword in hamrah_keywords:
        if keyword in email_lower:
            return "همراه اول"
    
    return "نامشخص"

def get_operator_status_message(operator: str) -> str:
    """
    Get status message for each operator
    Returns Persian message about operator status
    """
    messages = {
        "ایرانسل": "⚠️ این اپراتور در حال حاضر **دارای اختلال** است",
        "رایتل": "⚠️ این اپراتور در حال حاضر **دارای اختلال** است",
        "همراه اول": "✅ این اپراتور **پایدار** است",
        "نامشخص": "ℹ️ وضعیت اپراتور قابل تشخیص نیست"
    }
    return messages.get(operator, messages["نامشخص"])

def format_bytes(bytes_value: int) -> str:
    """Convert bytes to human readable format (GB/MB)"""
    gb = bytes_value / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.2f} GB"
    mb = bytes_value / (1024 ** 2)
    return f"{mb:.2f} MB"

def is_operator_blocked(operator: str) -> bool:
    """Check if operator is currently blocked/having issues"""
    blocked = ["ایرانسل", "رایتل"]
    return operator in blocked
