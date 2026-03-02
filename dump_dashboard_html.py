from playwright.sync_api import sync_playwright
import json
import os

def dump_dashboard():
    config_path = "config.json"
    if not os.path.exists(config_path):
        print("Config file not found.")
        return

    with open(config_path, "r") as f:
        config = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        print("Navigating to dashboard...")
        try:
            page.goto(config.get("dashboard_url", "https://aulaslenguas.utm.edu.ec:8443/dashboard"))
        except Exception as e:
            print(f"Error navigating: {e}")
            # Try login if needed, but assuming user is logged in or we can see login page
        
        # Check if we need to login
        if "login" in page.url or "signin" in page.url:
            print("Logging in...")
            page.fill("input[name='mail']", config["email"])
            page.fill("input[name='password']", config["password"])
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")
        
        print("Waiting for modules...")
        try:
            page.wait_for_selector(".bg-white.rounded-2xl.shadow-sm", timeout=10000)
        except:
            print("Timeout waiting for modules.")

        content = page.content()
        
        print(f"HTML dumped to dashboard_dump.html")
        
        # Quick analysis
        modules = page.query_selector_all(".bg-white.rounded-2xl.shadow-sm")
        print(f"Found {len(modules)} module containers.")
        
        for i, m in enumerate(modules):
            # Try to find title in various ways
            title_el = m.query_selector("span.text-yellow-600")
            if not title_el:
                 # Backup selector?
                 title_el = m.query_selector("h2")
            
            title = title_el.inner_text() if title_el else "NO TITLE FOUND"
            
            # Check for progress
            progress_text = "No progress found"
            spans = m.query_selector_all("span")
            for span in spans:
                if "%" in span.inner_text():
                    progress_text = span.inner_text()
                    break
            
            print(f"Module {i}: Title='{title}' | Progress='{progress_text}'")

        browser.close()

if __name__ == "__main__":
    dump_dashboard()
