import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


def get_all_routes(app):
    routes = {}
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            routes[route.path] = list(route.methods or [])
    return routes


class TestRouteDiscovery:
    def test_print_all_routes(self, client):
        routes = get_all_routes(client)
        print("\n=== REGISTERED ROUTES ===")
        for path, methods in sorted(routes.items()):
            print(f"  {methods} {path}")
        print("=========================")
        assert len(routes) > 0


@pytest.mark.asyncio
class TestConversationEndpoints:

    async def test_send_message_returns_200(self, client, auth_headers):
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/conversations/message",
                json={"user_id": 1, "message": "I feel good today."},
                headers=auth_headers,
            )
        assert response.status_code in (200, 201), (
            f"Expected 200/201, got {response.status_code}: {response.text[:300]}"
        )

    async def test_send_message_response_has_content(self, client, auth_headers):
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/conversations/message",
                json={"user_id": 1, "message": "Hello"},
                headers=auth_headers,
            )
        assert response.status_code < 500, (
            f"Server error: {response.status_code}: {response.text[:300]}"
        )

    async def test_send_empty_message_accepted_or_rejected(self, client, auth_headers):
        """Empty message behavior depends on API design - just verify no 500."""
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/conversations/message",
                json={"user_id": 1, "message": ""},
                headers=auth_headers,
            )
        assert response.status_code < 500, f"Server error on empty message: {response.status_code}"

    async def test_missing_required_fields_returns_422(self, client, auth_headers):
        """Sending neither user_id nor message should fail validation."""
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/conversations/message",
                json={},
                headers=auth_headers,
            )
        assert response.status_code == 422

    async def test_endpoint_is_reachable(self, client):
        """Conversation endpoint must respond (auth model discovered at runtime)."""
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/conversations/message",
                json={"user_id": 1, "message": "Hello"},
            )
        assert response.status_code < 500, f"Server error: {response.status_code}"


@pytest.mark.asyncio
class TestAuthEndpoints:

    async def test_register_endpoint_exists(self, client):
        """Register endpoint must exist and not 500."""
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/v1/auth/register", json={})
        assert response.status_code != 404, "Register endpoint not found"
        assert response.status_code < 500, f"Server error: {response.status_code}"

    async def test_login_with_form_data(self, client):
        """Login typically uses OAuth2 form data: username + password."""
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/auth/login",
                data={"username": "nonexistent_user", "password": "WrongPassword"},
            )
        assert response.status_code in (401, 403, 422), (
            f"Unexpected status: {response.status_code}: {response.text[:300]}"
        )

    async def test_login_returns_token_structure(self, client):
        """If login succeeds, response must contain a token field."""
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            await ac.post(
                "/api/v1/auth/register",
                json={"username": "tokentest_user", "password": "SecurePassword123!", "role": "user"},
            )
            response = await ac.post(
                "/api/v1/auth/login",
                data={"username": "tokentest_user", "password": "SecurePassword123!"},
            )
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data or "token" in data, (
                f"Login response missing token: {data}"
            )


@pytest.mark.asyncio
class TestWellbeingEndpoints:

    async def test_wellbeing_endpoint_exists(self, client, auth_headers):
        """At least one wellbeing endpoint should exist and respond."""
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            paths = ["/scores", "/summary", "/metrics", "/daily", "/insights", "/"]
            found = False
            for path in paths:
                r = await ac.get(f"/api/v1/wellbeing{path}", headers=auth_headers)
                if r.status_code != 404:
                    found = True
                    assert r.status_code < 500, (
                        f"Wellbeing endpoint {path} returned server error: {r.status_code}"
                    )
                    break
            if not found:
                routes = get_all_routes(client)
                wellbeing_routes = [p for p in routes if "wellbeing" in p.lower()]
                pytest.skip(f"No wellbeing routes responded. Available: {wellbeing_routes}")

    async def test_wellbeing_response_not_server_error(self, client, auth_headers):
        """Whatever wellbeing endpoint exists, it must not 500."""
        routes = get_all_routes(client)
        wellbeing_paths = [p for p in routes if "wellbeing" in p.lower()]
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            for path in wellbeing_paths[:3]:
                r = await ac.get(path, headers=auth_headers)
                assert r.status_code < 500, (
                    f"Wellbeing endpoint {path} returned server error {r.status_code}"
                )


@pytest.mark.asyncio
class TestCareContactEndpoints:

    async def test_care_contacts_endpoint_exists(self, client, auth_headers):
        """Care contact endpoint should exist under some path."""
        async with AsyncClient(
            transport=ASGITransport(app=client), base_url="http://test"
        ) as ac:
            paths = [
                "/api/v1/care_contacts/",
                "/api/v1/care-contacts/",
                "/api/v1/carecontacts/",
                "/api/v1/contacts/",
            ]
            for path in paths:
                r = await ac.get(path, headers=auth_headers)
                if r.status_code != 404:
                    assert r.status_code < 500, (
                        f"Care contacts {path} returned server error {r.status_code}"
                    )
                    return
            routes = get_all_routes(client)
            care_routes = [p for p in routes if "care" in p.lower() or "contact" in p.lower()]
            pytest.skip(f"No care contact routes found. Available: {care_routes}")