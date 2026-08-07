import requests
import logging
from pathlib import Path
from http.cookiejar import MozillaCookieJar, Cookie # Import necessary classes

# DISCLAIMER: 
# This script extracts cookies from a YouTube request. 
# By using this script, you are authorizing it to act on behalf of your account context.
# Ensure you are complying with YouTube's Terms of Service.

# --- CONFIGURATION ---
COOKIES_FILE_PATH = Path(__file__).parent.parent / 'cookies.txt'
YOUTUBE_URL = "https://www.youtube.com" # A general YouTube URL to fetch cookies from

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [COOKIE-UPDATER] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def update_cookies_file():
    logging.info(f"Attempting to fetch cookies from {YOUTUBE_URL} using requests...")
    try:
        # Use a session to persist cookies across potential redirects if any
        with requests.Session() as session:
            response = session.get(YOUTUBE_URL, timeout=30)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

            if not session.cookies:
                logging.warning("No cookies were received from the YouTube URL using requests.")
                return False

            # Create a MozillaCookieJar to save in Netscape format
            cj = MozillaCookieJar(str(COOKIES_FILE_PATH))
            for cookie in session.cookies:
                # requests cookie has different attributes than http.cookiejar.Cookie
                # We need to manually construct the Cookie object for MozillaCookieJar
                c = Cookie(
                    version=0,
                    name=cookie.name,
                    value=cookie.value,
                    port=None,
                    port_specified=False,
                    domain=cookie.domain,
                    domain_specified=bool(cookie.domain),
                    domain_initial_dot=cookie.domain.startswith('.'),
                    path=cookie.path,
                    path_specified=bool(cookie.path),
                    secure=cookie.secure,
                    expires=cookie.expires,
                    comment=None,
                    comment_url=None,
                    rest={'HttpOnly': cookie.httpOnly} if hasattr(cookie, 'httpOnly') else {},
                    # Infer discard based on expires: if expires is None, it's a session cookie
                    discard=True if cookie.expires is None else False,
                    rfc2109=False
                )
                cj.set_cookie(c)
            
            cj.save(ignore_discard=True, ignore_expires=True) # Save all cookies, including session ones
            
            logging.info(f"Successfully updated '{COOKIES_FILE_PATH}' with cookies from {YOUTUBE_URL} in Netscape format.")
            logging.warning("DISCLAIMER: While the cookie format is now correct, these cookies may still not be sufficient for authenticated YouTube sessions with yt-dlp due to YouTube's complex anti-bot measures. For more reliable results, consider using 'yt-dlp --cookies-from-browser CHROME' or exporting cookies from your browser.")
            return True

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch cookies using requests: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    logging.info("Starting YouTube cookies update script...")
    logging.warning("Usage of this script implies agreement to YouTube's Terms of Service.")
    if update_cookies_file():
        logging.info("Cookies update process finished.")
    else:
        logging.error("Cookies update process failed.")
