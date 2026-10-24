"""Fluxo real de uso, por HTTP, contra o PostgreSQL: o produtor que separa os insumos por
categoria, procura e filtra as listas, pagina as movimentações e lê o relatório por
período. E, com volume (50 mil movimentações), confere no plano do PostgreSQL que as
consultas da lista e do período usam os índices da migration 0011."""

import time
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import Engine, event, text
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.services import estoque, relatorio_por_periodo

HOJE = hoje()


def ok(resposta: httpx.Response, status: int = 200) -> Any:
    assert resposta.status_code == status, resposta.text
    return resposta.json() if resposta.content else None


def mes(atras: int, dia: int) -> date:
    """O dia `dia` do mês `atras` meses antes deste."""
    contagem = HOJE.year * 12 + HOJE.month - 1 - atras
    return date(contagem // 12, contagem % 12 + 1, dia)


def fazenda(api: httpx.Client) -> dict[str, Any]:
    """Três meses de história, com um mês inteiro sem movimento no meio (dois meses atrás).
    Ureia (fertilizante) de duas revendas, aplicada no talhão, descartada e com falta na
    contagem; glifosato (defensivo) comprado sem preço; sal (sem categoria)."""
    adubo = ok(api.post("/categorias", json={"nome": "Fertilizante"}), 201)
    defensivo = ok(api.post("/categorias", json={"nome": "Defensivo agrícola"}), 201)
    ureia = ok(
        api.post(
            "/insumos",
            json={"nome": "Uréia agrícola", "unidade": "kg", "categoria_id": adubo["id"]},
        ),
        201,
    )
    glifo = ok(
        api.post(
            "/insumos",
            json={"nome": "Glifosato 480", "unidade": "L", "categoria_id": defensivo["id"]},
        ),
        201,
    )
    sal = ok(api.post("/insumos", json={"nome": "Sal mineral", "unidade": "kg"}), 201)
    norte = ok(api.post("/talhoes", json={"nome": "Talhão Norte", "area_ha": 50}), 201)
    agro = ok(api.post("/fornecedores", json={"nome": "Agro Norte"}), 201)
    casa = ok(api.post("/fornecedores", json={"nome": "Casa do Adubo"}), 201)
    u, g, s = ureia["id"], glifo["id"], sal["id"]

    for corpo in (
        # Três meses atrás: as compras.
        {"insumo_id": u, "tipo": "entrada", "data": str(mes(3, 2)), "quantidade": 1000,
         "valor_unitario": 3.1, "fornecedor_id": agro["id"]},
        {"insumo_id": u, "tipo": "entrada", "data": str(mes(3, 3)), "quantidade": 500,
         "valor_unitario": 2.9, "fornecedor_id": casa["id"]},
        {"insumo_id": g, "tipo": "entrada", "data": str(mes(3, 3)), "quantidade": 40,
         "fornecedor_id": agro["id"]},
        {"insumo_id": s, "tipo": "entrada", "data": str(mes(3, 4)), "quantidade": 300,
         "valor_unitario": 4.5},
        # Mês passado: o uso, um descarte.
        {"insumo_id": u, "tipo": "saida", "data": str(mes(1, 5)), "quantidade": 200,
         "talhao_id": norte["id"]},
        {"insumo_id": u, "tipo": "saida", "data": str(mes(1, 6)), "quantidade": 100},
        {"insumo_id": g, "tipo": "saida", "data": str(mes(1, 6)), "quantidade": 5},
        {"insumo_id": s, "tipo": "saida", "data": str(mes(1, 7)), "quantidade": 30},
        {"insumo_id": u, "tipo": "saida", "data": str(mes(1, 8)), "quantidade": 50,
         "motivo": "descarte"},
    ):  # fmt: skip
        ok(api.post("/movimentacoes", json=corpo), 201)
    # Este mês, no dia 1 (nunca no futuro): a contagem acha 10 kg a menos de ureia.
    contagem = ok(
        api.post(
            f"/insumos/{u}/inventario",
            json={"quantidade_contada": 1140, "data": str(mes(0, 1))},
        )
    )
    assert contagem["diferenca"] == -10
    return {
        "adubo": adubo,
        "defensivo": defensivo,
        "ureia": ureia,
        "glifo": glifo,
        "sal": sal,
        "norte": norte,
        "agro": agro,
        "casa": casa,
    }


def test_categorias_filtros_e_paginas(api: httpx.Client) -> None:
    f = fazenda(api)

    # Categoria nos insumos e na contagem do cadastro.
    categorias = {c["nome"]: c["insumos"] for c in ok(api.get("/categorias"))}
    assert categorias == {"Defensivo agrícola": 1, "Fertilizante": 1}
    assert ok(api.delete(f"/categorias/{f['adubo']['id']}"), 409)["detail"].startswith(
        "Fertilizante tem 1 insumo"
    )
    # Busca sem acento nem maiúsculas, no PostgreSQL igual ao SQLite dos testes.
    assert [i["nome"] for i in ok(api.get("/insumos", params={"busca": "UREIA"}))] == [
        "Uréia agrícola"
    ]
    adubos = ok(api.get("/insumos", params={"categoria_id": f["adubo"]["id"]}))
    assert [(i["nome"], i["categoria"]) for i in adubos] == [("Uréia agrícola", "Fertilizante")]

    # Movimentações filtradas, com o total no cabeçalho.
    def filtradas(**params: Any) -> tuple[int, list[float]]:
        resposta = api.get("/movimentacoes", params=params)
        corpo = ok(resposta)
        return int(resposta.headers["X-Total-Count"]), [m["quantidade"] for m in corpo]

    assert filtradas(tipo="saida", motivo="nenhum") == (4, [30, 5, 100, 200])
    assert filtradas(motivo="inventario") == (1, [10])
    assert filtradas(categoria_id=f["defensivo"]["id"]) == (2, [5, 40])
    assert filtradas(talhao_id=f["norte"]["id"]) == (1, [200])
    assert filtradas(fornecedor_id=f["agro"]["id"]) == (2, [40, 1000])
    assert filtradas(busca="glifosato", desde=str(mes(1, 1))) == (1, [5])
    assert (
        api.get("/movimentacoes", params={"desde": str(HOJE), "ate": str(mes(3, 1))}).status_code
        == 422
    )

    # Páginas de 3: nenhuma se repete nem some, e a ordem é a da lista inteira.
    total, todas = filtradas(limite=1000)
    paginas: list[float] = []
    for deslocamento in range(0, total + 3, 3):
        assert filtradas(limite=3, deslocamento=deslocamento)[0] == total
        paginas += filtradas(limite=3, deslocamento=deslocamento)[1]
    assert (total, paginas) == (10, todas)
    ids = [m["id"] for m in ok(api.get("/movimentacoes", params={"limite": 1000}))]
    datas = [m["data"] for m in ok(api.get("/movimentacoes", params={"limite": 1000}))]
    assert list(zip(datas, ids, strict=True)) == sorted(zip(datas, ids, strict=True), reverse=True)


def test_relatorio_por_periodo(api: httpx.Client) -> None:
    f = fazenda(api)

    r = ok(api.get("/relatorios/periodo", params={"desde": str(mes(3, 1)), "agrupar": "mes"}))

    assert [p["inicio"] for p in r["periodos"]] == [str(mes(a, 1)) for a in (3, 2, 1, 0)]
    vazio = r["periodos"][1]
    assert (vazio["gasto"], vazio["perdas"], vazio["consumo"], vazio["por_categoria"]) == (
        0,
        0,
        [],
        [],
    )
    compras, uso, contagem = r["periodos"][0], r["periodos"][2], r["periodos"][3]
    # Gasto: 1000 × 3,10 + 500 × 2,90 + 300 × 4,50; o glifosato sem preço fica de fora.
    assert (compras["gasto"], compras["compras_sem_preco"]) == (5900.0, 1)
    # Consumo: só a retirada para uso, cada insumo na sua unidade (o descarte de 50 kg e a
    # falta de 10 kg não entram).
    consumo = [(c["insumo"], c["unidade"], c["quantidade"], c["valor"]) for c in uso["consumo"]]
    assert consumo == [
        ("Glifosato 480", "L", 5, None),
        ("Sal mineral", "kg", 30, 135.0),
        ("Uréia agrícola", "kg", 300, 909.0),  # custo médio de R$ 3,03
    ]
    assert uso["perdas"] == 151.5  # o descarte de 50 kg × R$ 3,03
    assert contagem["perdas"] == 30.3  # a falta de 10 kg
    total = r["total"]
    assert total["perdas"] == ok(api.get("/resumo"))["perdas"]["total"] == 181.8
    por_categoria = {
        c["categoria"]: (c["gasto"], c["consumo"], c["perdas"]) for c in total["por_categoria"]
    }
    assert por_categoria == {
        "Defensivo agrícola": (0, 0, 0),
        "Fertilizante": (4550.0, 909.0, 181.8),
        None: (1350.0, 135.0, 0),
    }
    assert sum(g for g, _, _ in por_categoria.values()) == total["gasto"] == 5900.0
    por_fornecedor = [
        (x["fornecedor"], x["gasto"], x["compras"], x["compras_sem_preco"])
        for x in total["por_fornecedor"]
    ]
    assert por_fornecedor == [
        ("Agro Norte", 3100.0, 2, 1),
        ("Casa do Adubo", 1450.0, 1, 0),
        (None, 1350.0, 1, 0),
    ]
    assert "1 compra sem preço ficou fora do gasto." in r["limitacoes"]

    # Recortes: por talhão só a aplicação; por semana e por dia, os mesmos totais.
    no_talhao = ok(
        api.get(
            "/relatorios/periodo", params={"desde": str(mes(3, 1)), "talhao_id": f["norte"]["id"]}
        )
    )
    assert [c["quantidade"] for c in no_talhao["total"]["consumo"]] == [200]
    for agrupar in ("semana", "dia"):
        outro = ok(
            api.get("/relatorios/periodo", params={"desde": str(mes(3, 1)), "agrupar": agrupar})
        )
        assert outro["total"] == total
    longo = api.get("/relatorios/periodo", params={"desde": "2020-01-01", "agrupar": "dia"})
    assert longo.status_code == 422


# --- Volume e índices ----------------------------------------------------------------

MOVIMENTACOES = 50_000
INSUMOS = 50
DIAS = 1_000  # quase três anos de história


def _com_volume(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO insumos (nome, unidade) "
                "SELECT 'Insumo ' || i, 'kg' FROM generate_series(1, :n) AS i"
            ),
            {"n": INSUMOS},
        )
        # Um terço compra, o resto retirada; espalhadas pelos dias e pelos insumos.
        conexao.execute(
            text(
                "INSERT INTO movimentacoes (insumo_id, tipo, data, quantidade) "
                "SELECT i % :insumos + 1, CASE WHEN i % 3 = 0 THEN 'entrada' ELSE 'saida' END, "
                "CAST(:hoje AS date) - (i % :dias), 1 + i % 7 "
                "FROM generate_series(1, :n) AS i"
            ),
            {"insumos": INSUMOS, "hoje": HOJE, "dias": DIAS, "n": MOVIMENTACOES},
        )
        # As estatísticas que o planejador usa, como o autovacuum faria depois da carga.
        conexao.execute(text("ANALYZE insumos, movimentacoes"))


