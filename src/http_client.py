import requests
import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def get(url: str, headers: Optional[dict]=None, etag: Optional[str]=None, last_modified: Optional[str]=None, retries: int=3, timeout: int=15) -> Tuple[int, dict, str]:
    """Perform GET with optional conditional headers and retries. Returns (status_code, resp_headers, text_or_empty).

    If 304 Not Modified returned, text will be empty.
    """
    hdrs = headers.copy() if headers else {}
    if etag:
        hdrs['If-None-Match'] = etag
    if last_modified:
        hdrs['If-Modified-Since'] = last_modified
    last_exc = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=hdrs, timeout=timeout)
            return r.status_code, r.headers, (r.text if r.status_code != 304 else '')
        except Exception as e:
            last_exc = e
            logger.warning('GET %s failed (attempt %s): %s', url, attempt+1, e)
            time.sleep(1 + attempt)
    logger.error('GET %s failed after %s attempts: %s', url, retries, last_exc)
    return 0, {}, ''
