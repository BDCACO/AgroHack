"""Filtros, busca e paginação nas listas de insumos e de movimentações. Todos opcionais:
sem eles, a resposta é a de sempre (o site e o app de hoje não os mandam)."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.relogio import hoje

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
