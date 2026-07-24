#!/usr/bin/env python3
"""Inject ChatGPT cookies into Edge using Selenium (more reliable than raw CDP)."""

import json
import sys
import time
import subprocess
from pathlib import Path

# Ensure selenium is available
try:
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options
except ImportError:
    print("Installing selenium...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium", "-q"])
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options

COOKIE_FILE = Path.home() / ".crcp" / "cookie-bridge" / "chatgpt_cookies.json"
PROFILE_DIR = Path.home() / ".crcp" / "cookie-bridge" / "edge-selenium"


def main():
    # Load cookies
    data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = data["cookies"]
    print(f"Loaded {len(cookies)} cookies")

    # Launch Edge with Selenium
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    opts = Options()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-extensions")

    print("Launching Edge via Selenium...")
    driver = webdriver.Edge(options=opts)

    # First navigate to chatgpt.com to establish the domain context
    driver.get("https://chatgpt.com/")
    time.sleep(2)

    # Clear existing cookies
    driver.delete_all_cookies()

    # Inject cookies
    injected = 0
    failed = 0
    for c in cookies:
        try:
            cookie_dict = {
                "name": c["name"],
                "value": c["value"],
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
            }

            # Domain handling for Selenium
            domain = c.get("domain", ".chatgpt.com")
            if domain.startswith("."):
                cookie_dict["domain"] = domain
            else:
                cookie_dict["domain"] = domain

            # Only set cookies for chatgpt.com domain (Selenium can't cross-domain)
            if "chatgpt.com" not in domain and "openai.com" not in domain:
                continue

            # If it's an openai.com cookie, we need to navigate there first
            if "openai.com" in domain and "chatgpt.com" not in domain:
                # Skip cross-domain cookies for now — they'll get set by redirects
                continue

            # Set httpOnly flag
            if c.get("httpOnly"):
                cookie_dict["httpOnly"] = True

            # Set expiry (make persistent)
            if c.get("expires", -1) > 0:
                cookie_dict["expiry"] = int(c["expires"])
            else:
                cookie_dict["expiry"] = int(time.time()) + (30 * 24 * 3600)

            # sameSite
            ss = c.get("sameSite", "Lax")
            if ss in ("Strict", "Lax", "None"):
                cookie_dict["sameSite"] = ss

            driver.add_cookie(cookie_dict)
            injected += 1
        except Exception as e:
            failed += 1
            print(f"  SKIP: {c['name']} @ {c.get('domain')}: {e}")

    print(f"\nInjected: {injected}, Skipped: {failed}")

    # Now navigate to openai auth domain to set those cookies
    print("Setting auth.openai.com cookies...")
    auth_cookies = [
        c
        for c in cookies
        if "openai.com" in c.get("domain", "") and "chatgpt" not in c.get("domain", "")
    ]
    if auth_cookies:
        driver.get("https://auth.openai.com/")
        time.sleep(2)
        auth_ok = 0
        for c in auth_cookies:
            try:
                cookie_dict = {
                    "name": c["name"],
                    "value": c["value"],
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", True),
                }
                domain = c.get("domain", ".auth.openai.com")
                if domain.startswith("."):
                    cookie_dict["domain"] = domain
                else:
                    cookie_dict["domain"] = domain
                if c.get("httpOnly"):
                    cookie_dict["httpOnly"] = True
                if c.get("expires", -1) > 0:
                    cookie_dict["expiry"] = int(c["expires"])
                else:
                    cookie_dict["expiry"] = int(time.time()) + (30 * 24 * 3600)
                driver.add_cookie(cookie_dict)
                auth_ok += 1
            except Exception as e:
                print(f"  SKIP auth: {c['name']}: {e}")
        print(f"  Auth cookies set: {auth_ok}")

    # Navigate back to ChatGPT
    print("\nNavigating to ChatGPT with cookies...")
    driver.get("https://chatgpt.com/")
    time.sleep(5)

    # Check result
    title = driver.title
    url = driver.current_url
    print("\nResult:")
    print(f"  Title: {title}")
    print(f"  URL: {url}")

    cookie_count = len(driver.get_cookies())
    print(f"  Cookies: {cookie_count}")

    if "login" not in url.lower():
        print("\n✅ SUCCESS — ChatGPT loaded without login redirect!")
    else:
        print("\n⚠️ Got redirected to login — cookies may have expired or been rejected")

    print("\nBrowser window stays open. Close it manually when done.")
    print(
        "To re-sync later: python cookie_bridge.py extract && python inject_selenium.py"
    )

    # Keep alive
    input("Press Enter to close Edge...")
    driver.quit()


if __name__ == "__main__":
    main()
