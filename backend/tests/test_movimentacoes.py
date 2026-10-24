from typing import Any

from fastapi.testclient import TestClient

from tests.test_insumos import criar_insumo

URL = "/api/v1/movimentacoes"


def registrar(client: TestClient, insumo_id: str, **campos: Any) -> Any:
    corpo = {"insumo_id": insumo_id, "tipo": "compra", "quantidade": 10, "data": "2026-10-01"}
    return client.post(URL, json={**corpo, **campos})


def saldo(client: TestClient, insumo_id: str) -> float:
    return client.get(f"/api/v1/insumos/{insumo_id}").json()["saldo_atual"]


def test_compra_e_retirada_atualizam_o_saldo(client: TestClient) -> None:
    insumo = criar_insumo(client)["id"]

    assert registrar(client, insumo, quantidade=100.25, validade="2027-03-01").status_code == 201
    assert registrar(client, insumo, tipo="retirada", quantidade=40).status_code == 201

    assert saldo(client, insumo) == 60.25
    assert client.get("/api/v1/insumos").json()[0]["saldo_atual"] == 60.25


def test_saida_traz_nome_e_unidade_do_insumo(client: TestClient) -> None:
    insumo = criar_insumo(client, nome="Glifosato", unidade="L")["id"]

    mov = registrar(client, insumo, observacao="  safra 26/27  ").json()

    assert mov["insumo_nome"] == "Glifosato"
    assert mov["insumo_unidade"] == "L"
    assert mov["observacao"] == "safra 26/27"
    assert mov["quantidade"] == 10


def test_retirada_maior_que_o_saldo_da_409_com_explicacao(client: TestClient) -> None:
    insumo = criar_insumo(client)["id"]
    registrar(client, insumo, quantidade=10)

    resposta = registrar(client, insumo, tipo="retirada", quantidade=15)

    assert resposta.status_code == 409
    assert resposta.json() == {
        "codigo": "ESTOQUE_INSUFICIENTE",
        "mensagem": "Retirada de 15 kg maior que o saldo disponível (10 kg).",
    }
    assert saldo(client, insumo) == 10


def test_quantidade_zero_ou_negativa_e_recusada(client: TestClient) -> None:
    insumo = criar_insumo(client)["id"]

    assert registrar(client, insumo, quantidade=0).status_code == 422
    assert registrar(client, insumo, quantidade=-3).status_code == 422


def test_validade_em_retirada_e_recusada(client: TestClient) -> None:
    insumo = criar_insumo(client)["id"]
    registrar(client, insumo)

    resposta = registrar(client, insumo, tipo="retirada", quantidade=1, validade="2027-01-01")

    assert resposta.status_code == 422


def test_insumo_inexistente_da_404(client: TestClient) -> None:
    resposta = registrar(client, "0190b6c2-0000-7000-8000-000000000000")

    assert resposta.status_code == 404


def test_lista_mais_recentes_primeiro_e_filtra_por_insumo(client: TestClient) -> None:
    ureia = criar_insumo(client, nome="Ureia")["id"]
    calcario = criar_insumo(client, nome="Calcário")["id"]
    registrar(client, ureia, data="2026-09-01")
    registrar(client, ureia, data="2026-10-05")
    registrar(client, calcario, data="2026-09-20")

    todas = client.get(URL).json()
    assert [m["data"] for m in todas] == ["2026-10-05", "2026-09-20", "2026-09-01"]

    so_ureia = client.get(URL, params={"insumo_id": ureia}).json()
    assert {m["insumo_id"] for m in so_ureia} == {ureia}
    assert len(so_ureia) == 2


def test_remover_retirada_devolve_ao_saldo(client: TestClient) -> None:
    insumo = criar_insumo(client)["id"]
    registrar(client, insumo, quantidade=10)
    retirada = registrar(client, insumo, tipo="retirada", quantidade=4).json()

    assert client.delete(f"{URL}/{retirada['id']}").status_code == 204
    assert saldo(client, insumo) == 10


def test_remover_compra_ja_consumida_da_409(client: TestClient) -> None:
    insumo = criar_insumo(client)["id"]
    compra = registrar(client, insumo, quantidade=10).json()
    registrar(client, insumo, tipo="retirada", quantidade=8)

    resposta = client.delete(f"{URL}/{compra['id']}")

    assert resposta.status_code == 409
    assert resposta.json()["codigo"] == "ESTOQUE_INSUFICIENTE"
    assert saldo(client, insumo) == 2


def test_remover_movimentacao_inexistente_da_404(client: TestClient) -> None:
    resposta = client.delete(f"{URL}/0190b6c2-0000-7000-8000-000000000000")

    assert resposta.status_code == 404
    assert resposta.json()["codigo"] == "MOVIMENTACAO_NAO_ENCONTRADA"
