"""O que cada ação do estoque deixa na trilha de auditoria: a movimentação e o insumo
removidos (com o conteúdo, para relançar à mão), o insumo alterado (o antes e o depois), e
que ação e evento entram ou falham juntos."""

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.models import Insumo, Movimentacao, Usuario
from app.services import autenticacao
from tests.conftest import IP_DO_TESTE, CriarUsuario, erro_inesperado
from tests.test_eventos_de_auditoria import eventos

HOJE = hoje()
API = "/api/v1"
# O que se manda no POST /movimentacoes: o evento de uma removida tem de trazer tudo isto.
CAMPOS_DO_LANCAMENTO = (
    "insumo_id",
    "tipo",
    "data",
    "quantidade",
    "validade",
    "motivo",
    "valor_unitario",
    "talhao_id",
    "fornecedor_id",
    "uuid",
)


def cabecalho(db: Session, usuario: Usuario, dispositivo: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {autenticacao.abrir_sessao(db, usuario, dispositivo)[0]}"}


def ok(resposta: Response, status: int = 200) -> Any:
    assert resposta.status_code == status, resposta.text
    return resposta.json() if resposta.content else None


@pytest.fixture
def fazenda(
    cliente_autenticado: TestClient, db: Session, criar_usuario: CriarUsuario
) -> SimpleNamespace:
    """O dono (Maria, no computador do escritório), o funcionário (Zé, no celular) e o
    cadastro de partida: a ureia, o Talhão Norte e a Revenda Boa Safra."""
    maria = criar_usuario("maria", papel="dono", nome="Dona Maria")
    ze = criar_usuario("ze", nome="Zé do Trator")
    dono = cabecalho(db, maria, "Computador do escritório")
    api = cliente_autenticado
    ureia = ok(
        api.post(f"{API}/insumos", headers=dono, json={"nome": "Ureia", "unidade": "kg"}), 201
    )
    talhao = {"nome": "Talhão Norte", "area_ha": 120}
    revenda = {"nome": "Revenda Boa Safra"}
    return SimpleNamespace(
        api=api,
        maria=maria,
        ze=ze,
        dono=dono,
        do_ze=cabecalho(db, ze, "Celular do Zé"),
        ureia=ureia["id"],
        talhao=ok(api.post(f"{API}/talhoes", headers=dono, json=talhao), 201)["id"],
        revenda=ok(api.post(f"{API}/fornecedores", headers=dono, json=revenda), 201)["id"],
    )


def test_movimentacao_removida_guarda_o_suficiente_para_relancar(
    fazenda: SimpleNamespace, db: Session
) -> None:
    api, f = fazenda.api, fazenda
    compra = {
        "insumo_id": f.ureia,
        "tipo": "entrada",
        "data": str(HOJE - timedelta(days=1)),
        "quantidade": 200,
        "validade": str(HOJE + timedelta(days=300)),
        "valor_unitario": 3.3,
        "fornecedor_id": f.revenda,
        "uuid": str(uuid4()),
    }
    lancada = ok(api.post(f"{API}/movimentacoes", headers=f.do_ze, json=compra), 201)

    ok(api.delete(f"{API}/movimentacoes/{lancada['id']}", headers=f.dono), 204)

    [evento] = eventos(db, "movimentacao.removida")
    assert (evento.usuario_id, evento.entidade, evento.entidade_id) == (
        f.maria.id,
        "movimentacao",
        lancada["id"],
    )
    assert (evento.origem, evento.ip, evento.dispositivo) == (
        "api",
        IP_DO_TESTE,
        "Computador do escritório",
    )
    assert evento.dados == {
        "id": lancada["id"],
        "insumo_id": f.ureia,
        "insumo": "Ureia",
        "tipo": "entrada",
        "data": compra["data"],
        "quantidade": 200.0,
        "validade": compra["validade"],
        "motivo": None,
        "valor_unitario": 3.3,
        "talhao_id": None,
        "talhao": None,
        "fornecedor_id": f.revenda,
        "fornecedor": "Revenda Boa Safra",
        "uuid": compra["uuid"],
        "usuario_id": f.ze.id,
        "lancado_por": "Zé do Trator",
        "item_do_pedido_id": None,
    }
    # Relançada à mão a partir do evento, volta igual (o mesmo uuid inclusive).
    corpo = {campo: evento.dados[campo] for campo in CAMPOS_DO_LANCAMENTO}
    relancada = ok(api.post(f"{API}/movimentacoes", headers=f.dono, json=corpo), 201)
    assert {c: relancada[c] for c in CAMPOS_DO_LANCAMENTO} == {
        c: lancada[c] for c in CAMPOS_DO_LANCAMENTO
    }


def test_aplicacao_removida_guarda_o_talhao(fazenda: SimpleNamespace, db: Session) -> None:
    api, f = fazenda.api, fazenda
    aplicacao = {"insumo_id": f.ureia, "tipo": "saida", "data": str(HOJE), "quantidade": 12.5}
    lancada = ok(
        api.post(f"{API}/movimentacoes", headers=f.do_ze, json=aplicacao | {"talhao_id": f.talhao}),
        201,
    )

    ok(api.delete(f"{API}/movimentacoes/{lancada['id']}", headers=f.dono), 204)

    [evento] = eventos(db, "movimentacao.removida")
    assert (evento.dados["talhao_id"], evento.dados["talhao"]) == (f.talhao, "Talhão Norte")
    assert (evento.dados["tipo"], evento.dados["quantidade"]) == ("saida", 12.5)


def test_insumo_removido_guarda_o_cadastro_as_movimentacoes_e_os_pedidos(
    fazenda: SimpleNamespace, db: Session
) -> None:
    api, f = fazenda.api, fazenda
    cadastro = {"nome": "Sal mineral", "unidade": "kg", "estoque_minimo": 150, "embalagem": 25}
    sal = ok(api.post(f"{API}/insumos", headers=f.dono, json=cadastro), 201)
    entrada = {"insumo_id": sal["id"], "tipo": "entrada", "data": str(HOJE), "quantidade": 500}
    ok(api.post(f"{API}/movimentacoes", headers=f.do_ze, json=entrada), 201)
    ok(api.post(f"{API}/movimentacoes", headers=f.dono, json=entrada | {"tipo": "saida"}), 201)
    linha = {"insumo_id": sal["id"], "quantidade": 100}
    pedido = ok(api.post(f"{API}/pedidos", headers=f.dono, json={"itens": [linha]}), 201)

    ok(api.delete(f"{API}/insumos/{sal['id']}", headers=f.dono), 204)

    [evento] = eventos(db, "insumo.removido")
    assert (evento.usuario_id, evento.entidade, evento.entidade_id) == (
        f.maria.id,
        "insumo",
        sal["id"],
    )
    assert evento.dados["insumo"] == {
        "id": sal["id"],
        "nome": "Sal mineral",
        "unidade": "kg",
        "estoque_minimo": 150.0,
        "prazo_reposicao_dias": None,
        "embalagem": 25.0,
        "pedido_minimo": None,
        "carencia_dias": None,
        "categoria_id": None,
        "codigo_de_barras": None,
        "categoria": None,
        "demonstracao": False,
    }
    removidas = [
        (m["tipo"], m["quantidade"], m["lancado_por"]) for m in evento.dados["movimentacoes"]
    ]
    assert removidas == [("entrada", 500.0, "Zé do Trator"), ("saida", 500.0, "Dona Maria")]
    assert evento.dados["itens_de_pedido"] == [
        {
            "pedido_id": pedido["id"],
            "quantidade": 100.0,
            "valor_unitario": None,
            "quantidade_recebida": 0.0,
        }
    ]
    # O pedido só tinha o sal: saiu junto, e o evento diz qual.
    assert evento.dados["pedidos_removidos"] == [pedido["id"]]


def test_insumo_alterado_guarda_o_antes_e_o_depois_do_que_mudou(
    fazenda: SimpleNamespace, db: Session
) -> None:
    api, f = fazenda.api, fazenda
    cadastro = {"nome": "Ureia", "unidade": "kg", "estoque_minimo": 300, "embalagem": 50}

    ok(api.put(f"{API}/insumos/{f.ureia}", headers=f.dono, json=cadastro))
    # O mesmo de novo: nada mudou, nada a registrar.
    ok(api.put(f"{API}/insumos/{f.ureia}", headers=f.dono, json=cadastro))

    [evento] = eventos(db, "insumo.alterado")
    assert (evento.usuario_id, evento.entidade_id) == (f.maria.id, f.ureia)
    assert evento.dados == {
        "nome": "Ureia",
        "antes": {"estoque_minimo": None, "embalagem": None},
        "depois": {"estoque_minimo": 300.0, "embalagem": 50.0},
    }


def test_sem_login_com_a_autenticacao_desligada_o_autor_fica_vazio(
    client: TestClient, db: Session
) -> None:
    ureia = ok(client.post(f"{API}/insumos", json={"nome": "Ureia", "unidade": "kg"}), 201)

    ok(client.delete(f"{API}/insumos/{ureia['id']}"), 204)

    [evento] = eventos(db, "insumo.removido")
    assert (evento.usuario_id, evento.origem, evento.dispositivo) == (None, "api", None)


def test_acao_que_falha_nao_deixa_evento(fazenda: SimpleNamespace, db: Session) -> None:
    api, f = fazenda.api, fazenda
    aplicacao = {"insumo_id": f.ureia, "tipo": "saida", "data": str(HOJE), "quantidade": 5}
    corpo = aplicacao | {"talhao_id": f.talhao}
    lancada = ok(api.post(f"{API}/movimentacoes", headers=f.dono, json=corpo), 201)

    assert api.delete(f"{API}/insumos/{f.ureia}", headers=f.dono).status_code == 409
    assert api.delete(f"{API}/movimentacoes/999", headers=f.dono).status_code == 404
    removida = api.delete(f"{API}/movimentacoes/{lancada['id']}", headers=f.do_ze)
    assert removida.status_code == 403

    assert eventos(db) == []


def test_evento_que_falha_desfaz_a_acao(
    fazenda: SimpleNamespace, db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Sem onde gravar o evento, a remoção não acontece: os dois vão na mesma transação."""
    api, f = fazenda.api, fazenda
    compra = {"insumo_id": f.ureia, "tipo": "entrada", "data": str(HOJE), "quantidade": 200}
    lancada = ok(api.post(f"{API}/movimentacoes", headers=f.do_ze, json=compra), 201)
    db.execute(text("DROP TABLE eventos_de_auditoria"))

    for caminho in (f"{API}/movimentacoes/{lancada['id']}", f"{API}/insumos/{f.ureia}"):
        caplog.clear()
        assert api.delete(caminho, headers=f.dono).status_code == 500
        erro = erro_inesperado(caplog)
        assert isinstance(erro, OperationalError)
        assert "eventos_de_auditoria" in str(erro)
        db.rollback()

    assert db.get(Movimentacao, lancada["id"]) is not None
    assert db.get(Insumo, f.ureia) is not None


def test_alteracao_que_o_banco_recusa_nao_deixa_evento(
    fazenda: SimpleNamespace, db: Session
) -> None:
    """O nome repetido só aparece no commit, depois de o evento estar na sessão: o evento
    tem de cair junto com a alteração, e não ficar contando uma mudança que não houve."""
    api, f = fazenda.api, fazenda
    ok(api.post(f"{API}/insumos", headers=f.dono, json={"nome": "Calcário", "unidade": "t"}), 201)
    ok(api.post(f"{API}/talhoes", headers=f.dono, json={"nome": "Pasto 1", "area_ha": 45}), 201)
    ok(api.post(f"{API}/fornecedores", headers=f.dono, json={"nome": "AgroVet"}), 201)
    adubo = ok(api.post(f"{API}/categorias", headers=f.dono, json={"nome": "Adubo"}), 201)
    ok(api.post(f"{API}/categorias", headers=f.dono, json={"nome": "Semente"}), 201)

    repetidos = [
        api.put(
            f"{API}/insumos/{f.ureia}",
            headers=f.dono,
            json={"nome": "Calcário", "unidade": "kg"},
        ),
        api.put(
            f"{API}/talhoes/{f.talhao}", headers=f.dono, json={"nome": "Pasto 1", "area_ha": 120}
        ),
        api.put(f"{API}/fornecedores/{f.revenda}", headers=f.dono, json={"nome": "AgroVet"}),
        api.put(f"{API}/categorias/{adubo['id']}", headers=f.dono, json={"nome": "Semente"}),
    ]

    assert [r.status_code for r in repetidos] == [409] * 4
    assert eventos(db) == []


def test_talhao_alterado_e_removido(fazenda: SimpleNamespace, db: Session) -> None:
    api, f = fazenda.api, fazenda
    alterado = {"nome": "Talhão Norte", "area_ha": 118.5, "cultura": "Soja"}

    ok(api.put(f"{API}/talhoes/{f.talhao}", headers=f.dono, json=alterado))
    ok(api.delete(f"{API}/talhoes/{f.talhao}", headers=f.dono), 204)

    alteracao, remocao = eventos(db)
    assert (alteracao.acao, alteracao.entidade, alteracao.entidade_id) == (
        "talhao.alterado",
        "talhao",
        f.talhao,
    )
    assert alteracao.dados == {
        "nome": "Talhão Norte",
        "antes": {"area_ha": 120.0, "cultura": None},
        "depois": {"area_ha": 118.5, "cultura": "Soja"},
    }
    assert (remocao.acao, remocao.usuario_id) == ("talhao.removido", f.maria.id)
    assert remocao.dados == {
        "id": f.talhao,
        "nome": "Talhão Norte",
        "area_ha": 118.5,
        "cultura": "Soja",
        "demonstracao": False,
    }


def test_talhao_com_aplicacao_nao_sai_nem_deixa_evento(
    fazenda: SimpleNamespace, db: Session
) -> None:
    api, f = fazenda.api, fazenda
    aplicacao = {"insumo_id": f.ureia, "tipo": "saida", "data": str(HOJE), "quantidade": 5}
    ok(
        api.post(f"{API}/movimentacoes", headers=f.dono, json=aplicacao | {"talhao_id": f.talhao}),
        201,
    )

    assert api.delete(f"{API}/talhoes/{f.talhao}", headers=f.dono).status_code == 409

    assert eventos(db, "talhao.removido") == []


def test_categoria_alterada_e_removida(fazenda: SimpleNamespace, db: Session) -> None:
    api, f = fazenda.api, fazenda
    categoria = ok(api.post(f"{API}/categorias", headers=f.dono, json={"nome": "Adubo"}), 201)

    ok(api.put(f"{API}/categorias/{categoria['id']}", headers=f.dono, json={"nome": "Adubos"}))
    ok(api.delete(f"{API}/categorias/{categoria['id']}", headers=f.dono), 204)

    alteracao, remocao = eventos(db)
    assert (alteracao.acao, alteracao.entidade_id) == ("categoria.alterada", categoria["id"])
    assert alteracao.dados == {"antes": {"nome": "Adubo"}, "depois": {"nome": "Adubos"}}
    assert (remocao.acao, remocao.dados) == (
        "categoria.removida",
        {"id": categoria["id"], "nome": "Adubos"},
    )


def test_fornecedor_alterado_so_no_que_veio_e_removido(
    fazenda: SimpleNamespace, db: Session
) -> None:
    api, f = fazenda.api, fazenda
    ok(
        api.put(
            f"{API}/fornecedores/{f.revenda}",
            headers=f.dono,
            json={"nome": "Revenda Boa Safra", "telefone": "69 99999-0000", "cidade": "Ariquemes"},
        )
    )
    ok(
        api.put(
            f"{API}/fornecedores/{f.revenda}",
            headers=f.dono,
            json={"nome": "Revenda Boa Safra", "ativo": False},
        )
    )

    ok(api.delete(f"{API}/fornecedores/{f.revenda}", headers=f.dono), 204)

    contato, desativado, remocao = eventos(db)
    assert (contato.acao, contato.entidade, contato.entidade_id) == (
        "fornecedor.alterado",
        "fornecedor",
        f.revenda,
    )
    assert contato.dados == {
        "nome": "Revenda Boa Safra",
        "antes": {"telefone": None, "cidade": None},
        "depois": {"telefone": "69 99999-0000", "cidade": "Ariquemes"},
    }
    assert desativado.dados == {
        "nome": "Revenda Boa Safra",
        "antes": {"ativo": True},
        "depois": {"ativo": False},
    }
    assert (remocao.acao, remocao.dados) == (
        "fornecedor.removido",
        {
            "id": f.revenda,
            "nome": "Revenda Boa Safra",
            "contato": None,
            "telefone": "69 99999-0000",
            "cidade": "Ariquemes",
            "observacao": None,
            "ativo": False,
            "demonstracao": False,
        },
    )


def test_pedido_cancelado_guarda_o_que_faltava_chegar(
    fazenda: SimpleNamespace, db: Session
) -> None:
    api, f = fazenda.api, fazenda
    feito = str(HOJE - timedelta(days=2))
    pedido = ok(
        api.post(
            f"{API}/pedidos",
            headers=f.dono,
            json={
                "fornecedor_id": f.revenda,
                "feito_em": feito,
                "itens": [{"insumo_id": f.ureia, "quantidade": 1000, "valor_unitario": 3.2}],
            },
        ),
        201,
    )
    linha = pedido["itens"][0]["id"]
    ok(
        api.post(
            f"{API}/pedidos/{pedido['id']}/receber",
            headers=f.do_ze,
            json={"itens": [{"item_id": linha, "quantidade": 400}]},
        )
    )

    ok(api.post(f"{API}/pedidos/{pedido['id']}/cancelar", headers=f.dono))
    # Cancelar de novo não muda nada, e não há o que registrar.
    ok(api.post(f"{API}/pedidos/{pedido['id']}/cancelar", headers=f.dono))

    # Receber é lançamento comum: as entradas já dizem quem conferiu.
    [evento] = eventos(db)
    assert (evento.acao, evento.entidade, evento.entidade_id, evento.usuario_id) == (
        "pedido.cancelado",
        "pedido",
        pedido["id"],
        f.maria.id,
    )
    assert evento.dados == {
        "situacao_antes": "parcial",
        "fornecedor_id": f.revenda,
        "fornecedor": "Revenda Boa Safra",
        "feito_em": feito,
        "previsto_para": None,
        "itens": [
            {
                "insumo_id": f.ureia,
                "insumo": "Ureia",
                "quantidade": 1000.0,
                "valor_unitario": 3.2,
                "quantidade_recebida": 400.0,
                "falta_receber": 600.0,
            }
        ],
    }


def test_pedido_alterado_guarda_o_antes_e_o_depois(fazenda: SimpleNamespace, db: Session) -> None:
    api, f = fazenda.api, fazenda
    linha = {"insumo_id": f.ureia, "quantidade": 1000, "valor_unitario": 3.2}
    pedido = ok(api.post(f"{API}/pedidos", headers=f.dono, json={"itens": [linha]}), 201)
    previsto = str(HOJE + timedelta(days=5))

    ok(
        api.put(
            f"{API}/pedidos/{pedido['id']}",
            headers=f.dono,
            json={"previsto_para": previsto, "itens": [linha | {"quantidade": 800}]},
        )
    )

    [evento] = eventos(db, "pedido.alterado")
    assert evento.entidade_id == pedido["id"]
    assert evento.dados == {
        "antes": {
            "previsto_para": None,
            "itens": [{"insumo_id": f.ureia, "quantidade": 1000.0, "valor_unitario": 3.2}],
        },
        "depois": {
            "previsto_para": previsto,
            "itens": [{"insumo_id": f.ureia, "quantidade": 800.0, "valor_unitario": 3.2}],
        },
    }


def test_importacao_confirmada_guarda_o_resumo(fazenda: SimpleNamespace, db: Session) -> None:
    api, f = fazenda.api, fazenda
    planilha = (
        "data;insumo;unidade;tipo;quantidade\n"
        "01/10/2026;Ureia;kg;entrada;1.000\n"
        "05/10/2026;Ureia;kg;saída;150\n"
        "03/10/2026;Glifosato;L;entrada;40\n"
    )

    # A prévia não grava, e não há o que registrar.
    ok(api.post(f"{API}/importacoes", headers=f.dono, json={"conteudo": planilha}))
    assert eventos(db) == []
    corpo = {"conteudo": planilha, "confirmar": True}
    assert ok(api.post(f"{API}/importacoes", headers=f.dono, json=corpo))["importado"]

    [evento] = eventos(db)
    assert (evento.acao, evento.entidade, evento.entidade_id, evento.usuario_id) == (
        "importacao.confirmada",
        "importacao",
        None,
        f.maria.id,
    )
    assert evento.dados == {
        "formato": "csv",
        "linhas": 3,
        "entradas": 2,
        "saidas": 1,
        "primeira_data": "2026-10-01",
        "ultima_data": "2026-10-05",
        "ja_lancadas": 0,
        "insumos": [
            {"nome": "Ureia", "unidade": "kg", "novo": False, "entradas": 1000.0, "saidas": 150.0},
            {"nome": "Glifosato", "unidade": "L", "novo": True, "entradas": 40.0, "saidas": 0.0},
        ],
        "fornecedores_novos": [],
        "categorias_novas": [],
    }


def test_importacao_com_erro_nao_grava_nem_deixa_evento(
    fazenda: SimpleNamespace, db: Session
) -> None:
    planilha = "data;insumo;unidade;tipo;quantidade\n01/10/2026;Ureia;kg;entrada;-5\n"
    corpo = {"conteudo": planilha, "confirmar": True}

    resultado = ok(fazenda.api.post(f"{API}/importacoes", headers=fazenda.dono, json=corpo))

    assert not resultado["importado"]
    assert eventos(db) == []
