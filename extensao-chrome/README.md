# CRM ao lado do WhatsApp — extensão (Nível 1)

Painel lateral do Chrome que mostra o CRM (Contatos/Tarefas) ao lado do
WhatsApp Web. Nesta fase, **não lê nada do WhatsApp** — é só um
posicionamento de janela conveniente, sem risco nenhum de conta.

**Importante:** o Chrome não deixa nenhuma extensão abrir o painel sozinha
— isso é uma trava de segurança da própria API, não uma limitação nossa.
Ele fica *disponível* automaticamente quando você está no WhatsApp Web,
mas abrir de fato sempre precisa de **um clique no ícone da extensão** na
barra de ferramentas (não precisa passar por nenhum menu, o clique já
abre direto).

## Como instalar (uso pessoal, sem loja)

1. Deixe o app rodando local: `uvicorn app.main:app` (veja o README
   principal do projeto).
2. Abra `chrome://extensions` no navegador.
3. Ative "Modo do desenvolvedor" (canto superior direito).
4. Clique em "Carregar sem compactação" e selecione esta pasta
   (`extensao-chrome`).
5. Abra `web.whatsapp.com` numa aba e clique no ícone da extensão na
   barra de ferramentas — o painel lateral abre com o CRM.

Depois de qualquer mudança nos arquivos da extensão, clique no ícone de
"recarregar" do card dela em `chrome://extensions` (recarregar a página
do WhatsApp não é suficiente — a extensão em si precisa recarregar).

## Próximos passos (Nível 2, ainda não construído)

- Content script lendo o cabeçalho da conversa aberta, pra já filtrar o
  CRM no contato certo automaticamente.
- Trocar a URL do `sidepanel.html` pelo domínio de produção, quando o app
  for implantado no Zeabur.
