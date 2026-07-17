import os

import psycopg2
import psycopg2.extras
import psycopg2.pool

from app.models import Coluna, Contato, Tarefa


# Abre uma conexão nova com o Postgres, lendo o endereço da variável de
# ambiente DATABASE_URL (nunca escrita direto no código — sempre vem de
# fora, do .env ou do ambiente do servidor). Usada pelo CLI e pelos testes,
# que abrem uma conexão só e a mantêm durante toda a sessão.
def conectar():
    return psycopg2.connect(os.environ["DATABASE_URL"])


# O site web (app/main.py) recebe muitas requisições curtas — cada clique
# no quadro é uma requisição nova. Abrir uma conexão do zero a cada clique
# é caro (principalmente hoje, em dev local, onde o banco está do outro
# lado da internet, no Zeabur). Esse "pool" mantém algumas conexões já
# abertas e prontas, emprestando uma pra cada requisição em vez de criar
# uma nova toda vez.
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def obter_conexao():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, os.environ["DATABASE_URL"])
    return _pool.getconn()


# Devolve a conexão pro pool (em vez de fechar de verdade), pra ela poder
# ser reaproveitada na próxima requisição.
def devolver_conexao(conexao) -> None:
    if _pool is not None:
        _pool.putconn(conexao)


# Cria as três tabelas do projeto se elas ainda não existirem. Pode rodar
# toda vez que o programa inicia sem medo — "IF NOT EXISTS" garante que não
# dá erro se a tabela já estiver lá.
#
# Repare que nenhuma tabela usa DELETE de verdade: em vez disso, todo mundo
# tem uma coluna "status", que é o nosso jeito de fazer "soft delete" — igual
# a Lixeira/Resolvidas do SpeckFlow, nada some de vez.
def criar_tabelas(conexao) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS colunas (
                id SERIAL PRIMARY KEY,
                usuario_id UUID NOT NULL REFERENCES auth.users(id),
                pilar TEXT NOT NULL,
                nome TEXT NOT NULL,
                ordem INTEGER NOT NULL,
                cor TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contatos (
                id SERIAL PRIMARY KEY,
                usuario_id UUID NOT NULL REFERENCES auth.users(id),
                nome TEXT NOT NULL,
                telefone TEXT NOT NULL,
                email TEXT NOT NULL,
                coluna_id INTEGER REFERENCES colunas(id),
                nota TEXT,
                origem TEXT NOT NULL DEFAULT 'manual',
                lembrete_em TIMESTAMPTZ,
                status TEXT NOT NULL DEFAULT 'ativo'
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tarefas (
                id SERIAL PRIMARY KEY,
                usuario_id UUID NOT NULL REFERENCES auth.users(id),
                titulo TEXT NOT NULL,
                descricao TEXT,
                contato_id INTEGER REFERENCES contatos(id),
                coluna_id INTEGER REFERENCES colunas(id),
                prazo DATE,
                lembrete_em TIMESTAMPTZ,
                origem TEXT NOT NULL DEFAULT 'manual',
                audio_url TEXT,
                status TEXT NOT NULL DEFAULT 'ativo'
            )
            """
        )
    conexao.commit()


# --- Colunas -----------------------------------------------------------

# Traduz uma linha crua do banco (um dicionário) pra um objeto Coluna.
def _linha_para_coluna(linha: dict) -> Coluna:
    return Coluna(
        id=linha["id"],
        usuario_id=str(linha["usuario_id"]),
        pilar=linha["pilar"],
        nome=linha["nome"],
        ordem=linha["ordem"],
        cor=linha["cor"],
    )


# Cria uma coluna nova pro usuário (ex: usuário criou a etapa "Negociando").
def inserir_coluna(conexao, coluna: Coluna) -> int:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO colunas (usuario_id, pilar, nome, ordem, cor)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (coluna.usuario_id, coluna.pilar, coluna.nome, coluna.ordem, coluna.cor),
        )
        id_gerado = cursor.fetchone()[0]
    conexao.commit()
    return id_gerado


# Lista as colunas de um usuário, filtrando por pilar ('contato' ou
# 'tarefa') — cada quadro só mostra as colunas que pertencem a ele.
def listar_colunas(conexao, usuario_id: str, pilar: str) -> list[Coluna]:
    with conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            "SELECT * FROM colunas WHERE usuario_id = %s AND pilar = %s ORDER BY ordem",
            (usuario_id, pilar),
        )
        linhas = cursor.fetchall()
    return [_linha_para_coluna(linha) for linha in linhas]


# Troca só o nome de uma coluna (o usuário decidiu chamar "Lead" de outra
# coisa, por exemplo) — a etapa continua a mesma, com os mesmos cards. O
# filtro por usuario_id garante que ninguém renomeia coluna de outra conta.
def atualizar_nome_coluna(conexao, coluna_id: int, nome: str, usuario_id: str) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE colunas SET nome = %s WHERE id = %s AND usuario_id = %s",
            (nome, coluna_id, usuario_id),
        )
        atualizado = cursor.rowcount > 0
    conexao.commit()
    return atualizado


# --- Contatos ------------------------------------------------------------

def _linha_para_contato(linha: dict) -> Contato:
    return Contato(
        id=linha["id"],
        usuario_id=str(linha["usuario_id"]),
        nome=linha["nome"],
        telefone=linha["telefone"],
        email=linha["email"],
        coluna_id=linha["coluna_id"],
        nota=linha["nota"],
        origem=linha["origem"],
        lembrete_em=linha["lembrete_em"],
        status=linha["status"],
    )


def inserir_contato(conexao, contato: Contato) -> int:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO contatos
                (usuario_id, nome, telefone, email, coluna_id, nota, origem, lembrete_em, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                contato.usuario_id,
                contato.nome,
                contato.telefone,
                contato.email,
                contato.coluna_id,
                contato.nota,
                contato.origem,
                contato.lembrete_em,
                contato.status,
            ),
        )
        id_gerado = cursor.fetchone()[0]
    conexao.commit()
    return id_gerado


# Lista os contatos "vivos" de um usuário (não apaga nada, só esconde quem
# está resolvido ou na lixeira).
def listar_contatos(conexao, usuario_id: str, status: str = "ativo") -> list[Contato]:
    with conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            "SELECT * FROM contatos WHERE usuario_id = %s AND status = %s ORDER BY id",
            (usuario_id, status),
        )
        linhas = cursor.fetchall()
    return [_linha_para_contato(linha) for linha in linhas]


# Busca um contato só se ele for do usuário informado — impede que alguém
# logado veja/edite o contato de outra conta só adivinhando o id.
def buscar_contato(conexao, id_contato: int, usuario_id: str) -> Contato | None:
    with conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            "SELECT * FROM contatos WHERE id = %s AND usuario_id = %s", (id_contato, usuario_id)
        )
        linha = cursor.fetchone()
    return _linha_para_contato(linha) if linha else None


def atualizar_contato(
    conexao, id_contato: int, nome: str, telefone: str, email: str, nota: str | None, usuario_id: str
) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            UPDATE contatos SET nome = %s, telefone = %s, email = %s, nota = %s
            WHERE id = %s AND usuario_id = %s
            """,
            (nome, telefone, email, nota, id_contato, usuario_id),
        )
        atualizado = cursor.rowcount > 0
    conexao.commit()
    return atualizado


# Move o contato pra outra coluna (ex: arrastar de "Lead" pra "Cliente").
def mover_contato_de_coluna(conexao, id_contato: int, coluna_id: int, usuario_id: str) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE contatos SET coluna_id = %s WHERE id = %s AND usuario_id = %s",
            (coluna_id, id_contato, usuario_id),
        )
        movido = cursor.rowcount > 0
    conexao.commit()
    return movido


