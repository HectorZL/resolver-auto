import nest_asyncio
nest_asyncio.apply()
import asyncio
import sys
from playwright.sync_api import sync_playwright

async def async_task():
    print("Async task running...")
    await asyncio.sleep(1)
    print("Async task finished.")

def main():
    print("TEST: Starting Playwright Sync/Async concurrency test...")
    
    # 1. Simulate an async loop (like Gemini/Google Generative AI does)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    print("TEST: Starting Playwright Instance 1...")
    p1 = sync_playwright().start()
    try:
        b1 = p1.chromium.launch()
        print("TEST: Playwright Instance 1 started successfully.")
        b1.close()
    except Exception as e:
        print(f"TEST ERROR: Failed to start Playwright 1: {e}")
        return

    # 2. Run async task to ensure loop is active/touched
    print("TEST: Running async task...")
    loop.run_until_complete(async_task())
    
    # 3. Try to start Playwright again (Simulating Recovery/Login Retry)
    # Without nest_asyncio, this usually fails if the loop is considered 'running' or interferes
    print("TEST: Starting Playwright Instance 2 (Simulating Recovery)...")
    try:
        p2 = sync_playwright().start() 
        print("TEST: Playwright Instance 2 started successfully (FIX VERIFIED).")
        p2.stop()
    except Exception as e:
        print(f"TEST FAILED: Caught error during re-entry: {e}")
        sys.exit(1)

    p1.stop()
    print("TEST: All checks passed.")

if __name__ == "__main__":
    main()
