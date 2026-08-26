def test_customer_can_list_own_orders(logged_in_client):
    response = logged_in_client.get("/api/orders")

    assert response.status_code == 200
    assert [order["order_number"] for order in response.json["orders"]] == ["ORD-1001", "ORD-1003"]


def test_customer_can_view_dashboard_and_tickets(logged_in_client):
    dashboard = logged_in_client.get("/dashboard")
    tickets = logged_in_client.get("/api/tickets")

    assert dashboard.status_code == 200
    assert "Pedidos recentes" in dashboard.get_data(as_text=True)
    assert tickets.status_code == 200
    assert len(tickets.json["tickets"]) == 2


def test_admin_can_list_all_orders(client):
    response = client.post(
        "/login",
        data={"username": "clara", "password": "admin123"},
    )

    assert response.status_code == 302
    response = client.get("/api/orders")

    assert response.status_code == 200
    assert len(response.json["orders"]) == 24


def test_admin_can_generate_summary_api(client, fake_summary_service):
    login_response = client.post(
        "/login",
        data={"username": "clara", "password": "admin123"},
    )
    assert login_response.status_code == 302
    response = client.post("/api/tickets/1/summary")

    assert response.status_code == 200
    assert response.json["ticket_id"] == 1
    assert "summary" in response.json
    assert set(response.json) == {"ticket_id", "summary"}


def test_customer_cannot_generate_summary_api(logged_in_client):
    response = logged_in_client.post("/api/tickets/1/summary")

    assert response.status_code == 403
