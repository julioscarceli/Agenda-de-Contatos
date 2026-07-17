import json
import os
import re

from openai import OpenAI

from app.models import Coluna, Contato, Tarefa
from app import storage

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Colunas que todo usuário novo ganha de cara, pra não abrir um quadro vazio.
# Isso não trava nada — o usuário pode renomear, apagar ou criar quantas
# quiser depois; é só um ponto de partida. Cada uma já vem com uma cor, pra
# virar a bolinha colorida do cabeçalho (estilo SpeckFlow).
COLUNAS_PADRAO_CONTATO = [
    ("Lead", "#6366f1"),
    ("Negociando", "#f59e0b"),
    ("Cliente", "#10b981"),
    ("Inativo", "#94a3b8"),
]
COLUNAS_PADRAO_TAREFA = [
    ("Executando", "#0ea5e9"),
    ("Prioridade", "#ef4444"),
    ("Lembretes", "#f59e0b"),
    ("Ideias", "#a855f7"),
]


class ContatoInvalido(Exception):
    pass


class ContatoNaoEncontrado(Exception):
    pass


class TarefaInvalida(Exception):
    pass


class TarefaNaoEncontrada(Exception):
    pass


class ColunaInvalida(Exception):
    pass


# Um contato nasce só com o nome (é só isso que a voz dita — telefone
# ditado por áudio é ruim de usar). Telefone e email ficam opcionais na
# criação; o card vem em branco nesses campos até alguém digitar depois.
def _validar_dados_contato(nome: str, telefone: str | None, email: str | None) -> None:
    if not nome.strip():
        raise ContatoInvalido("Nome não pode ser vazio.")
    if email and not REGEX_EMAIL.match(email):
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

    colunas_padrao = COLUNAS_PADRAO_CONTATO if pilar == "contato" else COLUNAS_PADRAO_TAREFA
    for ordem, (nome, cor) in enumerate(colunas_padrao):
        storage.inserir_coluna(
            conexao, Coluna(usuario_id=usuario_id, pilar=pilar, nome=nome, ordem=ordem, cor=cor)
        )
    return storage.listar_colunas(conexao, usuario_id, pilar)


def listar_colunas(conexao, usuario_id: str, pilar: str) -> list[Coluna]:
    return storage.listar_colunas(conexao, usuario_id, pilar)


# Muda o nome de uma fase (ex: renomear "Lead" pra "Novo Contato"). Os
# cards que já estão nela continuam lá — só o rótulo muda.
def renomear_coluna(conexao, coluna_id: int, novo_nome: str, usuario_id: str) -> None:
    if not novo_nome.strip():
        raise ColunaInvalida("Nome da fase não pode ser vazio.")
    atualizado = storage.atualizar_nome_coluna(conexao, coluna_id, novo_nome.strip(), usuario_id)
    if not atualizado:
        raise ColunaInvalida(f"Coluna {coluna_id} não encontrada.")


# Cria uma fase nova, sempre no final do quadro (depois da última coluna
# que já existe) — o usuário decide o nome, a gente só posiciona.
def criar_coluna(conexao, usuario_id: str, pilar: str, nome: str) -> Coluna:
    if not nome.strip():
        raise ColunaInvalida("Nome da fase não pode ser vazio.")
    colunas_existentes = storage.listar_colunas(conexao, usuario_id, pilar)
    nova_ordem = len(colunas_existentes)
    coluna = Coluna(usuario_id=usuario_id, pilar=pilar, nome=nome.strip(), ordem=nova_ordem)
    coluna.id = storage.inserir_coluna(conexao, coluna)
    return coluna


# --- Contatos ------------------------------------------------------------

def adicionar_contato(
    conexao, usuario_id: str, nome: str, telefone: str | None = None, email: str | None = None,
    coluna_id: int | None = None, nota: str | None = None, origem: str = "manual",
) -> Contato:
    _validar_dados_contato(nome, telefone, email)
    contato = Contato(
        usuario_id=usuario_id, nome=nome, telefone=telefone or "", email=email or "",
        coluna_id=coluna_id, nota=nota, origem=origem,
    )
    contato.id = storage.inserir_contato(conexao, contato)
    return contato


def listar_contatos(conexao, usuario_id: str, status: str = "ativo") -> list[Contato]:
    return storage.listar_contatos(conexao, usuario_id, status)


def editar_contato(
    conexao, id_contato: int, nome: str, usuario_id: str, telefone: str | None = None,
    email: str | None = None, nota: str | None = None,
) -> Contato:
    _validar_dados_contato(nome, telefone, email)
    atualizado = storage.atualizar_contato(
        conexao, id_contato, nome, telefone or "", email or "", nota, usuario_id
    )
    if not atualizado:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")
    return storage.buscar_contato(conexao, id_contato, usuario_id)


# Arrasta o card do contato pra outra coluna do quadro (ex: de "Lead" pra
# "Negociando").
def mover_contato(conexao, id_contato: int, coluna_id: int, usuario_id: str) -> Contato:
    movido = storage.mover_contato_de_coluna(conexao, id_contato, coluna_id, usuario_id)
    if not movido:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")
    return storage.buscar_contato(conexao, id_contato, usuario_id)


