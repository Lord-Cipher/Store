#!/usr/bin/env python3
"""Modern Telegram digital shop bot.

Highlights:
- English-first UI with consistent status controls.
- OxaPay invoices + HMAC-verified paid webhooks.
- Purchase history replaces the old deposit menu.
- Configuration-driven referral rewards, product catalog, and feature toggles.
- Role-aware admin panel with product CRUD, analytics, broadcast, and button manager.

Run with environment variables from .env (never commit secrets).
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import html
import io
import json
import logging
import os
import re
import secrets
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

try:
    from aiohttp import web
except ImportError:  # pragma: no cover
    web = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger("modern-shop")

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = Path(os.getenv("DATA_FILE", str(BASE_DIR / "bot_data.json")))
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OXAPAY_API_KEY = os.getenv("OXAPAY_MERCHANT_API_KEY", "").strip()
OXAPAY_API_URL = os.getenv("OXAPAY_API_URL", "https://api.oxapay.com/v1/payment/invoice").strip()
OXAPAY_STATUS_URL = os.getenv("OXAPAY_STATUS_URL", "https://api.oxapay.com/v1/payment").rstrip("/")
PAYMENT_POLL_SECONDS = max(30, int(os.getenv("PAYMENT_POLL_SECONDS", "45")))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
PUBLIC_WEBHOOK_URL = os.getenv("PUBLIC_WEBHOOK_URL", "").rstrip("/")
ADMIN_IDS = {int(x) for x in re.split(r"[,;\s]+", os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "")).strip()) if x.isdigit()}
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/your_support").strip()


def parse_force_join_channels(raw: str) -> list[dict[str, str]]:
    """Parse channel definitions as channel_id|title|join_url entries separated by semicolons."""
    channels = []
    for item in raw.split(";"):
        parts = [part.strip() for part in item.split("|", 2)]
        if len(parts) == 3 and all(parts):
            channels.append({"id": parts[0], "title": parts[1], "url": parts[2]})
    return channels


FORCE_JOIN_CHANNELS = parse_force_join_channels(os.getenv("FORCE_JOIN_CHANNELS", ""))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")
if not OXAPAY_API_KEY:
    log.warning("OXAPAY_MERCHANT_API_KEY is not set; payment buttons will explain setup is incomplete.")

DEFAULT_SETTINGS = {
    "shop_name": "Nova Store",
    "currency": "USD",
    "referral_rate": 5.0,
    "referrals_enabled": True,
    "purchases_enabled": True,
    "force_join_enabled": bool(FORCE_JOIN_CHANNELS),
    "force_join_channels": FORCE_JOIN_CHANNELS,
    "support_url": SUPPORT_URL,
    "main_buttons": {
        "shop": True, "history": True, "profile": True, "referrals": True,
        "support": True, "about": True,
    },
}

class Store:
    """Small atomic JSON store. It preserves existing data and is easy to migrate to Firebase later."""
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.data: dict[str, Any] = {}
        self.load()

    def load(self):
        with self.lock:
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            except (OSError, json.JSONDecodeError):
                log.exception("Could not load data; starting with an empty store")
                self.data = {}
            self.data.setdefault("settings", copy.deepcopy(DEFAULT_SETTINGS))
            self.data.setdefault("users", {})
            self.data.setdefault("products", {})
            self.data.setdefault("categories", {})
            self.data.setdefault("orders", {})
            self.data.setdefault("purchases", {})
            self.data.setdefault("admins", {str(uid): {"role": "owner"} for uid in ADMIN_IDS})
            self.save()

    def save(self):
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def user(self, uid: int, profile: Optional[dict] = None) -> dict:
        key = str(uid)
        with self.lock:
            user = self.data["users"].setdefault(key, {
                "id": uid, "balance": 0.0, "referrer_id": None, "referrals": 0,
                "referral_earnings": 0.0, "joined_at": iso_now(), "banned": False,
            })
            if profile:
                user.update({k: profile[k] for k in ("name", "username") if k in profile})
            self.save()
            return copy.deepcopy(user)

    def update_user(self, uid: int, updates: dict):
        with self.lock:
            self.data["users"].setdefault(str(uid), {"id": uid}).update(updates)
            self.save()

    def settings(self) -> dict:
        with self.lock:
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings.update(self.data.get("settings", {}))
            settings["main_buttons"] = {**DEFAULT_SETTINGS["main_buttons"], **settings.get("main_buttons", {})}
            return settings

    def update_settings(self, updates: dict):
        with self.lock:
            self.data["settings"].update(updates)
            self.save()

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(5)}"

    def add_order(self, order: dict) -> str:
        oid = order.get("id") or self.new_id("ord")
        order["id"] = oid
        with self.lock:
            self.data["orders"][oid] = order
            self.save()
        return oid

    def add_purchase(self, purchase: dict) -> str:
        pid = self.new_id("pur")
        purchase["id"] = pid
        with self.lock:
            self.data["purchases"][pid] = purchase
            self.save()
        return pid

store = Store(DATA_FILE)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def money(value: float) -> str:
    return f"{float(value):,.2f} {store.settings().get('currency', 'USD')}"


def status(enabled: bool) -> str:
    return "🟢 ON" if enabled else "🔴 OFF"


def stock_label(stock: Any) -> str:
    try:
        value = int(stock)
    except (TypeError, ValueError):
        value = 0
    if value < 0:
        return "🟢 Unlimited"
    if value == 0:
        return "🔴 Out of stock"
    return f"🟢 {value} available"


def referral_requirement(product: dict) -> int:
    try:
        return max(0, int(product.get("referrals_required", 0)))
    except (TypeError, ValueError):
        return 0


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS or str(uid) in store.data.get("admins", {})


def is_owner(uid: int) -> bool:
    return uid in ADMIN_IDS or store.data.get("admins", {}).get(str(uid), {}).get("role") == "owner"


def ensure_user(update: Update, start_param: Optional[str] = None) -> dict:
    user = update.effective_user
    existing = store.user(user.id, {"name": user.full_name, "username": user.username or ""})
    if start_param and start_param.startswith("ref_") and not existing.get("referrer_id"):
        try:
            referrer = int(start_param[4:])
            if referrer != user.id and str(referrer) in store.data["users"]:
                store.update_user(user.id, {"referrer_id": referrer})
                ref_user = store.user(referrer)
                store.update_user(referrer, {"referrals": int(ref_user.get("referrals", 0)) + 1})
                existing["referrer_id"] = referrer
        except ValueError:
            pass
    return store.user(user.id)


def force_join_settings() -> tuple[bool, list[dict[str, str]]]:
    settings = store.settings()
    channels = settings.get("force_join_channels", [])
    return bool(settings.get("force_join_enabled", False) and channels), channels


async def is_member_of_required_channels(bot, uid: int) -> tuple[bool, list[dict[str, str]]]:
    enabled, channels = force_join_settings()
    if not enabled or is_admin(uid):
        return True, []
    missing = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel["id"], uid)
            if member.status not in {"creator", "administrator", "member"} and not (member.status == "restricted" and member.is_member):
                missing.append(channel)
        except Exception as exc:
            log.warning("Force-join membership check failed for %s: %s", channel.get("id"), exc)
            missing.append(channel)
    return not missing, missing


async def force_join_screen(update: Update, ctx: ContextTypes.DEFAULT_TYPE, missing: list[dict[str, str]] | None = None):
    """Show the join gate with blue channel links and a green verification action."""
    _, configured = force_join_settings()
    channels = missing if missing is not None else configured
    rows = [[InlineKeyboardButton(f"🔵 Join {channel['title']}", url=channel["url"])] for channel in channels]
    rows.append([button("🟢 Verify membership", "verify_join")])
    rows.append([button("🔵 Support", "support")])
    text = ("🔐 <b>Join our community first</b>\n\n"
            "Please join all required channels below, then press the green verification button to continue.")
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


async def require_membership(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    ok, missing = await is_member_of_required_channels(ctx.bot, update.effective_user.id)
    if ok:
        return True
    await force_join_screen(update, ctx, missing)
    return False


def button(text: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=callback)


def home_keyboard(uid: int) -> InlineKeyboardMarkup:
    s = store.settings(); b = s["main_buttons"]
    rows = []
    if b.get("shop", True): rows.append([button("🔵 Browse shop", "shop")])
    row = []
    if b.get("history", True): row.append(button("🔵 Purchase history", "history"))
    if b.get("profile", True): row.append(button("🔵 My profile", "profile"))
    if row: rows.append(row)
    row = []
    if b.get("referrals", True) and s.get("referrals_enabled", True): row.append(button("🟢 Refer & earn", "referrals"))
    if b.get("support", True): row.append(button("🔵 Support", "support"))
    if row: rows.append(row)
    if b.get("about", True): rows.append([button("🔵 About", "about")])
    if is_admin(uid): rows.append([button("🔴 Admin control center", "admin")])
    return InlineKeyboardMarkup(rows)


def reply_keyboard(uid: int) -> ReplyKeyboardMarkup:
    rows = [["🛒 Browse shop", "📚 Purchase history"], ["👤 My profile", "🎁 Refer & earn"], ["🆘 Support", "ℹ️ About"]]
    if is_admin(uid): rows.append(["⚙️ Admin panel"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def home_text() -> str:
    s = store.settings()
    return (f"✨ <b>{esc(s['shop_name'])}</b>\n\n"
            "Premium digital products with secure crypto checkout and instant delivery.\n\n"
            "🛡️ Secure OxaPay payments\n⚡ Automated delivery\n📚 Permanent purchase history")


def nav() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button("🏠 Home", "home")]])

async def show(target, text: str, markup: InlineKeyboardMarkup | None = None):
    if getattr(target, "callback_query", None):
        q = target.callback_query
        await q.answer()
        try:
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup, disable_web_page_preview=True)
    else:
        await target.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup, disable_web_page_preview=True)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    param = ctx.args[0] if ctx.args else None
    user = ensure_user(update, param)
    if user.get("banned"):
        await update.message.reply_text("🚫 Your account is currently disabled.")
        return
    if not await require_membership(update, ctx):
        return
    await update.message.reply_text(home_text(), parse_mode=ParseMode.HTML, reply_markup=reply_keyboard(update.effective_user.id))
    await update.message.reply_text("Choose an option to continue:", reply_markup=home_keyboard(update.effective_user.id))

async def home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    if not await require_membership(update, ctx):
        return
    await show(update, home_text(), home_keyboard(update.effective_user.id))


async def verify_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ok, missing = await is_member_of_required_channels(ctx.bot, update.effective_user.id)
    if not ok:
        await force_join_screen(update, ctx, missing)
        return
    await update.callback_query.answer("Verified successfully!")
    await update.callback_query.edit_message_text(
        home_text(), parse_mode=ParseMode.HTML,
        reply_markup=home_keyboard(update.effective_user.id),
        disable_web_page_preview=True,
    )

async def shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not store.settings().get("purchases_enabled", True):
        await show(update, "🔴 <b>Shop is temporarily offline</b>\nPlease check back soon.", nav()); return
    products = store.data.get("products", {})
    active = [(pid, p) for pid, p in products.items() if p.get("active", True)]
    if not active:
        await show(update, "🛒 <b>Shop</b>\n\nNo products are available yet.", nav()); return
    category_map = store.data.get("categories", {})
    grouped = {}
    for pid, p in active:
        grouped.setdefault(p.get("category_id") or "general", []).append((pid, p))
    use_categories = len(grouped) > 1 or bool(category_map)
    if use_categories:
        rows = []
        for cid, items in grouped.items():
            name = category_map.get(cid, {}).get("name", "General")
            rows.append([button(f"🔵 {name} ({len(items)})", f"category:{cid}")])
    else:
        rows = [[button(f"🔵 {p.get('name','Product')} · {money(p.get('price', 0))} · {stock_label(p.get('stock', 0))}", f"product:{pid}")] for pid, p in active]
    rows.append([button("🏠 Home", "home")])
    prompt = "Select a category:" if use_categories else "Select a product:"
    await show(update, f"🛒 <b>Browse shop</b>\n\n{prompt}", InlineKeyboardMarkup(rows))


async def category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.callback_query.data.split(":", 1)[1]
    category_map = store.data.get("categories", {})
    products = [(pid, p) for pid, p in store.data.get("products", {}).items()
                if p.get("active", True) and (p.get("category_id") or "general") == cid]
    name = category_map.get(cid, {}).get("name", "General")
    if not products:
        await show(update, f"📂 <b>{esc(name)}</b>\n\nNo products are available in this category.", InlineKeyboardMarkup([[button("⬅️ Back to shop", "shop")]])); return
    rows = [[button(f"🔵 {p.get('name','Product')} · {money(p.get('price', 0))} · {stock_label(p.get('stock', 0))}", f"product:{pid}")] for pid, p in products]
    rows.append([button("⬅️ Back to shop", "shop")])
    await show(update, f"📂 <b>{esc(name)}</b>\n\nSelect a product:", InlineKeyboardMarkup(rows))

async def product(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split(":", 1)[1]
    p = store.data.get("products", {}).get(pid)
    if not p or not p.get("active", True):
        await show(update, "❌ Product unavailable.", nav()); return
    stock = p.get("stock", 0)
    required_referrals = referral_requirement(p)
    stock_text = stock_label(stock)
    text = (f"📦 <b>{esc(p.get('name'))}</b>\n\n{esc(p.get('description', ''))}\n\n"
            f"💳 Price: <b>{money(p.get('price', 0))}</b>\n📊 Stock: {stock_text}")
    if required_referrals:
        text += f"\n🎁 Referral unlock: <b>{required_referrals} referrals required</b>"
    rows = []
    if (stock == -1 or stock > 0) and (not required_referrals or store.user(update.effective_user.id).get("referrals", 0) >= required_referrals):
        rows.append([button("🟢 Buy now", f"buy:{pid}")])
    elif required_referrals and store.user(update.effective_user.id).get("referrals", 0) < required_referrals:
        rows.append([button(f"🔴 Unlock with {required_referrals} referrals", "referrals")])
    elif stock == 0:
        rows.append([button("🔴 Out of stock", "shop")])
    rows.append([button("⬅️ Back to shop", "shop")])
    await show(update, text, InlineKeyboardMarkup(rows))

async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    items = [p for p in store.data.get("purchases", {}).values() if p.get("uid") == uid]
    orders = [o for o in store.data.get("orders", {}).values() if o.get("uid") == uid and o.get("status") == "pending"]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    if not items and not orders:
        await show(update, "📚 <b>Purchase history</b>\n\nYou have not purchased anything yet.", InlineKeyboardMarkup([[button("🛒 Browse shop", "shop")], [button("🏠 Home", "home")]])); return
    lines = ["📚 <b>Purchase history</b>", ""]
    rows = []
    for order in orders[:10]:
        lines.append(f"⏳ Pending · {money(order.get('amount', 0))} · {esc(order.get('id'))}")
        rows.append([button("🔵 Check payment status", f"order:{order.get('id')}")])
    for p in items[:20]:
        lines.append(f"• {esc(p.get('product_name'))} — {money(p.get('price', 0))} — {esc(p.get('status', 'paid'))}")
        rows.append([button(f"🟢 Re-download {p.get('product_name')}", f"download:{p.get('id')}")])
    rows.append([button("🏠 Home", "home")])
    await show(update, "\n".join(lines), InlineKeyboardMarkup(rows))


async def order_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    oid = update.callback_query.data.split(":", 1)[1]
    order = store.data.get("orders", {}).get(oid)
    if not order or int(order.get("uid", 0)) != update.effective_user.id:
        await update.callback_query.answer("Order not found.", show_alert=True); return
    if order.get("status") == "pending" and order.get("track_id"):
        try:
            payment = await asyncio.to_thread(get_oxapay_payment_status, str(order["track_id"]))
            remote_status = str(payment.get("status", "pending")).lower()
            if remote_status in {"paid", "completed"}:
                await fulfill_order(order, ctx.bot)
            elif remote_status in {"expired", "failed", "cancelled", "canceled"}:
                order["status"] = remote_status; store.data["orders"][oid] = order; store.save()
        except Exception as exc:
            log.warning("Manual order status check failed: %s", exc)
    current = store.data.get("orders", {}).get(oid, {}).get("status", "pending")
    await show(update, f"🧾 <b>Order status</b>\n\nOrder: <code>{esc(oid)}</code>\nStatus: <b>{esc(current.title())}</b>", InlineKeyboardMarkup([[button("📚 Purchase history", "history")], [button("🏠 Home", "home")]]))


async def download_purchase(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    purchase_id = update.callback_query.data.split(":", 1)[1]
    purchase = store.data.get("purchases", {}).get(purchase_id)
    if not purchase or int(purchase.get("uid", 0)) != update.effective_user.id:
        await update.callback_query.answer("Purchase not found.", show_alert=True); return
    delivery = purchase.get("delivery", "")
    await update.callback_query.answer("Preparing your delivery...")
    if delivery.startswith("file:"):
        await ctx.bot.send_document(update.effective_user.id, delivery[5:].strip(), caption=f"📦 {purchase.get('product_name')} — re-download")
    elif delivery:
        await ctx.bot.send_message(update.effective_user.id, f"📦 <b>{esc(purchase.get('product_name'))}</b>\n\n<code>{esc(delivery)}</code>", parse_mode=ParseMode.HTML)
    else:
        await ctx.bot.send_message(update.effective_user.id, "⚠️ This purchase has no delivery content. Please contact support.")

async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = store.user(update.effective_user.id)
    text = (f"👤 <b>My profile</b>\n\n🆔 ID: <code>{u['id']}</code>\n"
            f"💰 Balance: <b>{money(u.get('balance', 0))}</b>\n👥 Referrals: {u.get('referrals', 0)}\n"
            f"🎁 Referral earnings: {money(u.get('referral_earnings', 0))}")
    await show(update, text, nav())

async def referrals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; u = store.user(uid); s = store.settings()
    me = await ctx.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{uid}"
    text = (f"🎁 <b>Refer & earn</b>\n\nInvite friends with your personal link. You earn <b>{s.get('referral_rate', 5)}%</b> from each referred user's completed purchase.\n\n"
            f"👥 Referrals: {u.get('referrals', 0)}\n💰 Earned: {money(u.get('referral_earnings', 0))}\n\n<code>{esc(link)}</code>")
    await show(update, text, InlineKeyboardMarkup([[button("📋 Copy link", "ref_copy")], [button("🏠 Home", "home")]]))

async def ref_copy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; me = await ctx.bot.get_me()
    await update.callback_query.answer(f"Your referral link: https://t.me/{me.username}?start=ref_{uid}", show_alert=True)

async def support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show(update, "🆘 <b>Support</b>\n\nNeed help? Contact our support team.", InlineKeyboardMarkup([[InlineKeyboardButton("Open support", url=store.settings().get("support_url", SUPPORT_URL))], [button("🏠 Home", "home")]]))

async def about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show(update, f"ℹ️ <b>About {esc(store.settings()['shop_name'])}</b>\n\nA modern automated digital store powered by OxaPay.", nav())

async def create_invoice(update: Update, ctx: ContextTypes.DEFAULT_TYPE, pid: str):
    if not OXAPAY_API_KEY:
        await show(update, "⚠️ Payments are not configured yet. Ask an administrator to set OXAPAY_MERCHANT_API_KEY.", nav()); return
    p = store.data["products"].get(pid); uid = update.effective_user.id
    order_id = store.new_id("ord")
    payload = {"amount": float(p["price"]), "currency": store.settings().get("currency", "USD"), "lifetime": 60,
               "callback_url": f"{PUBLIC_WEBHOOK_URL}/oxapay/webhook" if PUBLIC_WEBHOOK_URL else "",
               "order_id": order_id, "description": f"{p.get('name')} for Telegram user {uid}", "thanks_message": "Payment received. Your product will be delivered automatically."}
    payload = {k: v for k, v in payload.items() if v}
    req = urllib.request.Request(OXAPAY_API_URL, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json", "merchant_api_key": OXAPAY_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode())
        data = result.get("data", {})
        if not data.get("payment_url"):
            raise RuntimeError(result.get("message", "OxaPay did not return a payment URL"))
        store.add_order({"id": order_id, "uid": uid, "pid": pid, "amount": float(p["price"]), "status": "pending", "track_id": data.get("track_id"), "created_at": iso_now()})
        payment_note = "Automatic confirmation is active; you do not need to send a screenshot or transaction ID."
        await show(update, f"💳 <b>Secure checkout</b>\n\nProduct: {esc(p.get('name'))}\nAmount: <b>{money(p.get('price', 0))}</b>\n\nPay using the secure OxaPay page. {payment_note}", InlineKeyboardMarkup([[InlineKeyboardButton("🟢 Pay with OxaPay", url=data["payment_url"])], [button("📚 Purchase history", "history")], [button("🏠 Home", "home")]]))
    except Exception as exc:
        log.exception("OxaPay invoice error")
        await show(update, f"❌ Could not create checkout right now.\n\n<code>{esc(str(exc)[:180])}</code>", nav())

async def buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split(":", 1)[1]
    p = store.data.get("products", {}).get(pid)
    if not p: await show(update, "❌ Product unavailable.", nav()); return
    if p.get("stock", 0) == 0: await show(update, "❌ This product is out of stock.", nav()); return
    required_referrals = referral_requirement(p)
    user = store.user(update.effective_user.id)
    if required_referrals and int(user.get("referrals", 0)) < required_referrals:
        await show(update, f"🔒 <b>Referral unlock required</b>\n\nYou need {required_referrals} referrals to unlock this file. Your current total is {user.get('referrals', 0)}.", InlineKeyboardMarkup([[button("🟢 Refer & earn", "referrals")], [button("🏠 Home", "home")]])); return
    await create_invoice(update, ctx, pid)

async def fulfill_order(order: dict, bot):
    if order.get("status") == "paid": return
    p = store.data.get("products", {}).get(order.get("pid")); uid = int(order["uid"])
    if not p: return
    if int(p.get("stock", -1)) == 0:
        order["status"] = "paid_out_of_stock"; order["paid_at"] = iso_now(); store.data["orders"][order["id"]] = order; store.save()
        try:
            await bot.send_message(uid, "⚠️ Your payment was confirmed, but this product sold out before delivery. Please contact support for a replacement or refund.")
        except Exception:
            pass
        return
    order["status"] = "paid"; order["paid_at"] = iso_now(); store.data["orders"][order["id"]] = order
    if p.get("stock", -1) > 0: p["stock"] -= 1
    store.data["products"][order["pid"]] = p
    purchase = {"uid": uid, "product_name": p.get("name"), "price": float(p.get("price", 0)), "status": "paid", "created_at": iso_now(), "delivery": p.get("delivery", "")}
    store.add_purchase(purchase); store.save()
    s = store.settings(); u = store.user(uid)
    ref = u.get("referrer_id")
    if s.get("referrals_enabled", True) and ref:
        reward = round(float(p.get("price", 0)) * float(s.get("referral_rate", 5)) / 100, 2)
        ru = store.user(int(ref)); store.update_user(int(ref), {"balance": round(float(ru.get("balance", 0)) + reward, 2), "referral_earnings": round(float(ru.get("referral_earnings", 0)) + reward, 2)})
        try: await bot.send_message(int(ref), f"🎁 Referral reward: <b>{money(reward)}</b> was added to your balance.", parse_mode=ParseMode.HTML)
        except Exception: pass
    delivery = p.get("delivery", "")
    try:
        await bot.send_message(uid, f"✅ <b>Payment confirmed</b>\n\nYour purchase <b>{esc(p.get('name'))}</b> is ready.", parse_mode=ParseMode.HTML, reply_markup=nav())
        if delivery.startswith("file:"):
            await bot.send_document(uid, delivery[5:].strip(), caption=f"📦 {p.get('name')} — instant delivery")
        elif delivery:
            await bot.send_message(uid, f"📦 <b>Your delivery</b>\n\n<code>{esc(delivery)}</code>", parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("Delivery failed for %s", uid)

async def oxapay_webhook(request):
    raw = await request.read()
    signature = request.headers.get("HMAC", "")
    expected = hmac.new(OXAPAY_API_KEY.encode(), raw, hashlib.sha512).hexdigest()
    if not OXAPAY_API_KEY or not hmac.compare_digest(signature, expected):
        return web.Response(status=400, text="invalid signature")
    try: payload = json.loads(raw.decode())
    except json.JSONDecodeError: return web.Response(status=400, text="invalid json")
    if str(payload.get("type", "")).lower() != "invoice": return web.Response(status=400, text="invalid type")
    oid = payload.get("order_id"); order = store.data.get("orders", {}).get(oid)
    if order and str(payload.get("status", "")).lower() == "paid":
        await fulfill_order(order, request.app["telegram_bot"])
    return web.Response(status=200, text="ok")


def get_oxapay_payment_status(track_id: str) -> dict:
    """Query OxaPay's official payment-information endpoint for webhook-free hosting."""
    url = f"{OXAPAY_STATUS_URL}/{track_id}"
    req = urllib.request.Request(url, method="GET", headers={
        "Content-Type": "application/json",
        "merchant_api_key": OXAPAY_API_KEY,
    })
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode())
    return payload.get("data", {}) or {}


