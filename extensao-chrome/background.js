// Nível 1 da integração: o painel lateral só fica disponível quando a aba
// ativa é o WhatsApp Web. Em qualquer outro site, ele some — não é um
// painel genérico, é "o CRM do lado do WhatsApp".
const URL_WHATSAPP = "https://web.whatsapp.com";

async function atualizarPainelLateral(tabId, url) {
  const estaNoWhatsApp = Boolean(url && url.startsWith(URL_WHATSAPP));
  try {
    await chrome.sidePanel.setOptions({
      tabId,
      path: "sidepanel.html",
      enabled: estaNoWhatsApp,
    });
  } catch (erro) {
    // Acontece se a aba já foi fechada antes da gente conseguir atualizar
    // — inofensivo, só ignora.
  }
}

// Dispara toda vez que uma aba termina de carregar (ex: você navega até
// o WhatsApp Web) ou quando você troca de aba pra uma que já estava aberta.
chrome.tabs.onUpdated.addListener((tabId, mudanca, aba) => {
  if (mudanca.status === "complete") {
    atualizarPainelLateral(tabId, aba.url);
  }
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  const aba = await chrome.tabs.get(tabId);
  atualizarPainelLateral(tabId, aba.url);
});

// O Chrome não deixa a extensão abrir o painel sozinha — só decide se ele
// fica disponível. Abrir de fato sempre precisa de um clique seu. Esse
// clique no ícone da barra de ferramentas conta como esse clique, e abre
// o painel direto, sem menu no meio.
chrome.action.onClicked.addListener(async (aba) => {
  await chrome.sidePanel.open({ tabId: aba.id });
});
