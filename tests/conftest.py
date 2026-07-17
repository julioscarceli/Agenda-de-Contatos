import os

import psycopg2
import pytest
from dotenv import load_dotenv

from app import storage

load_dotenv()


# Os testes usam um banco separado (TEST_DATABASE_URL), nunca o
# DATABASE_URL de produção — esse fixture faz TRUNCATE a cada teste, e
# já aconteceu de apagar dados reais de verdade quando as duas variáveis
# apontavam pro mesmo banco. Ver EXPLICACAO-DO-PROJETO.md /
# memória "nunca truncar banco de produção".
@pytest.fixture
def conexao():
    url_teste = os.environ["TEST_DATABASE_URL"]
    if url_teste == os.environ.get("DATABASE_URL"):
        raise RuntimeError(
            "TEST_DATABASE_URL está igual ao DATABASE_URL de produção — "
            "abortando pra não truncar dado de verdade de novo."
        )

    conexao = psycopg2.connect(url_teste)

    # O banco de teste é um Postgres puro (sem o Supabase Auth em cima),
    # mas colunas/contatos/tarefas referenciam auth.users(id) via chave
    # estrangeira — precisa existir esse schema mínimo, com o usuário de
    # teste dentro, antes de criar as tabelas do projeto.
    with conexao.cursor() as cursor:
        cursor.execute("CREATE SCHEMA IF NOT EXISTS auth")
        cursor.execute("CREATE TABLE IF NOT EXISTS auth.users (id UUID PRIMARY KEY)")
        cursor.execute(
            "INSERT INTO auth.users (id) VALUES (%s) ON CONFLICT DO NOTHING",
            (os.environ["USUARIO_ID_TESTE"],),
        )
    conexao.commit()

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