async def poll_pending_payments(context: ContextTypes.DEFAULT_TYPE):
    """Fallback payment automation for bot hosts that cannot receive HTTPS callbacks."""
    pending = [order for order in store.data.get("orders", {}).values()
               if order.get("status") == "pending" and order.get("track_id")]
    for order in pending[:50]:
        try:
            payment = await asyncio.to_thread(get_oxapay_payment_status, str(order["track_id"]))
            status_value = str(payment.get("status", "")).lower()
            if status_value in {"paid", "completed"}:
                log.info("Polling confirmed OxaPay order %s", order.get("id"))
                await fulfill_order(order, context.bot)
            elif status_value in {"expired", "failed", "canceled", "cancelled"}:
                order["status"] = status_value
                store.data["orders"][order["id"]] = order
                store.save()
        except Exception as exc:
            log.warning("OxaPay status check failed for order %s: %s", order.get("id"), exc)

# ---------------- Admin ----------------
def admin_only(fn):
    @wraps(fn)
    async def wrapped(update, ctx):
        if not is_admin(update.effective_user.id):
            if update.callback_query: await update.callback_query.answer("Admin access required", show_alert=True)
            else: await update.message.reply_text("🚫 Admin access required.")
            return
        return await fn(update, ctx)
    return wrapped

