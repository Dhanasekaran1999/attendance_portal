# app/utils/date_utils.py

from datetime import date, datetime

def format_date(d):
    """Convert date to dd-mm-yyyy format"""
    if isinstance(d, (date, datetime)):
        return d.strftime('%d-%m-%Y')
    return d