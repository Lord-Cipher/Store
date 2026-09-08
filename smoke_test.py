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
