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

    assert previa["erros"] == ["Faltam as colunas: data, insumo, tipo, quantidade."]
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
