# cache_ma.py
import shelve
import os
from datetime import datetime, timedelta

CACHE_FILE = "ma_cache.db"
DAYS_TO_EXPIRE = 15

def save_in_cache(cache_key, cache_key_value):
    with shelve.open(CACHE_FILE, writeback=True) as cache:
        cache[cache_key] = {
            "timestamp": datetime.now().isoformat(),
            "data": cache_key_value
        }

def get_data_from_cache(cache_key):
    with shelve.open(CACHE_FILE) as cache:
        item = cache.get(cache_key)
        if not item:
            return None
        cache_key_date = datetime.fromisoformat(item["timestamp"])
        if datetime.now() - cache_key_date > timedelta(days = DAYS_TO_EXPIRE):
            print(f"🧹 Expired Cache for key: {cache_key}")
            delete_from_cache(cache_key)
            return None
        print(f"📦 Valid Cache for key: {cache_key}")
        return item["data"]

def delete_from_cache(cache_key):
    with shelve.open(CACHE_FILE, writeback=True) as cache:
        if cache_key in cache:
            del cache[cache_key]

def cleanup_expired_cache():
    with shelve.open(CACHE_FILE, writeback=True) as cache:
        cache_keys_to_delete = []
        for cache_key, item in cache.items():
            fecha = datetime.fromisoformat(item.get("timestamp", "1970-01-01T00:00:00"))
            if datetime.now() - fecha > timedelta(days = DAYS_TO_EXPIRE):
                cache_keys_to_delete.append(cache_key)
        for cache_key in cache_keys_to_delete:
            print(f"🧹 Cleaning up expired Cache: {cache_key}")
            del cache[cache_key]