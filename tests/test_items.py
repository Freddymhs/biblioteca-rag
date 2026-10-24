def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_items_empty(client):
    response = client.get("/api/items/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_item(client):
    response = client.post("/api/items/", json={"title": "Buy milk"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Buy milk"
    assert data["description"] is None
    assert "id" in data


def test_create_item_with_description(client):
    response = client.post(
        "/api/items/",
        json={"title": "Buy milk", "description": "From the store"},
    )
    assert response.status_code == 201
    assert response.json()["description"] == "From the store"


def test_get_item(client):
    created = client.post("/api/items/", json={"title": "Task A"}).json()
    response = client.get(f"/api/items/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Task A"


def test_get_item_not_found(client):
    response = client.get("/api/items/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["error"]


def test_update_item(client):
    created = client.post("/api/items/", json={"title": "Old title"}).json()
    response = client.patch(
        f"/api/items/{created['id']}", json={"title": "New title"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New title"


def test_delete_item(client):
    created = client.post("/api/items/", json={"title": "To delete"}).json()
    response = client.delete(f"/api/items/{created['id']}")
    assert response.status_code == 204

    # Confirm it's gone
    response = client.get(f"/api/items/{created['id']}")
    assert response.status_code == 404


def test_create_item_validation_error(client):
    response = client.post("/api/items/", json={"title": ""})  # too short
    assert response.status_code == 422
