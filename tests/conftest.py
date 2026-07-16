import pytest
from dotenv import load_dotenv

from app import storage

load_dotenv()


@pytest.fixture
def conexao():
    conexao = storage.conectar()
    storage.criar_tabela(conexao)
    with conexao.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE contatos RESTART IDENTITY")
    conexao.commit()

    yield conexao

    conexao.close()
