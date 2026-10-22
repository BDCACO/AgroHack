"""O comando que cria o primeiro dono (`python -m app.usuarios criar-dono`)."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import usuarios as comando
from app.core import senha
from app.models import Usuario


@pytest.fixture(autouse=True)
def banco_do_teste(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    fabrica = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(comando, "get_sessionmaker", lambda: fabrica)
    monkeypatch.delenv("SENHA_DO_DONO", raising=False)


def criar_dono(*argumentos: str) -> None:
    comando.main(["criar-dono", *argumentos])


def test_cria_o_dono_com_a_senha_da_variavel_de_ambiente(
    db: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SENHA_DO_DONO", "senha-da-maria")

    criar_dono("--login", "Maria", "--nome", "Dona Maria")

    dono = db.scalar(select(Usuario))
    assert (dono.login, dono.nome, dono.papel, dono.ativo) == ("maria", "Dona Maria", "dono", True)
    assert senha.conferir("senha-da-maria", dono.senha_hash)
    assert "senha-da-maria" not in capsys.readouterr().out


def test_sem_a_variavel_pede_a_senha_duas_vezes_no_terminal(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    digitadas = iter(["senha-da-maria", "senha-da-maria"])
    monkeypatch.setattr(comando.getpass, "getpass", lambda _: next(digitadas))

    criar_dono("--login", "maria", "--nome", "Dona Maria")

    assert senha.conferir("senha-da-maria", db.scalar(select(Usuario)).senha_hash)


def test_confirmacao_diferente_nao_cria(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    digitadas = iter(["senha-da-maria", "senha-da-mari"])
    monkeypatch.setattr(comando.getpass, "getpass", lambda _: next(digitadas))

    with pytest.raises(SystemExit, match="não conferem"):
        criar_dono("--login", "maria", "--nome", "Dona Maria")
    assert db.scalar(select(Usuario)) is None


def test_ja_havendo_dono_ativo_so_cria_outro_pedindo(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sem a trava, quem tem acesso ao servidor criaria um dono para si sem que o dono saiba;
    # o caminho normal para o segundo dono é o próprio dono, em POST /usuarios.
    monkeypatch.setenv("SENHA_DO_DONO", "senha-da-maria")
    criar_dono("--login", "maria", "--nome", "Dona Maria")

    with pytest.raises(SystemExit, match="--outro-dono"):
        criar_dono("--login", "joao", "--nome", "João")
    criar_dono("--login", "joao", "--nome", "João", "--outro-dono")

    assert [u.login for u in db.scalars(select(Usuario).order_by(Usuario.id))] == ["maria", "joao"]


def test_dono_desativado_nao_impede_criar_um_novo(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A saída para quando o único dono foi desativado (ou esqueceu a senha e saiu da fazenda).
    monkeypatch.setenv("SENHA_DO_DONO", "senha-da-maria")
    criar_dono("--login", "maria", "--nome", "Dona Maria")
    db.scalar(select(Usuario)).ativo = False
    db.commit()

    criar_dono("--login", "joao", "--nome", "João")

    assert db.scalar(select(Usuario).where(Usuario.login == "joao")).papel == "dono"


@pytest.mark.parametrize(
    ("argumentos", "senha_digitada", "frase"),
    [
        (["--login", "maria", "--nome", "Maria"], "curta", "pelo menos 8 caracteres"),
        (["--login", "maria josé", "--nome", "Maria"], "senha-da-maria", "O login só pode"),
        (["--login", "maria", "--nome", " "], "senha-da-maria", "nome"),
    ],
)
def test_dado_invalido_explica_e_nao_cria(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    argumentos: list[str],
    senha_digitada: str,
    frase: str,
) -> None:
    monkeypatch.setenv("SENHA_DO_DONO", senha_digitada)

    with pytest.raises(SystemExit, match=frase):
        criar_dono(*argumentos)
    assert db.scalar(select(Usuario)) is None


def test_login_ja_usado(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENHA_DO_DONO", "senha-da-maria")
    criar_dono("--login", "maria", "--nome", "Dona Maria")

    with pytest.raises(SystemExit, match="Já existe um usuário com o login maria"):
        criar_dono("--login", "MARIA", "--nome", "Outra", "--outro-dono")
