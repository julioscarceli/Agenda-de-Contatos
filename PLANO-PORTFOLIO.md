# TalkFlow — Plano de ação pro portfólio

Checklist prático pra transformar o que já foi construído em uma peça de
portfólio forte — não é sobre adicionar mais features, é sobre **mostrar
bem** o que já existe.

---

## 1. README do GitHub (repo `Agenda-de-Contatos`)

- [ ] Trocar o nome de exibição pra **TalkFlow** no topo do README (o repo
      pode manter o nome técnico, mas o README já vende o produto certo)
- [ ] Adicionar 2-3 **GIFs curtos** mostrando, nessa ordem:
      1. Falar um comando de voz criando um contato (mic → card aparecendo)
      2. Arrastar um card entre colunas
      3. Clicar no ✎ pra completar telefone depois
- [ ] Adicionar o **link ao vivo** assim que o deploy terminar
- [ ] Seção "Por que esse projeto existe" contando a virada de rumo:
      desafio da Rocketseat → embrião de CRM — isso é uma boa história de
      "product thinking", não só código

## 2. Case study (post/artigo, estilo LinkedIn)

Contar a jornada em 4 atos, que é genuinamente interessante pra quem lê:

1. **O desafio original** — Agenda de Contatos, exercício de módulo 1
2. **A virada** — por que virou CRM (dor real: organizar clientes que
   vêm pelo WhatsApp)
3. **A decisão de design mais forte** — trocar formulário por comando de
   voz como interface principal, depois de testar e perceber que digitar
   telefone por voz era ruim (mostra iteração real, não só "código bonito")
4. **A arquitetura por trás** — camadas (models/storage/services),
   Postgres self-hosted, GPT interpretando intenção — sem precisar
   explicar tudo, só o suficiente pra mostrar que teve pensamento de
   arquitetura, não só "colei um CRUD"

## 3. Onde publicar

- [ ] GitHub (já feito, manter atualizado)
- [ ] Adicionar ao **Portfolio Pessoal** (projeto que já existe — conferir
      com o Obsidian/`contexto-projeto` o que esse projeto pessoal já tem
      de estrutura, pra encaixar o TalkFlow lá)
- [ ] LinkedIn (post de case study, seção 2)

## 4. O que destacar tecnicamente (pros recrutadores que olham código)

- Backend em camadas, testável (17 testes automatizados)
- Soft delete (nunca perde dado, sempre recuperável)
- Integração com IA de duas formas diferentes (Whisper pra transcrever,
  GPT pra interpretar intenção) — não é só "chamei uma API", é um
  pipeline de voz → texto → intenção → ação
- Banco Postgres self-hosted (não só "usei o Supabase gerenciado")
- Extensão de Chrome própria, com raciocínio de segurança explícito
  (por que ela não lê o WhatsApp ainda, por que isso importa)

## 5. Depois do deploy (pendente até o link ao vivo existir)

- [ ] Testar o link em aba anônima (garantir que funciona sem estado
      salvo do seu navegador)
- [ ] Confirmar que o login por email+token está funcionando antes de
      divulgar o link publicamente (senão qualquer um mexe nos seus dados
      de teste)

---

**Status:** rascunho gerado 17/07/2026, enquanto o deploy rodava. Revisar
com calma antes de publicar qualquer coisa.
