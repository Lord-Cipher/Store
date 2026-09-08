# Modern Telegram Digital Shop Bot

This version replaces the legacy mixed-language experience with an English-first, configuration-driven digital shop. The user flow is centered on browsing products, secure OxaPay checkout, automatic delivery, purchase history, profile, and referrals. The old deposit button has been removed.

## Included

- Consistent inline UI using blue navigation buttons, green action buttons, and red control/status buttons.
- Product catalog with price, stock, description, active/inactive state, and delivery content.
- Purchase history stored by user.
- OxaPay invoice creation with `merchant_api_key` and `order_id`.
- HMAC-SHA512 validation for OxaPay webhooks.
- Automatic OxaPay payment-status polling when no public webhook URL is available.
- Fulfillment only after OxaPay reports `Paid`.
- Configurable referral percentage and automatic referral balance rewards.
- Optional force-join gate with blue channel buttons and a green **Verify membership** button.
- Admin control center with product toggles, analytics, button manager, settings, and broadcast.
- Atomic JSON persistence suitable for a small bot; migrate to Firebase/Postgres when multi-instance scale is required.

## Setup

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2. Set `BOT_TOKEN`, `ADMIN_IDS`, and `OXAPAY_MERCHANT_API_KEY`. On a bot-hosting panel, add them in the host's **Environment Variables**, **Secrets**, or **Config Variables** section. If the host does not provide that section, copy `.env.example` to `.env`; the bot loads that file automatically. Do not commit the real `.env` file. The provided merchant key should be entered there locally, not committed to GitHub. Since it was shared in chat, rotate it in OxaPay if it has been exposed anywhere else.

3. A public HTTPS URL is optional. If you have one, set `PUBLIC_WEBHOOK_URL`; OxaPay will send signed callbacks to `POST /oxapay/webhook`. If you do not have one, leave it empty: the bot automatically checks each pending invoice through OxaPay's official payment-information endpoint every `PAYMENT_POLL_SECONDS` seconds. The hosting process must remain online for this automatic checker to run.

4. To require users to join one or more Telegram channels before using the shop, set `FORCE_JOIN_CHANNELS` using this format:

```env
FORCE_JOIN_CHANNELS=@my_channel|Official channel|https://t.me/my_channel
```

For multiple channels, separate entries with semicolons. The bot must be an administrator in each required channel so Telegram can verify membership. Users see a join UI and a green **Verify membership** button; the shop opens only after every channel is verified. The admin panel can turn the force-join feature on or off.

5. Start the bot:

```bash
python3 botsellingbot.py
```

The host must install `requirements.txt` before starting the bot. Environment variables supplied by the hosting panel take priority over values in a local `.env` file.

## Product management

From the admin panel, choose **Products**, then **Add product** and send:

```text
Name | price | stock | description | delivery
```

Use stock `-1` for unlimited stock. Delivery may be plain text or `file:TELEGRAM_FILE_ID`.

## Payment safety

The bot records an order as pending when an invoice is created. It only marks the order paid, decrements finite stock, adds the purchase-history record, sends delivery, and credits the referral reward after a valid OxaPay webhook with status `Paid`. Duplicate webhooks are idempotent.

## Validation

```bash
python3 -m py_compile botsellingbot.py
```

The official references used for the integration are [OxaPay Generate Invoice](https://docs.oxapay.com/api-reference/payment/generate-invoice) and [OxaPay Webhook](https://docs.oxapay.com/webhook).
