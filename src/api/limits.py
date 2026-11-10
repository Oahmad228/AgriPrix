"""Per-client rate limiting (ENF-05): protects the public demo against abuse.

Every business route is decorated with ``@limited``. The SlowAPI *middleware* is not used:
with the FastAPI/Starlette versions pinned in requirements.lock it cannot resolve the route
of a request and silently exempts everything (found by tests/integration/test_api.py).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import get_settings

limiter = Limiter(key_func=get_remote_address)
limited = limiter.limit(get_settings().api_rate_limit)
