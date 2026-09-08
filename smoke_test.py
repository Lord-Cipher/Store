import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    os.environ['BOT_TOKEN'] = 'test-token'
    os.environ['ADMIN_IDS'] = '1001'
    os.environ['DATA_FILE'] = str(Path(td) / 'data.json')
    os.environ['OXAPAY_MERCHANT_API_KEY'] = 'test-key'
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
    print('smoke tests passed')
