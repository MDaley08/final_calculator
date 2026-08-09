# tests/integration/test_main.py
"""
Integration tests for app/main.py, exercised through FastAPI's TestClient.

Unlike the e2e suite (tests/e2e), which spawns a real `uvicorn` subprocess and
talks to it over HTTP, TestClient runs the ASGI app in-process. That's what
lets coverage.py see which lines of app/main.py actually execute.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    # `with` triggers the lifespan context manager (startup/shutdown).
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client, fake_user_data) -> dict:
    """Register + log in a fresh user, returning Bearer auth headers."""
    payload = {**fake_user_data, "confirm_password": fake_user_data["password"]}
    client.post("/auth/register", json=payload)
    response = client.post(
        "/auth/login",
        json={"username": fake_user_data["username"], "password": fake_user_data["password"]},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Web (HTML) routes
# ============================================================================
@pytest.mark.parametrize("path", [
    "/", "/login", "/register", "/dashboard",
    f"/dashboard/view/{uuid.uuid4()}", f"/dashboard/edit/{uuid.uuid4()}",
])
def test_html_pages(client, path):
    assert client.get(path).status_code == 200


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ============================================================================
# Registration & login
# ============================================================================
def test_register_success(client, fake_user_data):
    payload = {**fake_user_data, "confirm_password": fake_user_data["password"]}
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["username"] == fake_user_data["username"]


def test_register_duplicate_username_fails(client, fake_user_data):
    payload = {**fake_user_data, "confirm_password": fake_user_data["password"]}
    client.post("/auth/register", json=payload)
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400


@pytest.mark.parametrize("endpoint,build_body", [
    ("/auth/login", lambda u: {"json": {"username": u["username"], "password": u["password"]}}),
    ("/auth/token", lambda u: {"data": {"username": u["username"], "password": u["password"]}}),
])
def test_login_success(client, fake_user_data, endpoint, build_body):
    payload = {**fake_user_data, "confirm_password": fake_user_data["password"]}
    client.post("/auth/register", json=payload)
    response = client.post(endpoint, **build_body(fake_user_data))
    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.parametrize("endpoint", ["/auth/login", "/auth/token"])
def test_login_invalid_credentials(client, fake_user_data, endpoint):
    payload = {**fake_user_data, "confirm_password": fake_user_data["password"]}
    client.post("/auth/register", json=payload)
    bad_creds = {"username": fake_user_data["username"], "password": "wrong-password"}
    kwarg = "json" if endpoint == "/auth/login" else "data"
    response = client.post(endpoint, **{kwarg: bad_creds})
    assert response.status_code == 401


# ============================================================================
# Calculations (BREAD)
# ============================================================================
def create_calc(client, auth_headers, inputs=(1, 2)):
    return client.post(
        "/calculations",
        json={"type": "addition", "inputs": list(inputs)},
        headers=auth_headers,
    ).json()


def test_create_calculation_success(client, auth_headers):
    response = client.post(
        "/calculations", json={"type": "addition", "inputs": [1, 2, 3]}, headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["result"] == 6


def test_create_calculation_rejects_invalid_input(client, auth_headers):
    response = client.post(
        "/calculations", json={"type": "division", "inputs": [10, 0]}, headers=auth_headers
    )
    assert response.status_code >= 400


def test_list_calculations(client, auth_headers):
    create_calc(client, auth_headers)
    response = client.get("/calculations", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_calculation_success(client, auth_headers):
    created = create_calc(client, auth_headers)
    response = client.get(f"/calculations/{created['id']}", headers=auth_headers)
    assert response.status_code == 200


def test_update_calculation_recomputes_result(client, auth_headers):
    created = create_calc(client, auth_headers)
    response = client.put(
        f"/calculations/{created['id']}", json={"inputs": [10, 20]}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["result"] == 30


def test_update_calculation_without_inputs_keeps_result(client, auth_headers):
    created = create_calc(client, auth_headers)
    response = client.put(f"/calculations/{created['id']}", json={}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["result"] == created["result"]


def test_delete_calculation(client, auth_headers):
    created = create_calc(client, auth_headers)
    assert client.delete(f"/calculations/{created['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/calculations/{created['id']}", headers=auth_headers).status_code == 404


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_calculation_invalid_id_format(client, auth_headers, method):
    kwargs = {"json": {"inputs": [1, 2]}} if method == "put" else {}
    response = getattr(client, method)("/calculations/not-a-uuid", headers=auth_headers, **kwargs)
    assert response.status_code == 400


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_calculation_not_found(client, auth_headers, method):
    kwargs = {"json": {"inputs": [1, 2]}} if method == "put" else {}
    response = getattr(client, method)(f"/calculations/{uuid.uuid4()}", headers=auth_headers, **kwargs)
    assert response.status_code == 404
