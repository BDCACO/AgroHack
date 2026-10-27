"""Filtros, busca e paginação nas listas de insumos e de movimentações. Todos opcionais:
sem eles, a resposta é a de sempre (o site e o app de hoje não os mandam)."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.services import autenticacao
from tests.conftest import CriarUsuario

HOJE = hoje()


def dia(dias_atras: int) -> str:
    return str(HOJE - timedelta(days=dias_atras))


def post(client: TestClient, rota: str, **corpo: Any) -> dict[str, Any]:
    resposta = client.post(f"/api/v1/{rota}", json=corpo)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def nomes(client: TestClient, consulta: str = "") -> list[str]:
    resposta = client.get(f"/api/v1/insumos{consulta}")
    assert resposta.status_code == 200, resposta.json()
    return [i["nome"] for i in resposta.json()]


@pytest.fixture
def fazenda(client: TestClient) -> dict[str, Any]:
    """Três insumos: a ureia abaixo do mínimo (alerta alto), o calcário sem alerta e o
    glifosato sem categoria e sem alerta."""
    adubo = post(client, "categorias", nome="Fertilizante")
    corretivo = post(client, "categorias", nome="Corretivo de solo")
    ureia = post(
        client,
        "insumos",
        nome="Uréia agrícola",
        unidade="kg",
        estoque_minimo=100,
        categoria_id=adubo["id"],
    )
    calcario = post(
        client, "insumos", nome="Calcário dolomítico", unidade="t", categoria_id=corretivo["id"]
    )
    glifosato = post(client, "insumos", nome="Glifosato", unidade="L")
    return {
        "adubo": adubo,
        "corretivo": corretivo,
        "ureia": ureia,
        "calcario": calcario,
        "glifosato": glifosato,
    }


def test_insumos_sem_filtro_como_sempre(client: TestClient, fazenda: dict[str, Any]) -> None:
    assert nomes(client) == ["Calcário dolomítico", "Glifosato", "Uréia agrícola"]


def test_insumos_por_categoria(client: TestClient, fazenda: dict[str, Any]) -> None:
    assert nomes(client, f"?categoria_id={fazenda['adubo']['id']}") == ["Uréia agrícola"]
    # Categoria sem insumo (ou que não existe): lista vazia, não erro. É um filtro.
    assert nomes(client, "?categoria_id=999") == []


@pytest.mark.parametrize(
    ("busca", "esperado"),
    [
        ("ureia", ["Uréia agrícola"]),  # sem o acento que o nome tem
        ("URÉIA", ["Uréia agrícola"]),  # sem diferenciar maiúsculas
        ("calcario", ["Calcário dolomítico"]),
        ("agricola", ["Uréia agrícola"]),  # no meio do nome
        ("  glifo ", ["Glifosato"]),  # espaços nas pontas não contam
        ("a", ["Calcário dolomítico", "Glifosato", "Uréia agrícola"]),
        ("soja", []),
    ],
)
def test_busca_pelo_nome_sem_acento_nem_maiusculas(
    client: TestClient, fazenda: dict[str, Any], busca: str, esperado: list[str]
) -> None:
    assert nomes(client, f"?busca={busca}") == esperado


def test_insumos_por_alerta(client: TestClient, fazenda: dict[str, Any]) -> None:
    # A ureia está abaixo do mínimo: alerta alto. Os outros não têm alerta.
    assert nomes(client, "?com_alerta=true") == ["Uréia agrícola"]
    assert nomes(client, "?com_alerta=false") == ["Calcário dolomítico", "Glifosato"]
    assert nomes(client, "?gravidade=alta") == ["Uréia agrícola"]
    assert nomes(client, "?gravidade=media") == []
    # Os filtros se somam.
    consulta = f"?gravidade=alta&categoria_id={fazenda['corretivo']['id']}"
    assert nomes(client, consulta) == []


@pytest.mark.parametrize(
    "consulta", ["?gravidade=urgente", "?com_alerta=talvez", "?categoria_id=x", "?busca="]
)
def test_filtro_de_insumo_invalido_e_422(
    client: TestClient, fazenda: dict[str, Any], consulta: str
) -> None:
    assert client.get(f"/api/v1/insumos{consulta}").status_code == 422


@pytest.fixture
def lancamentos(
    client: TestClient, fazenda: dict[str, Any], db: Session, criar_usuario: CriarUsuario
) -> dict[str, Any]:
    """Uma história curta, com um lançamento de cada jeito. A retirada de 20 dias atrás é
    do Zé, logado; o resto, sem login."""
    norte = post(client, "talhoes", nome="Talhão Norte", area_ha=10)
    revenda = post(client, "fornecedores", nome="Agropecuária Ariquemes")
    ze = criar_usuario("ze", nome="Zé do Trator")
    token = autenticacao.abrir_sessao(db, ze, None)[0]
    ureia, calcario = fazenda["ureia"]["id"], fazenda["calcario"]["id"]

    def lancar(cabecalho: dict[str, str] | None = None, **corpo: Any) -> dict[str, Any]:
        resposta = client.post("/api/v1/movimentacoes", json=corpo, headers=cabecalho or {})
        assert resposta.status_code == 201, resposta.json()
        return resposta.json()

    lancar(
        insumo_id=ureia,
        tipo="entrada",
        data=dia(30),
        quantidade=100,
        valor_unitario=3,
        fornecedor_id=revenda["id"],
    )
    lancar(insumo_id=calcario, tipo="entrada", data=dia(25), quantidade=2)
    lancar(
        {"Authorization": f"Bearer {token}"},
        insumo_id=ureia,
        tipo="saida",
        data=dia(20),
        quantidade=10,
        talhao_id=norte["id"],
    )
    lancar(insumo_id=calcario, tipo="saida", data=dia(15), quantidade=1)
    lancar(insumo_id=ureia, tipo="saida", data=dia(10), quantidade=5)
    lancar(insumo_id=ureia, tipo="saida", data=dia(5), quantidade=2, motivo="descarte")
    # Saldo 83 no dia, contados 80: a falta de 3 vira um ajuste de inventário.
    contagem = client.post(
        f"/api/v1/insumos/{ureia}/inventario", json={"quantidade_contada": 80, "data": dia(3)}
    )
    assert contagem.json()["diferenca"] == -3
    return {"norte": norte, "revenda": revenda, "ze": ze}


def movimentacoes(client: TestClient, consulta: str = "") -> list[tuple[str, str, float]]:
    resposta = client.get(f"/api/v1/movimentacoes{consulta}")
    assert resposta.status_code == 200, resposta.json()
    return [(m["data"], m["tipo"], m["quantidade"]) for m in resposta.json()]


def test_movimentacoes_sem_filtro_como_sempre_e_com_o_total(
    client: TestClient, lancamentos: dict[str, Any]
) -> None:
    resposta = client.get("/api/v1/movimentacoes")

    # A lista continua lista, a mais recente primeiro; o total vai no cabeçalho.
    assert [m["quantidade"] for m in resposta.json()] == [3, 2, 5, 1, 10, 2, 100]
    assert resposta.headers["X-Total-Count"] == "7"


@pytest.mark.parametrize(
    ("consulta", "esperado"),
    [
        ("?tipo=entrada", [(dia(25), "entrada", 2), (dia(30), "entrada", 100)]),
        ("?motivo=descarte", [(dia(5), "saida", 2)]),
        ("?motivo=inventario", [(dia(3), "saida", 3)]),
        # Sem motivo: a retirada para uso (e, na entrada, a compra).
        (
            "?tipo=saida&motivo=nenhum",
            [(dia(10), "saida", 5), (dia(15), "saida", 1), (dia(20), "saida", 10)],
        ),
        (
            "?desde={d15}&ate={d5}",
            [(dia(5), "saida", 2), (dia(10), "saida", 5), (dia(15), "saida", 1)],
        ),
        ("?ate={d25}", [(dia(25), "entrada", 2), (dia(30), "entrada", 100)]),
        ("?busca=calcario", [(dia(15), "saida", 1), (dia(25), "entrada", 2)]),
        ("?busca=soja", []),
    ],
)
def test_movimentacoes_filtradas(
    client: TestClient,
    lancamentos: dict[str, Any],
    consulta: str,
    esperado: list[tuple[str, str, float]],
) -> None:
    consulta = consulta.format(d15=dia(15), d5=dia(5), d25=dia(25))
    resposta = client.get(f"/api/v1/movimentacoes{consulta}")

    assert [(m["data"], m["tipo"], m["quantidade"]) for m in resposta.json()] == esperado
    assert resposta.headers["X-Total-Count"] == str(len(esperado))


def test_movimentacoes_por_cadastro(
    client: TestClient, fazenda: dict[str, Any], lancamentos: dict[str, Any]
) -> None:
    corretivo = fazenda["corretivo"]["id"]
    assert movimentacoes(client, f"?categoria_id={corretivo}") == [
        (dia(15), "saida", 1),
        (dia(25), "entrada", 2),
    ]
    assert movimentacoes(client, f"?talhao_id={lancamentos['norte']['id']}") == [
        (dia(20), "saida", 10)
    ]
    assert movimentacoes(client, f"?fornecedor_id={lancamentos['revenda']['id']}") == [
        (dia(30), "entrada", 100)
    ]
    assert movimentacoes(client, f"?usuario_id={lancamentos['ze'].id}") == [(dia(20), "saida", 10)]
    # Os filtros se somam; o insumo_id de antes continua valendo.
    ureia = fazenda["ureia"]["id"]
    assert movimentacoes(client, f"?insumo_id={ureia}&tipo=saida&desde={dia(10)}") == [
        (dia(3), "saida", 3),
        (dia(5), "saida", 2),
        (dia(10), "saida", 5),
    ]


def test_paginas_em_ordem_estavel_com_o_total(client: TestClient, fazenda: dict[str, Any]) -> None:
    # Muitas no mesmo dia: a ordem entre elas é a do id (a mais recente primeiro), e
    # nenhuma se repete nem some de uma página para a outra.
    ureia = fazenda["ureia"]["id"]
    for quantidade in range(1, 8):
        post(
            client,
            "movimentacoes",
            insumo_id=ureia,
            tipo="entrada",
            data=dia(1),
            quantidade=quantidade,
        )
    post(client, "movimentacoes", insumo_id=ureia, tipo="entrada", data=dia(0), quantidade=99)

    paginas = []
    for deslocamento in (0, 3, 6, 9):
        resposta = client.get(f"/api/v1/movimentacoes?limite=3&deslocamento={deslocamento}")
        assert resposta.headers["X-Total-Count"] == "8"
        paginas.append([m["quantidade"] for m in resposta.json()])

    assert paginas == [[99, 7, 6], [5, 4, 3], [2, 1], []]


@pytest.mark.parametrize(
    "consulta",
    [
        "?desde={d5}&ate={d15}",  # invertido
        "?deslocamento=-1",
        "?limite=0",
        "?tipo=troca",
        "?motivo=perda",
        "?busca=",
        "?desde=ontem",
    ],
)
def test_filtro_de_movimentacao_invalido_e_422(client: TestClient, consulta: str) -> None:
    resposta = client.get(f"/api/v1/movimentacoes{consulta.format(d5=dia(5), d15=dia(15))}")
    assert resposta.status_code == 422
