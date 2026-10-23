"""/pedidos: o que foi pedido à revenda, o que já chegou, e o que está a caminho entrando na
análise do insumo (para não mandar comprar de novo)."""

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.core.relogio import hoje
from tests.conftest import CriarUsuario, entrar


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


def receber(client: TestClient, pedido_id: int, **corpo: Any):
    return client.post(f"/api/v1/pedidos/{pedido_id}/receber", json=corpo)


def test_recebe_em_duas_vezes_e_cada_parte_vira_entrada(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    loja = revenda(client)
    feito = pedido(
        client,
        fornecedor_id=loja["id"],
        feito_em=dia(-3),
        previsto_para=dia(2),
        itens=[{"insumo_id": ureia["id"], "quantidade": 100, "valor_unitario": 3.6}],
    )
    linha = feito["itens"][0]["id"]

    primeira = receber(
        client,
        feito["id"],
        data=dia(-1),
        itens=[{"item_id": linha, "quantidade": 40, "validade": dia(300)}],
    )

    assert primeira.status_code == 200, primeira.json()
    corpo = primeira.json()
    assert corpo["avisos"] == []
    assert corpo["pedido"]["situacao"] == "parcial"
    item = corpo["pedido"]["itens"][0]
    assert (item["quantidade_recebida"], item["falta_receber"]) == (40, 60)
    [entrada] = corpo["movimentacoes"]
    campos = (
        "tipo",
        "data",
        "quantidade",
        "validade",
        "valor_unitario",
        "fornecedor_id",
        "comprado_de",
        "item_do_pedido_id",
        "motivo",
    )
    assert {chave: entrada[chave] for chave in campos} == {
        "tipo": "entrada",
        "data": dia(-1),
        "quantidade": 40,
        "validade": dia(300),
        "valor_unitario": 3.6,  # o preço combinado no pedido
        "fornecedor_id": loja["id"],
        "comprado_de": "Revenda Boa Safra",
        "item_do_pedido_id": linha,
        "motivo": None,
    }
    insumo = client.get(f"/api/v1/insumos/{ureia['id']}").json()
    # 20 + 40 kg no galpão, 60 a caminho; custo médio: (260 × 3 + 40 × 3,6) / 300.
    assert (insumo["estoque_atual"], insumo["em_pedido"]) == (60, 60)
    assert insumo["custo_medio"] == 3.08

    # O resto chega com a nota mais cara: vale o preço da nota.
    segunda = receber(
        client, feito["id"], itens=[{"item_id": linha, "quantidade": 60, "valor_unitario": 3.8}]
    ).json()

    assert segunda["pedido"]["situacao"] == "recebido"
    assert segunda["movimentacoes"][0]["data"] == dia(0)  # sem data, a chegada é hoje
    assert segunda["movimentacoes"][0]["valor_unitario"] == 3.8
    insumo = client.get(f"/api/v1/insumos/{ureia['id']}").json()
    assert (insumo["estoque_atual"], insumo["em_pedido"]) == (120, 0)
    assert client.get(f"/api/v1/pedidos/{feito['id']}").json() == segunda["pedido"]


def test_carga_a_mais_entra_com_aviso(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    feito = pedido(client, itens=[{"insumo_id": ureia["id"], "quantidade": 100}])
    linha = feito["itens"][0]["id"]

    corpo = receber(client, feito["id"], itens=[{"item_id": linha, "quantidade": 150}]).json()

    # O que chegou está no galpão: recusar deixaria o estoque menor que o real.
    assert corpo["avisos"] == [
        "Chegaram 150 kg de Ureia, 50 kg a mais que o pedido (100 kg): confira a nota."
    ]
    assert corpo["pedido"]["situacao"] == "recebido"
    item = corpo["pedido"]["itens"][0]
    assert (item["quantidade_recebida"], item["falta_receber"]) == (150, 0)
    assert client.get(f"/api/v1/insumos/{ureia['id']}").json()["em_pedido"] == 0


def test_receber_so_o_que_pode(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    sal = criar(client, "/api/v1/insumos", {"nome": "Sal mineral", "unidade": "kg"})
    feito = pedido(client, feito_em=dia(-2), itens=[{"insumo_id": ureia["id"], "quantidade": 100}])
    outro = pedido(client, itens=[{"insumo_id": sal["id"], "quantidade": 10}])
    linha = feito["itens"][0]["id"]
    item = {"item_id": linha, "quantidade": 10}

    for corpo, frase in (
        ({"itens": []}, None),
        ({"itens": [item | {"quantidade": 0}]}, None),
        ({"itens": [item], "data": dia(1)}, "a data de chegada não pode ser futura"),
        ({"itens": [item, item]}, "a mesma linha do pedido aparece mais de uma vez"),
    ):
        resposta = receber(client, feito["id"], **corpo)
        assert resposta.status_code == 422, corpo
        if frase:
            assert frase in str(resposta.json())
    feito_em = hoje() - timedelta(days=2)
    for corpo, frase in (
        (
            {"itens": [item], "data": dia(-3)},
            f"A carga não chega antes do pedido: o pedido é de {feito_em.strftime('%d/%m/%Y')}.",
        ),
        (
            {"itens": [{"item_id": outro["itens"][0]["id"], "quantidade": 1}]},
            f"A linha {outro['itens'][0]['id']} não é deste pedido.",
        ),
    ):
        resposta = receber(client, feito["id"], **corpo)
        assert resposta.status_code == 422, corpo
        assert resposta.json()["detail"] == frase
    assert receber(client, 999, itens=[item]).status_code == 404
    # Nada entrou no estoque com os erros.
    assert client.get(f"/api/v1/insumos/{ureia['id']}").json()["em_pedido"] == 100


def test_pedido_cancelado_ou_ja_recebido_nao_recebe(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    cancelado = pedido(client, itens=[{"insumo_id": ureia["id"], "quantidade": 10}])
    client.post(f"/api/v1/pedidos/{cancelado['id']}/cancelar")
    recebido = pedido(client, itens=[{"insumo_id": ureia["id"], "quantidade": 10}])
    item = {"item_id": recebido["itens"][0]["id"], "quantidade": 10}
    receber(client, recebido["id"], itens=[item])

    resposta = receber(
        client, cancelado["id"], itens=[{"item_id": cancelado["itens"][0]["id"], "quantidade": 1}]
    )
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == (
        "Este pedido está cancelado: não há o que receber. Se a carga chegou mesmo assim, "
        "lance a entrada como uma compra."
    )
    de_novo = receber(client, recebido["id"], itens=[item])
    assert de_novo.status_code == 409
    assert de_novo.json()["detail"] == (
        "Este pedido já chegou inteiro: lance a carga a mais como uma compra."
    )
    # Nem se altera nem se cancela o que já chegou.
    alterar = client.put(f"/api/v1/pedidos/{recebido['id']}", json={"itens": alterado_itens(ureia)})
    assert alterar.status_code == 409
    assert client.post(f"/api/v1/pedidos/{recebido['id']}/cancelar").status_code == 409


def test_pedido_parcial_nao_se_altera_e_cancela_so_o_que_falta(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    feito = pedido(client, itens=[{"insumo_id": ureia["id"], "quantidade": 100}])
    receber(client, feito["id"], itens=[{"item_id": feito["itens"][0]["id"], "quantidade": 30}])

    alterar = client.put(f"/api/v1/pedidos/{feito['id']}", json={"itens": alterado_itens(ureia)})
    assert alterar.status_code == 409
    assert "está com parte recebida" in alterar.json()["detail"]

    cancelado = client.post(f"/api/v1/pedidos/{feito['id']}/cancelar").json()

    assert cancelado["situacao"] == "cancelado"
    insumo = client.get(f"/api/v1/insumos/{ureia['id']}").json()
    # Os 30 kg que chegaram ficam; os 70 que faltavam não vêm mais.
    assert (insumo["estoque_atual"], insumo["em_pedido"]) == (50, 0)


def test_remover_a_entrada_recebida_devolve_ao_pedido(client: TestClient) -> None:
    ureia = ureia_com_consumo(client)
    feito = pedido(client, itens=[{"insumo_id": ureia["id"], "quantidade": 100}])
    linha = feito["itens"][0]["id"]
    primeira = receber(client, feito["id"], itens=[{"item_id": linha, "quantidade": 30}]).json()
    segunda = receber(client, feito["id"], itens=[{"item_id": linha, "quantidade": 70}]).json()
    assert segunda["pedido"]["situacao"] == "recebido"

    # O funcionário digitou errado: o dono remove a segunda entrada.
    client.delete(f"/api/v1/movimentacoes/{segunda['movimentacoes'][0]['id']}")

    depois = client.get(f"/api/v1/pedidos/{feito['id']}").json()
    assert depois["situacao"] == "parcial"
    assert depois["itens"][0]["quantidade_recebida"] == 30
    assert client.get(f"/api/v1/insumos/{ureia['id']}").json()["em_pedido"] == 70
    client.delete(f"/api/v1/movimentacoes/{primeira['movimentacoes'][0]['id']}")
    assert client.get(f"/api/v1/pedidos/{feito['id']}").json()["situacao"] == "aberto"


def test_funcionario_recebe_e_o_dono_faz_o_pedido(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    client = cliente_autenticado
    criar_usuario("maria", papel="dono", nome="Dona Maria")
    criar_usuario("ze", nome="Zé")
    dono, ze = entrar(client, "maria"), entrar(client, "ze")
    ureia = client.post(
        "/api/v1/insumos", headers=dono, json={"nome": "Ureia", "unidade": "kg"}
    ).json()
    corpo = {"itens": [{"insumo_id": ureia["id"], "quantidade": 50}]}
    assert client.post("/api/v1/pedidos", headers=ze, json=corpo).status_code == 403
    feito = client.post("/api/v1/pedidos", headers=dono, json=corpo).json()
    assert feito["feito_por"] == "Dona Maria"

    # O peão confere a carga no galpão e dá a entrada.
    resposta = client.post(
        f"/api/v1/pedidos/{feito['id']}/receber",
        headers=ze,
        json={"itens": [{"item_id": feito["itens"][0]["id"], "quantidade": 50}]},
    )

    assert resposta.status_code == 200, resposta.json()
    assert resposta.json()["movimentacoes"][0]["lancado_por"] == "Zé"
    assert client.post(f"/api/v1/pedidos/{feito['id']}/cancelar", headers=ze).status_code == 403
