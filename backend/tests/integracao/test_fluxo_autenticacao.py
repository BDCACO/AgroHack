"""Fluxo real de uso, por HTTP, com o login ligado: o dono criado pelo comando no servidor
cadastra o funcionário; o funcionário lança no campo (pelo POST e pela fila do app) e não
consegue o que é do dono; sair, trocar a senha e ser desativado derrubam a sessão na hora;
senhas erradas seguidas bloqueiam o login. E a API de produção que não sobe sem login."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import Engine, text

from app.core.relogio import hoje
from tests.integracao.conftest import BACKEND, URL_DO_BANCO, subir_uvicorn

HOJE = str(hoje())
SENHA_DO_DONO = "dona-maria-2026"
SENHA_DO_ZE = "ze-do-trator-1"


def ok(resposta: httpx.Response, status: int = 200) -> Any:
    assert resposta.status_code == status, resposta.text
    return resposta.json() if resposta.content else None


def criar_dono(login: str, nome: str, *extras: str) -> subprocess.CompletedProcess[str]:
    """O comando de verdade, como no servidor, com a senha pela variável de ambiente."""
    ambiente = os.environ | {
        "ENVIRONMENT": "test",
        "DATABASE_URL": URL_DO_BANCO,
        "SENHA_DO_DONO": SENHA_DO_DONO,
    }
    comando = ["criar-dono", "--login", login, "--nome", nome, *extras]
    return subprocess.run(  # noqa: S603 — comando fixo, sem entrada de usuário
        [sys.executable, "-m", "app.usuarios", *comando],
        cwd=BACKEND,
        env=ambiente,
        capture_output=True,
        text=True,
        check=False,
    )


def entrar(api: httpx.Client, login: str, senha: str, dispositivo: str | None = None) -> dict:
    corpo = ok(
        api.post("/auth/entrar", json={"login": login, "senha": senha, "dispositivo": dispositivo})
    )
    return {"Authorization": f"Bearer {corpo['token']}"}


def test_dono_e_funcionario_do_comando_ao_campo(
    api_autenticada: httpx.Client, banco: Engine
) -> None:
    api = api_autenticada
    criado = criar_dono("Maria", "Dona Maria")
    assert criado.returncode == 0, criado.stderr
    assert "Dono criado: Dona Maria (login maria)" in criado.stdout
    assert SENHA_DO_DONO not in criado.stdout + criado.stderr
    # O segundo dono pelo comando só com --outro-dono: o caminho normal é o dono cadastrar.
    recusado = criar_dono("joao", "João")
    assert recusado.returncode != 0
    assert "--outro-dono" in recusado.stderr

    # Sem login, nada além do público.
    assert ok(api.get("/health")) == {"status": "ok"}
    for cabecalho in [{}, {"Authorization": "Bearer token-inventado"}]:
        resposta = api.get("/insumos", headers=cabecalho)
        assert resposta.status_code == 401
        assert resposta.headers["www-authenticate"] == "Bearer"

    dono = entrar(api, "MARIA", SENHA_DO_DONO, "Computador do escritório")
    ureia = ok(api.post("/insumos", headers=dono, json={"nome": "Ureia", "unidade": "kg"}), 201)
    compra = {"insumo_id": ureia["id"], "tipo": "entrada", "data": HOJE, "quantidade": 500}
    ok(api.post("/movimentacoes", headers=dono, json=compra | {"valor_unitario": 3.2}), 201)
    ze = ok(
        api.post(
            "/usuarios",
            headers=dono,
            json={
                "nome": "Zé do Trator",
                "login": "ze",
                "senha": SENHA_DO_ZE,
                "papel": "funcionario",
            },
        ),
        201,
    )

    # O funcionário no campo: lança pelo POST e pela fila do app, e o autor fica gravado.
    celular = entrar(api, "ze", SENHA_DO_ZE, "Celular do Zé")
    assert ok(api.get("/auth/eu", headers=celular))["papel"] == "funcionario"
    saida = {"insumo_id": ureia["id"], "tipo": "saida", "data": HOJE, "quantidade": 20}
    lancada = ok(api.post("/movimentacoes", headers=celular, json=saida), 201)
    assert (lancada["usuario_id"], lancada["lancado_por"]) == (ze["id"], "Zé do Trator")
    fila = [saida | {"uuid": str(uuid4()), "quantidade": q} for q in (5, 7)]
    lote = ok(api.post("/movimentacoes/lote", headers=celular, json={"movimentacoes": fila}))
    assert lote["resumo"] == {"gravadas": 2, "ja_existiam": 0, "recusadas": 0}
    assert {r["movimentacao"]["lancado_por"] for r in lote["resultados"]} == {"Zé do Trator"}
    with banco.connect() as conexao:
        autores = conexao.execute(
            text(
                "SELECT u.login, count(*) FROM movimentacoes m JOIN usuarios u"
                " ON u.id = m.usuario_id GROUP BY u.login ORDER BY u.login"
            )
        ).all()
    assert [tuple(a) for a in autores] == [("maria", 1), ("ze", 3)]
    assert ok(api.get("/insumos", headers=celular))[0]["estoque_atual"] == 468

    # O que é do dono, o funcionário não faz.
    proibidos = [
        api.delete(f"/movimentacoes/{lancada['id']}", headers=celular),
        api.post("/importacoes", headers=celular, json={"conteudo": "data;insumo\n"}),
        api.get("/relatorio.xlsx", headers=celular),
        api.post("/insumos", headers=celular, json={"nome": "Calcário", "unidade": "t"}),
        api.get("/usuarios", headers=celular),
        api.put(f"/usuarios/{ze['id']}", headers=celular, json={"papel": "dono"}),
    ]
    assert [r.status_code for r in proibidos] == [403] * len(proibidos)
    assert proibidos[0].json()["detail"] == "Só o dono da fazenda pode fazer isto: peça a ele."
    assert len(ok(api.get("/movimentacoes", headers=dono))) == 4  # nada foi apagado

    # Sair encerra só aquela sessão.
    computador = entrar(api, "ze", SENHA_DO_ZE, "Computador do galpão")
    assert api.post("/auth/sair", headers=computador).status_code == 204
    assert api.get("/auth/eu", headers=computador).status_code == 401
    assert api.get("/auth/eu", headers=celular).status_code == 200

    # Trocar a senha derruba as outras sessões; a de quem trocou continua.
    tablet = entrar(api, "ze", SENHA_DO_ZE, "Tablet")
    troca = {"senha_atual": SENHA_DO_ZE, "senha_nova": "nova-senha-do-ze"}
    assert api.put("/auth/senha", headers=celular, json=troca).status_code == 204
    assert api.get("/auth/eu", headers=tablet).status_code == 401
    assert api.get("/auth/eu", headers=celular).status_code == 200

    # A sessão vencida (validade gravada no PostgreSQL, com fuso) não vale mais.
    outra_do_dono = entrar(api, "maria", SENHA_DO_DONO)
    with banco.begin() as conexao:
        conexao.execute(
            text(
                "UPDATE sessoes SET criada_em = now() - interval '31 days',"
                " expira_em = now() - interval '1 day'"
                " WHERE id = (SELECT max(id) FROM sessoes)"
            )
        )
    vencida = api.get("/auth/eu", headers=outra_do_dono)
    assert vencida.status_code == 401
    assert "expirou" in vencida.json()["detail"]

    # O dono desativa o funcionário: o celular dele perde o acesso na hora.
    ok(api.put(f"/usuarios/{ze['id']}", headers=dono, json={"ativo": False}))
    assert api.get("/insumos", headers=celular).status_code == 401
    assert (
        api.post("/auth/entrar", json={"login": "ze", "senha": "nova-senha-do-ze"}).status_code
        == 401
    )

    # O último dono ativo não se desativa nem vira funcionário.
    eu = ok(api.get("/auth/eu", headers=dono))
    for mudanca in [{"ativo": False}, {"papel": "funcionario"}]:
        assert api.put(f"/usuarios/{eu['id']}", headers=dono, json=mudanca).status_code == 409
    assert ok(api.get("/auth/eu", headers=dono))["papel"] == "dono"


def test_senhas_erradas_seguidas_bloqueiam_o_login(
    api_autenticada: httpx.Client, banco: Engine
) -> None:
    api = api_autenticada
    assert criar_dono("maria", "Dona Maria").returncode == 0
    dono = entrar(api, "maria", SENHA_DO_DONO)
    ze = ok(
        api.post(
            "/usuarios",
            headers=dono,
            json={"nome": "Zé", "login": "ze", "senha": SENHA_DO_ZE, "papel": "funcionario"},
        ),
        201,
    )

    def tentar(senha: str) -> httpx.Response:
        return api.post("/auth/entrar", json={"login": "ze", "senha": senha})

    erradas = [tentar(f"chute-{i}") for i in range(5)]
    sexta = tentar(SENHA_DO_ZE)

    assert [r.status_code for r in erradas] == [401] * 5
    assert sexta.status_code == 401
    # A mesma resposta de um login que nem existe.
    assert (
        sexta.json()
        == tentar("ninguem-sabe").json()
        == api.post("/auth/entrar", json={"login": "ninguem", "senha": SENHA_DO_ZE}).json()
    )
    with banco.connect() as conexao:
        bloqueio = conexao.scalar(
            text("SELECT bloqueado_ate - now() FROM usuarios WHERE login = 'ze'")
        )
    assert 14 * 60 < bloqueio.total_seconds() <= 15 * 60

    # O dono redefine a senha: desbloqueia.
    nova = {"senha_nova": "senha-nova-do-ze"}
    assert api.put(f"/usuarios/{ze['id']}/senha", headers=dono, json=nova).status_code == 204
    assert tentar("senha-nova-do-ze").status_code == 200


def test_chutes_simultaneos_nao_passam_do_limite(
    api_autenticada: httpx.Client, banco: Engine, servidor_autenticado: str
) -> None:
    # Dez senhas ao mesmo tempo, em threads contra o uvicorn: sem a trava na linha do
    # usuário, todas leriam "0 erros" antes de alguma gravar, e o bloqueio não viria.
    assert criar_dono("maria", "Dona Maria").returncode == 0

    def chutar(i: int) -> int:
        with httpx.Client(base_url=servidor_autenticado, timeout=60) as cliente:
            resposta = cliente.post("/auth/entrar", json={"login": "maria", "senha": f"chute-{i}"})
            return resposta.status_code

    with ThreadPoolExecutor(max_workers=10) as threads:
        assert list(threads.map(chutar, range(10))) == [401] * 10

    with banco.connect() as conexao:
        falhas, bloqueado = conexao.execute(
            text("SELECT falhas_seguidas, bloqueado_ate IS NOT NULL FROM usuarios")
        ).one()
    assert (falhas, bloqueado) == (0, True)
    resposta = api_autenticada.post("/auth/entrar", json={"login": "maria", "senha": SENHA_DO_DONO})
    assert resposta.status_code == 401


def test_producao_sem_autenticacao_nao_sobe(banco: Engine) -> None:
    ambiente = os.environ | {
        "ENVIRONMENT": "production",
        "DATABASE_URL": URL_DO_BANCO,
    }
    ambiente.pop("AUTENTICACAO", None)

    for variaveis in [{}, {"AUTENTICACAO": "false"}]:
        processo = subprocess.run(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "0"],
            cwd=BACKEND,
            env=ambiente | variaveis,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert processo.returncode != 0
        assert "AUTENTICACAO=true" in processo.stderr


def test_producao_com_autenticacao_sobe_sem_docs(banco: Engine) -> None:
    for base in subir_uvicorn(ENVIRONMENT="production", AUTENTICACAO="true"):
        assert httpx.get(f"{base}/ready").json() == {"status": "pronto", "database": "ok"}
        assert httpx.get(f"{base}/docs").status_code == 404
        assert httpx.get(f"{base}/insumos").status_code == 401
