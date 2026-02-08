
import nest_asyncio
nest_asyncio.apply()
import asyncio
from browser_controller import BrowserController

async def async_task():
    print("TEST: Async task executed.")
    await asyncio.sleep(0.1)

def main():
    print("TEST: Starting Integration Test for BrowserController...")
    
    # 1. Simulate active async loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_task())
    
    # 2. Initialize Controller
    browser = BrowserController(headless=True) # Use headless for test
    
    print("TEST: First start()...")
    try:
        page1 = browser.start()
        print("TEST: First start() successful.")
    except Exception as e:
        print(f"TEST ERROR: First start failed: {e}")
        return

    # 3. Simulate work and async loop usage again
    loop.run_until_complete(async_task())
    
    # 4. Attempt Second Start (Simulate Recovery)
    print("TEST: Second start() (Idempotency Check)...")
    try:
        page2 = browser.start()
        
        if page1 == page2:
             print("TEST: Page/Browser was correctly reused.")
        else:
             print("TEST: New page returned (acceptable).")
             
        print("TEST: Second start() successful (FIX VERIFIED).")
        
    except Exception as e:
        print(f"TEST FAILED: Second start crash: {e}")
        browser.close()
        return

    browser.close()
    print("TEST: Cleanup done. All passed.")

if __name__ == "__main__":
    main()
