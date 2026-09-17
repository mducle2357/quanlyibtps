from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiting on login (prompt §31) to slow down credential-stuffing attempts.
limiter = Limiter(key_func=get_remote_address)
