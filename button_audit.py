import ast
from pathlib import Path

source = Path(__file__).with_name('botsellingbot.py').read_text(encoding='utf-8')
tree = ast.parse(source)
callbacks = set()
for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue
    if isinstance(node.func, ast.Name) and node.func.id == 'button' and len(node.args) >= 2:
        if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
            callbacks.add(node.args[1].value)
    for kw in node.keywords:
        if kw.arg == 'callback_data' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            callbacks.add(kw.value.value)

exact = {
    'verify_join', 'support', 'shop', 'history', 'profile', 'referrals', 'about', 'admin',
    'home', 'ref_copy', 'adm:products', 'adm:add', 'adm:stats', 'adm:buttons',
    'adm:settings', 'adm:ref_rate', 'adm:broadcast', 'adm:user_search', 'adm:backup',
    'adm:restore', 'adm:setting:purchases_enabled', 'adm:setting:referrals_enabled',
    'adm:setting:force_join_enabled',
}
prefixes = ('category:', 'product:', 'buy:', 'order:', 'download:', 'adm:product:', 'adm:edit:', 'adm:delete:', 'adm:delete_confirm:', 'adm:toggle:', 'adm:button:', 'adm:setting:')
unhandled = sorted(c for c in callbacks if c not in exact and not c.startswith(prefixes))
assert not unhandled, f'Unhandled static callback values: {unhandled}'

assert 'ReplyKeyboardMarkup' not in source, 'Persistent reply keyboard found; UI must be inline-only'
assert 'reply_keyboard' not in source, 'Persistent reply keyboard helper found; UI must be inline-only'
print(f'button audit passed: {len(callbacks)} static callback values checked; inline-only UI enforced')
