"""O celular perdido, por HTTP, contra o uvicorn de verdade e o PostgreSQL, com o login
ligado: o funcionário entra no celular e no notebook; o dono encerra só o celular, que
cai na hora, e o notebook segue; o funcionário encerra as outras sessões dele; a sessão
de outro usuário é 404, a gestão dos aparelhos é do dono; tudo na trilha. E o último uso
gravado pelo papel da aplicação de tempos em tempos, e não a cada pedido (conferido pelo
`xmin` da linha, que muda a cada UPDATE), com a validade renovada até o teto."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import httpx
from sqlalchemy import Engine, text

from tests.integracao.test_fluxo_autenticacao import (
    SENHA_DO_DONO,
    SENHA_DO_ZE,
    criar_dono,
    entrar,
    ok,
)


def _linha_da_sessao(banco: Engine, sessao_id: int) -> dict:
    """A sessão como o PostgreSQL a guarda, com o `xmin`: a transação que gravou a versão
    atual da linha. Ele só muda se alguém fez UPDATE nela."""
    with banco.connect() as conexao:
        linha = conexao.execute(
            text(
                "SELECT xmin::text AS xmin, ultimo_uso_em, expira_em, criada_em, ip,"
                " revogada_em FROM sessoes WHERE id = :id"
            ),
            {"id": sessao_id},
        ).one()
    return dict(linha._mapping)


def test_o_celular_perdido_cai_e_o_notebook_segue(
    api_autenticada: httpx.Client, banco: Engine
) -> None:
    api = api_autenticada
    assert criar_dono("maria", "Dona Maria").returncode == 0
    dono = entrar(api, "maria", SENHA_DO_DONO, "Computador do escritório")
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

    # O Zé entra no celular e no notebook.
    celular = entrar(api, "ze", SENHA_DO_ZE, "Celular do Zé")
    notebook = entrar(api, "ze", SENHA_DO_ZE, "Notebook")
    minhas = api.get("/auth/sessoes", headers=notebook)
    lista = ok(minhas)
    assert sorted((s["dispositivo"], s["atual"]) for s in lista) == [
        ("Celular do Zé", False),
        ("Notebook", True),
    ]
    # O IP que o uvicorn viu, e nada do token.
    assert {s["ip"] for s in lista} == {"127.0.0.1"}
    assert "token" not in minhas.text
    for cabecalho in (celular, notebook):
        assert cabecalho["Authorization"].removeprefix("Bearer ") not in minhas.text

    # O celular "é perdido": o dono vê os aparelhos do Zé e encerra só o celular.
    aparelhos = {
        s["dispositivo"]: s for s in ok(api.get(f"/usuarios/{ze['id']}/sessoes", headers=dono))
    }
    assert set(aparelhos) == {"Celular do Zé", "Notebook"}
    id_do_celular = aparelhos["Celular do Zé"]["id"]
    assert (
        api.delete(f"/usuarios/{ze['id']}/sessoes/{id_do_celular}", headers=dono).status_code == 204
    )

    # O token do celular cai na hora; o do notebook continua, e o Zé continua ativo.
    caiu = api.get("/insumos", headers=celular)
    assert caiu.status_code == 401
    assert "encerrada" in caiu.json()["detail"]
    assert ok(api.get("/auth/eu", headers=notebook))["login"] == "ze"
    assert [s["dispositivo"] for s in ok(api.get("/auth/sessoes", headers=notebook))] == [
        "Notebook"
    ]
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT ativo FROM usuarios WHERE login = 'ze'")) is True

    # O funcionário não mexe na sessão de outro (404, como a que não existe) nem na gestão.
    da_maria = next(s["id"] for s in ok(api.get("/auth/sessoes", headers=dono)) if s["atual"])
    de_outro = api.delete(f"/auth/sessoes/{da_maria}", headers=notebook)
    inexistente = api.delete("/auth/sessoes/999999", headers=notebook)
    assert de_outro.status_code == inexistente.status_code == 404
    assert de_outro.json() == inexistente.json()
    assert api.get("/auth/eu", headers=dono).status_code == 200
    for pedido in (
        api.get(f"/usuarios/{ze['id']}/sessoes", headers=notebook),
        api.post(f"/usuarios/{ze['id']}/sessoes/encerrar", headers=notebook),
    ):
        assert pedido.status_code == 403

    # Do notebook, o Zé encerra "as outras" (o tablet que ficou na cooperativa).
    tablet = entrar(api, "ze", SENHA_DO_ZE, "Tablet da cooperativa")
    assert ok(api.post("/auth/sessoes/encerrar-outras", headers=notebook)) == {"encerradas": 1}
    assert api.get("/auth/eu", headers=tablet).status_code == 401
    assert api.get("/auth/eu", headers=notebook).status_code == 200

    # Na trilha: o dono encerrando o celular e o Zé encerrando o tablet, com quem, de qual
    # aparelho e o que foi encerrado. Nenhum hash de token nos dados.
    trilha = ok(api.get("/auditoria", headers=dono, params={"acao": "sessao"}))
    assert [(e["acao"], e["feito_por"], e["dispositivo"], e["ip"]) for e in trilha] == [
        ("sessao.encerradas", "Zé do Trator", "Notebook", "127.0.0.1"),
        ("sessao.encerrada", "Dona Maria", "Computador do escritório", "127.0.0.1"),
    ]
    assert {(e["entidade"], e["entidade_id"]) for e in trilha} == {("usuario", ze["id"])}
    assert trilha[1]["dados"]["sessao"]["dispositivo"] == "Celular do Zé"
    assert [s["dispositivo"] for s in trilha[0]["dados"]["sessoes"]] == ["Tablet da cooperativa"]
    with banco.connect() as conexao:
        hashes = conexao.scalars(text("SELECT token_hash FROM sessoes")).all()
        gravado = conexao.scalar(
            text("SELECT string_agg(dados::text, ' ') FROM eventos_de_auditoria")
        )
    assert not any(h in gravado for h in hashes)
    assert "token" not in gravado


def test_ultimo_uso_gravado_de_tempos_em_tempos_e_validade_ate_o_teto(
    api_autenticada: httpx.Client, banco: Engine
) -> None:
    api = api_autenticada
    assert criar_dono("maria", "Dona Maria").returncode == 0
    notebook = entrar(api, "maria", SENHA_DO_DONO, "Notebook")
    [sessao] = ok(api.get("/auth/sessoes", headers=notebook))
    antes = _linha_da_sessao(banco, sessao["id"])
    assert antes["ip"] == "127.0.0.1"

    # Pedidos seguidos, dentro dos 5 minutos: a linha não é regravada (o mesmo xmin).
    for _ in range(10):
        assert api.get("/insumos", headers=notebook).status_code == 200
    depois = _linha_da_sessao(banco, sessao["id"])
    assert (depois["xmin"], depois["ultimo_uso_em"]) == (antes["xmin"], antes["ultimo_uso_em"])

    # Último uso há 10 minutos: o próximo pedido o anota, pelo papel da aplicação, e renova
    # a validade, 30 dias a partir de agora. Oito pedidos ao mesmo tempo, como o Painel ao
    # abrir: nenhum espera a trava até o lock_timeout (nenhum 503).
    with banco.begin() as conexao:
        conexao.execute(
            text("UPDATE sessoes SET ultimo_uso_em = now() - interval '10 minutes' WHERE id = :id"),
            {"id": sessao["id"]},
        )
    velho = _linha_da_sessao(banco, sessao["id"])
    with ThreadPoolExecutor(max_workers=8) as threads:
        respostas = list(
            threads.map(lambda _: api.get("/insumos", headers=notebook).status_code, range(8))
        )
    assert respostas == [200] * 8
    anotado = _linha_da_sessao(banco, sessao["id"])
    assert anotado["xmin"] != velho["xmin"]
    assert anotado["ultimo_uso_em"] - velho["ultimo_uso_em"] >= timedelta(minutes=9)
    assert abs(anotado["expira_em"] - (anotado["ultimo_uso_em"] + timedelta(days=30))) < timedelta(
        seconds=1
    )
    # E de novo, logo em seguida, nada é regravado.
    for _ in range(5):
        assert api.get("/auth/eu", headers=notebook).status_code == 200
    assert _linha_da_sessao(banco, sessao["id"])["xmin"] == anotado["xmin"]

    # Perto do teto (login há 89 dias), o uso renova só até os 90 dias desde o login.
    with banco.begin() as conexao:
        conexao.execute(
            text(
                "UPDATE sessoes SET criada_em = now() - interval '89 days',"
                " ultimo_uso_em = now() - interval '1 hour', expira_em = now() + interval '1 day'"
                " WHERE id = :id"
            ),
            {"id": sessao["id"]},
        )
    assert api.get("/auth/eu", headers=notebook).status_code == 200
    teto = _linha_da_sessao(banco, sessao["id"])
    assert teto["expira_em"] == teto["criada_em"] + timedelta(days=90)
    listada = ok(api.get("/auth/sessoes", headers=notebook))[0]
    assert datetime.fromisoformat(listada["expira_em"]) == teto["expira_em"]

    # Passado o teto, a sessão vencida não abre mais nada.
    with banco.begin() as conexao:
        conexao.execute(
            text(
                "UPDATE sessoes SET criada_em = now() - interval '91 days',"
                " expira_em = now() - interval '1 day' WHERE id = :id"
            ),
            {"id": sessao["id"]},
        )
    vencida = api.get("/auth/eu", headers=notebook)
    assert vencida.status_code == 401
    assert "expirou" in vencida.json()["detail"]
