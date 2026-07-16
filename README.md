# Agenda de Contatos

Desafio prático do módulo "Introdução ao Python" (Rocketseat), evoluído além
do mínimo pedido: backend modularizado em camadas, persistência real em
Postgres, testes automatizados, com o objetivo de virar peça de portfólio
com deploy no ar.

Veja [`EXPLICACAO-DO-PROJETO.md`](./EXPLICACAO-DO-PROJETO.md) para entender
a lógica por trás de cada decisão (por que camadas, por que Postgres, etc).

## Requisitos do desafio

- Adicionar contato (Nome, Telefone, Email, Favorito)
- Listar contatos cadastrados
- Editar um contato existente
- Marcar/desmarcar um contato como favorito
- Listar contatos favoritos
- Deletar um contato

## Estrutura

```
app/
  models.py    # Contato (dataclass)
  storage.py   # acesso ao Postgres (psycopg2, SQL puro)
  services.py  # validação e regras de negócio
cli.py         # menu de terminal
tests/         # testes de services.py contra um Postgres real
```

## Rodando localmente

```bash
pip install -r requirements.txt
cp .env.example .env  # preencher DATABASE_URL com um Postgres real
python cli.py
```

## Testes

```bash
pytest tests/
```

## Status

Backend modularizado e validado. Frontend web (FastAPI) ainda não construído.
