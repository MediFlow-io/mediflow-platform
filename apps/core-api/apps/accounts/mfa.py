"""Two-factor sign-in with an authenticator app (TOTP, RFC 6238).

Flow: the password is checked as usual; if the account has a confirmed authenticator, /api/auth/login
answers {mfa_required, mfa_token} instead of tokens. The mfa_token is signed, names the user and expires
after 5 minutes. /api/auth/mfa/verify exchanges it plus a current code for the usual tokens.

Staff enable it themselves (setup → confirm). MFA_REQUIRED_ROLES (e.g. "admin,doctor,nurse") makes it
mandatory: those accounts are told to set it up at sign-in and can't turn it off. Admins can reset a
lost authenticator.
"""
import base64
import time

import pyotp
import segno
from django.conf import settings
from django.core import signing
from django.db import transaction

from .models import TotpDevice, User

ISSUER = "MediFlow"
CHALLENGE_SALT = "mediflow.mfa.challenge"
CHALLENGE_SECONDS = 300


def required_for(user: User) -> bool:
    return user.role in settings.MFA_REQUIRED_ROLES


def enabled_for(user: User) -> bool:
    device = TotpDevice.objects.filter(user=user).first()
    return bool(device and device.confirmed_at)


def challenge_for(user: User) -> str:
    return signing.dumps({"u": user.pk}, salt=CHALLENGE_SALT)


def user_from_challenge(token: str) -> User | None:
    try:
        data = signing.loads(token, salt=CHALLENGE_SALT, max_age=CHALLENGE_SECONDS)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    return User.objects.filter(pk=data.get("u"), is_active=True).first()


def start_setup(user: User) -> dict:
    """A new secret (replacing any unconfirmed one) with its otpauth URI and a QR code."""
    secret = pyotp.random_base32()
    TotpDevice.objects.update_or_create(user=user, defaults={"secret": secret, "confirmed_at": None, "last_step": 0})
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name=ISSUER)
    svg = segno.make(uri, error="m").svg_inline(scale=4, border=2)
    return {"secret": secret, "otpauthUri": uri,
            "qrSvg": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()}


def check_code(device: TotpDevice, code: str) -> bool:
    """True for a current code (±30 s for clock drift) that hasn't been used before."""
    code = "".join(ch for ch in str(code) if ch.isdigit())
    if len(code) != 6:
        return False
    totp = pyotp.TOTP(device.secret)
    now = int(time.time())
    with transaction.atomic():
        fresh = TotpDevice.objects.select_for_update().get(pk=device.pk)
        for drift in (-1, 0, 1):
            moment = now + drift * totp.interval
            step = moment // totp.interval
            if step > fresh.last_step and totp.at(moment) == code:
                fresh.last_step = step
                fresh.save(update_fields=["last_step"])
                device.last_step = step
                return True
    return False
