"""O contador de tentativas por janela de tempo, sem HTTP e sem dormir: o relógio é dado."""

import pytest

from app.core.limite_de_taxa import Janela, LimiteEmMemoria, Recusa

POR_MINUTO = Janela(limite=10, segundos=60)
POR_HORA = Janela(limite=20, segundos=3600)


class Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


@pytest.fixture
def relogio() -> Relogio:
    return Relogio()


def test_cabe_ate_o_limite_e_recusa_a_seguinte(relogio: Relogio) -> None:
    limite = LimiteEmMemoria([POR_MINUTO], relogio)

    assert [limite.tentar("1.2.3.4") for _ in range(10)] == [None] * 10
    assert limite.tentar("1.2.3.4") == Recusa(espere=60, janela=POR_MINUTO, primeira=True)


def test_a_recusa_diz_quanto_esperar_e_libera_depois(relogio: Relogio) -> None:
    limite = LimiteEmMemoria([POR_MINUTO], relogio)
    for segundo in range(10):
        relogio.agora = 1000.0 + segundo
        limite.tentar("ip")

    relogio.agora = 1030.0
    recusa = limite.tentar("ip")
    # A mais antiga (1000) sai da janela em 1060: faltam 30 s.
    assert recusa is not None
    assert recusa.espere == 30
    relogio.agora = 1060.0
    assert limite.tentar("ip") is None
    # Só uma vaga abriu (a de 1000); a de 1001 sai em 1061.
    assert limite.tentar("ip") is not None


def test_insistir_durante_a_recusa_nao_conta_nem_empurra_o_fim(relogio: Relogio) -> None:
    limite = LimiteEmMemoria([POR_MINUTO], relogio)
    for _ in range(10):
        limite.tentar("ip")

    for segundo in range(1, 60):
        relogio.agora = 1000.0 + segundo
        assert limite.tentar("ip") is not None
    relogio.agora = 1060.0
    assert limite.tentar("ip") is None


def test_avisa_a_primeira_recusa_uma_vez_so(relogio: Relogio) -> None:
    limite = LimiteEmMemoria([POR_MINUTO], relogio)
    for _ in range(10):
        limite.tentar("ip")

    primeiras = [limite.tentar("ip").primeira for _ in range(5)]  # type: ignore[union-attr]
    assert primeiras == [True, False, False, False, False]
    # Liberou e passou do limite de novo: é outra rodada, e avisa de novo.
    relogio.agora += 60
    for _ in range(10):
        assert limite.tentar("ip") is None
    assert limite.tentar("ip").primeira is True  # type: ignore[union-attr]


def test_a_janela_maior_vale_mesmo_com_as_tentativas_espacadas(relogio: Relogio) -> None:
    # Dez por minuto, mas não 600 por hora: quem espaça as tentativas para caber no minuto
    # esbarra no teto da hora.
    limite = LimiteEmMemoria([POR_MINUTO, POR_HORA], relogio)
    for rodada in range(2):
        relogio.agora = 1000.0 + rodada * 61
        for _ in range(10):
            assert limite.tentar("ip") is None

    relogio.agora = 1000.0 + 3 * 61
    recusa = limite.tentar("ip")
    assert recusa is not None
    assert recusa.janela == POR_HORA
    # A mais antiga das 20 (1000) sai da hora em 4600.
    assert recusa.espere == 4600 - relogio.agora
    relogio.agora = 4600.0
    assert limite.tentar("ip") is None


def test_cada_chave_tem_a_sua_conta(relogio: Relogio) -> None:
    limite = LimiteEmMemoria([POR_MINUTO], relogio)
    for _ in range(10):
        limite.tentar("ip-do-ataque")

    assert limite.tentar("ip-do-ataque") is not None
    assert limite.tentar("ip-da-fazenda") is None


def test_a_memoria_tem_teto(relogio: Relogio) -> None:
    limite = LimiteEmMemoria([POR_MINUTO], relogio, max_chaves=100)
    for numero in range(1000):
        limite.tentar(f"ip-{numero}")

    assert len(limite._tentativas) <= 100
    # A chave parada há mais que a maior janela é esquecida na próxima tentativa.
    relogio.agora += 61
    limite.tentar("outro")
    assert list(limite._tentativas) == ["outro"]


def test_janela_sem_limite_ou_duracao_e_recusada() -> None:
    with pytest.raises(ValueError, match="maiores que zero"):
        Janela(limite=0, segundos=60)
    with pytest.raises(ValueError, match="ao menos uma janela"):
        LimiteEmMemoria([])
