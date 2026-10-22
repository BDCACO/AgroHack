"""A data de "hoje" é a de Rondônia, não a do servidor: um container em UTC viraria
o dia às 20h locais, e uma retirada lançada à noite cairia no dia seguinte."""

from datetime import UTC, date, datetime, timedelta, timezone

# Fuso fixo, sem tzdata: Rondônia não tem horário de verão (o Brasil o aboliu em 2019).
FUSO_RONDONIA = timezone(timedelta(hours=-4), "America/Porto_Velho")


def hoje() -> date:
    return datetime.now(FUSO_RONDONIA).date()


def agora() -> datetime:
    """O instante, em UTC: sessões e bloqueio de login comparam instantes, não dias."""
    return datetime.now(UTC)
