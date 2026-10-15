from django.test import TestCase


class MetricsTests(TestCase):
    def test_metrics_endpoint_exposes_request_counters(self):
        self.client.get("/api/health")
        body = self.client.get("/metrics").content.decode()
        self.assertIn("django_http_requests_total_by_view_transport_method_total", body)
        self.assertIn("django_http_responses_total_by_status_total", body)
