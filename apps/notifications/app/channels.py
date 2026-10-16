"""Delivery channels besides in-app. In-app needs nothing: the row in notifications_notification is it.

Email and SMS go through a `Channel`. The built-in ones only log (dev, CI). To go live, write a class with
the same `send()` (e.g. SMTP, or an SMS gateway's HTTP API) and register it in `CHANNELS`.

What leaves the system is deliberately generic: no names, departments or times, because email and SMS are
not a safe place for health information. The full text stays behind the login.
"""
import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger("notifications.channels")

GENERIC_MESSAGE = "You have a new MediFlow notification. Sign in to view it."


@dataclass(frozen=True)
class Contact:
    email: str
    phone: str


class Channel(Protocol):
    name: str

    def address(self, contact: Contact) -> str: ...

    def send(self, to: str, message: str) -> None:
        """Raise on failure."""


def _mask(value: str) -> str:
    return value[:2] + "***" if len(value) > 2 else "***"


class LogEmail:
    name = "email"

    def address(self, contact: Contact) -> str:
        return contact.email

    def send(self, to: str, message: str) -> None:
        log.info("email to %s: %s", _mask(to), message)


class LogSMS:
    name = "sms"

    def address(self, contact: Contact) -> str:
        return contact.phone

    def send(self, to: str, message: str) -> None:
        log.info("sms to %s: %s", _mask(to), message)


CHANNELS: dict[str, type] = {"email": LogEmail, "sms": LogSMS}


def build(names: list[str]) -> list[Channel]:
    unknown = [n for n in names if n not in CHANNELS]
    if unknown:
        raise ValueError(f"unknown NOTIFY_CHANNELS: {', '.join(unknown)} (known: {', '.join(CHANNELS)})")
    return [CHANNELS[n]() for n in names]


def deliver(channel: Channel, contact: Contact) -> tuple[str, str]:
    """Returns (status, detail) for the notifications_delivery row."""
    to = channel.address(contact)
    if not to:
        return "skipped", f"no {channel.name} address"
    try:
        channel.send(to, GENERIC_MESSAGE)
    except Exception as exc:  # a provider failure must not stop in-app delivery
        log.warning("%s delivery failed: %s", channel.name, exc)
        return "failed", str(exc)[:200]
    return "sent", ""
