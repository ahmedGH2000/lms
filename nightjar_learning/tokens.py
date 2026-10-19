import base64, hashlib, hmac, json, re, time
from pathlib import Path

ASSET = re.compile(r"[a-f0-9]{32}\Z")
FILE = re.compile(r"(?:index\.m3u8|key\.bin|segment_[0-9]{5}\.ts)\Z")


def key(secret):
    if not secret or len(secret.encode()) < 32:
        raise ValueError("Signing secret must have at least 32 bytes")
    return secret.encode()


def enc(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def issue(secret, *, member, session, lesson, asset, now=None):
    now = int(time.time() if now is None else now)
    payload = enc(
        json.dumps(
            dict(
                u=member,
                s=hashlib.sha256(session.encode()).hexdigest(),
                l=lesson,
                a=asset,
                iat=now,
                exp=now + 300,
                v=1,
            ),
            separators=(",", ":"),
        ).encode()
    )
    return (
        payload
        + "."
        + enc(hmac.new(key(secret), payload.encode(), hashlib.sha256).digest())
    )


def verify(secret, token, *, member, session, now=None):
    if not isinstance(token, str) or len(token) > 4096:
        raise ValueError("Invalid token")
    try:
        payload, sig = token.split(".")
        if not hmac.compare_digest(
            sig, enc(hmac.new(key(secret), payload.encode(), hashlib.sha256).digest())
        ):
            raise ValueError("Invalid signature")
        d = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        now = int(time.time() if now is None else now)
        if (
            d["v"] != 1
            or d["u"] != member
            or d["s"] != hashlib.sha256(session.encode()).hexdigest()
            or d["exp"] <= now
            or d["iat"] > now + 10
            or d["exp"] - d["iat"] > 300
            or not ASSET.fullmatch(d["a"])
        ):
            raise ValueError("Expired or mismatched token")
        return d
    except (KeyError, TypeError, UnicodeError) as e:
        raise ValueError("Invalid token") from e


def safe_path(root, asset, filename):
    if not ASSET.fullmatch(asset) or not FILE.fullmatch(filename):
        raise ValueError("Invalid path")
    root = Path(root).resolve(strict=True)
    target = (root / asset / filename).resolve(strict=True)
    if target.parent != root / asset or not target.is_file():
        raise ValueError("Invalid path")
    return target
