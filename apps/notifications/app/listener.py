"""Listens for patient-flow events (PostgreSQL LISTEN on `mediflow_visits`) and turns them into notifications.

Events are only delivered while connected, so anything published while this service is down is not
notified later. That is acceptable for "you've been called" messages, which are only useful in the moment.
"""
import json
import logging
import threading
from zoneinfo import ZoneInfo

import psycopg

from . import store

CHANNEL = "mediflow_visits"  # store.NotifyChannel in apps/patient-flow
log = logging.getLogger("notifications.listener")


def run(database_url: str, tz: ZoneInfo, senders: list, stop: threading.Event) -> None:
    delay = 1.0
    while not stop.is_set():
        try:
            with (psycopg.connect(database_url, autocommit=True) as listen_conn,
                  psycopg.connect(database_url, autocommit=True) as work):
                listen_conn.execute(f"LISTEN {CHANNEL}")
                log.info("listening on %s", CHANNEL)
                delay = 1.0
                while not stop.is_set():
                    for message in listen_conn.notifies(timeout=5.0):
                        handle(work, message.payload, tz, senders)
        except psycopg.OperationalError as exc:
            log.warning("database connection lost (%s); retrying in %.0fs", exc, delay)
            stop.wait(delay)
            delay = min(delay * 2, 30.0)


def handle(conn: psycopg.Connection, payload: str, tz: ZoneInfo, senders: list) -> None:
    try:
        event = json.loads(payload)
    except ValueError:
        log.warning("ignoring malformed event %r", payload[:200])
        return
    try:
        created = store.handle_event(conn, event, tz, senders)
    except psycopg.OperationalError:
        raise  # reconnect
    except Exception:
        log.exception("could not handle event %s", event)
        return
    if created:
        log.info("event %s -> %d notification(s)", event.get("action"), len(created))


def start(database_url: str, tz: ZoneInfo, senders: list) -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=run, args=(database_url, tz, senders, stop), name="event-listener", daemon=True).start()
    return stop


if __name__ == "__main__":  # python -m app.listener: run the listener on its own
    from . import channels
    from .config import Settings

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    try:
        run(settings.database_url, ZoneInfo(settings.time_zone), channels.build(settings.channels), threading.Event())
    except KeyboardInterrupt:
        pass