# Muda o status do contato (ativo / resolvido / lixeira) — é o nosso "soft
# delete": nunca roda DELETE de verdade num contato.
def mudar_status_contato(conexao, id_contato: int, status: str, usuario_id: str) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE contatos SET status = %s WHERE id = %s AND usuario_id = %s",
            (status, id_contato, usuario_id),
        )
        alterado = cursor.rowcount > 0
    conexao.commit()
    return alterado


# --- Tarefas ------------------------------------------------------------

def _linha_para_tarefa(linha: dict) -> Tarefa:
    return Tarefa(
        id=linha["id"],
        usuario_id=str(linha["usuario_id"]),
        titulo=linha["titulo"],
        descricao=linha["descricao"],
        contato_id=linha["contato_id"],
        coluna_id=linha["coluna_id"],
        prazo=linha["prazo"],
        lembrete_em=linha["lembrete_em"],
        origem=linha["origem"],
        audio_url=linha["audio_url"],
        status=linha["status"],
    )


def inserir_tarefa(conexao, tarefa: Tarefa) -> int:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO tarefas
                (usuario_id, titulo, descricao, contato_id, coluna_id, prazo,
                 lembrete_em, origem, audio_url, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                tarefa.usuario_id,
                tarefa.titulo,
                tarefa.descricao,
                tarefa.contato_id,
                tarefa.coluna_id,
                tarefa.prazo,
                tarefa.lembrete_em,
                tarefa.origem,
                tarefa.audio_url,
                tarefa.status,
            ),
        )
        id_gerado = cursor.fetchone()[0]
    conexao.commit()
    return id_gerado


