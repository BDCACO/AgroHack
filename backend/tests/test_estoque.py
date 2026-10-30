"""Cadastro de insumos e movimentações pela API, com o banco de teste (SQLite)."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.schemas.estoque import InsumoCadastro
from app.services import estoque as servico

HOJE = hoje()


def dia(dias_atras: int) -> str:
    return str(HOJE - timedelta(days=dias_atras))


def criar(client: TestClient, **campos: Any) -> dict[str, Any]:
    resposta = client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"} | campos)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def lancar(client: TestClient, **campos: Any) -> dict[str, Any]:
    resposta = client.post("/api/v1/movimentacoes", json=campos)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_cadastro_de_insumo_e_nome_duplicado(client: TestClient) -> None:
    insumo = criar(client, estoque_minimo=10)

    assert insumo["estoque_atual"] == 0
    assert [(a["tipo"], a["gravidade"]) for a in insumo["analise"]["alertas"]] == [
        ("abaixo_do_minimo", "alta")
    ]
    # Espaços nas pontas não fazem um nome novo.
    duplicado = client.post("/api/v1/insumos", json={"nome": " Ureia ", "unidade": "kg"})
    assert duplicado.status_code == 409


def test_estoque_e_analise_saem_das_movimentacoes(client: TestClient) -> None:
    insumo = criar(client, estoque_minimo=10, prazo_reposicao_dias=15)
    validade = str(HOJE + timedelta(days=10))
    lancar(
        client,
        insumo_id=insumo["id"],
        tipo="entrada",
        data=dia(30),
        quantidade=100,
        validade=validade,
    )
    for dias_atras in range(30):
        lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(dias_atras), quantidade=2)

    [listado] = client.get("/api/v1/insumos").json()

    # 100 entraram, 30 × 2 saíram; o lote é o mesmo, então sobram 40 kg dele.
    assert listado["estoque_atual"] == 40
    assert listado["analise"]["consumo_diario"] == pytest.approx(60 / 31)
    vencimento = [a for a in listado["analise"]["alertas"] if a["tipo"] == "vencimento_proximo"]
    assert vencimento[0]["justificativa"].startswith("40 kg vencem em")
    assert any("Saldo por lote estimado" in t for t in listado["analise"]["limitacoes"])


@pytest.mark.parametrize(
    "mudanca",
    [
        {"tipo": "saida", "validade": dia(-30)},  # validade só em entrada
        {"data": dia(-1)},  # data futura
        {"quantidade": 0},
        {"insumo_id": 999},
        {"motivo": "descarte"},  # descarte é saída
        {"tipo": "saida", "motivo": "perdi"},
        {"tipo": "saida", "valor_unitario": 3},  # preço é da compra
        {"tipo": "saida", "motivo": "descarte", "valor_unitario": 3},
        {"valor_unitario": 0},
        {"valor_unitario": -2},
    ],
)
def test_movimentacao_invalida_e_recusada(client: TestClient, mudanca: dict[str, Any]) -> None:
    insumo = criar(client)
    corpo = {"insumo_id": insumo["id"], "tipo": "entrada", "data": dia(0), "quantidade": 5}

    resposta = client.post("/api/v1/movimentacoes", json=corpo | mudanca)

    assert resposta.status_code == 422


def test_descarte_tira_o_lote_vencido_sem_contar_como_consumo(client: TestClient) -> None:
    insumo = criar(client)
    vencido = dia(10)
    lancar(
        client,
        insumo_id=insumo["id"],
        tipo="entrada",
        data=dia(60),
        quantidade=10,
        validade=vencido,
    )
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(60), quantidade=20)
    # Retiradas só depois do vencimento: saem do lote bom, e o vencido fica inteiro.
    for dias_atras in range(0, 10, 2):
        lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(dias_atras), quantidade=1)
    antes = client.get(f"/api/v1/insumos/{insumo['id']}").json()
    assert "vencido" in [a["tipo"] for a in antes["analise"]["alertas"]]

    descarte = lancar(
        client, insumo_id=insumo["id"], tipo="saida", motivo="descarte", data=dia(0), quantidade=10
    )

    depois = client.get(f"/api/v1/insumos/{insumo['id']}").json()
    assert descarte["motivo"] == "descarte"
    assert depois["estoque_atual"] == antes["estoque_atual"] - 10
    assert "vencido" not in [a["tipo"] for a in depois["analise"]["alertas"]]
    # O consumo é o das 5 retiradas: os 10 descartados não entram na conta.
    assert depois["analise"]["consumo_diario"] == antes["analise"]["consumo_diario"]
    assert depois["movimentacoes"][0]["motivo"] == "descarte"


def contar(client: TestClient, insumo_id: int, **corpo: Any) -> dict[str, Any]:
    resposta = client.post(f"/api/v1/insumos/{insumo_id}/inventario", json=corpo)
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


def test_inventario_com_falta_lanca_a_diferenca_sem_virar_consumo(client: TestClient) -> None:
    insumo = criar(client)
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(40), quantidade=100)
    for dias_atras in range(0, 40, 4):
        lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(dias_atras), quantidade=2)
    antes = client.get(f"/api/v1/insumos/{insumo['id']}").json()

    ajuste = contar(client, insumo["id"], quantidade_contada=70)

    assert (ajuste["saldo_registrado"], ajuste["quantidade_contada"]) == (80, 70)
    assert ajuste["diferenca"] == -10
    assert ajuste["movimentacao"] | {"id": 0} == {
        "id": 0,
        "insumo_id": insumo["id"],
        "tipo": "saida",
        "motivo": "inventario",
        "data": dia(0),
        "quantidade": 10,
        "validade": None,
        "valor_unitario": None,
        "uuid": None,  # a contagem é feita no sistema, não chega da fila do app
        "talhao_id": None,  # a falta não foi aplicada em lugar nenhum
        "usuario_id": None,  # autenticação desligada e sem login: ninguém é o autor
        "lancado_por": None,
        "fornecedor_id": None,  # a falta não veio de revenda nenhuma
        "comprado_de": None,
        "item_do_pedido_id": None,
    }
    depois = client.get(f"/api/v1/insumos/{insumo['id']}").json()
    assert depois["estoque_atual"] == 70
    assert depois["analise"]["consumo_diario"] == antes["analise"]["consumo_diario"]
    assert any("inventário" in t for t in depois["analise"]["limitacoes"])


def test_inventario_com_sobra_lanca_uma_entrada(client: TestClient) -> None:
    insumo = criar(client)
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(10), quantidade=5)

    ajuste = contar(client, insumo["id"], quantidade_contada=7.5, data=dia(2))

    assert ajuste["diferenca"] == 2.5
    assert ajuste["movimentacao"]["tipo"] == "entrada"
    assert ajuste["movimentacao"]["data"] == dia(2)
    assert client.get("/api/v1/insumos").json()[0]["estoque_atual"] == 7.5


def test_inventario_compara_com_o_saldo_da_data_da_contagem(client: TestClient) -> None:
    insumo = criar(client)
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(10), quantidade=50)
    lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(1), quantidade=20)

    # Contou 50 há 5 dias: batia com o registro daquele dia; a saída de depois não conta.
    ajuste = contar(client, insumo["id"], quantidade_contada=50, data=dia(5))

    assert (ajuste["diferenca"], ajuste["movimentacao"]) == (0, None)
    assert len(client.get("/api/v1/movimentacoes").json()) == 2


@pytest.mark.parametrize(
    "corpo", [{"quantidade_contada": -1}, {"quantidade_contada": 5, "data": dia(-1)}, {}]
)
def test_inventario_invalido(client: TestClient, corpo: dict[str, Any]) -> None:
    insumo = criar(client)

    resposta = client.post(f"/api/v1/insumos/{insumo['id']}/inventario", json=corpo)

    assert resposta.status_code == 422
    inexistente = client.post("/api/v1/insumos/999/inventario", json={"quantidade_contada": 1})
    assert inexistente.status_code == 404


def test_movimentacao_de_inventario_so_pela_contagem(client: TestClient) -> None:
    insumo = criar(client)
    corpo = {"insumo_id": insumo["id"], "tipo": "saida", "data": dia(0), "quantidade": 1}

    resposta = client.post("/api/v1/movimentacoes", json=corpo | {"motivo": "inventario"})

    assert resposta.status_code == 422


def test_atualizar_insumo(client: TestClient) -> None:
    ureia = criar(client)
    criar(client, nome="Calcário", unidade="t")

    atualizado = client.put(
        f"/api/v1/insumos/{ureia['id']}",
        json={"nome": "Ureia 45%", "unidade": "kg", "estoque_minimo": 50},
    )
    assert atualizado.status_code == 200
    assert (atualizado.json()["nome"], atualizado.json()["estoque_minimo"]) == ("Ureia 45%", 50)

    duplicado = {"nome": "Calcário", "unidade": "t"}
    assert client.put(f"/api/v1/insumos/{ureia['id']}", json=duplicado).status_code == 409
    assert client.put("/api/v1/insumos/999", json=duplicado).status_code == 404


def test_listar_e_remover_movimentacoes(client: TestClient) -> None:
    ureia, calcario = criar(client), criar(client, nome="Calcário", unidade="t")
    antiga = lancar(client, insumo_id=ureia["id"], tipo="entrada", data=dia(5), quantidade=10)
    recente = lancar(client, insumo_id=ureia["id"], tipo="saida", data=dia(1), quantidade=3)
    lancar(client, insumo_id=calcario["id"], tipo="entrada", data=dia(2), quantidade=4)

    da_ureia = client.get("/api/v1/movimentacoes", params={"insumo_id": ureia["id"]}).json()
    assert [m["id"] for m in da_ureia] == [recente["id"], antiga["id"]]
    assert len(client.get("/api/v1/movimentacoes", params={"limite": 2}).json()) == 2

    assert client.delete(f"/api/v1/movimentacoes/{recente['id']}").status_code == 204
    assert client.delete(f"/api/v1/movimentacoes/{recente['id']}").status_code == 404
    estoques = {i["nome"]: i["estoque_atual"] for i in client.get("/api/v1/insumos").json()}
    assert estoques == {"Calcário": 4, "Ureia": 10}


def test_detalhe_traz_o_historico_do_estoque(client: TestClient) -> None:
    ureia = criar(client)
    lancar(client, insumo_id=ureia["id"], tipo="entrada", data=dia(10), quantidade=100)
    lancar(client, insumo_id=ureia["id"], tipo="saida", data=dia(10), quantidade=20)
    lancar(client, insumo_id=ureia["id"], tipo="saida", data=dia(3), quantidade=30)

    detalhe = client.get(f"/api/v1/insumos/{ureia['id']}").json()

    assert detalhe["estoque_atual"] == 50
    # Um ponto por dia com movimentação: o saldo no fim daquele dia.
    assert detalhe["historico"] == [
        {"data": dia(10), "saldo": 80},
        {"data": dia(3), "saldo": 50},
    ]
    assert [m["quantidade"] for m in detalhe["movimentacoes"]] == [30, 20, 100]
    assert client.get("/api/v1/insumos/999").status_code == 404


def test_remover_insumo_leva_as_movimentacoes(client: TestClient) -> None:
    ureia = criar(client)
    lancar(client, insumo_id=ureia["id"], tipo="entrada", data=dia(1), quantidade=10)

    assert client.delete(f"/api/v1/insumos/{ureia['id']}").status_code == 204

    assert client.get("/api/v1/insumos").json() == []
    assert client.get("/api/v1/movimentacoes").json() == []
    assert client.delete(f"/api/v1/insumos/{ureia['id']}").status_code == 404


def test_compras_com_preco_dao_custo_medio_e_valor_em_estoque(client: TestClient) -> None:
    insumo = criar(client, embalagem=50, pedido_minimo=500)
    assert (insumo["embalagem"], insumo["pedido_minimo"]) == (50, 500)
    assert (insumo["custo_medio"], insumo["valor_em_estoque"]) == (None, None)
    compra = lancar(
        client,
        insumo_id=insumo["id"],
        tipo="entrada",
        data=dia(20),
        quantidade=1000,
        valor_unitario=3,
    )
    lancar(
        client,
        insumo_id=insumo["id"],
        tipo="entrada",
        data=dia(10),
        quantidade=500,
        valor_unitario=3.6,
    )
    lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(5), quantidade=300)

    detalhe = client.get(f"/api/v1/insumos/{insumo['id']}").json()

    assert compra["valor_unitario"] == 3
    # (1000 × 3,00 + 500 × 3,60) / 1500 = 3,20; restam 1200 kg × 3,20.
    assert detalhe["custo_medio"] == pytest.approx(3.2)
    assert detalhe["valor_em_estoque"] == pytest.approx(3840)
    assert [m["valor_unitario"] for m in detalhe["movimentacoes"]] == [None, 3.6, 3]
    assert not any("preço" in t for t in detalhe["analise"]["limitacoes"])


def test_compra_sem_preco_fica_fora_do_custo_e_a_analise_diz(client: TestClient) -> None:
    insumo = criar(client)
    lancar(
        client, insumo_id=insumo["id"], tipo="entrada", data=dia(9), quantidade=10, valor_unitario=5
    )
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(8), quantidade=30)
    # A sobra da contagem não é compra: não pesa no custo nem conta como compra sem preço.
    contar(client, insumo["id"], quantidade_contada=45)

    [listado] = client.get("/api/v1/insumos").json()

    assert listado["custo_medio"] == 5
    assert listado["valor_em_estoque"] == 225
    assert (
        "Custo médio só das compras com preço (1 de 2): as outras ficam fora da conta."
        in listado["analise"]["limitacoes"]
    )


def test_estoque_negativo_nao_vale_dinheiro(client: TestClient) -> None:
    insumo = criar(client)
    lancar(
        client, insumo_id=insumo["id"], tipo="entrada", data=dia(9), quantidade=10, valor_unitario=5
    )
    lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(8), quantidade=15)

    assert client.get("/api/v1/insumos").json()[0]["valor_em_estoque"] == 0


@pytest.mark.parametrize("campos", [{"embalagem": 0}, {"pedido_minimo": -1}])
def test_embalagem_e_pedido_minimo_invalidos(client: TestClient, campos: dict[str, Any]) -> None:
    resposta = client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"} | campos)

    assert resposta.status_code == 422


def test_alterar_insumo_sem_os_campos_novos_mantem_embalagem(client: TestClient) -> None:
    # O site e o app de antes não conhecem embalagem nem pedido mínimo: um PUT deles não
    # pode apagar o que outro cadastrou.
    ureia = criar(client, embalagem=50, pedido_minimo=200)

    sem = client.put(f"/api/v1/insumos/{ureia['id']}", json={"nome": "Ureia", "unidade": "kg"})
    limpando = client.put(
        f"/api/v1/insumos/{ureia['id']}",
        json={"nome": "Ureia", "unidade": "kg", "embalagem": None, "pedido_minimo": 100},
    )

    assert (sem.json()["embalagem"], sem.json()["pedido_minimo"]) == (50, 200)
    assert (limpando.json()["embalagem"], limpando.json()["pedido_minimo"]) == (None, 100)


def test_cadastro_com_marcas_preferenciais(client: TestClient) -> None:
    insumo = criar(client, marcas_preferenciais="Yara, Heringer")
    assert insumo["marcas_preferenciais"] == "Yara, Heringer"


def test_alterar_insumo_sem_marcas_preferenciais_mantem_a_gravada(client: TestClient) -> None:
    ureia = criar(client, marcas_preferenciais="Yara, Heringer")

    sem = client.put(f"/api/v1/insumos/{ureia['id']}", json={"nome": "Ureia", "unidade": "kg"})

    assert sem.json()["marcas_preferenciais"] == "Yara, Heringer"


def test_cadastro_com_codigo_de_barras_e_duplicado(client: TestClient) -> None:
    ureia = criar(client, codigo_de_barras="7891234567890")
    assert ureia["codigo_de_barras"] == "7891234567890"

    duplicado = client.post(
        "/api/v1/insumos",
        json={"nome": "Calcário", "unidade": "t", "codigo_de_barras": "7891234567890"},
    )
    assert duplicado.status_code == 409


def test_alterar_insumo_sem_codigo_de_barras_mantem_o_gravado(client: TestClient) -> None:
    # O leitor do app só manda o código quando lê um novo: um PUT sem ele (de quem não lê
    # código de barras) não pode apagar o vínculo já ensinado.
    ureia = criar(client, codigo_de_barras="7891234567890")

    sem = client.put(f"/api/v1/insumos/{ureia['id']}", json={"nome": "Ureia", "unidade": "kg"})

    assert sem.json()["codigo_de_barras"] == "7891234567890"


def test_preco_em_saida_explica_o_porque(client: TestClient) -> None:
    insumo = criar(client)
    corpo = {"insumo_id": insumo["id"], "tipo": "saida", "data": dia(0), "quantidade": 1}

    resposta = client.post("/api/v1/movimentacoes", json=corpo | {"valor_unitario": 3})

    assert "só se informa numa entrada" in resposta.json()["detail"][0]["msg"]


@pytest.mark.parametrize(
    "mudanca",
    [
        {"quantidade": 0.0004},  # vira 0,000 na coluna de 3 casas
        {"tipo": "entrada", "valor_unitario": 0.00004},  # vira 0,0000 na de 4 casas
    ],
)
def test_numero_que_o_banco_arredondaria_para_zero_e_422(
    client: TestClient, mudanca: dict[str, Any]
) -> None:
    insumo = criar(client)
    corpo = {"insumo_id": insumo["id"], "tipo": "saida", "data": dia(0), "quantidade": 1}

    resposta = client.post("/api/v1/movimentacoes", json=corpo | mudanca)

    assert resposta.status_code == 422


def test_numeros_chegam_arredondados_como_o_banco_guarda(client: TestClient) -> None:
    # O PostgreSQL arredonda o meio para longe do zero; o round() do Python, pelo valor
    # binário do float (1.2345 vira 1.234). A API arredonda como o banco, para o que ela
    # responde e compara ser o que fica gravado.
    insumo = criar(client, embalagem=0.0125)
    entrada = lancar(
        client,
        insumo_id=insumo["id"],
        tipo="entrada",
        data=dia(0),
        quantidade=1.2345,
        valor_unitario=0.01235,
    )

    assert (entrada["quantidade"], entrada["valor_unitario"]) == (1.235, 0.0124)
    assert client.get("/api/v1/insumos").json()[0]["embalagem"] == 0.013


@pytest.mark.parametrize("campo", ["embalagem", "estoque_minimo", "pedido_minimo"])
def test_cadastro_com_numero_que_vira_zero(client: TestClient, campo: str) -> None:
    resposta = client.post(
        "/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg", campo: 0.0004}
    )

    # Embalagem zero não existe (422); mínimo e pedido mínimo zero existem.
    if campo == "embalagem":
        assert resposta.status_code == 422
    else:
        assert (resposta.status_code, resposta.json()[campo]) == (201, 0)


def test_so_nome_repetido_vira_nome_duplicado(db: Session) -> None:
    # Outra regra do banco violada não pode virar "já existe um insumo com esse nome".
    sem_validacao = InsumoCadastro.model_construct(
        nome="Ureia",
        unidade="kg",
        estoque_minimo=-1,
        prazo_reposicao_dias=None,
        embalagem=None,
        pedido_minimo=None,
        carencia_dias=None,
    )

    with pytest.raises(IntegrityError):
        servico.criar_insumo(db, sem_validacao)
