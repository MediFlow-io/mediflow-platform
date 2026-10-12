from django.test import TestCase
from django.urls import reverse
from rest_framework import status


class OpenAPIDocsTests(TestCase):
    def test_schema_endpoint(self):
        url = reverse('schema')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Content should contain OpenAPI spec keywords
        content = response.content.decode('utf-8')
        self.assertIn('openapi: 3.', content)
        self.assertIn('MediFlow API - Authentication', content)
        self.assertIn('/api/v1/auth/register/student/', content)
        self.assertIn('/api/v1/auth/register/staff/', content)
        self.assertIn('/api/v1/auth/login/', content)
        self.assertIn('/api/v1/auth/logout/', content)
        self.assertIn('/api/v1/auth/token/refresh/', content)
        self.assertIn('/api/v1/auth/change-password/', content)
        self.assertIn('jwtAuth', content)

    def test_swagger_ui_endpoint(self):
        url = reverse('swagger-ui')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode('utf-8')
        self.assertIn('swagger-ui', content.lower())

    def test_redoc_ui_endpoint(self):
        url = reverse('redoc')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode('utf-8')
        self.assertIn('redoc', content.lower())
