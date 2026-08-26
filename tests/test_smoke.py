def test_health_check_is_deterministic(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok", "service": "mock-store"}


def test_login_renders_dashboard_for_synthetic_customer(client):
    response = client.post(
        "/login",
        data={"username": "alice", "password": "user123"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Painel de pedidos" in response.get_data(as_text=True)
    assert "Alice Silva" in response.get_data(as_text=True)


def test_root_redirects_unauthenticated_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_root_redirects_authenticated_to_dashboard(logged_in_client):
    response = logged_in_client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"


def test_download_receipt_returns_content(logged_in_client):
    response = logged_in_client.get("/orders/receipt?file=receipt_default.txt")
    assert response.status_code == 200
    assert "MOCK STORE ENTERPRISE" in response.get_data(as_text=True)
