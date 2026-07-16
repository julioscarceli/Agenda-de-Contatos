// Esse script só faz sentido na página do quadro Kanban (tem microfone,
// drag-and-drop, modais). Na página de "Resolvidos" (lista simples) nada
// disso existe, então nem tenta rodar — evita erro no console por
// procurar um botão que não está ali.
if (document.querySelector(".quadro")) {

// Descobre se estamos no quadro de Contatos ou de Tarefas, pra saber em
// qual rota da API mandar as ações (/contatos/... ou /tarefas/...).
const pilar = document.querySelector("main").dataset.pilar;
const prefixoRota = pilar === "contato" ? "/contatos" : "/tarefas";

// --- Arrastar e soltar entre colunas ---------------------------------------

// Cada coluna vira uma "lista arrastável" independente. Quando um card cai
// numa lista diferente da que ele saiu, a gente avisa o backend pra mover
// o card de coluna de verdade no banco.
document.querySelectorAll(".lista-cards").forEach((lista) => {
  new Sortable(lista, {
    group: "cards",
    animation: 150,
    // Deixa mais fácil "acertar" a coluna: não precisa soltar exatamente
    // em cima de um card — chegar perto/na direção da coluna já basta.
    emptyInsertThreshold: 60,
    swapThreshold: 0.65,
    invertSwap: true,
    onEnd: (evento) => {
      const idItem = evento.item.dataset.itemId;
      const idColunaNova = evento.to.dataset.colunaId;

      fetch(`${prefixoRota}/${idItem}/mover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ coluna_id: Number(idColunaNova) }),
      });
    },
  });
});

// --- Comando de voz (jeito principal de criar contato/tarefa) --------------

const botaoComando = document.getElementById("botao-comando-voz");
const statusComando = document.getElementById("status-comando");

let gravadorDeComando = null;
let pedacosDoComando = [];
let gravandoComando = false;

// Um clique começa a gravar o comando falado; o próximo clique para e manda
// o áudio pro backend, que transcreve, interpreta a intenção e já cria o
// contato/tarefa sozinho. A página recarrega no final pra mostrar o card
// novo — simples e garante que tudo (colunas, contagens) fica consistente.
botaoComando.addEventListener("click", async () => {
  if (!gravandoComando) {
    const streamDeAudio = await navigator.mediaDevices.getUserMedia({ audio: true });
    gravadorDeComando = new MediaRecorder(streamDeAudio);
    pedacosDoComando = [];

    gravadorDeComando.ondataavailable = (evento) => pedacosDoComando.push(evento.data);
    gravadorDeComando.start();

    gravandoComando = true;
    botaoComando.classList.add("gravando");
    statusComando.textContent = "Ouvindo... clique de novo pra terminar.";
    return;
  }

  gravadorDeComando.addEventListener("stop", async () => {
    statusComando.textContent = "Transcrevendo e interpretando...";

    const blobDeAudio = new Blob(pedacosDoComando, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("audio", blobDeAudio, "comando.webm");

    try {
      const resposta = await fetch("/comando-de-voz", { method: "POST", body: formData });
      const dados = await resposta.json();

      if (!resposta.ok || dados.erro) {
        statusComando.textContent = dados.mensagem || "Não consegui entender o comando.";
        return;
      }

      statusComando.textContent = dados.mensagem;
      setTimeout(() => location.reload(), 900);
    } catch (erro) {
      statusComando.textContent = "Falha ao falar com o servidor. Tenta de novo.";
    }
  });

  gravadorDeComando.stop();
  gravandoComando = false;
  botaoComando.classList.remove("gravando");
});

// --- Editar um card existente (digitando) -----------------------------------

const modalEditar = document.getElementById("modal-editar");
const formEditar = document.getElementById("form-editar");

document.querySelectorAll(".acao-editar").forEach((botao) => {
  botao.addEventListener("click", () => {
    const card = botao.closest(".card");
    const idItem = card.dataset.itemId;
    formEditar.action = `${prefixoRota}/${idItem}/editar`;

    if (pilar === "contato") {
      document.getElementById("editar-nome").value = card.dataset.nome || "";
      document.getElementById("editar-telefone").value = card.dataset.telefone || "";
      document.getElementById("editar-email").value = card.dataset.email || "";
      document.getElementById("editar-nota").value = card.dataset.nota || "";
    } else {
      document.getElementById("editar-titulo").value = card.dataset.titulo || "";
      document.getElementById("editar-descricao").value = card.dataset.descricao || "";
    }

    modalEditar.showModal();
  });
});

document.getElementById("botao-cancelar-editar").addEventListener("click", () => modalEditar.close());

// --- Renomear ou criar uma fase (coluna) -----------------------------------

const modalColuna = document.getElementById("modal-coluna");
const formColuna = document.getElementById("form-coluna");
const inputNomeColuna = document.getElementById("input-nome-coluna");
const tituloModalColuna = document.getElementById("titulo-modal-coluna");

// O lápis pequeno ao lado do nome da coluna abre o mesmo modal de baixo,
// só que já preenchido com o nome atual e apontando pra rota de renomear.
document.querySelectorAll(".acao-editar-coluna").forEach((botao) => {
  botao.addEventListener("click", () => {
    formColuna.action = `/colunas/${botao.dataset.colunaId}/renomear`;
    tituloModalColuna.textContent = "Renomear fase";
    inputNomeColuna.value = botao.dataset.nome || "";
    modalColuna.showModal();
  });
});

// O "+ nova fase" no final do quadro abre o mesmo modal vazio, apontando
// pra rota de criar em vez de renomear.
document.getElementById("botao-nova-coluna").addEventListener("click", () => {
  formColuna.action = "/colunas";
  tituloModalColuna.textContent = "Nova fase";
  inputNomeColuna.value = "";
  modalColuna.showModal();
});

document.getElementById("botao-cancelar-coluna").addEventListener("click", () => modalColuna.close());

// --- Formulário manual (plano B) -------------------------------------------

const modalAdicionar = document.getElementById("modal-adicionar");
const linkAdicionarManual = document.getElementById("link-adicionar-manual");
const botaoCancelar = document.getElementById("botao-cancelar");

linkAdicionarManual.addEventListener("click", (evento) => {
  evento.preventDefault();
  modalAdicionar.showModal();
});
botaoCancelar.addEventListener("click", () => modalAdicionar.close());

}
