"""
Base test case classes.

Use these instead of Django's TestCase or APITestCase directly so we can
add project-wide helpers (e.g., assert_error_code, assert_paginated) once
and have them everywhere.

pytest-style tests (plain functions with fixtures) are preferred for new code.
These classes exist for cases where class-based organisation genuinely helps
(e.g., a large view test with shared setUp logic).
"""

from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status


class BaseTestCase(TestCase):
    """
    Base for non-API Django tests.
    Wraps each test in a transaction that is rolled back after the test.
    """


class BaseAPITestCase(APITestCase):
    """
    Base for DRF API tests.

    Usage:
        class TestMyEndpoint(BaseAPITestCase):
            def setUp(self):
                self.player = PlayerUserFactory()
                self.authenticate(self.player)

            def test_something(self):
                response = self.client.get("/api/...")
                self.assert_ok(response)
    """

    def authenticate(self, user):
        """Force-authenticate the test client as ``user``."""
        self.client.force_authenticate(user=user)

    def deauthenticate(self):
        """Remove authentication from the test client."""
        self.client.force_authenticate(user=None)

    # ── Response assertion helpers ──────────────────────────────────────────

    def assert_ok(self, response):
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def assert_created(self, response):
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def assert_no_content(self, response):
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def assert_bad_request(self, response):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def assert_unauthorized(self, response):
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, response.data)

    def assert_forbidden(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    def assert_not_found(self, response):
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.data)

    def assert_field_error(self, response, field):
        """Assert that ``field`` appears in the validation error response."""
        self.assert_bad_request(response)
        self.assertIn(field, response.data, f"Expected error on field '{field}', got: {response.data}")

    def assert_paginated(self, response, *, count=None):
        """Assert the response is a paginated list and optionally check total count."""
        self.assert_ok(response)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        if count is not None:
            self.assertEqual(response.data["count"], count)