@admin_only
async def admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = store.settings(); users = len(store.data.get("users", {})); orders = list(store.data.get("orders", {}).values())
    pending = sum(1 for o in orders if o.get("status") == "pending")
    text = (f"🔴 <b>Admin control center</b>\n\n👥 Users: {users}\n🧾 Orders: {len(orders)}\n⏳ Pending payments: {pending}\n\n"
            f"Purchases: {status(s.get('purchases_enabled', True))} · Referrals: {status(s.get('referrals_enabled', True))}")
    kb = InlineKeyboardMarkup([[button("📦 Products", "adm:products"), button("📊 Analytics", "adm:stats")], [button("👥 User search", "adm:user_search"), button("🎛️ Button manager", "adm:buttons")], [button("⚙️ Settings", "adm:settings"), button("📢 Broadcast", "adm:broadcast")], [button("💾 Backup", "adm:backup"), button("♻️ Restore", "adm:restore")], [button("🏠 User home", "home")]])
    await show(update, text, kb)


@admin_only
async def admin_user_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["admin_state"] = "user_search"
    await show(update, "👥 <b>User search</b>\n\nSend a Telegram user ID or username.", InlineKeyboardMarkup([[button("Cancel", "admin")]]))


@admin_only
async def admin_user_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE, uid: int):
    user = store.data.get("users", {}).get(str(uid))
    if not user:
        await update.message.reply_text("No matching user found."); return
    purchases = [p for p in store.data.get("purchases", {}).values() if int(p.get("uid", 0)) == uid]
    await update.message.reply_text(
        f"👤 <b>User profile</b>\n\nID: <code>{uid}</code>\nName: {esc(user.get('name','Unknown'))}\nUsername: @{esc(user.get('username',''))}\nBalance: <b>{money(user.get('balance', 0))}</b>\nReferrals: {user.get('referrals', 0)}\nPurchases: {len(purchases)}",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[button("⬅️ Admin center", "admin")]]))


