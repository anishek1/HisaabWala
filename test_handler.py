"""
End-to-end handler test — simulates the full pipeline without Telegram.
Creates test data, processes messages, verifies results, cleans up.
"""
import asyncio
import logging
from services.handler import process_message
from db.queries import get_merchant_by_telegram_id
from db.connection import supabase

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("test_handler")

TEST_TELEGRAM_ID = 777777777


async def cleanup():
    merchant = await get_merchant_by_telegram_id(TEST_TELEGRAM_ID)
    if merchant:
        supabase.table("message_log").delete().eq("merchant_id", merchant.id).execute()
        supabase.table("transactions").delete().eq("merchant_id", merchant.id).execute()
        supabase.table("entities").delete().eq("merchant_id", merchant.id).execute()
        supabase.table("merchants").delete().eq("telegram_id", TEST_TELEGRAM_ID).execute()
    print("Cleanup done")


async def test():
    await cleanup()

    passed = 0
    failed = 0

    # 1: First message → welcome (onboarding)
    print("\n1. First message (new user)...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "hello", 1001)
    if "स्वागत" in resp.messages[0] or "नमस्ते" in resp.messages[0]:
        print("   PASS - Got welcome message")
        passed += 1
    else:
        print(f"   FAIL - Expected welcome, got: {resp.messages[0][:80]}")
        failed += 1

    # 2: Send shop name → complete onboarding
    print("\n2. Shop name (onboarding)...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "Sharma General Store", 1002)
    if "रजिस्टर" in resp.messages[0] or "Sharma" in resp.messages[0]:
        print("   PASS - Onboarding complete")
        passed += 1
    else:
        print(f"   FAIL - Expected registration confirm, got: {resp.messages[0][:80]}")
        failed += 1

    # 3: Send transaction text → get confirmation prompt
    print("\n3. Transaction via text...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "Ramesh ne 500 diye", 1003)
    if "लेनदेन" in resp.messages[0] or "Ramesh" in resp.messages[0]:
        print(f"   PASS - Transaction confirmation: {resp.messages[0][:100]}")
        passed += 1
    else:
        print(f"   FAIL - Expected transaction confirm, got: {resp.messages[0][:100]}")
        failed += 1

    # 4: Confirm with "haan"
    print("\n4. Confirm with 'haan'...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "haan", 1004)
    if "सेव" in resp.messages[0] or "confirmed" in resp.messages[0].lower():
        print("   PASS - Transactions confirmed")
        passed += 1
    else:
        print(f"   FAIL - Expected confirmation, got: {resp.messages[0][:80]}")
        failed += 1

    # 5: Balance query
    print("\n5. Balance query...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "Ramesh ka kitna baaki hai", 1005)
    if "हिसाब" in resp.messages[0] or "\u20b9" in resp.messages[0]:
        print(f"   PASS - Balance response: {resp.messages[0][:100]}")
        passed += 1
    else:
        print(f"   FAIL - Expected balance, got: {resp.messages[0][:100]}")
        failed += 1

    # 6: Transaction then reject
    print("\n6. Transaction then reject...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "Suresh 1000 udhaar", 1006)
    if "लेनदेन" in resp.messages[0] or "Suresh" in resp.messages[0]:
        print(f"   PASS - Transaction logged: {resp.messages[0][:100]}")
    else:
        print(f"   INFO - Got: {resp.messages[0][:100]}")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "nahi", 1007)
    if "रद्द" in resp.messages[0]:
        print("   PASS - Rejection worked")
        passed += 1
    else:
        print(f"   FAIL - Expected rejection, got: {resp.messages[0][:80]}")
        failed += 1

    # 7: Report request
    print("\n7. Report request...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "mera hisaab bhejo", 1008)
    if "रिपोर्ट" in resp.messages[0] or "\U0001f4ca" in resp.messages[0] or "आमदनी" in resp.messages[0]:
        print(f"   PASS - Report: {resp.messages[0][:120]}")
        passed += 1
    else:
        print(f"   FAIL - Expected report, got: {resp.messages[0][:100]}")
        failed += 1

    # 8: Greeting
    print("\n8. Greeting...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "namaste", 1009)
    if "नमस्ते" in resp.messages[0] or "Voice note" in resp.messages[0]:
        print("   PASS - Greeting response")
        passed += 1
    else:
        print(f"   FAIL - Expected greeting, got: {resp.messages[0][:80]}")
        failed += 1

    # 9: /help command
    print("\n9. /help command...")
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "/help", 1010)
    if "इस्तेमाल" in resp.messages[0] or "Voice note" in resp.messages[0]:
        print("   PASS - Help message received")
        passed += 1
    else:
        print(f"   FAIL - Expected help, got: {resp.messages[0][:80]}")
        failed += 1

    # 10: Correction flow
    print("\n10. Correction flow...")
    await process_message(TEST_TELEGRAM_ID, "test_user", None, "Mohan ne 800 diye", 1011)
    resp = await process_message(TEST_TELEGRAM_ID, "test_user", None, "woh 800 nahi 600 tha", 1012)
    if "सुधार" in resp.messages[0] or "\u2192" in resp.messages[0]:
        print(f"   PASS - Correction applied: {resp.messages[0][:100]}")
        passed += 1
    else:
        print(f"   FAIL - Expected correction, got: {resp.messages[0][:100]}")
        failed += 1

    await cleanup()

    print()
    print("=" * 50)
    print(f"HANDLER TEST RESULTS: {passed}/{passed + failed} passed")
    print("=" * 50)
    if failed > 0:
        print(f"  {failed} tests failed")
    else:
        print("  All handler tests passed!")


asyncio.run(test())
