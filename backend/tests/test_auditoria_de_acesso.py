"""O que mexe em quem entra no sistema deixa rastro: usuário criado, alterado, senha
redefinida ou trocada, login recusado e bloqueado. Nunca com a senha, o hash ou o token."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import usuarios as comando
from app.core.relogio import agora
from app.models import Sessao, Usuario
from tests.conftest import SENHA, CriarUsuario, entrar, erro_inesperado
from tests.test_auditoria_do_estoque import API, ok
from tests.test_eventos_de_auditoria import eventos

SENHA_DO_ZE = "senha-do-ze-1"


@pytest.fixture
def equipe(cliente_autenticado: TestClient, criar_usuario: CriarUsuario) -> SimpleNamespace:
    maria = criar_usuario("maria", papel="dono", nome="Dona Maria")
    return SimpleNamespace(
        api=cliente_autenticado, maria=maria, dono=entrar(cliente_autenticado, "maria")
    )


def cadastrar_ze(equipe: SimpleNamespace) -> dict:
    corpo = {"nome": "Zé do Trator", "login": "ze", "senha": SENHA_DO_ZE, "papel": "funcionario"}
    return ok(equipe.api.post(f"{API}/usuarios", headers=equipe.dono, json=corpo), 201)


def tentar(api: TestClient, login: str, senha: str) -> int:
    corpo = {"login": login, "senha": senha, "dispositivo": "Celular estranho"}
    return api.post(f"{API}/auth/entrar", json=corpo).status_code


def test_dono_cria_altera_e_redefine_a_senha(equipe: SimpleNamespace, db: Session) -> None:
    api = equipe.api
    ze = cadastrar_ze(equipe)
    ok(api.put(f"{API}/usuarios/{ze['id']}", headers=equipe.dono, json={"ativo": False}))
    ok(
        api.put(
            f"{API}/usuarios/{ze['id']}/senha",
            headers=equipe.dono,
            json={"senha_nova": "outra-senha-do-ze"},
        ),
        204,
    )

    criado, alterado, redefinida = eventos(db)
    for evento in (criado, alterado, redefinida):
        assert (evento.usuario_id, evento.entidade, evento.entidade_id) == (
            equipe.maria.id,
            "usuario",
            ze["id"],
        )
    assert (criado.acao, criado.dados) == (
        "usuario.criado",
        {"login": "ze", "nome": "Zé do Trator", "papel": "funcionario"},
    )
    assert (alterado.acao, alterado.dados) == (
        "usuario.alterado",
        {"login": "ze", "antes": {"ativo": True}, "depois": {"ativo": False}},
    )
    assert (redefinida.acao, redefinida.dados) == (
        "usuario.senha_redefinida",
        {"login": "ze", "desbloqueou": False},
    )


def test_alterar_sem_mudar_nada_nao_deixa_evento(equipe: SimpleNamespace, db: Session) -> None:
    ze = cadastrar_ze(equipe)

    ok(equipe.api.put(f"{API}/usuarios/{ze['id']}", headers=equipe.dono, json={"ativo": True}))

    assert [e.acao for e in eventos(db)] == ["usuario.criado"]


def test_senha_errada_bloqueio_e_tentativa_durante_o_bloqueio(
    equipe: SimpleNamespace, db: Session
) -> None:
    api = equipe.api
    ze = cadastrar_ze(equipe)

    for _ in range(5):
        assert tentar(api, "ze", "chute-errado") == 401
    assert tentar(api, "ze", SENHA_DO_ZE) == 401  # bloqueado, mesmo com a senha certa

    recusas = eventos(db, "login.recusado")
    assert [e.dados for e in recusas] == [{"login": "ze", "motivo": "senha_incorreta"}] * 5 + [
        {"login": "ze", "motivo": "bloqueado"}
    ]
    for evento in recusas:
        # Quem tentou não é conhecido; o alvo, sim.
        assert (evento.usuario_id, evento.entidade, evento.entidade_id) == (
            None,
            "usuario",
            ze["id"],
        )
        assert (evento.ip, evento.dispositivo) == ("testclient", "Celular estranho")
    [bloqueio] = eventos(db, "login.bloqueado")
    assert bloqueio.entidade_id == ze["id"]
    assert bloqueio.dados["login"] == "ze"
    assert bloqueio.dados["tentativas"] == 5
    bloqueado_ate = datetime.fromisoformat(bloqueio.dados["bloqueado_ate"])
    assert bloqueado_ate == db.get(Usuario, ze["id"]).bloqueado_ate
    # O bloqueio veio junto com a quinta recusa, e antes da sexta.
    assert recusas[4].id < bloqueio.id < recusas[5].id

    # A senha redefinida desfaz o bloqueio, e o evento diz isso.
    corpo = {"senha_nova": "outra-senha-do-ze"}
    ok(api.put(f"{API}/usuarios/{ze['id']}/senha", headers=equipe.dono, json=corpo), 204)
    assert eventos(db, "usuario.senha_redefinida")[0].dados == {"login": "ze", "desbloqueou": True}


def test_desativado_com_a_senha_certa_e_login_inexistente(
    equipe: SimpleNamespace, db: Session
) -> None:
    api = equipe.api
    ze = cadastrar_ze(equipe)
    ok(api.put(f"{API}/usuarios/{ze['id']}", headers=equipe.dono, json={"ativo": False}))

    assert tentar(api, "ze", SENHA_DO_ZE) == 401
    # O login que não existe não deixa evento: não há a quem atribuir, e o que se digitou no
    # campo do login pode ser uma senha.
    assert tentar(api, "senha-no-lugar-do-login", "x") == 401

    [recusa] = eventos(db, "login.recusado")
    assert recusa.dados == {"login": "ze", "motivo": "usuario_desativado"}


def test_trocar_a_propria_senha(equipe: SimpleNamespace, db: Session) -> None:
    api = equipe.api
    errada = {"senha_atual": "nao-e-esta", "senha_nova": "nova-senha-da-maria"}
    certa = {"senha_atual": SENHA, "senha_nova": "nova-senha-da-maria"}

    assert api.put(f"{API}/auth/senha", headers=equipe.dono, json=errada).status_code == 400
    ok(api.put(f"{API}/auth/senha", headers=equipe.dono, json=certa), 204)

    recusa, trocada = eventos(db)
    # Aqui quem tentou é conhecido: a sessão é dela.
    assert (recusa.acao, recusa.usuario_id, recusa.entidade_id, recusa.dados) == (
        "login.recusado",
        equipe.maria.id,
        equipe.maria.id,
        {"login": "maria", "motivo": "senha_atual_incorreta"},
    )
    assert (trocada.acao, trocada.usuario_id, trocada.entidade_id, trocada.dados) == (
        "usuario.senha_trocada",
        equipe.maria.id,
        equipe.maria.id,
        {"login": "maria"},
    )


def test_a_recusa_entra_junto_com_a_contagem_de_falhas(
    equipe: SimpleNamespace, db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Sem onde gravar o evento, a falha também não conta: a recusa e a contagem são uma
    transação só."""
    ze = cadastrar_ze(equipe)
    db.execute(text("DROP TABLE eventos_de_auditoria"))

    assert tentar(equipe.api, "ze", "chute-errado") == 500
    erro = erro_inesperado(caplog)
    assert isinstance(erro, OperationalError)
    assert "eventos_de_auditoria" in str(erro)

    db.rollback()
    assert db.get(Usuario, ze["id"]).falhas_seguidas == 0


