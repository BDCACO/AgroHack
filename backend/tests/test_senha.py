"""O hash da senha (scrypt da biblioteca padrão), sem banco."""

import unicodedata

from app.core import senha


def test_hash_guarda_os_parametros_e_nao_a_senha() -> None:
    guardado = senha.gerar_hash("milho-safrinha")

    algoritmo, n, r, p, sal, _ = guardado.split("$")
    assert (algoritmo, n, r, p) == ("scrypt", str(senha.N), str(senha.R), str(senha.P))
    assert sal
    assert "milho-safrinha" not in guardado


def test_cada_hash_tem_o_seu_sal() -> None:
    # A mesma senha em dois usuários não pode dar o mesmo hash: senão, quem lê o banco sabe
    # que as senhas são iguais, e uma tabela pronta quebra as duas de uma vez.
    assert senha.gerar_hash("milho-safrinha") != senha.gerar_hash("milho-safrinha")


def test_confere_a_senha_certa_e_recusa_a_errada() -> None:
    guardado = senha.gerar_hash("milho-safrinha")

    assert senha.conferir("milho-safrinha", guardado)
    assert not senha.conferir("milho-safrinh", guardado)
    assert not senha.conferir("Milho-safrinha", guardado)


def test_acento_digitado_no_celular_ou_no_computador_e_a_mesma_senha() -> None:
    # "ç" pode chegar como um caractere só ou como "c" + cedilha, conforme o teclado.
    composta = unicodedata.normalize("NFC", "açaí-colhido")
    decomposta = unicodedata.normalize("NFD", "açaí-colhido")
    assert composta != decomposta

    assert senha.conferir(decomposta, senha.gerar_hash(composta))


def test_hash_com_outro_custo_ainda_confere_e_pede_para_refazer() -> None:
    # Subir o custo depois não pode trancar quem já tem senha: o hash diz com que custo foi
    # feito, e o login refaz com o custo novo.
    antigo = senha.gerar_hash("milho-safrinha", n=2**10)

    assert senha.conferir("milho-safrinha", antigo)
    assert senha.precisa_refazer(antigo)
    assert not senha.precisa_refazer(senha.gerar_hash("milho-safrinha"))


def test_hash_ilegivel_nao_confere_nem_derruba() -> None:
    for guardado in ["", "scrypt$1$2", "bcrypt$x$y$z$a$b", "scrypt$x$8$1$AAAA$AAAA"]:
        assert not senha.conferir("milho-safrinha", guardado)
        assert senha.precisa_refazer(guardado)
