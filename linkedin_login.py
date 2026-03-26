"""
LinkedIn Login Automation via Pyppeteer (Puppeteer Python)

Automates LinkedIn login and cookie extraction.
Uses local browser automation - no external services needed.
Single IP (server) = LinkedIn security bypass.
"""

import asyncio
import logging
from pathlib import Path
import time

try:
    from pyppeteer import launch
    from pyppeteer.errors import TimeoutError as PuppeteerTimeout
except ImportError:
    raise ImportError("pyppeteer required: pip install pyppeteer")

logger = logging.getLogger(__name__)

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"


async def login_and_extract_cookies(email: str, password: str, timeout: int = 60) -> dict:
    """
    Automate LinkedIn login and extract cookies.
    
    Args:
        email: LinkedIn email
        password: LinkedIn password
        timeout: Timeout in seconds (default 60)
    
    Returns:
        dict with cookies: li_at, jsessionid, bcookie, lidc, etc.
    
    Raises:
        Exception: If login fails
    """
    
    logger.info(f"🚀 Launching Pyppeteer browser for {email}...")
    
    browser = None
    try:
        # Launch browser (headless, single process for speed)
        browser = await launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',  # Avoid /dev/shm issues
                '--single-process'
            ]
        )
        
        logger.info("✓ Browser launched")
        
        # Create page
        page = await browser.newPage()
        
        # Set viewport
        await page.setViewport({'width': 1920, 'height': 1080})
        
        logger.info("📍 Navigating to LinkedIn login...")
        
        # Navigate to login
        try:
            await page.goto(LINKEDIN_LOGIN_URL, {'waitUntil': 'networkidle2', 'timeout': timeout * 1000})
        except PuppeteerTimeout:
            raise Exception(f"Login page timeout after {timeout}s")
        
        logger.info("✓ Login page loaded")
        
        # Fill email
        logger.info("📝 Entering email...")
        await page.type('input[type="email"]', email, {'delay': 50})
        
        # Fill password
        logger.info("🔐 Entering password...")
        await page.type('input[type="password"]', password, {'delay': 50})
        
        # Click login button
        logger.info("🔘 Clicking login button...")
        await page.click('button[type="submit"]')
        
        # Wait for navigation (LinkedIn redirects after login)
        logger.info("⏳ Waiting for dashboard...")
        try:
            await page.waitForNavigation({'waitUntil': 'networkidle2', 'timeout': timeout * 1000})
        except PuppeteerTimeout:
            raise Exception(f"Dashboard load timeout after {timeout}s")
        
        logger.info("✓ Login successful")
        
        # Extract cookies
        logger.info("🍪 Extracting cookies...")
        cookies = await page.cookies()
        
        logger.info(f"✓ Extracted {len(cookies)} cookies")
        
        # Parse cookies into dict
        cookies_dict = {}
        for cookie in cookies:
            cookies_dict[cookie['name']] = cookie['value']
        
        logger.info(f"Cookie names: {list(cookies_dict.keys())}")
        
        # Verify required cookies
        required = ['li_at', 'JSESSIONID']
        for req in required:
            if req not in cookies_dict:
                logger.warning(f"⚠️  Missing cookie: {req}")
        
        # Close page
        await page.close()
        
        logger.info("✅ Login and cookie extraction successful")
        
        return cookies_dict
    
    except Exception as e:
        logger.error(f"❌ Login failed: {e}")
        raise
    
    finally:
        if browser:
            await browser.close()
            logger.info("🔌 Browser closed")


def login_and_extract_cookies_sync(email: str, password: str, timeout: int = 60) -> dict:
    """
    Synchronous wrapper for login_and_extract_cookies()
    
    Args:
        email: LinkedIn email
        password: LinkedIn password
        timeout: Timeout in seconds
    
    Returns:
        dict with cookies
    """
    
    logger.info("Starting async login process...")
    
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("Cannot run async function from running event loop")
    except RuntimeError:
        # No loop or closed loop, create new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(login_and_extract_cookies(email, password, timeout))
    finally:
        loop.close()


async def validate_login(email: str, password: str) -> tuple[bool, str]:
    """
    Test login without extracting full cookies.
    Returns (success, message)
    """
    
    logger.info(f"🔍 Validating login for {email}...")
    
    try:
        await login_and_extract_cookies(email, password, timeout=30)
        return True, "Login exitoso"
    except Exception as e:
        return False, f"Login fallido: {str(e)}"
