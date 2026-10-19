"""Importação de movimentações a partir de uma planilha CSV.

Para o produtor que já anota compras e retiradas no Excel não relançar tudo pela tela.
Tudo ou nada: com um erro sequer, nada entra. Meia planilha importada é pior que
nenhuma, porque o estoque fica errado sem que ninguém perceba.
"""

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.models import Insumo, Movimentacao
from app.schemas.estoque import QUANTIDADE_MAXIMA

COLUNAS_OBRIGATORIAS = ("data", "insumo", "tipo", "quantidade")
TIPOS = {
    "entrada": "entrada",
    "compra": "entrada",
    "saida": "saida",
    "saída": "saida",
    "retirada": "saida",
}
# O Excel em português grava DD/MM/AAAA (ou DD/MM/AA, se a célula estiver assim).
FORMATOS_DE_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y")
# "1.000" na planilha de uma fazenda brasileira é mil, não um.
_MILHAR = re.compile(r"\d{1,3}(\.\d{3})+")


@dataclass
class ResultadoImportacao:
    linhas: int = 0
    entradas: int = 0
    saidas: int = 0
    insumos_novos: list[str] = field(default_factory=list)
    primeira_data: date | None = None
    ultima_data: date | None = None
    # Linhas idênticas a movimentações que já estão no banco: sinal de planilha
    # importada duas vezes. Só aviso — duas retiradas iguais no mesmo dia existem.
    ja_lancadas: int = 0
    erros: list[str] = field(default_factory=list)
    importado: bool = False


@dataclass(frozen=True)
class _Linha:
    insumo: str
    unidade: str
    tipo: str
    data: date
    quantidade: float
    validade: date | None


def importar(db: Session, conteudo: str, *, confirmar: bool) -> ResultadoImportacao:
    """Confere a planilha e devolve o resumo. Com `confirmar` e sem erros, grava."""
    resultado = ResultadoImportacao()
    conteudo = conteudo.lstrip("\ufeff")
    if not conteudo.strip():
        resultado.erros.append("O arquivo está vazio.")
        return resultado

    # O Excel em português separa por ponto e vírgula; o resto do mundo, por vírgula.
    delimitador = ";" if ";" in conteudo.split("\n", 1)[0] else ","
    leitor = csv.reader(io.StringIO(conteudo, newline=""), delimiter=delimitador)
    cabecalho = [coluna.strip().lower() for coluna in next(leitor)]
    if faltando := [c for c in COLUNAS_OBRIGATORIAS if c not in cabecalho]:
        resultado.erros.append(f"Faltam as colunas: {', '.join(faltando)}.")
        return resultado

    existentes = {insumo.nome.casefold(): insumo for insumo in db.scalars(select(Insumo))}
    novos: dict[str, Insumo] = {}
    linhas: list[_Linha] = []
    for celulas in leitor:
        if not any(celula.strip() for celula in celulas):
            continue
        campos = dict(zip(cabecalho, (celula.strip() for celula in celulas), strict=False))
        try:
            linha = _ler(campos)
            _conferir_insumo(linha, existentes, novos)
        except ValueError as erro:
            resultado.erros.append(f"Linha {leitor.line_num}: {erro}")
            continue
        linhas.append(linha)

    if not linhas and not resultado.erros:
        resultado.erros.append("Nenhuma movimentação na planilha.")
    resultado.linhas = len(linhas)
    resultado.entradas = sum(linha.tipo == "entrada" for linha in linhas)
    resultado.saidas = resultado.linhas - resultado.entradas
    resultado.insumos_novos = [insumo.nome for insumo in novos.values()]
    if linhas:
        resultado.primeira_data = min(linha.data for linha in linhas)
        resultado.ultima_data = max(linha.data for linha in linhas)
    resultado.ja_lancadas = _ja_lancadas(db, linhas, existentes)
    if resultado.erros or not confirmar:
        return resultado

    for linha in linhas:
        chave = linha.insumo.casefold()
        movimentacao = Movimentacao(
            tipo=linha.tipo, data=linha.data, quantidade=linha.quantidade, validade=linha.validade
        )
        if chave in novos:
            novos[chave].movimentacoes.append(movimentacao)
        else:
            movimentacao.insumo_id = existentes[chave].id
            db.add(movimentacao)
    db.add_all(novos.values())
    db.commit()
    resultado.importado = True
    return resultado


