"""As migrations no PostgreSQL: descem até o zero e sobem de novo, e o schema que elas
criam é o mesmo dos modelos (o autogenerate não acha nada a fazer)."""

import subprocess

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from tests.integracao.conftest import alembic


def test_migrations_descem_e_sobem_e_batem_com_os_modelos(banco: Engine) -> None:
    # O banco da sessão pode ter preços, uuids, talhões, usuários, compras e categorias de
    # outro teste: descartá-los é o pedido aqui.
    alembic(
        "-x",
        "descartar_categorias=sim",
        "-x",
        "descartar_compras=sim",
        "-x",
        "descartar_precos=sim",
        "-x",
        "descartar_uuids=sim",
        "-x",
        "descartar_talhoes=sim",
        "-x",
        "descartar_usuarios=sim",
        "downgrade",
        "base",
    )
    alembic("upgrade", "head")

    assert "No new upgrade operations detected" in alembic("check").stdout


def test_downgrade_nao_descarta_precos_sem_pedir(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(
            text("INSERT INTO insumos (nome, unidade, embalagem) VALUES ('Ureia', 'kg', 50)")
        )

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0005")
    assert "descartar_precos=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT embalagem FROM insumos")) == 50

    alembic("-x", "descartar_precos=sim", "downgrade", "0005")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT nome FROM insumos")) == "Ureia"
    alembic("upgrade", "head")


def test_downgrade_nao_descarta_o_uuid_do_app_sem_pedir(banco: Engine) -> None:
    identificador = "6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e"
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))
        conexao.execute(
            text(
                "INSERT INTO movimentacoes (insumo_id, tipo, data, quantidade, uuid)"
                " VALUES (1, 'entrada', '2026-10-01', 5, :uuid)"
            ),
            {"uuid": identificador},
        )

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0006")
    assert "descartar_uuids=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert str(conexao.scalar(text("SELECT uuid FROM movimentacoes"))) == identificador

    alembic("-x", "descartar_uuids=sim", "downgrade", "0006")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT quantidade FROM movimentacoes")) == 5
    alembic("upgrade", "head")


def test_downgrade_nao_descarta_talhoes_sem_pedir(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, talhoes RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO talhoes (nome, area_ha) VALUES ('Talhão Norte', 120)"))

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0007")
    assert "descartar_talhoes=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT area_ha FROM talhoes")) == 120

    alembic("-x", "descartar_talhoes=sim", "downgrade", "0007")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT to_regclass('talhoes')")) is None
    alembic("upgrade", "head")


def test_downgrade_nao_descarta_a_carencia_sem_pedir(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, talhoes RESTART IDENTITY CASCADE"))
        conexao.execute(
            text("INSERT INTO insumos (nome, unidade, carencia_dias) VALUES ('Fungicida', 'L', 30)")
        )

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0007")
    assert "descartar_talhoes=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT carencia_dias FROM insumos")) == 30
    alembic("-x", "descartar_talhoes=sim", "downgrade", "0007")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT nome FROM insumos")) == "Fungicida"
    alembic("upgrade", "head")


def test_downgrade_nao_descarta_usuarios_sem_pedir(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, usuarios RESTART IDENTITY CASCADE"))
        conexao.execute(
            text(
                "INSERT INTO usuarios (nome, login, senha_hash, papel)"
                " VALUES ('Dona Maria', 'maria', 'scrypt$x', 'dono')"
            )
        )

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0008")
    assert "descartar_usuarios=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT login FROM usuarios")) == "maria"

    alembic("-x", "descartar_usuarios=sim", "downgrade", "0008")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT to_regclass('usuarios')")) is None
    alembic("upgrade", "head")


@pytest.mark.parametrize(
    ("login", "papel", "restricao"),
    [
        ("Maria", "dono", "ck_usuarios_login_minusculo"),  # o login se compara em minúsculas
        ("maria", "gerente", "ck_usuarios_papel_valido"),
    ],
)
def test_banco_recusa_usuario_incoerente_mesmo_fora_da_api(
    banco: Engine, login: str, papel: str, restricao: str
) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE usuarios RESTART IDENTITY CASCADE"))

    with pytest.raises(IntegrityError, match=restricao), banco.begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO usuarios (nome, login, senha_hash, papel)"
                " VALUES ('Maria', :login, 'scrypt$x', :papel)"
            ),
            {"login": login, "papel": papel},
        )


def test_usuario_que_lancou_nao_se_apaga_nem_fora_da_api(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, usuarios RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))
        conexao.execute(
            text(
                "INSERT INTO usuarios (nome, login, senha_hash, papel)"
                " VALUES ('Zé', 'ze', 'scrypt$x', 'funcionario')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO movimentacoes (insumo_id, tipo, data, quantidade, usuario_id)"
                " VALUES (1, 'saida', '2026-10-01', 1, 1)"
            )
        )

    with (
        pytest.raises(IntegrityError, match="fk_movimentacoes_usuario_id_usuarios"),
        banco.begin() as conexao,
    ):
        conexao.execute(text("DELETE FROM usuarios"))


