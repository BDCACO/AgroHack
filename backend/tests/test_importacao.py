"""Importação de movimentações por planilha CSV (POST /importacoes)."""

import base64
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

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
        # A grafia da primeira linha vale; "ureia agrícola" é o mesmo insumo. O total de
        # cada um é onde o produtor percebe um erro de escala antes de gravar.
        "insumos": [
            {
                "nome": "Ureia agrícola",
                "unidade": "kg",
                "novo": True,
                "entradas": 1000,
                "saidas": 25.5,
            },
            {"nome": "Ivermectina 1%", "unidade": "L", "novo": True, "entradas": 5, "saidas": 0},
        ],
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

    assert previa["ja_lancadas"] == 3
    assert [i["novo"] for i in previa["insumos"]] == [False, False]


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

    assert previa["erros"] == [
        "Faltam as colunas: data, insumo, tipo, quantidade. A primeira linha precisa ter os "
        "títulos — use a planilha modelo."
    ]
    assert importar(client, "")["erros"] == ["O arquivo está vazio."]
    so_cabecalho = importar(client, "data;insumo;tipo;quantidade\n")
    assert so_cabecalho["erros"] == ["Nenhuma movimentação na planilha."]


def _quantidades(client: TestClient, planilha: str) -> dict[str, tuple[float, float]]:
    previa = importar(client, planilha)
    assert previa["erros"] == [], previa["erros"]
    return {i["nome"]: (i["entradas"], i["saidas"]) for i in previa["insumos"]}


def test_formato_dos_numeros_e_decidido_pela_planilha_inteira(client: TestClient) -> None:
    cabecalho = "data;insumo;unidade;tipo;quantidade\n"
    # Ponto e vírgula, sem pista: o padrão do Excel em português — ponto é milhar.
    assert _quantidades(client, cabecalho + f"{br(1)};A;kg;entrada;1.000\n") == {"A": (1000, 0)}
    # "0.250" e "2.5" só podem ter ponto decimal; então "1.000" na mesma planilha é 1.
    planilha = cabecalho + f"{br(2)};A;kg;entrada;0.250\n{br(1)};B;kg;entrada;1.000\n"
    assert _quantidades(client, planilha) == {"A": (0.25, 0), "B": (1, 0)}
    # Separada por vírgula, sem pista: o padrão internacional — ponto é decimal.
    planilha = f"data,insumo,unidade,tipo,quantidade\n{br(1)},A,kg,entrada,25.500\n"
    assert _quantidades(client, planilha) == {"A": (25.5, 0)}
    planilha = f'data,insumo,unidade,tipo,quantidade\n{br(1)},A,kg,entrada,"1,234.5"\n'
    assert _quantidades(client, planilha) == {"A": (1234.5, 0)}


def test_planilha_que_mistura_virgula_e_ponto_decimal(client: TestClient) -> None:
    planilha = (
        f"data;insumo;unidade;tipo;quantidade\n{br(2)};A;kg;entrada;25,5\n{br(1)};A;kg;saida;2.5\n"
    )

    assert importar(client, planilha)["erros"] == [
        "Quantidades com vírgula decimal (linha 2: 25,5) e com ponto decimal (linha 3: 2.5) "
        "na mesma planilha: use um formato só."
    ]


def test_linha_com_celulas_a_mais_ou_aspa_sem_fechar(client: TestClient) -> None:
    planilha = (
        "data,insumo,unidade,tipo,quantidade\n"
        f"{br(3)},Ureia,kg,entrada,25,5\n"  # vírgula decimal num arquivo separado por vírgula
        f'{br(2)},"Ureia,kg,entrada,10\n'
        f"{br(1)},Ureia,kg,saida,1\n"
    )

    assert importar(client, planilha)["erros"] == [
        "Linha 2: 6 colunas, mas o cabeçalho tem 5. Se a quantidade tem vírgula decimal, "
        "separe as colunas por ponto e vírgula ou ponha o número entre aspas.",
        'Linha 3: aspa (") sem fechar; o resto do arquivo virou uma célula só.',
    ]


def test_aspa_sem_fechar_num_arquivo_grande_nao_derruba_a_api(client: TestClient) -> None:
    planilha = "data;insumo;unidade;tipo;quantidade\n" + f'{br(1)};"Ureia' + "x" * 200_000

    [erro] = importar(client, planilha)["erros"]

    assert erro.startswith("Linha 2: ")


def test_nomes_que_so_diferem_em_maiusculas_no_cadastro(client: TestClient) -> None:
    client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"})
    client.post("/api/v1/insumos", json={"nome": "UREIA", "unidade": "kg"})

    erros = importar(client, f"data;insumo;tipo;quantidade\n{br(1)};ureia;entrada;5\n")["erros"]

    assert erros == [
        'Linha 2: há mais de um insumo cadastrado como "ureia" (UREIA, Ureia); '
        "renomeie um deles na tela de Insumos."
    ]


# --- Planilha do Excel (.xlsx) ---------------------------------------------------------

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def baixar_modelo(client: TestClient) -> Workbook:
    resposta = client.get("/api/v1/importacoes/modelo.xlsx")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == XLSX
    assert 'filename="modelo-campocerto.xlsx"' in resposta.headers["content-disposition"]
    return load_workbook(BytesIO(resposta.content))


