"""/pedidos: o que foi pedido à revenda, o que já chegou, e o que está a caminho entrando na
análise do insumo (para não mandar comprar de novo)."""

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.core.relogio import hoje


def dia(dias: int) -> str:
    """Dias a partir de hoje: negativo é passado."""
    return str(hoje() + timedelta(days=dias))


def criar(client: TestClient, url: str, corpo: dict[str, Any]) -> dict[str, Any]:
    resposta = client.post(url, json=corpo)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def ureia_com_consumo(client: TestClient) -> dict[str, Any]:
    """20 kg em estoque, 2 kg/dia nos últimos 120 dias, mínimo 10, entrega em 15 dias: a
    conta da reposição dá 70 kg, para hoje."""
    insumo = criar(
        client,
        "/api/v1/insumos",
        {"nome": "Ureia", "unidade": "kg", "estoque_minimo": 10, "prazo_reposicao_dias": 15},
    )
    base = {"insumo_id": insumo["id"]}
    criar(
        client,
        "/api/v1/movimentacoes",
        base | {"tipo": "entrada", "data": dia(-120), "quantidade": 260, "valor_unitario": 3},
    )
    for atras in range(120):
        criar(
            client,
            "/api/v1/movimentacoes",
            base | {"tipo": "saida", "data": dia(-atras), "quantidade": 2},
        )
    return client.get(f"/api/v1/insumos/{insumo['id']}").json()


def revenda(client: TestClient, **campos: Any) -> dict[str, Any]:
    return criar(client, "/api/v1/fornecedores", {"nome": "Revenda Boa Safra"} | campos)


def pedido(client: TestClient, **campos: Any) -> dict[str, Any]:
    return criar(client, "/api/v1/pedidos", campos)


