"""Importação de movimentações por planilha CSV (POST /importacoes)."""

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.core.relogio import hoje

HOJE = hoje()


def br(dias_atras: int) -> str:
    """Data como o Excel brasileiro escreve: DD/MM/AAAA."""
    return f"{HOJE - timedelta(days=dias_atras):%d/%m/%Y}"


def importar(client: TestClient, conteudo: str, *, confirmar: bool = False) -> dict[str, Any]:
    resposta = client.post(
        "/api/v1/importacoes", json={"conteudo": conteudo, "confirmar": confirmar}
    )
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


# Como sai do Excel em português: ponto e vírgula, vírgula decimal, BOM no início.
PLANILHA = (
    "\ufeffData;Insumo;Unidade;Tipo;Quantidade;Validade\r\n"
    f"{br(30)};Ureia agrícola;kg;entrada;1.000;\r\n"
    f"{br(20)};ureia agrícola;;saída;25,5;\r\n"
    f"{br(10)};Ivermectina 1%;L;compra;5;{br(-200)}\r\n"
    ";;;;;\r\n"  # linha em branco que o Excel deixa no fim
)


def test_previa_resume_e_nao_grava(client: TestClient) -> None:
    previa = importar(client, PLANILHA)

    assert previa == {
        "linhas": 3,
        "entradas": 2,
        "saidas": 1,
        # A grafia da primeira linha vale; "ureia agrícola" é o mesmo insumo.
        "insumos_novos": ["Ureia agrícola", "Ivermectina 1%"],
        "primeira_data": str(HOJE - timedelta(days=30)),
        "ultima_data": str(HOJE - timedelta(days=10)),
        "ja_lancadas": 0,
        "erros": [],
        "importado": False,
    }
    assert client.get("/api/v1/insumos").json() == []


def test_confirmar_grava_insumos_e_movimentacoes(client: TestClient) -> None:
    resultado = importar(client, PLANILHA, confirmar=True)

    assert resultado["importado"] is True
    estoques = {i["nome"]: i["estoque_atual"] for i in client.get("/api/v1/insumos").json()}
    assert estoques == {"Ivermectina 1%": 5, "Ureia agrícola": 974.5}
    validades = [m["validade"] for m in client.get("/api/v1/movimentacoes").json()]
    assert str(HOJE + timedelta(days=200)) in validades


def test_reimportar_avisa_que_ja_foi_lancada(client: TestClient) -> None:
    importar(client, PLANILHA, confirmar=True)

    previa = importar(client, PLANILHA)

    assert (previa["ja_lancadas"], previa["insumos_novos"]) == (3, [])


def test_insumo_existente_com_outra_unidade_e_erro(client: TestClient) -> None:
    client.post("/api/v1/insumos", json={"nome": "Calcário", "unidade": "t"})
    planilha = f"data,insumo,unidade,tipo,quantidade\n{br(1)},CALCÁRIO,kg,entrada,2.5\n"

    previa = importar(client, planilha)

    assert previa["erros"] == ['Linha 2: "CALCÁRIO" já está cadastrado em t, não em kg.']


def test_com_um_erro_nada_e_gravado(client: TestClient) -> None:
    planilha = (
        "data;insumo;unidade;tipo;quantidade;validade\n"
        f"{br(5)};Ureia;kg;entrada;100;\n"
        f"31/02/2026;Ureia;kg;saida;10;\n"
        f"{br(-1)};Ureia;kg;saida;10;\n"
        f"{br(3)};Ureia;kg;devolução;10;\n"
        f"{br(3)};Ureia;kg;saida;0;\n"
        f"{br(3)};Ureia;kg;saida;dez;\n"
        f"{br(3)};Ureia;kg;saida;5;{br(-30)}\n"
        f"{br(3)};Glifosato;;entrada;5;\n"
        f"{br(3)};;kg;entrada;5;\n"
    )

    resultado = importar(client, planilha, confirmar=True)

    assert resultado["importado"] is False
    assert resultado["erros"] == [
        'Linha 3: data "31/02/2026" inválida; use DD/MM/AAAA.',
        "Linha 4: data no futuro.",
        'Linha 5: tipo "devolução" desconhecido; use entrada ou saída.',
        "Linha 6: quantidade deve ser maior que zero.",
        'Linha 7: quantidade "dez" não é um número.',
        "Linha 8: validade só se informa numa entrada.",
        'Linha 9: "Glifosato" não está cadastrado; informe a unidade para cadastrá-lo.',
        "Linha 10: falta o nome do insumo.",
    ]
    assert client.get("/api/v1/insumos").json() == []


def test_planilha_sem_as_colunas_do_modelo(client: TestClient) -> None:
    previa = importar(client, "produto;qtd\nUreia;10\n")

    assert previa["erros"] == ["Faltam as colunas: data, insumo, tipo, quantidade."]
    assert importar(client, "")["erros"] == ["O arquivo está vazio."]
    so_cabecalho = importar(client, "data;insumo;tipo;quantidade\n")
    assert so_cabecalho["erros"] == ["Nenhuma movimentação na planilha."]
