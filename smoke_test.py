import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    os.environ['BOT_TOKEN'] = 'test-token'
    os.environ['ADMIN_IDS'] = '1001'
    os.environ['DATA_FILE'] = str(Path(td) / 'data.json')
    os.environ['OXAPAY_MERCHANT_API_KEY'] = 'test-key'
    os.environ['FORCE_JOIN_CHANNELS'] = '@demo|Demo channel|https://t.me/demo'
    import botsellingbot as bot

    assert bot.is_admin(1001)
    bot.store.data['products']['p1'] = {'name': 'Demo', 'price': 10, 'stock': 2, 'active': True}
    bot.store.save()
    assert bot.store.data['products']['p1']['price'] == 10
    bot.store.update_settings({'referral_rate': 7.5, 'main_buttons': {'history': False}})
    assert bot.store.settings()['referral_rate'] == 7.5
    assert bot.store.settings()['main_buttons']['history'] is False
    assert bot.status(True) == '🟢 ON'
    assert bot.status(False) == '🔴 OFF'
    assert bot.stock_label(100) == '🟢 100 available'
    assert bot.stock_label(0) == '🔴 Out of stock'
    assert bot.stock_label(-1) == '🟢 Unlimited'
    assert bot.referral_requirement({'referrals_required': 3}) == 3
    assert bot.effective_price({'price': 10, 'sale_price': 4, 'sale_ends_at': '2999-01-01T00:00:00+00:00'}) == 4
    bot.store.data['coupons']['WELCOME10'] = {'code': 'WELCOME10', 'type': 'percent', 'value': 10, 'max_uses': 10, 'uses': 0, 'used_by': [], 'active': True, 'min_amount': 0}
    coupon, error = bot.active_coupon('welcome10', 1001, 10)
    assert coupon and not error and bot.coupon_discount(coupon, 10) == 1
    reservation = bot.reserve_stock('p1', 1001)
    assert reservation and bot.store.data['products']['p1']['stock'] == 1
    bot.release_reservation({'reservation_id': reservation})
    assert bot.store.data['products']['p1']['stock'] == 2
    assert bot.admin_role(1001) == 'owner'
    assert bot.store.settings()['currency'] == 'USD'
    assert any(code == 'oxapay' for _, code, _ in bot.enabled_payment_methods())
    bot.store.data['payment_methods']['manual']['demo'] = {'name': 'Demo Manual', 'instructions': 'Send proof', 'enabled': False}
    assert not any(code == 'demo' for _, code, _ in bot.enabled_payment_methods())
    bot.notify_user(1001, 'test notification')
    assert bot.store.data['notifications']['1001'][-1]['message'] == 'test notification'
    enabled, channels = bot.force_join_settings()
    assert enabled is True
    assert channels[0]['title'] == 'Demo channel'
    assert channels[0]['url'] == 'https://t.me/demo'
    assert bot.PAYMENT_POLL_SECONDS >= 30
    assert bot.OXAPAY_STATUS_URL.endswith('/payment')
    bot.store.data['categories']['automation'] = {'name': 'Automation'}
    bot.store.data['products']['p1']['category_id'] = 'automation'
    purchase_id = bot.store.add_purchase({'uid': 1001, 'product_name': 'Demo', 'price': 10, 'delivery': 'demo-key', 'status': 'paid'})
    assert purchase_id in bot.store.data['purchases']
    assert bot.store.data['products']['p1']['category_id'] == 'automation'
    print('smoke tests passed')
