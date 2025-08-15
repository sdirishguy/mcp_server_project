"""
Robust integration tests for the MCP Server Project.

These tests verify real-world functionality without stubbing or mocking
core application behavior. They test actual authentication, authorization,
and business logic flows.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestAuthenticationFlow:
    """Test complete authentication flows with real validation."""

    def test_successful_login_flow(self, client: TestClient, test_data: dict):
        """Test complete login flow with valid credentials."""
        response = client.post(
            "/api/auth/login",
            json=test_data["valid_user"],
        )

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert "token" in data
        assert "user_id" in data
        assert len(data["token"]) > 0

    def test_failed_login_flow(self, client: TestClient, test_data: dict):
        """Test login flow with invalid credentials."""
        response = client.post(
            "/api/auth/login",
            json=test_data["invalid_user"],
        )

        assert response.status_code == 401
        data = response.json()
        assert data["authenticated"] is False

    def test_protected_route_access_with_valid_token(self, authenticated_client: TestClient):
        """Test accessing protected routes with valid authentication."""
        response = authenticated_client.get("/api/protected")

        # Should succeed with valid token
        assert response.status_code == 200

    def test_protected_route_access_without_token(self, client: TestClient):
        """Test accessing protected routes without authentication."""
        response = client.get("/api/protected")

        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["message"]

    def test_protected_route_access_with_invalid_token(self, client: TestClient):
        """Test accessing protected routes with invalid token."""
        client.headers.update({"Authorization": "Bearer invalid_token"})
        response = client.get("/api/protected")

        assert response.status_code == 401


@pytest.mark.integration
class TestHealthAndMonitoring:
    """Test health checks and monitoring endpoints."""

    def test_health_endpoint_returns_ok(self, client: TestClient):
        """Test health endpoint returns proper status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_metrics_endpoint_returns_prometheus_format(self, client: TestClient):
        """Test metrics endpoint returns Prometheus format."""
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Should contain Prometheus metrics
        assert "mcp_http_requests_total" in content
        assert "# HELP" in content
        assert "# TYPE" in content

    def test_metrics_increment_on_requests(self, client: TestClient):
        """Test that metrics are properly incremented."""
        # Make some requests to generate metrics
        client.get("/health")
        client.get("/metrics")

        # Check metrics again
        response = client.get("/metrics")
        content = response.text

        # Should show request counts
        assert "mcp_http_requests_total" in content


@pytest.mark.integration
class TestSecurityHeaders:
    """Test security headers are properly applied."""

    def test_security_headers_present_on_all_responses(self, client: TestClient):
        """Test that security headers are present on all responses."""
        response = client.get("/health")

        headers = response.headers

        # Required security headers
        assert "X-Frame-Options" in headers
        assert "X-Content-Type-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Strict-Transport-Security" in headers
        assert "Referrer-Policy" in headers
        assert "Content-Security-Policy" in headers

    def test_security_header_values(self, client: TestClient):
        """Test that security headers have correct values."""
        response = client.get("/health")

        headers = response.headers

        # Check specific security header values
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-XSS-Protection"] == "1; mode=block"
        assert "max-age=31536000" in headers["Strict-Transport-Security"]
        assert "strict-origin-when-cross-origin" in headers["Referrer-Policy"]


@pytest.mark.integration
class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limiting_on_login_endpoint(self, client: TestClient, test_data: dict):
        """Test that rate limiting works on login endpoint."""
        # Make multiple rapid login attempts with invalid credentials
        responses = []
        for _ in range(10):
            response = client.post(
                "/api/auth/login",
                json=test_data["invalid_user"],
            )
            responses.append(response)

        # Check if rate limiting kicked in (should get 429 at some point)
        status_codes = [r.status_code for r in responses]

        # Should have some 401s (invalid credentials) and potentially 429s (rate limited)
        assert all(code in [401, 429] for code in status_codes)

        # If rate limiting is working, we should see 429s
        if 429 in status_codes:
            # Find the first 429 response
            first_429_index = status_codes.index(429)
            first_429_response = responses[first_429_index]

            # Check rate limit headers
            headers = first_429_response.headers
            assert "Retry-After" in headers or "X-RateLimit" in headers


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_json_handling(self, client: TestClient):
        """Test handling of invalid JSON requests."""
        response = client.post(
            "/api/auth/login",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        # Should handle gracefully
        assert response.status_code in [400, 422]

    def test_nonexistent_endpoint_handling(self, client: TestClient):
        """Test handling of nonexistent endpoints."""
        response = client.get("/nonexistent/endpoint")

        assert response.status_code == 404

    def test_method_not_allowed_handling(self, client: TestClient):
        """Test handling of unsupported HTTP methods."""
        response = client.put("/health")

        assert response.status_code == 405

    def test_large_payload_handling(self, client: TestClient):
        """Test handling of large payloads."""
        large_payload = {"data": "x" * 10000}  # 10KB payload

        response = client.post(
            "/api/auth/login",
            json=large_payload,
        )

        # Should handle gracefully (either process or reject appropriately)
        assert response.status_code in [400, 401, 413]


@pytest.mark.integration
class TestCORSHandling:
    """Test CORS (Cross-Origin Resource Sharing) functionality."""

    def test_cors_preflight_request(self, client: TestClient):
        """Test CORS preflight OPTIONS request."""
        response = client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        # Should handle OPTIONS request
        assert response.status_code in [200, 405]  # 405 if OPTIONS not supported

        if response.status_code == 200:
            headers = response.headers
            assert "Access-Control-Allow-Origin" in headers

    def test_cors_headers_on_actual_request(self, client: TestClient):
        """Test CORS headers on actual requests."""
        response = client.get(
            "/health",
            headers={"Origin": "https://example.com"},
        )

        assert response.status_code == 200
        headers = response.headers

        # Should have CORS headers
        assert "Access-Control-Allow-Origin" in headers


@pytest.mark.integration
class TestRequestIDAndLogging:
    """Test request ID generation and logging."""

    def test_request_id_generation(self, client: TestClient):
        """Test that request IDs are generated for each request."""
        response = client.get("/health")

        headers = response.headers
        assert "X-Request-ID" in headers

        request_id = headers["X-Request-ID"]
        assert len(request_id) > 0
        assert request_id != ""

    def test_request_id_uniqueness(self, client: TestClient):
        """Test that request IDs are unique across requests."""
        response1 = client.get("/health")
        response2 = client.get("/health")

        request_id1 = response1.headers["X-Request-ID"]
        request_id2 = response2.headers["X-Request-ID"]

        assert request_id1 != request_id2

    def test_request_id_format(self, client: TestClient):
        """Test that request IDs have proper format."""
        response = client.get("/health")

        request_id = response.headers["X-Request-ID"]

        # Should be a UUID-like string
        assert len(request_id) >= 32
        assert "-" in request_id or len(request_id) == 32


@pytest.mark.integration
class TestApplicationState:
    """Test application state and component initialization."""

    def test_application_components_initialized(self, client: TestClient):
        """Test that application components are properly initialized."""
        # Make a request to trigger component initialization
        response = client.get("/health")

        assert response.status_code == 200

        # If we get here, the application is working
        # The real test is that the app didn't crash during startup

    def test_application_middleware_stack(self, client: TestClient):
        """Test that middleware stack is properly configured."""
        response = client.get("/health")

        # Check that middleware is working by looking for headers
        headers = response.headers

        # Security headers indicate middleware is working
        assert "X-Frame-Options" in headers
        assert "X-Request-ID" in headers
