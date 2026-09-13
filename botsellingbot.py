#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════
#   𝗖𝗢𝗗𝗜𝗡𝗚_𝗝𝗔𝗠𝗘𝗦 𝗣𝗔𝗜𝗗 𝗭𝗢𝗡𝗘 — 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗦𝗛𝗢𝗣 𝗕𝗢𝗧
#   Developer: @coderjamesx  |  Firebase: bot-script-sell
# ═══════════════════════════════════════════════════════════════

import os
import sys
import html
import logging
import asyncio
import re
import json
import time
import copy
import threading
import queue
import urllib.request
import urllib.error
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any, List

try:
    import firebase_admin
    from firebase_admin import credentials, db
    HAS_FIREBASE_ADMIN = True
except ImportError:
    firebase_admin = None
    credentials = None
    db = None
    HAS_FIREBASE_ADMIN = False

import telegram.error
from telegram import (
    Update, InlineKeyboardButton as _OrigInlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton as _OrigKeyboardButton, ReplyKeyboardRemove,
    BotCommand, MenuButtonCommands,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN         = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS_RAW     = os.environ.get("ADMIN_ID", os.environ.get("ADMIN_IDS", ""))
ADMIN_USERNAME    = os.environ.get("ADMIN_USERNAME", "@lord_ciph3r")

# Embedded Firebase Web & Cloud Configuration
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyBD2aXB98P2Fjc6HndfZvANIU5u6vpv2gY",
    "authDomain": "bot-script-sell.firebaseapp.com",
    "projectId": "bot-script-sell",
    "storageBucket": "bot-script-sell.firebasestorage.app",
    "messagingSenderId": "206856426710",
    "appId": "1:206856426710:web:77aa6b9a06b91f3170a577",
    "measurementId": "G-LDYHSB6K1D",
}

FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", FIREBASE_CONFIG["projectId"])
FIREBASE_API_KEY    = os.environ.get("FIREBASE_API_KEY", FIREBASE_CONFIG["apiKey"])
FIREBASE_URL        = os.environ.get("FIREBASE_URL", f"https://{FIREBASE_PROJECT_ID}-default-rtdb.firebaseio.com")
FIREBASE_AUTH_KEY   = os.environ.get("FIREBASE_AUTH_KEY", os.environ.get("FIREBASE_SECRET", FIREBASE_API_KEY))
SERVICE_KEY         = os.environ.get("SERVICE_KEY", "serviceAccountKey.json")

# Parse comma-separated ADMIN_IDs
ADMIN_IDS = set()
for _part in re.split(r"[,;:\s]+", str(ADMIN_IDS_RAW).strip()):
    if _part.isdigit():
        ADMIN_IDS.add(int(_part))
if not ADMIN_IDS:
    ADMIN_IDS.add(8065173971)
ADMIN_ID = list(ADMIN_IDS)[0]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BUTTON COLOR BADGE SYSTEM & BOT INSTANCE REGISTRY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_global_bot = None

def get_bot_instance(target=None, ctx=None):
    """Safely retrieves active Telegram Bot instance across all contexts & updates."""
    global _global_bot
    if ctx and hasattr(ctx, "bot") and ctx.bot:
        _global_bot = ctx.bot
        return ctx.bot
    if target:
        if hasattr(target, "bot") and target.bot:
            _global_bot = target.bot
            return target.bot
        if hasattr(target, "message") and target.message and hasattr(target.message, "bot") and target.message.bot:
            _global_bot = target.message.bot
            return target.message.bot
        if hasattr(target, "_bot") and target._bot:
            _global_bot = target._bot
            return target._bot
    return _global_bot

def _find_button_style(text: str) -> str:
    if not text:
        return "secondary"
    t = text.lower()
    
    # ⚪ Navigation:
    if any(k in t for k in ["back to", "back", "English", "English", "English", "home", "English", "menu", "Menu", "⬅️", "🏠"]):
        return "nav"
        
    # 🔴 Danger / Reject / Cancel / Delete:
    if any(k in t for k in [
        "cancel", "Cancel", "reject", "Reject", "remove", "Remove", "delete", "Delete",
        "ban", "English", "kick", "close panel", "Close panel", "reset", "English", "off", "Off",
        "All Balance English", "⛔", "❌", "🗑️"
    ]):
        return "danger"
        
    # 🟡 Warning & Withdraw:
    if any(k in t for k in [
        "withdraw", "English", "English", "pending", "English", "shortage", "English", "Pending", "⏳", "⚠️"
    ]):
        return "warning"
        
    # 🟣 Admin & Settings & Support:
    if any(k in t for k in [
        "admin", "Admin", "owner", "English", "manager", "English", "role", "English",
        "setting", "Settings", "broadcast", "English", "btnmgr", "Button manager",
        "button manager", "support", "Support", "👑", "⚙️", "🎛️", "🆘"
    ]):
        return "admin"
        
    # 🟠 Shop & Products:
    if any(k in t for k in [
        "buy product", "my product", "shop", "Shop", "product", "Product", "Product", "script", "English",
        "category", "Category", "stock", "Stock", "My products", "📦", "🛒", "📁"
    ]):
        return "shop"

    # 🟢 Success & Deposit & Payment:
    if any(k in t for k in [
        "approve", "Approve", "Approve", "confirm", "Confirm", "submit", "Submit",
        "deposit", "Deposit", "USD English", "buy now", "Buy", "add", "English", "New",
        "earn", "English", "active", "Online", "on", "English", "On", "verify", "Verify",
        "done", "Completed", "pay", "Payment", "Payment", "Payment", "Payment", "bkash", "nagad", "rocket", "binance",
        "✅", "🟢", "💰", "💎"
    ]):
        return "success"

    # 🔵 Secondary / Profile / Refer / Info / Check Data:
    return "secondary"

def strip_button_balls(text: str) -> str:
    """Strip any colored circle/ball emojis from button text to maintain clean styling."""
    if not text:
        return "" if text is None else str(text)
    text_s = str(text).strip()
    ball_emojis = ["🟢", "🔴", "🟡", "🔵", "🟣", "🟠", "⚪", "⚫"]
    changed = True
    while changed:
        changed = False
        for ball in ball_emojis:
            if text_s.startswith(ball):
                text_s = text_s[len(ball):].strip()
                changed = True
    return text_s

def colorize_button_text(text: str, color: str = None) -> str:
    """Apply consistent red, blue, or green visual status badges to buttons."""
    clean = strip_button_balls(text)
    style = color or _find_button_style(clean)
    badge = {"danger": "🔴", "warning": "🔴", "success": "🟢", "shop": "🟢", "nav": "🔵", "admin": "🔵", "secondary": "🔵"}.get(style, "🔵")
    return f"{badge} {clean}" if clean else badge

class InlineKeyboardButton(_OrigInlineKeyboardButton):
    """Inline button with a red, blue, or green visual status badge."""
    def __init__(self, text: str, *args, color: str = None, **kwargs):
        styled = colorize_button_text(text, color)
        super().__init__(styled, *args, **kwargs)

class KeyboardButton(_OrigKeyboardButton):
    """Persistent menu button with a red, blue, or green visual status badge."""
    def __init__(self, text: str, *args, color: str = None, **kwargs):
        styled = colorize_button_text(text, color)
        super().__init__(styled, *args, **kwargs)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LOGGING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FIREBASE INITIALIZATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
firebase_app = None
if HAS_FIREBASE_ADMIN:
    try:
        if os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
            service_account_dict = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
            cred = credentials.Certificate(service_account_dict)
            firebase_app = firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})
            logger.info(f"✅ Firebase initialized with environment service account for: {FIREBASE_URL}")
        elif os.path.exists(SERVICE_KEY):
            cred = credentials.Certificate(SERVICE_KEY)
            firebase_app = firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})
            logger.info(f"✅ Firebase initialized with certificate file '{SERVICE_KEY}' for: {FIREBASE_URL}")
        else:
            logger.warning(
                f"ℹ️ Certificate file '{SERVICE_KEY}' not found. "
                f"Running high-speed in-memory engine with local persistence & auto Firebase REST sync."
            )
    except Exception as e:
        logger.error(f"❌ Failed to initialize Firebase Admin SDK: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HIGH-SPEED IN-MEMORY + BACKGROUND SYNC STORAGE ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOCAL_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_data.json")

# In-Memory primary store (sub-millisecond instant reads/writes)
_MEM_CACHE: Dict[str, Any] = {}
_cache_lock = threading.RLock()
_sync_queue: queue.Queue = queue.Queue(maxsize=5000)
_disk_save_pending = False
_threads_started = False

_firebase_status = {
    "mode": "Firebase Admin SDK" if firebase_app else ("Firebase REST" if FIREBASE_URL else "Local High-Speed Storage"),
    "connected": False,
    "last_check": None,
    "latency_ms": None,
    "diagnostic": "Checking...",
    "url": FIREBASE_URL,
}

def _get_path_parts(path: str) -> list:
    return [p for p in str(path).strip("/").split("/") if p]

def _load_local_store() -> dict:
    if os.path.exists(LOCAL_DB_FILE):
        try:
            with open(LOCAL_DB_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.error(f"Error reading {LOCAL_DB_FILE}: {e}")
    return {}

def _save_local_store_atomic(data: dict):
    try:
        tmp_file = LOCAL_DB_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, LOCAL_DB_FILE)
    except Exception as e:
        logger.error(f"Error atomic saving {LOCAL_DB_FILE}: {e}")

def _disk_saver_loop():
    global _disk_save_pending
    while True:
        try:
            time.sleep(1.0)
            if _disk_save_pending:
                with _cache_lock:
                    data_copy = copy.deepcopy(_MEM_CACHE)
                    _disk_save_pending = False
                _save_local_store_atomic(data_copy)
        except Exception as e:
            logger.debug(f"Disk saver loop exception: {e}")

def _firebase_rest_req(method: str, path: str, data=None, timeout: float = 3.0):
    if not FIREBASE_URL or not FIREBASE_URL.startswith("http"):
        return None
    url = f"{FIREBASE_URL.rstrip('/')}/{path.strip('/')}.json"
    if FIREBASE_AUTH_KEY:
        url += f"?auth={FIREBASE_AUTH_KEY}"
    try:
        req = urllib.request.Request(url, method=method.upper())
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "JamesShopBot/2.0")
        body = json.dumps(data).encode("utf-8") if data is not None else None
        with urllib.request.urlopen(req, data=body, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            if resp_body and resp_body != "null":
                try:
                    return json.loads(resp_body)
                except Exception:
                    return True
            return True
    except urllib.error.HTTPError as he:
        logger.debug(f"Firebase REST {method} HTTP {he.code} for {url}: {he}")
        return {"_http_error": he.code, "_msg": str(he)}
    except Exception as e:
        logger.debug(f"Firebase REST {method} note: {e}")
        return None

def check_firebase_health() -> dict:
    t0 = time.time()
    info = {
        "connected": False,
        "mode": "🟢 Firebase Admin SDK" if firebase_app else "🟡 Firebase REST API",
        "url": FIREBASE_URL,
        "latency_ms": None,
        "diagnostic": "",
    }
    if firebase_app and HAS_FIREBASE_ADMIN:
        try:
            db.reference("_health").set({"last_ping": datetime.now().isoformat()})
            latency = round((time.time() - t0) * 1000, 1)
            info["connected"] = True
            info["latency_ms"] = latency
            info["diagnostic"] = f"🟢 Admin SDK Connected ({latency}ms)"
        except Exception as e:
            info["diagnostic"] = f"⚠️ Admin SDK error: {e}"
    elif FIREBASE_URL and FIREBASE_URL.startswith("http"):
        res = _firebase_rest_req("GET", "settings", timeout=2.5)
        latency = round((time.time() - t0) * 1000, 1)
        info["latency_ms"] = latency
        if isinstance(res, dict) and "_http_error" in res:
            code = res["_http_error"]
            if code == 404:
                info["diagnostic"] = f"🔴 404 Not Found — Check database URL in .env / settings"
            elif code in (401, 403):
                info["diagnostic"] = f"🟡 401/403 Permission Denied — Update Realtime Database Rules or add serviceAccountKey.json"
            else:
                info["diagnostic"] = f"⚠️ HTTP {code} Error"
        elif res is not None:
            info["connected"] = True
            info["diagnostic"] = f"🟢 REST API Connected ({latency}ms)"
        else:
            info["diagnostic"] = "⚠️ Unreachable (Timeout or DNS error)"
    else:
        info["mode"] = "🟢 Local High-Speed Storage (Active)"
        info["connected"] = True
        info["diagnostic"] = "🟢 Local database running at 0ms latency"
    
    _firebase_status.update(info)
    _firebase_status["last_check"] = datetime.now().strftime("%H:%M:%S")
    return info

def _firebase_sync_loop():
    while True:
        try:
            item = _sync_queue.get()
            if item is None:
                break
            method, path, data = item
            if firebase_app and HAS_FIREBASE_ADMIN:
                try:
                    ref = db.reference(path)
                    if method == "PUT":
                        ref.set(data)
                    elif method == "PATCH":
                        ref.update(data)
                    elif method == "DELETE":
                        ref.delete()
                except Exception as e:
                    logger.debug(f"Background Admin SDK sync error {path}: {e}")
            elif FIREBASE_URL and FIREBASE_URL.startswith("http"):
                _firebase_rest_req(method, path, data, timeout=2.5)
            _sync_queue.task_done()
        except Exception as e:
            logger.debug(f"Firebase sync worker note: {e}")

def _enqueue_firebase_sync(method: str, path: str, data=None):
    try:
        _sync_queue.put_nowait((method, path, data))
    except queue.Full:
        try:
            _sync_queue.get_nowait()
            _sync_queue.put_nowait((method, path, data))
        except Exception:
            pass

def fb_get(path: str, default=None):
    """Ultra-fast O(1) in-memory lookup (<0.01ms)"""
    with _cache_lock:
        parts = _get_path_parts(path)
        if not parts:
            return copy.deepcopy(_MEM_CACHE) if _MEM_CACHE else default
        curr = _MEM_CACHE
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return default
        if isinstance(curr, (dict, list)):
            return copy.deepcopy(curr)
        return curr

def fb_set(path: str, data: Any):
    """Ultra-fast in-memory update with non-blocking background disk & Firebase sync"""
    global _disk_save_pending
    with _cache_lock:
        parts = _get_path_parts(path)
        if not parts:
            if isinstance(data, dict):
                _MEM_CACHE.clear()
                _MEM_CACHE.update(copy.deepcopy(data))
        else:
            curr = _MEM_CACHE
            for p in parts[:-1]:
                if p not in curr or not isinstance(curr[p], dict):
                    curr[p] = {}
                curr = curr[p]
            curr[parts[-1]] = copy.deepcopy(data)
        _disk_save_pending = True
        try:
            _save_local_store_atomic(_MEM_CACHE)
        except Exception:
            pass
    _enqueue_firebase_sync("PUT", path, data)
    return True

def fb_update(path: str, update_dict: dict):
    """Ultra-fast in-memory partial update with non-blocking background sync"""
    global _disk_save_pending
    if not isinstance(update_dict, dict):
        return fb_set(path, update_dict)
    with _cache_lock:
        parts = _get_path_parts(path)
        curr = _MEM_CACHE
        for p in parts:
            if p not in curr or not isinstance(curr[p], dict):
                curr[p] = {}
            curr = curr[p]
        if isinstance(curr, dict):
            curr.update(copy.deepcopy(update_dict))
        _disk_save_pending = True
        try:
            _save_local_store_atomic(_MEM_CACHE)
        except Exception:
            pass
    _enqueue_firebase_sync("PATCH", path, update_dict)
    return True

def fb_push(path: str, data: Any):
    push_id = f"-M{int(datetime.now().timestamp() * 1000)}"
    full_path = f"{path.strip('/')}/{push_id}"
    fb_set(full_path, data)
    return type("PushResult", (), {"key": push_id})()

def fb_delete(path: str):
    global _disk_save_pending
    with _cache_lock:
        parts = _get_path_parts(path)
        if not parts:
            _MEM_CACHE.clear()
        else:
            curr = _MEM_CACHE
            for p in parts[:-1]:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                else:
                    curr = None
                    break
            if isinstance(curr, dict) and parts[-1] in curr:
                del curr[parts[-1]]
        _disk_save_pending = True
        try:
            _save_local_store_atomic(_MEM_CACHE)
        except Exception:
            pass
    _enqueue_firebase_sync("DELETE", path, None)
    return True

def init_db():
    """Initializes local storage into memory, starts worker threads, and tests Firebase."""
    global _threads_started
    # 1. Load local store into memory cache
    data = _load_local_store()
    with _cache_lock:
        _MEM_CACHE.clear()
        _MEM_CACHE.update(data)
    logger.info(f"💾 Loaded {_MEM_CACHE.__len__()} root keys from local storage into memory cache.")

    # 2. Start background worker threads
    if not _threads_started:
        threading.Thread(target=_disk_saver_loop, daemon=True, name="DiskSaverThread").start()
        threading.Thread(target=_firebase_sync_loop, daemon=True, name="FirebaseSyncThread").start()
        _threads_started = True

    # 3. Background non-blocking Firebase health check & initial sync
    def _initial_sync_worker():
        health = check_firebase_health()
        logger.info(f"🔥 Firebase Status: {health['diagnostic']}")
        if health.get("connected"):
            try:
                remote_data = None
                if firebase_app and HAS_FIREBASE_ADMIN:
                    remote_data = db.reference("/").get()
                elif FIREBASE_URL and FIREBASE_URL.startswith("http"):
                    remote_data = _firebase_rest_req("GET", "", timeout=3.0)
                if isinstance(remote_data, dict) and remote_data:
                    with _cache_lock:
                        for k, v in remote_data.items():
                            if k not in _MEM_CACHE:
                                _MEM_CACHE[k] = v
                    logger.info("✅ Merged existing data from remote Firebase into memory cache.")
            except Exception as e:
                logger.debug(f"Initial remote sync note: {e}")

    threading.Thread(target=_initial_sync_worker, daemon=True, name="InitialSyncThread").start()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  USER BALANCE RESET & AUDIT PERSISTENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def reset_all_user_balances() -> int:
    """Sets all users' balance to 0.0 both in local memory cache and syncs to Firebase."""
    count = 0
    with _cache_lock:
        users = _MEM_CACHE.get("users", {})
        if isinstance(users, dict):
            for uid, udata in users.items():
                if isinstance(udata, dict):
                    udata["balance"] = 0.0
                    count += 1
        _save_local_store_atomic(_MEM_CACHE)
    if isinstance(users, dict) and users:
        _enqueue_firebase_sync("PATCH", "users", {uid: {"balance": 0.0} for uid in users.keys()})
    logger.info(f"⚠️ Reset {count} users balance to 0.0 (Local & Firebase)")
    return count

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DEFAULT SETTINGS (written once if not exist)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def init_defaults():
    settings = fb_get("settings")
    default_main_buttons = {
        "buy_product":   {"label": "BUY PRODUCT",   "icon": "🛒", "enabled": True},
        "deposit_money": {"label": "DEPOSIT MONEY", "icon": "💳", "enabled": True},
        "refer":         {"label": "REFER & EARN",  "icon": "🎁", "enabled": True},
        "my_product":    {"label": "MY PRODUCT",    "icon": "📦", "enabled": True},
        "my_profile":    {"label": "MY PROFILE",    "icon": "👤", "enabled": True},
        "check_data":    {"label": "CHECK DATA",    "icon": "🌐", "enabled": True},
        "support":       {"label": "SUPPORT",       "icon": "🆘", "enabled": True},
        "my_id":         {"label": "MY ID",         "icon": "🆔", "enabled": True},
        "about":         {"label": "ABOUT",         "icon": "ℹ️", "enabled": True},
    }

    if not settings:
        fb_set("settings", {
            "bot_name":           "JAMES 💎",
            "welcome_text":       "𝙒𝙀𝙇𝘾𝙊𝙈𝙀 𝙏𝙊 𝙋𝙍𝙀𝙈𝙄𝙐𝙈 𝙎𝙃𝙊𝙋 𝘽𝙊𝙏",
            "currency_symbol":    "$",
            "currency_name":      "USD",
            "local_currency":     "USD",
            "exchange_rate":      1,            # USD-only pricing
            "referral_pct":       5.0,          # 5% deposit commission
            "referral_bonus_bdt": 10.0,         # 10 USD Instant Signup Bonus per Referral
            "deposit_open":       True,         # DEFAULT: OPEN
            "withdraw_open":      True,
            "min_deposit":        1.0,
            "min_withdraw":       2.0,
            "support_link":       "t.me/CODINGJAMES_X",
            "admin_ids":          list(ADMIN_IDS),
            "force_join_enabled": False,        # Disabled by default so users are not trapped
            "dev_name":           "@CODINGJAMES_X",
            "dev_url":            "@CODINGJAMES_X",
            "main_buttons":       default_main_buttons,
        })
    else:
        # Guarantee deposit is open if not specified
        updates = {}
        curr_bname = settings.get("bot_name", "")
        if any(x in str(curr_bname) for x in ["𝗖𝗢𝗗𝗜𝗡𝗚_𝗝𝗔𝗠𝗘𝗦", "𝗖𝗢𝗗𝗜𝗡𝗚_𝗝𝗔𝗠𝗘𝗦", "𝗖𝗢𝗗𝗜𝗡𝗚_𝗝𝗔𝗠𝗘𝗦"]):
            updates["bot_name"] = "JAMES 💎"
        if "deposit_open" not in settings or settings.get("deposit_open") is False:
            updates["deposit_open"] = True
        if "admin_ids" not in settings:
            updates["admin_ids"] = list(ADMIN_IDS)
        if "force_join_enabled" not in settings:
            updates["force_join_enabled"] = False
        if "referral_bonus_bdt" not in settings:
            updates["referral_bonus_bdt"] = 10.0
        if "dev_name" not in settings:
            updates["dev_name"] = "t.me/CODINGJAMES_X"
            updates["dev_url"] = "t.me/CODINGJAMES_X"
        if "main_buttons" not in settings:
            updates["main_buttons"] = default_main_buttons
        if updates:
            fb_update("settings", updates)

    if fb_get("payment_methods") is None:
        fb_set("payment_methods", {
            "bkash":   {"enabled": True,  "number": "off", "name": "𝗕𝗸𝗮𝘀𝗵"},
            "nagad":   {"enabled": True,  "number": "01619789895", "name": "𝗡𝗮𝗴𝗮𝗱"},
            "rocket":  {"enabled": True,  "number": "01619789895", "name": "𝗥𝗼𝗰𝗸𝗲𝘁"},
            "binance": {"enabled": False, "address": "", "1210169527": "𝗕𝗶𝗻𝗮𝗻𝗰𝗲 𝗨𝗦𝗗𝗧"},
        })

    if fb_get("check_data_links") is None:
        fb_set("check_data_links", {
            "link_1": {"title": "🌐 Bot English English", "url": "https://t.me/PayHosting_bot?start=7831629041"},
            "link_2": {"title": "📺 Bot English English English", "url": "https://youtube.com"},
            "link_3": {"title": "💬 English Support Group", "url": "https://t.me/cipher_tech team"},
        })

    if fb_get("force_join_channels") is None:
        fb_set("force_join_channels", {})

    if fb_get("admins") is None:
        init_admins = {}
        for aid in ADMIN_IDS:
            init_admins[str(aid)] = {
                "id": aid,
                "name": ADMIN_USERNAME,
                "role": "owner",
                "added_at": datetime.now().isoformat()
            }
        fb_set("admins", init_admins)

    # Initial setup complete (Balance reset is controlled via Admin Panel button)

# Initialize DB and defaults on module load
init_db()
init_defaults()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONVERSATION STATES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
(
    ADMIN_MENU, ADMIN_PRODUCTS, ADMIN_ADD_CAT_NAME, ADMIN_ADD_PROD_NAME,
    ADMIN_ADD_PROD_DESC, ADMIN_ADD_PROD_PRICE, ADMIN_ADD_PROD_STOCK,
    ADMIN_EDIT_PROD, ADMIN_SETTINGS_MENU, ADMIN_SET_FIELD,
    ADMIN_PAYMENT_MENU, ADMIN_PAY_FIELD,
    ADMIN_BROADCAST, ADMIN_MANAGE_USERS,
    DEPOSIT_CHOOSE_METHOD, DEPOSIT_ENTER_AMOUNT, DEPOSIT_ENTER_TXID,
    WITHDRAW_ENTER_AMOUNT, WITHDRAW_ENTER_METHOD, WITHDRAW_ENTER_ACCOUNT,
    BUY_CHOOSE_CAT, BUY_CHOOSE_PROD, BUY_CONFIRM,
) = range(23)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEXT STYLES  (𝙎𝙡𝙖𝙣𝙩𝙚𝙙 𝘽𝙤𝙡𝙙)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def sb(text: str) -> str:
    """Slanted Bold Unicode"""
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    slanted_bold = (
        "𝘼𝘽𝘾𝘿𝙀𝙁𝙂𝙃𝙄𝙅𝙆𝙇𝙈𝙉𝙊𝙋𝙌𝙍𝙎𝙏𝙐𝙑𝙒𝙓𝙔𝙕"
        "𝙖𝙗𝙘𝙙𝙚𝙛𝙜𝙝𝙞𝙟𝙠𝙡𝙢𝙣𝙤𝙥𝙦𝙧𝙨𝙩𝙪𝙫𝙬𝙭𝙮𝙯"
        "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    )
    result = ""
    for ch in text:
        idx = normal.find(ch)
        result += slanted_bold[idx] if idx != -1 else ch
    return result

def bold(text: str) -> str:
    return f"<b>{text}</b>"

def divider() -> str:
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━"

def mini_divider() -> str:
    return "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  USER & ROLE HELPERS (RBAC)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_user(uid: int) -> dict:
    return fb_get(f"users/{uid}", {})

def ensure_user(update: Update) -> dict:
    uid = update.effective_user.id
    user = get_user(uid)
    if not user:
        referrer = None
        args = update.message.text.split() if (update.message and update.message.text) else []
        if len(args) > 1 and args[1].isdigit():
            referrer = int(args[1])
        user = {
            "id":         uid,
            "name":       update.effective_user.full_name,
            "username":   update.effective_user.username or "",
            "balance":    0.0,
            "joined":     datetime.now().isoformat(),
            "referrer":   referrer,
            "referrals":  0,
            "verified_referrals": 0,
            "total_earned": 0.0,
            "banned":     False,
        }
        fb_set(f"users/{uid}", user)
        # notify referrer
        if referrer and referrer != uid:
            ref_user = get_user(referrer)
            if ref_user:
                s = get_settings()
                ref_bonus_bdt = float(s.get("referral_bonus_bdt", 10.0))
                rate = float(s.get("exchange_rate", 125))
                bonus_usd = round(ref_bonus_bdt / rate, 4)

                total_refs = (ref_user.get("referrals") or 0) + 1
                curr_bal = float(ref_user.get("balance") or 0.0)
                curr_earned = float(ref_user.get("total_earned") or 0.0)
                new_bal = curr_bal + bonus_usd
                new_earned = curr_earned + bonus_usd

                fb_update(f"users/{referrer}", {
                    "referrals": total_refs,
                    "balance": new_bal,
                    "total_earned": new_earned,
                })

                import asyncio
                async def _notify_ref():
                    try:
                        bot = get_bot_instance(update, None)
                        if bot:
                            import html
                            user_name_esc = html.escape(update.effective_user.full_name or "New Member")
                            await bot.send_message(
                                chat_id=referrer,
                                text=(
                                    f"🎉 <b>English! New Referral English has been!</b>\n"
                                    f"{divider()}\n"
                                    f"👤 New English: {user_name_esc}\n"
                                    f"🎁 <b>Referral EnglishnotEnglish:</b> +{int(ref_bonus_bdt)} USD (${bonus_usd:.2f})\n"
                                    f"💳 <b>Your Current English:</b> ${new_bal:.2f} (~{int(new_bal*rate)} USD)\n"
                                    f"{divider()}\n"
                                    f"🚀 ClosedEnglish More English English and English EnglishnotEnglish English English!"
                                ),
                                parse_mode=ParseMode.HTML
                            )
                    except Exception as e:
                        logger.debug(f"Referral notification note: {e}")
                try:
                    asyncio.create_task(_notify_ref())
                except Exception:
                    pass
    return user

def get_admin_role(uid: int) -> Optional[str]:
    if uid in ADMIN_IDS:
        return "owner"
    admins = fb_get("admins", {})
    if isinstance(admins, dict) and str(uid) in admins:
        return admins[str(uid)].get("role", "viewer")
    s = get_settings()
    extra_admins = s.get("admin_ids", [])
    if uid in extra_admins or str(uid) in extra_admins:
        return "manager"
    user = get_user(uid)
    if user and (user.get("is_admin") or user.get("role") == "admin"):
        return "manager"
    return None

def is_admin(uid: int) -> bool:
    return get_admin_role(uid) is not None

def is_owner(uid: int) -> bool:
    return get_admin_role(uid) == "owner"

def can_manage(uid: int) -> bool:
    return get_admin_role(uid) in ["owner", "manager"]

def get_all_admin_ids() -> list:
    ids = set(ADMIN_IDS)
    admins = fb_get("admins", {})
    if isinstance(admins, dict):
        for aid in admins.keys():
            if str(aid).isdigit():
                ids.add(int(aid))
    s = get_settings()
    for aid in s.get("admin_ids", []):
        if str(aid).isdigit():
            ids.add(int(aid))
    return list(ids)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FORCE JOIN HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_force_join_channels() -> dict:
    chans = fb_get("force_join_channels")
    if chans is None or not isinstance(chans, dict):
        return {}
    return chans

async def safe_edit_text(target, text: str, reply_markup=None, parse_mode=ParseMode.HTML, disable_web_page_preview=True):
    """Safely edits message text or sends a replacement message if the original contained media."""
    bot = get_bot_instance(target, None)
    chat_id = None
    if hasattr(target, "message") and target.message:
        chat_id = target.message.chat_id
    elif hasattr(target, "from_user") and target.from_user:
        chat_id = target.from_user.id
    elif hasattr(target, "chat_id"):
        chat_id = target.chat_id

    try:
        if hasattr(target, "edit_message_text"):
            msg = getattr(target, "message", None)
            if msg and (getattr(msg, "photo", None) or getattr(msg, "video", None) or getattr(msg, "animation", None) or getattr(msg, "document", None)):
                try:
                    await msg.delete()
                except Exception:
                    pass
                if bot and chat_id:
                    return await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup,
                        disable_web_page_preview=disable_web_page_preview
                    )
            return await target.edit_message_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        elif hasattr(target, "reply_text"):
            return await target.reply_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        elif hasattr(target, "message") and hasattr(target.message, "reply_text"):
            return await target.message.reply_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return None
        try:
            if bot and chat_id:
                return await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview
                )
        except Exception as e2:
            logger.debug(f"safe_edit_text fallback error: {e2}")
    return None

