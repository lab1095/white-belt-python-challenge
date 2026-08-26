from __future__ import annotations


def login(client, username: str, password: str) -> None:
    response = client.post("/login", data={"username": username, "password": password})
    assert response.status_code == 302


def test_ticket_list_is_limited_by_account_and_uses_table(logged_in_client, client):
    customer_page = logged_in_client.get("/tickets")
    assert customer_page.status_code == 200
    customer_html = customer_page.get_data(as_text=True)
    assert "Número" in customer_html
    assert "Data de abertura" in customer_html
    assert "Assunto" in customer_html
    assert "Status" in customer_html
    assert "Ver mensagens" in customer_html
    assert customer_html.count('class="ticket-row"') == 2
    assert "Criar novo chamado" in customer_html

    login(client, "clara", "admin123")
    admin_page = client.get("/tickets")
    assert admin_page.status_code == 200
    admin_html = admin_page.get_data(as_text=True)
    assert admin_html.count('class="ticket-row"') == 3
    assert "Criar novo chamado" not in admin_html


def test_customer_and_admin_can_exchange_messages(logged_in_client, client):
    response = logged_in_client.get("/tickets/1")
    assert response.status_code == 200
    assert "Conversas do chamado" in response.get_data(as_text=True)

    message = "Mensagem enviada pelo cliente"
    response = logged_in_client.post("/tickets/1/messages", data={"message": message})
    assert response.status_code == 302

    login(client, "clara", "admin123")
    admin_page = client.get("/tickets/1")
    assert message in admin_page.get_data(as_text=True)
    response = client.post(
        "/tickets/1/messages",
        data={"message": "Resposta enviada pelo atendimento"},
    )
    assert response.status_code == 302

    customer_page = logged_in_client.get("/tickets/1")
    assert "Resposta enviada pelo atendimento" in customer_page.get_data(as_text=True)


def test_customer_cannot_view_another_customers_ticket(logged_in_client):
    response = logged_in_client.get("/tickets/3")
    assert response.status_code == 404


def test_admin_can_generate_summary_page(client, fake_summary_service):
    login(client, "clara", "admin123")

    response = client.get("/tickets/1")
    assert response.status_code == 200
    assert "Gerar resumo" in response.get_data(as_text=True)

    response = client.post("/tickets/1/summary")
    assert response.status_code == 200
    assert "Resultado" in response.get_data(as_text=True)


def test_message_api_respects_ticket_visibility(logged_in_client, client):
    response = logged_in_client.get("/api/tickets/1/messages")
    assert response.status_code == 200
    assert response.json["messages"]

    response = logged_in_client.get("/api/tickets/3/messages")
    assert response.status_code == 404

    login(client, "clara", "admin123")
    response = client.get("/api/tickets/3/messages")
    assert response.status_code == 200
