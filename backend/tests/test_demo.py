"""A fazenda de demonstração acende o que promete — se um limiar do motor mudar, este
teste avisa que o roteiro da apresentação precisa ser revisto."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.demo import carregar, limpar
from app.models import Movimentacao
from tests.test_eventos_de_auditoria import eventos


def test_cada_insumo_acende_os_alertas_do_roteiro(client: TestClient, db: Session) -> None:
    carregar(db, hoje())

    insumos = client.get("/api/v1/insumos").json()

    assert {i["nome"]: {a["tipo"] for a in i["analise"]["alertas"]} for i in insumos} == {
        "Calcário dolomítico": {"excesso"},
        "Fungicida azoxistrobina": {"baixa_movimentacao"},
        "Glifosato 480": {"vencimento_proximo"},
        "Ivermectina 1%": {"vencido"},
        "Sal mineral 80P": {"consumo_incomum"},
        "Semente de milho híbrido": set(),
        "Ureia agrícola": {"risco_de_falta", "abaixo_do_minimo"},
    }
    assert all(i["demonstracao"] for i in insumos)


def test_a_demonstracao_fala_em_reais(client: TestClient, db: Session) -> None:
    carregar(db, hoje())

    insumos = {i["nome"]: i for i in client.get("/api/v1/insumos").json()}

    assert all(i["custo_medio"] for i in insumos.values())
    alertas = {a["tipo"]: a for i in insumos.values() for a in i["analise"]["alertas"]}
    for tipo in ("vencido", "vencimento_proximo", "excesso"):
        assert alertas[tipo]["valor"] > 0
        assert "R$" in alertas[tipo]["justificativa"]
    # Ureia em sacos de 50 kg: a compra sugerida fecha sacos e diz quanto custa.
    reposicao = insumos["Ureia agrícola"]["analise"]["reposicao"]
    assert insumos["Ureia agrícola"]["embalagem"] == 50
    assert reposicao["quantidade"] % 50 == 0
    assert reposicao["justificativa"].startswith("Pedir hoje 14 embalagens de 50 kg")
    assert reposicao["custo_estimado"] > 0
    assert client.get("/api/v1/resumo").json()["insumos_sem_preco"] == 0


def test_um_talhao_em_carencia_no_dia_da_apresentacao(client: TestClient, db: Session) -> None:
    carregar(db, hoje())

    talhoes = {t["nome"]: t for t in client.get("/api/v1/talhoes").json()}

    assert set(talhoes) == {"Talhão Norte", "Talhão Sul", "Pasto 1"}
    assert all(t["demonstracao"] for t in talhoes.values())
    assert [nome for nome, t in talhoes.items() if t["em_carencia"]] == ["Talhão Norte"]
    # O glifosato de 2 dias atrás, com 7 dias de carência.
    norte = talhoes["Talhão Norte"]
    assert norte["colheita_liberada_em"] == str(hoje() + timedelta(days=5))
    assert "Glifosato 480 aplicado em" in norte["alertas"][0]["justificativa"]
    # Tudo tem preço: o custo por hectare de cada talhão sai em reais.
    assert all(t["custo_por_ha"] for t in talhoes.values())
    # O calcário vai para o pasto sem carência cadastrada: a limitação diz.
    assert any("(Calcário dolomítico)" in t for t in talhoes["Pasto 1"]["limitacoes"])
    assert client.get("/api/v1/resumo").json()["talhoes_em_carencia"] == 1


def test_limpar_apaga_so_a_demonstracao(client: TestClient, db: Session) -> None:
    real = client.post("/api/v1/insumos", json={"nome": "Adubo da fazenda", "unidade": "kg"})
    client.post("/api/v1/talhoes", json={"nome": "Talhão da fazenda", "area_ha": 30})
    carregar(db, hoje())
    carregar(db, hoje())  # recarregar substitui, não duplica

    limpar(db)

    assert [i["nome"] for i in client.get("/api/v1/insumos").json()] == ["Adubo da fazenda"]
    assert [t["nome"] for t in client.get("/api/v1/talhoes").json()] == ["Talhão da fazenda"]
    assert real.json()["demonstracao"] is False
    assert db.scalar(select(func.count()).select_from(Movimentacao)) == 0
    assert client.get("/api/v1/fornecedores").json() == []
    assert client.get("/api/v1/pedidos").json() == []


def test_limpar_mantem_talhao_com_aplicacao_de_insumo_real(client: TestClient, db: Session) -> None:
    carregar(db, hoje())
    norte = next(t for t in client.get("/api/v1/talhoes").json() if t["nome"] == "Talhão Norte")
    real = client.post("/api/v1/insumos", json={"nome": "Adubo da fazenda", "unidade": "kg"})
    aplicacao = {"tipo": "saida", "data": str(hoje()), "quantidade": 1, "talhao_id": norte["id"]}
    client.post("/api/v1/movimentacoes", json=aplicacao | {"insumo_id": real.json()["id"]})

    limpar(db)

    # Apagá-lo levaria o registro de onde o adubo real foi aplicado.
    assert [t["nome"] for t in client.get("/api/v1/talhoes").json()] == ["Talhão Norte"]
    # E deixa de ser demonstração: guarda dado real. A próxima carga o reaproveita, em
    # vez de quebrar no nome único ao recriar o "Talhão Norte".
    assert client.get("/api/v1/talhoes").json()[0]["demonstracao"] is False

    carregar(db, hoje())

    nomes = sorted(t["nome"] for t in client.get("/api/v1/talhoes").json())
    assert nomes == ["Pasto 1", "Talhão Norte", "Talhão Sul"]
    insumos = client.get("/api/v1/insumos").json()
    assert sum(1 for i in insumos if i["demonstracao"]) == 7


def test_carregar_com_talhao_real_de_mesmo_nome(client: TestClient, db: Session) -> None:
    client.post("/api/v1/talhoes", json={"nome": "Pasto 1", "area_ha": 30, "cultura": "Pasto"})

    carregar(db, hoje())

    pastos = [t for t in client.get("/api/v1/talhoes").json() if t["nome"] == "Pasto 1"]
    assert [(t["area_ha"], t["demonstracao"]) for t in pastos] == [(30, False)]


def test_compras_com_fornecedor_e_um_pedido_a_caminho(client: TestClient, db: Session) -> None:
    carregar(db, hoje())

    fornecedores = {f["nome"]: f for f in client.get("/api/v1/fornecedores").json()}
    assert set(fornecedores) == {"Revenda Boa Safra", "Cooperativa Vale Verde", "AgroVet Pioneiro"}
    assert all(f["demonstracao"] for f in fornecedores.values())
    insumos = {i["nome"]: i for i in client.get("/api/v1/insumos").json()}
    # A ureia foi comprada nas duas revendas: o produtor compara o preço pago a cada uma.
    ureia = client.get(f"/api/v1/insumos/{insumos['Ureia agrícola']['id']}").json()
    assert [(p["fornecedor"], p["preco_medio"]) for p in ureia["precos_por_fornecedor"]] == [
        ("Cooperativa Vale Verde", 2.9),
        ("Revenda Boa Safra", 3.3),
    ]
    # O pedido aberto é do sal mineral, e não da ureia: o roteiro da ureia (risco de falta,
    # pedir hoje) não muda.
    [pedido] = client.get("/api/v1/pedidos").json()
    assert (pedido["situacao"], pedido["fornecedor"]) == ("aberto", "AgroVet Pioneiro")
    assert [(i["insumo"], i["quantidade"]) for i in pedido["itens"]] == [("Sal mineral 80P", 500)]
    assert pedido["previsto_para"] == str(hoje() + timedelta(days=5))
    assert insumos["Sal mineral 80P"]["em_pedido"] == 500
    assert insumos["Ureia agrícola"]["em_pedido"] == 0
    assert insumos["Ureia agrícola"]["analise"]["reposicao"]["pedir_hoje"] is True
    # A sugestão de pedido manda a ureia para a revenda da última compra.
    grupos = client.get("/api/v1/pedidos/sugestao").json()["grupos"]
    assert [(g["fornecedor"], [i["insumo"] for i in g["itens"]]) for g in grupos] == [
        ("Revenda Boa Safra", ["Ureia agrícola"])
    ]


def test_limpar_mantem_fornecedor_com_compra_real(client: TestClient, db: Session) -> None:
    carregar(db, hoje())
    revenda = next(
        f for f in client.get("/api/v1/fornecedores").json() if f["nome"] == "Revenda Boa Safra"
    )
    real = client.post("/api/v1/insumos", json={"nome": "Adubo da fazenda", "unidade": "kg"})
    compra = {"tipo": "entrada", "data": str(hoje()), "quantidade": 10}
    compra |= {"insumo_id": real.json()["id"], "fornecedor_id": revenda["id"]}
    client.post("/api/v1/movimentacoes", json=compra)

    limpar(db)

    # Apagá-lo levaria de quem foi a compra real; e deixa de ser demonstração.
    assert [(f["nome"], f["demonstracao"]) for f in client.get("/api/v1/fornecedores").json()] == [
        ("Revenda Boa Safra", False)
    ]
    carregar(db, hoje())  # e a próxima carga o reaproveita
    assert len(client.get("/api/v1/fornecedores").json()) == 3


def test_cada_insumo_na_sua_categoria(client: TestClient, db: Session) -> None:
    # A categoria que já existe (a migration cria as de partida) é reaproveitada pelo nome.
    adubo = client.post("/api/v1/categorias", json={"nome": "Fertilizante"}).json()
    carregar(db, hoje())
    carregar(db, hoje())  # recarregar não duplica categoria

    insumos = {i["nome"]: i for i in client.get("/api/v1/insumos").json()}

    assert {nome: i["categoria"] for nome, i in insumos.items()} == {
        "Calcário dolomítico": "Corretivo de solo",
        "Fungicida azoxistrobina": "Defensivo agrícola",
        "Glifosato 480": "Defensivo agrícola",
        "Ivermectina 1%": "Medicamento veterinário",
        "Sal mineral 80P": "Nutrição animal",
        "Semente de milho híbrido": "Semente e muda",
        "Ureia agrícola": "Fertilizante",
    }
    assert insumos["Ureia agrícola"]["categoria_id"] == adubo["id"]
    categorias = client.get("/api/v1/categorias").json()
    assert len(categorias) == 6
    # Limpar não apaga categoria: são as de partida, e o dono pode usá-las nos insumos reais.
    limpar(db)
    assert len(client.get("/api/v1/categorias").json()) == 6


def test_carregar_e_limpar_deixam_rastro(db: Session) -> None:
    """A demonstração apaga e cria em massa, rodada no servidor: a trilha diz quando e
    quanto, com origem terminal e sem usuário."""
    carregar(db, hoje())
    carregar(db, hoje())  # recarregar apaga a carga anterior: o evento diz quanto

    limpar(db)

    primeira, segunda, limpeza = eventos(db)
    assert [e.acao for e in (primeira, segunda, limpeza)] == [
        "demo.carregada",
        "demo.carregada",
        "demo.limpa",
    ]
    for evento in (primeira, segunda, limpeza):
        assert (evento.origem, evento.usuario_id, evento.entidade) == ("terminal", None, None)
    nada = {"insumos": 0, "talhoes": 0, "fornecedores": 0, "pedidos": 0}
    tudo = {"insumos": 7, "talhoes": 3, "fornecedores": 3, "pedidos": 1}
    assert primeira.dados == {"referencia": str(hoje()), "criados": tudo, "removidos": nada}
    assert segunda.dados["removidos"] == tudo
    assert limpeza.dados == {"removidos": tudo}


def test_limpar_recalcula_a_situacao_do_pedido_real_que_fica(
    client: TestClient, db: Session
) -> None:
    # Pedidos reais com uma linha de insumo de demonstração: ela sai com o insumo, e o
    # pedido que fica tem a situação pelo que sobrou, e não a de antes.
    carregar(db, hoje())
    sal = next(i for i in client.get("/api/v1/insumos").json() if i["nome"] == "Sal mineral 80P")
    adubo = client.post("/api/v1/insumos", json={"nome": "Adubo da fazenda", "unidade": "kg"})
    calcario = client.post("/api/v1/insumos", json={"nome": "Calcário", "unidade": "t"})

    def pedir_e_receber(real: dict, recebe_o_real: bool) -> int:
        feito = client.post(
            "/api/v1/pedidos",
            json={
                "feito_em": str(hoje() - timedelta(days=10)),
                "previsto_para": str(hoje() - timedelta(days=2)),
                "itens": [
                    {"insumo_id": real["id"], "quantidade": 10},
                    {"insumo_id": sal["id"], "quantidade": 10},
                ],
            },
        ).json()
        recebe = real["id"] if recebe_o_real else sal["id"]
        linha = next(i["id"] for i in feito["itens"] if i["insumo_id"] == recebe)
        recebido = client.post(
            f"/api/v1/pedidos/{feito['id']}/receber",
            json={"itens": [{"item_id": linha, "quantidade": 10 if recebe_o_real else 4}]},
        )
        assert recebido.json()["pedido"]["situacao"] == "parcial"
        return feito["id"]

    chegou_o_resto = pedir_e_receber(adubo.json(), recebe_o_real=True)
    nada_chegou = pedir_e_receber(calcario.json(), recebe_o_real=False)

    limpar(db)

    recebido = client.get(f"/api/v1/pedidos/{chegou_o_resto}").json()
    assert (recebido["situacao"], recebido["atrasado"]) == ("recebido", False)
    assert client.get(f"/api/v1/pedidos/{nada_chegou}").json()["situacao"] == "aberto"