async def check_force_join(bot, user_id: int) -> list:
    s = get_settings()
    if not s.get("force_join_enabled", False):
        return []
    if is_admin(user_id):
        return []
    channels = get_force_join_channels()
    if not channels or not isinstance(channels, dict):
        return []
    not_joined = []
    for cid, ch in channels.items():
        if not isinstance(ch, dict):
            continue
        chat_target = ch.get("id") or ch.get("chat_id") or ch.get("username")
        if not chat_target:
            continue
        chat_target_str = str(chat_target).strip()
        # Skip placeholder developer handles or invalid usernames
        if chat_target_str.lower() in [str(ADMIN_USERNAME).lower(), "@bd_top_admin"]:
            continue
        try:
            member = await bot.get_chat_member(chat_id=chat_target_str, user_id=user_id)
            if member and getattr(member, "status", None) in ['left', 'kicked']:
                not_joined.append({"key": cid, **ch})
        except Exception as e:
            # If bot cannot check (not an admin in that channel, channel not found, etc.),
            # do NOT trap users from using the bot!
            logger.debug(f"Force join check member notice for {chat_target_str}: {e}")
            continue
    return not_joined

async def send_force_join_screen(target, not_joined: list, is_edit: bool = False):
    text = (
        f"💡 <b>Join All Channels to Continue</b>\n\n"
        f"Then click ✅ <b>Joined</b>"
    )
    buttons = []
    row = []
    for ch in not_joined:
        name = ch.get("name") or ch.get("title") or "Join ♕"
        url = ch.get("url") or f"https://t.me/{str(ch.get('id','')).replace('@','')}"
        btn = InlineKeyboardButton(name, url=url)
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Green verify button as in screenshot
    buttons.append([InlineKeyboardButton("☠️ verify 🍃 ☠️", callback_data="verify_force_join")])
    kb = InlineKeyboardMarkup(buttons)

    if is_edit:
        await safe_edit_text(target, text, reply_markup=kb)
    elif hasattr(target, "reply_text"):
        await target.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
    elif hasattr(target, "message") and hasattr(target.message, "reply_text"):
        await target.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

def get_settings() -> dict:
    s = fb_get("settings", {})
    if not s or not isinstance(s, dict):
        init_defaults()
        s = fb_get("settings", {})
    return s or {}

def get_payment_methods() -> dict:
    methods = fb_get("payment_methods", {})
    if not methods or not isinstance(methods, dict):
        init_defaults()
        methods = fb_get("payment_methods", {})
    return methods or {}

def parse_clean_amount(text: str) -> float:
    """Safely extracts a numeric amount handling Bengali digits (English-English) and English numbers and currency symbols."""
    bengali_digits = "English"
    s = str(text).strip()
    for i, bd in enumerate(bengali_digits):
        s = s.replace(bd, str(i))
    # Remove common currency terms
    for w in ["tk", "bdt", "usd", "$", "USD", "English", "English"]:
        s = re.sub(re.escape(w), "", s, flags=re.IGNORECASE)
    # Find decimal or integer number
    m = re.search(r"\d+(?:\.\d+)?", s.replace(",", ""))
    if m:
        return float(m.group(0))
    raise ValueError(f"No valid numeric amount found in: '{text}'")

def format_amount(amount: float, settings: dict = None) -> str:
    """Format all user-facing prices as US dollars only."""
    return f"${float(amount):,.2f}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN MENU KEYBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main_menu_keyboard(uid: int = None) -> ReplyKeyboardMarkup:
    keys = []
    if uid and is_admin(uid):
        keys.append([KeyboardButton("⚙️ " + sb("ADMIN PANEL"))])

    s = get_settings()
    mb = s.get("main_buttons", {})

    def is_on(btn_id):
        if not mb or btn_id not in mb:
            return True
        return mb[btn_id].get("enabled", True)

    active_buttons = []
    if is_on("buy_product"):
        active_buttons.append(KeyboardButton(sb("BUY PRODUCT")))
    if is_on("deposit_money"):
        active_buttons.append(KeyboardButton(sb("DEPOSIT MONEY")))
    if is_on("refer"):
        active_buttons.append(KeyboardButton(sb("REFER")))
    if is_on("my_product"):
        active_buttons.append(KeyboardButton(sb("MY PRODUCT")))
    if is_on("my_profile"):
        active_buttons.append(KeyboardButton(sb("MY PROFILE")))
    if is_on("check_data"):
        active_buttons.append(KeyboardButton(sb("CHECK DATA")))
    if is_on("support"):
        active_buttons.append(KeyboardButton(sb("SUPPORT")))
    if is_on("my_id"):
        active_buttons.append(KeyboardButton("🆔 " + sb("MY ID")))
    if is_on("about"):
        active_buttons.append(KeyboardButton("ℹ️ " + sb("ABOUT")))

    for i in range(0, len(active_buttons), 2):
        keys.append(active_buttons[i:i+2])

    return ReplyKeyboardMarkup(keys, resize_keyboard=True, one_time_keyboard=False)

def home_menu_inline(uid: int = None) -> InlineKeyboardMarkup:
    s = get_settings()
    chk_title = s.get("checkdata_button_title", "🌐 CHECK DATA")
    chk_url = s.get("checkdata_button_url")
    rows = [
        [InlineKeyboardButton("🛒 " + sb("BUY PRODUCT"), callback_data="shop"),
         InlineKeyboardButton("💳 " + sb("DEPOSIT MONEY"), callback_data="deposit")],
        [InlineKeyboardButton("👤 " + sb("MY PROFILE"), callback_data="profile"),
         InlineKeyboardButton("📦 " + sb("MY PRODUCT"), callback_data="my_products")],
        [InlineKeyboardButton("🎁 " + sb("REFER & EARN"), callback_data="refer"),
         InlineKeyboardButton("ℹ️ " + sb("ABOUT"), callback_data="about_dev")]
    ]
    if chk_url:
        rows.append([InlineKeyboardButton(chk_title, url=chk_url)])
    else:
        rows.append([InlineKeyboardButton(chk_title, callback_data="check_data")])
    rows.append([InlineKeyboardButton("🆘 " + sb("SUPPORT"), callback_data="support")])
    if uid and is_admin(uid):
        rows.append([InlineKeyboardButton("👑 " + sb("ADMIN PANEL"), callback_data="adm_panel")])
    return InlineKeyboardMarkup(rows)

