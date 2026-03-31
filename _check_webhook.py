import inspect
from telegram.webhook import handle_message, register_handlers

source = inspect.getsource(handle_message)

checks = {
    "rate_limiter":    "rate_limit" in source.lower() or "limiter" in source.lower(),
    "voice_duration":  "60" in source,
    "process_message": "process_message" in source,
    "stub_removed":    "_stub_handler" not in source,
    "send_text":       "send_text" in source,
    "send_document":   "send_document" in source,
}

all_ok = True
for name, passed in checks.items():
    status = "OK" if passed else "FAIL"
    print(f"[{status}] {name}")
    if not passed:
        all_ok = False

# Also confirm register_handlers still exists
try:
    register_handlers  # noqa
    print("[OK] register_handlers exists")
except NameError:
    print("[FAIL] register_handlers missing")
    all_ok = False

print()
print("Webhook integrity:", "OK" if all_ok else "ISSUES FOUND")
