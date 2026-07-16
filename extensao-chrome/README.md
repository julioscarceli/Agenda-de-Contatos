# CRM ao lado do WhatsApp — extensão (Nível 1)

Painel lateral do Chrome que abre o CRM (Contatos/Tarefas) automaticamente
quando você está no WhatsApp Web. Nesta fase, **não lê nada do WhatsApp** —
é só um posicionamento de janela conveniente, sem risco nenhum de conta.

## Como instalar (uso pessoal, sem loja)

1. Deixe o app rodando local: `uvicorn app.main:app` (veja o README
   principal do projeto).
2. Abra `chrome://extensions` no navegador.
3. Ative "Modo do desenvolvedor" (canto superior direito).
4. Clique em "Carregar sem compactação" e selecione esta pasta
   (`extensao-chrome`).
5. Abra `web.whatsapp.com` numa aba — o ícone da extensão na barra de
   ferramentas passa a abrir o painel lateral com o CRM.

## Próximos passos (Nível 2, ainda não construído)

- Content script lendo o cabeçalho da conversa aberta, pra já filtrar o
  CRM no contato certo automaticamente.
- Trocar a URL do `sidepanel.html` pelo domínio de produção, quando o app
  for implantado no Zeabur.