def home_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        "🏠 " + sb("Home"), callback_data="home")]])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /id and /myid
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def my_id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = html.escape(update.effective_user.full_name or "")
    username = f"@{update.effective_user.username}" if update.effective_user.username else "None"
    admin_status = "👑 <b>ADMIN ACCESS ACTIVE</b>" if is_admin(uid) else "👤 <i>Regular User</i>"

    text = (
        f"🆔 {bold(sb('USER IDENTIFICATION'))}\n"
        f"{divider()}\n"
        f"👤 {sb('Name:')} {name}\n"
        f"🏷️ {sb('Username:')} {username}\n"
        f"🆔 {sb('Telegram ID:')} <code>{uid}</code>\n"
        f"🔰 {sb('Status:')} {admin_status}\n"
        f"{divider()}\n"
    )
    if is_admin(uid):
        text += f"💡 {sb('You have full admin privileges. Type')} <b>/admin</b> {sb('to open Admin Panel!')}"
    else:
        text += (
            f"💡 {sb('To gain Admin access, copy your ID')} <code>{uid}</code>\n"
            f"{sb('and add it into Admin ID in your Bot Dashboard!')}"
        )

    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /start
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["awaiting"] = None
    user = ensure_user(update)
    uid = update.effective_user.id
    if user.get("banned"):
        await update.message.reply_text("🚫 You are banned from this bot.")
        return

    # Check Force Join for non-admin users
    if not is_admin(uid):
        not_joined = await check_force_join(ctx.bot, uid)
        if not_joined:
            await send_force_join_screen(update, not_joined)
            return

    s = get_settings()
    bot_name = s.get("bot_name", "JAMES 💎")
    admin_banner = f"\n👑 {bold('Admin Access Enabled')} — Use /admin or button below\n" if is_admin(uid) else ""

    text = (
        f"🔥 {bold('Hello Hey!')}\n\n"
        f"🌟 𝙒𝙚𝙡𝙘𝙤𝙢𝙚 𝙩𝙤 {bold(bot_name)}\n"
        f"{admin_banner}"
        f"{divider()}\n"
        f"⚡ {sb('Instant Delivery')}\n"
        f"🛡️ {sb('Secure Purchase')}\n"
        f"💎 {sb('Premium Quality')}\n"
        f"✅ {sb('Trusted Service')}\n"
        f"{divider()}\n\n"
        f"👋 {sb('Welcome to the Shop Menu!')} Select an option below:"
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(uid)
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BUY PRODUCT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def shop_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    categories = fb_get("categories", {})
    if not categories:
        text = (
            f"🛒 {bold(sb('PREMIUM SHOP CENTER'))}\n"
            f"{divider()}\n"
            f"⚡ Instant Delivery\n🛡️ Secure Purchase\n"
            f"💎 Premium Quality\n✅ Trusted Service\n"
            f"{divider()}\n\n"
            f"📂 {sb('No categories available yet.')}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home")
        ]])
        if update.callback_query:
            await safe_edit_text(
                update.callback_query, text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await update.message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    s = get_settings()
    text = (
        f"🎯 {bold(sb('PREMIUM SHOP CENTER'))}\n"
        f"{divider()}\n"
        f"⚡ {sb('Instant Delivery')}\n"
        f"🛡️ {sb('Secure Purchase')}\n"
        f"💎 {sb('Premium Quality')}\n"
        f"✅ {sb('Trusted Service')}\n"
        f"{divider()}\n\n"
        f"📂 {sb('Select Product Category')}\n"
        f"Choose your favorite category from the buttons below ➡️"
    )
    buttons = []
    for cat_id, cat in categories.items():
        prods = cat.get("products", {})
        count = len(prods)
        buttons.append([InlineKeyboardButton(
            f"🎁 {sb(cat.get('name','?'))} ({count})",
            callback_data=f"cat_{cat_id}"
        )])
    buttons.append([InlineKeyboardButton(
        "🏠 " + sb("Home"), callback_data="home")])

    kb = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        await safe_edit_text(
            update.callback_query, text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def show_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = query.data.replace("cat_", "")
    cat = fb_get(f"categories/{cat_id}", {})
    if not cat:
        await query.answer("Category not found!", show_alert=True)
        return

    products = cat.get("products", {})
    text = (
        f"📦 {bold(sb(cat.get('name','?')))}\n"
        f"{divider()}\n"
        f"🛍️ {sb('Available Products:')} {len(products)}\n"
        f"{sb('Select a product to purchase:')}\n"
        f"{divider()}"
    )
    buttons = []
    for pid, prod in products.items():
        s = get_settings()
        price_str = format_amount(prod.get("price", 0), s)
        buttons.append([InlineKeyboardButton(
            f"🎁 {sb(prod.get('name','?'))}",
            callback_data=f"prod_{cat_id}_{pid}"
        )])
    buttons.append([InlineKeyboardButton(
        "⬅️ " + sb("Back to Shop"), callback_data="shop")])

    await safe_edit_text(query, 
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons))

async def show_product(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, cat_id, pid = query.data.split("_", 2)
    prod = fb_get(f"categories/{cat_id}/products/{pid}", {})
    if not prod:
        await query.answer("Product not found!", show_alert=True)
        return

    s = get_settings()
    price_str = format_amount(prod.get("price", 0), s)
    stock = prod.get("stock", 0)
    stock_status = f"✅ {sb('In Stock')} ({stock})" if stock > 0 else f"❌ {sb('Out of Stock')}"

    text = (
        f"🎯 {bold(sb('VIP PACKAGE DETAILS'))}\n"
        f"{divider()}\n"
        f"📦 {bold(prod.get('name','?'))}\n"
        f"{mini_divider()}\n"
        f"💰 {sb('Price:')} {bold(price_str)}\n"
        f"📊 {sb('Stock:')} {stock_status}\n"
    )
    files = prod.get("files", [])
    if files:
        text += f"📁 {sb('Files:')} Total {len(files)}  English File (Auto-Delivery ⚡)\n"
    elif prod.get("is_file") or prod.get("file_name"):
        fname = prod.get("file_name", "Script / Bot Archive")
        text += f"📁 {sb('File:')} <code>{fname}</code> (Instant Auto-Delivery ⚡)\n"

    demo_link = prod.get("demo_link")
    if demo_link:
        text += f"🤖 {sb('Demo Bot:')} is attached (open using the button below)\n"

    if prod.get("run_guide"):
        text += f"🛠️ {sb('Setup & Run Guide:')} English English English English Required English English ✅\n"

    if prod.get("description"):
        text += f"📝 {sb('Description:')}\n{prod.get('description')}\n"
    text += f"{divider()}"

    buttons = []
    # Demo bot link button if available (clean button, never raw link in text!)
    if demo_link:
        durl = demo_link if demo_link.startswith("http") else (f"https://t.me/{demo_link[1:]}" if demo_link.startswith("@") else f"https://{demo_link}")
        buttons.append([InlineKeyboardButton("🌐 English Link / Open Demo ↗️", url=durl)])

    if prod.get("run_guide"):
        buttons.append([InlineKeyboardButton("📖 English English English English English", callback_data=f"guide_{cat_id}_{pid}")])

    if stock > 0:
        buttons.append([InlineKeyboardButton(
            f"💎 {sb('Buy Now')} — {price_str}",
            callback_data=f"buy_{cat_id}_{pid}")])
    buttons.append([InlineKeyboardButton(
        "⬅️ " + sb("Back to Category"), callback_data=f"cat_{cat_id}")])

    # If product has media (video, photo, or animation) attached
    img = prod.get("image")
    vid = prod.get("video")
    mtype = prod.get("media_type")
    chat_id = query.message.chat_id

    # Try Video First if video is specified or media_type is video
    if vid or mtype == "video" or (isinstance(img, str) and any(img.lower().endswith(ext) for ext in [".mp4", ".mov", ".webm", ".avi"])):
        try:
            await query.message.delete()
            await ctx.bot.send_video(
                chat_id=chat_id,
                video=vid or img,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
        except Exception as e:
            logger.warning(f"Could not send product video: {e}")

    # Try Animation/GIF if media_type is animation
    if mtype == "animation":
        try:
            await query.message.delete()
            await ctx.bot.send_animation(
                chat_id=chat_id,
                animation=img,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
        except Exception as e:
            logger.warning(f"Could not send product animation: {e}")

    # Try Photo
    if img:
        try:
            await query.message.delete()
            await ctx.bot.send_photo(
                chat_id=chat_id,
                photo=img,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
        except Exception as e:
            # Fallback: file_id could be a video sent as image
            try:
                await ctx.bot.send_video(
                    chat_id=chat_id,
                    video=img,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return
            except Exception:
                pass

    await safe_edit_text(
        query, text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons))

async def guide_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_", 2)
    cat_id, pid = parts[1], parts[2]
    prod = fb_get(f"categories/{cat_id}/products/{pid}", {})
    guide = prod.get("run_guide", "any English English English English English English English।")
    pname = prod.get("name", "Product")

    text = (
        f"🛠️ <b>{pname} — English English English English Required English</b>\n"
        f"{divider()}\n"
        f"<code>{guide}</code>\n"
        f"{divider()}\n"
        f"💡 <i>above English English English EnglishnotEnglish/English English English। any English English English SupportEnglish AddEnglishAdd।</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ English English", callback_data=f"prod_{cat_id}_{pid}")]
    ])
    if query.message.photo:
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await safe_edit_text(query, text, reply_markup=kb)

async def confirm_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    _, cat_id, pid = query.data.split("_", 2)

    user = get_user(uid)
    prod = fb_get(f"categories/{cat_id}/products/{pid}", {})
    if not prod:
        await query.answer("Product not found!", show_alert=True)
        return

    s = get_settings()
    price = prod.get("price", 0)
    balance = user.get("balance", 0.0)

    if balance < price:
        short = format_amount(price - balance, s)
        text_insufficient = (
            f"❌ {bold(sb('Insufficient Balance!'))}\n"
            f"{divider()}\n"
            f"💰 {sb('Your Balance:')} {format_amount(balance, s)}\n"
            f"💎 {sb('Required:')} {format_amount(price, s)}\n"
            f"📉 {sb('Shortage:')} {bold(short)}\n"
            f"{divider()}\n\n"
            f"💡 {sb('Please deposit money to continue.')}"
        )
        kb_insufficient = InlineKeyboardMarkup([[
            InlineKeyboardButton("💳 " + sb("Deposit Now"), callback_data="deposit"),
            InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home"),
        ]])
        if query.message.photo:
            await query.message.delete()
            await ctx.bot.send_message(
                uid, text_insufficient, parse_mode=ParseMode.HTML, reply_markup=kb_insufficient)
        else:
            await safe_edit_text(query, 
                text_insufficient, parse_mode=ParseMode.HTML, reply_markup=kb_insufficient)
        return

    # check stock
    stock = prod.get("stock", 0)
    items = prod.get("items", [])
    if stock <= 0 or not items:
        await query.answer("Out of stock!", show_alert=True)
        return

    # deduct balance & deliver item
    item = items[0]
    is_file_prod = prod.get("is_file", False) or (isinstance(item, str) and item.startswith("FILE::"))
    
    # For file scripts with unlimited stock, keep item available; otherwise pop item
    if is_file_prod:
        remaining_items = items  # keep file in stock
        new_stock = stock - 1 if stock > 1 else 999
    else:
        remaining_items = items[1:]
        new_stock = max(0, stock - 1)

    new_balance = round(balance - price, 4)
    fb_update(f"users/{uid}", {"balance": new_balance})
    fb_update(f"categories/{cat_id}/products/{pid}", {
        "stock": new_stock,
        "items": remaining_items,
    })

    # determine file details if any
    file_id = None
    file_name = None
    if isinstance(item, str) and item.startswith("FILE::"):
        parts = item.split("::")
        if len(parts) >= 3:
            file_id = parts[1]
            file_name = parts[2]
    elif prod.get("file_id"):
        file_id = prod.get("file_id")
        file_name = prod.get("file_name", "script.zip")

    files_list = prod.get("files")
    if not files_list and file_id:
        files_list = [{"file_id": file_id, "file_name": file_name}]

    # log purchase
    purchase_data = {
        "uid":        uid,
        "name":       query.from_user.full_name,
        "prod":       prod.get("name"),
        "cat_id":     cat_id,
        "pid":        pid,
        "price":      price,
        "item":       item,
        "is_file":    bool(file_id or files_list),
        "files":      files_list,
        "file_id":    file_id,
        "file_name":  file_name,
        "run_guide":  prod.get("run_guide"),
        "time":       datetime.now().isoformat(),
    }
    fb_push("purchases", purchase_data)
    purch_ref = fb_push(f"users/{uid}/products", purchase_data)
    purch_key = purch_ref.key if purch_ref else "item"

    # Send success response
    success_text = (
        f"✅ {bold(sb('Purchase Successful!'))}\n"
        f"{divider()}\n"
        f"📦 {sb('Product:')} {bold(prod.get('name','?'))}\n"
        f"💰 {sb('Paid:')} {format_amount(price, s)}\n"
        f"💳 {sb('Remaining Balance:')} {format_amount(new_balance, s)}\n"
        f"{divider()}\n"
    )

    if files_list:
        success_text += (
            f"🎁 {bold('Your English / FileEnglish below English English English ⬇️')}\n"
            f"📁 Total File: <b>{len(files_list)}</b> \n"
            f"⚡ <i>FileEnglish below sent English। any time 'MY PRODUCT' from English Download English English।</i>"
        )
    elif file_id:
        success_text += (
            f"🎁 {bold(sb('Your Script / File is delivering below! ⬇️'))}\n"
            f"📁 <code>{file_name}</code>\n"
            f"⚡ <i>File attached directly below. You can also re-download anytime from 'MY PRODUCT'.</i>"
        )
    else:
        success_text += (
            f"🎁 {bold(sb('Your Item / Content:'))}\n"
            f"<code>{item}</code>"
        )

    if query.message.photo:
        await query.message.delete()
        await ctx.bot.send_message(
            uid, success_text, parse_mode=ParseMode.HTML, reply_markup=home_inline())
    else:
        await safe_edit_text(query, 
            success_text, parse_mode=ParseMode.HTML, reply_markup=home_inline())

    # Send all files to user if multiple files exist
    if files_list:
        for idx, fobj in enumerate(files_list, 1):
            fid = fobj.get("file_id")
            fname = fobj.get("file_name") or f"file_{idx}.zip"
            if fid:
                try:
                    await ctx.bot.send_document(
                        chat_id=uid,
                        document=fid,
                        filename=fname,
                        caption=(
                            f"🎁 <b>{prod.get('name')}</b> (File {idx}/{len(files_list)})\n"
                            f"📁 <code>{fname}</code>\n"
                            f"⚡ Instant Auto-Delivery"
                        ),
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Failed to send document {fname} to user {uid}: {e}")
    elif file_id:
        try:
            await ctx.bot.send_document(
                chat_id=uid,
                document=file_id,
                filename=file_name or "bot_script.zip",
                caption=(
                    f"🎁 <b>{prod.get('name')}</b>\n"
                    f"⚡ Instant Auto-Delivery\n"
                    f"✨ Thank you for your purchase!"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send document to user {uid}: {e}")

    # If product has run commands/guide, deliver it right after files
    if prod.get("run_guide"):
        await ctx.bot.send_message(
            chat_id=uid,
            text=(
                f"🛠️ <b>{prod.get('name')} — Run instructions and commands:</b>\n"
                f"{divider()}\n"
                f"<code>{prod.get('run_guide')}</code>\n"
                f"{divider()}\n"
                f"💡 <i>above English English and Your English English EnglishnotEnglish English English English English।</i>"
            ),
            parse_mode=ParseMode.HTML
        )

    # notify admin
    try:
        await ctx.bot.send_message(
            ADMIN_ID,
            f"🛒 {bold('New Purchase!')}\n"
            f"👤 User: {query.from_user.full_name} ({uid})\n"
            f"📦 Product: {prod.get('name')}\n"
            f"💰 Price: {format_amount(price, s)}"
            + (f"\n📁 File: {file_name}" if file_name else ""),
            parse_mode=ParseMode.HTML
        )
    except:
        pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MY PROFILE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def my_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    s = get_settings()
    balance = user.get("balance", 0.0)
    referrals = user.get("referrals", 0)
    verified = user.get("verified_referrals", 0)
    earned = user.get("total_earned", 0.0)
    joined = user.get("joined", "N/A")[:10]

    text = (
        f"👤 {bold(sb('MY PROFILE'))}\n"
        f"{divider()}\n"
        f"🆔 {sb('User ID:')} <code>{uid}</code>\n"
        f"📛 {sb('Name:')} {html.escape(update.effective_user.full_name or 'Member')}\n"
        f"📅 {sb('Joined:')} {joined}\n"
        f"{mini_divider()}\n"
        f"💰 {sb('Balance:')} {bold(format_amount(balance, s))}\n"
        f"👥 {sb('Total Referrals:')} {referrals}\n"
        f"✅ {sb('Verified Referrals:')} {verified}\n"
        f"💎 {sb('Total Earned:')} {format_amount(earned, s)}\n"
        f"{divider()}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 " + sb("Withdraw Money"), callback_data="user_withdraw"),
         InlineKeyboardButton("💳 " + sb("Deposit Money"), callback_data="deposit")],
        [InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home")]
    ])

    if update.callback_query:
        if update.callback_query.message.photo:
            await update.callback_query.message.delete()
            await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await safe_edit_text(update.callback_query, text, reply_markup=kb)
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MY PRODUCTS & FILE RE-DOWNLOAD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def my_products(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    products = fb_get(f"users/{uid}/products", {})

    if not products:
        text = (
            f"📦 {bold(sb('MY PRODUCTS'))}\n"
            f"{divider()}\n"
            f"💎 " + sb("You don't have any products yet.") + "\n"
            f"🛍️ {sb('Purchase products from the shop to see them here.')}\n"
            f"{divider()}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 " + sb("Buy Products"), callback_data="shop")],
            [InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home")],
        ])
    else:
        text = f"📦 {bold(sb('MY PRODUCTS & SCRIPTS'))}\n{divider()}\n"
        buttons = []
        for pkey, prod in list(products.items())[-8:]:  # show last 8
            ptime = prod.get("time","")[:10]
            pname = prod.get("prod") or prod.get("prod_name") or prod.get("product_name") or prod.get("name","Product")
            file_id = prod.get("file_id")
            files_list = prod.get("files") or []
            item_raw = str(prod.get("item",""))

            if not file_id and item_raw.startswith("FILE::"):
                parts = item_raw.split("::")
                if len(parts) >= 2:
                    file_id = parts[1]

            text += (
                f"🎁 {bold(pname)}\n"
                f"   📅 {ptime}\n"
            )
            if file_id or files_list or prod.get("is_file"):
                fname = prod.get("file_name") or "script_archive.zip"
                count_str = f" ({len(files_list)} files)" if len(files_list) > 1 else ""
                text += f"   📁 <code>{fname}</code>{count_str}\n"
                buttons.append([InlineKeyboardButton(f"📥 Download: {pname[:20]}", callback_data=f"dl_{pkey}", color="shop")])
            else:
                text += f"   <code>{item_raw}</code>\n"
            text += f"{mini_divider()}\n"

        buttons.append([InlineKeyboardButton("🛒 " + sb("Buy More"), callback_data="shop", color="shop")])
        buttons.append([InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home", color="nav")])
        kb = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        if update.callback_query.message.photo:
            await update.callback_query.message.delete()
            await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await safe_edit_text(update.callback_query, 
                text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def download_purchased_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    pkey = query.data.replace("dl_", "")
    purch = fb_get(f"users/{uid}/products/{pkey}", {})
    if not purch:
        await query.answer("Product record not found!", show_alert=True)
        return

    prod_title = purch.get("prod") or purch.get("prod_name") or purch.get("product_name") or purch.get("name", "Script File")
    files_list = purch.get("files") or []
    if files_list:
        sent_count = 0
        for idx, fobj in enumerate(files_list, 1):
            fid = fobj.get("file_id")
            fname = fobj.get("file_name") or f"file_{idx}.zip"
            if fid:
                try:
                    await ctx.bot.send_document(
                        chat_id=uid,
                        document=fid,
                        filename=fname,
                        caption=f"📥 <b>{prod_title}</b> (Part {idx}/{len(files_list)})\n📁 <code>{fname}</code>\n⚡ <i>Re-download from My Products</i>",
                        parse_mode=ParseMode.HTML
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error re-sending multi-file {fid}: {e}")
        if sent_count > 0:
            await query.answer(f"✅ {sent_count}  File sent successfully!", show_alert=True)
            return

    file_id = purch.get("file_id")
    file_name = purch.get("file_name", "bot_script.zip")
    item_raw = str(purch.get("item", ""))

    if not file_id and item_raw.startswith("FILE::"):
        parts = item_raw.split("::")
        if len(parts) >= 3:
            file_id = parts[1]
            file_name = parts[2]

    if not file_id:
        await query.answer("No downloadable file attached to this product.", show_alert=True)
        return

    try:
        await ctx.bot.send_document(
            chat_id=uid,
            document=file_id,
            filename=file_name,
            caption=(
                f"📥 <b>{prod_title}</b>\n"
                f"📁 <code>{file_name}</code>\n"
                f"⚡ Re-download from My Products\n"
                f"✨ Instant Delivery"
            ),
            parse_mode=ParseMode.HTML
        )
        await query.answer("File sent successfully! Check below.", show_alert=True)
    except Exception as e:
        logger.error(f"Error re-sending file {file_id}: {e}")
        await query.answer("Failed to send file. Please contact support.", show_alert=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REFER & EARN (PREMIUM DESIGN & 10 TK BONUS)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def refer_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    s = get_settings()
    bot_info = await ctx.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={uid}"
    ref_pct = s.get("referral_pct", 5.0)
    ref_bonus_bdt = float(s.get("referral_bonus_bdt", 10.0))
    referrals = user.get("referrals", 0)
    verified = user.get("verified_referrals", 0)
    earned = user.get("total_earned", 0.0)
    bal = user.get("balance", 0.0)

    text = (
        f"💎 {bold('𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐑𝐄𝐅𝐄𝐑𝐑𝐀𝐋 & 𝐄𝐀𝐑𝐍 𝐏𝐑𝐎𝐆𝐑𝐀𝐌')}\n"
        f"{divider()}\n"
        f"🎁 <b>Each successful referral Instant {int(ref_bonus_bdt)} USD guaranteed bonus!</b>\n\n"
        f"🔥 Your ClosedEnglish English Shop BotEnglish English English। Your Share English LinkEnglish English any New English BotEnglish English English You with with English <b>{int(ref_bonus_bdt)} USD English EnglishnotEnglish</b>!\n"
        f"⚡ English Your Referral English Each DepositEnglish English English <b>{ref_pct}% deposit commission</b>!\n\n"
        f"📊 <b>Your referral statistics:</b>\n"
        f"{mini_divider()}\n"
        f"👥 <b>Total referrals:</b> <code>{referrals}</code> users\n"
        f"🟢 <b>Verified users:</b> <code>{verified}</code> users\n"
        f"💰 <b>Total referral earnings:</b> {bold(format_amount(earned, s))}\n"
        f"💳 <b>Current wallet balance:</b> {bold(format_amount(bal, s))}\n"
        f"{mini_divider()}\n\n"
        f"🔗 <b>Your personal referral link (tap to copy):</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"💡 <i>below ButtonEnglish Click and directly Invite friends or Link English and any GroupEnglish Share English!</i>"
    )

    import urllib.parse
    bot_n = s.get("bot_name", "JAMES 💎")
    share_text = f"🔥 {bot_n} — English English Bot English English Shop!\n🎁 My Referral linkEnglish Join English and EnglishEnd English English English:\n{ref_link}"
    tg_share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote(share_text)}"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Invite friends (Invite Friends)", url=tg_share_url)],
        [InlineKeyboardButton("📋 Copy link (Copy Link)", callback_data="ref_copy_link"),
         InlineKeyboardButton("💸 Cash out earnings", callback_data="user_withdraw")],
        [InlineKeyboardButton("🏠 Home menu", callback_data="home")]
    ])

    if update.callback_query:
        await safe_edit_text(update.callback_query, text, reply_markup=kb)
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def ref_copy_link_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    bot_info = await ctx.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={uid}"
    await query.answer("📋 Referral link below Create English has been!", show_alert=False)
    await query.message.reply_text(
        f"📋 <b>Your Referral link (Tap and English English):</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        f"👆 <i>LinkEnglish English Tap English English isEnglish English! ClosedEnglish English and English ReferralEnglish English USD and EnglishnotEnglish English।</i>",
        parse_mode=ParseMode.HTML
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DEPOSIT MONEY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def deposit_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    if not s.get("deposit_open", True):
        text = (
            f"🚫 {bold(sb('DEPOSIT SYSTEM CLOSED!'))}\n"
            f"{divider()}\n"
            f"⚠️ {sb('Sorry, the deposit system is currently offline for maintenance.')}\n"
            f"💬 {sb('Please contact')} <a href='{s.get('support_link','https://t.me/bd_top_admin')}'>{sb('Support')}</a> {sb('for more details.')}\n"
            f"{divider()}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 " + sb("Back to Home"), callback_data="home")
        ]])
        if update.callback_query:
            await safe_edit_text(update.callback_query, 
                text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await update.message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    methods = get_payment_methods()
    enabled = {k: v for k, v in methods.items() if v.get("enabled")}
    if not enabled:
        init_defaults()
        methods = get_payment_methods()
        enabled = {k: v for k, v in methods.items() if v.get("enabled")}

    sym = s.get("currency_symbol", "$")
    rate = s.get("exchange_rate", 125)
    local = s.get("local_currency", "USD")
    min_dep = s.get("min_deposit", 1.0)
    min_local = int(min_dep * rate)

    text = (
        f"💳 {bold(sb('DEPOSIT MONEY'))}\n"
        f"{divider()}\n"
        f"💰 <b>{sb('Min Deposit:')}</b> {sym}{min_dep:.2f} ({min_local} {local})\n"
        f"📈 <b>{sb('Rate:')}</b> 1 {s.get('currency_name','USD')} = {rate} {local}\n"
        f"⚡ <i>Admin Verify English with withEnglish Your English Balance English isEnglish English।</i>\n"
        f"{divider()}\n"
        f"📌 <b>{sb('Select Payment Method:')}</b>"
    )
    buttons = []
    for key, pm in enabled.items():
        buttons.append([InlineKeyboardButton(
            f"💳 {pm.get('name','?')}",
            callback_data=f"dep_{key}"
        )])
    buttons.append([InlineKeyboardButton(
        "🏠 " + sb("Back to Home"), callback_data="home")])

    kb = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        await safe_edit_text(update.callback_query, 
            text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def deposit_method_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method_key = query.data.replace("dep_","")
    methods = get_payment_methods()
    pm = methods.get(method_key, {})
    s = get_settings()
    rate = s.get("exchange_rate", 125)
    local = s.get("local_currency","USD")
    min_dep = s.get("min_deposit", 1.0)
    min_local = int(min_dep * rate)
    sym = s.get("currency_symbol", "$")

    number = pm.get("number") or pm.get("address","")
    num_display = f"<code>{number}</code>" if number else "<i>(NameEnglish not set)</i>"

    text = (
        f"💳 <b>{pm.get('name','?')} Deposit</b>\n"
        f"{divider()}\n"
        f"📱 <b>Send Money To:</b> {num_display}\n"
        f"<i>(NameEnglish English Tap English English isEnglish English)</i>\n\n"
        f"💰 <b>Minimum deposit:</b> {min_local} {local} ({sym}{min_dep:.2f})\n"
        f"📊 <b>Rate:</b> 1 {s.get('currency_name','USD')} = {rate} {local}\n"
        f"{divider()}\n"
        f"✏️ <b>Enter the deposit amount:</b>\n"
        f"<i>(English: 500 English English)</i>"
    )
    ctx.user_data["dep_method"] = method_key
    ctx.user_data["dep_number"] = number
    ctx.user_data["dep_name"]   = pm.get("name","")
    ctx.user_data["awaiting"]   = "deposit_amount"

    await safe_edit_text(query, 
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ " + sb("Cancel / Cancel"), callback_data="deposit")
        ]]))

