import os

import pytest
from dotenv import load_dotenv

from app import storage

load_dotenv()


@pytest.fixture
def conexao():
    conexao = storage.conectar()
    storage.criar_tabelas(conexao)

    # Limpa as três tabelas antes de cada teste. A ordem importa: tarefas
    # aponta pra contatos e colunas, contatos aponta pra colunas — por isso
    # truncamos tudo junto com CASCADE, em vez de uma tabela de cada vez.
    with conexao.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE tarefas, contatos, colunas RESTART IDENTITY CASCADE")
    conexao.commit()

    yield conexao

    conexao.close()


# O mesmo usuário de teste em toda a suíte — como ainda não existe tela de
# login, todo teste roda "como se fosse" esse usuário fixo.
@pytest.fixture
def usuario_id() -> str:
    return os.environ["USUARIO_ID_TESTE"]