@admin_only
async def admin_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    payload = json.dumps(store.data, ensure_ascii=False, indent=2).encode("utf-8")
    await update.callback_query.answer("Preparing backup...")
    await ctx.bot.send_document(update.effective_user.id, io.BytesIO(payload), filename=f"bot-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json", caption="💾 Database backup")


@admin_only
async def admin_restore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["admin_state"] = "restore"
    await show(update, "♻️ <b>Restore database</b>\n\nSend a JSON backup file exported by this bot. The current database will be replaced after validation.", InlineKeyboardMarkup([[button("Cancel", "admin")]]))


@admin_only
async def admin_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("admin_state") != "restore":
        return
    document = update.message.document
    file = await document.get_file()
    raw = bytes(await file.download_as_bytearray())
    try:
        restored = json.loads(raw.decode("utf-8"))
        required = {"settings", "users", "products", "orders", "purchases"}
        if not isinstance(restored, dict) or not required.issubset(restored):
            raise ValueError("missing required database sections")
        store.data = restored
        store.data.setdefault("categories", {})
        store.save(); ctx.user_data.pop("admin_state", None)
        await update.message.reply_text("✅ Database restored successfully.", reply_markup=reply_keyboard(update.effective_user.id))
    except Exception as exc:
        await update.message.reply_text(f"❌ Restore rejected: {esc(str(exc))}", parse_mode=ParseMode.HTML)

