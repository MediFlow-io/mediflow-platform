"""MediFlow notification service (Flask).

Owns in-app notifications: it listens for patient-flow events, writes notifications for the people they
concern, and serves each signed-in user their own. See README.md.
"""
import logging
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, request
from psycopg_pool import ConnectionPool

from . import channels, listener, store
from .auth import AuthError, Verifier
from .config import Settings

PAGE_SIZE, MAX_PAGE_SIZE = 30, 100


def create_app(settings: Settings | None = None, verifier: Verifier | None = None) -> Flask:
    settings = settings or Settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = Flask(__name__)
    app.json.sort_keys = False
    tz = ZoneInfo(settings.time_zone)
    senders = channels.build(settings.channels)
    pool = ConnectionPool(settings.database_url, min_size=1, max_size=10, open=True,
                          kwargs={"autocommit": True}, name="notifications")
    verifier = verifier or Verifier(settings.jwks_url, settings.jwt_issuer, settings.jwt_audience)
    app.extensions["mediflow"] = {"pool": pool, "settings": settings}
    if settings.listen:
        app.extensions["mediflow"]["stop"] = listener.start(settings.database_url, tz, senders)

    def error(status: int, detail: str):
        return jsonify(detail=detail), status

    def signed_in(view):
        """Verifies the token and re-reads the account, so a deactivated user is refused at once."""
        def wrapper(*args, **kwargs):
            try:
                user_id = verifier.verify(request.headers.get("Authorization"))
            except AuthError as exc:
                return error(401, str(exc))
            with pool.connection() as conn:
                if not store.active_user(conn, user_id):
                    return error(401, "User is inactive or no longer exists.")
                g.user_id, g.conn = user_id, conn
                return view(*args, **kwargs)
        wrapper.__name__ = view.__name__
        return wrapper

    @app.get("/healthz")
    def health():
        try:
            with pool.connection() as conn:
                conn.execute("SELECT 1")
        except Exception:
            return error(503, "database unreachable")
        return jsonify(status="ok", channels=["in_app", *settings.channels])

    @app.get("/api/notifications")
    @signed_in
    def list_notifications():
        try:
            limit = min(max(int(request.args.get("limit", PAGE_SIZE)), 1), MAX_PAGE_SIZE)
            before = int(request.args["before"]) if request.args.get("before") else None
        except ValueError:
            return error(400, "limit and before must be whole numbers.")
        unread_only = request.args.get("unread") in ("1", "true")
        results = store.list_for(g.conn, g.user_id, unread_only=unread_only, limit=limit, before=before)
        return jsonify(results=results, unread=store.unread_count(g.conn, g.user_id))

    @app.get("/api/notifications/unread-count")
    @signed_in
    def unread():
        return jsonify(unread=store.unread_count(g.conn, g.user_id))

    @app.post("/api/notifications/<int:notification_id>/read")
    @signed_in
    def read_one(notification_id: int):
        if not store.mark_read(g.conn, g.user_id, notification_id):
            return error(404, "Not found.")
        return jsonify(unread=store.unread_count(g.conn, g.user_id))

    @app.post("/api/notifications/read-all")
    @signed_in
    def read_all():
        updated = store.mark_all_read(g.conn, g.user_id)
        return jsonify(updated=updated, unread=0)

    @app.errorhandler(404)
    def not_found(_):
        return error(404, "Not found.")

    @app.errorhandler(405)
    def not_allowed(_):
        return error(405, "Method not allowed.")

    @app.after_request
    def no_store(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app
