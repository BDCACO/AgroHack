"""Entradas que o SQLite aceita e o PostgreSQL recusa com erro de dado, e que viravam 500.
Vieram da revisão de segurança."""

import uuid

import httpx
import pytest

from app.core.relogio import hoje

# Maior que o `integer` do PostgreSQL (2^31 − 1).
GRANDE_DEMAIS = 2**40


def test_login_com_caractere_nulo_e_recusado_como_login_inexistente(api: httpx.Client) -> None:
    # Rota pública: um 500 aqui deixaria qualquer um na rede encher o log de erros. E a
    # resposta tem de ser a mesma do login que não existe, para não revelar nada.
    nulo = api.post("/auth/entrar", json={"login": "ma\u0000ria", "senha": "qualquer-coisa"})
    inexistente = api.post("/auth/entrar", json={"login": "maria", "senha": "qualquer-coisa"})

    assert nulo.status_code == inexistente.status_code == 401
    assert nulo.json() == inexistente.json()


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("GET", f"/insumos/{GRANDE_DEMAIS}"),
        ("DELETE", f"/movimentacoes/{GRANDE_DEMAIS}"),
        ("GET", f"/talhoes/{GRANDE_DEMAIS}"),
        ("GET", f"/movimentacoes?insumo_id={GRANDE_DEMAIS}"),
    ],
)
def test_id_grande_demais_nao_vira_500(api: httpx.Client, metodo: str, caminho: str) -> None:
    resposta = api.request(metodo, caminho)

    assert resposta.status_code in (404, 422), resposta.text


def test_item_do_lote_com_id_grande_demais_e_recusado_sem_derrubar_o_lote(
    api: httpx.Client,
) -> None:
    insumo = api.post("/insumos", json={"nome": "Ureia", "unidade": "kg"}).json()["id"]

    def item(insumo_id: int) -> dict[str, object]:
        return {
            "uuid": str(uuid.uuid4()),
            "insumo_id": insumo_id,
            "tipo": "entrada",
            "data": str(hoje()),
            "quantidade": 1,
        }

    resposta = api.post(
        "/movimentacoes/lote", json={"movimentacoes": [item(insumo), item(GRANDE_DEMAIS)]}
    )

    assert resposta.status_code == 200, resposta.text
    assert [r["situacao"] for r in resposta.json()["resultados"]] == ["gravada", "recusada"]
