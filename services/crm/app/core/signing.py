"""Callback authentication.

`/receipts` is the one endpoint a stranger on the internet could POST to in order
to fake delivery/open stats. We defend it with an HMAC-SHA256 signature over the
raw body using a shared secret. The channel service signs; the CRM verifies in
constant time. No valid signature -> 401, the event never touches the log.
"""

from __future__ import annotations

import hashlib
import hmac


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify(body: bytes, signature: str, secret: str) -> bool:
    expected = sign(body, secret)
    # compare_digest avoids leaking timing information about the secret.
    return hmac.compare_digest(expected, signature or "")
