from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_db


def test_health_responde_ok(client: TestClient) -> None:
    resposta = client.get("/api/v1/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_ready_com_banco_acessivel(client: TestClient) -> None:
    resposta = client.get("/api/v1/ready")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "pronto", "database": "ok"}


def test_ready_devolve_503_quando_o_banco_falha(client: TestClient) -> None:
    class SessaoQuebrada:
        def execute(self, *_: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("conexão recusada"))

    def db_quebrado() -> Iterator[SessaoQuebrada]:
        yield SessaoQuebrada()

    client.app.dependency_overrides[get_db] = db_quebrado

    resposta = client.get("/api/v1/ready")

    assert resposta.status_code == 503
    assert resposta.json() == {"status": "indisponivel", "database": "erro"}