# Marca o contato como resolvido — some do quadro ativo, mas continua no
# banco (aparece numa vista de "Resolvidos", não é apagado de verdade).
def resolver_contato(conexao, id_contato: int, usuario_id: str) -> None:
    alterado = storage.mudar_status_contato(conexao, id_contato, "resolvido", usuario_id)
    if not alterado:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")


# Manda o contato pra lixeira — mesma lógica do resolver, só que pro "lixo".
def mover_contato_para_lixeira(conexao, id_contato: int, usuario_id: str) -> None:
    alterado = storage.mudar_status_contato(conexao, id_contato, "lixeira", usuario_id)
    if not alterado:
        raise ContatoNaoEncontrado(f"Contato {id_contato} não encontrado.")


# Traz um contato resolvido de volta pro quadro ativo — a vista de
# "Resolvidos" usa isso quando você decide que, na verdade, ainda não
# terminou com aquele contato.
def reabrir_contato(conexao, id_contato: int, usuario_id: str) -> None:
    alterado = storage.mudar_status_contato(conexao, id_contato, "ativo", usuario_id)
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
def listar_tarefas(
    conexao, usuario_id: str, contato_id: int | None = None, status: str = "ativo"
) -> list[Tarefa]:
    return storage.listar_tarefas(conexao, usuario_id, contato_id, status)


def editar_tarefa(
    conexao, id_tarefa: int, titulo: str, descricao: str | None, prazo, usuario_id: str
) -> Tarefa:
    _validar_titulo_tarefa(titulo)
    atualizada = storage.atualizar_tarefa(conexao, id_tarefa, titulo, descricao, prazo, usuario_id)
    if not atualizada:
        raise TarefaNaoEncontrada(f"Tarefa {id_tarefa} não encontrada.")
    return storage.buscar_tarefa(conexao, id_tarefa, usuario_id)


def mover_tarefa(conexao, id_tarefa: int, coluna_id: int, usuario_id: str) -> Tarefa:
    movida = storage.mover_tarefa_de_coluna(conexao, id_tarefa, coluna_id, usuario_id)
    if not movida:
        raise TarefaNaoEncontrada(f"Tarefa {id_tarefa} não encontrada.")
    return storage.buscar_tarefa(conexao, id_tarefa, usuario_id)


def resolver_tarefa(conexao, id_tarefa: int, usuario_id: str) -> None:
    alterada = storage.mudar_status_tarefa(conexao, id_tarefa, "resolvido", usuario_id)
    if not alterada:
        raise TarefaNaoEncontrada(f"Tarefa {id_tarefa} não encontrada.")


def mover_tarefa_para_lixeira(conexao, id_tarefa: int, usuario_id: str) -> None:
    alterada = storage.mudar_status_tarefa(conexao, id_tarefa, "lixeira", usuario_id)
    if not alterada:
        raise TarefaNaoEncontrada(f"Tarefa {id_tarefa} não encontrada.")


# Traz uma tarefa resolvida de volta pro quadro ativo.
def reabrir_tarefa(conexao, id_tarefa: int, usuario_id: str) -> None:
    alterada = storage.mudar_status_tarefa(conexao, id_tarefa, "ativo", usuario_id)
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


# O "cérebro" do comando de voz: pega o texto já transcrito e pede pro GPT
# devolver, em formato estruturado (JSON), o que a pessoa quis dizer — se é
# pra criar um contato ou uma tarefa, em qual coluna, com quais campos.
# Usamos o gpt-4o-mini (o modelo mais leve/rápido da OpenAI) porque essa
# tarefa é simples — extrair alguns campos de uma frase curta — não precisa
# do modelo mais caro e mais lento.
PROMPT_INTERPRETADOR = """\
Você organiza uma agenda de contatos e tarefas. A pessoa vai falar um
comando em português pra criar um Contato ou uma Tarefa. Devolva SOMENTE um
JSON (sem markdown, sem explicação) com estes campos:

{{
  "pilar": "contato" ou "tarefa",
  "coluna_nome": nome da coluna mencionada (ou a mais parecida), ou null,
  "nome": nome da pessoa (só se pilar for contato) — é a ÚNICA informação
    que se espera por voz pra um contato; telefone, email e nota são
    preenchidos depois, digitados no card, então ignore mesmo que a pessoa
    fale mais alguma coisa,
  "titulo": título da tarefa (só se pilar for tarefa), ou null,
  "descricao": detalhe da tarefa (só se pilar for tarefa) — aqui pode vir
    bem completo, tarefa é ditada por inteiro, ou null,
  "contato_nome": nome do contato que a tarefa menciona vincular, ou null
}}

Colunas disponíveis de Contato: {colunas_contato}
Colunas disponíveis de Tarefa: {colunas_tarefa}
Contatos já cadastrados (pra vincular tarefa, se mencionado): {contatos}
"""


def interpretar_comando_de_voz(
    texto: str, nomes_colunas_contato: list[str], nomes_colunas_tarefa: list[str],
    nomes_contatos: list[str],
) -> dict:
    cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    prompt = PROMPT_INTERPRETADOR.format(
        colunas_contato=", ".join(nomes_colunas_contato),
        colunas_tarefa=", ".join(nomes_colunas_tarefa),
        contatos=", ".join(nomes_contatos) or "nenhum ainda",
    )
    resposta = cliente.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": texto},
        ],
    )
    return json.loads(resposta.choices[0].message.content)
