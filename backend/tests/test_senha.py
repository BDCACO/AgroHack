"""O hash da senha (Argon2id), sem banco. E as senhas gravadas antes, em scrypt, que
continuam valendo até o próximo login refazê-las."""

import base64
import hashlib
import secrets
import unicodedata

from app.core import senha


def scrypt_de_antes(texto: str) -> str:
    """Um hash como a versão anterior gravava (`scrypt$n$r$p$sal$hash`)."""
    sal = secrets.token_bytes(16)
    calculado = hashlib.scrypt(texto.encode(), salt=sal, n=2**14, r=8, p=1, dklen=32)
    b64 = base64.b64encode
    return f"scrypt${2**14}$8$1${b64(sal).decode()}${b64(calculado).decode()}"


def test_hash_e_argon2id_com_os_parametros_e_sem_a_senha() -> None:
    guardado = senha.gerar_hash("milho-safrinha")

    assert guardado.startswith("$argon2id$v=19$")
    custo = f"m={senha.MEMORIA_KIB},t={senha.ITERACOES},p={senha.PARALELISMO}$"
    assert custo in guardado
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


def test_senha_gravada_em_scrypt_ainda_confere_e_pede_para_refazer() -> None:
    # Trocar o algoritmo não pode trancar quem já tem senha: o login confere pelo hash
    # antigo e o refaz em Argon2id.
    antigo = scrypt_de_antes("milho-safrinha")

    assert senha.conferir("milho-safrinha", antigo)
    assert not senha.conferir("milho-safrinh", antigo)
    assert senha.precisa_refazer(antigo)
    assert not senha.precisa_refazer(senha.gerar_hash("milho-safrinha"))


def test_argon2_com_outro_custo_ainda_confere_e_pede_para_refazer() -> None:
    antigo = senha.gerar_hash("milho-safrinha", memoria_kib=8 * 1024, iteracoes=1)

    assert senha.conferir("milho-safrinha", antigo)
    assert senha.precisa_refazer(antigo)


def test_hash_ilegivel_nao_confere_nem_derruba() -> None:
    for guardado in [
        "",
        "scrypt$1$2",
        "bcrypt$x$y$z$a$b",
        "scrypt$x$8$1$AAAA$AAAA",
        "$argon2id$v=19$m=65536,t=3,p=4$quebrado",
        "$argon2i$lixo",
    ]:
        assert not senha.conferir("milho-safrinha", guardado)
        assert senha.precisa_refazer(guardado)
