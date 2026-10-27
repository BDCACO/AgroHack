"""GET /pedidos/sugestao: o pedido montado a partir da reposição do motor, por fornecedor
da última compra, para o produtor confirmar e mandar para POST /pedidos."""

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.core.relogio import hoje


def dia(dias: int) -> str:
    return str(hoje() + timedelta(days=dias))


def ok(resposta, status: int = 200) -> Any:
    assert resposta.status_code == status, resposta.json()
    return resposta.json()


def insumo(
    client: TestClient, nome: str, estoque: float, compras: list[dict[str, Any]]
) -> dict[str, Any]:
    """Mínimo 10, entrega em 15 dias, 2 por dia nos últimos 120 dias (6 a cada 3 dias), e
    as `compras` (a primeira, há 120 dias) somando o que deixa `estoque` hoje."""
    criado = ok(
        client.post(
            "/api/v1/insumos",
            json={"nome": nome, "unidade": "kg", "estoque_minimo": 10, "prazo_reposicao_dias": 15},
        ),
        201,
    )
    base = {"insumo_id": criado["id"]}
    falta = estoque + 240 - sum(c["quantidade"] for c in compras[1:])
    for numero, compra in enumerate(compras):
        corpo = base | {"tipo": "entrada", "data": dia(-120)} | compra
        if numero == 0:
            corpo["quantidade"] = falta
        ok(client.post("/api/v1/movimentacoes", json=corpo), 201)
    for atras in range(0, 120, 3):
        saida = base | {"tipo": "saida", "data": dia(-atras), "quantidade": 6}
        ok(client.post("/api/v1/movimentacoes", json=saida), 201)
    return criado


def fornecedor(client: TestClient, nome: str, **campos: Any) -> int:
    return ok(client.post("/api/v1/fornecedores", json={"nome": nome} | campos), 201)["id"]


def test_sugestao_agrupa_pelo_fornecedor_da_ultima_compra(client: TestClient) -> None:
    cooperativa = fornecedor(client, "Cooperativa Vale Verde")
    revenda = fornecedor(client, "Revenda Boa Safra")
    # Ureia: comprada na cooperativa e, por último, na revenda, mais cara. 20 kg: pedir hoje.
    ureia = insumo(
        client,
        "Ureia",
        20,
        [
            {"quantidade": 0, "valor_unitario": 3, "fornecedor_id": cooperativa},
            {"data": dia(-60), "quantidade": 100, "valor_unitario": 3.6, "fornecedor_id": revenda},
        ],
    )
    # Sal: comprado sem fornecedor; vai para o grupo sem fornecedor, pelo custo médio.
    sal = insumo(client, "Sal mineral", 20, [{"quantidade": 0, "valor_unitario": 4}])
    # Calcário: estoque para pedir só daqui a 30 dias.
    insumo(client, "Calcário", 100, [{"quantidade": 0, "fornecedor_id": cooperativa}])

    sugestao = ok(client.get("/api/v1/pedidos/sugestao"))

    assert (sugestao["referencia"], sugestao["dias"]) == (dia(0), 7)
    [da_revenda, sem_fornecedor] = sugestao["grupos"]
    assert (da_revenda["fornecedor_id"], da_revenda["fornecedor"]) == (revenda, "Revenda Boa Safra")
    [item] = da_revenda["itens"]
    assert {k: item[k] for k in ("insumo_id", "insumo", "unidade", "quantidade")} == {
        "insumo_id": ureia["id"],
        "insumo": "Ureia",
        "unidade": "kg",
        "quantidade": 70,
    }
    # O preço da última compra (R$ 3,60), e não o custo médio: é o que a revenda cobra hoje.
    assert (item["valor_unitario"], item["custo_estimado"]) == (3.6, 252)
    assert (item["pedir_em"], item["pedir_hoje"]) == (dia(0), True)
    assert item["justificativa"].startswith("Pedir hoje 70 kg")
    assert da_revenda["custo_estimado"] == 252
    assert (sem_fornecedor["fornecedor_id"], sem_fornecedor["fornecedor"]) == (None, None)
    assert [(i["insumo_id"], i["valor_unitario"]) for i in sem_fornecedor["itens"]] == [
        (sal["id"], 4)
    ]
    assert sugestao["limitacoes"] == [
        "O fornecedor de cada insumo é o da última compra com fornecedor, e o preço é o dessa "
        "compra (sem ele, o custo médio): confirme com a revenda antes de fechar."
    ]
    # Olhando 30 dias à frente, o calcário entra, na cooperativa (a última compra dele).
    adiante = ok(client.get("/api/v1/pedidos/sugestao", params={"dias": 30}))
    nomes = {g["fornecedor"]: [i["insumo"] for i in g["itens"]] for g in adiante["grupos"]}
    assert nomes == {
        "Cooperativa Vale Verde": ["Calcário"],
        "Revenda Boa Safra": ["Ureia"],
        None: ["Sal mineral"],
    }
    assert client.get("/api/v1/pedidos/sugestao", params={"dias": -1}).status_code == 422
    assert client.get("/api/v1/pedidos/sugestao", params={"dias": 91}).status_code == 422


def test_a_sugestao_confirmada_vira_o_pedido_e_sai_da_sugestao(client: TestClient) -> None:
    revenda = fornecedor(client, "Revenda Boa Safra")
    ureia = insumo(
        client, "Ureia", 20, [{"quantidade": 0, "valor_unitario": 3, "fornecedor_id": revenda}]
    )
    [grupo] = ok(client.get("/api/v1/pedidos/sugestao"))["grupos"]

    # O grupo vai como está: os campos a mais do item são ignorados pelo POST.
    feito = ok(
        client.post(
            "/api/v1/pedidos",
            json={
                "fornecedor_id": grupo["fornecedor_id"],
                "previsto_para": dia(5),
                "itens": grupo["itens"],
            },
        ),
        201,
    )

    assert [(i["insumo_id"], i["quantidade"], i["valor_unitario"]) for i in feito["itens"]] == [
        (ureia["id"], 70, 3)
    ]
    # Já foi pedido: a sugestão não manda pedir de novo.
    assert ok(client.get("/api/v1/pedidos/sugestao"))["grupos"] == []


def test_fornecedor_desativado_nao_e_sugerido(client: TestClient) -> None:
    revenda = fornecedor(client, "Revenda Boa Safra")
    insumo(client, "Ureia", 20, [{"quantidade": 0, "valor_unitario": 3, "fornecedor_id": revenda}])
    client.put(
        f"/api/v1/fornecedores/{revenda}", json={"nome": "Revenda Boa Safra", "ativo": False}
    )

    [grupo] = ok(client.get("/api/v1/pedidos/sugestao"))["grupos"]

    # O pedido a ele seria recusado: o insumo vai para o grupo sem fornecedor, com o preço.
    assert (grupo["fornecedor_id"], grupo["itens"][0]["valor_unitario"]) == (None, 3)


def test_sem_nada_a_pedir(client: TestClient) -> None:
    sugestao = ok(client.get("/api/v1/pedidos/sugestao"))

    assert (sugestao["grupos"], sugestao["limitacoes"]) == ([], [])
