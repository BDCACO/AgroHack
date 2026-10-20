"""Importação de movimentações a partir de uma planilha CSV.

Para o produtor que já anota compras e retiradas no Excel não relançar tudo pela tela.
Tudo ou nada: com um erro sequer, nada entra. Meia planilha importada é pior que
nenhuma, porque o estoque fica errado sem que ninguém perceba.
"""

import _csv
import csv
import io
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


@dataclass
class TotalDoInsumo:
    nome: str
    unidade: str
    novo: bool
    entradas: float = 0.0
    saidas: float = 0.0


@dataclass
class ResultadoImportacao:
    linhas: int = 0
    entradas: int = 0
    saidas: int = 0
    # Quanto entra e sai de cada insumo, na ordem da planilha: é onde um erro de
    # escala (mil lido como um) salta aos olhos antes de gravar.
    insumos: list[TotalDoInsumo] = field(default_factory=list)
    primeira_data: date | None = None
    ultima_data: date | None = None
    # Linhas idênticas a movimentações que já estão no banco: sinal de planilha
    # importada duas vezes. Só aviso — duas retiradas iguais no mesmo dia existem.
    ja_lancadas: int = 0
    erros: list[str] = field(default_factory=list)
    importado: bool = False


@dataclass(frozen=True)
class _Linha:
    insumo: Insumo  # o cadastrado, ou um novo que só entra na sessão ao confirmar
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

    lidas = _ler_celulas(leitor, len(cabecalho), resultado.erros)
    if lidas is None:
        return resultado
    try:
        decimal = _separador_decimal(lidas, cabecalho, delimitador)
    except ValueError as erro:
        resultado.erros.append(str(erro))
        return resultado

    cadastrados: dict[str, list[Insumo]] = {}
    for insumo in db.scalars(select(Insumo).order_by(Insumo.nome)):
        cadastrados.setdefault(insumo.nome.casefold(), []).append(insumo)
    novos: dict[str, Insumo] = {}
    linhas: list[_Linha] = []
    for numero, celulas in lidas:
        campos = dict(zip(cabecalho, celulas, strict=False))
        try:
            linhas.append(_ler(campos, decimal, cadastrados, novos))
        except ValueError as erro:
            resultado.erros.append(f"Linha {numero}: {erro}")

    if not linhas and not resultado.erros:
        resultado.erros.append("Nenhuma movimentação na planilha.")
    _resumir(resultado, linhas)
    resultado.ja_lancadas = _ja_lancadas(db, linhas)
    if resultado.erros or not confirmar:
        return resultado

    for linha in linhas:
        movimentacao = Movimentacao(
            tipo=linha.tipo, data=linha.data, quantidade=linha.quantidade, validade=linha.validade
        )
        if linha.insumo.id is None:
            linha.insumo.movimentacoes.append(movimentacao)
        else:
            movimentacao.insumo_id = linha.insumo.id
            db.add(movimentacao)
    db.add_all(novos.values())
    db.commit()
    resultado.importado = True
    return resultado


def _ler_celulas(
    leitor: _csv.Reader, colunas: int, erros: list[str]
) -> list[tuple[int, list[str]]] | None:
    """As linhas com conteúdo, com o número da linha onde cada uma começa no arquivo.
    None se o arquivo nem pôde ser lido."""
    lidas = []
    inicio = 2  # a linha 1 é o cabeçalho
    try:
        for celulas in leitor:
            numero, inicio = inicio, leitor.line_num + 1
            if not any(celula.strip() for celula in celulas):
                continue
            if any("\n" in celula or "\r" in celula for celula in celulas):
                # Uma aspa aberta faz o csv juntar o que vem depois numa célula só.
                erros.append(
                    f'Linha {numero}: aspa (") sem fechar; o resto do arquivo virou uma célula só.'
                )
            elif any("\x00" in celula for celula in celulas):
                erros.append(
                    f"Linha {numero}: caractere inválido; salve a planilha de novo como CSV."
                )
            elif any(celula.strip() for celula in celulas[colunas:]):
                # Excel deixa ";;" no fim das linhas: célula vazia a mais não é erro.
                erros.append(
                    f"Linha {numero}: {len(celulas)} colunas, mas o cabeçalho tem {colunas}. "
                    "Se a quantidade tem vírgula decimal, separe as colunas por ponto e vírgula "
                    "ou ponha o número entre aspas."
                )
            else:
                lidas.append((numero, [celula.strip() for celula in celulas]))
    except csv.Error as erro:
        erros.append(
            f'Linha {inicio}: não deu para ler o arquivo ({erro}). Há uma aspa (") sem fechar?'
        )
        return None
    return lidas


def _separador_decimal(
    lidas: list[tuple[int, list[str]]], cabecalho: list[str], delimitador: str
) -> str:
    """Vírgula ou ponto, decidido pela planilha inteira: sozinha, a célula "25.500" não diz
    se é vinte e cinco e meio ou vinte e cinco mil."""
    coluna = cabecalho.index("quantidade")
    pistas: dict[str, tuple[int, str]] = {}
    for numero, celulas in lidas:
        texto = celulas[coluna].replace(" ", "") if coluna < len(celulas) else ""
        if (separador := _pista(texto)) is not None:
            pistas.setdefault(separador, (numero, texto))
    if len(pistas) > 1:
        (linha_v, virgula), (linha_p, ponto) = pistas[","], pistas["."]
        raise ValueError(
            f"Quantidades com vírgula decimal (linha {linha_v}: {virgula}) e com ponto decimal "
            f"(linha {linha_p}: {ponto}) na mesma planilha: use um formato só."
        )
    if pistas:
        return next(iter(pistas))
    # Nenhuma célula decide: vale o costume de cada tipo de arquivo. O Excel em português
    # separa as colunas por ponto e vírgula e os decimais por vírgula.
    return "," if delimitador == ";" else "."


