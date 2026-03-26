"""
Interactive LinkedIn Login - Web UI for 2FA flow

Allows step-by-step login via browser:
1. User enters email/password
2. Server starts Pyppeteer
3. LinkedIn asks for 2FA code
4. User pastes code in web form
5. Server completes login
6. Cookies extracted and saved
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

# Store active login sessions
# Key: session_id, Value: {browser, page, cookies}
ACTIVE_SESSIONS = {}


async def start_login_with_2fa(email: str, password: str, session_id: str) -> dict:
    """
    Start login process and wait for 2FA code prompt.
    Returns when LinkedIn asks for 2FA verification.
    
    Returns:
    {
        "status": "waiting_2fa",
        "message": "Código enviado a tu email. Ingresa el código de 6 dígitos",
        "session_id": session_id
    }
    """
    
    logger.info(f"🚀 Starting interactive login for {email}...")
    
    try:
        # Launch browser
        browser = await launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--single-process'
            ]
        )
        
        logger.info("✓ Browser launched")
        
        # Create page
        page = await browser.newPage()
        await page.setViewport({'width': 1920, 'height': 1080})
        
        logger.info("📍 Navigating to LinkedIn login...")
        await page.goto('https://www.linkedin.com/login', {'waitUntil': 'networkidle2', 'timeout': 30000})
        
        logger.info("✓ Login page loaded")
        
        # Wait for inputs and fill credentials
        logger.info("📝 Filling email and password...")
        await page.waitForSelector('input[name="username"]', {'timeout': 10000})
        await page.type('input[name="username"]', email, {'delay': 50})
        
        await page.waitForSelector('input[name="password"]', {'timeout': 10000})
        await page.type('input[name="password"]', password, {'delay': 50})
        
        # Click submit
        logger.info("🔘 Submitting login...")
        await page.click('button[type="submit"]')
        
        # Wait for either:
        # A) 2FA prompt
        # B) Dashboard (no 2FA)
        logger.info("⏳ Waiting for 2FA or dashboard...")
        
        try:
            # Wait for 2FA code input OR dashboard
            # Try to detect 2FA verification page
            await page.waitForSelector(
                'input[id*="verification"], input[name*="code"], input[placeholder*="code"], input[placeholder*="verify"]',
                {'timeout': 15000}
            )
            
            logger.info("✓ 2FA verification code field detected")
            
            # Store session for later use
            ACTIVE_SESSIONS[session_id] = {
                'browser': browser,
                'page': page,
                'email': email,
                'timestamp': time.time(),
                'awaiting_code': True
            }
            
            return {
                'status': 'waiting_2fa',
                'message': 'Código de verificación enviado a tu email. Ingresa el código de 6 dígitos.',
                'session_id': session_id
            }
        
        except PuppeteerTimeout:
            # No 2FA found, likely dashboard already loaded
            logger.info("No 2FA detected, checking if logged in...")
            
            # Check current URL
            current_url = page.url
            if 'feed' in current_url or 'mynetwork' in current_url or 'dashboard' in current_url:
                logger.info("✓ Successfully logged in (no 2FA required)")
                
                # Extract cookies and close
                page_cookies = await page.cookies()
                cookies_dict = {c['name']: c['value'] for c in page_cookies}
                
                await browser.close()
                
                return {
                    'status': 'success',
                    'message': 'Login successful (no 2FA required)',
                    'cookies': cookies_dict
                }
            else:
                logger.warning(f"Unknown page: {current_url}")
                await browser.close()
                raise Exception(f"Unexpected page after login: {current_url}")
    
    except Exception as e:
        logger.error(f"❌ Login start failed: {e}")
        raise


async def complete_login_with_code(session_id: str, verification_code: str) -> dict:
    """
    Complete login by entering 2FA verification code.
    
    Returns:
    {
        "status": "success",
        "message": "Login successful",
        "cookies": {...}
    }
    """
    
    logger.info(f"🔐 Attempting to complete login with verification code...")
    
    if session_id not in ACTIVE_SESSIONS:
        raise Exception(f"Session {session_id} not found or expired")
    
    session = ACTIVE_SESSIONS[session_id]
    browser = session['browser']
    page = session['page']
    
    try:
        # Clean verification code (remove spaces, dashes)
        code_clean = verification_code.replace(' ', '').replace('-', '').strip()
        
        if len(code_clean) != 6 or not code_clean.isdigit():
            raise Exception(f"Invalid code format. Expected 6 digits, got: {code_clean}")
        
        logger.info(f"📝 Entering verification code: {code_clean}")
        
        # Find and fill verification code input
        code_selectors = [
            'input[id*="verification"]',
            'input[name*="code"]',
            'input[placeholder*="code"]',
            'input[placeholder*="verify"]',
            'input[id*="pin"]',
            'input[id*="otp"]'
        ]
        
        code_entered = False
        for selector in code_selectors:
            try:
                await page.type(selector, code_clean, {'delay': 100})
                logger.info(f"✓ Code entered using selector: {selector}")
                code_entered = True
                break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
        
        if not code_entered:
            raise Exception("Could not find verification code input field")
        
        # Find and click verify button
        logger.info("🔘 Clicking verify button...")
        verify_selectors = [
            'button:contains("Verify")',
            'button[type="submit"]',
            'button:contains("Confirmar")',
            'button:contains("Submit")'
        ]
        
        button_clicked = False
        for selector in verify_selectors:
            try:
                await page.click(selector)
                logger.info(f"✓ Button clicked using selector: {selector}")
                button_clicked = True
                break
            except Exception as e:
                logger.debug(f"Button selector {selector} failed: {e}")
        
        if not button_clicked:
            # Try Enter key
            logger.info("🔘 Trying Enter key...")
            await page.press('Enter')
        
        # Wait for dashboard or error
        logger.info("⏳ Waiting for dashboard...")
        try:
            await page.waitForNavigation({'waitUntil': 'networkidle2', 'timeout': 20000})
        except PuppeteerTimeout:
            logger.warning("Navigation timeout, checking current state...")
        
        # Wait a bit more for page to stabilize
        await asyncio.sleep(3)
        
        # Check current URL
        current_url = page.url
        logger.info(f"Current URL: {current_url}")
        
        if any(x in current_url for x in ['feed', 'mynetwork', 'dashboard', 'home']):
            logger.info("✓ Successfully logged in!")
            
            # Extract cookies
            logger.info("🍪 Extracting cookies...")
            page_cookies = await page.cookies()
            cookies_dict = {c['name']: c['value'] for c in page_cookies}
            
            logger.info(f"✓ Extracted {len(cookies_dict)} cookies")
            
            # Close browser
            await browser.close()
            
            # Clean up session
            del ACTIVE_SESSIONS[session_id]
            
            return {
                'status': 'success',
                'message': 'Login successful',
                'cookies': cookies_dict
            }
        else:
            logger.error(f"Unexpected URL after verification: {current_url}")
            
            # Check for error messages on page
            error_text = await page.evaluate('document.body.innerText')
            if 'incorrect' in error_text.lower() or 'invalid' in error_text.lower():
                raise Exception("Verification code rejected. Please try again.")
            else:
                raise Exception(f"Unexpected page after verification: {current_url}")
    
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        try:
            await browser.close()
        except:
            pass
        if session_id in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[session_id]
        raise


def cleanup_expired_sessions():
    """Remove sessions older than 30 minutes"""
    now = time.time()
    expired = [sid for sid, sess in ACTIVE_SESSIONS.items() if now - sess['timestamp'] > 1800]
    for sid in expired:
        try:
            # Try to close browser
            browser = ACTIVE_SESSIONS[sid].get('browser')
            if browser:
                asyncio.run(browser.close())
        except:
            pass
        del ACTIVE_SESSIONS[sid]
    
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")