def _planos(banco: Engine, chamar: Any) -> list[str]:
    """O EXPLAIN de cada consulta que o serviço faz, com o SQL e os parâmetros exatos que
    ele manda ao PostgreSQL (capturados no caminho), e não uma cópia escrita à mão."""
    consultas: list[tuple[str, Any]] = []

    def capturar(_conexao: Any, _cursor: Any, sql: str, parametros: Any, *_: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            consultas.append((sql, parametros))

    with Session(banco) as sessao:
        event.listen(banco, "before_cursor_execute", capturar)
        try:
            chamar(sessao)
        finally:
            event.remove(banco, "before_cursor_execute", capturar)
        planos = []
        for sql, parametros in consultas:
            linhas = sessao.connection().exec_driver_sql(f"EXPLAIN {sql}", parametros)
            planos.append("\n".join(linha[0] for linha in linhas))
    return planos


def test_indices_sustentam_as_listas_com_volume(api: httpx.Client, banco: Engine) -> None:
    _com_volume(banco)

    # A primeira página da lista: lida pelo índice (data, id), já na ordem, sem ordenar
    # as 50 mil.
    pagina, contagem = _da_pagina_e_do_total(
        _planos(
            banco,
            lambda s: estoque.listar_movimentacoes(s, estoque.FiltroDeMovimentacoes(), 200),
        )
    )
    print(f"\nlista, primeira página:\n{pagina}\ntotal:\n{contagem}")
    assert "ix_movimentacoes_data_id" in pagina
    assert "Sort" not in pagina

    # As de um insumo e o total delas: pelo índice (insumo_id, data, id). Com mil linhas
    # do insumo espalhadas pela tabela, o PostgreSQL prefere buscá-las pelo índice em
    # bitmap e ordenar as mil na memória a lê-las uma a uma na ordem: a escolha é dele,
    # pelo custo, e a conta só pede que não leia a tabela inteira.
    pagina, contagem = _da_pagina_e_do_total(
        _planos(
            banco,
            lambda s: estoque.listar_movimentacoes(
                s, estoque.FiltroDeMovimentacoes(insumo_id=7), 200, deslocamento=200
            ),
        )
    )
    print(f"\nde um insumo, segunda página:\n{pagina}\ntotal:\n{contagem}")
    assert "ix_movimentacoes_insumo_id_data_id" in pagina
    assert "Seq Scan on movimentacoes" not in pagina
    assert "ix_movimentacoes_insumo_id_data_id" in contagem

    # O relatório de um mês lê só o trecho do período, pelo índice (data, id).
    [periodo] = [
        plano
        for plano in _planos(
            banco,
            lambda s: relatorio_por_periodo.gerar(s, HOJE - timedelta(days=29), HOJE, "dia"),
        )
        if "data >=" in plano
    ]
    print(f"\nrelatório de 30 dias, as movimentações do período:\n{periodo}")
    assert "ix_movimentacoes_data_id" in periodo
    assert "Seq Scan on movimentacoes" not in periodo

    # E pela API, com o volume: o total no cabeçalho e as respostas em tempo de tela.
    comeco = time.perf_counter()
    resposta = api.get("/movimentacoes", params={"limite": 200})
    lista = time.perf_counter() - comeco
    assert resposta.headers["X-Total-Count"] == str(MOVIMENTACOES)
    comeco = time.perf_counter()
    ano = ok(api.get("/relatorios/periodo"))
    doze_meses = time.perf_counter() - comeco
    print(f"\nGET /movimentacoes: {lista:.3f} s; GET /relatorios/periodo: {doze_meses:.3f} s")
    assert len(ano["periodos"]) == 12
    assert len(ano["total"]["consumo"]) == INSUMOS


def _da_pagina_e_do_total(planos: list[str]) -> tuple[str, str]:
    """A lista faz duas consultas: a da página (com LIMIT) e a do total (com count)."""
    [pagina] = [plano for plano in planos if "Limit" in plano]
    [contagem] = [plano for plano in planos if "Aggregate" in plano]
    return pagina, contagem
