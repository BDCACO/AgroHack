from typing import Any

from fastapi.testclient import TestClient

URL = "/api/v1/insumos"


def criar_insumo(client: TestClient, **campos: Any) -> dict[str, Any]:
    corpo = {"nome": "Ureia", "unidade": "kg", "estoque_minimo": 100, **campos}
    resposta = client.post(URL, json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_cria_e_lista_com_saldo_zero(client: TestClient) -> None:
    criado = criar_insumo(client, categoria="Fertilizante", estoque_minimo=150.5)

    assert criado["nome"] == "Ureia"
    assert criado["estoque_minimo"] == 150.5  # número no JSON, não string
    assert criado["saldo_atual"] == 0

    lista = client.get(URL).json()
    assert [i["id"] for i in lista] == [criado["id"]]


def test_lista_em_ordem_alfabetica_sem_diferenciar_maiusculas(client: TestClient) -> None:
    for nome in ["ureia", "Adubo", "glifosato"]:
        criar_insumo(client, nome=nome)

    assert [i["nome"] for i in client.get(URL).json()] == ["Adubo", "glifosato", "ureia"]


def test_nome_e_aparado_e_vazio_e_recusado(client: TestClient) -> None:
    assert criar_insumo(client, nome="  Calcário  ")["nome"] == "Calcário"
    assert (
        client.post(URL, json={"nome": "   ", "unidade": "kg", "estoque_minimo": 0}).status_code
        == 422
    )


def test_estoque_minimo_negativo_e_recusado(client: TestClient) -> None:
    resposta = client.post(URL, json={"nome": "X", "unidade": "kg", "estoque_minimo": -1})

    assert resposta.status_code == 422


def test_nome_duplicado_sem_diferenciar_maiusculas_da_409(client: TestClient) -> None:
    criar_insumo(client, nome="Ureia")

    resposta = client.post(URL, json={"nome": "UREIA", "unidade": "kg", "estoque_minimo": 0})

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "INSUMO_DUPLICADO"


def test_atualiza(client: TestClient) -> None:
    criado = criar_insumo(client)

    resposta = client.put(
        f"{URL}/{criado['id']}",
        json={"nome": "Ureia 45%", "unidade": "saco 50 kg", "estoque_minimo": 3},
    )

    assert resposta.status_code == 200
    assert resposta.json()["unidade"] == "saco 50 kg"
    assert client.get(f"{URL}/{criado['id']}").json()["nome"] == "Ureia 45%"


def test_renomear_para_nome_existente_da_409(client: TestClient) -> None:
    criar_insumo(client, nome="Ureia")
    outro = criar_insumo(client, nome="Calcário")

    resposta = client.put(
        f"{URL}/{outro['id']}", json={"nome": "ureia", "unidade": "kg", "estoque_minimo": 0}
    )

    assert resposta.status_code == 409


def test_insumo_inexistente_da_404(client: TestClient) -> None:
    resposta = client.get(f"{URL}/0190b6c2-0000-7000-8000-000000000000")

    assert resposta.status_code == 404
    assert resposta.json() == {
        "codigo": "INSUMO_NAO_ENCONTRADO",
        "mensagem": "Insumo não encontrado.",
    }


def test_remove_insumo_sem_movimentacoes(client: TestClient) -> None:
    criado = criar_insumo(client)

    assert client.delete(f"{URL}/{criado['id']}").status_code == 204
    assert client.get(URL).json() == []


def test_nao_remove_insumo_com_movimentacoes(client: TestClient) -> None:
    criado = criar_insumo(client)
    client.post(
        "/api/v1/movimentacoes",
        json={"insumo_id": criado["id"], "tipo": "compra", "quantidade": 5, "data": "2026-10-01"},
    )

    resposta = client.delete(f"{URL}/{criado['id']}")

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "INSUMO_COM_MOVIMENTACOES"
