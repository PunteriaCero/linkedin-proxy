"""
LinkedIn Voyager API Helper Functions

Direct HTTP implementation for LinkedIn Voyager API
Handles session management, cookies, and headers correctly
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)


def create_voyager_session(
    li_at: str, 
    jsessionid: str, 
    bcookie: str = "", 
    lidc: str = "",
    user_match_history: str = "",
    aam_uuid: str = ""
) -> requests.Session:
    """
    Create a requests.Session configured for LinkedIn Voyager API
    
    Session automatically handles:
    - Cookie management
    - Cookie renewal on Set-Cookie headers
    - Proper retries on connection errors
    - Timeout management
    
    Args:
        li_at: Authentication cookie (required)
        jsessionid: Session ID cookie (required)
        bcookie: Browser cookie (optional but recommended)
        lidc: Data center cookie (optional but recommended)
        user_match_history: Tracking cookie (optional)
        aam_uuid: Audience Manager UUID (optional)
    
    Returns:
        requests.Session configured and ready for Voyager API calls
    """
    
    logger.info("🚀 Creating Voyager session...")
    
    # Create session
    session = requests.Session()
    
    # Set cookies - requests.Session will auto-manage renewal
    logger.info(f"Setting cookies: li_at ({len(li_at)} chars), JSESSIONID ({len(jsessionid)} chars)")
    session.cookies.set('li_at', li_at)
    session.cookies.set('JSESSIONID', jsessionid)
    
    if bcookie:
        session.cookies.set('bcookie', bcookie)
        logger.info("✓ bcookie set")
    
    if lidc:
        session.cookies.set('lidc', lidc)
        logger.info("✓ lidc set")
    
    if user_match_history:
        session.cookies.set('UserMatchHistory', user_match_history)
        logger.info("✓ UserMatchHistory set")
    
    if aam_uuid:
        session.cookies.set('aam_uuid', aam_uuid)
        logger.info("✓ aam_uuid set")
    
    # Set headers - makes request look like normal browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/vnd.linkedin.normalized+json+2.1',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json',
        'Csrf-Token': jsessionid.strip('"'),  # LinkedIn expects csrf-token header
        'X-Requested-With': 'XMLHttpRequest',
        'X-RestLi-Protocol-Version': '2.0.0',
        'Referer': 'https://www.linkedin.com/messaging/thread/2-YWJjZWY=',  # Normal referer
        'Origin': 'https://www.linkedin.com'
    })
    
    logger.info("✓ Headers configured")
    
    # Configure automatic retries for resilience
    # This handles transient network issues gracefully
    retry_strategy = Retry(
        total=3,  # Max 3 retries
        backoff_factor=1,  # 1s, 2s, 4s delays between retries
        status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
        allowed_methods=["GET", "POST", "PUT", "DELETE"]  # Don't retry body-based methods by default
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    logger.info("✓ Retry strategy configured (3 retries, exponential backoff)")
    logger.info("✅ Voyager session created successfully")
    
    return session


def get_profile_voyager(session: requests.Session) -> dict:
    """
    Get current user's profile from Voyager API
    
    Args:
        session: requests.Session from create_voyager_session()
    
    Returns:
        dict with profile data: firstName, lastName, occupation, etc.
    
    Raises:
        Exception: If API call fails
    """
    
    logger.info("📋 Fetching profile from Voyager...")
    
    try:
        response = session.get(
            'https://www.linkedin.com/voyager/api/me',
            timeout=30,
            allow_redirects=False  # 🔥 CRITICAL: Don't follow redirects
        )
        
        logger.info(f"Voyager /me response: {response.status_code}")
        
        if response.status_code == 200:
            profile = response.json()
            
            # Extract useful info
            mini_profile = profile.get('miniProfile', {})
            first_name = mini_profile.get('firstName', 'Unknown')
            last_name = mini_profile.get('lastName', '')
            
            logger.info(f"✓ Profile retrieved: {first_name} {last_name}")
            logger.debug(f"Full profile: {profile}")
            
            return profile
        
        elif response.status_code == 302:
            logger.error("❌ 302 Redirect - Session invalid or cookies expired")
            logger.debug(f"Redirect to: {response.headers.get('Location', 'Unknown')}")
            raise Exception("Sesión inválida (302 Redirect). Cookies expiradas o rechazadas por LinkedIn.")
        
        elif response.status_code == 401:
            logger.error("❌ 401 Unauthorized - Cookies expired or invalid")
            raise Exception("Cookies expiradas o inválidas (401 Unauthorized)")
        
        elif response.status_code == 403:
            logger.error("❌ 403 Forbidden - Access denied")
            raise Exception("Acceso denegado (403 Forbidden)")
        
        elif response.status_code == 429:
            logger.error("❌ 429 Too Many Requests - Rate limited")
            raise Exception("Rate limit alcanzado (429). Intenta más tarde.")
        
        else:
            logger.error(f"❌ Voyager error: {response.status_code}")
            logger.debug(f"Response: {response.text[:500]}")
            raise Exception(f"Voyager API error: {response.status_code}")
    
    except requests.exceptions.Timeout:
        logger.error("⏱️ Timeout connecting to LinkedIn")
        raise Exception("Timeout conectando a LinkedIn. Verifica tu conexión.")
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"🔌 Connection error: {e}")
        raise Exception("Error de conexión. Verifica tu internet y prueba VPN.")
    
    except Exception as e:
        logger.error(f"❌ Error en get_profile_voyager: {e}")
        raise


def get_conversations_voyager(session: requests.Session, limit: int = 50) -> dict:
    """
    Get messaging conversations from Voyager API
    
    Args:
        session: requests.Session from create_voyager_session()
        limit: Number of conversations to fetch (default 50)
    
    Returns:
        dict with conversations list
    
    Raises:
        Exception: If API call fails
    """
    
    logger.info(f"💬 Fetching conversations (limit={limit})...")
    
    try:
        response = session.get(
            f'https://www.linkedin.com/voyager/api/messaging/conversations?keyVersion=LEGACY_INBOX&count={limit}',
            timeout=30,
            allow_redirects=False  # 🔥 Don't follow redirects
        )
        
        logger.info(f"Voyager /conversations response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            conversations = data.get('elements', [])
            logger.info(f"✓ Retrieved {len(conversations)} conversations")
            return data
        
        elif response.status_code == 302:
            raise Exception("Sesión inválida (302). Regenera cookies.")
        
        elif response.status_code == 401:
            raise Exception("Cookies expiradas (401)")
        
        elif response.status_code == 429:
            raise Exception("Rate limit (429)")
        
        else:
            raise Exception(f"Conversations error: {response.status_code}")
    
    except requests.exceptions.Timeout:
        raise Exception("Timeout conectando a LinkedIn")
    
    except requests.exceptions.ConnectionError:
        raise Exception("Error de conexión")
    
    except Exception as e:
        logger.error(f"❌ Error en get_conversations_voyager: {e}")
        raise


def get_conversation_messages(session: requests.Session, conversation_id: str, limit: int = 50) -> dict:
    """
    Get messages from a specific conversation
    
    Args:
        session: requests.Session from create_voyager_session()
        conversation_id: Conversation ID (e.g., "2-YWJjZWY=")
        limit: Number of messages to fetch (default 50)
    
    Returns:
        dict with messages array
    """
    
    logger.info(f"📨 Fetching messages from conversation {conversation_id}...")
    
    try:
        response = session.get(
            f'https://www.linkedin.com/voyager/api/messaging/conversations/{conversation_id}/events?direction=AFTER&start=0&count={limit}',
            timeout=30,
            allow_redirects=False  # 🔥 Don't follow redirects
        )
        
        if response.status_code == 200:
            return response.json()
        
        elif response.status_code == 302:
            raise Exception("Sesión inválida (302). Regenera cookies.")
        
        elif response.status_code == 401:
            raise Exception("Cookies expiradas (401)")
        
        else:
            raise Exception(f"Messages error: {response.status_code}")
    
    except Exception as e:
        logger.error(f"❌ Error fetching messages: {e}")
        raise


def send_message_voyager(
    session: requests.Session, 
    conversation_id: str, 
    message_text: str
) -> dict:
    """
    Send a message in a conversation
    
    Args:
        session: requests.Session from create_voyager_session()
        conversation_id: Conversation ID
        message_text: Message content
    
    Returns:
        dict with response data
    """
    
    logger.info(f"📤 Sending message to conversation {conversation_id}...")
    
    try:
        payload = {
            "body": message_text,
            "attachments": []
        }
        
        response = session.post(
            f'https://www.linkedin.com/voyager/api/messaging/conversations/{conversation_id}/events',
            json=payload,
            timeout=30,
            allow_redirects=False  # 🔥 Don't follow redirects
        )
        
        logger.info(f"Send message response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            logger.info("✓ Message sent successfully")
            return response.json()
        
        elif response.status_code == 302:
            raise Exception("Sesión inválida (302). Regenera cookies.")
        
        elif response.status_code == 401:
            raise Exception("Cookies expiradas (401)")
        
        elif response.status_code == 429:
            raise Exception("Rate limit (429)")
        
        else:
            logger.error(f"Send failed: {response.status_code}")
            raise Exception(f"Send message error: {response.status_code}")
    
    except Exception as e:
        logger.error(f"❌ Error sending message: {e}")
        raise


def extract_cookies_from_session(session: requests.Session) -> dict:
    """
    Extract cookies from session (for saving after they're renewed)
    
    Args:
        session: requests.Session
    
    Returns:
        dict with current cookie values
    """
    
    cookies = {}
    for key, value in session.cookies.items():
        cookies[key] = value
    
    logger.debug(f"Extracted cookies: {list(cookies.keys())}")
    return cookies