async def deposit_handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    awaiting = ctx.user_data.get("awaiting")
    text_raw = (update.message.text or update.message.caption or "").strip()
    uid = update.effective_user.id
    s = get_settings()

    # Cancel command or text
    if text_raw.lower() in ["cancel", "Cancel", "exit", "/cancel", "back", "❌ cancel", "❌ Cancel"]:
        ctx.user_data["awaiting"] = None
        await update.message.reply_text(
            "❌ Deposit cancelled।",
            reply_markup=main_menu_keyboard(uid)
        )
        return

    if awaiting == "deposit_amount":
        rate = s.get("exchange_rate", 125)
        local = s.get("local_currency","USD")
        min_dep = s.get("min_deposit", 1.0)
        min_local = int(min_dep * rate)
        sym = s.get("currency_symbol","$")

        try:
            amount_local = parse_clean_amount(text_raw)
            if amount_local <= 0:
                raise ValueError("Amount must be positive")
            if amount_local < min_local:
                await update.message.reply_text(
                    f"❌ Minimum deposit <b>{min_local} {local}</b> ({sym}{min_dep:.2f})।\n"
                    f"Please English {min_local} {local} English English English Amount Enter:\n"
                    f"<i>(Cancel English 'cancel' Enter)</i>",
                    parse_mode=ParseMode.HTML
                )
                return

            amount_usd = round(amount_local / rate, 4)
            ctx.user_data["dep_amount_local"] = amount_local
            ctx.user_data["dep_amount_usd"]   = amount_usd
            ctx.user_data["awaiting"]          = "deposit_txid"

            dep_name = ctx.user_data.get("dep_name", "Payment")
            dep_num  = ctx.user_data.get("dep_number", "")
            num_info = f" ({dep_num})" if dep_num else ""

            await update.message.reply_text(
                f"✅ <b>Amount confirmed:</b> {amount_local:,.2f} {local} = {sym}{amount_usd:.4f}\n"
                f"💳 <b>Method:</b> {dep_name}{num_info}\n\n"
                f"📝 <b>Send your transaction ID or payment screenshot:</b>\n"
                f"<i>(Payment/Payment/PaymentEnglish TrxID English English English Send or English English English Send)</i>\n"
                f"<i>(Cancel English 'cancel' Enter)</i>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Error parsing deposit amount from input '{text_raw}': {e}")
            await update.message.reply_text(
                f"❌ Please English USDEnglish Amount Enter (English: 500 English English)।\n"
                f"Cancel English <b>cancel</b> Enter।",
                parse_mode=ParseMode.HTML
            )

    elif awaiting == "deposit_txid":
        photo_id = None
        txid = ""
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            txid = update.message.caption.strip() if update.message.caption else "Payment Screenshot"
        elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith("image/"):
            photo_id = update.message.document.file_id
            txid = update.message.caption.strip() if update.message.caption else "Payment Screenshot (Doc)"
        elif update.message.text:
            txid = update.message.text.strip()
        else:
            await update.message.reply_text(
                "❌ Please English English ID (TxID) or PaymentEnglish English Send।\n"
                "Cancel English 'cancel' Enter।"
            )
            return

        ctx.user_data["awaiting"] = None
        amt_local = ctx.user_data.get("dep_amount_local", 0)
        amt_usd   = ctx.user_data.get("dep_amount_usd", 0)
        dep_method = ctx.user_data.get("dep_method", "manual")
        dep_name   = ctx.user_data.get("dep_name", "Payment")
        sym = s.get("currency_symbol","$")
        local = s.get("local_currency","USD")

        if amt_local <= 0 or amt_usd <= 0:
            await update.message.reply_text(
                "⚠️ DepositEnglish Amount English English English English End English English। Please again Deposit Start English।",
                reply_markup=main_menu_keyboard(uid)
            )
            return

        ref = fb_push("deposits", {
            "uid":          uid,
            "name":         update.effective_user.full_name,
            "username":     update.effective_user.username or "",
            "method":       dep_method,
            "method_name":  dep_name,
            "amount_local": amt_local,
            "amount_usd":   amt_usd,
            "txid":         txid,
            "screenshot":   photo_id,
            "status":       "pending",
            "time":         datetime.now().isoformat(),
        })
        dep_id = ref.key if ref else f"dep_{int(datetime.now().timestamp())}"

        await update.message.reply_text(
            f"⏳ {bold(sb('Deposit Request Submitted!'))}\n"
            f"{divider()}\n"
            f"🆔 <b>Deposit ID:</b> <code>{dep_id}</code>\n"
            f"💰 <b>Amount:</b> {amt_local:,.2f} {local} ({sym}{amt_usd:.4f})\n"
            f"📱 <b>Method:</b> {html.escape(dep_name)}\n"
            f"🧾 <b>TxID / Screenshot:</b> <code>{html.escape(str(txid))}</code>\n"
            f"{divider()}\n"
            f"✅ <b>Your Deposit English Successfully English has been।</b>\n"
            f"Admin Check and English Your English Balance English and English।",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(uid)
        )

        # Notify ALL admins with Photo or Text
        admin_text = (
            f"💳 {bold('New Deposit Request!')}\n"
            f"👤 User: {html.escape(update.effective_user.full_name or 'Member')} (<code>{uid}</code>)\n"
            f"💰 Amount: {amt_local:,.2f} {local} = {sym}{amt_usd:.4f}\n"
            f"📱 Method: {html.escape(dep_name)}\n"
            f"🧾 TxID: <code>{html.escape(str(txid))}</code>\n"
            f"🆔 Dep ID: <code>{dep_id}</code>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"adep_ok_{dep_id}_{uid}_{amt_usd}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"adep_no_{dep_id}_{uid}"),
        ]])

        for aid in get_all_admin_ids():
            try:
                if photo_id:
                    await ctx.bot.send_photo(
                        chat_id=aid,
                        photo=photo_id,
                        caption=admin_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb
                    )
                else:
                    await ctx.bot.send_message(
                        chat_id=aid,
                        text=admin_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb
                    )
            except Exception as e:
                logger.warning(f"Could not notify admin {aid} for deposit: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SUPPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def support_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    support_link = s.get("support_link", "https://t.me/bd_top_admin")
    text = f"🤖 {sb('Contact us for any help:')}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🆘 " + sb("SUPPORT"), url=support_link)
    ]])
    if update.callback_query:
        await safe_edit_text(update.callback_query, 
            text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CHECK DATA (Custom Direct Link Buttons)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def check_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    links = fb_get("check_data_links", {})
    s = get_settings()
    bot_name = s.get("bot_name", "𝗗𝗫𝗔 𝗣𝗔𝗜𝗗 𝗭𝗢𝗡𝗘 💎")

    text = (
        f"🌐 {bold(sb('CHECK DATA & IMPORTANT LINKS'))}\n"
        f"{divider()}\n"
        f"📌 <b>below Required English English English English directly Link English English:</b>\n"
        f"<i>(any ButtonEnglish Click English directly English Link English isEnglish English)</i>\n"
        f"{divider()}"
    )

    buttons = []
    if links and isinstance(links, dict):
        for lid, linfo in links.items():
            if not isinstance(linfo, dict):
                continue
            title = linfo.get("title", "🔗 Link")
            url = linfo.get("url", "https://t.me")
            buttons.append([InlineKeyboardButton(f"👉 {title}", url=url)])
    else:
        text += f"\n\n⚠️ <i>any Link English Data Button nowEnglish Add English isEnglish। Admin panel from Create English English।</i>"

    buttons.append([InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home")])
    kb = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await safe_edit_text(update.callback_query, 
            text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HOME callback
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def home_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["awaiting"] = None
    s = get_settings()
    bot_name = s.get("bot_name", "JAMES 💎")
    uid = query.from_user.id
    admin_banner = f"\n👑 {bold('Admin Access Enabled')} — Use /admin or button below\n" if is_admin(uid) else ""
    text = (
        f"🌟 {bold(bot_name)}\n"
        f"{admin_banner}"
        f"{divider()}\n"
        f"⚡ {sb('Instant Delivery')}\n"
        f"🛡️ {sb('Secure Purchase')}\n"
        f"💎 {sb('Premium Quality')}\n"
        f"✅ {sb('Trusted Service')}\n"
        f"{divider()}\n\n"
        f"👋 {sb('Welcome to the Shop Menu!')} Select an option below:"
    )
    kb = home_menu_inline(uid)
    await safe_edit_text(query, text, reply_markup=kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ██████████  ADMIN PANEL  ██████████
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_admin(uid):
            if update.message:
                await update.message.reply_text("🚫 Admin only!")
            elif update.callback_query:
                await update.callback_query.answer("🚫 Admin only!", show_alert=True)
            return
        return await func(update, ctx)
    return wrapper

def manager_or_owner(func):
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not can_manage(uid):
            msg = "⚠️ You English English (View Only) Admin। Edit English English English English none।"
            if update.message:
                await update.message.reply_text(msg)
            elif update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            return
        return await func(update, ctx)
    return wrapper

def owner_only(func):
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_owner(uid):
            msg = "🚫 English Owner Admin This English English English।"
            if update.message:
                await update.message.reply_text(msg)
            elif update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            return
        return await func(update, ctx)
    return wrapper

@admin_only
async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    role = get_admin_role(uid)
    role_badge = "👑 OWNER (English)" if role == "owner" else ("🛠️ MANAGER (English)" if role == "manager" else "👁️ VIEW ONLY (English)")
    s = get_settings()
    fj_status = "🟢 English" if s.get("force_join_enabled", True) else "🔴 Off"
    dep_status = "🟢 On" if s.get("deposit_open", True) else "🔴 Closed"
    wdraw_status = "🟢 On" if s.get("withdraw_open", True) else "🔴 Closed"
    
    text = (
        f"👑 {bold(sb('ADMIN CONTROL CENTER'))} 👑\n"
        f"{divider()}\n"
        f"🤖 <b>Bot English English English English</b>\n\n"
        f"👤 <b>Admin:</b> {html.escape(update.effective_user.full_name or 'Member')} (@{update.effective_user.username or 'N/A'})\n"
        f"🔰 <b>Your English:</b> {role_badge}\n"
        f"⚡ <b>English English:</b> English English English 🟢\n"
        f"📢 <b>Force Join:</b> {fj_status} | 💳 <b>Deposit:</b> {dep_status} | 📤 <b>English:</b> {wdraw_status}\n"
        f"{divider()}\n"
        f"📌 <b>English Menu from English English English English:</b>"
    )
    kb = InlineKeyboardMarkup([
        # 1. Shop English English English
        [InlineKeyboardButton("🛒 " + sb("Manage Products & Scripts"), callback_data="adm_products")],
        # 2. User English English
        [InlineKeyboardButton("👥 User English English English", callback_data="adm_users"),
         InlineKeyboardButton("⛔ English / English User", callback_data="adm_ban")],
        # 3. English English English
        [InlineKeyboardButton("💳 Deposit English", callback_data="adm_deposits"),
         InlineKeyboardButton("📤 English English", callback_data="adm_withdrawals")],
        [InlineKeyboardButton("🎁 English Balance English", callback_data="adm_addbal"),
         InlineKeyboardButton("💰 Payment Method English", callback_data="adm_payments")],
        # 4. English English English Button manager
        [InlineKeyboardButton("🎛️ English Button manager (Button Manager)", callback_data="adm_btnmgr")],
        [InlineKeyboardButton("⚙️ BotEnglish English Settings", callback_data="adm_settings"),
         InlineKeyboardButton("👑 Admin English English English", callback_data="adm_roles")],
        [InlineKeyboardButton("📢 Force Join Channel English", callback_data="adm_forcejoin"),
         InlineKeyboardButton("🔗 CHECK DATA Button manager", callback_data="adm_checkdata")],
        # 5. Balance English English DataEnglish English
        [InlineKeyboardButton("⚠️ All Balance English English", callback_data="adm_resetbal_ask"),
         InlineKeyboardButton("💾 DataEnglish English (.json)", callback_data="adm_dbbackup")],
        # 6. English, EnglishnotEnglish English English
        [InlineKeyboardButton("📢 English English", callback_data="adm_broadcast"),
         InlineKeyboardButton("📊 Bot English", callback_data="adm_stats")],
        [InlineKeyboardButton("🔥 English English English English English", callback_data="adm_fbstatus")],
        # 7. English
        [InlineKeyboardButton("🏠 Close panel English", callback_data="home")]
    ])
    if update.message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await safe_edit_text(update.callback_query, text, reply_markup=kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN: MAIN BUTTONS MANAGER (Toggle Any Main Menu Button)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@admin_only
async def adm_btnmgr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    s = get_settings()
    mb = s.get("main_buttons", {})

    default_buttons = {
        "buy_product":   {"label": "BUY PRODUCT",   "icon": "🛒"},
        "deposit_money": {"label": "DEPOSIT MONEY", "icon": "💳"},
        "refer":         {"label": "REFER & EARN",  "icon": "🎁"},
        "my_product":    {"label": "MY PRODUCT",    "icon": "📦"},
        "my_profile":    {"label": "MY PROFILE",    "icon": "👤"},
        "check_data":    {"label": "CHECK DATA",    "icon": "🌐"},
        "support":       {"label": "SUPPORT",       "icon": "🆘"},
        "my_id":         {"label": "MY ID",         "icon": "🆔"},
        "about":         {"label": "ABOUT",         "icon": "ℹ️"},
    }

    text = (
        f"🎛️ <b>English Button manager English (Button Manager)</b>\n"
        f"{divider()}\n"
        f"BotEnglish User MenuEnglish English English Button English will be English English from English/English English English:\n\n"
    )

    buttons = []
    for btn_id, info in default_buttons.items():
        curr = mb.get(btn_id, {})
        is_on = curr.get("enabled", True)
        status_text = "🟢 On" if is_on else "🔴 Closed"
        label = info["label"]
        icon = info["icon"]
        text += f"• {icon} <b>{label}:</b> {status_text}\n"

        toggle_label = f"{icon} {label} [{status_text}]"
        buttons.append([InlineKeyboardButton(toggle_label, callback_data=f"adm_btntog_{btn_id}")])

    buttons.append([InlineKeyboardButton("⬅️ English English Admin panel", callback_data="adm_panel")])
    kb = InlineKeyboardMarkup(buttons)

    if query:
        await safe_edit_text(query, text, reply_markup=kb)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def adm_btntog_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    btn_id = query.data.replace("adm_btntog_", "")
    s = get_settings()
    mb = s.get("main_buttons", {})
    if btn_id not in mb:
        mb[btn_id] = {"enabled": True}
    curr_status = mb[btn_id].get("enabled", True)
    mb[btn_id]["enabled"] = not curr_status
    fb_update("settings", {"main_buttons": mb})
    await adm_btnmgr(update, ctx)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN: RESET ALL USER BALANCES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@admin_only
async def adm_resetbal_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = fb_get("users", {})
    text = (
        f"⚠️ <b>EnglishMessage: All UserEnglish Balance English English</b>\n"
        f"{divider()}\n"
        f"Current Total English User: <b>{len(users)}</b> users\n\n"
        f"You English Confirm English You BotEnglish <b>English UserEnglish Balance English (English)</b> English English?\n"
        f"⚡ This English with with English English and English DataEnglish English will be।"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ English, Confirm! All Balance English English", callback_data="adm_resetbal_confirm")],
        [InlineKeyboardButton("❌ Cancel English", callback_data="adm_panel")]
    ])
    await safe_edit_text(query, text, reply_markup=kb)

@admin_only
async def adm_resetbal_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = reset_all_user_balances()
    text = (
        f"✅ <b>English UserEnglish Balance Successfully English English has been!</b>\n"
        f"{divider()}\n"
        f"👥 Total <b>{count}</b> users UserEnglish English Balance English.English English has been।\n"
        f"🔥 English and English DataEnglish Successfully English Completed has been।"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Admin panel", callback_data="adm_panel")]
    ])
    await safe_edit_text(query, text, reply_markup=kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN: DATABASE BACKUP EXPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@admin_only
async def adm_dbbackup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("💾 DataEnglish English English English...", show_alert=False)
    uid = query.from_user.id
    try:
        with _cache_lock:
            _save_local_store_atomic(_MEM_CACHE)
        backup_name = f"james_bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(LOCAL_DB_FILE, "rb") as f:
            await ctx.bot.send_document(
                chat_id=uid,
                document=f,
                filename=backup_name,
                caption=(
                    f"💾 <b>JAMES — DataEnglish English English File</b>\n"
                    f"{mini_divider()}\n"
                    f"📅 Date: {datetime.now().strftime('%d %B %Y, %I:%M %p')}\n"
                    f"🛡️ English User, Balance, Product, Category English Settings English।"
                ),
                parse_mode=ParseMode.HTML
            )
        await query.answer("✅ English English File Your English Sent!", show_alert=True)
    except Exception as e:
        logger.error(f"Backup export error: {e}")
        await query.answer(f"❌ English English English has been: {e}", show_alert=True)

# ─── ADMIN: PRODUCTS ─────────────────────────────────────────
@admin_only
async def adm_products(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = fb_get("categories", {})
    text = (
        f"🛒 {bold(sb('MANAGE PRODUCTS'))}\n"
        f"{divider()}\n"
        f"📂 {sb('Total Categories:')} {len(categories)}\n"
        f"{divider()}"
    )
    buttons = []
    for cat_id, cat in categories.items():
        prods = cat.get("products",{})
        buttons.append([InlineKeyboardButton(
            f"📂 {cat.get('name','?')} ({len(prods)} prods)",
            callback_data=f"adm_cat_{cat_id}"
        )])
    buttons += [
        [InlineKeyboardButton("➕ " + sb("Add Category"),  callback_data="adm_addcat"),
         InlineKeyboardButton("🗑️ " + sb("Del Category"),  callback_data="adm_delcat")],
        [InlineKeyboardButton("⬅️ " + sb("Back"),          callback_data="adm_panel")],
    ]
    await safe_edit_text(query, 
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons))

@admin_only
async def adm_category_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = query.data.replace("adm_cat_","")
    cat = fb_get(f"categories/{cat_id}", {})
    products = cat.get("products",{})
    text = (
        f"📂 {bold(cat.get('name','?'))}\n"
        f"{divider()}\n"
        f"🎁 {sb('Products:')} {len(products)}\n"
        f"{divider()}"
    )
    buttons = []
    for pid, prod in products.items():
        stock = prod.get("stock",0)
        buttons.append([InlineKeyboardButton(
            f"🎁 {prod.get('name','?')} | Stock: {stock}",
            callback_data=f"adm_prod_{cat_id}_{pid}"
        )])
    buttons += [
        [InlineKeyboardButton("➕ " + sb("Add Product"),   callback_data=f"adm_addprod_{cat_id}"),
         InlineKeyboardButton("⬅️ " + sb("Back"),          callback_data="adm_products")],
    ]
    await safe_edit_text(query, 
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons))

@admin_only
async def adm_prod_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("adm_prod_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    cat = fb_get(f"categories/{cat_id}", {})
    cat_name = cat.get("name", cat_id)
    prod = fb_get(f"categories/{cat_id}/products/{pid}", {})
    if not prod:
        await query.answer("❌ Product not found!", show_alert=True)
        return

    s = get_settings()
    rate = s.get("exchange_rate", 125)
    local_sym = s.get("local_currency", "$")
    price_val = float(prod.get("price", 0))
    local_price = round(price_val * rate, 2)

    p_name = prod.get("name", "N/A")
    demo_link = prod.get("demo_link") or "—"
    entry_file = prod.get("entry_file") or "main.py"
    source_file = prod.get("file_name") or ("File Attached" if prod.get("file_id") else "—")
    dl_count = prod.get("downloads", 0)
    is_hidden = prod.get("hidden", False)
    visibility_str = "🔴 English (Hidden)" if is_hidden else "🟢 English (Active)"
    description = prod.get("description") or "—"
    run_guide = prod.get("run_guide") or "—"
    mtype = prod.get("media_type") or ("video" if prod.get("video") else ("photo" if prod.get("image") else "None"))
    media_badge = f"🎥 English ({mtype})" if mtype == "video" else (f"🖼️ English ({mtype})" if mtype == "photo" else ("✨ English" if mtype == "animation" else "any English none"))

    text = (
        f"⚙️ <b>English English English EditEnglish</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• <b>Name:</b> {p_name}\n"
        f"• <b>Category:</b> {cat_name}\n"
        f"• <b>Price:</b> {price_val}$ ({local_price} {local_sym})\n"
        f"• <b>English EnglishnotEnglish:</b> {media_badge}\n"
        f"• <b>English Link:</b> {demo_link}\n"
        f"• <b>English English File:</b> {entry_file}\n"
        f"• <b>English File:</b> {source_file}\n"
        f"• <b>Download English:</b> {dl_count} English\n"
        f"• <b>English:</b> {visibility_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>Description:</b>\n{description}\n\n"
        f"🛠️ <b>English English English English English:</b>\n{run_guide}"
    )

    vis_label = "👁️ English: English English" if is_hidden else "👁️ English: English English"

    buttons = [
        [
            InlineKeyboardButton("✏️ Name English", callback_data=f"aedt_name_{cat_id}_{pid}"),
            InlineKeyboardButton("💰 Price English", callback_data=f"aedt_price_{cat_id}_{pid}")
        ],
        [
            InlineKeyboardButton("📁 Category English", callback_data=f"aedt_cat_{cat_id}_{pid}"),
            InlineKeyboardButton("🔗 English Link Edit", callback_data=f"aedt_demo_{cat_id}_{pid}")
        ],
        [
            InlineKeyboardButton("📝 English Edit", callback_data=f"aedt_desc_{cat_id}_{pid}"),
            InlineKeyboardButton("🛠️ English English Edit", callback_data=f"aedt_guide_{cat_id}_{pid}")
        ],
        [
            InlineKeyboardButton("🖼️/🎥 English Edit (English/English)", callback_data=f"aedt_media_{cat_id}_{pid}"),
            InlineKeyboardButton("🚀 English File English", callback_data=f"aedt_entry_{cat_id}_{pid}")
        ],
        [
            InlineKeyboardButton("📤 File English / Stock", callback_data=f"aedt_file_{cat_id}_{pid}"),
            InlineKeyboardButton("📥 English Download", callback_data=f"aedt_testdl_{cat_id}_{pid}")
        ],
        [
            InlineKeyboardButton(vis_label, callback_data=f"aedt_vis_{cat_id}_{pid}"),
            InlineKeyboardButton("🗑️ English Delete", callback_data=f"adm_delprod_{cat_id}_{pid}")
        ],
        [
            InlineKeyboardButton("⬅️ English", callback_data=f"adm_cat_{cat_id}")
        ]
    ]

    try:
        await safe_edit_text(query, 
            text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

# ─── ADMIN: PRODUCT EDITORS (FROM SCREENSHOT) ────────────────
@admin_only
async def aedt_start_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_name_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"aedt_name_{cat_id}_{pid}"
    await safe_edit_text(query, 
        f"✏️ <b>English / ProductEnglish Name English</b>\n{divider()}\n"
        f"📝 Please New Name English Send:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def aedt_start_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_price_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"aedt_price_{cat_id}_{pid}"
    s = get_settings()
    rate = s.get("exchange_rate", 125)
    local_sym = s.get("local_currency", "USD")
    await safe_edit_text(query, 
        f"💰 <b>Price English</b>\n{divider()}\n"
        f"💵 New Price USD English Enter (English: <code>5.0</code> English <code>2.5</code>):\n"
        f"<i>(Current Rate: 1 USD = {rate} {local_sym})</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def aedt_start_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_cat_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    categories = fb_get("categories", {})
    buttons = []
    for c_id, c in categories.items():
        if c_id != cat_id:
            buttons.append([InlineKeyboardButton(
                f"📁 {c.get('name', c_id)}", callback_data=f"aedt_moveto_{cat_id}_{pid}_{c_id}"
            )])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")])
    await safe_edit_text(query, 
        f"📁 <b>Category English</b>\n{divider()}\n"
        f"This Product English CategoryEnglish English English English English English:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons))

@admin_only
async def aedt_move_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_moveto_","").split("_", 2)
    from_cat, pid, to_cat = parts[0], parts[1], parts[2]
    prod = fb_get(f"categories/{from_cat}/products/{pid}", {})
    if prod:
        fb_set(f"categories/{to_cat}/products/{pid}", prod)
        fb_delete(f"categories/{from_cat}/products/{pid}")
        await query.answer("✅ Category Successfully English has been!", show_alert=True)
    query.data = f"adm_prod_{to_cat}_{pid}"
    await adm_prod_detail(update, ctx)

@admin_only
async def aedt_start_demo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_demo_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"aedt_demo_{cat_id}_{pid}"
    await safe_edit_text(query, 
        f"🔗 <b>English Link Edit</b>\n{divider()}\n"
        f"🤖 New English Link English @UserEnglish Enter:\n"
        f"<i>(Link Remove English <code>clear</code> English Send)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def aedt_start_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_desc_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"aedt_desc_{cat_id}_{pid}"
    await safe_edit_text(query, 
        f"📝 <b>English Edit</b>\n{divider()}\n"
        f"✏️ ProductEnglish New Description English English English Send:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def aedt_start_guide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_guide_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"aedt_guide_{cat_id}_{pid}"
    await safe_edit_text(query, 
        f"🛠️ <b>English English English English English Edit (Setup & Run Guide)</b>\n{divider()}\n"
        f"📌 BotEnglish English English, English English English English English English Send:\n"
        f"<i>(English English English <code>clear</code> English Send)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def aedt_start_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_media_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"aedt_media_{cat_id}_{pid}"
    await safe_edit_text(query, 
        f"🖼️/🎥 <b>English EditEnglish (English / English EnglishnotEnglish)</b>\n{divider()}\n"
        f"📸 This ProductEnglish for New English <b>English</b> or <b>English</b> directly Send।\n"
        f"🔗 or English/English English English Send।\n\n"
        f"🗑️ Current English English English English <code>remove</code> English Send।",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def aedt_start_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_entry_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"aedt_entry_{cat_id}_{pid}"
    await safe_edit_text(query, 
        f"🚀 <b>English English File English</b>\n{divider()}\n"
        f"📄 English English FileEnglish Name Enter:\n"
        f"<i>(English: <code>main.py</code>, <code>server.js</code>, <code>bot.py</code>, <code>index.php</code>)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def aedt_start_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_file_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"aedt_file_{cat_id}_{pid}"
    await safe_edit_text(query, 
        f"📤 <b>New File English / Stock English</b>\n{divider()}\n"
        f"📁 <b>Option 1:</b> directly any File (<code>.zip</code>, <code>.py</code>, <code>.js</code>, <code>.rar</code>) English English English।\n\n"
        f"📝 <b>Option 2:</b> English Stock English English English English English Send।",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def aedt_test_download(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_testdl_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    prod = fb_get(f"categories/{cat_id}/products/{pid}", {})
    if not prod:
        await query.answer("Product not found!", show_alert=True)
        return

    pname = prod.get("name", pid)
    file_id = prod.get("file_id")
    file_name = prod.get("file_name", f"{pid}.zip")
    items = prod.get("items", [])

    if file_id:
        try:
            await ctx.bot.send_document(
                chat_id=query.from_user.id,
                document=file_id,
                filename=file_name,
                caption=f"📥 <b>[English Download]</b> {pname}\n🚀 <i>English File:</i> <code>{prod.get('entry_file', 'main.py')}</code>",
                parse_mode=ParseMode.HTML
            )
            await query.answer("✅ English File Sent!", show_alert=True)
            return
        except Exception as e:
            logger.error(f"Test download error: {e}")

    for it in items:
        if isinstance(it, str) and it.startswith("FILE::"):
            _, fid, fn = it.split("::", 2)
            try:
                await ctx.bot.send_document(
                    chat_id=query.from_user.id,
                    document=fid,
                    filename=fn,
                    caption=f"📥 <b>[English Download]</b> {pname}",
                    parse_mode=ParseMode.HTML
                )
                await query.answer("✅ English File Sent!", show_alert=True)
                return
            except Exception as e:
                pass

    if items:
        preview_text = "\n".join(items[:5])
        await ctx.bot.send_message(
            query.from_user.id,
            f"📥 <b>[English Data English]</b> {pname}\n{divider()}\n<code>{preview_text}</code>",
            parse_mode=ParseMode.HTML
        )
        await query.answer("✅ English Data Sent!", show_alert=True)
    else:
        await query.answer("⚠️ any File English Stock English English none!", show_alert=True)

@admin_only
async def aedt_toggle_visibility(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("aedt_vis_","").split("_",1)
    cat_id, pid = parts[0], parts[1]
    prod = fb_get(f"categories/{cat_id}/products/{pid}", {})
    is_hidden = prod.get("hidden", False)
    fb_update(f"categories/{cat_id}/products/{pid}", {"hidden": not is_hidden})
    status_msg = "🔴 Product now English English has been (User ShopEnglish English not)" if not is_hidden else "🟢 Product now English English has been (User ShopEnglish English)"
    await query.answer(status_msg, show_alert=True)
    query.data = f"adm_prod_{cat_id}_{pid}"
    await adm_prod_detail(update, ctx)

# ─── ADMIN: SETTINGS ─────────────────────────────────────────
@admin_only
async def adm_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    s = get_settings()
    dep_st = "🟢 On" if s.get('deposit_open') else "🔴 Closed"
    wdr_st = "🟢 On" if s.get('withdraw_open') else "🔴 Closed"
    text = (
        f"⚙️ <b>BotEnglish English English English Settings</b>\n"
        f"{divider()}\n"
        f"🤖 <b>BotEnglish Name:</b> {s.get('bot_name','')}\n"
        f"💱 <b>International currency:</b> {s.get('currency_name','')} ({s.get('currency_symbol','')})\n"
        f"🏦 <b>Local currency:</b> {s.get('local_currency','')}\n"
        f"📈 <b>Exchange rate:</b> 1$ = {s.get('exchange_rate','')} {s.get('local_currency','USD')}\n"
        f"💳 <b>Deposit English:</b> {dep_st}\n"
        f"📤 <b>English English:</b> {wdr_st}\n"
        f"⬇️ <b>Minimum deposit:</b> {s.get('min_deposit','')}\n"
        f"⬆️ <b>English English:</b> {s.get('min_withdraw','')}\n"
        f"🎁 <b>Referral Commission:</b> {s.get('referral_pct',5)}%\n"
        f"🔗 <b>Support Link:</b> {s.get('support_link','')}\n"
        f"{divider()}\n"
        f"💡 <i>any Information English English below ButtonEnglish English:</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ BotEnglish Name", callback_data="aset_bot_name"),
         InlineKeyboardButton("✏️ English English", callback_data="aset_welcome_text")],
        [InlineKeyboardButton("✏️ Currency name", callback_data="aset_currency_name"),
         InlineKeyboardButton("✏️ Currency symbol", callback_data="aset_currency_symbol")],
        [InlineKeyboardButton("✏️ Local currency", callback_data="aset_local_currency"),
         InlineKeyboardButton("✏️ Exchange rate", callback_data="aset_exchange_rate")],
        [InlineKeyboardButton("✏️ Minimum deposit", callback_data="aset_min_deposit"),
         InlineKeyboardButton("✏️ English English", callback_data="aset_min_withdraw")],
        [InlineKeyboardButton("✏️ Referral Commission %", callback_data="aset_referral_pct"),
         InlineKeyboardButton("✏️ Support UserEnglish/Link", callback_data="aset_support_link")],
        [InlineKeyboardButton(
            ("⏸️ Deposit Closed English" if s.get("deposit_open") else "▶️ Deposit On English"),
            callback_data="aset_toggle_deposit"),
         InlineKeyboardButton(
            ("⏸️ English Closed English" if s.get("withdraw_open") else "▶️ English On English"),
            callback_data="aset_toggle_withdraw")],
        [InlineKeyboardButton("⬅️ Admin panel", callback_data="adm_panel")],
    ])
    await safe_edit_text(query, text, reply_markup=kb)

# ─── ADMIN: PAYMENT METHODS ──────────────────────────────────
@admin_only
async def adm_payments(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    methods = get_payment_methods()
    text = (
        f"💰 <b>Payment Method English English Number English</b>\n"
        f"{divider()}\n"
        f"📌 DepositEnglish for English Payment Method English NameEnglish:\n\n"
    )
    for key, pm in methods.items():
        status = "🟢 English" if pm.get("enabled") else "🔴 Closed"
        number = pm.get("number") or pm.get("address","N/A")
        text += f"• <b>{pm.get('name','?')}</b> ({status}):\n   <code>{number}</code>\n"
    text += f"{divider()}\n💡 <i>English NameEnglish English English English/English English ButtonEnglish English:</i>"

    buttons = []
    for key, pm in methods.items():
        toggle_label = ("⏸️ Closed English" if pm.get("enabled") else "▶️ On English")
        buttons.append([
            InlineKeyboardButton(f"✏️ {pm.get('name','?')}", callback_data=f"apm_edit_{key}"),
            InlineKeyboardButton(toggle_label, callback_data=f"apm_toggle_{key}"),
        ])
    buttons.append([InlineKeyboardButton("⬅️ Admin panel", callback_data="adm_panel")])

    await safe_edit_text(
        query, text,
        reply_markup=InlineKeyboardMarkup(buttons))

# ─── ADMIN: DEPOSITS ─────────────────────────────────────────
@admin_only
async def adm_deposits(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deposits = fb_get("deposits", {})
    pending = {k: v for k, v in deposits.items() if v.get("status")=="pending"}
    s = get_settings()
    sym = s.get("currency_symbol","$")
    local = s.get("local_currency","USD")

    text = (
        f"💳 {bold(sb('DEPOSIT REQUESTS'))}\n"
        f"{divider()}\n"
        f"⏳ {sb('Pending:')} {len(pending)}\n"
        f"✅ {sb('Total:')} {len(deposits)}\n"
        f"{divider()}"
    )
    buttons = []
    for dep_id, dep in list(pending.items())[-10:]:
        uid_d = dep.get("uid","?")
        amt   = dep.get("amount_local","?")
        meth  = dep.get("method","?")
        buttons.append([
            InlineKeyboardButton(
                f"👤{uid_d} | {amt} {local} | {meth}",
                callback_data=f"adep_view_{dep_id}"
            )
        ])
    buttons.append([InlineKeyboardButton("⬅️ " + sb("Back"), callback_data="adm_panel")])
    await safe_edit_text(query, 
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons))

@admin_only
async def adm_deposit_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dep_id = query.data.replace("adep_view_","")
    dep = fb_get(f"deposits/{dep_id}", {})
    s = get_settings()
    sym = s.get("currency_symbol","$")
    local = s.get("local_currency","USD")
    uid_d = dep.get("uid","?")
    amt_u = dep.get("amount_usd", 0)

    text = (
        f"💳 {bold(sb('Deposit Details'))}\n"
        f"{divider()}\n"
        f"👤 {sb('User:')} {dep.get('name','?')} (<code>{uid_d}</code>)\n"
        f"💰 {sb('Amount:')} {dep.get('amount_local','?')} {local} = {sym}{amt_u:.4f}\n"
        f"📱 {sb('Method:')} {dep.get('method_name', dep.get('method','?'))}\n"
        f"🧾 {sb('TxID:')} <code>{dep.get('txid','?')}</code>\n"
        f"📅 {sb('Time:')} {dep.get('time','?')[:16]}\n"
        f"📊 {sb('Status:')} {dep.get('status','?')}\n"
        f"{divider()}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"adep_ok_{dep_id}_{uid_d}_{amt_u}"),
         InlineKeyboardButton("❌ Reject",  callback_data=f"adep_no_{dep_id}_{uid_d}")],
        [InlineKeyboardButton("⬅️ " + sb("Back"), callback_data="adm_deposits")],
    ])

    photo_id = dep.get("screenshot")
    if photo_id:
        try:
            await query.message.delete()
            await ctx.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo_id,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
            return
        except Exception:
            pass

    await safe_edit_text(query, text, reply_markup=kb)

async def adm_deposit_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("Admin only!", show_alert=True)
        return

    data = query.data.replace("adep_ok_", "")
    dep = fb_get(f"deposits/{data}", {})
    dep_id = data
    uid_d  = 0
    amount = 0.0

    if not dep:
        parts = data.rsplit("_", 2)
        dep_id = "_".join(parts[:-2]) if len(parts) >= 3 else parts[0]
        uid_d  = int(parts[-2]) if len(parts) >= 3 and parts[-2].isdigit() else 0
        amount = float(parts[-1]) if len(parts) >= 3 else 0.0
        dep = fb_get(f"deposits/{dep_id}", {})

    if not dep:
        await query.answer("❌ Deposit English English English!", show_alert=True)
        return

    status = dep.get("status")
    if status == "approved":
        await query.answer("⚠️ This Deposit English Approve (Approved) English has been!", show_alert=True)
        return
    elif status == "rejected":
        await query.answer("⚠️ This Deposit English Reject (Rejected) English has been!", show_alert=True)
        return

    s = get_settings()
    if amount <= 0:
        amount = float(dep.get("amount_usd", 0.0))
    if amount <= 0 and dep.get("amount_local"):
        rate = float(s.get("exchange_rate", 125))
        amount = round(float(dep.get("amount_local")) / rate, 4)

    if not uid_d and dep.get("uid"):
        uid_d = int(dep.get("uid"))

    fb_update(f"deposits/{dep_id}", {
        "status": "approved",
        "approved_by": query.from_user.id,
        "approved_at": datetime.now().isoformat()
    })

    user = get_user(uid_d)
    old_bal = float(user.get("balance", 0.0))
    new_bal = round(old_bal + amount, 4)
    old_dep = float(user.get("total_deposited", 0.0))

    # referral commission
    ref_pct = float(s.get("referral_pct", 5.0))
    referrer = user.get("referrer")
    if referrer and str(referrer) != str(uid_d):
        commission = round(amount * ref_pct / 100, 4)
        if commission > 0:
            ref_user = get_user(int(referrer))
            if ref_user:
                ref_bal = float(ref_user.get("balance", 0.0))
                ref_earned = float(ref_user.get("total_earned", 0.0))
                v_refs = int(ref_user.get("verified_referrals", 0))
                fb_update(f"users/{referrer}", {
                    "balance":           round(ref_bal + commission, 4),
                    "total_earned":      round(ref_earned + commission, 4),
                    "verified_referrals": v_refs + 1,
                })
                try:
                    await ctx.bot.send_message(
                        int(referrer),
                        f"🎉 {bold(sb('Referral Commission!'))}\n"
                        f"💰 {sb('Earned:')} {format_amount(commission, s)}\n"
                        f"📊 {sb('From deposit of your referral.')}",
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass

    fb_update(f"users/{uid_d}", {
        "balance": new_bal,
        "total_deposited": round(old_dep + amount, 4)
    })

    await safe_edit_text(
        query,
        f"✅ {bold(sb('Deposit Approved!'))}\n"
        f"👤 User: <code>{uid_d}</code>\n"
        f"💰 Added: {format_amount(amount, s)}\n"
        f"💳 New Balance: {format_amount(new_bal, s)}\n"
        f"🆔 Dep ID: <code>{dep_id}</code>\n"
        f"👑 Approved By: {query.from_user.id}",
        parse_mode=ParseMode.HTML)

    try:
        await ctx.bot.send_message(
            uid_d,
            f"🎉 {bold(sb('Deposit Approved!'))}\n"
            f"{divider()}\n"
            f"💰 {sb('Added Balance:')} <b>{format_amount(amount, s)}</b>\n"
            f"💳 {sb('Total Current Balance:')} <b>{format_amount(new_bal, s)}</b>\n"
            f"🆔 Deposit ID: <code>{dep_id}</code>\n"
            f"{divider()}\n"
            f"🛍️ <b>nowEnglish Shop from Your English Product English English!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(uid_d)
        )
    except Exception:
        pass

async def adm_deposit_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("Admin only!", show_alert=True)
        return

    data = query.data.replace("adep_no_", "")
    dep = fb_get(f"deposits/{data}", {})
    dep_id = data
    uid_d  = 0

    if not dep:
        parts = data.rsplit("_", 1)
        dep_id = "_".join(parts[:-1]) if len(parts) >= 2 else parts[0]
        uid_d  = int(parts[-1]) if len(parts) >= 2 and parts[-1].isdigit() else 0
        dep = fb_get(f"deposits/{dep_id}", {})

    if not dep:
        await query.answer("❌ Deposit English English English!", show_alert=True)
        return
    status = dep.get("status")
    if status == "approved":
        await query.answer("⚠️ This Deposit English English (Approved) has been!", show_alert=True)
        return
    elif status == "rejected":
        await query.answer("⚠️ This Deposit English Cancel (Rejected) English has been!", show_alert=True)
        return

    if not uid_d and dep.get("uid"):
        uid_d = int(dep.get("uid"))

    fb_update(f"deposits/{dep_id}", {
        "status": "rejected",
        "rejected_by": query.from_user.id,
        "rejected_at": datetime.now().isoformat()
    })
    await safe_edit_text(query, f"❌ Deposit <code>{dep_id}</code> (User: <code>{uid_d}</code>) Rejected.")

    try:
        if uid_d:
            s = get_settings()
            await ctx.bot.send_message(
                uid_d,
                f"❌ {bold(sb('Deposit Rejected'))}\n"
                f"{divider()}\n"
                f"Your Deposit English (ID: <code>{dep_id}</code>) Cancel English has been।\n"
                f"English TrxID or PaymentEnglish Proof with English Try English or <a href='{s.get('support_link','https://t.me/bd_top_admin')}'>SupportEnglish</a> AddEnglishAdd।",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(uid_d)
            )
    except Exception:
        pass

# ─── ADMIN: ADD BALANCE ──────────────────────────────────────
@admin_only
async def adm_addbal_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["awaiting"] = "adm_addbal_uid"
    await safe_edit_text(query, 
        f"💰 {bold(sb('ADD BALANCE'))}\n{divider()}\n"
        f"✏️ {sb('Enter User ID:')}", parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="adm_panel")]]))

# ─── ADMIN: BAN/UNBAN ────────────────────────────────────────
@admin_only
async def adm_ban_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["awaiting"] = "adm_ban_uid"
    await safe_edit_text(query, 
        f"⛔ {bold(sb('BAN / UNBAN USER'))}\n{divider()}\n"
        f"✏️ {sb('Enter User ID:')}", parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="adm_panel")]]))

# ─── ADMIN: BROADCAST ────────────────────────────────────────
@admin_only
async def adm_broadcast_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["awaiting"] = "adm_broadcast_msg"
    await safe_edit_text(query, 
        f"📢 {bold(sb('BROADCAST'))}\n{divider()}\n"
        f"✏️ {sb('Send the message to broadcast to all users:')}", parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="adm_panel")]]))

# ─── ADMIN: FIREBASE STATUS & SYNC ───────────────────────────
@admin_only
async def adm_fbstatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Run active health check
    health = check_firebase_health()
    
    users = fb_get("users", {})
    categories = fb_get("categories", {})
    deposits = fb_get("deposit_requests", {}) or fb_get("deposits", {})
    orders = fb_get("purchases", {})
    payment_methods = fb_get("payment_methods", {})
    settings = fb_get("settings", {})

    total_prods = sum(len(c.get("products", {})) for c in categories.values()) if isinstance(categories, dict) else 0
    
    text = (
        f"🔥 <b>English English English English English English</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>English English:</b> 🟢 0.01ms (English-English O(1) English English)\n"
        f"• <b>English English:</b> {health.get('diagnostic', 'OK')}\n"
        f"• <b>English English English:</b> {health.get('mode', 'Hybrid')}\n"
        f"• <b>Firebase URL:</b> <code>{FIREBASE_URL}</code>\n"
        f"• <b>English File English:</b> 🟢 <code>bot_data.json</code> (English)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>English English Current English English:</b>\n"
        f"• 👥 Total English User: <b>{len(users)} users</b>\n"
        f"• 📁 Category English: <b>{len(categories)} </b>\n"
        f"• 🤖 Total Product English English: <b>{total_prods} </b>\n"
        f"• 💳 Total Deposit English: <b>{len(deposits)} </b>\n"
        f"• 🛍️ Completed English English: <b>{len(orders)} </b>\n"
        f"• 💰 Payment Method English: <b>{len(payment_methods)} </b>\n"
        f"• ⚙️ English Settings: <b>English English English</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Bot now English% English-English English English। Button Click English Menu English with with any English English English English।</i>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 nowEnglish English English English English", callback_data="adm_fbreforce")],
        [InlineKeyboardButton("⬅️ English", callback_data="adm_panel")]
    ])
    await safe_edit_text(query, text, reply_markup=kb)

