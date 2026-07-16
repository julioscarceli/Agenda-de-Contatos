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

// --- Modal de adicionar ------------------------------------------------

const modal = document.getElementById("modal-adicionar");
const botaoAdicionar = document.getElementById("botao-adicionar");
const botaoCancelar = document.getElementById("botao-cancelar");

botaoAdicionar.addEventListener("click", () => modal.showModal());
botaoCancelar.addEventListener("click", () => modal.close());

// --- Captura de nota por voz ---------------------------------------------

const botaoGravar = document.getElementById("botao-gravar");
const campoTranscrito = document.getElementById("campo-transcrito");
const statusGravacao = document.getElementById("status-gravacao");

let gravador = null;
let pedacosDeAudio = [];
let gravando = false;

// Ao clicar, alterna entre "começar a gravar" e "parar e transcrever". O
// áudio gravado vai pro Whisper (rota /transcrever do backend), que
// devolve o texto e a gente preenche o campo sozinho — sem digitar nada.
botaoGravar.addEventListener("click", async () => {
  if (!gravando) {
    const streamDeAudio = await navigator.mediaDevices.getUserMedia({ audio: true });
    gravador = new MediaRecorder(streamDeAudio);
    pedacosDeAudio = [];

    gravador.ondataavailable = (evento) => pedacosDeAudio.push(evento.data);
    gravador.start();

    gravando = true;
    botaoGravar.classList.add("gravando");
    statusGravacao.textContent = "Gravando... clique de novo pra parar.";
    return;
  }

  gravador.addEventListener("stop", async () => {
    statusGravacao.textContent = "Transcrevendo...";

    const blobDeAudio = new Blob(pedacosDeAudio, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("audio", blobDeAudio, "nota.webm");

    const resposta = await fetch("/transcrever", { method: "POST", body: formData });
    const dados = await resposta.json();

    campoTranscrito.value = dados.texto;
    statusGravacao.textContent = "Pronto!";
  });

  gravador.stop();
  gravando = false;
  botaoGravar.classList.remove("gravando");
});