def test_faz_o_pedido_e_ele_entra_na_analise(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    sal = criar(client, "/api/v1/insumos", {"nome": "Sal mineral", "unidade": "kg"})
    loja = revenda(client)
    assert ureia["analise"]["reposicao"]["pedir_hoje"] is True
    assert (ureia["em_pedido"], ureia["chegada_prevista"]) == (0, None)

    feito = pedido(
        client,
        fornecedor_id=loja["id"],
        previsto_para=dia(5),
        observacao="Combinado por WhatsApp.",
        itens=[
            {"insumo_id": ureia["id"], "quantidade": 70, "valor_unitario": 3.2},
            {"insumo_id": sal["id"], "quantidade": 100},
        ],
    )

    assert feito["situacao"] == "aberto"
    assert (feito["feito_em"], feito["previsto_para"]) == (dia(0), dia(5))
    assert (feito["fornecedor_id"], feito["fornecedor"]) == (loja["id"], "Revenda Boa Safra")
    assert (feito["usuario_id"], feito["feito_por"], feito["atrasado"]) == (None, None, False)
    assert feito["custo_estimado"] == 224  # só o item com preço: 70 × 3,20
    item = feito["itens"][0]
    assert (item["insumo"], item["unidade"], item["quantidade"]) == ("Ureia", "kg", 70)
    assert (item["quantidade_recebida"], item["falta_receber"]) == (0, 70)
    # O que está a caminho entra na análise: a reposição o desconta, e não manda pedir hoje.
    depois = client.get(f"/api/v1/insumos/{ureia['id']}").json()
    assert (depois["em_pedido"], depois["chegada_prevista"]) == (70, dia(5))
    assert depois["analise"]["reposicao"]["pedir_hoje"] is False
    risco = next(a for a in depois["analise"]["alertas"] if a["tipo"] == "risco_de_falta")
    assert risco["gravidade"] == "media"
    assert "Já foram pedidos 70 kg." in risco["justificativa"]
    lista = {i["nome"]: i for i in client.get("/api/v1/insumos").json()}
    assert (lista["Ureia"]["em_pedido"], lista["Sal mineral"]["em_pedido"]) == (70, 100)
    assert client.get(f"/api/v1/pedidos/{feito['id']}").json() == feito


def test_pedido_sem_fornecedor_e_sem_previsao_vale(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)

    feito = pedido(client, itens=[{"insumo_id": ureia["id"], "quantidade": 70}])

    assert (feito["fornecedor"], feito["previsto_para"], feito["custo_estimado"]) == (
        None,
        None,
        None,
    )
    depois = client.get(f"/api/v1/insumos/{ureia['id']}").json()
    assert (depois["em_pedido"], depois["chegada_prevista"]) == (70, None)
    assert any("sem data prevista" in t for t in depois["analise"]["limitacoes"])


def test_pedido_invalido_e_422(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    desativada = revenda(client, ativo=False)
    item = {"insumo_id": ureia["id"], "quantidade": 70}

    for corpo, frase in (
        ({"itens": []}, None),
        ({"itens": [item | {"quantidade": 0}]}, None),
        ({"itens": [item | {"valor_unitario": 0}]}, None),
        ({"itens": [item, item]}, "o mesmo insumo aparece em mais de uma linha"),
        ({"itens": [item], "feito_em": dia(1)}, "a data do pedido não pode ser futura"),
        (
            {"itens": [item], "feito_em": dia(-2), "previsto_para": dia(-3)},
            "a previsão de chegada não pode ser antes do pedido",
        ),
        ({"itens": [item], "observacao": "nulo\x00"}, None),
    ):
        resposta = client.post("/api/v1/pedidos", json=corpo)
        assert resposta.status_code == 422, corpo
        if frase:
            assert frase in str(resposta.json()), resposta.json()
    for corpo, frase in (
        ({"itens": [{"insumo_id": 999, "quantidade": 1}]}, "Insumo 999 não encontrado."),
        ({"itens": [item], "fornecedor_id": 999}, "Fornecedor não encontrado."),
        (
            {"itens": [item], "fornecedor_id": desativada["id"]},
            "Revenda Boa Safra está desativado: reative-o na tela de Fornecedores para fazer "
            "um pedido a ele.",
        ),
    ):
        resposta = client.post("/api/v1/pedidos", json=corpo)
        assert resposta.status_code == 422, corpo
        assert resposta.json()["detail"] == frase
    assert client.get("/api/v1/pedidos").json() == []
    assert client.get("/api/v1/pedidos/999").status_code == 404


def test_lista_com_filtros(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    sal = criar(client, "/api/v1/insumos", {"nome": "Sal mineral", "unidade": "kg"})
    loja = revenda(client)
    antigo = pedido(client, feito_em=dia(-10), itens=[{"insumo_id": sal["id"], "quantidade": 50}])
    novo = pedido(
        client, fornecedor_id=loja["id"], itens=[{"insumo_id": ureia["id"], "quantidade": 70}]
    )
    client.post(f"/api/v1/pedidos/{antigo['id']}/cancelar")

    def ids(**filtros: Any) -> list[int]:
        resposta = client.get("/api/v1/pedidos", params=filtros)
        assert resposta.status_code == 200, resposta.json()
        return [p["id"] for p in resposta.json()]

    # Os mais recentes primeiro.
    assert ids() == [novo["id"], antigo["id"]]
    assert ids(situacao="aberto") == [novo["id"]]
    assert ids(situacao="cancelado") == [antigo["id"]]
    assert ids(fornecedor_id=loja["id"]) == [novo["id"]]
    assert ids(insumo_id=sal["id"]) == [antigo["id"]]
    assert client.get("/api/v1/pedidos", params={"situacao": "perdido"}).status_code == 422


def test_altera_o_pedido_aberto(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    sal = criar(client, "/api/v1/insumos", {"nome": "Sal mineral", "unidade": "kg"})
    calcario = criar(client, "/api/v1/insumos", {"nome": "Calcário", "unidade": "t"})
    feito = pedido(
        client,
        itens=[
            {"insumo_id": ureia["id"], "quantidade": 70},
            {"insumo_id": sal["id"], "quantidade": 100},
        ],
    )

    resposta = client.put(
        f"/api/v1/pedidos/{feito['id']}",
        json={
            "previsto_para": dia(3),
            "itens": [
                {"insumo_id": calcario["id"], "quantidade": 2},
                {"insumo_id": ureia["id"], "quantidade": 100, "valor_unitario": 3.1},
            ],
        },
    )

    assert resposta.status_code == 200, resposta.json()
    alterado = resposta.json()
    assert alterado["previsto_para"] == dia(3)
    assert [(i["insumo"], i["quantidade"]) for i in alterado["itens"]] == [
        ("Ureia", 100),
        ("Calcário", 2),
    ]
    # A linha da ureia é a mesma (o recebimento aponta para ela); a do sal saiu.
    assert alterado["itens"][0]["id"] == feito["itens"][0]["id"]
    assert client.get(f"/api/v1/insumos/{sal['id']}").json()["em_pedido"] == 0
    assert client.get(f"/api/v1/insumos/{ureia['id']}").json()["em_pedido"] == 100
    sem_itens = client.put(f"/api/v1/pedidos/{feito['id']}", json={"itens": []})
    assert sem_itens.status_code == 422
    assert (
        client.put("/api/v1/pedidos/999", json={"itens": alterado_itens(ureia)}).status_code == 404
    )


def alterado_itens(ureia: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"insumo_id": ureia["id"], "quantidade": 1}]


def test_cancela_e_o_pedido_sai_da_analise(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    feito = pedido(client, itens=[{"insumo_id": ureia["id"], "quantidade": 70}])

    resposta = client.post(f"/api/v1/pedidos/{feito['id']}/cancelar")

    assert resposta.status_code == 200
    assert resposta.json()["situacao"] == "cancelado"
    depois = client.get(f"/api/v1/insumos/{ureia['id']}").json()
    assert depois["em_pedido"] == 0
    assert depois["analise"]["reposicao"]["pedir_hoje"] is True
    # Cancelar de novo não muda nada; alterar o cancelado, sim, é conflito.
    assert client.post(f"/api/v1/pedidos/{feito['id']}/cancelar").json()["situacao"] == "cancelado"
    alterar = client.put(f"/api/v1/pedidos/{feito['id']}", json={"itens": alterado_itens(ureia)})
    assert alterar.status_code == 409
    assert alterar.json()["detail"] == (
        "Este pedido está cancelado: só se altera o pedido aberto, antes de chegar qualquer "
        "coisa. Faça um pedido novo."
    )
    assert client.post("/api/v1/pedidos/999/cancelar").status_code == 404


def test_pedido_atrasado(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)

    feito = pedido(
        client,
        feito_em=dia(-10),
        previsto_para=dia(-1),
        itens=[{"insumo_id": ureia["id"], "quantidade": 70}],
    )

    assert feito["atrasado"] is True
    risco = next(
        a
        for a in client.get(f"/api/v1/insumos/{ureia['id']}").json()["analise"]["alertas"]
        if a["tipo"] == "risco_de_falta"
    )
    assert risco["gravidade"] == "alta"
    assert "e ainda não chegaram: cobre a revenda." in risco["justificativa"]


def test_remover_insumo_leva_o_que_foi_pedido_dele(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    sal = criar(client, "/api/v1/insumos", {"nome": "Sal mineral", "unidade": "kg"})
    so_ureia = pedido(client, itens=[{"insumo_id": ureia["id"], "quantidade": 70}])
    os_dois = pedido(
        client,
        itens=[
            {"insumo_id": ureia["id"], "quantidade": 70},
            {"insumo_id": sal["id"], "quantidade": 100},
        ],
    )

    assert client.delete(f"/api/v1/insumos/{ureia['id']}").status_code == 204

    # O pedido que ficou vazio sai junto; o outro fica com o sal.
    assert client.get(f"/api/v1/pedidos/{so_ureia['id']}").status_code == 404
    restante = client.get(f"/api/v1/pedidos/{os_dois['id']}").json()
    assert [i["insumo"] for i in restante["itens"]] == ["Sal mineral"]