def test_nenhum_evento_leva_senha_hash_ou_token(equipe: SimpleNamespace, db: Session) -> None:
    api = equipe.api
    ze = cadastrar_ze(equipe)
    do_ze = entrar(api, "ze", SENHA_DO_ZE)
    tentar(api, "ze", "chute-errado")
    ok(api.put(f"{API}/usuarios/{ze['id']}", headers=equipe.dono, json={"papel": "dono"}))
    corpo = {"senha_nova": "senha-redefinida-1"}
    ok(api.put(f"{API}/usuarios/{ze['id']}/senha", headers=equipe.dono, json=corpo), 204)
    do_ze = entrar(api, "ze", "senha-redefinida-1")
    troca = {"senha_atual": "senha-redefinida-1", "senha_nova": "senha-trocada-22"}
    ok(api.put(f"{API}/auth/senha", headers=do_ze, json=troca), 204)

    trilha = json.dumps([e.dados for e in eventos(db)], ensure_ascii=False)
    assert len(eventos(db)) == 5
    segredos = [SENHA, SENHA_DO_ZE, "chute-errado", "senha-redefinida-1", "senha-trocada-22"]
    segredos += [
        cabecalho.split()[-1]
        for cabecalho in (equipe.dono["Authorization"], do_ze["Authorization"])
    ]
    segredos += [u.senha_hash for u in db.query(Usuario)] + [s.token_hash for s in db.query(Sessao)]
    for segredo in segredos:
        assert segredo not in trilha
    assert "argon2" not in trilha
    # Nem a resposta da consulta.
    resposta = api.get(f"{API}/auditoria", headers=equipe.dono)
    for segredo in segredos:
        assert segredo not in resposta.text


def test_dono_criado_pelo_comando_no_servidor(db: Session) -> None:
    dono = comando.criar_dono(db, "maria", "Dona Maria", "senha-do-dono-1", outro_dono=False)

    [evento] = eventos(db)
    assert (evento.acao, evento.usuario_id, evento.origem, evento.ip) == (
        "usuario.criado",
        None,
        "terminal",
        None,
    )
    assert (evento.entidade_id, evento.dados) == (
        dono.id,
        {"login": "maria", "nome": "Dona Maria", "papel": "dono"},
    )
    assert agora() >= evento.ocorrido_em
