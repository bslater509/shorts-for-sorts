"""Playwright-based TikTok video upload and session-login automation."""

from __future__ import annotations

import asyncio
import os

from playwright.async_api import async_playwright

# --- Constants ---

LOGIN_TIMEOUT_MS: int = 300_000
"""Maximum time (ms) to wait for TikTok login to complete."""

LOGIN_COOKIE_SETTLE_SECONDS: float = 5.0
"""Seconds to wait after login page navigation for cookies to finalise."""

UPLOAD_WAIT_SELECTOR_TIMEOUT_MS: int = 30_000
"""Timeout (ms) for the file input selector on the TikTok upload page."""

UPLOAD_CAPTION_TIMEOUT_MS: int = 60_000
"""Timeout (ms) for the caption editor to appear."""

UPLOAD_POST_TIMEOUT_MS: int = 60_000
"""Timeout (ms) for the final "Your video has been uploaded" confirmation."""

TIKTOK_LOGIN_URL: str = "https://www.tiktok.com/login"
TIKTOK_UPLOAD_URL: str = (
    "https://www.tiktok.com/tiktokstudio/upload?is_from_native_theme=1"
)

SEL_FILE_INPUT: str = "input[type='file'][accept='video/*']"
SEL_CAPTION: str = ".public-DraftEditor-content"

USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# --- Public API ---


async def login_to_tiktok() -> str | None:
    """Open a browser for the user to log into TikTok interactively.

    Returns the ``sessionid`` cookie value after successful login,
    or ``None`` if login was not completed (timeout or early close).

    The browser runs in non-headless mode so the user can interact.
    """
    print("Launching browser for TikTok login...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(TIKTOK_LOGIN_URL)
        print("Please log into TikTok in the opened browser window.")
        print(
            "Waiting for login to complete... "
            "(Close the browser when done or wait 5 minutes)"
        )

        try:
            await page.wait_for_url("https://www.tiktok.com/", timeout=LOGIN_TIMEOUT_MS)
            await asyncio.sleep(LOGIN_COOKIE_SETTLE_SECONDS)
        except Exception:
            pass  # Timeout or closed early

        cookies = await context.cookies()
        await browser.close()

        sessionid: str | None = None
        for cookie in cookies:
            if cookie["name"] == "sessionid":
                sessionid = cookie["value"]
                break

        return sessionid


async def upload_video(
    sessionid: str,
    video_path: str,
    description: str,
    visibility: str = "Public",
) -> bool:
    """Upload a video to TikTok using Playwright automation with a session cookie.

    Args:
        sessionid: The ``sessionid`` cookie value (obtained via :func:`login_to_tiktok`).
        video_path: Path to the local video file to upload.
        description: Caption/description text for the video.
        visibility: Visibility setting (``"Public"``, ``"Friends"``, ``"Private"``).

    Returns:
        ``True`` if the upload was confirmed successful.

    Raises:
        FileNotFoundError: If ``video_path`` does not exist.
        Exception: Re-raises any Playwright-level upload error.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    print(f"Uploading {video_path} to TikTok...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)

        # Set the sessionid cookie
        await context.add_cookies(
            [
                {
                    "name": "sessionid",
                    "value": sessionid,
                    "domain": ".tiktok.com",
                    "path": "/",
                }
            ]
        )

        page = await context.new_page()

        try:
            await page.goto(TIKTOK_UPLOAD_URL)

            # Wait for the file input
            await page.wait_for_selector(
                SEL_FILE_INPUT, timeout=UPLOAD_WAIT_SELECTOR_TIMEOUT_MS
            )

            # Set the file
            await page.set_input_files(SEL_FILE_INPUT, video_path)

            # Wait for the caption editor to appear
            await page.wait_for_selector(SEL_CAPTION, timeout=UPLOAD_CAPTION_TIMEOUT_MS)

            # Clear existing caption and type the new one
            await page.click(SEL_CAPTION)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(description, delay=50)

            # Click the Post button
            post_button = page.locator("button:has-text('Post')").last
            await post_button.click()

            # Wait for upload confirmation
            await page.wait_for_selector(
                "text=Your video has been uploaded",
                timeout=UPLOAD_POST_TIMEOUT_MS,
            )

            print("Upload successful!")
            return True

        except Exception as e:
            print(f"Error during upload: {e}")
            await page.screenshot(path="tiktok_error.png")
            raise e
        finally:
            await browser.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "login":
        sid: str | None = asyncio.run(login_to_tiktok())
        if sid:
            print(f"Login successful! Session ID: {sid}")
        else:
            print("Failed to get session ID.")
