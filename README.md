# Agenda de Contatos + Tarefas

Nasceu como o desafio prático do módulo "Introdução ao Python" (Rocketseat),
mas evoluiu pra ser o embrião de um CRM: dois pilares (Contatos e Tarefas),
organizados num quadro Kanban com colunas que cada usuário personaliza,
inspirado no [SpeckFlow](https://speckflow.zeabur.app) — incluindo captura
por voz como forma de entrada.

Veja [`EXPLICACAO-DO-PROJETO.md`](./EXPLICACAO-DO-PROJETO.md) para entender
a lógica por trás de cada decisão.

## O que já existe

- **Contatos**: adicionar, listar, editar, mover entre colunas, resolver,
  mover pra lixeira (nada se apaga de vez).
- **Tarefas**: as mesmas ações, e podem ficar soltas ou vinculadas a um
  contato específico.
- **Colunas personalizáveis** por usuário e por pilar (contato/tarefa),
  com um conjunto padrão pra não começar vazio.
- **Transcrição de voz** (Whisper da OpenAI) pronta em `services.py`, ainda
  sem interface conectada — vai plugar quando o frontend/extensão existir.

## Estrutura

```
app/
  models.py    # Coluna, Contato, Tarefa (dataclasses)
  storage.py   # acesso ao Postgres (psycopg2, SQL puro), soft delete
  services.py  # validação, regras de negócio, transcrição de voz
cli.py         # menu de terminal (interface provisória, até o frontend)
tests/         # testes de services.py contra um Postgres real
```

## Rodando localmente

O Postgres não tem porta pública exposta por padrão (prática de segurança —
ver `EXPLICACAO-DO-PROJETO.md`). Pra rodar local, reabilitar temporariamente:

```bash
zeabur service port-forward --id 6a590446725eab1a1db8003e --enable
pip install -r requirements.txt
cp .env.example .env
# preencher DATABASE_URL (via `zeabur service instruction`), USUARIO_ID_TESTE e OPENAI_API_KEY
python cli.py
# ao terminar:
zeabur service port-forward --id 6a590446725eab1a1db8003e --disable
```

## Testes

```bash
pytest tests/
```

## Status

Backend com os dois pilares modularizado e validado (17 testes). Frontend
(Kanban + voz) ainda não construído.