@admin_only
async def adm_fbreforce(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 English English English On has been...", show_alert=True)
    
    # Non-blocking sync: Enqueue all root keys to background worker
    with _cache_lock:
        items = list(_MEM_CACHE.items())
    for root_key, root_val in items:
        _enqueue_firebase_sync("PUT", root_key, root_val)
    
    await adm_fbstatus(update, ctx)

# ─── ADMIN: STATS ────────────────────────────────────────────
@admin_only
async def adm_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users       = fb_get("users", {})
    purchases   = fb_get("purchases", {})
    deposits    = fb_get("deposits", {})
    withdrawals = fb_get("withdrawals", {})
    cats        = fb_get("categories", {})
    s = get_settings()
    sym   = s.get("currency_symbol","$")
    local = s.get("local_currency","USD")
    rate  = s.get("exchange_rate",125)

    total_bal   = sum(u.get("balance",0) for u in users.values()) if isinstance(users, dict) else 0
    total_rev   = sum(p.get("price",0) for p in purchases.values()) if isinstance(purchases, dict) else 0
    banned      = sum(1 for u in users.values() if isinstance(u, dict) and u.get("banned")) if isinstance(users, dict) else 0
    total_prods = sum(len(c.get("products",{})) for c in cats.values()) if isinstance(cats, dict) else 0
    
    pending_d   = sum(1 for d in deposits.values() if isinstance(d, dict) and d.get("status")=="pending") if isinstance(deposits, dict) else 0
    approved_d  = sum(1 for d in deposits.values() if isinstance(d, dict) and d.get("status")=="approved") if isinstance(deposits, dict) else 0
    
    pending_w   = sum(1 for w in withdrawals.values() if isinstance(w, dict) and w.get("status")=="pending") if isinstance(withdrawals, dict) else 0
    approved_w  = sum(1 for w in withdrawals.values() if isinstance(w, dict) and w.get("status")=="approved") if isinstance(withdrawals, dict) else 0

    text = (
        f"📊 {bold(sb('BOT PERFORMANCE & ANALYTICS'))}\n"
        f"{divider()}\n"
        f"👥 {sb('Total Users:')} <b>{len(users)} users</b>\n"
        f"🚫 {sb('Banned Users:')} <b>{banned} users</b>\n"
        f"💰 {sb('Total System Balance:')} <b>{sym}{total_bal:.2f}</b> (~{round(total_bal * rate):,} {local})\n"
        f"{mini_divider()}\n"
        f"🛒 {sb('Total Orders Delivered:')} <b>{len(purchases)} </b>\n"
        f"💵 {sb('Total Product Revenue:')} <b>{sym}{total_rev:.2f}</b> (~{round(total_rev * rate):,} {local})\n"
        f"📂 {sb('Categories:')} <b>{len(cats)} </b> | 🎁 {sb('Scripts & Files:')} <b>{total_prods} </b>\n"
        f"{mini_divider()}\n"
        f"💳 {sb('Deposits:')} ⏳ Pending: <b>{pending_d}</b> | ✅ Approved: <b>{approved_d}</b>\n"
        f"📤 {sb('Withdrawals:')} ⏳ Pending: <b>{pending_w}</b> | ✅ Approved: <b>{approved_w}</b>\n"
        f"{divider()}\n"
        f"⚡ <i>English English English English-English English English English।</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 English English", callback_data="adm_stats"),
         InlineKeyboardButton("⬅️ Admin panel", callback_data="adm_panel")]
    ])
    await safe_edit_text(query, text, reply_markup=kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN: CHECK DATA LINK BUTTONS MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@admin_only
async def adm_checkdata(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    links = fb_get("check_data_links", {})
    if not isinstance(links, dict):
        links = {}

    text = (
        f"🔗 <b>CHECK DATA Link Button English</b>\n"
        f"{divider()}\n"
        f"📌 here Create English Link ButtonEnglish UserEnglish English <b>CHECK DATA</b> English English English।\n"
        f"any ButtonEnglish Click English directly English Link (English: Bot English English, English, English) English will be।\n"
        f"{divider()}\n\n"
    )

    buttons = []
    buttons.append([InlineKeyboardButton("➕ New Link Button Create English", callback_data="adm_addlink_start")])

    if links:
        text += f"📋 <b>Current English Link ButtonEnglish ({len(links)} ):</b>\n\n"
        for lid, linfo in links.items():
            if not isinstance(linfo, dict):
                continue
            title = linfo.get("title", "Link")
            url = linfo.get("url", "")
            text += f"🔹 <b>{title}</b>\n   🔗 <code>{url}</code>\n"
            buttons.append([
                InlineKeyboardButton(f"✏️ Name: {title[:12]}", callback_data=f"adm_edlt_{lid}"),
                InlineKeyboardButton("🔗 Link Edit", callback_data=f"adm_edlu_{lid}"),
                InlineKeyboardButton("🗑️", callback_data=f"adm_dellink_{lid}")
            ])
    else:
        text += "⚠️ <i>any Link Button Create English none। above ButtonEnglish Click and Create English।</i>"

    buttons.append([InlineKeyboardButton("⬅️ Admin panel", callback_data="adm_panel")])
    kb = InlineKeyboardMarkup(buttons)

    if query:
        await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

@admin_only
async def adm_addlink_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["awaiting"] = "adm_addlink_title"
    text = (
        f"➕ <b>New CHECK DATA Link Button Create (English English/English)</b>\n"
        f"{divider()}\n"
        f"📝 <b>ButtonEnglish Name / English Enter:</b>\n"
        f"<i>(English: 🌐 English English English English 📺 English English English 💬 English Group)</i>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_checkdata")]])
    await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def adm_edlink_title_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lid = query.data.replace("adm_edlt_", "")
    ctx.user_data["awaiting"] = f"adm_edlt_{lid}"
    link = fb_get(f"check_data_links/{lid}", {})
    text = (
        f"✏️ <b>Button English Edit</b>\n"
        f"{divider()}\n"
        f"Current Name: <b>{link.get('title', '')}</b>\n\n"
        f"📝 <b>New ButtonEnglish Name English Send:</b>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_checkdata")]])
    await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def adm_edlink_url_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lid = query.data.replace("adm_edlu_", "")
    ctx.user_data["awaiting"] = f"adm_edlu_{lid}"
    link = fb_get(f"check_data_links/{lid}", {})
    text = (
        f"🔗 <b>Button Link (URL) Edit</b>\n"
        f"{divider()}\n"
        f"Button: <b>{link.get('title', '')}</b>\n"
        f"Current Link: <code>{link.get('url', '')}</code>\n\n"
        f"🌐 <b>New Link English Send (English: https://...):</b>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_checkdata")]])
    await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def adm_dellink_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lid = query.data.replace("adm_dellink_", "")
    fb_delete(f"check_data_links/{lid}")
    await query.answer("🗑️ Link Button Successfully Delete English has been!", show_alert=True)
    await adm_checkdata(update, ctx)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN: FORCE JOIN CHANNELS MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@admin_only
async def adm_forcejoin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    s = get_settings()
    is_enabled = s.get("force_join_enabled", True)
    channels = get_force_join_channels()
    
    status_text = "🟢 English (Active)" if is_enabled else "🔴 Off (Disabled)"
    toggle_label = "⏸️ Force Join Closed English" if is_enabled else "▶️ Force Join On English"
    
    text = (
        f"📢 <b>FORCE JOIN Channel English Group English</b>\n"
        f"{divider()}\n"
        f"📌 <b>Current English:</b> {status_text}\n"
        f"💡 UserEnglish BotEnglish English English English English This ChannelEnglish Join English।\n"
        f"⚠️ <i>BotEnglish English Channel English GroupEnglish <b>Admin (Admin)</b> and English will be English English Check English English!</i>\n"
        f"{divider()}\n\n"
    )
    
    buttons = [
        [InlineKeyboardButton(f"🔘 {toggle_label}", callback_data="afj_toggle")],
        [InlineKeyboardButton("➕ New Channel / Group Add", callback_data="afj_add_start")],
    ]
    
    if channels:
        text += f"📋 <b>English ChannelEnglish ({len(channels)} ):</b>\n\n"
        for cid, ch in channels.items():
            if not isinstance(ch, dict):
                continue
            name = ch.get("name", "Join")
            chat_id = ch.get("id", "@channel")
            url = ch.get("url", "https://t.me/...")
            text += f"🔹 <b>{name}</b>\n   🆔 <code>{chat_id}</code>\n   🔗 <code>{url}</code>\n"
            buttons.append([
                InlineKeyboardButton(f"✏️ Name: {name[:10]}", callback_data=f"afj_edname_{cid}"),
                InlineKeyboardButton("🆔 ID", callback_data=f"afj_edid_{cid}"),
                InlineKeyboardButton("🔗 Link", callback_data=f"afj_edurl_{cid}"),
                InlineKeyboardButton("🗑️", callback_data=f"afj_del_{cid}")
            ])
    else:
        text += "⚠️ <i>any Channel English English none। above ButtonEnglish Click and Channel Add।</i>\n"
        
    buttons.append([InlineKeyboardButton("⬅️ Admin panel", callback_data="adm_panel")])
    kb = InlineKeyboardMarkup(buttons)
    
    if query:
        await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

@admin_only
async def afj_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    s = get_settings()
    curr = s.get("force_join_enabled", True)
    new_val = not curr
    fb_update("settings", {"force_join_enabled": new_val})
    status_str = "On" if new_val else "Closed"
    await query.answer(f"📢 Force Join English {status_str} English has been!", show_alert=True)
    await adm_forcejoin(update, ctx)

@admin_only
async def afj_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["awaiting"] = "afj_add_id"
    text = (
        f"➕ <b>New Force Join Channel Add (English English/English)</b>\n"
        f"{divider()}\n"
        f"📌 <b>Channel English GroupEnglish Username or Chat ID Enter:</b>\n"
        f"<i>(English: <code>@bd_top_admin</code> or English English <code>-1001234567890</code>)</i>\n\n"
        f"⚠️ <b>English English:</b> BotEnglish English English ChannelEnglish Admin EnglishnotEnglish will be।"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_forcejoin")]])
    await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def afj_del_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    cid = query.data.replace("afj_del_", "")
    fb_delete(f"force_join_channels/{cid}")
    await query.answer("🗑️ Channel Successfully English English has been!", show_alert=True)
    await adm_forcejoin(update, ctx)

@admin_only
async def afj_edname_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = query.data.replace("afj_edname_", "")
    ctx.user_data["awaiting"] = f"afj_edname_{cid}"
    ch = fb_get(f"force_join_channels/{cid}", {})
    text = (
        f"✏️ <b>Channel Button Name Edit</b>\n"
        f"{divider()}\n"
        f"Current Name: <b>{ch.get('name', '')}</b>\n\n"
        f"📝 <b>New ButtonEnglish Name English Send (English: Join=ಌ English Join ♕):</b>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_forcejoin")]])
    await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def afj_edid_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = query.data.replace("afj_edid_", "")
    ctx.user_data["awaiting"] = f"afj_edid_{cid}"
    ch = fb_get(f"force_join_channels/{cid}", {})
    text = (
        f"🆔 <b>Channel ID Edit</b>\n"
        f"{divider()}\n"
        f"Current ID: <code>{ch.get('id', '')}</code>\n\n"
        f"📝 <b>New Username English Chat ID English Send:</b>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_forcejoin")]])
    await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def afj_edurl_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = query.data.replace("afj_edurl_", "")
    ctx.user_data["awaiting"] = f"afj_edurl_{cid}"
    ch = fb_get(f"force_join_channels/{cid}", {})
    text = (
        f"🔗 <b>Channel English Link Edit</b>\n"
        f"{divider()}\n"
        f"Current Link: <code>{ch.get('url', '')}</code>\n\n"
        f"🌐 <b>New English Link English Send:</b>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_forcejoin")]])
    await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN: ROLES & ADMIN MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@admin_only
