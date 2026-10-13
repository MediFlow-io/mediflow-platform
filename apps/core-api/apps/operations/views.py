from django.db import connection
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

class HealthView(APIView):
    """Liveness + database check for container health checks. Reveals nothing sensitive."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})
