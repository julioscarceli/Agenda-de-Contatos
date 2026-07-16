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

**Por que rodando no Zeabur e não no Supabase.com?**
Sua conta Supabase.com já tem um limite de 2 projetos gratuitos ocupado.
Só que existe uma segunda opção, que é o que este projeto usa: o
**Supabase self-hosted** — o mesmo software open-source do Supabase
(Postgres + Auth + Storage + Studio + API REST automática, tudo em
containers Docker) rodando dentro de um projeto Zeabur comum, sem nenhuma
relação com a conta Supabase.com e sem o limite de 2 projetos (esse limite
é só da versão gerenciada/paga). Fica tudo (app + banco + Studio) no mesmo
lugar, com a interface visual do Supabase Studio pra ver e editar os dados.

**Composição do stack** (12 serviços, todos no projeto Zeabur
`agenda-contatos`): `postgresql-gang` (o banco), `studio` (interface
visual), `meta` (conecta o Studio ao Postgres), `auth`, `rest`,
`realtime-dev`, `storage`, `supavisor` (pool de conexões), `kong` (gateway
que expõe tudo por HTTPS num domínio só), `minio`, `imgproxy`, `functions`.
Hoje só usamos o Postgres via `psycopg2` direto — Auth/Storage ficam
disponíveis prontos caso o projeto ganhe login de usuário ou upload de
arquivo no futuro.

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

## 6. A virada: de agenda simples pra CRM com dois pilares

Depois da primeira versão (só Contato, com um favorito sim/não), o objetivo
do projeto mudou: virar a base de um CRM real, inspirado em duas coisas —
o jeito como você usa o WhatsApp pra gerir clientes, e o
[SpeckFlow](https://speckflow.zeabur.app) (seu quadro de notas por voz).
Isso trouxe mudanças estruturais:

**Dois pilares, mesmo projeto.** `Contato` continua existindo, e ganhou um
companheiro: `Tarefa`. Uma tarefa pode viver solta (um lembrete qualquer)
ou grudada num contato específico (`contato_id`), tipo "ligar pro Cliente
X amanhã". Isso é o que transforma uma lista de contatos numa ferramenta
de gestão de relacionamento de verdade.

**Coluna: a etapa que o próprio usuário desenha.** Antes, "favorito" era
fixo (só sim ou não). Agora existe uma tabela `colunas`, onde cada usuário
cria as etapas que fazem sentido pra ele (ex: "Lead", "Negociando",
"Cliente" pros contatos; "Prioridade", "Lembretes" pras tarefas) — o
sistema só sugere um conjunto padrão pra não começar vazio
(`garantir_colunas_padrao` em `services.py`), mas o usuário manda de
verdade. Isso é o que vai virar, no frontend, um quadro Kanban de arrastar
e soltar.

**Nada se apaga de vez.** Apagar de verdade (`DELETE`) virou trocar o
campo `status` pra `"resolvido"` ou `"lixeira"` — igual ao Lixeira/Resolvidas
do SpeckFlow. Um contato ou tarefa "resolvido" some da tela principal, mas
continua no banco, recuperável.

**Nasceu o conceito de usuário.** Se cada pessoa tem suas próprias
colunas, o sistema precisa saber de quem é cada coisa. Por isso toda
tabela agora tem `usuario_id`, apontando pra tabela `auth.users` que o
Supabase self-hosted já gerencia sozinho — não criamos uma tabela de
usuário do zero, aproveitamos a que já veio pronta com o Auth. Como o
login de verdade é coisa de frontend (fica pro final), hoje existe um
único usuário de teste fixo (ver `USUARIO_ID_TESTE` no `.env`) que todo
mundo usa localmente.

**Voz como forma de entrada (peça pronta, ainda não conectada).** A
função `transcrever_audio` em `services.py` manda um áudio pro Whisper da
OpenAI e devolve o texto. Ela existe e funciona, mas ninguém chama ela
ainda — gravar áudio é interface (frontend/extensão), então essa parte só
vai ganhar uso quando chegarmos lá. É a mesma lógica de "construir a
fundação antes da parede decorativa".

---

## 7. Segurança aplicada (16/07/2026)

- **Chaves de demonstração rotacionadas**: o template do Supabase
  self-hosted sobe com `JWT_SECRET`/`ANON_KEY`/`SERVICE_ROLE_KEY` de
  demonstração, documentados publicamente pelo próprio Supabase — qualquer
  bot que conheça esse padrão comum acessaria o Studio/API. Foram
  substituídos por valores gerados aleatoriamente.
- **Postgres sem porta pública**: por padrão a porta 5432 não fica mais
  exposta na internet — só serviços dentro do mesmo projeto Zeabur
  conseguem acessar via rede interna. Pra dev local, reabilitar
  temporariamente (ver `README.md`).
- **Rate limiting e imagens atualizadas**: adiados por ora (rate limiting
  fica pro Cloudflare ou pra própria aplicação FastAPI mais pra frente;
  atualização de imagem vira revisão periódica, não ação única).

## 8. O que ainda falta (próximos passos combinados)

- [x] Backend modularizado, no ar no Zeabur, código no GitHub
- [x] Dois pilares (Contato + Tarefa), colunas personalizáveis, soft delete
      — 17 testes passando ponta a ponta (incluindo o `cli.py`)
- [x] Usuário de teste criado (via SQL direto, contornando uma
      instabilidade do container de Auth — ver pendência abaixo)
- [ ] Investigar por que o container `auth` do stack self-hosted fica
      instável/suspenso (possível limitação de recursos rodando 12
      containers no plano gratuito do Zeabur) — não bloqueia o trabalho
      atual porque falamos com o Postgres direto, mas vai bloquear login
      de verdade mais pra frente
- [ ] Conectar a transcrição de voz (`transcrever_audio`) a uma interface
      real — depende do frontend/extensão
- [ ] Decidir e construir o frontend (Kanban + voz), agora que o backend
      cobre os dois pilares