async def adm_roles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    caller_uid = update.effective_user.id
    admins = fb_get("admins", {})
    if not isinstance(admins, dict):
        admins = {}
    
    text = (
        f"👑 <b>Admin English English English (RBAC System)</b>\n"
        f"{divider()}\n"
        f"📌 <b>Admin English Description:</b>\n"
        f"• 👑 <b>Owner:</b> English Englishnot English English English।\n"
        f"• 🛠️ <b>Manager:</b> Product, Category, Deposit English Link English English English।\n"
        f"• 👁️ <b>View Only:</b> English Information English English English English (Edit English)।\n"
        f"{divider()}\n\n"
    )
    
    buttons = []
    if is_owner(caller_uid):
        buttons.append([InlineKeyboardButton("➕ Add new admin", callback_data="adm_addadmin_start")])
    
    text += f"📋 <b>Current Admin English ({len(admins)} users):</b>\n\n"
    for aid_str, ainfo in admins.items():
        if not isinstance(ainfo, dict):
            continue
        aid = ainfo.get("id", aid_str)
        aname = ainfo.get("name", "Admin")
        arole = ainfo.get("role", "viewer")
        
        badge = "👑 Owner" if arole == "owner" else ("🛠️ Manager" if arole == "manager" else "👁️ View Only")
        text += f"👤 <b>{aname}</b> (<code>{aid}</code>)\n   🔰 English: <b>{badge}</b>\n"
        
        if is_owner(caller_uid) and str(aid) not in [str(x) for x in ADMIN_IDS] and arole != "owner":
            next_role = "viewer" if arole == "manager" else "manager"
            next_label = "👁️ View Only English" if next_role == "viewer" else "🛠️ Manager English"
            buttons.append([
                InlineKeyboardButton(f"🔄 {next_label}", callback_data=f"adm_chrole_{aid}_{next_role}"),
                InlineKeyboardButton("🗑️ Remove", callback_data=f"adm_deladmin_{aid}")
            ])
            
    buttons.append([InlineKeyboardButton("⬅️ Admin panel", callback_data="adm_panel")])
    kb = InlineKeyboardMarkup(buttons)
    
    if query:
        await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

@owner_only
async def adm_addadmin_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["awaiting"] = "adm_addadmin_id"
    text = (
        f"➕ <b>Add new admin</b>\n"
        f"{divider()}\n"
        f"📝 <b>English UserEnglish Admin EnglishnotEnglish English English Telegram User ID English Send:</b>\n"
        f"<i>(User /id English English English ID English English)</i>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_roles")]])
    await safe_edit_text(query, text, parse_mode=ParseMode.HTML, reply_markup=kb)

@owner_only
async def adm_setrole_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # data: adm_setrole_{role}_{uid}
    parts = query.data.replace("adm_setrole_", "").split("_", 1)
    role, target_uid_str = parts[0], parts[1]
    target_uid = int(target_uid_str)
    
    u = get_user(target_uid)
    uname = u.get("name") or u.get("username") or f"User_{target_uid}"
    
    admin_obj = {
        "id": target_uid,
        "name": uname,
        "role": role,
        "added_at": datetime.now().isoformat()
    }
    fb_set(f"admins/{target_uid}", admin_obj)
    fb_update(f"users/{target_uid}", {"is_admin": True, "role": role})
    
    role_name = "Manager (English)" if role == "manager" else "View Only (English)"
    await query.answer(f"✅ {uname} English Successfully {role_name} English has been!", show_alert=True)
    
    try:
        await ctx.bot.send_message(
            chat_id=target_uid,
            text=f"🎉 <b>English!</b> EnglishnotEnglish BotEnglish <b>{role_name}</b> English English English has been।\nEnglish English <b>/admin</b> English English!",
            parse_mode=ParseMode.HTML
        )
    except:
        pass
        
    await adm_roles(update, ctx)

@owner_only
async def adm_chrole_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.replace("adm_chrole_", "").split("_", 1)
    target_uid_str, next_role = parts[0], parts[1]
    target_uid = int(target_uid_str)
    
    fb_update(f"admins/{target_uid}", {"role": next_role})
    fb_update(f"users/{target_uid}", {"role": next_role})
    
    role_name = "Manager" if next_role == "manager" else "View Only"
    await query.answer(f"✅ English English and {role_name} English has been!", show_alert=True)
    await adm_roles(update, ctx)

@owner_only
async def adm_deladmin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    target_uid_str = query.data.replace("adm_deladmin_", "")
    target_uid = int(target_uid_str)
    
    fb_delete(f"admins/{target_uid}")
    fb_update(f"users/{target_uid}", {"is_admin": False, "role": "user"})
    
    await query.answer("🗑️ Admin Remove English has been!", show_alert=True)
    await adm_roles(update, ctx)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN INPUT HANDLER (text, photo, document upload)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@admin_only
async def admin_text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    awaiting = ctx.user_data.get("awaiting")
    text = update.message.text.strip() if update.message.text else ""

    if awaiting == "adm_broadcast_msg":
        ctx.user_data["awaiting"] = None
        users = fb_get("users", {})
        sent = 0
        for uid_s in users:
            try:
                await ctx.bot.send_message(int(uid_s), text, parse_mode=ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
        await update.message.reply_text(
            f"📢 {sb('Broadcast sent to')} {sent}/{len(users)} {sb('users.')}",
            reply_markup=main_menu_keyboard())

    elif awaiting == "adm_addbal_uid":
        if text.isdigit():
            ctx.user_data["adm_addbal_uid"] = int(text)
            ctx.user_data["awaiting"] = "adm_addbal_amount"
            await update.message.reply_text(
                f"💰 {sb('Enter amount to add (in USD):')}")
        else:
            await update.message.reply_text(f"❌ {sb('Invalid user ID.')}")

    elif awaiting == "adm_addbal_amount":
        try:
            amount = float(text)
            uid_t = ctx.user_data.get("adm_addbal_uid")
            user_t = get_user(uid_t)
            if not user_t:
                await update.message.reply_text(f"❌ {sb('User not found.')}")
            else:
                s = get_settings()
                old = user_t.get("balance",0)
                new = round(old + amount, 4)
                fb_update(f"users/{uid_t}", {"balance": new})
                ctx.user_data["awaiting"] = None
                await update.message.reply_text(
                    f"✅ {sb('Balance added!')}\n"
                    f"👤 {uid_t}\n"
                    f"💰 Added: {format_amount(amount, s)}\n"
                    f"💳 New Balance: {format_amount(new, s)}",
                    parse_mode=ParseMode.HTML)
                try:
                    await ctx.bot.send_message(
                        uid_t,
                        f"✅ {bold(sb('Balance Added by Admin!'))}\n"
                        f"💰 {sb('Added:')} {format_amount(amount, s)}\n"
                        f"💳 {sb('New Balance:')} {format_amount(new, s)}",
                        parse_mode=ParseMode.HTML)
                except:
                    pass
        except ValueError:
            await update.message.reply_text(f"❌ {sb('Invalid amount.')}")

    elif awaiting == "adm_ban_uid":
        if text.isdigit():
            uid_b = int(text)
            user_b = get_user(uid_b)
            if not user_b:
                await update.message.reply_text(f"❌ {sb('User not found.')}")
            else:
                is_banned = user_b.get("banned", False)
                fb_update(f"users/{uid_b}", {"banned": not is_banned})
                action = "Unbanned" if is_banned else "Banned"
                ctx.user_data["awaiting"] = None
                await update.message.reply_text(
                    f"✅ User {uid_b} {action} successfully.")
        else:
            await update.message.reply_text(f"❌ {sb('Invalid user ID.')}")

    # Settings text inputs
    elif awaiting and awaiting.startswith("aset_"):
        field = awaiting.replace("aset_","")
        ctx.user_data["awaiting"] = None
        # Type conversion
        if field in ["exchange_rate","min_deposit","min_withdraw","referral_pct"]:
            try:
                val = float(text)
            except:
                await update.message.reply_text("❌ Invalid number.")
                return
        else:
            val = text
        fb_update("settings", {field: val})
        await update.message.reply_text(
            f"✅ {sb('Setting updated!')}\n{field}: {val}",
            reply_markup=main_menu_keyboard())

    # Category creation
    elif awaiting == "adm_addcat_name":
        cat_id = text.lower().replace(" ","_").replace("/","_")
        fb_set(f"categories/{cat_id}", {"name": text, "products": {}})
        ctx.user_data["awaiting"] = None
        await update.message.reply_text(
            f"✅ {sb('Category')} '{text}' {sb('created!')}",
            reply_markup=main_menu_keyboard())

    # ─── 7-STEP PRODUCT CREATION WIZARD (ADVANCED & MULTI-FILE) ───
    # STEP 1: Name -> Ask for Description
    elif awaiting == "adm_addprod_name":
        ctx.user_data["adm_new_prod"] = {"name": text, "files": []}
        ctx.user_data["awaiting"] = "adm_addprod_desc"
        await update.message.reply_text(
            f"📝 {bold('STEP 2/7: Product Description & Details')}\n{divider()}\n"
            f"✏️ Product English English English English Enter:\n"
            f"<i>(or English English <code>skip</code> English Send)</i>",
            parse_mode=ParseMode.HTML)

    # STEP 2: Description -> Ask for Photo/Video Banner
    elif awaiting == "adm_addprod_desc":
        if text.lower() != "skip":
            ctx.user_data["adm_new_prod"]["description"] = text
        ctx.user_data["awaiting"] = "adm_addprod_image"
        await update.message.reply_text(
            f"🖼️/🎥 {bold('STEP 3/7: Product Banner (Photo or Video)')}\n{divider()}\n"
            f"📸 ProductEnglish for English <b>English (Photo)</b> or <b>English (Video)</b> directly Send:\n"
            f"🔗 or English/English English English English Send।\n"
            f"<i>(or any EnglishnotEnglish English English <code>skip</code> English Send)</i>",
            parse_mode=ParseMode.HTML)

    # STEP 3: Photo/Video -> Ask for Run Guide & Commands (Option 4 requested by user)
    elif awaiting == "adm_addprod_image":
        if update.message.video:
            vid_id = update.message.video.file_id
            ctx.user_data["adm_new_prod"]["video"] = vid_id
            ctx.user_data["adm_new_prod"]["image"] = vid_id
            ctx.user_data["adm_new_prod"]["media_type"] = "video"
        elif update.message.animation:
            anim_id = update.message.animation.file_id
            ctx.user_data["adm_new_prod"]["image"] = anim_id
            ctx.user_data["adm_new_prod"]["media_type"] = "animation"
        elif update.message.photo:
            photo_file_id = update.message.photo[-1].file_id
            ctx.user_data["adm_new_prod"]["image"] = photo_file_id
            ctx.user_data["adm_new_prod"]["media_type"] = "photo"
        elif update.message.document and update.message.document.mime_type:
            mime = update.message.document.mime_type
            if mime.startswith("video/"):
                ctx.user_data["adm_new_prod"]["video"] = update.message.document.file_id
                ctx.user_data["adm_new_prod"]["image"] = update.message.document.file_id
                ctx.user_data["adm_new_prod"]["media_type"] = "video"
            elif mime.startswith("image/"):
                ctx.user_data["adm_new_prod"]["image"] = update.message.document.file_id
                ctx.user_data["adm_new_prod"]["media_type"] = "photo"
        elif text and text.lower() != "skip":
            ctx.user_data["adm_new_prod"]["image"] = text
            if any(text.lower().endswith(ext) for ext in [".mp4", ".mov", ".webm", ".avi"]):
                ctx.user_data["adm_new_prod"]["video"] = text
                ctx.user_data["adm_new_prod"]["media_type"] = "video"
            else:
                ctx.user_data["adm_new_prod"]["media_type"] = "photo"

        ctx.user_data["awaiting"] = "adm_addprod_runguide"
        await update.message.reply_text(
            f"🛠️ {bold('STEP 4/7: English English English English English (Setup & Run Guide)')}\n{divider()}\n"
            f"📌 <b>UserEnglish This Bot English English English English English English English Instructions English:</b>\n"
            f"💡 English: Required English, English English, EnglishnotEnglish English English English any English English Details English Send।\n\n"
            f"<i>(EnglishnotEnglish English User This English English English। English not English English <code>skip</code> English Send)</i>",
            parse_mode=ParseMode.HTML)

    # STEP 4: Run Guide -> Ask for Demo Bot Link
    elif awaiting == "adm_addprod_runguide":
        if text and text.lower() != "skip":
            ctx.user_data["adm_new_prod"]["run_guide"] = text

        ctx.user_data["awaiting"] = "adm_addprod_demolink"
        await update.message.reply_text(
            f"🤖 {bold('STEP 5/7: Demo Bot Link / Username')}\n{divider()}\n"
            f"🔗 English English for English Bot Link English @username Enter:\n"
            f"<i>(English: <code>https://t.me/YourDemoBot</code> English <code>@YourDemoBot</code>, or English English <code>skip</code>)</i>",
            parse_mode=ParseMode.HTML)

    # STEP 5: Demo Link -> Ask for Price (USD)
    elif awaiting == "adm_addprod_demolink":
        if text and text.lower() != "skip":
            dlink = text
            if not dlink.startswith("http") and not dlink.startswith("@"):
                dlink = f"https://t.me/{dlink}"
            ctx.user_data["adm_new_prod"]["demo_link"] = dlink

        ctx.user_data["awaiting"] = "adm_addprod_price"
        s = get_settings()
        rate = s.get("exchange_rate", 125)
        local = s.get("local_currency", "USD")
        await update.message.reply_text(
            f"💰 {bold('STEP 6/7: Product Price (USD)')}\n{divider()}\n"
            f"💵 ProductEnglish Price USD English Enter (English: <code>5.0</code> English <code>2.5</code>):\n"
            f"<i>Current Exchange rate: 1 USD = {rate} {local} (English: $5 = {5*rate} {local})</i>",
            parse_mode=ParseMode.HTML)

    # STEP 6: Price -> Ask for Files Upload (Supports Multiple Files)
    elif awaiting == "adm_addprod_price":
        try:
            price = float(text)
            ctx.user_data["adm_new_prod"]["price"] = price
            ctx.user_data["adm_new_prod"]["files"] = []
            ctx.user_data["awaiting"] = "adm_addprod_file_or_stock"
            await update.message.reply_text(
                f"📁 {bold('STEP 7/7: English English File English English Stock English')}\n{divider()}\n"
                f"📤 <b>BotEnglish FileEnglish Send (Multi-File Support):</b>\n"
                f"• English English English File English English English English English English English (English: <code>.zip</code>, <code>.py</code>, <code>.json</code>, <code>.txt</code> English)।\n"
                f"• English File sentEnglish English Bot English Save English।\n"
                f"• All File sent End English <code>done</code> English English Completed English।\n\n"
                f"📝 <b>or (English / English English-English English):</b>\n"
                f"directly English English Stock English English English English।",
                parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Please English English Enter (English: 5.0)।")

    # STEP 7: Multi-File Upload OR Done OR Text Stock
    elif awaiting == "adm_addprod_file_or_stock":
        prod_data = ctx.user_data.get("adm_new_prod", {})
        cat_id = ctx.user_data.get("adm_addprod_cat")
        pname = prod_data.get("name", "Product")
        pid = pname.lower().replace(" ", "_").replace("/", "_")
        s = get_settings()

        if update.message.document:
            doc = update.message.document
            file_id = doc.file_id
            file_name = doc.file_name or f"script_{len(prod_data.get('files', []))+1}.zip"
            if "files" not in prod_data:
                prod_data["files"] = []
            prod_data["files"].append({"file_id": file_id, "file_name": file_name})
            total_f = len(prod_data["files"])

            await update.message.reply_text(
                f"✅ <b>File Successfully Add has been! (#{total_f})</b>\n"
                f"📁 Name: <code>{file_name}</code>\n"
                f"📎 Total File English: <b>{total_f}</b> \n{mini_divider()}\n"
                f"💡 <i>More any File English English English, or English End English <code>done</code> English Send।</i>",
                parse_mode=ParseMode.HTML
            )
            return

        elif text and text.strip().lower() == "done":
            files = prod_data.get("files", [])
            if not files:
                await update.message.reply_text("⚠️ You nowEnglish any File SendEnglish! File English English Send or English Stock Enter।")
                return

            main_file = files[0]
            prod_data["is_file"] = True
            prod_data["file_id"] = main_file["file_id"]
            prod_data["file_name"] = main_file["file_name"]
            item_str = f"FILE::{main_file['file_id']}::{main_file['file_name']}"
            prod_data["items"] = [item_str] * 999
            prod_data["stock"] = 999

            fb_set(f"categories/{cat_id}/products/{pid}", prod_data)
            ctx.user_data["awaiting"] = None

            price_str = format_amount(prod_data.get("price", 0), s)
            guide_info = "✅ is attached" if prod_data.get("run_guide") else "❌ none"
            await update.message.reply_text(
                f"🎉 {bold('Product Successfully Create English ShopEnglish English has been!')}\n"
                f"{divider()}\n"
                f"📦 {sb('Name:')} {bold(pname)}\n"
                f"💰 {sb('Price:')} {bold(price_str)}\n"
                f"📁 {sb('English File:')} Total <b>{len(files)}</b>  File (Auto Instant Delivery ⚡)\n"
                f"🛠️ {sb('English English English English:')} {guide_info}\n"
                f"🖼️ {sb('EnglishnotEnglish English:')} {'✅ Yes' if prod_data.get('image') else '❌ No'}\n"
                f"🤖 {sb('English Link:')} {prod_data.get('demo_link', 'None')}\n"
                f"📊 {sb('English Stock:')} 999  English\n"
                f"{divider()}\n"
                f"🛒 <i>Product now English has been and UserEnglish Shop Menu from English English!</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(update.effective_user.id)
            )

        elif text and text.strip():
            items = [line.strip() for line in text.split("\n") if line.strip()]
            prod_data["is_file"] = False
            prod_data["items"] = items
            prod_data["stock"] = len(items)
            fb_set(f"categories/{cat_id}/products/{pid}", prod_data)
            ctx.user_data["awaiting"] = None

            price_str = format_amount(prod_data.get("price", 0), s)
            await update.message.reply_text(
                f"✅ {bold(sb('Product Created Successfully!'))}\n"
                f"{divider()}\n"
                f"📦 {sb('Name:')} {bold(pname)}\n"
                f"💰 {sb('Price:')} {bold(price_str)}\n"
                f"📝 {sb('Stock Items:')} {len(items)}\n"
                f"🖼️ {sb('Photo:')} {'✅ Yes' if prod_data.get('image') else '❌ No'}\n"
                f"🤖 {sb('Demo Bot:')} {prod_data.get('demo_link', 'None')}\n"
                f"{divider()}\n"
                f"🛒 {sb('Product is now live in the Shop menu!')}",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(update.effective_user.id))
        else:
            await update.message.reply_text("❌ Please send a file or enter text items.")

    # Stock addition for existing products
    elif awaiting and awaiting.startswith("adm_addstock_"):
        parts = awaiting.replace("adm_addstock_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        prod = fb_get(f"categories/{cat_id}/products/{pid}", {})

        if update.message.document:
            doc = update.message.document
            file_id = doc.file_id
            file_name = doc.file_name or f"{pid}.zip"
            item_str = f"FILE::{file_id}::{file_name}"
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "is_file": True,
                "file_id": file_id,
                "file_name": file_name,
                "items": [item_str] * 999,
                "stock": 999,
            })
            ctx.user_data["awaiting"] = None
            await update.message.reply_text(
                f"✅ {sb('Product script file updated to')} <code>{file_name}</code> (Stock: 999)",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard())
        elif text and text.strip():
            new_items = [line.strip() for line in text.split("\n") if line.strip()]
            old_items = prod.get("items", [])
            merged = old_items + new_items
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "items": merged,
                "stock": len(merged),
            })
            ctx.user_data["awaiting"] = None
            await update.message.reply_text(
                f"✅ {sb('Added')} {len(new_items)} {sb('items. Total stock:')} {len(merged)}",
                reply_markup=main_menu_keyboard())

    elif awaiting and awaiting.startswith("apm_edit_"):
        key = awaiting.replace("apm_edit_","")
        ctx.user_data["awaiting"] = None
        fb_update(f"payment_methods/{key}", {"number": text})
        await update.message.reply_text(
            f"✅ {sb('Payment number updated for')} {key}.",
            reply_markup=main_menu_keyboard())

    # Script/Product Editor: Name
    elif awaiting and awaiting.startswith("aedt_name_"):
        parts = awaiting.replace("aedt_name_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        ctx.user_data["awaiting"] = None
        fb_update(f"categories/{cat_id}/products/{pid}", {"name": text})
        await update.message.reply_text(
            f"✅ <b>English/ProductEnglish Name English English has been:</b>\n<code>{text}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
        )

    # Script/Product Editor: Price
    elif awaiting and awaiting.startswith("aedt_price_"):
        parts = awaiting.replace("aedt_price_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        try:
            val = float(text)
            ctx.user_data["awaiting"] = None
            fb_update(f"categories/{cat_id}/products/{pid}", {"price": val})
            s = get_settings()
            rate = s.get("exchange_rate", 125)
            local_sym = s.get("local_currency", "$")
            await update.message.reply_text(
                f"✅ <b>Price Successfully English English has been:</b>\n💰 <code>{val}$</code> ({round(val*rate, 2)} {local_sym})",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
            )
        except ValueError:
            await update.message.reply_text("❌ Please English English Enter (English: 5.0)।")

    # Script/Product Editor: Demo Link
    elif awaiting and awaiting.startswith("aedt_demo_"):
        parts = awaiting.replace("aedt_demo_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        ctx.user_data["awaiting"] = None
        if text.lower() == "clear":
            val = ""
        elif text.startswith("http") or text.startswith("@"):
            val = text
        else:
            val = f"https://t.me/{text}"
        fb_update(f"categories/{cat_id}/products/{pid}", {"demo_link": val})
        await update.message.reply_text(
            f"✅ <b>English Link English English has been:</b>\n🔗 {val if val else '<i>Remove English has been</i>'}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
        )

    # Script/Product Editor: Description
    elif awaiting and awaiting.startswith("aedt_desc_"):
        parts = awaiting.replace("aedt_desc_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        ctx.user_data["awaiting"] = None
        fb_update(f"categories/{cat_id}/products/{pid}", {"description": text})
        await update.message.reply_text(
            f"✅ <b>English Successfully English English has been!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
        )

    # Script/Product Editor: Run Guide & Commands
    elif awaiting and awaiting.startswith("aedt_guide_"):
        parts = awaiting.replace("aedt_guide_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        ctx.user_data["awaiting"] = None
        val = "" if text.strip().lower() == "clear" else text
        fb_update(f"categories/{cat_id}/products/{pid}", {"run_guide": val})
        await update.message.reply_text(
            f"✅ <b>English English English English English English English has been!</b>\n\n{val if val else '<i>Remove English has been</i>'}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
        )

    # Script/Product Editor: Media (Photo/Video)
    elif awaiting and awaiting.startswith("aedt_media_"):
        parts = awaiting.replace("aedt_media_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        ctx.user_data["awaiting"] = None

        if text.lower() in ["remove", "clear", "delete", "none"]:
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "image": None,
                "video": None,
                "media_type": None
            })
            await update.message.reply_text(
                "✅ <b>ProductEnglish English EnglishnotEnglish Successfully English English has been!</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
            )
        elif update.message.video:
            vid_id = update.message.video.file_id
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "video": vid_id,
                "image": vid_id,
                "media_type": "video"
            })
            await update.message.reply_text(
                "✅ <b>New English EnglishnotEnglish Successfully English English has been! 🎥</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
            )
        elif update.message.animation:
            anim_id = update.message.animation.file_id
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "image": anim_id,
                "video": None,
                "media_type": "animation"
            })
            await update.message.reply_text(
                "✅ <b>New English/GIF EnglishnotEnglish Successfully English English has been! ✨</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
            )
        elif update.message.photo:
            photo_file_id = update.message.photo[-1].file_id
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "image": photo_file_id,
                "video": None,
                "media_type": "photo"
            })
            await update.message.reply_text(
                "✅ <b>New English EnglishnotEnglish Successfully English English has been! 🖼️</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
            )
        elif update.message.document and update.message.document.mime_type:
            mime = update.message.document.mime_type
            if mime.startswith("video/"):
                vid_id = update.message.document.file_id
                fb_update(f"categories/{cat_id}/products/{pid}", {
                    "video": vid_id,
                    "image": vid_id,
                    "media_type": "video"
                })
                await update.message.reply_text(
                    "✅ <b>New English EnglishnotEnglish English English has been! 🎥</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
                )
            else:
                img_id = update.message.document.file_id
                fb_update(f"categories/{cat_id}/products/{pid}", {
                    "image": img_id,
                    "video": None,
                    "media_type": "photo"
                })
                await update.message.reply_text(
                    "✅ <b>New English EnglishnotEnglish English English has been! 🖼️</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
                )
        elif text and text.strip():
            is_vid = any(text.lower().endswith(ext) for ext in [".mp4", ".mov", ".webm", ".avi"])
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "image": text,
                "video": text if is_vid else None,
                "media_type": "video" if is_vid else "photo"
            })
            await update.message.reply_text(
                f"✅ <b>English English Successfully English English has been!</b> ({'English 🎥' if is_vid else 'English 🖼️'})",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
            )
        else:
            await update.message.reply_text("❌ Please English English English Send or remove Enter।")

    # Script/Product Editor: Entry File
    elif awaiting and awaiting.startswith("aedt_entry_"):
        parts = awaiting.replace("aedt_entry_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        ctx.user_data["awaiting"] = None
        fb_update(f"categories/{cat_id}/products/{pid}", {"entry_file": text})
        await update.message.reply_text(
            f"✅ <b>English English File English English has been:</b> <code>{text}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
        )

    # Script/Product Editor: Upload New File / Stock
    elif awaiting and awaiting.startswith("aedt_file_"):
        parts = awaiting.replace("aedt_file_","").split("_",1)
        cat_id, pid = parts[0], parts[1]
        if update.message.document:
            doc = update.message.document
            file_id = doc.file_id
            file_name = doc.file_name or f"{pid}.zip"
            item_str = f"FILE::{file_id}::{file_name}"
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "is_file": True,
                "file_id": file_id,
                "file_name": file_name,
                "items": [item_str] * 999,
                "stock": 999,
            })
            ctx.user_data["awaiting"] = None
            await update.message.reply_text(
                f"✅ <b>New English File Successfully English English has been:</b>\n📁 <code>{file_name}</code> (Auto Delivery English ⚡)",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
            )
        elif text and text.strip():
            new_items = [line.strip() for line in text.split("\n") if line.strip()]
            fb_update(f"categories/{cat_id}/products/{pid}", {
                "items": new_items,
                "stock": len(new_items),
                "is_file": False
            })
            ctx.user_data["awaiting"] = None
            await update.message.reply_text(
                f"✅ <b>Stock English English Completed!</b> (Total Stock: {len(new_items)})",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Back to editor", callback_data=f"adm_prod_{cat_id}_{pid}")]])
            )

    # ─── CHECK DATA LINK BUTTON BUILDER & EDITORS ───
    # Link Creation: Step 1 Title -> Ask for URL
    elif awaiting == "adm_addlink_title":
        ctx.user_data["new_link_title"] = text
        ctx.user_data["awaiting"] = "adm_addlink_url"
        await update.message.reply_text(
            f"🔗 <b>New CHECK DATA Link Button Create (English English/English)</b>\n"
            f"{divider()}\n"
            f"ButtonEnglish Name: <b>{text}</b>\n\n"
            f"🌐 <b>English directly English Link (URL) Send:</b>\n"
            f"<i>(English: <code>https://render.com</code> English <code>https://t.me/yourchannel</code>)</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_checkdata")]])
        )

    # Link Creation: Step 2 URL -> Save
    elif awaiting == "adm_addlink_url":
        title = ctx.user_data.get("new_link_title", "Link")
        url = text.strip()
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("tg://"):
            url = f"https://{url}"
        lid = f"link_{int(datetime.now().timestamp() * 1000)}"
        fb_set(f"check_data_links/{lid}", {"title": title, "url": url})
        ctx.user_data["awaiting"] = None
        ctx.user_data["new_link_title"] = None
        await update.message.reply_text(
            f"✅ <b>New CHECK DATA Link Button Successfully Create has been!</b>\n\n"
            f"👉 <b>ButtonEnglish Name:</b> {title}\n"
            f"🔗 <b>Link:</b> <code>{url}</code>\n\n"
            f"⚡ <i>UserEnglish now <b>CHECK DATA</b> ButtonEnglish Click English directly This LinkEnglish English English।</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Link Button managerEnglish Back", callback_data="adm_checkdata")]])
        )

    # Link Title Edit
    elif awaiting and awaiting.startswith("adm_edlt_"):
        lid = awaiting.replace("adm_edlt_", "")
        ctx.user_data["awaiting"] = None
        fb_update(f"check_data_links/{lid}", {"title": text})
        await update.message.reply_text(
            f"✅ <b>Button English English Completed!</b>\n👉 <b>{text}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Link Button managerEnglish Back", callback_data="adm_checkdata")]])
        )

    # Link URL Edit
    elif awaiting and awaiting.startswith("adm_edlu_"):
        lid = awaiting.replace("adm_edlu_", "")
        ctx.user_data["awaiting"] = None
        url = text.strip()
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("tg://"):
            url = f"https://{url}"
        fb_update(f"check_data_links/{lid}", {"url": url})
        await update.message.reply_text(
            f"✅ <b>Button Link English Completed!</b>\n🔗 <code>{url}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Link Button managerEnglish Back", callback_data="adm_checkdata")]])
        )

    # ─── FORCE JOIN CHANNELS BUILDER & EDITORS ───
    # Step 1: Channel ID -> Ask for Button Name
    elif awaiting == "afj_add_id":
        ctx.user_data["new_fj_id"] = text.strip()
        ctx.user_data["awaiting"] = "afj_add_name"
        await update.message.reply_text(
            f"➕ <b>New Force Join Channel Add (English English/English)</b>\n"
            f"{divider()}\n"
            f"Channel ID: <code>{text.strip()}</code>\n\n"
            f"📝 <b>ButtonEnglish Name English English Enter:</b>\n"
            f"<i>(English: <code>Join=ಌ</code> English <code>Join ♕</code> English <code>Official Channel</code>)</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_forcejoin")]])
        )

    # Step 2: Button Name -> Ask for Invite Link
    elif awaiting == "afj_add_name":
        ctx.user_data["new_fj_name"] = text.strip()
        ctx.user_data["awaiting"] = "afj_add_url"
        await update.message.reply_text(
            f"➕ <b>New Force Join Channel Add (English English/English)</b>\n"
            f"{divider()}\n"
            f"ButtonEnglish Name: <b>{text.strip()}</b>\n\n"
            f"🌐 <b>ChannelEnglish English Link English Send:</b>\n"
            f"<i>(English: <code>https://t.me/yourchannel</code>)</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_forcejoin")]])
        )

    # Step 3: Invite Link -> Save to Firebase
    elif awaiting == "afj_add_url":
        ch_id = ctx.user_data.get("new_fj_id", "")
        ch_name = ctx.user_data.get("new_fj_name", "Join")
        url = text.strip()
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("tg://"):
            url = f"https://{url}"
        cid = f"ch_{int(datetime.now().timestamp() * 1000)}"
        ch_obj = {"id": ch_id, "name": ch_name, "url": url}
        fb_set(f"force_join_channels/{cid}", ch_obj)
        ctx.user_data["awaiting"] = None
        ctx.user_data["new_fj_id"] = None
        ctx.user_data["new_fj_name"] = None
        await update.message.reply_text(
            f"✅ <b>New Force Join Channel Successfully English has been!</b>\n\n"
            f"🔹 <b>Button Name:</b> {ch_name}\n"
            f"🆔 <b>ID:</b> <code>{ch_id}</code>\n"
            f"🔗 <b>Link:</b> <code>{url}</code>\n\n"
            f"⚡ <i>UserEnglish now BotEnglish Enter English English This ChannelEnglish Join English will be।</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Force Join English Back", callback_data="adm_forcejoin")]])
        )

    # Channel Name Edit
    elif awaiting and awaiting.startswith("afj_edname_"):
        cid = awaiting.replace("afj_edname_", "")
        ctx.user_data["awaiting"] = None
        fb_update(f"force_join_channels/{cid}", {"name": text})
        await update.message.reply_text(
            f"✅ <b>Channel Button Name English Completed!</b>\n👉 <b>{text}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Force Join English Back", callback_data="adm_forcejoin")]])
        )

    # Channel ID Edit
    elif awaiting and awaiting.startswith("afj_edid_"):
        cid = awaiting.replace("afj_edid_", "")
        ctx.user_data["awaiting"] = None
        fb_update(f"force_join_channels/{cid}", {"id": text.strip()})
        await update.message.reply_text(
            f"✅ <b>Channel ID English Completed!</b>\n🆔 <code>{text.strip()}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Force Join English Back", callback_data="adm_forcejoin")]])
        )

    # Channel URL Edit
    elif awaiting and awaiting.startswith("afj_edurl_"):
        cid = awaiting.replace("afj_edurl_", "")
        ctx.user_data["awaiting"] = None
        url = text.strip()
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("tg://"):
            url = f"https://{url}"
        fb_update(f"force_join_channels/{cid}", {"url": url})
        await update.message.reply_text(
            f"✅ <b>Channel Link English Completed!</b>\n🔗 <code>{url}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Force Join English Back", callback_data="adm_forcejoin")]])
        )

    # ─── ADMIN ROLE ASSIGNMENT ───
    elif awaiting == "adm_addadmin_id":
        if text.isdigit():
            target_uid = int(text)
            ctx.user_data["awaiting"] = None
            u = get_user(target_uid)
            uname = u.get("name") or u.get("username") or f"User {target_uid}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛠️ Manager (Edit English English)", callback_data=f"adm_setrole_manager_{target_uid}")],
                [InlineKeyboardButton("👁️ View Only (English English)", callback_data=f"adm_setrole_viewer_{target_uid}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="adm_roles")]
            ])
            await update.message.reply_text(
                f"👤 <b>User English English:</b> {uname} (<code>{target_uid}</code>)\n\n"
                f"🔰 <b>This AdminEnglish English English English English English English:</b>\n"
                f"• <b>Manager:</b> Product, Category, Deposit Edit English English।\n"
                f"• <b>View Only:</b> English English English User English English English।",
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        else:
            await update.message.reply_text("❌ Please English English Telegram User ID Send।")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN SETTINGS CALLBACKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@admin_only
async def adm_settings_field(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("aset_","")

    if field == "toggle_deposit":
        s = get_settings()
        fb_update("settings", {"deposit_open": not s.get("deposit_open", False)})
        await adm_settings(update, ctx)
        return
    if field == "toggle_withdraw":
        s = get_settings()
        fb_update("settings", {"withdraw_open": not s.get("withdraw_open", True)})
        await adm_settings(update, ctx)
        return

    labels = {
        "bot_name":       "Bot Name",
        "welcome_text":   "Welcome Text",
        "currency_name":  "Currency Name (e.g. USD)",
        "currency_symbol":"Currency Symbol (e.g. $)",
        "local_currency": "Local Currency (e.g. USD)",
        "exchange_rate":  "Exchange Rate (number)",
        "min_deposit":    "Minimum Deposit (USD)",
        "min_withdraw":   "Minimum Withdraw (USD)",
        "referral_pct":   "Referral Commission %",
        "support_link":   "Support Link (URL)",
    }
    label = labels.get(field, field)
    ctx.user_data["awaiting"] = f"aset_{field}"
    await safe_edit_text(query, 
        f"✏️ {bold(sb('EDIT SETTING'))}\n{divider()}\n"
        f"🔧 {sb('Field:')} {label}\n"
        f"📝 {sb('Enter new value:')}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="adm_settings")]]))

# ─── ADMIN: PAYMENT EDIT / TOGGLE ───────────────────────────
@admin_only
async def adm_pay_edit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("apm_edit_","")
    ctx.user_data["awaiting"] = f"apm_edit_{key}"
    methods = get_payment_methods()
    pm = methods.get(key, {})
    await safe_edit_text(query, 
        f"✏️ {bold(sb('Edit Payment Method'))}\n{divider()}\n"
        f"📱 {sb('Method:')} {pm.get('name','?')}\n"
        f"📝 {sb('Enter new number/address:')}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="adm_payments")]]))

@admin_only
async def adm_pay_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("apm_toggle_","")
    methods = get_payment_methods()
    pm = methods.get(key, {})
    fb_update(f"payment_methods/{key}", {"enabled": not pm.get("enabled", True)})
    await adm_payments(update, ctx)

# ─── ADMIN: ADD CATEGORY / PRODUCT ──────────────────────────
@admin_only
async def adm_addcat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["awaiting"] = "adm_addcat_name"
    await safe_edit_text(query, 
        f"➕ {bold(sb('ADD CATEGORY'))}\n{divider()}\n"
        f"✏️ {sb('Enter category name:')}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="adm_products")]]))

@admin_only
async def adm_addprod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = query.data.replace("adm_addprod_","")
    ctx.user_data["adm_addprod_cat"] = cat_id
    ctx.user_data["adm_new_prod"] = {}
    ctx.user_data["awaiting"] = "adm_addprod_name"
    await safe_edit_text(query, 
        f"➕ {bold(sb('STEP 1/6: PRODUCT NAME'))}\n{divider()}\n"
        f"✏️ {sb('Enter product / bot name:')}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_cat_{cat_id}")]]))

@admin_only
async def adm_addstock(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.replace("adm_addstock_","")
    parts = data.split("_",1)
    cat_id, pid = parts[0], parts[1]
    ctx.user_data["awaiting"] = f"adm_addstock_{cat_id}_{pid}"
    await safe_edit_text(query, 
        f"📦 {bold(sb('ADD STOCK / UPDATE SCRIPT FILE'))}\n{divider()}\n"
        f"📤 <b>Option A:</b> Send a <code>.zip</code>, <code>.py</code>, <code>.js</code> file directly\n"
        f"📝 <b>Option B:</b> Enter text credentials (one per line)",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"adm_prod_{cat_id}_{pid}")]]))

