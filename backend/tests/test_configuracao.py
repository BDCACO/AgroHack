"""/configuracao: o calendário de safra da fazenda inteira, usado pelo motor de análise."""

from fastapi.testclient import TestClient


def test_sem_configurar_vem_vazio(client: TestClient) -> None:
    resposta = client.get("/api/v1/configuracao")

    assert resposta.status_code == 200
    assert resposta.json() == {"meses_de_safra": []}


def test_define_e_le_de_volta(client: TestClient) -> None:
    definido = client.put("/api/v1/configuracao", json={"meses_de_safra": [9, 10, 11, 12, 1, 2, 3]})

    assert definido.status_code == 200
    assert definido.json()["meses_de_safra"] == [1, 2, 3, 9, 10, 11, 12]
    lido = client.get("/api/v1/configuracao")
    assert lido.json()["meses_de_safra"] == [1, 2, 3, 9, 10, 11, 12]


def test_redefinir_substitui_a_anterior_sem_duplicar_linha(client: TestClient) -> None:
    client.put("/api/v1/configuracao", json={"meses_de_safra": [9, 10, 11]})

    redefinido = client.put("/api/v1/configuracao", json={"meses_de_safra": [6, 7]})

    assert redefinido.json()["meses_de_safra"] == [6, 7]
    assert client.get("/api/v1/configuracao").json()["meses_de_safra"] == [6, 7]


def test_mes_fora_do_intervalo_e_422(client: TestClient) -> None:
    resposta = client.put("/api/v1/configuracao", json={"meses_de_safra": [0, 13]})

    assert resposta.status_code == 422


def test_esvaziar_desliga_a_sazonalidade(client: TestClient) -> None:
    client.put("/api/v1/configuracao", json={"meses_de_safra": [9, 10, 11]})

    client.put("/api/v1/configuracao", json={"meses_de_safra": []})

    assert client.get("/api/v1/configuracao").json()["meses_de_safra"] == []