def test_banco_recusa_o_mesmo_uuid_duas_vezes(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))
    inserir = text(
        "INSERT INTO movimentacoes (insumo_id, tipo, data, quantidade, uuid)"
        " VALUES (1, 'saida', '2026-10-01', 1, '6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e')"
    )
    with banco.begin() as conexao:
        conexao.execute(inserir)

    with pytest.raises(IntegrityError, match="uq_movimentacoes_uuid"), banco.begin() as conexao:
        conexao.execute(inserir)


@pytest.mark.parametrize(
    ("tipo", "motivo", "validade", "valor"),
    [
        ("entrada", "descarte", None, None),  # descarte é saída
        ("saida", "perdi", None, None),  # motivo desconhecido
        ("saida", None, "2027-01-01", None),  # validade só em entrada
        ("troca", None, None, None),  # tipo desconhecido
        ("saida", None, None, 3),  # preço é de compra
        ("entrada", "inventario", None, 3),  # a sobra da contagem não foi comprada
        ("entrada", None, None, 0),  # preço zero não é preço
    ],
)
def test_banco_recusa_movimentacao_incoerente_mesmo_fora_da_api(
    banco: Engine, tipo: str, motivo: str | None, validade: str | None, valor: float | None
) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))

    with pytest.raises(IntegrityError, match="ck_movimentacoes"), banco.begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO movimentacoes"
                " (insumo_id, tipo, data, quantidade, motivo, validade, valor_unitario)"
                " VALUES (1, :tipo, '2026-10-01', 1, :motivo, :validade, :valor)"
            ),
            {"tipo": tipo, "motivo": motivo, "validade": validade, "valor": valor},
        )


@pytest.mark.parametrize(
    ("tipo", "motivo"),
    [("entrada", None), ("saida", "descarte"), ("saida", "inventario"), ("entrada", "inventario")],
)
def test_banco_recusa_talhao_fora_da_retirada_para_uso(
    banco: Engine, tipo: str, motivo: str | None
) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, talhoes RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Glifosato', 'L')"))
        conexao.execute(text("INSERT INTO talhoes (nome, area_ha) VALUES ('Norte', 120)"))
    inserir = text(
        "INSERT INTO movimentacoes (insumo_id, tipo, data, quantidade, motivo, talhao_id)"
        " VALUES (1, :tipo, '2026-10-01', 1, :motivo, 1)"
    )

    with (
        pytest.raises(IntegrityError, match="ck_movimentacoes_talhao_so_em_aplicacao"),
        banco.begin() as conexao,
    ):
        conexao.execute(inserir, {"tipo": tipo, "motivo": motivo})
    # A retirada para uso aceita; e o talhão com ela não se apaga, nem fora da API.
    with banco.begin() as conexao:
        conexao.execute(inserir, {"tipo": "saida", "motivo": None})
    with (
        pytest.raises(IntegrityError, match="fk_movimentacoes_talhao_id_talhoes"),
        banco.begin() as conexao,
    ):
        conexao.execute(text("DELETE FROM talhoes"))


def test_downgrade_nao_descarta_fornecedores_e_pedidos_sem_pedir(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(
            text("TRUNCATE insumos, fornecedores, pedidos, usuarios RESTART IDENTITY CASCADE")
        )
        conexao.execute(text("INSERT INTO fornecedores (nome) VALUES ('Revenda Boa Safra')"))

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0009")
    assert "descartar_compras=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT nome FROM fornecedores")) == "Revenda Boa Safra"

    alembic("-x", "descartar_compras=sim", "downgrade", "0009")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT to_regclass('fornecedores')")) is None
        assert conexao.scalar(text("SELECT to_regclass('pedidos')")) is None
    alembic("upgrade", "head")