@admin_only
async def adm_delprod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.replace("adm_delprod_","")
    parts = data.split("_",1)
    cat_id, pid = parts[0], parts[1]
    fb_delete(f"categories/{cat_id}/products/{pid}")
    await safe_edit_text(query, 
        f"🗑️ {sb('Product deleted.')}\n",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back", callback_data=f"adm_cat_{cat_id}")]]))

@admin_only
async def adm_delcat_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = fb_get("categories", {})
    buttons = [[InlineKeyboardButton(
        f"🗑️ {cat.get('name','?')}", callback_data=f"adm_delcat_{cat_id}")]
        for cat_id, cat in categories.items()]
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="adm_products")])
    await safe_edit_text(query, 
        f"🗑️ {bold(sb('DELETE CATEGORY'))}\n{divider()}\n"
        f"⚠️ {sb('Select category to delete (ALL products inside will be lost!):')}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons))

@admin_only
async def adm_delcat_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = query.data.replace("adm_delcat_","")
    fb_delete(f"categories/{cat_id}")
    await safe_edit_text(query, 
        f"🗑️ {sb('Category deleted.')}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back", callback_data="adm_products")]]))

@admin_only
async def adm_manage_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = fb_get("users", {})
    s = get_settings()
    sym = s.get("currency_symbol","$")
    text = (
        f"👥 {bold(sb('MANAGE USERS'))}\n"
        f"{divider()}\n"
        f"👤 {sb('Total:')} {len(users)}\n"
        f"🚫 {sb('Banned:')} {sum(1 for u in users.values() if u.get('banned'))}\n"
        f"{divider()}\n"
        f"💡 {sb('Use buttons below to manage:')}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 " + sb("Add Balance"),   callback_data="adm_addbal"),
         InlineKeyboardButton("⛔ " + sb("Ban/Unban"),     callback_data="adm_ban")],
        [InlineKeyboardButton("👑 Admin English English English", callback_data="adm_roles"),
         InlineKeyboardButton("📋 " + sb("List Users"),    callback_data="adm_listusers")],
        [InlineKeyboardButton("⬅️ " + sb("Back"),          callback_data="adm_panel")],
    ])
    await safe_edit_text(query, 
        text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def adm_list_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = fb_get("users", {})
    s = get_settings()
    sym = s.get("currency_symbol","$")
    text = f"👥 {bold(sb('USER LIST'))} (last 20)\n{divider()}\n"
    for uid_s, u in list(users.items())[-20:]:
        ban = "🚫" if u.get("banned") else "✅"
        bal = round(u.get("balance",0),2)
        text += f"{ban} {u.get('name','?')} (<code>{uid_s}</code>) — {sym}{bal}\n"
    text += divider()
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ " + sb("Back"), callback_data="adm_users")
    ]])
    await safe_edit_text(query, 
        text, parse_mode=ParseMode.HTML, reply_markup=kb)

@admin_only
async def adm_withdrawals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    withdrawals = fb_get("withdrawals", {})
    s = get_settings()
    sym = s.get("currency_symbol","$")
    pending = {k: v for k, v in withdrawals.items() if isinstance(v, dict) and v.get("status")=="pending"}
    text = (
        f"📤 {bold(sb('WITHDRAWALS'))}\n"
        f"{divider()}\n"
        f"⏳ {sb('Pending:')} {len(pending)}\n"
        f"✅ {sb('Total:')} {len(withdrawals)}\n"
        f"{divider()}"
    )
    buttons = []
    for wid, w in list(pending.items())[-10:]:
        uid_w = w.get("uid","?")
        amt   = w.get("amount","?")
        meth  = w.get("method","?")
        buttons.append([InlineKeyboardButton(
            f"👤{uid_w} | {sym}{amt} | {meth}",
            callback_data=f"awdraw_view_{wid}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ " + sb("Back"), callback_data="adm_panel")])
    await safe_edit_text(query, text, reply_markup=InlineKeyboardMarkup(buttons))

@admin_only
async def adm_withdraw_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    wid = query.data.replace("awdraw_view_", "")
    w = fb_get(f"withdrawals/{wid}", {})
    if not w:
        await query.answer("English English English English!", show_alert=True)
        return
    s = get_settings()
    sym = s.get("currency_symbol", "$")
    local = s.get("local_currency", "USD")
    rate = s.get("exchange_rate", 125)
    uid_w = w.get("uid", "?")
    try:
        amt_usd = float(w.get("amount", 0.0))
    except (ValueError, TypeError):
        amt_usd = 0.0
    local_amt = round(amt_usd * rate)
    status = w.get("status", "pending")

    text = (
        f"📤 {bold(sb('Withdrawal Details'))}\n"
        f"{divider()}\n"
        f"👤 {sb('User:')} {w.get('name', '?')} (<code>{uid_w}</code>)\n"
        f"💰 {sb('Amount:')} {sym}{amt_usd:.2f} (~{local_amt:,} {local})\n"
        f"📱 {sb('Method:')} {w.get('method', '?')}\n"
        f"🏦 {sb('Account/Number:')} <code>{w.get('account', '?')}</code>\n"
        f"📅 {sb('Time:')} {str(w.get('time', '?'))[:16]}\n"
        f"📊 {sb('Status:')} <b>{status.upper()}</b>\n"
        f"{divider()}"
    )
    buttons = []
    if status == "pending":
        buttons.append([
            InlineKeyboardButton("✅ Approve (Payment Completed)", callback_data=f"awdraw_ok_{wid}_{uid_w}_{amt_usd}"),
            InlineKeyboardButton("❌ Reject & Refund", callback_data=f"awdraw_no_{wid}_{uid_w}_{amt_usd}")
        ])
    buttons.append([InlineKeyboardButton("⬅️ " + sb("Back"), callback_data="adm_withdrawals")])
    await safe_edit_text(query, text, reply_markup=InlineKeyboardMarkup(buttons))

