"""Relatório em Excel (GET /relatorio.xlsx), com a fazenda de demonstração."""

import base64
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.demo import carregar


def baixar(client: TestClient) -> tuple[bytes, Workbook]:
    resposta = client.get("/api/v1/relatorio.xlsx")
    assert resposta.status_code == 200
    nome = f'filename="relatorio-campocerto-{hoje()}.xlsx"'
    assert nome in resposta.headers["content-disposition"]
    return resposta.content, load_workbook(BytesIO(resposta.content))


def test_relatorio_traz_alertas_reposicao_e_estoque(client: TestClient, db: Session) -> None:
    carregar(db, hoje())

    _, livro = baixar(client)

    assert livro.sheetnames == ["Resumo", "Alertas", "Reposição", "Estoque", "Movimentações"]
    alertas = list(livro["Alertas"].iter_rows(min_row=2, values_only=True))
    # Os mais graves primeiro, cada um com a conta que o justifica.
    assert [a[0] for a in alertas] == ["Urgente"] * 2 + ["Atenção"] * 3 + ["Observar"] * 2
    assert ("Urgente", "Ureia agrícola", "Risco de falta") in {a[:3] for a in alertas}
    assert all(a[3] for a in alertas)
    reposicao = list(livro["Reposição"].iter_rows(min_row=2, values_only=True))
    assert reposicao[0][:3] == ("Ureia agrícola", 662, "kg")
    estoque = {linha[0]: linha for linha in livro["Estoque"].iter_rows(min_row=2, values_only=True)}
    assert len(estoque) == 7
    assert estoque["Semente de milho híbrido"][7] == "Sem alertas"
    assert livro["Resumo"]["A1"].value == "Situação do estoque"


def test_movimentacoes_do_relatorio_voltam_pela_importacao(client: TestClient, db: Session) -> None:
    carregar(db, hoje())
    [ivermectina] = [i for i in client.get("/api/v1/insumos").json() if "Ivermectina" in i["nome"]]
    descarte = {"insumo_id": ivermectina["id"], "tipo": "saida", "motivo": "descarte"}
    client.post("/api/v1/movimentacoes", json=descarte | {"data": str(hoje()), "quantidade": 4})
    insumos = {i["nome"]: i for i in client.get("/api/v1/insumos").json()}
    ureia, sal = insumos["Ureia agrícola"], insumos["Sal mineral 80P"]
    for insumo, diferenca in ((ureia, 5), (sal, -5)):
        contagem = {"quantidade_contada": insumo["estoque_atual"] + diferenca}
        client.post(f"/api/v1/insumos/{insumo['id']}/inventario", json=contagem)
    conteudo, livro = baixar(client)
    linhas = livro["Movimentações"].max_row - 1
    tipos = {linha[3] for linha in livro["Movimentações"].iter_rows(min_row=2, values_only=True)}
    assert tipos == {"entrada", "saída", "descarte", "sobra", "falta"}

    resposta = client.post(
        "/api/v1/importacoes", json={"xlsx": base64.b64encode(conteudo).decode()}
    )

    # É a cópia de segurança: tudo já está no sistema, e a prévia avisa.
    previa = resposta.json()
    assert (previa["erros"], previa["linhas"], previa["ja_lancadas"]) == ([], linhas, linhas)


def test_relatorio_sem_nada_cadastrado(client: TestClient) -> None:
    _, livro = baixar(client)

    assert livro["Alertas"]["A2"].value == "Nenhum alerta hoje."
