"""O limite de pedidos por IP: as tentativas de login (o maior risco: quem sabe um login
podia bloqueá-lo de propósito e encher a trilha de auditoria) e as escritas em geral. As
leituras do Painel não têm limite. A prova com o uvicorn de verdade está em
tests/integracao/test_blindagem_da_api.py."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.protecoes import frase_de_espera
from app.core.config import Settings
from app.core.database import get_db
from app.core.limite_de_taxa import Janela, LimiteEmMemoria
from app.core.relogio import hoje
from app.main import create_app
from app.models import EventoDeAuditoria
from tests.conftest import SENHA, CriarUsuario

IP = "203.0.113.7"
FRASE_DO_LOGIN = "Muitas tentativas de entrar a partir desta rede. Espere 1 minuto e tente de novo."
FRASE_DA_ESCRITA = "Muitos pedidos seguidos a partir desta rede. Espere 1 minuto e tente de novo."


def criar_api(db: Session, **config: object) -> object:
    configuracao = {"autenticacao": True, "limite_por_ip": True} | config
    app = create_app(Settings(environment="test", database_url="sqlite://", **configuracao))
    app.dependency_overrides[get_db] = lambda: db
    return app


def cliente(app: object, ip: str = IP) -> TestClient:
    return TestClient(app, client=(ip, 50000))  # type: ignore[arg-type]


def tentar(api: TestClient, login: str = "ninguem", senha: str = "senha-errada") -> int:
    return api.post("/api/v1/auth/entrar", json={"login": login, "senha": senha}).status_code


def eventos(db: Session) -> list[EventoDeAuditoria]:
    return list(db.scalars(select(EventoDeAuditoria).order_by(EventoDeAuditoria.id)))


def test_os_numeros_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    # O conftest o desliga para a suíte; sem a variável, vem ligado.
    monkeypatch.delenv("LIMITE_POR_IP")
    padrao = Settings(environment="test", database_url="sqlite://", _env_file=None)

    assert padrao.limite_por_ip is True
    assert padrao.limite_login_por_minuto == 10
    assert padrao.limite_login_por_hora == 20
    assert padrao.limite_escritas_por_minuto == 120


def test_produtor_que_erra_a_senha_tres_vezes_entra(
    db: Session, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("maria", "dono")
    api = cliente(criar_api(db))

    assert [tentar(api, "maria") for _ in range(3)] == [401, 401, 401]
    assert tentar(api, "maria", SENHA) == 200


def test_passou_de_10_no_minuto_e_429_com_retry_after(db: Session) -> None:
    api = cliente(criar_api(db))

    assert [tentar(api) for _ in range(10)] == [401] * 10
    resposta = api.post("/api/v1/auth/entrar", json={"login": "ninguem", "senha": "x" * 8})

    assert resposta.status_code == 429
    assert 1 <= int(resposta.headers["Retry-After"]) <= 60
    assert resposta.json()["detail"] == FRASE_DO_LOGIN
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Request-ID" in resposta.headers


def test_o_429_nao_conta_como_erro_do_usuario(db: Session, criar_usuario: CriarUsuario) -> None:
    # Senão, quem chega ao limite ainda bloquearia o login de alguém com as tentativas que
    # nem foram conferidas.
    maria = criar_usuario("maria", "dono")
    api = cliente(criar_api(db))
    for _ in range(10):
        tentar(api)

    assert [tentar(api, "maria") for _ in range(6)] == [429] * 6

    db.refresh(maria)
    assert (maria.falhas_seguidas, maria.bloqueado_ate) == (0, None)
    assert [e.acao for e in eventos(db)] == ["login.limitado"]


def test_um_evento_so_quando_o_ip_passa_a_ser_limitado(db: Session) -> None:
    # Um por rodada, e não um por tentativa: quem insiste não enche a trilha.
    api = cliente(criar_api(db))
    for _ in range(10):
        tentar(api)

    assert [tentar(api) for _ in range(20)] == [429] * 20

    [evento] = eventos(db)
    assert (evento.acao, evento.ip, evento.usuario_id) == ("login.limitado", IP, None)
    assert evento.dados["limite"] == 10
    assert evento.dados["janela_segundos"] == 60
    assert "liberado_em" in evento.dados


def test_outro_ip_continua_entrando(db: Session, criar_usuario: CriarUsuario) -> None:
    criar_usuario("maria", "dono")
    app = criar_api(db)
    ataque, fazenda = cliente(app, IP), cliente(app, "198.51.100.20")
    for _ in range(11):
        tentar(ataque)

    assert tentar(ataque, "maria", SENHA) == 429
    assert tentar(fazenda, "maria", SENHA) == 200


def test_x_forwarded_for_nao_engana_o_limite(db: Session) -> None:
    # O cabeçalho qualquer um escreve: trocá-lo a cada tentativa não pode zerar a conta.
    api = cliente(criar_api(db))
    respostas = [
        api.post(
            "/api/v1/auth/entrar",
            json={"login": "ninguem", "senha": "senha-errada"},
            headers={"X-Forwarded-For": f"10.0.0.{numero}"},
        ).status_code
        for numero in range(11)
    ]

    assert respostas == [401] * 10 + [429]


def test_as_janelas_vem_da_configuracao(db: Session) -> None:
    app = criar_api(db, limite_login_por_minuto=3, limite_login_por_hora=7)

    assert app.state.limite_de_login._janelas == (Janela(3, 60), Janela(7, 3600))
    assert [tentar(cliente(app)) for _ in range(4)] == [401, 401, 401, 429]


def test_desligado_nao_limita(db: Session) -> None:
    api = cliente(criar_api(db, limite_por_ip=False))

    assert [tentar(api) for _ in range(15)] == [401] * 15


def test_escritas_alem_do_limite_sao_429_e_nao_gravam(db: Session) -> None:
    api = cliente(criar_api(db, autenticacao=False, limite_escritas_por_minuto=3))

    criados = [
        api.post("/api/v1/insumos", json={"nome": f"Insumo {n}", "unidade": "kg"}).status_code
        for n in range(4)
    ]

    assert criados == [201, 201, 201, 429]
    recusado = api.post("/api/v1/insumos", json={"nome": "Mais um", "unidade": "kg"})
    assert recusado.json()["detail"] == FRASE_DA_ESCRITA
    assert 1 <= int(recusado.headers["Retry-After"]) <= 60
    assert [i["nome"] for i in api.get("/api/v1/insumos").json()] == [
        "Insumo 0",
        "Insumo 1",
        "Insumo 2",
    ]
    # Sem evento de auditoria: não é tentativa de entrar à força, e cada 429 seria uma linha.
    assert eventos(db) == []


def test_leituras_nao_tem_limite(db: Session) -> None:
    # O Painel recarrega tudo a cada alteração: limitar a leitura travaria a tela.
    api = cliente(criar_api(db, autenticacao=False, limite_escritas_por_minuto=1))

    assert {api.get("/api/v1/insumos").status_code for _ in range(50)} == {200}


def test_o_lote_do_app_conta_como_um_pedido(db: Session) -> None:
    api = cliente(criar_api(db, autenticacao=False, limite_escritas_por_minuto=3))
    insumo = api.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"}).json()["id"]
    fila = [
        {
            "uuid": str(uuid4()),
            "insumo_id": insumo,
            "tipo": "entrada",
            "data": str(hoje()),
            "quantidade": 1,
        }
        for _ in range(200)
    ]

    envio = api.post("/api/v1/movimentacoes/lote", json={"movimentacoes": fila})
    reenvio = api.post("/api/v1/movimentacoes/lote", json={"movimentacoes": fila})

    assert envio.json()["resumo"]["gravadas"] == 200
    assert reenvio.json()["resumo"]["ja_existiam"] == 200


def test_o_login_tem_o_limite_dele_e_nao_o_das_escritas(db: Session) -> None:
    api = cliente(criar_api(db, limite_escritas_por_minuto=1))

    assert [tentar(api) for _ in range(5)] == [401] * 5


def test_o_teto_da_hora_pede_mais_minutos_na_frase(db: Session) -> None:
    # Quem espaça as tentativas para caber no minuto esbarra no teto da hora, e a frase diz
    # quantos minutos faltam, e não "1 minuto".
    app = criar_api(db)
    relogio = [1000.0]
    app.state.limite_de_login = LimiteEmMemoria(
        [Janela(10, 60), Janela(20, 3600)], lambda: relogio[0]
    )
    api = cliente(app)
    for rodada in range(2):
        relogio[0] = 1000.0 + rodada * 61
        assert [tentar(api) for _ in range(10)] == [401] * 10
    relogio[0] = 1000.0 + 2 * 61

    resposta = api.post("/api/v1/auth/entrar", json={"login": "ninguem", "senha": "x" * 8})

    # A primeira das 20 (em 1000) sai da hora em 4600: faltam 3478 s, uns 58 minutos.
    assert resposta.status_code == 429
    assert resposta.headers["Retry-After"] == "3478"
    assert resposta.json()["detail"] == (
        "Muitas tentativas de entrar a partir desta rede. Espere 58 minutos e tente de novo."
    )
    [evento] = eventos(db)
    assert (evento.dados["limite"], evento.dados["janela_segundos"]) == (20, 3600)


def test_frase_de_espera_em_minutos_para_cima() -> None:
    assert frase_de_espera("Calma", 1) == "Calma. Espere 1 minuto e tente de novo."
    assert frase_de_espera("Calma", 60) == "Calma. Espere 1 minuto e tente de novo."
    assert frase_de_espera("Calma", 61) == "Calma. Espere 2 minutos e tente de novo."
    assert frase_de_espera("Calma", 3540) == "Calma. Espere 59 minutos e tente de novo."


def test_teto_da_hora_menor_que_o_do_minuto_e_recusado() -> None:
    with pytest.raises(ValueError, match="LIMITE_LOGIN_POR_HORA"):
        Settings(
            environment="test",
            database_url="sqlite://",
            limite_login_por_minuto=10,
            limite_login_por_hora=5,
        )


def test_limite_zero_e_recusado() -> None:
    with pytest.raises(ValueError, match="limite_escritas_por_minuto"):
        Settings(environment="test", database_url="sqlite://", limite_escritas_por_minuto=0)


def test_texto_que_nao_e_ip_nao_abre_conta_nova_nem_entra_na_trilha(db: Session) -> None:
    # Se o uvicorn subisse sem --no-proxy-headers, o `client` seria o texto do
    # X-Forwarded-For. Cada texto não pode abrir uma conta nova, nem ir para a trilha.
    app = criar_api(db)
    respostas = [tentar(cliente(app, f"forjado-{numero}\nlinha")) for numero in range(11)]

    assert respostas == [401] * 10 + [429]
    [evento] = (
        db.execute(select(EventoDeAuditoria).where(EventoDeAuditoria.acao == "login.limitado"))
        .scalars()
        .all()
    )
    assert evento.ip is None


def test_o_ip_vai_na_forma_canonica(db: Session) -> None:
    # O mesmo IPv6 escrito de dois jeitos é a mesma conta.
    app = criar_api(db)
    for _ in range(5):
        tentar(cliente(app, "2001:db8::1"))
    for _ in range(5):
        tentar(cliente(app, "2001:0db8:0:0:0:0:0:1"))

    assert tentar(cliente(app, "2001:db8::1")) == 429