# Lista as tarefas de um usuário filtrando por status (ativo, resolvido ou
# lixeira). Se contato_id for passado, filtra só as tarefas daquele contato
# específico (útil pra mostrar a timeline dele).
def listar_tarefas(
    conexao, usuario_id: str, contato_id: int | None = None, status: str = "ativo"
) -> list[Tarefa]:
    with conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        if contato_id is None:
            cursor.execute(
                "SELECT * FROM tarefas WHERE usuario_id = %s AND status = %s ORDER BY id",
                (usuario_id, status),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM tarefas
                WHERE usuario_id = %s AND contato_id = %s AND status = %s
                ORDER BY id
                """,
                (usuario_id, contato_id, status),
            )
        linhas = cursor.fetchall()
    return [_linha_para_tarefa(linha) for linha in linhas]


# Mesma ideia de buscar_contato: só acha a tarefa se ela for do usuário
# informado, pra ninguém mexer na tarefa de outra conta pelo id.
def buscar_tarefa(conexao, id_tarefa: int, usuario_id: str) -> Tarefa | None:
    with conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            "SELECT * FROM tarefas WHERE id = %s AND usuario_id = %s", (id_tarefa, usuario_id)
        )
        linha = cursor.fetchone()
    return _linha_para_tarefa(linha) if linha else None


def atualizar_tarefa(
    conexao, id_tarefa: int, titulo: str, descricao: str | None, prazo, usuario_id: str
) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            UPDATE tarefas SET titulo = %s, descricao = %s, prazo = %s
            WHERE id = %s AND usuario_id = %s
            """,
            (titulo, descricao, prazo, id_tarefa, usuario_id),
        )
        atualizado = cursor.rowcount > 0
    conexao.commit()
    return atualizado


def mover_tarefa_de_coluna(conexao, id_tarefa: int, coluna_id: int, usuario_id: str) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE tarefas SET coluna_id = %s WHERE id = %s AND usuario_id = %s",
            (coluna_id, id_tarefa, usuario_id),
        )
        movida = cursor.rowcount > 0
    conexao.commit()
    return movida


def mudar_status_tarefa(conexao, id_tarefa: int, status: str, usuario_id: str) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE tarefas SET status = %s WHERE id = %s AND usuario_id = %s",
            (status, id_tarefa, usuario_id),
        )
        alterado = cursor.rowcount > 0
    conexao.commit()
    return alterado
