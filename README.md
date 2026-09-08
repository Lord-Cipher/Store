# Modern Telegram Digital Shop Bot

This version replaces the legacy mixed-language experience with an English-first, configuration-driven digital shop. The user flow is centered on browsing products, secure OxaPay checkout, automatic delivery, purchase history, profile, referrals, and runtime-managed payment methods. The old deposit button has been removed.

## Features

- English-first inline-only interface with red, blue, and green status/action buttons.
- OxaPay invoice creation, HMAC-verified webhooks, and automatic status polling when no public webhook URL is available.
- OxaPay settlement is always USD. The display label can be configured independently in the admin panel, for example `500.00 PRS`, `£1.00`, or `30.00 ₹`.
- Runtime payment manager with automatic and manual payment categories. Admins can enable, disable, add, edit, and delete methods. Disabled methods are hidden from users.
- Purchase history with pending status checks and re-download buttons.
- Finite stock depletion, out-of-stock handling, temporary stock reservations, and automatic reservation release.
- Product categories, product CRUD, referral unlock requirements, flash-sale prices, and flash-sale expiry.
- Coupons with percentage/fixed discounts, expiry, usage limits, minimum amounts, and free checkout.
- Support tickets, admin replies, notifications, analytics, low-stock alerts, broadcasts, backups, and restore.
- Admin roles: owner, manager, finance, support, and viewer.
- Runtime force-join channel manager with configurable IDs, titles, URLs, and enabled state.

## Hosting setup

1. Extract the ZIP.
2. Install the dependencies from the included `requirements.txt`:

```bash
python3 -m pip install -r requirements.txt
```

3. Configure the variables from `.env.example`. Hosting panels may call these **Environment Variables**, **Secrets**, or **Config Variables**. If the panel has no environment-variable section, copy `.env.example` to `.env`; the bot loads it automatically. Never commit the real `.env` file.
4. Start the bot:

```bash
python3 botsellingbot.py
```

Required variables are `BOT_TOKEN`, `ADMIN_IDS`, and `OXAPAY_MERCHANT_API_KEY`. A public HTTPS URL is optional because the bot can poll OxaPay payment status automatically.

### Important dependency note

This bot uses the **python-telegram-bot** package and imports `from telegram import ...`. Do not install `pyTelegramBotAPI`; it is a different library and will cause `ModuleNotFoundError: No module named 'telegram'` or incompatible imports. The included requirements file pins the correct package as `python-telegram-bot==21.11`.

If a hosting panel has cached or preconfigured packages, remove `pyTelegramBotAPI` from its package list and redeploy using the included `requirements.txt`. The startup log should show `python-telegram-bot` being installed, not `pyTelegramBotAPI`.

## Configuration

### Force join

To require users to join channels, use **Admin control center → Settings → Manage required channels** and enter:

```text
channel_id|button title|https://t.me/channel
```

Separate multiple channels with semicolons. Send `off` to disable force join and clear the configured channels. `FORCE_JOIN_CHANNELS` in `.env.example` is only an optional initial seed.

### Products

From **Admin control center → Products → Add product**, send:

```text
Name | price | stock | description | delivery | category | referrals_required | sale_price | sale_ends_at
```

Use stock `-1` for unlimited stock. Delivery can be plain text, one Telegram file such as `file:TELEGRAM_FILE_ID`, or multiple files separated with `||`. Existing shorter product lines remain supported.

### Coupons

From **Admin control center → Coupons → Create coupon**, send:

```text
CODE | percent/fixed | value | max_uses | expires_at | min_amount
```

Use `-1` for unlimited uses and leave the expiry blank for no expiry.

### Payment methods

From **Admin control center → Payments**:

- Toggle automatic OxaPay on or off.
- Add, edit, enable, disable, or delete manual payment methods.
- Manual methods use `code | display name | instructions`.
- Disabled methods are not displayed to users.
- Manual payment orders remain pending until an authorized admin confirms them.

## Payment safety

The bot records an order as pending when an invoice is created. It only marks an automatic order paid, decrements finite stock, adds purchase history, sends delivery, and credits a referral reward after OxaPay reports `Paid`. Duplicate callbacks are idempotent. Manual orders use the same fulfillment path after admin confirmation.

## Security

Keep `BOT_TOKEN`, `ADMIN_IDS`, and `OXAPAY_MERCHANT_API_KEY` private. Because the merchant key was shared in chat previously, rotate it in OxaPay before production use if it has been exposed elsewhere.
