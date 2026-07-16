from dataclasses import dataclass
from datetime import date, datetime


# Coluna é a "etapa" ou "gaveta" que o próprio usuário cria pra organizar o
# quadro dele — tipo "Lead", "Prioridade", "Ideias". Ela não vem pronta no
# sistema: cada usuário desenha o quadro do jeito que faz sentido pra ele.
# O campo "pilar" diz se essa coluna organiza Contatos ou Tarefas, já que os
# dois pilares moram no mesmo projeto mas têm quadros separados.
@dataclass
class Coluna:
    usuario_id: str
    pilar: str
    nome: str
    ordem: int
    cor: str | None = None
    id: int | None = None


# Contato é o "card" de uma pessoa na agenda. Antes ele só tinha um favorito
# (sim/não) — agora ele vive numa Coluna (a etapa em que está: lead,
# negociando, cliente...) e ganha uma nota livre, pra guardar aquele
# combinado ou detalhe que não cabe em nenhum campo fixo.
@dataclass
class Contato:
    usuario_id: str
    nome: str
    telefone: str
    email: str
    coluna_id: int | None = None
    nota: str | None = None
    origem: str = "manual"
    lembrete_em: datetime | None = None
    status: str = "ativo"
    id: int | None = None


# Tarefa é o segundo pilar do projeto. Ela pode viver solta (um lembrete
# genérico) ou grudada num Contato específico (ex: "ligar pro Cliente X") —
# por isso contato_id é opcional. Se ela nasceu de uma nota de voz, guardamos
# o áudio original em audio_url, além do texto transcrito em descricao.
@dataclass
class Tarefa:
    usuario_id: str
    titulo: str
    descricao: str | None = None
    contato_id: int | None = None
    coluna_id: int | None = None
    prazo: date | None = None
    lembrete_em: datetime | None = None
    origem: str = "manual"
    audio_url: str | None = None
    status: str = "ativo"
    id: int | None = None