@admin_only
async def admin_products(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    products = store.data.get("products", {}); rows = []
    for pid, p in products.items(): rows.append([button(f"{'🟢' if p.get('active', True) else '🔴'} {p.get('name')} · {money(p.get('price', 0))}", f"adm:product:{pid}")])
    rows.append([button("🟢 Add product", "adm:add")])
    rows.append([button("⬅️ Admin center", "admin")])
    await show(update, "📦 <b>Product management</b>\n\nTap a product to edit, delete, or toggle availability.", InlineKeyboardMarkup(rows))


@admin_only
async def admin_product_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split(":", 2)[2]
    p = store.data.get("products", {}).get(pid)
    if not p:
        await show(update, "❌ Product not found.", InlineKeyboardMarkup([[button("⬅️ Products", "adm:products")]])); return
    category_name = store.data.get("categories", {}).get(p.get("category_id", ""), {}).get("name", "General")
    text = (f"📦 <b>{esc(p.get('name'))}</b>\n\nPrice: <b>{money(p.get('price', 0))}</b>\n"
            f"Stock: <b>{stock_label(p.get('stock', 0))}</b>\nCategory: <b>{esc(category_name)}</b>\n"
            f"Referral unlock: <b>{referral_requirement(p)} referrals</b>\n"
            f"Availability: {status(p.get('active', True))}")
    kb = InlineKeyboardMarkup([
        [button("🟢 Edit product", f"adm:edit:{pid}"), button("🔴 Delete", f"adm:delete:{pid}")],
        [button(f"{status(p.get('active', True))} Toggle availability", f"adm:toggle:{pid}")],
        [button("⬅️ Products", "adm:products")],
    ])
    await show(update, text, kb)

@admin_only
async def admin_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["admin_state"] = "add_product"
    await show(update, "🟢 <b>Add product</b>\n\nSend one line in this format:\n<code>Name | price | stock | description | delivery | category | referrals_required</code>\n\nUse stock <code>-1</code> for unlimited stock. Delivery can be text or <code>file:TELEGRAM_FILE_ID</code>. Set referrals_required to 0 for no unlock requirement.", InlineKeyboardMarkup([[button("Cancel", "adm:products")]]))


@admin_only
async def admin_edit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split(":", 2)[2]
    p = store.data.get("products", {}).get(pid)
    if not p:
        await show(update, "❌ Product not found.", InlineKeyboardMarkup([[button("⬅️ Products", "adm:products")]])); return
    ctx.user_data["admin_state"] = f"edit_product:{pid}"
    current = f"{p.get('name','')} | {p.get('price',0)} | {p.get('stock',0)} | {p.get('description','')} | {p.get('delivery','')} | {p.get('category_id','')} | {p.get('referrals_required',0)}"
    await show(update, f"🟢 <b>Edit product</b>\n\nSend the updated line:\n<code>{esc(current)}</code>\n\nUse: Name | price | stock | description | delivery | category | referrals_required", InlineKeyboardMarkup([[button("Cancel", f"adm:product:{pid}")]]))


@admin_only
async def admin_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split(":", 2)[2]
    p = store.data.get("products", {}).get(pid, {})
    await show(update, f"⚠️ <b>Delete {esc(p.get('name', 'this product'))}?</b>\n\nThis removes it from the shop. Existing purchase history is preserved.", InlineKeyboardMarkup([[button("🔴 Confirm delete", f"adm:delete_confirm:{pid}")], [button("⬅️ Cancel", f"adm:product:{pid}")]]))


@admin_only
async def admin_delete_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split(":", 2)[2]
    store.data.get("products", {}).pop(pid, None); store.save()
    await admin_products(update, ctx)

@admin_only
async def admin_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split(":", 2)[2]
    if pid in store.data["products"]:
        p = store.data["products"][pid]; p["active"] = not p.get("active", True); store.save()
    await admin_products(update, ctx)

@admin_only
async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    orders = list(store.data.get("orders", {}).values()); paid = [o for o in orders if o.get("status") == "paid"]
    revenue = sum(float(o.get("amount", 0)) for o in paid)
    await show(update, f"📊 <b>Analytics</b>\n\n👥 Users: {len(store.data.get('users', {}))}\n📦 Products: {len(store.data.get('products', {}))}\n✅ Paid orders: {len(paid)}\n💰 Revenue: <b>{money(revenue)}</b>", InlineKeyboardMarkup([[button("⬅️ Admin center", "admin")]]))

@admin_only
async def admin_buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    b = store.settings()["main_buttons"]; rows = []
    labels = {"shop": "Browse shop", "history": "Purchase history", "profile": "My profile", "referrals": "Refer & earn", "support": "Support", "about": "About"}
    for key, label in labels.items(): rows.append([button(f"{status(b.get(key, True))} {label}", f"adm:button:{key}")])
    rows.append([button("⬅️ Admin center", "admin")])
    await show(update, "🎛️ <b>Button manager</b>\n\nGreen means visible. Red means hidden.", InlineKeyboardMarkup(rows))

@admin_only
async def admin_button_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    key = update.callback_query.data.split(":", 2)[2]; b = store.settings()["main_buttons"]; b[key] = not b.get(key, True); store.update_settings({"main_buttons": b}); await admin_buttons(update, ctx)

@admin_only
async def admin_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = store.settings()
    force_enabled = bool(s.get("force_join_enabled", False) and s.get("force_join_channels"))
    text = (f"⚙️ <b>Settings</b>\n\nPurchases: {status(s.get('purchases_enabled', True))}\n"
            f"Referrals: {status(s.get('referrals_enabled', True))}\n"
            f"Force join: {status(force_enabled)}\n"
            f"Required channels: <b>{len(s.get('force_join_channels', []))}</b>\n"
            f"Referral reward: <b>{s.get('referral_rate', 5)}%</b>")
    kb = InlineKeyboardMarkup([
        [button(f"{status(s.get('purchases_enabled', True))} Purchases", "adm:setting:purchases_enabled")],
        [button(f"{status(s.get('referrals_enabled', True))} Referrals", "adm:setting:referrals_enabled")],
        [button(f"{status(force_enabled)} Force join", "adm:setting:force_join_enabled")],
        [button("🟢 Change referral %", "adm:ref_rate")],
        [button("⬅️ Admin center", "admin")],
    ])
    await show(update, text, kb)

@admin_only
async def admin_setting_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    key = update.callback_query.data.split(":", 2)[2]; s = store.settings(); store.update_settings({key: not s.get(key, True)}); await admin_settings(update, ctx)

@admin_only
async def admin_ref_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["admin_state"] = "ref_rate"; await show(update, "🟢 Send the new referral percentage, for example <code>7.5</code>.", InlineKeyboardMarkup([[button("Cancel", "adm:settings")]]))

@admin_only
async def admin_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["admin_state"] = "broadcast"; await show(update, "📢 Send the broadcast message now. It will be sent to all non-banned users.", InlineKeyboardMarkup([[button("Cancel", "admin")]]))

@admin_only
async def admin_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state = ctx.user_data.pop("admin_state", None); text = update.message.text.strip()
    if state == "user_search":
        query = text.lstrip("@").lower()
        matches = []
        for uid, user in store.data.get("users", {}).items():
            if query == uid or query in str(user.get("username", "")).lower() or query in str(user.get("name", "")).lower():
                matches.append(int(uid))
        if not matches:
            await update.message.reply_text("No matching user found."); return
        for uid in matches[:10]:
            await admin_user_detail(update, ctx, uid)
    elif state == "ref_rate":
        try: store.update_settings({"referral_rate": max(0, min(100, float(text)))})
        except ValueError: await update.message.reply_text("Please send a valid number."); return
        await update.message.reply_text("✅ Referral percentage updated.")
    elif state == "add_product":
        parts = [x.strip() for x in text.split("|", 6)]
        while len(parts) < 7:
            parts.append("")
        try: price, stock = float(parts[1]), int(parts[2])
        except ValueError: await update.message.reply_text("Price and stock must be numeric."); return
        try: referrals_required = max(0, int(parts[6] or 0))
        except ValueError: await update.message.reply_text("referrals_required must be a whole number."); return
        category_id = parts[5].lower().replace(" ", "_") if parts[5] else "general"
        if category_id != "general":
            store.data["categories"].setdefault(category_id, {"name": parts[5], "created_at": iso_now()})
        pid = store.new_id("prod"); store.data["products"][pid] = {"name": parts[0], "price": price, "stock": stock, "description": parts[3], "delivery": parts[4], "category_id": category_id, "referrals_required": referrals_required, "active": True}; store.save(); await update.message.reply_text("✅ Product added.", reply_markup=reply_keyboard(update.effective_user.id))
    elif isinstance(state, str) and state.startswith("edit_product:"):
        pid = state.split(":", 1)[1]
        if pid not in store.data["products"]:
            await update.message.reply_text("Product no longer exists."); return
        parts = [x.strip() for x in text.split("|", 6)]
        while len(parts) < 7:
            parts.append("")
        try: price, stock = float(parts[1]), int(parts[2])
        except ValueError: await update.message.reply_text("Price and stock must be numeric."); return
        try: referrals_required = max(0, int(parts[6] or 0))
        except ValueError: await update.message.reply_text("referrals_required must be a whole number."); return
        category_id = parts[5].lower().replace(" ", "_") if parts[5] else "general"
        if category_id != "general":
            store.data["categories"].setdefault(category_id, {"name": parts[5], "created_at": iso_now()})
        store.data["products"][pid].update({"name": parts[0], "price": price, "stock": stock, "description": parts[3], "delivery": parts[4], "category_id": category_id, "referrals_required": referrals_required}); store.save(); await update.message.reply_text("✅ Product updated.", reply_markup=reply_keyboard(update.effective_user.id))
    elif state == "broadcast":
        sent = 0
        for uid, u in store.data.get("users", {}).items():
            if not u.get("banned"):
                try: await ctx.bot.send_message(int(uid), text); sent += 1
                except Exception: pass
        await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")

async def text_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    if is_admin(update.effective_user.id) and ctx.user_data.get("admin_state"):
        await admin_text(update, ctx); return
    mapping = {"🛒 Browse shop": shop, "📚 Purchase history": history, "👤 My profile": profile, "🎁 Refer & earn": referrals, "🆘 Support": support, "ℹ️ About": about, "⚙️ Admin panel": admin}
    fn = mapping.get(t)
    if fn:
        if t != "🆘 Support" and not is_admin(update.effective_user.id) and not await require_membership(update, ctx):
            return
        await fn(update, ctx)


async def document_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id) and ctx.user_data.get("admin_state") == "restore":
        await admin_document(update, ctx)

