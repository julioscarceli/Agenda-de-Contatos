# Agenda de Contatos — Por que o projeto foi feito desse jeito

Este documento explica a **lógica por trás das decisões**, não só o que o código
faz. A ideia é que, lendo isso, você entenda o raciocínio mesmo sem estar
olhando o código ao mesmo tempo.

---

## 1. Por que separar tudo em camadas, em vez de um arquivo só?

No script do módulo (`gerenciador.py`, o de tarefas), tudo mora num arquivo só:
as funções e o menu que pergunta pro usuário o que fazer estão misturados.
Funciona para um exercício pequeno, mas cria um problema: se amanhã você
quiser transformar esse gerenciador numa API web, ou testar as funções sem
digitar nada no teclado, não dá — a lógica está grudada na parte que conversa
com o usuário.

Por isso a Agenda de Contatos foi dividida em **camadas**, cada uma com uma
responsabilidade única:

```
cli.py            → conversa com o usuário (menu, input, print)
app/services.py   → regras de negócio (validar, decidir o que é permitido)
app/storage.py    → conversa com o banco de dados (SQL puro)
app/models.py     → o "formato" de um Contato
```

**A regra por trás disso:** cada camada só conhece a camada de baixo, nunca a
de cima. `services.py` não sabe que existe um `input()` em algum lugar — ele
só recebe nome/telefone/email como texto e devolve um resultado. Isso quer
dizer que, quando a gente quiser adicionar a versão web (FastAPI) mais pra
frente, ela vai chamar exatamente as mesmas funções de `services.py` que o
CLI chama hoje — sem duplicar nada e sem reescrever regra de negócio.

**Analogia:** pensa num restaurante. O garçom (`cli.py`) anota o pedido e
entrega pro cliente. A cozinha (`services.py`) decide se o pedido faz
sentido (não dá pra pedir um prato que não existe) e manda pro estoque. O
estoque (`storage.py`) é só quem guarda e busca ingredientes, sem opinar
sobre nada. Se amanhã o restaurante abrir um totem de autoatendimento (a
versão web), a cozinha continua a mesma — só muda quem faz o pedido.

---

## 2. Por que Postgres (banco de dados de verdade) em vez de lista em memória?

O script original do módulo guarda tudo numa lista Python (`tarefas = []`).
Isso funciona enquanto o programa está rodando, mas **assim que você fecha o
terminal, tudo desaparece** — a lista vive só na memória RAM do processo.

Um banco de dados como o Postgres grava a informação em disco (ou em outro
servidor), então os contatos continuam lá mesmo depois que você fecha e abre
o programa de novo, ou mesmo que a aplicação rode em outro lugar (o
Zeabur, por exemplo).

**Por que Postgres especificamente, e não um arquivo `.json` ou SQLite?**
Porque a decisão que você tomou foi: sempre que o projeto envolver dado que
precisa "durar", usar banco de dados relacional de verdade — não arquivo
solto. Isso também é mais parecido com o que se usa em produção no mercado
(inclusive nos seus outros projetos, como o Automatik, que já usa Postgres
via Supabase).

**Por que rodando no Zeabur e não no Supabase?**
Sua conta Supabase já tem um limite de 2 projetos gratuitos ocupado. O
Zeabur também oferece um serviço de Postgres dentro do mesmo projeto onde a
aplicação vai rodar — sem esse limite de conta, e mantendo tudo (app +
banco) no mesmo lugar.

---

## 3. Por que a validação (nome vazio, email inválido) fica em `services.py` e não em `storage.py`?

`storage.py` só sabe conversar com o banco: inserir, buscar, atualizar,
deletar. Ele não deveria decidir se um e-mail é válido — essa é uma regra do
**negócio** (da Agenda de Contatos), não do banco de dados em si. Se um dia
você trocar o banco por outro (ou mockar ele num teste), a regra "email
precisa ter formato válido" continua valendo, porque ela não está amarrada a
nenhum banco específico.

Isso também evita duplicar validação: se no futuro a versão web também
adicionar contatos, ela reusa `services.adicionar_contato()`, que já valida
— não precisa reescrever a checagem de e-mail em outro lugar.

---

## 4. Por que cada função faz uma coisa só, sem classes com comportamento?

Você já decidiu, em outros projetos, seguir um **estilo funcional**: funções
que recebem dado, fazem uma coisa e devolvem resultado — em vez de objetos
que guardam estado e têm métodos. Por isso `Contato` é só um "molde de
dados" (`@dataclass`, sem métodos), e toda a lógica fica em funções soltas
dentro de `services.py` e `storage.py`.

**Vantagem prática:** cada função é fácil de testar isolada (dá pra chamar
`adicionar_contato(...)` num teste sem precisar simular o menu inteiro) — é
exatamente isso que os testes em `tests/test_services.py` fazem.

---

## 5. Como os dados fluem, do início ao fim

Exemplo: usuário escolhe "1. Adicionar contato" no menu.

1. `cli.py` pergunta nome/telefone/email com `input()`.
2. `cli.py` chama `services.adicionar_contato(conexao, nome, telefone, email)`.
3. `services.py` valida os dados. Se algo estiver errado, levanta um erro
   (`ContatoInvalido`) que o `cli.py` sabe capturar e mostrar uma mensagem
   amigável — sem o programa quebrar.
4. Se os dados estiverem OK, `services.py` chama
   `storage.inserir_contato(conexao, contato)`.
5. `storage.py` roda o `INSERT` no Postgres e devolve o `id` gerado pelo
   banco.
6. Esse `id` volta pro `Contato`, que volta pro `cli.py`, que mostra
   "Contato adicionado com sucesso!".

Cada seta desse fluxo é uma função chamando a de baixo — nunca pulando
camada (o `cli.py` nunca fala direto com o banco, por exemplo).

---

## 6. O que ainda falta (próximos passos combinados)

- [x] Provisionar o serviço de Postgres dentro do projeto Zeabur
      (`agenda-contatos`) e obter a `DATABASE_URL` real — feito via
      `zeabur template deploy` (template oficial PostgreSQL), sempre pelo
      CLI, nunca pelo dashboard
- [x] Rodar os testes (`pytest`) contra esse banco — 7 testes passando,
      backend validado ponta a ponta (incluindo o `cli.py`)
- [ ] Subir este código pro repositório do GitHub
      (`julioscarceli/Agenda-de-Contatos`, hoje vazio)
- [ ] Decidir e construir o frontend (web), agora que o backend está
      validado — combinado que isso viria depois da modularização
