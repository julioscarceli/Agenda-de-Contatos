import os
import re

from openai import OpenAI

from app.models import Coluna, Contato, Tarefa
from app import storage

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Colunas que todo usuário novo ganha de cara, pra não abrir um quadro vazio.
# Isso não trava nada — o usuário pode renomear, apagar ou criar quantas
# quiser depois; é só um ponto de partida.
COLUNAS_PADRAO_CONTATO = ["Lead", "Negociando", "Cliente", "Inativo"]
COLUNAS_PADRAO_TAREFA = ["Executando", "Prioridade", "Lembretes", "Ideias"]


class ContatoInvalido(Exception):
    pass


class ContatoNaoEncontrado(Exception):
    pass


class TarefaInvalida(Exception):
    pass


class TarefaNaoEncontrada(Exception):
    pass


def _validar_dados_contato(nome: str, telefone: str, email: str) -> None:
    if not nome.strip():
        raise ContatoInvalido("Nome não pode ser vazio.")
    if not telefone.strip():
        raise ContatoInvalido("Telefone não pode ser vazio.")
    if not REGEX_EMAIL.match(email):
        raise ContatoInvalido(f"Email '{email}' é inválido.")


def _validar_titulo_tarefa(titulo: str) -> None:
    if not titulo.strip():
        raise TarefaInvalida("Título não pode ser vazio.")


# --- Colunas -----------------------------------------------------------

# Se o usuário ainda não tem nenhuma coluna nesse pilar (ex: primeira vez
# usando o quadro de Tarefas), cria as colunas padrão pra ele começar com
# algo organizado em vez de uma tela vazia. Depois disso, é tudo dele: pode
# renomear, reordenar ou apagar — a gente só dá o empurrão inicial.
def garantir_colunas_padrao(conexao, usuario_id: str, pilar: str) -> list[Coluna]:
    colunas_existentes = storage.listar_colunas(conexao, usuario_id, pilar)
    if colunas_existentes:
        return colunas_existentes

    nomes_padrao = COLUNAS_PADRAO_CONTATO if pilar == "contato" else COLUNAS_PADRAO_TAREFA
    for ordem, nome in enumerate(nomes_padrao):
        storage.inserir_coluna(
            conexao, Coluna(usuario_id=usuario_id, pilar=pilar, nome=nome, ordem=ordem)
        )
    return storage.listar_colunas(conexao, usuario_id, pilar)


def listar_colunas(conexao, usuario_id: str, pilar: str) -> list[Coluna]:
    return storage.listar_colunas(conexao, usuario_id, pilar)


# --- Contatos ------------------------------------------------------------

def adicionar_contato(
    conexao, usuario_id: str, nome: str, telefone: str, email: str,
    coluna_id: int | None = None, nota: str | None = None,
) -> Contato:
    _validar_dados_contato(nome, telefone, email)
    contato = Contato(
        usuario_id=usuario_id, nome=nome, telefone=telefone, email=email,
        coluna_id=coluna_id, nota=nota,
    )
    contato.id = storage.inserir_contato(conexao, contato)
    return contato


def listar_contatos(conexao, usuario_id: str) -> list[Contato]:
    return storage.listar_contatos(conexao, usuario_id)


def editar_contato(
    conexao, id_contato: int, nome: str, telefone: str, email: str, nota: str | None = None,
) -> Contato:
    _validar_dados_contato(nome, telefone, email)
    atualizado = storage.atualizar_contato(conexao, id_contato, nome, telefone, email, nota)
    if not atualizado:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")
    return storage.buscar_contato(conexao, id_contato)


# Arrasta o card do contato pra outra coluna do quadro (ex: de "Lead" pra
# "Negociando").
def mover_contato(conexao, id_contato: int, coluna_id: int) -> Contato:
    movido = storage.mover_contato_de_coluna(conexao, id_contato, coluna_id)
    if not movido:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")
    return storage.buscar_contato(conexao, id_contato)


# Marca o contato como resolvido — some do quadro ativo, mas continua no
# banco (aparece numa vista de "Resolvidos", não é apagado de verdade).
def resolver_contato(conexao, id_contato: int) -> None:
    alterado = storage.mudar_status_contato(conexao, id_contato, "resolvido")
    if not alterado:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")


# Manda o contato pra lixeira — mesma lógica do resolver, só que pro "lixo".
def mover_contato_para_lixeira(conexao, id_contato: int) -> None:
    alterado = storage.mudar_status_contato(conexao, id_contato, "lixeira")
    if not alterado:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")


# --- Tarefas ------------------------------------------------------------

def adicionar_tarefa(
    conexao, usuario_id: str, titulo: str, descricao: str | None = None,
    contato_id: int | None = None, coluna_id: int | None = None,
    prazo=None, origem: str = "manual", audio_url: str | None = None,
) -> Tarefa:
    _validar_titulo_tarefa(titulo)
    tarefa = Tarefa(
        usuario_id=usuario_id, titulo=titulo, descricao=descricao,
        contato_id=contato_id, coluna_id=coluna_id, prazo=prazo,
        origem=origem, audio_url=audio_url,
    )
    tarefa.id = storage.inserir_tarefa(conexao, tarefa)
    return tarefa


# Lista as tarefas do usuário — se contato_id for passado, mostra só as
# tarefas daquele contato (a "timeline" dele: o que falta fazer com ele).
def listar_tarefas(conexao, usuario_id: str, contato_id: int | None = None) -> list[Tarefa]:
    return storage.listar_tarefas(conexao, usuario_id, contato_id)


def editar_tarefa(conexao, id_tarefa: int, titulo: str, descricao: str | None, prazo) -> Tarefa:
    _validar_titulo_tarefa(titulo)
    atualizada = storage.atualizar_tarefa(conexao, id_tarefa, titulo, descricao, prazo)
    if not atualizada:
        raise TarefaNaoEncontrada(f"Tarefa {id_tarefa} não encontrada.")
    return storage.buscar_tarefa(conexao, id_tarefa)


def mover_tarefa(conexao, id_tarefa: int, coluna_id: int) -> Tarefa:
    movida = storage.mover_tarefa_de_coluna(conexao, id_tarefa, coluna_id)
    if not movida:
        raise TarefaNaoEncontrada(f"Tarefa {id_tarefa} não encontrada.")
    return storage.buscar_tarefa(conexao, id_tarefa)


def resolver_tarefa(conexao, id_tarefa: int) -> None:
    alterada = storage.mudar_status_tarefa(conexao, id_tarefa, "resolvido")
    if not alterada:
        raise TarefaNaoEncontrada(f"Tarefa {id_tarefa} não encontrada.")


def mover_tarefa_para_lixeira(conexao, id_tarefa: int) -> None:
    alterada = storage.mudar_status_tarefa(conexao, id_tarefa, "lixeira")
    if not alterada:
        raise TarefaNaoEncontrada(f"Tarefa {id_tarefa} não encontrada.")


# --- Voz -----------------------------------------------------------------

# Manda um arquivo de áudio pro Whisper da OpenAI e devolve o texto
# transcrito. É a peça que vai permitir criar Contato/Tarefa falando em vez
# de digitar — a captura por voz que a gente gostou no SpeckFlow.
def transcrever_audio(caminho_arquivo: str) -> str:
    cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with open(caminho_arquivo, "rb") as arquivo_audio:
        resposta = cliente.audio.transcriptions.create(
            model="whisper-1", file=arquivo_audio, language="pt"
        )
    return resposta.text