def _ler(campos: dict[str, str]) -> _Linha:
    insumo = campos.get("insumo", "")
    if not insumo:
        raise ValueError("falta o nome do insumo.")
    if len(insumo) > 120:
        raise ValueError("nome do insumo com mais de 120 caracteres.")
    unidade = campos.get("unidade", "")
    if len(unidade) > 20:
        raise ValueError("unidade com mais de 20 caracteres.")

    tipo = TIPOS.get(campos.get("tipo", "").casefold())
    if tipo is None:
        raise ValueError(f'tipo "{campos.get("tipo", "")}" desconhecido; use entrada ou saída.')

    data = _data(campos.get("data", ""), "data")
    if data > hoje():
        raise ValueError("data no futuro.")

    texto = campos.get("quantidade", "")
    try:
        quantidade = round(_numero(texto), 3)
    except ValueError:
        raise ValueError(f'quantidade "{texto}" não é um número.') from None
    # `not >` em vez de `<=`: pega também o NaN, que float("nan") aceita.
    if not quantidade > 0:
        raise ValueError("quantidade deve ser maior que zero.")
    if quantidade > QUANTIDADE_MAXIMA:
        raise ValueError("quantidade grande demais.")

    validade = None
    if texto_validade := campos.get("validade", ""):
        if tipo != "entrada":
            raise ValueError("validade só se informa numa entrada.")
        validade = _data(texto_validade, "validade")
    return _Linha(insumo, unidade, tipo, data, quantidade, validade)


def _conferir_insumo(
    linha: _Linha, existentes: dict[str, Insumo], novos: dict[str, Insumo]
) -> None:
    """Casa o nome da planilha com o cadastro, sem diferenciar maiúsculas. Insumo novo
    entra com a grafia e a unidade da primeira linha em que aparece."""
    chave = linha.insumo.casefold()
    cadastrado = existentes.get(chave) or novos.get(chave)
    if cadastrado is None:
        if not linha.unidade:
            raise ValueError(
                f'"{linha.insumo}" não está cadastrado; informe a unidade para cadastrá-lo.'
            )
        novos[chave] = Insumo(nome=linha.insumo, unidade=linha.unidade)
    elif linha.unidade and linha.unidade.casefold() != cadastrado.unidade.casefold():
        # Somar kg com saca daria um estoque sem sentido.
        raise ValueError(
            f'"{linha.insumo}" já está cadastrado em {cadastrado.unidade}, não em {linha.unidade}.'
        )


def _data(texto: str, coluna: str) -> date:
    for formato in FORMATOS_DE_DATA:
        try:
            return datetime.strptime(texto, formato).date()  # noqa: DTZ007 — só a data
        except ValueError:
            continue
    raise ValueError(f'{coluna} "{texto}" inválida; use DD/MM/AAAA.')


def _numero(texto: str) -> float:
    """1.234,5 → 1234.5 · 25,5 → 25.5 · 1.000 → 1000 · 2.5 → 2.5"""
    texto = texto.replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif _MILHAR.fullmatch(texto):
        texto = texto.replace(".", "")
    return float(texto)


def _ja_lancadas(db: Session, linhas: list[_Linha], existentes: dict[str, Insumo]) -> int:
    ids = {i.id for linha in linhas if (i := existentes.get(linha.insumo.casefold()))}
    if not ids:
        return 0
    no_banco = Counter(
        (m.insumo_id, m.tipo, m.data, m.quantidade, m.validade)
        for m in db.scalars(select(Movimentacao).where(Movimentacao.insumo_id.in_(ids)))
    )
    repetidas = 0
    for linha in linhas:
        if (insumo := existentes.get(linha.insumo.casefold())) is None:
            continue
        chave = (insumo.id, linha.tipo, linha.data, linha.quantidade, linha.validade)
        if no_banco[chave] > 0:
            no_banco[chave] -= 1
            repetidas += 1
    return repetidas
