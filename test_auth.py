import sys
import asyncio
from tiktok_uploader.upload import TikTokUploader

sessionid = "f1bfffe6a6cf3dce326f8a327e752a5f"
try:
    print("Testing TikTokUploader auth...")
    uploader = TikTokUploader(sessionid=sessionid, headless=True, browser="chromium")
    # Accessing page triggers lazy loading and auth
    page = uploader.page
    print("Page URL:", page.url)
    
    # Let's navigate to upload page and see if we get bounced to login
    page.goto("https://www.tiktok.com/creator-center/upload")
    page.wait_for_timeout(2000)
    print("Final URL:", page.url)
    if "login" in page.url:
        print("AUTH FAILED: Redirected to login")
    else:
        print("AUTH SUCCESS: Reached creator center")
    uploader.close()
except Exception as e:
    print(f"Error: {e}")
