"""Runs the scheduled jobs (appointment reminders, long-delay notices, email/SMS retries) every minute.

Only one instance runs them at a time, even with several replicas: each holds a PostgreSQL advisory
lock for as long as it is the runner. Every notification has a dedupe key, so a job that runs twice
(or overlaps a restart) still notifies once.
"""
import logging
import threading
from zoneinfo import ZoneInfo

import psycopg

from . import store

LOCK_ID = 727_001  # any constant shared by all instances of this service
log = logging.getLogger("notifications.scheduler")


def run(database_url: str, tz: ZoneInfo, senders: list, stop: threading.Event, interval: float = 60.0) -> None:
    while not stop.is_set():
        try:
            with psycopg.connect(database_url, autocommit=True) as conn:
                if not conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,)).fetchone()[0]:
                    stop.wait(interval)  # another instance is the runner
                    continue
                log.info("running scheduled jobs every %.0fs", interval)
                while not stop.is_set():
                    try:
                        result = store.run_scheduled(conn, tz, senders)
                        if any(result.values()):
                            log.info("scheduled jobs: %s", result)
                    except psycopg.OperationalError:
                        raise
                    except Exception:
                        log.exception("scheduled jobs failed")
                    stop.wait(interval)
        except psycopg.OperationalError as exc:
            log.warning("database connection lost (%s); retrying", exc)
            stop.wait(min(interval, 30.0))


def start(database_url: str, tz: ZoneInfo, senders: list) -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=run, args=(database_url, tz, senders, stop), name="scheduler", daemon=True).start()
    return stop
