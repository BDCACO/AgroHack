"""Senha guardada como hash Argon2id (`argon2-cffi`), a primeira escolha da OWASP para
senhas: lento e caro em memória de propósito, para quem copiar o banco não testar
milhões de senhas por segundo, nem com placa de vídeo.

O hash leva junto o sal e os parâmetros (`$argon2id$v=19$m=…,t=…,p=…$sal$hash`), para o
custo poder subir depois sem trancar quem já tem senha: o login confere com os
parâmetros antigos e refaz com os novos. As senhas gravadas antes, em scrypt
(`scrypt$n$r$p$sal$hash`), seguem valendo do mesmo jeito: o próximo login as refaz em
Argon2id.
"""

import base64
import binascii
import hashlib
import hmac
import unicodedata

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# O perfil de baixa memória da RFC 9106 (o padrão do argon2-cffi): 64 MiB e 3 passadas,
# uns 0,1 s por tentativa num computador modesto. Folga sobre o mínimo da OWASP
# (19 MiB, 2 passadas) sem pesar no servidor de uma fazenda.
MEMORIA_KIB = 64 * 1024
ITERACOES = 3
PARALELISMO = 4

_PADRAO = PasswordHasher(
    time_cost=ITERACOES, memory_cost=MEMORIA_KIB, parallelism=PARALELISMO, type=Type.ID
)


def gerar_hash(senha: str, *, memoria_kib: int = MEMORIA_KIB, iteracoes: int = ITERACOES) -> str:
    if (memoria_kib, iteracoes) == (MEMORIA_KIB, ITERACOES):
        return _PADRAO.hash(_normalizada(senha))
    # Outro custo: só os testes pedem, para simular um hash gravado com o custo de antes.
    outro = PasswordHasher(
        time_cost=iteracoes, memory_cost=memoria_kib, parallelism=PARALELISMO, type=Type.ID
    )
    return outro.hash(_normalizada(senha))


def conferir(senha: str, guardado: str) -> bool:
    """Compara em tempo constante. Hash ilegível não confere (e não vira 500)."""
    if guardado.startswith("$argon2"):
        try:
            return _PADRAO.verify(guardado, _normalizada(senha))
        except VerifyMismatchError, VerificationError, InvalidHashError:
            return False
    if guardado.startswith("scrypt$"):
        return _conferir_scrypt(senha, guardado)
    return False


def precisa_refazer(guardado: str) -> bool:
    """O hash é do algoritmo de antes (scrypt), ilegível, ou de outro custo."""
    if not guardado.startswith("$argon2id$"):
        return True
    try:
        return _PADRAO.check_needs_rehash(guardado)
    except InvalidHashError, ValueError:
        return True


def _normalizada(senha: str) -> str:
    # NFC: o "ç" digitado no celular pode chegar decomposto ("c" + cedilha), e seria
    # outra senha para o hash.
    return unicodedata.normalize("NFC", senha)


def _conferir_scrypt(senha: str, guardado: str) -> bool:
    """Só para as senhas gravadas antes do Argon2id; nenhuma senha nova usa scrypt."""
    try:
        _, n, r, p, sal, esperado = guardado.split("$")
        sal_bytes, esperado_bytes = base64.b64decode(sal), base64.b64decode(esperado)
        n_, r_, p_ = int(n), int(r), int(p)
        # A memória que o scrypt usa é 128·r·n; o teto padrão (32 MiB) barraria um custo maior.
        calculado = hashlib.scrypt(
            _normalizada(senha).encode(),
            salt=sal_bytes,
            n=n_,
            r=r_,
            p=p_,
            maxmem=128 * r_ * n_ + 1024 * 1024,
            dklen=len(esperado_bytes),
        )
    except ValueError, binascii.Error:
        return False
    return hmac.compare_digest(calculado, esperado_bytes)