async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "verify_join":
        await verify_join(update, ctx)
        return
    if data != "support" and not is_admin(update.effective_user.id):
        if not await require_membership(update, ctx):
            return
    routes = {"home": home, "shop": shop, "history": history, "profile": profile, "referrals": referrals, "ref_copy": ref_copy, "support": support, "about": about, "admin": admin, "adm:products": admin_products, "adm:add": admin_add, "adm:stats": admin_stats, "adm:buttons": admin_buttons, "adm:settings": admin_settings, "adm:ref_rate": admin_ref_rate, "adm:broadcast": admin_broadcast, "adm:user_search": admin_user_search, "adm:backup": admin_backup, "adm:restore": admin_restore}
    if data in routes: await routes[data](update, ctx); return
    if data.startswith("category:"): await category(update, ctx)
    if data.startswith("product:"): await product(update, ctx)
    elif data.startswith("buy:"): await buy(update, ctx)
    elif data.startswith("order:"): await order_status(update, ctx)
    elif data.startswith("download:"): await download_purchase(update, ctx)
    elif data.startswith("adm:product:"): await admin_product_detail(update, ctx)
    elif data.startswith("adm:edit:"): await admin_edit(update, ctx)
    elif data.startswith("adm:delete_confirm:"): await admin_delete_confirm(update, ctx)
    elif data.startswith("adm:delete:"): await admin_delete(update, ctx)
    elif data.startswith("adm:toggle:"): await admin_toggle(update, ctx)
    elif data.startswith("adm:button:"): await admin_button_toggle(update, ctx)
    elif data.startswith("adm:setting:"): await admin_setting_toggle(update, ctx)

