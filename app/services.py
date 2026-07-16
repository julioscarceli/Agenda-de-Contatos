import re
import sqlite3

from app.models import Contato
from app import storage

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContatoInvalido(Exception):
    pass


class ContatoNaoEncontrado(Exception):
    pass


def _validar_dados(nome: str, telefone: str, email: str) -> None:
    if not nome.strip():
        raise ContatoInvalido("Nome não pode ser vazio.")
    if not telefone.strip():
        raise ContatoInvalido("Telefone não pode ser vazio.")
    if not REGEX_EMAIL.match(email):
        raise ContatoInvalido(f"Email '{email}' é inválido.")


def adicionar_contato(
    conexao: sqlite3.Connection, nome: str, telefone: str, email: str
) -> Contato:
    _validar_dados(nome, telefone, email)
    contato = Contato(nome=nome, telefone=telefone, email=email)
    contato.id = storage.inserir_contato(conexao, contato)
    return contato


def listar_contatos(conexao: sqlite3.Connection) -> list[Contato]:
    return storage.listar_contatos(conexao)


def listar_favoritos(conexao: sqlite3.Connection) -> list[Contato]:
    return storage.listar_favoritos(conexao)


def editar_contato(
    conexao: sqlite3.Connection, id_contato: int, nome: str, telefone: str, email: str
) -> Contato:
    _validar_dados(nome, telefone, email)
    atualizado = storage.atualizar_contato(conexao, id_contato, nome, telefone, email)
    if not atualizado:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")
    return storage.buscar_contato(conexao, id_contato)


def alternar_favorito(conexao: sqlite3.Connection, id_contato: int) -> Contato:
    alterado = storage.alternar_favorito(conexao, id_contato)
    if not alterado:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")
    return storage.buscar_contato(conexao, id_contato)


def deletar_contato(conexao: sqlite3.Connection, id_contato: int) -> None:
    removido = storage.deletar_contato(conexao, id_contato)
    if not removido:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")
