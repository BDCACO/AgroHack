"""A trilha de auditoria no PostgreSQL de verdade: a API conectada com o papel da aplicação
só acrescenta e lê eventos, e nem o dono os altera ou apaga sem querer. E o fluxo por
HTTP, com o login ligado: o dono e o funcionário agindo, os logins errados e o bloqueio,
e o dono lendo quem fez o quê, quando e o que foi apagado; o evento que o banco recusa
desfaz a ação."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.core.relogio import hoje
from tests.integracao.conftest import PAPEL_DA_APP, URL_DA_APP, garantir_o_papel_da_aplicacao
from tests.integracao.test_fluxo_autenticacao import (
    HOJE,
    SENHA_DO_DONO,
    SENHA_DO_ZE,
    criar_dono,
    entrar,
    ok,
)

VALIDADE = str(hoje() + timedelta(days=365))


@pytest.fixture
def evento_gravado(banco: Engine) -> int:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE eventos_de_auditoria RESTART IDENTITY"))
        return conexao.scalar(
            text(
                "INSERT INTO eventos_de_auditoria (acao, entidade, entidade_id, dados, origem)"
                " VALUES ('insumo.removido', 'insumo', 1, CAST(:dados AS jsonb), 'terminal')"
                " RETURNING id"
            ),
            {"dados": '{"nome": "Ureia"}'},
        )


@pytest.fixture
def app_no_banco(banco: Engine) -> Iterator[Connection]:
    """Uma conexão com o papel da aplicação, a da API; o que ela fizer é desfeito no fim."""
    engine = create_engine(URL_DA_APP)
    with engine.connect() as conexao:
        yield conexao
        conexao.rollback()
    engine.dispose()


@pytest.mark.parametrize(
    "comando",
    [
        "UPDATE eventos_de_auditoria SET dados = '{}'",
        "UPDATE eventos_de_auditoria SET acao = 'demo.limpa' WHERE id = 1",
        "DELETE FROM eventos_de_auditoria",
        "DELETE FROM eventos_de_auditoria WHERE id = 1",
        "TRUNCATE eventos_de_auditoria",
    ],
)
def test_o_papel_da_aplicacao_nao_altera_nem_apaga_evento(
    evento_gravado: int, app_no_banco: Connection, comando: str
) -> None:
    with pytest.raises(ProgrammingError) as recusa:
        app_no_banco.execute(text(comando))

    assert recusa.value.orig.sqlstate == "42501"  # insufficient_privilege
    app_no_banco.rollback()
    assert app_no_banco.scalar(text("SELECT dados->>'nome' FROM eventos_de_auditoria")) == "Ureia"


def test_o_papel_da_aplicacao_acrescenta_e_le(
    evento_gravado: int, app_no_banco: Connection
) -> None:
    app_no_banco.execute(
        text(
            "INSERT INTO eventos_de_auditoria (acao, dados, origem)"
            " VALUES ('demo.limpa', CAST('{}' AS jsonb), 'terminal')"
        )
    )

    assert app_no_banco.scalar(text("SELECT count(*) FROM eventos_de_auditoria")) == 2


def test_o_comando_do_papel_rodado_de_novo_nao_devolve_o_delete(
    evento_gravado: int, banco: Engine
) -> None:
    """A cada subida ele refaz as permissões com um GRANT em todas as tabelas: a trilha
    tem de sair dele só com INSERT e SELECT de novo."""
    garantir_o_papel_da_aplicacao()

    engine = create_engine(URL_DA_APP)
    with pytest.raises(ProgrammingError), engine.begin() as conexao:
        conexao.execute(text("DELETE FROM eventos_de_auditoria"))
    engine.dispose()


@pytest.mark.parametrize(
    "comando",
    [
        "UPDATE eventos_de_auditoria SET dados = '{}'",
        "DELETE FROM eventos_de_auditoria",
    ],
)
def test_nem_o_dono_altera_ou_apaga_evento_sem_querer(
    evento_gravado: int, banco: Engine, comando: str
) -> None:
    # O DELETE à mão no psql, ou a migration que "limpa" dados, não apagam o rastro: só
    # derrubando o gatilho, o que ninguém faz por engano.
    with pytest.raises(IntegrityError, match="só aceita acrescentar"), banco.begin() as conexao:
        conexao.execute(text(comando))

    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT dados->>'nome' FROM eventos_de_auditoria")) == "Ureia"


# O fluxo real, por HTTP, com o login ligado: o dono e o funcionário agindo, a API com o
# papel da aplicação gravando a trilha, e o dono lendo quem fez o quê.


def _eventos(api: httpx.Client, cabecalho: dict, **filtros: object) -> tuple[list[dict], int]:
    resposta = api.get("/auditoria", headers=cabecalho, params=filtros)
    assert resposta.status_code == 200, resposta.text
    return resposta.json(), int(resposta.headers["X-Total-Count"])


def test_dono_le_quem_fez_o_que_com_o_conteudo_apagado(
    api_autenticada: httpx.Client, banco: Engine
) -> None:
    api = api_autenticada
    assert criar_dono("maria", "Dona Maria").returncode == 0
    dono = entrar(api, "maria", SENHA_DO_DONO, "Computador do escritório")
    corpo_do_ze = {"nome": "Zé do Trator", "login": "ze", "senha": SENHA_DO_ZE}
    ze = ok(api.post("/usuarios", headers=dono, json=corpo_do_ze | {"papel": "funcionario"}), 201)
    ureia = ok(api.post("/insumos", headers=dono, json={"nome": "Ureia", "unidade": "kg"}), 201)
    revenda = ok(api.post("/fornecedores", headers=dono, json={"nome": "Revenda Boa Safra"}), 201)
    norte = {"nome": "Talhão Norte", "area_ha": 120, "cultura": "Soja"}
    talhao = ok(api.post("/talhoes", headers=dono, json=norte), 201)

    # O funcionário lança no campo (lançamento comum: sem evento) e troca a própria senha.
    celular = entrar(api, "ze", SENHA_DO_ZE, "Celular do Zé")
    lote = str(uuid4())
    compra = {
        "insumo_id": ureia["id"],
        "tipo": "entrada",
        "data": HOJE,
        "quantidade": 200,
        "validade": VALIDADE,
        "valor_unitario": 3.2,
        "fornecedor_id": revenda["id"],
        "uuid": lote,
    }
    compra = ok(api.post("/movimentacoes", headers=celular, json=compra), 201)
    no_talhao = {"insumo_id": ureia["id"], "tipo": "saida", "data": HOJE, "quantidade": 30}
    aplicacao = no_talhao | {"talhao_id": talhao["id"]}
    aplicacao = ok(api.post("/movimentacoes", headers=celular, json=aplicacao), 201)
    nova_do_ze = "nova-senha-do-ze"
    troca = {"senha_atual": SENHA_DO_ZE, "senha_nova": nova_do_ze}
    assert api.put("/auth/senha", headers=celular, json=troca).status_code == 204
    # O que é do dono o funcionário não faz, nem lê a trilha; e a recusa não deixa evento.
    assert api.get("/auditoria", headers=celular).status_code == 403
    assert api.delete(f"/movimentacoes/{compra['id']}", headers=celular).status_code == 403

    # O dono remove, altera, cancela e importa.
    ok(api.delete(f"/movimentacoes/{compra['id']}", headers=dono), 204)
    ok(api.delete(f"/movimentacoes/{aplicacao['id']}", headers=dono), 204)
    ok(api.delete(f"/talhoes/{talhao['id']}", headers=dono), 204)
    ok(api.put(f"/usuarios/{ze['id']}", headers=dono, json={"papel": "dono"}))
    linha = {"insumo_id": ureia["id"], "quantidade": 500, "valor_unitario": 3.4}
    corpo_do_pedido = {"fornecedor_id": revenda["id"], "itens": [linha]}
    pedido = ok(api.post("/pedidos", headers=dono, json=corpo_do_pedido), 201)
    ok(api.post(f"/pedidos/{pedido['id']}/cancelar", headers=dono))
    planilha = (
        "data;insumo;unidade;tipo;quantidade;validade\n"
        f"{hoje():%d/%m/%Y};Calcário;t;entrada;12;\n"
        f"{hoje():%d/%m/%Y};Calcário;t;saída;2;\n"
    )
    importacao = {"conteudo": planilha, "confirmar": True}
    assert ok(api.post("/importacoes", headers=dono, json=importacao))["importado"]
    calcario = next(i for i in ok(api.get("/insumos", headers=dono)) if i["nome"] == "Calcário")
    ok(api.delete(f"/insumos/{calcario['id']}", headers=dono), 204)

    # Senhas erradas seguidas: cada uma recusada, a quinta bloqueia, e a certa durante o
    # bloqueio também é recusada. O login que não existe não deixa evento.
    def tentar(login: str, senha: str) -> int:
        return api.post("/auth/entrar", json={"login": login, "senha": senha}).status_code

    assert [tentar("ze", f"chute-{i}") for i in range(5)] == [401] * 5
    assert tentar("ze", nova_do_ze) == 401
    assert tentar("ninguem", "qualquer-uma") == 401

    eventos, total = _eventos(api, dono)
    assert [e["acao"] for e in reversed(eventos)] == [
        "usuario.criado",  # o dono, pelo comando no servidor
        "usuario.criado",  # o Zé, pelo dono
        "usuario.senha_trocada",
        "movimentacao.removida",
        "movimentacao.removida",
        "talhao.removido",
        "usuario.alterado",
        "pedido.cancelado",
        "importacao.confirmada",
        "insumo.removido",
        *["login.recusado"] * 5,
        "login.bloqueado",
        "login.recusado",
    ]
    assert total == len(eventos) == 17
    instantes = [datetime.fromisoformat(e["ocorrido_em"]) for e in eventos]
    assert instantes == sorted(instantes, reverse=True)  # os mais recentes primeiro
    assert all(abs(datetime.now(UTC) - instante) < timedelta(minutes=5) for instante in instantes)

    por_acao: dict[str, list[dict]] = {}
    for evento in reversed(eventos):
        por_acao.setdefault(evento["acao"], []).append(evento)

    # Quem e de onde: o comando no servidor, o dono no computador, o Zé no celular.
    pelo_comando, pelo_dono = por_acao["usuario.criado"]
    assert (pelo_comando["origem"], pelo_comando["usuario_id"]) == ("terminal", None)
    assert (pelo_dono["origem"], pelo_dono["feito_por"], pelo_dono["ip"]) == (
        "api",
        "Dona Maria",
        "127.0.0.1",
    )
    assert pelo_dono["dispositivo"] == "Computador do escritório"
    [trocada] = por_acao["usuario.senha_trocada"]
    assert (trocada["feito_por"], trocada["dispositivo"]) == ("Zé do Trator", "Celular do Zé")

    # O conteúdo inteiro da compra removida: o bastante para relançá-la à mão.
    removida, aplicada = por_acao["movimentacao.removida"]
    assert (removida["entidade_id"], removida["feito_por"]) == (compra["id"], "Dona Maria")
    assert removida["dados"] == {
        "id": compra["id"],
        "insumo_id": ureia["id"],
        "insumo": "Ureia",
        "tipo": "entrada",
        "data": HOJE,
        "quantidade": 200,
        "validade": VALIDADE,
        "motivo": None,
        "valor_unitario": 3.2,
        "talhao_id": None,
        "talhao": None,
        "fornecedor_id": revenda["id"],
        "fornecedor": "Revenda Boa Safra",
        "uuid": lote,
        "usuario_id": ze["id"],
        "lancado_por": "Zé do Trator",
        "item_do_pedido_id": None,
    }
    assert (aplicada["dados"]["talhao"], aplicada["dados"]["quantidade"]) == ("Talhão Norte", 30)
    [talhao_removido] = por_acao["talhao.removido"]
    assert talhao_removido["dados"]["area_ha"] == 120
    [alterado] = por_acao["usuario.alterado"]
    assert alterado["dados"] == {
        "login": "ze",
        "antes": {"papel": "funcionario"},
        "depois": {"papel": "dono"},
    }
    [cancelado] = por_acao["pedido.cancelado"]
    assert cancelado["dados"]["itens"][0]["falta_receber"] == 500
    [importada] = por_acao["importacao.confirmada"]
    assert (importada["dados"]["linhas"], importada["dados"]["entradas"]) == (2, 1)
    [insumo_removido] = por_acao["insumo.removido"]
    assert insumo_removido["dados"]["insumo"]["nome"] == "Calcário"
    assert len(insumo_removido["dados"]["movimentacoes"]) == 2
    [bloqueio] = por_acao["login.bloqueado"]
    assert (bloqueio["usuario_id"], bloqueio["entidade_id"]) == (None, ze["id"])
    motivos = [e["dados"]["motivo"] for e in por_acao["login.recusado"]]
    assert motivos == ["senha_incorreta"] * 5 + ["bloqueado"]

    # Filtros, que se somam: o grupo, quem fez, sobre o quê, o período; e as páginas.
    logins, total_de_logins = _eventos(api, dono, acao="login")
    assert total_de_logins == len(logins) == 7
    do_ze, _ = _eventos(api, dono, usuario_id=ze["id"])
    assert [e["acao"] for e in do_ze] == ["usuario.senha_trocada"]
    da_compra, _ = _eventos(api, dono, entidade="movimentacao", entidade_id=compra["id"])
    assert [e["id"] for e in da_compra] == [removida["id"]]
    assert _eventos(api, dono, desde=HOJE, ate=HOJE)[1] == 17
    ontem = str(hoje() - timedelta(days=1))
    assert _eventos(api, dono, ate=ontem) == ([], 0)
    paginas = [_eventos(api, dono, limite=5, deslocamento=d) for d in (0, 5, 10, 15)]
    assert [len(pagina) for pagina, _ in paginas] == [5, 5, 5, 2]
    assert {total for _, total in paginas} == {17}
    assert [e["id"] for pagina, _ in paginas for e in pagina] == [e["id"] for e in eventos]
    assert api.get("/auditoria", params={"acao": "nada"}, headers=dono).status_code == 422
    assert api.get("/auditoria").status_code == 401

    # Nenhum segredo na trilha: nem as senhas, nem os hashes, nem os tokens.
    with banco.connect() as conexao:
        trilha = conexao.scalar(
            text("SELECT string_agg(dados::text, ' ') FROM eventos_de_auditoria")
        )
        hashes = conexao.scalars(
            text("SELECT senha_hash FROM usuarios UNION ALL SELECT token_hash FROM sessoes")
        ).all()
    tokens = [cabecalho["Authorization"].removeprefix("Bearer ") for cabecalho in (dono, celular)]
    for segredo in [SENHA_DO_DONO, SENHA_DO_ZE, nova_do_ze, *hashes, *tokens]:
        assert segredo not in trilha
    assert "argon2" not in trilha


def test_evento_que_o_banco_recusa_desfaz_a_acao(
    api_autenticada: httpx.Client, banco: Engine
) -> None:
    """Atômico de verdade, no PostgreSQL: sem poder gravar o evento, a remoção não
    acontece."""
    api = api_autenticada
    assert criar_dono("maria", "Dona Maria").returncode == 0
    dono = entrar(api, "maria", SENHA_DO_DONO)
    ureia = ok(api.post("/insumos", headers=dono, json={"nome": "Ureia", "unidade": "kg"}), 201)
    compra = {"insumo_id": ureia["id"], "tipo": "entrada", "data": HOJE, "quantidade": 200}
    lancada = ok(api.post("/movimentacoes", headers=dono, json=compra), 201)
    with banco.begin() as conexao:
        antes = conexao.scalar(text("SELECT count(*) FROM eventos_de_auditoria"))
        conexao.execute(text(f"REVOKE INSERT ON eventos_de_auditoria FROM {PAPEL_DA_APP}"))
    try:
        recusada = api.delete(f"/movimentacoes/{lancada['id']}", headers=dono)
    finally:
        # O comando do papel devolve o INSERT (e só ele), como a cada subida.
        garantir_o_papel_da_aplicacao()

    assert recusada.status_code >= 500
    assert [m["id"] for m in ok(api.get("/movimentacoes", headers=dono))] == [lancada["id"]]
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT count(*) FROM eventos_de_auditoria")) == antes

    # Com o poder de volta, a remoção e o evento entram juntos.
    ok(api.delete(f"/movimentacoes/{lancada['id']}", headers=dono), 204)
    assert ok(api.get("/movimentacoes", headers=dono)) == []
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT count(*) FROM eventos_de_auditoria")) == antes + 1
