"""/fornecedores: o cadastro das revendas de quem se compra, e o que se pagou a cada uma."""

from typing import Any

from fastapi.testclient import TestClient

REVENDA = {
    "nome": "  Revenda Boa Safra ",
    "contato": "Seu Antônio",
    "telefone": "(69) 99999-0000",
    "cidade": "Ariquemes",
    "observacao": "Entrega na quinta.\nFrete grátis acima de 20 sacos.",
}


def cadastrar(client: TestClient, **campos: Any) -> dict[str, Any]:
    resposta = client.post("/api/v1/fornecedores", json=REVENDA | campos)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_cadastra_lista_e_detalha(client: TestClient) -> None:
    revenda = cadastrar(client)
    cadastrar(client, nome="Agropecuária Central", contato="", telefone=None, observacao=" ")

    assert revenda["nome"] == "Revenda Boa Safra"
    assert (revenda["ativo"], revenda["demonstracao"]) == (True, False)
    assert revenda["observacao"] == "Entrega na quinta.\nFrete grátis acima de 20 sacos."
    lista = client.get("/api/v1/fornecedores").json()
    assert [f["nome"] for f in lista] == ["Agropecuária Central", "Revenda Boa Safra"]
    # Campo apagado na tela chega como "": é fornecedor sem contato, não contato "".
    assert (lista[0]["contato"], lista[0]["telefone"], lista[0]["observacao"]) == (None,) * 3
    detalhe = client.get(f"/api/v1/fornecedores/{revenda['id']}").json()
    assert detalhe["telefone"] == "(69) 99999-0000"
    assert client.get("/api/v1/fornecedores/999").status_code == 404


def test_nome_repetido_e_409_e_dado_invalido_422(client: TestClient) -> None:
    cadastrar(client)

    repetido = client.post("/api/v1/fornecedores", json={"nome": "Revenda Boa Safra"})
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "Já existe um fornecedor com esse nome."
    for corpo in (
        {"nome": ""},
        {"nome": "Revenda\x00"},
        {"nome": "Ok", "telefone": "9" * 31},
        {"nome": "Ok", "cidade": "Porto\x07Velho"},
        {"nome": "Ok", "observacao": "nulo\x00aqui"},
    ):
        assert client.post("/api/v1/fornecedores", json=corpo).status_code == 422, corpo


def test_alterar_muda_so_o_que_veio(client: TestClient) -> None:
    revenda = cadastrar(client)
    outra = cadastrar(client, nome="Cooperativa Vale Verde")

    resposta = client.put(
        f"/api/v1/fornecedores/{revenda['id']}", json={"nome": "Revenda Boa Safra", "ativo": False}
    )

    assert resposta.status_code == 200
    # O telefone, que não veio, fica: a tela que só desativa não apaga o resto.
    assert (resposta.json()["ativo"], resposta.json()["telefone"]) == (False, "(69) 99999-0000")
    limpo = client.put(f"/api/v1/fornecedores/{revenda['id']}", json={"nome": "R", "telefone": ""})
    assert (limpo.json()["telefone"], limpo.json()["ativo"]) == (None, False)
    nome_de_outro = {"nome": "Cooperativa Vale Verde"}
    assert (
        client.put(f"/api/v1/fornecedores/{revenda['id']}", json=nome_de_outro).status_code == 409
    )
    assert client.put("/api/v1/fornecedores/999", json=nome_de_outro).status_code == 404
    assert client.get(f"/api/v1/fornecedores/{outra['id']}").json()["ativo"] is True


def test_remove_o_fornecedor_sem_historia(client: TestClient) -> None:
    revenda = cadastrar(client)

    assert client.delete(f"/api/v1/fornecedores/{revenda['id']}").status_code == 204
    assert client.get("/api/v1/fornecedores").json() == []
    assert client.delete(f"/api/v1/fornecedores/{revenda['id']}").status_code == 404
