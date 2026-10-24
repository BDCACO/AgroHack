"""/categorias: o agrupamento dos insumos (fertilizante, defensivo, nutrição animal...), e a
categoria no cadastro do insumo."""

from typing import Any

from fastapi.testclient import TestClient


def categoria(client: TestClient, nome: str) -> dict[str, Any]:
    resposta = client.post("/api/v1/categorias", json={"nome": nome})
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def insumo(client: TestClient, **campos: Any) -> dict[str, Any]:
    resposta = client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"} | campos)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_cadastra_lista_altera_e_conta_os_insumos(client: TestClient) -> None:
    adubo = categoria(client, "  Fertilizante ")
    categoria(client, "Defensivo agrícola")
    insumo(client, categoria_id=adubo["id"])

    assert adubo["nome"] == "Fertilizante"
    lista = client.get("/api/v1/categorias").json()
    # Pelo nome, e com quantos insumos cada uma tem (a tela mostra antes de remover).
    assert [(c["nome"], c["insumos"]) for c in lista] == [
        ("Defensivo agrícola", 0),
        ("Fertilizante", 1),
    ]
    alterada = client.put(f"/api/v1/categorias/{adubo['id']}", json={"nome": "Adubo"})
    assert alterada.status_code == 200
    assert (alterada.json()["nome"], alterada.json()["insumos"]) == ("Adubo", 1)
    assert client.put("/api/v1/categorias/999", json={"nome": "X"}).status_code == 404


def test_nome_repetido_e_409_e_nome_invalido_422(client: TestClient) -> None:
    categoria(client, "Fertilizante")
    outra = categoria(client, "Semente e muda")

    assert client.post("/api/v1/categorias", json={"nome": "Fertilizante"}).status_code == 409
    repetida = client.put(f"/api/v1/categorias/{outra['id']}", json={"nome": "Fertilizante"})
    assert repetida.status_code == 409
    assert repetida.json()["detail"] == "Já existe uma categoria com esse nome."
    for corpo in ({"nome": ""}, {"nome": " "}, {"nome": "Adubo\x00"}, {"nome": "x" * 61}):
        assert client.post("/api/v1/categorias", json=corpo).status_code == 422, corpo


def test_remove_so_a_categoria_sem_insumo(client: TestClient) -> None:
    adubo = categoria(client, "Fertilizante")
    vazia = categoria(client, "Combustível e lubrificante")
    insumo(client, categoria_id=adubo["id"])
    insumo(client, nome="NPK 20-05-20", categoria_id=adubo["id"])

    recusada = client.delete(f"/api/v1/categorias/{adubo['id']}")
    assert recusada.status_code == 409
    assert recusada.json()["detail"].startswith("Fertilizante tem 2 insumos")
    assert client.delete(f"/api/v1/categorias/{vazia['id']}").status_code == 204
    assert client.delete(f"/api/v1/categorias/{vazia['id']}").status_code == 404
    assert [c["nome"] for c in client.get("/api/v1/categorias").json()] == ["Fertilizante"]


def test_insumo_com_categoria_e_categoria_inexistente(client: TestClient) -> None:
    adubo = categoria(client, "Fertilizante")

    ureia = insumo(client, categoria_id=adubo["id"])
    assert (ureia["categoria_id"], ureia["categoria"]) == (adubo["id"], "Fertilizante")
    sem = insumo(client, nome="Sal mineral")
    assert (sem["categoria_id"], sem["categoria"]) == (None, None)
    detalhe = client.get(f"/api/v1/insumos/{ureia['id']}").json()
    assert detalhe["categoria"] == "Fertilizante"
    inexistente = client.post(
        "/api/v1/insumos", json={"nome": "Glifosato", "unidade": "L", "categoria_id": 999}
    )
    assert inexistente.status_code == 422
    assert inexistente.json()["detail"] == "Categoria não encontrada."
    alterar = {"nome": "Ureia", "unidade": "kg", "categoria_id": 999}
    assert client.put(f"/api/v1/insumos/{ureia['id']}", json=alterar).status_code == 422


def test_alterar_insumo_sem_a_categoria_mantem_a_gravada(client: TestClient) -> None:
    adubo = categoria(client, "Fertilizante")
    ureia = insumo(client, categoria_id=adubo["id"])

    # O site e o app de antes não conhecem o campo: o PUT deles não pode apagá-lo.
    antigo = {"nome": "Ureia agrícola", "unidade": "kg", "estoque_minimo": 300}
    alterado = client.put(f"/api/v1/insumos/{ureia['id']}", json=antigo).json()
    assert (alterado["nome"], alterado["categoria_id"]) == ("Ureia agrícola", adubo["id"])
    # Mandar null de propósito tira a categoria.
    limpo = client.put(f"/api/v1/insumos/{ureia['id']}", json=antigo | {"categoria_id": None})
    assert limpo.json()["categoria_id"] is None
