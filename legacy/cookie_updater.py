import requests
import os
from pathlib import Path
from http.cookiejar import MozillaCookieJar, Cookie

# --- CONFIGURATION ---
YOUTUBE_URL = "https://www.youtube.com"

def update_cookies_file():
    """
    Fetches fresh cookies from YouTube using the requests library
    and saves them to cookies.txt in the Netscape format.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookies_path = os.path.join(project_root, 'cookies.txt')

    print("\n" + "~"*40)
    print(" PRE-FLIGHT: UPDATING COOKIES")
    print("~"*40)
    print(f"Fetching fresh cookies from {YOUTUBE_URL}...")

    try:
        # Use a session to persist cookies across potential redirects
        with requests.Session() as session:
            response = session.get(YOUTUBE_URL, timeout=30)
            response.raise_for_status()

            if not session.cookies:
                print("Warning: No cookies were received from YouTube.")
                return False

            # Create a MozillaCookieJar to save in Netscape format
            cj = MozillaCookieJar(cookies_path)
            for cookie in session.cookies:
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
                    discard=True if cookie.expires is None else False,
                    rfc2109=False
                )
                cj.set_cookie(c)
            
            cj.save(ignore_discard=True, ignore_expires=True)
            print(f"Success! Updated '{cookies_path}'.")
            return True

    except requests.exceptions.RequestException as e:
        print(f"Error fetching cookies: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False