def _pista(texto: str) -> str | None:
    """O separador decimal que a célula revela, se revela algum."""
    virgulas, pontos = texto.count(","), texto.count(".")
    if virgulas and pontos:  # 1.234,5 ou 1,234.5: o último é o decimal
        return "," if texto.rfind(",") > texto.rfind(".") else "."
    if virgulas + pontos > 1:  # 1.234.567: o repetido é o de milhar; o decimal é o outro
        return "," if pontos else "."
    if not virgulas + pontos:
        return None
    separador = "," if virgulas else "."
    inteiro, decimais = texto.split(separador)
    # "25.500" ou "1,000": três casas depois de um número que não é zero tanto podem ser
    # milhar quanto decimal. "0.250" e "2.5" não deixam dúvida.
    if len(decimais) == 3 and inteiro.lstrip("+-") not in ("", "0"):
        return None
    return separador


def _ler(
    campos: dict[str, str],
    decimal: str,
    cadastrados: dict[str, list[Insumo]],
    novos: dict[str, Insumo],
) -> _Linha:
    nome = campos.get("insumo", "")
    if not nome:
        raise ValueError("falta o nome do insumo.")
    if len(nome) > 120:
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
    milhar = "." if decimal == "," else ","
    try:
        quantidade = round(
            float(texto.replace(" ", "").replace(milhar, "").replace(decimal, ".")), 3
        )
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
    insumo = _insumo(nome, unidade, cadastrados, novos)
    return _Linha(insumo, tipo, data, quantidade, validade)


def _insumo(
    nome: str, unidade: str, cadastrados: dict[str, list[Insumo]], novos: dict[str, Insumo]
) -> Insumo:
    """Casa o nome da planilha com o cadastro, sem diferenciar maiúsculas. Insumo novo
    entra com a grafia e a unidade da primeira linha em que aparece."""
    chave = nome.casefold()
    match cadastrados.get(chave, []):
        case [insumo]:
            pass
        case []:
            if chave not in novos:
                if not unidade:
                    raise ValueError(
                        f'"{nome}" não está cadastrado; informe a unidade para cadastrá-lo.'
                    )
                novos[chave] = Insumo(nome=nome, unidade=unidade)
            insumo = novos[chave]
        case varios:
            # O cadastro diferencia maiúsculas; a planilha, não. Escolher um seria chute.
            raise ValueError(
                f'há mais de um insumo cadastrado como "{nome}" '
                f"({', '.join(i.nome for i in varios)}); renomeie um deles na tela de Insumos."
            )
    if unidade and unidade.casefold() != insumo.unidade.casefold():
        # Somar kg com saca daria um estoque sem sentido.
        raise ValueError(f'"{nome}" já está cadastrado em {insumo.unidade}, não em {unidade}.')
    return insumo


def _data(texto: str, coluna: str) -> date:
    for formato in FORMATOS_DE_DATA:
        try:
            return datetime.strptime(texto, formato).date()  # noqa: DTZ007 — só a data
        except ValueError:
            continue
    raise ValueError(f'{coluna} "{texto}" inválida; use DD/MM/AAAA.')


def _resumir(resultado: ResultadoImportacao, linhas: list[_Linha]) -> None:
    totais: dict[int, TotalDoInsumo] = {}
    for linha in linhas:
        insumo = linha.insumo
        total = totais.setdefault(
            id(insumo), TotalDoInsumo(insumo.nome, insumo.unidade, novo=insumo.id is None)
        )
        if linha.tipo == "entrada":
            total.entradas = round(total.entradas + linha.quantidade, 3)
        else:
            total.saidas = round(total.saidas + linha.quantidade, 3)
    resultado.insumos = list(totais.values())
    resultado.linhas = len(linhas)
    resultado.entradas = sum(linha.tipo == "entrada" for linha in linhas)
    resultado.saidas = resultado.linhas - resultado.entradas
    if linhas:
        resultado.primeira_data = min(linha.data for linha in linhas)
        resultado.ultima_data = max(linha.data for linha in linhas)


def _ja_lancadas(db: Session, linhas: list[_Linha]) -> int:
    ids = {linha.insumo.id for linha in linhas if linha.insumo.id is not None}
    if not ids:
        return 0
    no_banco = Counter(
        (m.insumo_id, m.tipo, m.data, m.quantidade, m.validade)
        for m in db.scalars(select(Movimentacao).where(Movimentacao.insumo_id.in_(ids)))
    )
    repetidas = 0
    for linha in linhas:
        chave = (linha.insumo.id, linha.tipo, linha.data, linha.quantidade, linha.validade)
        if no_banco[chave] > 0:
            no_banco[chave] -= 1
            repetidas += 1
    return repetidas
