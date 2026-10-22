"""Senha guardada como hash scrypt, da biblioteca padrão (`hashlib`): sem dependência nova.

scrypt é lento e gasta memória de propósito: quem copiar o banco não testa milhões de
senhas por segundo, nem com placa de vídeo. O hash leva junto o sal e os parâmetros com
que foi feito (`scrypt$n$r$p$sal$hash`), para o custo poder subir depois sem trancar
quem já tem senha: o login confere com os parâmetros antigos e refaz com os novos.
"""

import base64
import binascii
import hashlib
import hmac
import secrets
import unicodedata

# 2**14 com r=8: 16 MiB e uns 0,2 s por tentativa num computador modesto. É o custo
# clássico para login interativo; subir N dobra o tempo e a memória.
N = 2**14
R = 8
P = 1
TAMANHO_DO_SAL = 16
TAMANHO_DO_HASH = 32
_ALGORITMO = "scrypt"


def gerar_hash(senha: str, *, n: int = N, r: int = R, p: int = P) -> str:
    sal = secrets.token_bytes(TAMANHO_DO_SAL)
    calculado = _scrypt(senha, sal, n, r, p, TAMANHO_DO_HASH)
    return "$".join([_ALGORITMO, str(n), str(r), str(p), _b64(sal), _b64(calculado)])


def conferir(senha: str, guardado: str) -> bool:
    """Compara em tempo constante. Hash ilegível não confere (e não vira 500)."""
    try:
        algoritmo, n, r, p, sal, esperado = guardado.split("$")
        if algoritmo != _ALGORITMO:
            return False
        sal_bytes, esperado_bytes = base64.b64decode(sal), base64.b64decode(esperado)
        calculado = _scrypt(senha, sal_bytes, int(n), int(r), int(p), len(esperado_bytes))
    except ValueError, binascii.Error:
        return False
    return hmac.compare_digest(calculado, esperado_bytes)


def precisa_refazer(guardado: str) -> bool:
    """O hash foi feito com outros parâmetros (o custo subiu desde então)."""
    return guardado.split("$")[:4] != [_ALGORITMO, str(N), str(R), str(P)]


def _scrypt(senha: str, sal: bytes, n: int, r: int, p: int, tamanho: int) -> bytes:
    # NFC: o "ç" digitado no celular pode chegar decomposto ("c" + cedilha), e seria
    # outra senha para o hash.
    normalizada = unicodedata.normalize("NFC", senha).encode()
    # A memória que o scrypt usa é 128·r·n; o teto padrão (32 MiB) barraria um custo maior.
    memoria = 128 * r * n + 1024 * 1024
    return hashlib.scrypt(normalizada, salt=sal, n=n, r=r, p=p, maxmem=memoria, dklen=tamanho)


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode()
