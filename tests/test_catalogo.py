from fastapi.testclient import TestClient


def test_alta_y_listado_de_espacios_y_colecciones(client: TestClient) -> None:
    espacio = client.post("/api/espacios", json={"slug": "intereses", "nombre": "Intereses"})
    coleccion = client.post(
        "/api/espacios/intereses/colecciones", json={"slug": "agricultura", "nombre": "Agricultura"}
    )

    assert espacio.status_code == 201
    assert coleccion.status_code == 201
    assert coleccion.json()["espacio"] == "intereses"
    assert [e["slug"] for e in client.get("/api/espacios").json()] == ["intereses"]
    listado = client.get("/api/espacios/intereses/colecciones").json()
    assert [(c["espacio"], c["slug"]) for c in listado] == [("intereses", "agricultura")]


def test_slug_repetido_responde_409(client: TestClient) -> None:
    client.post("/api/espacios", json={"slug": "intereses", "nombre": "Intereses"})
    client.post("/api/espacios/intereses/colecciones", json={"slug": "agro", "nombre": "A"})

    espacio = client.post("/api/espacios", json={"slug": "intereses", "nombre": "Otro"})
    coleccion = client.post(
        "/api/espacios/intereses/colecciones", json={"slug": "agro", "nombre": "B"}
    )

    assert espacio.status_code == 409
    assert coleccion.status_code == 409


def test_misma_coleccion_en_dos_espacios_es_valida(client: TestClient) -> None:
    for espacio in ("intereses", "personal"):
        client.post("/api/espacios", json={"slug": espacio, "nombre": espacio})

    respuestas = [
        client.post(f"/api/espacios/{e}/colecciones", json={"slug": "notas", "nombre": "Notas"})
        for e in ("intereses", "personal")
    ]

    assert [r.status_code for r in respuestas] == [201, 201]


def test_espacio_inexistente_responde_404(client: TestClient) -> None:
    respuesta = client.get("/api/espacios/no-existe/colecciones")

    assert respuesta.status_code == 404
    assert respuesta.json() == {"error": "El espacio «no-existe» no existe"}


def test_slug_invalido_responde_422(client: TestClient) -> None:
    respuesta = client.post("/api/espacios", json={"slug": "Con Espacios", "nombre": "x"})

    assert respuesta.status_code == 422
