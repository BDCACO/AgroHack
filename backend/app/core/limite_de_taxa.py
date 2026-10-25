"""Quantas tentativas cabem numa janela de tempo, por chave (o IP de quem pede).

`LimiteDeTaxa` é a interface que a API usa; `LimiteEmMemoria` a implementa na memória do
processo, o que basta enquanto a API roda num processo só (o uvicorn do compose). Com
vários processos ou réplicas, cada um contaria à parte e o limite real seria o número
deles vezes o configurado: aí a contagem tem de morar fora, no PostgreSQL (uma tabela com
as tentativas e um `DELETE` das velhas) ou num Redis, numa classe com o mesmo `tentar`.
Reiniciar a API também zera a contagem, o que só devolve a quem pedia demais a cota de uma
janela.
"""

import math
import threading
import time
from bisect import bisect_right
from collections import OrderedDict, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Janela:
    """`limite` tentativas a cada `segundos`."""

    limite: int
    segundos: int

    def __post_init__(self) -> None:
        if self.limite <= 0 or self.segundos <= 0:
            raise ValueError("a janela precisa de limite e duração maiores que zero")


@dataclass(frozen=True)
class Recusa:
    """A tentativa não coube. `espere` é quanto falta, em segundos inteiros (o
    `Retry-After`), para caber de novo; `primeira` diz se esta chave acabou de passar do
    limite (a primeira recusa desde a última tentativa aceita), para avisar uma vez só, e
    não a cada pedido de quem insiste."""

    espere: int
    janela: Janela
    primeira: bool


class LimiteDeTaxa(Protocol):
    def tentar(self, chave: str) -> Recusa | None:
        """Conta a tentativa se ela cabe (devolve None); se não cabe, devolve a recusa e
        não a conta: quem insiste durante a recusa não empurra o fim dela para frente."""
        ...


class LimiteEmMemoria:
    """Janela deslizante exata: guarda o instante de cada tentativa aceita na maior janela
    (no máximo o maior limite por chave) e conta quantas caem em cada uma.

    Seguro entre threads (a rota de login é síncrona e roda no threadpool). A memória tem
    teto: chave sem tentativa na maior janela é esquecida, e passando de `max_chaves` (um
    ataque de muitos IPs, que o IPv6 torna barato) a que ficou mais tempo sem pedir sai
    primeiro. Esquecer uma chave só a deixa tentar de novo, e o bloqueio por usuário no
    banco continua valendo."""

    def __init__(
        self,
        janelas: Sequence[Janela],
        relogio: Callable[[], float] = time.monotonic,
        max_chaves: int = 50_000,
    ) -> None:
        if not janelas:
            raise ValueError("o limite precisa de ao menos uma janela")
        self._janelas = tuple(sorted(janelas, key=lambda j: j.segundos))
        self._maior = max(j.segundos for j in self._janelas)
        self._relogio = relogio
        self._max_chaves = max_chaves
        self._tentativas: OrderedDict[str, deque[float]] = OrderedDict()
        self._recusadas: set[str] = set()
        self._trava = threading.Lock()

    def tentar(self, chave: str) -> Recusa | None:
        with self._trava:
            agora = self._relogio()
            instantes = self._tentativas.get(chave)
            if instantes is None:
                instantes = self._tentativas[chave] = deque()
            self._tentativas.move_to_end(chave)
            while instantes and instantes[0] <= agora - self._maior:
                instantes.popleft()
            for janela in self._janelas:
                inicio = agora - janela.segundos
                dentro = len(instantes) - bisect_right(instantes, inicio)
                if dentro >= janela.limite:
                    # Volta a caber quando a mais antiga das `limite` últimas sair da janela.
                    sai_em = instantes[-janela.limite] + janela.segundos
                    primeira = chave not in self._recusadas
                    self._recusadas.add(chave)
                    return Recusa(max(1, math.ceil(sai_em - agora)), janela, primeira)
            instantes.append(agora)
            self._recusadas.discard(chave)
            self._esquecer_as_paradas(agora)
            return None

    def _esquecer_as_paradas(self, agora: float) -> None:
        # Da mais parada para a mais recente (a ordem do OrderedDict): para na primeira que
        # ainda tem tentativa na maior janela.
        while self._tentativas:
            chave, instantes = next(iter(self._tentativas.items()))
            parada = not instantes or instantes[-1] <= agora - self._maior
            if not parada and len(self._tentativas) <= self._max_chaves:
                break
            del self._tentativas[chave]
            self._recusadas.discard(chave)