@admin_only
async def adm_withdraw_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rest = query.data.replace("awdraw_ok_", "")
    parts = rest.rsplit("_", 2)
    wid = parts[0]
    uid_w = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    amt = float(parts[2]) if len(parts) > 2 else 0.0
    
    fb_update(f"withdrawals/{wid}", {
        "status": "approved",
        "processed_at": datetime.now().isoformat()
    })
    
    s = get_settings()
    sym = s.get("currency_symbol", "$")
    
    try:
        await ctx.bot.send_message(
            chat_id=uid_w,
            text=(
                f"✅ <b>English Successfully Completed has been!</b>\n"
                f"{divider()}\n"
                f"💰 Your English English <b>{sym}{amt:.2f}</b> Approve English has been and Payment English English has been।\n"
                f"English English with English for! 💎"
            ),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.debug(f"User notify error on withdraw approve: {e}")
    
    await query.answer("✅ English Successfully Approve English has been!", show_alert=True)
    await adm_withdrawals(update, ctx)

@admin_only
async def adm_withdraw_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rest = query.data.replace("awdraw_ok_", "")
    parts = rest.rsplit("_", 2)
    wid = parts[0]
    uid_w = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    amt = float(parts[2]) if len(parts) > 2 else 0.0
    
    fb_update(f"withdrawals/{wid}", {
        "status": "rejected",
        "processed_at": datetime.now().isoformat()
    })
    
    # Refund user balance
    user = get_user(uid_w)
    old_bal = user.get("balance", 0.0)
    new_bal = round(old_bal + amt, 4)
    fb_update(f"users/{uid_w}", {"balance": new_bal})
    
    s = get_settings()
    sym = s.get("currency_symbol", "$")
    
    try:
        await ctx.bot.send_message(
            chat_id=uid_w,
            text=(
                f"❌ <b>English English Cancel English has been</b>\n"
                f"{divider()}\n"
                f"⚠️ Your English English (<b>{sym}{amt:.2f}</b>) Cancel English has been and English Your English BalanceEnglish English English has been।\n"
                f"💰 Current Balance: <b>{sym}{new_bal:.2f}</b>\n"
                f"Details InformationEnglish for SupportEnglish AddEnglishAdd।"
            ),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.debug(f"User notify error on withdraw reject: {e}")
    
    await query.answer("❌ English Cancel English Balance English English has been!", show_alert=True)
    await adm_withdrawals(update, ctx)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  USER WITHDRAWAL SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def user_withdraw_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    uid = update.effective_user.id
    user = get_user(uid)
    s = get_settings()
    
    if not s.get("withdraw_open", True):
        text = (
            f"🚫 {bold(sb('WITHDRAW SYSTEM CLOSED'))}\n"
            f"{divider()}\n"
            f"⚠️ {sb('Sorry, the withdrawal system is currently offline for maintenance.')}\n"
            f"💬 {sb('Please contact')} <a href='{s.get('support_link','https://t.me/bd_top_admin')}'>{sb('Support')}</a> {sb('for more details.')}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home")]])
        if query:
            await safe_edit_text(query, text, reply_markup=kb)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    sym = s.get("currency_symbol", "$")
    min_w = float(s.get("min_withdraw", 2.0))
    bal = float(user.get("balance", 0.0))

    if bal < min_w:
        text = (
            f"⚠️ {bold(sb('INSUFFICIENT BALANCE'))}\n"
            f"{divider()}\n"
            f"💰 {sb('Your Balance:')} <b>{format_amount(bal, s)}</b>\n"
            f"⬆️ {sb('Minimum Withdraw:')} <b>{format_amount(min_w, s)}</b>\n\n"
            f"💡 {sb('Earn more by referring friends or purchasing products!')}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 " + sb("Refer & Earn"), callback_data="refer")],
            [InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home")]
        ])
        if query:
            await safe_edit_text(query, text, reply_markup=kb)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # Choose method
    methods = get_payment_methods()
    buttons = []
    for m_key, m_val in methods.items():
        if m_val.get("enabled", True):
            buttons.append([InlineKeyboardButton(f"💳 {m_val.get('name', m_key.title())}", callback_data=f"uwdraw_meth_{m_key}")])
    
    buttons.append([InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home")])
    kb = InlineKeyboardMarkup(buttons)
    
    text = (
        f"📤 {bold(sb('WITHDRAW MONEY'))}\n"
        f"{divider()}\n"
        f"💰 {sb('Available Balance:')} <b>{format_amount(bal, s)}</b>\n"
        f"⬆️ {sb('Minimum Withdraw:')} <b>{format_amount(min_w, s)}</b>\n\n"
        f"👉 {sb('Select your withdrawal payment method below:')}"
    )
    if query:
        await safe_edit_text(query, text, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def user_withdraw_method_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m_key = query.data.replace("uwdraw_meth_", "")
    methods = get_payment_methods()
    m_info = methods.get(m_key, {})
    m_name = m_info.get("name", m_key.title())
    
    ctx.user_data["wdraw_method"] = m_name
    ctx.user_data["awaiting"] = "withdraw_amount"
    
    s = get_settings()
    sym = s.get("currency_symbol", "$")
    min_w = float(s.get("min_withdraw", 2.0))
    user = get_user(update.effective_user.id)
    bal = float(user.get("balance", 0.0))
    
    text = (
        f"📤 {bold(sb('Withdraw Via'))} <b>{m_name}</b>\n"
        f"{divider()}\n"
        f"💰 {sb('Your Balance:')} {sym}{bal:.2f}\n"
        f"⬆️ {sb('Minimum Withdraw:')} {sym}{min_w:.2f}\n\n"
        f"✏️ <b>{sb('Enter withdrawal amount in USD:')}</b> (e.g. <code>{min_w:.1f}</code>)"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ " + sb("Cancel"), callback_data="profile")]])
    await safe_edit_text(query, text, reply_markup=kb)

async def user_withdraw_handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    s = get_settings()
    sym = s.get("currency_symbol", "$")
    min_w = float(s.get("min_withdraw", 2.0))
    bal = float(user.get("balance", 0.0))
    txt = (update.message.text or "").strip()
    awaiting = ctx.user_data.get("awaiting")

    if awaiting == "withdraw_amount":
        try:
            amt = float(txt)
        except ValueError:
            await update.message.reply_text("⚠️ Please English English Enter (English: 2.0)")
            return
        if amt < min_w:
            await update.message.reply_text(f"⚠️ Minimum English Amount {sym}{min_w:.2f}")
            return
        if amt > bal:
            await update.message.reply_text(f"⚠️ English Balance! Your Balance {sym}{bal:.2f}")
            return
        ctx.user_data["wdraw_amount"] = amt
        ctx.user_data["awaiting"] = "withdraw_account"
        meth = ctx.user_data.get("wdraw_method", "Payment")
        await update.message.reply_text(
            f"📱 <b>{meth} English English Number Enter:</b>\n"
            f"(English NumberEnglish English English USD English English English English English Send)",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="profile")]])
        )
        return

    elif awaiting == "withdraw_account":
        account = txt
        amt = float(ctx.user_data.get("wdraw_amount", 0.0))
        meth = ctx.user_data.get("wdraw_method", "Payment")
        ctx.user_data["awaiting"] = None
        
        # Deduct balance immediately
        new_bal = round(bal - amt, 4)
        fb_update(f"users/{uid}", {"balance": new_bal})
        
        wid = f"-W{int(datetime.now().timestamp() * 1000)}"
        w_record = {
            "id": wid,
            "uid": uid,
            "name": update.effective_user.full_name,
            "amount": amt,
            "method": meth,
            "account": account,
            "status": "pending",
            "time": datetime.now().isoformat(),
        }
        fb_set(f"withdrawals/{wid}", w_record)
        
        rate = s.get("exchange_rate", 125)
        local = s.get("local_currency", "USD")
        local_amt = round(amt * rate)
        
        await update.message.reply_text(
            f"✅ <b>English English Successfully English has been!</b>\n"
            f"{divider()}\n"
            f"🆔 <b>English ID:</b> <code>{wid}</code>\n"
            f"💰 <b>Amount:</b> {sym}{amt:.2f} (~{local_amt:,} {local})\n"
            f"📱 <b>Method:</b> {meth}\n"
            f"🏦 <b>English:</b> <code>{account}</code>\n"
            f"⏳ <b>English:</b> English (Pending)\n"
            f"💵 <b>English Balance:</b> {sym}{new_bal:.2f}\n"
            f"{divider()}\n"
            f"⚡ <i>Admin Verify and English Your Payment English English।</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(uid)
        )
        
        for aid in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    chat_id=aid,
                    text=(
                        f"🚨 <b>New English English!</b>\n"
                        f"{divider()}\n"
                        f"👤 User: {html.escape(update.effective_user.full_name or 'Member')} (<code>{uid}</code>)\n"
                        f"💰 Amount: {sym}{amt:.2f} (~{local_amt:,} {local})\n"
                        f"📱 Method: {meth}\n"
                        f"🏦 English: <code>{account}</code>\n"
                        f"🆔 ID: <code>{wid}</code>"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔍 View Request", callback_data=f"awdraw_view_{wid}")]
                    ])
                )
            except Exception as e:
                logger.debug(f"Admin withdraw alert error: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VERIFY FORCE JOIN & ABOUT CALLBACKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def verify_force_join_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    not_joined = await check_force_join(ctx.bot, uid)
    if not_joined:
        await query.answer("⚠️ You nowEnglish All ChannelEnglish Join andEnglish! AllEnglish ChannelEnglish Join English and English Verify ButtonEnglish English।", show_alert=True)
        await send_force_join_screen(update, not_joined, is_edit=True)
        return
    
    await query.answer("✅ English Success has been! English।", show_alert=True)
    s = get_settings()
    bot_name = s.get("bot_name", "JAMES 💎")
    admin_banner = f"\n👑 {bold('Admin Access Enabled')} — Use /admin or button below\n" if is_admin(uid) else ""
    text = (
        f"🔥 {bold('Hello Hey!')}\n\n"
        f"🌟 𝙒𝙚𝙡𝙘𝙤𝙢𝙚 𝙩𝙤 {bold(bot_name)}\n"
        f"{admin_banner}"
        f"{divider()}\n"
        f"⚡ {sb('Instant Delivery')}\n"
        f"🛡️ {sb('Secure Purchase')}\n"
        f"💎 {sb('Premium Quality')}\n"
        f"✅ {sb('Trusted Service')}\n"
        f"{divider()}\n\n"
        f"👋 {sb('Welcome to the Shop Menu!')} Select an option below:"
    )
    try:
        await query.message.delete()
    except:
        pass
    await ctx.bot.send_message(
        chat_id=uid,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(uid)
    )

async def about_dev_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    dev_name = s.get("dev_name", "@bd_top_admin")
    dev_url = s.get("dev_url", "https://t.me/bd_top_admin")
    bot_name = s.get("bot_name", "JAMES 💎")
    
    text = (
        f"ℹ️ {bold(sb('DEVELOPER & PLATFORM INFO'))}\n"
        f"{divider()}\n"
        f"👑 {sb('Bot Platform:')} {bold(bot_name)}\n"
        f"💻 {sb('Developer / Owner:')} <b>{dev_name}</b>\n"
        f"🚀 {sb('System Version:')} <b>v3.5 Pro Cloud Realtime</b>\n"
        f"⚡ {sb('Feature:')} Instant Delivery & Auto Verification\n"
        f"🛡️ {sb('Security:')} RBAC Multi-Admin & Encrypted Storage\n"
        f"{divider()}\n"
        f"💡 {sb('For bot customization or inquiries, contact developer below:')}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact Developer", url=dev_url)],
        [InlineKeyboardButton("🏠 " + sb("Home"), callback_data="home")]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit_text(update.callback_query, text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN MESSAGE ROUTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    uid  = update.effective_user.id
    user = get_user(uid)
    if user and user.get("banned"):
        await update.message.reply_text("🚫 You are banned.")
        return

    # Check Force Join for non-admin users before processing text/buttons
    if not is_admin(uid):
        not_joined = await check_force_join(ctx.bot, uid)
        if not_joined:
            await send_force_join_screen(update, not_joined)
            return

    txt = update.message.text or update.message.caption or ""
    txt_clean = txt.strip().lower()

    if txt_clean in ["/cancel", "cancel", "Cancel", "❌ cancel", "❌ Cancel"]:
        ctx.user_data["awaiting"] = None
        await update.message.reply_text("❌ English Cancel English has been।", reply_markup=main_menu_keyboard(uid))
        return

    # Normalize slanted bold to ASCII for comparison
    def normalize(s):
        normal_map = dict(zip(
            "𝘼𝘽𝘾𝘿𝙀𝙁𝙂𝙃𝙄𝙅𝙆𝙇𝙈𝙉𝙊𝙋𝙌𝙍𝙎𝙏𝙐𝙑𝙒𝙓𝙔𝙕𝙖𝙗𝙘𝙙𝙚𝙛𝙜𝙝𝙞𝙟𝙠𝙡𝙢𝙣𝙤𝙥𝙦𝙧𝙨𝙩𝙪𝙫𝙬𝙭𝙮𝙯",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        ))
        return "".join(normal_map.get(c, c) for c in s).upper()

    ntxt = normalize(txt)

    # Check if this is a main menu button click; if so, clear any stuck awaiting state and navigate
    is_menu_btn = any(btn in ntxt for btn in [
        "BUY PRODUCT", "DEPOSIT MONEY", "WITHDRAW", "REFER", "MY PRODUCT",
        "MY PROFILE", "SUPPORT", "ABOUT", "CHECK DATA", "MY ID", "ADMIN PANEL"
    ]) or "English" in txt

    if is_menu_btn:
        ctx.user_data["awaiting"] = None

    # User deposit/general text and photo inputs MUST take priority so admins & users can deposit seamlessly
    if ctx.user_data.get("awaiting") in ["deposit_amount", "deposit_txid"]:
        await deposit_handle_text(update, ctx)
        return

    # User withdrawal text inputs MUST take priority so admins & users can withdraw seamlessly
    if ctx.user_data.get("awaiting") in ["withdraw_amount", "withdraw_account"]:
        await user_withdraw_handle_text(update, ctx)
        return

    # Admin text inputs take priority for administrative operations
    if is_admin(uid) and ctx.user_data.get("awaiting"):
        await admin_text_handler(update, ctx)
        return

    if "BUY PRODUCT" in ntxt or "Shop" in txt or "Product" in txt:
        await shop_menu(update, ctx)
    elif "DEPOSIT MONEY" in ntxt or "DEPOSIT" in ntxt or "Deposit" in txt or "USD English" in txt:
        await deposit_menu(update, ctx)
    elif "WITHDRAW" in ntxt or "English" in txt or "English" in txt:
        await user_withdraw_start(update, ctx)
    elif "REFER" in ntxt or "English" in txt:
        await refer_menu(update, ctx)
    elif "MY PRODUCT" in ntxt or "My Product" in txt or "My products" in txt:
        await my_products(update, ctx)
    elif "MY PROFILE" in ntxt or "PROFILE" in ntxt or "EnglishFile" in txt:
        await my_profile(update, ctx)
    elif "SUPPORT" in ntxt or "Support" in txt:
        await support_menu(update, ctx)
    elif "ABOUT" in ntxt or "About" in txt:
        await about_dev_callback(update, ctx)
    elif "CHECK DATA" in ntxt or "Check Data" in txt:
        await check_data(update, ctx)
    elif "MY ID" in ntxt or "ID" == ntxt or "My ID" in txt or "ID" in txt:
        await my_id_cmd(update, ctx)
    elif "ADMIN PANEL" in ntxt or "ADMIN" in ntxt or "/admin" in txt.lower() or "Admin" in txt:
        if is_admin(uid):
            await admin_panel(update, ctx)
        else:
            await admin_cmd(update, ctx)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALLBACK ROUTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    uid   = update.effective_user.id

    # Handle verification and about first
    if data == "verify_force_join":
        await verify_force_join_callback(update, ctx)
        return
    elif data in ["about_dev", "about"]:
        await about_dev_callback(update, ctx)
        return

    # Check Force Join for non-admins for regular callback queries
    if not is_admin(uid) and data not in ["home", "support", "about", "about_dev", "verify_force_join"]:
        not_joined = await check_force_join(ctx.bot, uid)
        if not_joined:
            await query.answer("⚠️ Please English ChannelEnglish Join English!", show_alert=True)
            await send_force_join_screen(update, not_joined, is_edit=True)
            return

    if data == "home":
        await home_callback(update, ctx)
    elif data == "shop":
        await shop_menu(update, ctx)
    elif data == "deposit":
        await deposit_menu(update, ctx)
    elif data == "refer":
        await refer_menu(update, ctx)
    elif data == "ref_copy_link":
        await ref_copy_link_callback(update, ctx)
    elif data == "support":
        await support_menu(update, ctx)
    elif data == "profile":
        await my_profile(update, ctx)
    elif data in ["my_products", "my_product"]:
        await my_products(update, ctx)
    elif data == "check_data":
        await check_data(update, ctx)
    elif data in ["my_id", "id"]:
        await my_id_cmd(update, ctx)
    elif data in ["about", "about_dev"]:
        await about_dev_callback(update, ctx)
    elif data == "user_withdraw":
        await user_withdraw_start(update, ctx)
    elif data.startswith("uwdraw_meth_"):
        await user_withdraw_method_chosen(update, ctx)

    # Shop
    elif data.startswith("cat_"):
        await show_category(update, ctx)
    elif data.startswith("prod_"):
        await show_product(update, ctx)
    elif data.startswith("guide_"):
        await guide_callback(update, ctx)
    elif data.startswith("buy_"):
        await confirm_buy(update, ctx)
    elif data.startswith("dl_"):
        await download_purchased_file(update, ctx)

    # Deposit gateway selection
    elif data.startswith("dep_"):
        await deposit_method_chosen(update, ctx)

    # Admin panel
    elif data == "adm_panel":
        await admin_panel(update, ctx)
    elif data == "adm_products":
        await adm_products(update, ctx)
    elif data.startswith("adm_cat_"):
        await adm_category_detail(update, ctx)
    elif data.startswith("adm_prod_"):
        await adm_prod_detail(update, ctx)
    elif data == "adm_settings":
        await adm_settings(update, ctx)
    elif data == "adm_payments":
        await adm_payments(update, ctx)
    elif data == "adm_deposits":
        await adm_deposits(update, ctx)
    elif data.startswith("adep_view_"):
        await adm_deposit_view(update, ctx)
    elif data.startswith("adep_ok_"):
        await adm_deposit_approve(update, ctx)
    elif data.startswith("adep_no_"):
        await adm_deposit_reject(update, ctx)
    elif data == "adm_broadcast":
        await adm_broadcast_start(update, ctx)
    elif data == "adm_stats":
        await adm_stats(update, ctx)
    elif data == "adm_fbstatus":
        await adm_fbstatus(update, ctx)
    elif data == "adm_fbreforce":
        await adm_fbreforce(update, ctx)
    elif data == "adm_addbal":
        await adm_addbal_start(update, ctx)
    elif data == "adm_ban":
        await adm_ban_start(update, ctx)
    elif data == "adm_users":
        await adm_manage_users(update, ctx)
    elif data == "adm_listusers":
        await adm_list_users(update, ctx)
    elif data == "adm_withdrawals":
        await adm_withdrawals(update, ctx)
    elif data.startswith("awdraw_view_"):
        await adm_withdraw_view(update, ctx)
    elif data.startswith("awdraw_ok_"):
        await adm_withdraw_approve(update, ctx)
    elif data.startswith("awdraw_no_"):
        await adm_withdraw_reject(update, ctx)
    elif data == "adm_addcat":
        await adm_addcat(update, ctx)
    elif data == "adm_delcat":
        await adm_delcat_prompt(update, ctx)
    elif data.startswith("adm_delcat_"):
        await adm_delcat_confirm(update, ctx)
    elif data.startswith("adm_addprod_"):
        await adm_addprod(update, ctx)
    elif data.startswith("adm_addstock_"):
        await adm_addstock(update, ctx)
    elif data.startswith("adm_delprod_"):
        await adm_delprod(update, ctx)
    elif data == "adm_checkdata":
        await adm_checkdata(update, ctx)
    elif data == "adm_btnmgr":
        await adm_btnmgr(update, ctx)
    elif data.startswith("adm_btntog_"):
        await adm_btntog_callback(update, ctx)
    elif data == "adm_resetbal_ask":
        await adm_resetbal_ask(update, ctx)
    elif data == "adm_resetbal_confirm":
        await adm_resetbal_confirm(update, ctx)
    elif data == "adm_dbbackup":
        await adm_dbbackup(update, ctx)
    elif data == "adm_addlink_start":
        await adm_addlink_start(update, ctx)
    elif data.startswith("adm_edlt_"):
        await adm_edlink_title_start(update, ctx)
    elif data.startswith("adm_edlu_"):
        await adm_edlink_url_start(update, ctx)
    elif data.startswith("adm_dellink_"):
        await adm_dellink_confirm(update, ctx)
    # Force Join Admin Callbacks
    elif data == "adm_forcejoin":
        await adm_forcejoin(update, ctx)
    elif data == "afj_toggle":
        await afj_toggle(update, ctx)
    elif data == "afj_add_start":
        await afj_add_start(update, ctx)
    elif data.startswith("afj_del_"):
        await afj_del_confirm(update, ctx)
    elif data.startswith("afj_edname_"):
        await afj_edname_start(update, ctx)
    elif data.startswith("afj_edid_"):
        await afj_edid_start(update, ctx)
    elif data.startswith("afj_edurl_"):
        await afj_edurl_start(update, ctx)
    # Admin Roles
    elif data == "adm_roles":
        await adm_roles(update, ctx)
    elif data == "adm_addadmin_start":
        await adm_addadmin_start(update, ctx)
    elif data.startswith("adm_setrole_"):
        await adm_setrole_callback(update, ctx)
    elif data.startswith("adm_chrole_"):
        await adm_chrole_callback(update, ctx)
    elif data.startswith("adm_deladmin_"):
        await adm_deladmin_callback(update, ctx)
    # Bengali Script Details & Editor Callbacks
    elif data.startswith("aedt_name_"):
        await aedt_start_name(update, ctx)
    elif data.startswith("aedt_price_"):
        await aedt_start_price(update, ctx)
    elif data.startswith("aedt_cat_"):
        await aedt_start_cat(update, ctx)
    elif data.startswith("aedt_moveto_"):
        await aedt_move_cat(update, ctx)
    elif data.startswith("aedt_demo_"):
        await aedt_start_demo(update, ctx)
    elif data.startswith("aedt_desc_"):
        await aedt_start_desc(update, ctx)
    elif data.startswith("aedt_guide_"):
        await aedt_start_guide(update, ctx)
    elif data.startswith("aedt_media_"):
        await aedt_start_media(update, ctx)
    elif data.startswith("aedt_entry_"):
        await aedt_start_entry(update, ctx)
    elif data.startswith("aedt_file_"):
        await aedt_start_file(update, ctx)
    elif data.startswith("aedt_testdl_"):
        await aedt_test_download(update, ctx)
    elif data.startswith("aedt_vis_"):
        await aedt_toggle_visibility(update, ctx)
    elif data.startswith("aset_"):
        await adm_settings_field(update, ctx)
    elif data.startswith("apm_edit_"):
        await adm_pay_edit(update, ctx)
    elif data.startswith("apm_toggle_"):
        await adm_pay_toggle(update, ctx)
    else:
        await query.answer("Unknown action.", show_alert=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /admin command
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        text = (
            f"🚫 {bold('Access Restricted — Admin Only')}\n"
            f"{divider()}\n"
            f"🆔 {sb('Your Telegram User ID:')} <code>{uid}</code>\n"
            f"👤 {sb('Name:')} {html.escape(update.effective_user.full_name or 'Member')}\n"
            f"🏷️ {sb('Username:')} @{update.effective_user.username or 'N/A'}\n"
            f"{divider()}\n"
            f"💡 {sb('To authorize this Telegram account:')}\n"
            f"1. Open your web app Config panel\n"
            f"2. Add <code>{uid}</code> to <b>Admin Telegram ID</b>\n"
            f"3. Click <b>Save & Restart</b>, then send <b>/admin</b> again!"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return
    await admin_panel(update, ctx)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  POST-INIT: REGISTER BOT COMMANDS & MENU BUTTON (Single /start)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def post_init(application: Application):
    global _global_bot
    _global_bot = application.bot
    # Only single /start command in menu drawer as requested
    commands = [
        BotCommand("start", "Open main menu"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("✅ Telegram Bot command /start successfully set in menu button!")
    except Exception as e:
        logger.warning(f"Could not set bot commands or menu button: {e}")

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, (telegram.error.NetworkError, telegram.error.TimedOut)):
        logger.warning(f"Telegram network transient event: {err}. Handled gracefully.")
        return
    if isinstance(err, telegram.error.Conflict):
        logger.warning(f"Telegram polling conflict: {err}. A previous session is releasing.")
        return
    logger.error(f"Exception while handling an update: {err}", exc_info=err)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN (24/7/365 AUTO-RECOVERY RESILIENT LOOP)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    init_defaults()
    print(f"🤖 Initializing Telegram Bot with Token: {BOT_TOKEN[:10]}...")
    retry_count = 0
    while True:
        try:
            app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

            app.add_error_handler(global_error_handler)
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("menu", start))
            app.add_handler(CommandHandler("help", start))
            app.add_handler(CommandHandler("admin", admin_cmd))
            app.add_handler(CommandHandler("id", my_id_cmd))
            app.add_handler(CommandHandler("myid", my_id_cmd))
            app.add_handler(CallbackQueryHandler(callback_router))
            app.add_handler(MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL) & ~filters.COMMAND, handle_message))

            logger.info("🚀 JAMES Bot is running in 24/7/365 Resilient Mode...")
            print("🚀 Bot started successfully and listening for updates (24/7 Resilient Mode)!")
            retry_count = 0
            app.run_polling(drop_pending_updates=True, close_loop=False)
            logger.warning("Bot polling loop finished. Auto-restarting in 2 seconds...")
            time.sleep(2)
        except Exception as e:
            err_name = type(e).__name__
            err_str = str(e)
            if "InvalidToken" in err_name or "Unauthorized" in err_str:
                print("\n" + "="*65)
                print("❌ TELEGRAM BOT TOKEN ERROR: 401 Unauthorized")
                print("="*65)
                print("⚠️ Your Telegram Bot Token- Telegram English English Reject has been।")
                print("English English English: English BotFather from English/English English has been or English।")
                print("\n👉 English (How to fix):")
                print("1. Telegram-English @BotFather-English English")
                print("2. /mybots English English -> API Token English New English View English /token with English English")
                print("3. New Bot Token English।")
                print("="*65 + "\n")
                logger.error("Invalid token. Retrying in 30 seconds...")
                time.sleep(30)
            elif "Conflict" in err_name or "terminated by other getUpdates request" in err_str:
                logger.warning("Telegram polling conflict detected. Waiting 4 seconds before reconnecting...")
                time.sleep(4)
            else:
                retry_count += 1
                wait_time = min(30, max(2, retry_count * 2))
                logger.error(f"Transient error in bot runtime ({err_name}: {err_str}). Auto-recovering in {wait_time}s...", exc_info=True)
                time.sleep(wait_time)

if __name__ == "__main__":
    main()