def importar_xlsx(client: TestClient, livro: Workbook, *, confirmar: bool = False) -> Any:
    arquivo = BytesIO()
    livro.save(arquivo)
    xlsx = base64.b64encode(arquivo.getvalue()).decode()
    resposta = client.post("/api/v1/importacoes", json={"xlsx": xlsx, "confirmar": confirmar})
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


def preencher(aba: Any, linhas: list[tuple]) -> None:
    for numero, linha in enumerate(linhas, start=2):
        for coluna, valor in enumerate(linha, start=1):
            aba.cell(numero, coluna, valor)


def em_datetime(dias_atras: int) -> datetime:
    return datetime.combine(HOJE - timedelta(days=dias_atras), datetime.min.time())


def test_planilha_modelo_vem_formatada_e_com_os_insumos(client: TestClient) -> None:
    client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"})

    livro = baixar_modelo(client)

    assert livro.sheetnames == ["Movimentações", "Como preencher", "Exemplo", "Insumos cadastrados"]
    aba = livro["Movimentações"]
    assert [c.value for c in aba[1]] == [
        "data",
        "insumo",
        "unidade",
        "tipo",
        "quantidade",
        "validade",
    ]
    assert aba["A1"].font.bold
    assert aba["A1"].comment.text.startswith("Dia em que a compra chegou")
    assert aba.freeze_panes == "A2"
    assert aba["A2"].number_format == aba["F1001"].number_format == "DD/MM/YYYY"
    listas = {str(v.sqref): v.formula1 for v in aba.data_validations.dataValidation}
    assert listas["B2:B1001"] == "'Insumos cadastrados'!$A$2:$A$2"
    assert listas["D2:D1001"] == '"entrada,saída"'
    assert livro["Insumos cadastrados"]["A2"].value == "Ureia"


def test_modelo_preenchido_volta_pela_importacao(client: TestClient) -> None:
    client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"})
    livro = baixar_modelo(client)
    preencher(
        livro["Movimentações"],
        [
            # Data e número com tipo, como o Excel grava a célula formatada...
            (em_datetime(10), "Ureia", None, "entrada", 1000, None),
            (em_datetime(5), "ureia", "kg", "saída", 25.5, None),
            # ...e digitados como texto, que também valem.
            (br(3), "Vacina contra aftosa", "dose", "entrada", "12,5", br(-100)),
        ],
    )

    previa = importar_xlsx(client, livro)

    assert previa["erros"] == []
    assert previa["insumos"] == [
        {"nome": "Ureia", "unidade": "kg", "novo": False, "entradas": 1000, "saidas": 25.5},
        {
            "nome": "Vacina contra aftosa",
            "unidade": "dose",
            "novo": True,
            "entradas": 12.5,
            "saidas": 0,
        },
    ]
    assert importar_xlsx(client, livro, confirmar=True)["importado"] is True


def test_o_exemplo_do_modelo_importa_sem_erro(client: TestClient) -> None:
    exemplo = Workbook()
    for linha in baixar_modelo(client)["Exemplo"].iter_rows(values_only=True):
        exemplo.active.append(linha)

    previa = importar_xlsx(client, exemplo)

    assert (previa["erros"], previa["linhas"]) == ([], 3)


def test_modelo_vazio_nao_tem_o_que_importar(client: TestClient) -> None:
    assert importar_xlsx(client, baixar_modelo(client))["erros"] == [
        "Nenhuma movimentação na planilha."
    ]


def test_erros_do_xlsx_apontam_a_linha_do_excel(client: TestClient) -> None:
    livro = Workbook()
    aba = livro.active
    aba.append(["Data", "Insumo", "Unidade", "Tipo", "Quantidade"])
    preencher(
        aba,
        [
            (em_datetime(5), "Ureia", "kg", "entrada", 10),
            (),  # linha 3 em branco: pulada, mas a numeração segue a do Excel
            (em_datetime(4), "Ureia", "kg", "devolução", 5),
            (46000, "Ureia", "kg", "entrada", 5),  # número de série numa célula sem formato
            (em_datetime(2), "Ureia", "kg", "entrada", 1, None, None, "anotação"),
        ],
    )

    assert importar_xlsx(client, livro)["erros"] == [
        'Linha 4: tipo "devolução" desconhecido; use entrada ou saída.',
        'Linha 5: data "46000" inválida; use DD/MM/AAAA.',
        "Linha 6: há valores em colunas sem título; apague-os ou dê um título à coluna.",
    ]


def test_arquivo_que_nao_e_xlsx(client: TestClient) -> None:
    resposta = client.post(
        "/api/v1/importacoes", json={"xlsx": base64.b64encode(b"isto nao e uma planilha").decode()}
    )

    [erro] = resposta.json()["erros"]
    assert erro.startswith("Não deu para abrir a planilha do Excel.")


def test_pedido_com_os_dois_formatos_ou_nenhum(client: TestClient) -> None:
    xlsx = base64.b64encode(b"x").decode()
    for corpo in ({}, {"conteudo": "a", "xlsx": xlsx}):
        assert client.post("/api/v1/importacoes", json=corpo).status_code == 422
