import base64
import hashlib
import time

def checkSign(hash: str, secret: str, query: dict) -> bool:
    if not (s := query.get("s")) or not (e := query.get("e")):
        return False
    sign = (
        base64.urlsafe_b64encode(
            hashlib.sha1(f"{secret}{hash}{e}".encode()).digest()
        )
        .decode()
        .rstrip("=")
    )
    return sign == s and time.time() < int(e, 36)