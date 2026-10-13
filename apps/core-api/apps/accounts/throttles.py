from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """Limits login attempts per (client IP, username).

    Keyed on both so one person guessing passwords is stopped, while many students
    behind the same campus NAT address can still sign in.
    """
    scope = "login"

    def get_cache_key(self, request, view):
        data = request.data if hasattr(request, "data") else {}
        username = str(data.get("staffId") or data.get("username") or data.get("unique_id") or data.get("email") or "")
        return self.cache_format % {"scope": self.scope, "ident": f"{self.get_ident(request)}:{username.lower()[:150]}"}


class RegisterRateThrottle(SimpleRateThrottle):
    """Limits public account creation per client IP."""
    scope = "register"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
