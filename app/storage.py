import os

import psycopg2
import psycopg2.extras

from app.models import Contato


def conectar() -> psycopg2.extensions.connection:
    return psycopg2.connect(os.environ["DATABASE_URL"])


def criar_tabela(conexao) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contatos (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                telefone TEXT NOT NULL,
                email TEXT NOT NULL,
                favorito BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )
    conexao.commit()


def _linha_para_contato(linha: dict) -> Contato:
    return Contato(
        id=linha["id"],
        nome=linha["nome"],
        telefone=linha["telefone"],
        email=linha["email"],
        favorito=linha["favorito"],
    )


def inserir_contato(conexao, contato: Contato) -> int:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO contatos (nome, telefone, email, favorito)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (contato.nome, contato.telefone, contato.email, contato.favorito),
        )
        id_gerado = cursor.fetchone()[0]
    conexao.commit()
    return id_gerado


def listar_contatos(conexao) -> list[Contato]:
    with conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute("SELECT * FROM contatos ORDER BY id")
        linhas = cursor.fetchall()
    return [_linha_para_contato(linha) for linha in linhas]


def listar_favoritos(conexao) -> list[Contato]:
    with conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute("SELECT * FROM contatos WHERE favorito = TRUE ORDER BY id")
        linhas = cursor.fetchall()
    return [_linha_para_contato(linha) for linha in linhas]


def buscar_contato(conexao, id_contato: int) -> Contato | None:
    with conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute("SELECT * FROM contatos WHERE id = %s", (id_contato,))
        linha = cursor.fetchone()
    return _linha_para_contato(linha) if linha else None


def atualizar_contato(conexao, id_contato: int, nome: str, telefone: str, email: str) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE contatos SET nome = %s, telefone = %s, email = %s WHERE id = %s",
            (nome, telefone, email, id_contato),
        )
        atualizado = cursor.rowcount > 0
    conexao.commit()
    return atualizado


def alternar_favorito(conexao, id_contato: int) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute(
            "UPDATE contatos SET favorito = NOT favorito WHERE id = %s", (id_contato,)
        )
        alterado = cursor.rowcount > 0
    conexao.commit()
    return alterado


def deletar_contato(conexao, id_contato: int) -> bool:
    with conexao.cursor() as cursor:
        cursor.execute("DELETE FROM contatos WHERE id = %s", (id_contato,))
        removido = cursor.rowcount > 0
    conexao.commit()
    return removido