async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled update error", exc_info=ctx.error)

async def run_webhook_server(app: Application):
    if not web or not PUBLIC_WEBHOOK_URL:
        log.info("No public webhook URL configured; OxaPay payment status polling will be used every %ss", PAYMENT_POLL_SECONDS)
        return None
    server = web.Application(); server["telegram_bot"] = app.bot; server.router.add_post("/oxapay/webhook", oxapay_webhook)
    runner = web.AppRunner(server); await runner.setup(); await web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT).start(); log.info("OxaPay webhook listening on %s:%s", WEBHOOK_HOST, WEBHOOK_PORT); return runner

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("shop", shop)); app.add_handler(CommandHandler("history", history)); app.add_handler(CommandHandler("profile", profile)); app.add_handler(CommandHandler("refer", referrals)); app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(callback_router)); app.add_handler(MessageHandler(filters.Document.ALL, document_router)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)); app.add_error_handler(error_handler)
    await app.initialize(); await app.bot.set_my_commands([BotCommand("start", "Open the shop"), BotCommand("shop", "Browse products"), BotCommand("history", "Purchase history"), BotCommand("profile", "My profile"), BotCommand("refer", "Referral program")]); await app.start()
    if app.job_queue:
        app.job_queue.run_repeating(poll_pending_payments, interval=PAYMENT_POLL_SECONDS, first=5, name="oxapay-payment-poller")
    await run_webhook_server(app); await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    log.info("Modern shop bot is running")
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop(); await app.stop(); await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())

# Official OxaPay references:
# https://docs.oxapay.com/api-reference/payment/generate-invoice
# https://docs.oxapay.com/webhook
# Webhook fulfillment intentionally waits for status=Paid and verifies HMAC-SHA512.


def migrate_legacy_products():
    """Optional helper for operators: legacy categories can be transformed outside runtime."""
    return None


# End of file
