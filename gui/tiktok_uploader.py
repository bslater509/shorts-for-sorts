import asyncio
import os

from playwright.async_api import async_playwright


async def login_to_tiktok():
    """Opens a browser to let the user log into TikTok and save cookies."""
    print("Launching browser for TikTok login...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.tiktok.com/login")
        print("Please log into TikTok in the opened browser window.")
        print("Waiting for login to complete... (Close the browser when done or wait 5 minutes)")

        try:
            # Wait until the user is logged in (e.g. upload button is visible) or timeout
            await page.wait_for_url("https://www.tiktok.com/", timeout=300000)
            await asyncio.sleep(5)  # Wait a bit for cookies to settle
        except Exception:
            pass  # Timeout or closed early

        cookies = await context.cookies()
        await browser.close()

        sessionid = None
        for cookie in cookies:
            if cookie["name"] == "sessionid":
                sessionid = cookie["value"]
                break

        return sessionid


async def upload_video(sessionid, video_path, description, visibility="Public"):
    """Uploads a video to TikTok using Playwright and the sessionid cookie."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    print(f"Uploading {video_path} to TikTok...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # or False for debugging
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Set the sessionid cookie
        await context.add_cookies(
            [{"name": "sessionid", "value": sessionid, "domain": ".tiktok.com", "path": "/"}]
        )

        page = await context.new_page()

        try:
            await page.goto("https://www.tiktok.com/tiktokstudio/upload?is_from_native_theme=1")

            # Check if login was successful (we should see the upload interface, not login)
            # We can wait for the file input
            file_input_selector = "input[type='file'][accept='video/*']"
            await page.wait_for_selector(file_input_selector, timeout=30000)

            # Set the file
            await page.set_input_files(file_input_selector, video_path)

            # Wait for upload to complete and the editor to appear
            # TikTok usually shows a caption editor
            caption_selector = ".public-DraftEditor-content"
            await page.wait_for_selector(caption_selector, timeout=60000)

            # Clear existing caption and type the new one
            await page.click(caption_selector)
            # Press backspace a lot or select all and delete
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")

            # Type the new description
            await page.keyboard.type(description, delay=50)

            # Post button
            # Find the button that says "Post"
            post_button = page.locator("button:has-text('Post')").last
            await post_button.click()

            # Wait for successful upload confirmation
            # This could be a modal saying "Your video has been uploaded"
            await page.wait_for_selector("text=Your video has been uploaded", timeout=60000)

            print("Upload successful!")
            return True

        except Exception as e:
            print(f"Error during upload: {e}")
            # Try to save a screenshot for debugging
            await page.screenshot(path="tiktok_error.png")
            raise e
        finally:
            await browser.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "login":
        sid = asyncio.run(login_to_tiktok())
        if sid:
            print(f"Login successful! Session ID: {sid}")
        else:
            print("Failed to get session ID.")
