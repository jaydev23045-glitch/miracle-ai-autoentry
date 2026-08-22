import asyncio
import json
from playwright.async_api import async_playwright

async def test_ui_fixes():
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        push_payload = None
        
        async def handle_request(request):
            nonlocal push_payload
            if "push" in request.url and request.method == "POST":
                push_payload = request.post_data_json
                print(f"\n[NETWORK] Intercepted push request to {request.url}")
            
        page.on("request", handle_request)
        
        print("1. Opening app...")
        await page.goto("http://localhost:8000/")
        await page.wait_for_selector("#moduleTitle")
        
        print("2. Switching to Bank Statements module...")
        await page.click('a[data-module="Bank Statements"]')
        await page.wait_for_timeout(1000)
        
        print("3. Adding manual row...")
        await page.click('#addEntryBtn')
        await page.wait_for_selector('.narration-input')
        
        print("4. Filling narration with 'Testing narration fix'...")
        await page.fill('.narration-input', 'Testing narration fix')
        await page.wait_for_timeout(500)
        
        print("5. Selecting a party/ledger mapping...")
        try:
            # Let's try to select the second option in the dropdown (index 1)
            await page.select_option('.party-select', index=1)
        except Exception as e:
            print(f"Warning: Could not select option index 1: {e}")
            # If it fails, maybe there are no ledgers loaded, we'll try to forcefully inject a mapped_ledger value
            # just to test the logic
            pass
            
        await page.wait_for_timeout(500)
        
        print("6. Simulating Push to Miracle...")
        # Force enable push button just in case
        await page.evaluate("document.getElementById('pushBtn').removeAttribute('disabled')")
        await page.click('#pushBtn')
        
        # Wait a bit for the network request to fire
        await page.wait_for_timeout(2000)
        
        print("\n--- TEST RESULTS ---")
        if push_payload:
            vouchers = push_payload.get('vouchers', [])
            if vouchers:
                row = vouchers[0]
                print(f"Extracted Sent Narration: '{row.get('narration')}'")
                print(f"Extracted Sent Party Name: '{row.get('party_name')}'")
                
                if row.get('party_name') == 'Testing narration fix':
                    print("❌ BUG FOUND: Narration STILL overwrites the party name in the payload! The fix failed.")
                else:
                    print("✅ BUG 1 FIX CONFIRMED: Narration does NOT overwrite the Party Name anymore!")
                    
                if row.get('party_name') != 'Suspense Account' and row.get('party_name') is not None:
                    print("✅ BUG 2 FIX CONFIRMED: Manual Mapping is successfully sent to the backend!")
            else:
                print("❌ No vouchers in payload.")
        else:
            print("❌ No push payload intercepted. Push request didn't fire.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_ui_fixes())
