import logging
import time
from typing import Callable, Optional

import cookie.firefox_cookies as firefox_cookies

logger = logging.getLogger(__name__)

def mask_cookie(cookie_value: str) -> str:
    """Mask a cookie value to show only stars and last 4 characters"""
    if not cookie_value or len(cookie_value) <= 4:
        return "****"
    return "****" + cookie_value[-4:]

def get_vpn_cookie(initial_cookies: list[str], should_stop_callback: Optional[Callable[[], bool]] = None) -> Optional[str]:
    """
    Wait for a new webvpn cookie to appear.

    Args:
        initial_cookies: List of cookies that existed before login
        should_stop_callback: Optional function that returns True if monitoring should stop

    Returns:
        Cookie value if found, None if timeout or cancelled
    """
    logger.info("Waiting for webvpn cookie to be set after login")
    max_wait_time = 120  # seconds
    start_time = time.time()

    while time.time() - start_time < max_wait_time:
        # Check for cancellation if callback provided
        if should_stop_callback and should_stop_callback():
            logger.info("Cookie monitoring cancelled by user")
            return None

        elapsed = int(time.time() - start_time)

        # Get current webvpn cookies from Firefox cookie file
        current_cookies = firefox_cookies.get_webvpn_cookies() # TODO: Add cookie host filter
        masked_cookies = [mask_cookie(cookie) for cookie in current_cookies] if current_cookies else []
        logger.debug(f"Found webvpn cookies after {elapsed}s: {masked_cookies}")

        # Check if we have any new cookies that weren't in the initial set
        new_cookies = [cookie for cookie in current_cookies if cookie not in initial_cookies]

        if new_cookies:
            # Return the first new webvpn cookie found
            cookie_value = new_cookies[0]
            logger.info(f"Found new webvpn cookie: {mask_cookie(cookie_value)}")
            return cookie_value
        elif current_cookies and not initial_cookies:
            # If we didn't have any initial cookies but now we do, use the first one
            cookie_value = current_cookies[0]
            logger.info(f"Found webvpn cookie: {mask_cookie(cookie_value)}")
            return cookie_value

        if elapsed % 10 == 0:  # Log every 10 seconds
            logger.info(f"Still waiting for webvpn cookie... ({elapsed}s elapsed)")

        # Use shorter sleep intervals if cancellation callback is provided for better responsiveness
        if should_stop_callback:
            # Check for cancellation more frequently
            for _ in range(10):  # Check every 200ms instead of sleeping for 2 seconds
                if should_stop_callback():
                    logger.info("Cookie monitoring cancelled by user")
                    return None
                time.sleep(0.2)
        else:
            time.sleep(2)

    logger.error("Timeout waiting for webvpn cookie")
    return None
