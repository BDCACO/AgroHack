"""Agrega as rotas da v1. Cada recurso novo entra com uma linha aqui, e com o nível de
permissão dele (app/api/permissoes.py): é aqui, num lugar só, que se vê quem pode o quê.
`tests/test_permissoes.py` recusa rota que não esteja na matriz."""

from fastapi import APIRouter, Depends

from app.api.permissoes import (
    exigir_dono,
    exigir_dono_com_login,
    exigir_funcionario,
    exigir_sessao,
)
from app.api.routes import (
    analises,
    autenticacao,
    estoque,
    fornecedores,
    health,
    pedidos,
    talhoes,
    usuarios,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(autenticacao.publico)
api_router.include_router(autenticacao.router, dependencies=[Depends(exigir_sessao)])
api_router.include_router(estoque.campo, dependencies=[Depends(exigir_funcionario)])
api_router.include_router(estoque.gestao, dependencies=[Depends(exigir_dono)])
api_router.include_router(talhoes.campo, dependencies=[Depends(exigir_funcionario)])
api_router.include_router(talhoes.gestao, dependencies=[Depends(exigir_dono)])
api_router.include_router(fornecedores.campo, dependencies=[Depends(exigir_funcionario)])
api_router.include_router(fornecedores.gestao, dependencies=[Depends(exigir_dono)])
api_router.include_router(pedidos.campo, dependencies=[Depends(exigir_funcionario)])
api_router.include_router(pedidos.gestao, dependencies=[Depends(exigir_dono)])
api_router.include_router(analises.router, dependencies=[Depends(exigir_dono)])
api_router.include_router(usuarios.router, dependencies=[Depends(exigir_dono_com_login)])