@pytest.mark.parametrize(
    ("tipo", "motivo"), [("saida", None), ("saida", "descarte"), ("entrada", "inventario")]
)
def test_banco_recusa_fornecedor_e_pedido_fora_da_compra(
    banco: Engine, tipo: str, motivo: str | None
) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, fornecedores, pedidos RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))
        conexao.execute(text("INSERT INTO fornecedores (nome) VALUES ('Revenda')"))
        conexao.execute(
            text(
                "INSERT INTO pedidos (fornecedor_id, situacao, feito_em)"
                " VALUES (1, 'aberto', '2026-10-01')"
            )
        )
        conexao.execute(
            text("INSERT INTO itens_do_pedido (pedido_id, insumo_id, quantidade) VALUES (1, 1, 50)")
        )
    inserir = text(
        "INSERT INTO movimentacoes"
        " (insumo_id, tipo, data, quantidade, motivo, fornecedor_id, item_do_pedido_id)"
        " VALUES (1, :tipo, '2026-10-01', 1, :motivo, :fornecedor, :item)"
    )
    for fornecedor, item, restricao in (
        (1, None, "ck_movimentacoes_fornecedor_so_em_compra"),
        (None, 1, "ck_movimentacoes_pedido_so_em_compra"),
    ):
        with pytest.raises(IntegrityError, match=restricao), banco.begin() as conexao:
            conexao.execute(
                inserir, {"tipo": tipo, "motivo": motivo, "fornecedor": fornecedor, "item": item}
            )
    # A compra aceita os dois; e o fornecedor com compra ou pedido não se apaga, nem fora
    # da API.
    with banco.begin() as conexao:
        conexao.execute(inserir, {"tipo": "entrada", "motivo": None, "fornecedor": 1, "item": 1})
    with (
        pytest.raises(
            IntegrityError, match=r"fk_(movimentacoes|pedidos)_fornecedor_id_fornecedores"
        ),
        banco.begin() as conexao,
    ):
        conexao.execute(text("DELETE FROM fornecedores"))


@pytest.mark.parametrize(
    ("situacao", "previsto_para", "restricao"),
    [
        ("perdido", None, "ck_pedidos_situacao_valida"),
        ("aberto", "2026-09-30", "ck_pedidos_previsto_depois_de_feito"),
    ],
)
def test_banco_recusa_pedido_incoerente_mesmo_fora_da_api(
    banco: Engine, situacao: str, previsto_para: str | None, restricao: str
) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE pedidos RESTART IDENTITY CASCADE"))

    with pytest.raises(IntegrityError, match=restricao), banco.begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO pedidos (situacao, feito_em, previsto_para)"
                " VALUES (:situacao, '2026-10-01', :previsto_para)"
            ),
            {"situacao": situacao, "previsto_para": previsto_para},
        )


def test_a_migration_cria_as_categorias_de_partida(banco: Engine) -> None:
    alembic("-x", "descartar_categorias=sim", "downgrade", "0010")
    alembic("upgrade", "head")

    with banco.connect() as conexao:
        nomes = conexao.scalars(text("SELECT nome FROM categorias ORDER BY id")).all()
    assert nomes[:3] == ["Fertilizante", "Corretivo de solo", "Defensivo agrícola"]
    assert "Nutrição animal" in nomes


@pytest.mark.parametrize("o_que", ["insumo com categoria", "categoria cadastrada pelo dono"])
def test_downgrade_nao_descarta_categorias_sem_pedir(banco: Engine, o_que: str) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, categorias RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO categorias (nome) VALUES ('Fertilizante')"))
        if o_que == "insumo com categoria":
            conexao.execute(
                text("INSERT INTO insumos (nome, unidade, categoria_id) VALUES ('Ureia', 'kg', 1)")
            )
        else:
            conexao.execute(text("INSERT INTO categorias (nome) VALUES ('Sementes de pasto')"))

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0010")
    assert "descartar_categorias=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT count(*) FROM categorias")) >= 1

    alembic("-x", "descartar_categorias=sim", "downgrade", "0010")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT to_regclass('categorias')")) is None
    alembic("upgrade", "head")


def test_so_as_categorias_de_partida_descem_sem_pedir(banco: Engine) -> None:
    # Recriadas pela própria migration ao subir: descê-las não perde nada.
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, categorias RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO categorias (nome) VALUES ('Fertilizante'), ('Outros')"))

    alembic("downgrade", "0010")
    alembic("upgrade", "head")


def test_categoria_com_insumo_nao_se_apaga_nem_fora_da_api(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, categorias RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO categorias (nome) VALUES ('Fertilizante')"))
        conexao.execute(
            text("INSERT INTO insumos (nome, unidade, categoria_id) VALUES ('Ureia', 'kg', 1)")
        )

    with (
        pytest.raises(IntegrityError, match="fk_insumos_categoria_id_categorias"),
        banco.begin() as conexao,
    ):
        conexao.execute(text("DELETE FROM categorias"))


def _indices_de_movimentacoes(banco: Engine) -> set[str]:
    with banco.connect() as conexao:
        return set(
            conexao.scalars(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'movimentacoes'")
            )
        )


def test_indices_da_lista_de_movimentacoes_sobem_e_descem(banco: Engine) -> None:
    novos = {"ix_movimentacoes_data_id", "ix_movimentacoes_insumo_id_data_id"}
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos, categorias RESTART IDENTITY CASCADE"))

    assert novos <= _indices_de_movimentacoes(banco)
    # O composto começa por insumo_id: o simples sairia redundante.
    assert "ix_movimentacoes_insumo_id" not in _indices_de_movimentacoes(banco)

    alembic("-x", "descartar_categorias=sim", "downgrade", "0010")
    depois = _indices_de_movimentacoes(banco)
    assert not novos & depois
    assert "ix_movimentacoes_insumo_id" in depois
    alembic("upgrade", "head")
