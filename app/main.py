import os
import tempfile
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import services, storage

load_dotenv()

# Enquanto não existe tela de login, todo mundo que usa o site age como
# esse usuário de teste fixo — igual o cli.py já fazia.
USUARIO_ID = os.environ["USUARIO_ID_TESTE"]


# Roda uma vez, quando o servidor sobe: garante que as tabelas existem antes
# de qualquer requisição chegar. É o equivalente do "criar_tabelas" que o
# cli.py chamava no início do __main__.
@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    conexao = storage.conectar()
    storage.criar_tabelas(conexao)
    conexao.close()
    yield


app = FastAPI(lifespan=ciclo_de_vida)
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Abre uma conexão nova pra cada requisição e garante que ela fecha no
# final, mesmo se a rota der erro no meio do caminho.
def get_conexao():
    conexao = storage.conectar()
    try:
        yield conexao
    finally:
        conexao.close()


# O "corpo" que o JavaScript manda quando arrasta um card pra outra coluna —
# só o novo id da coluna, nada mais.
class MoverPayload(BaseModel):
    coluna_id: int


@app.get("/")
def raiz():
    return RedirectResponse("/contatos")


# Monta os dados de um quadro (Contatos ou Tarefas) pro template desenhar:
# as colunas do usuário e os cards já agrupados dentro de cada uma.
def _montar_quadro(request: Request, conexao, pilar: str):
    colunas = services.garantir_colunas_padrao(conexao, USUARIO_ID, pilar)

    if pilar == "contato":
        itens = services.listar_contatos(conexao, USUARIO_ID)
        contatos_para_vincular = None
    else:
        itens = services.listar_tarefas(conexao, USUARIO_ID)
        contatos_para_vincular = services.listar_contatos(conexao, USUARIO_ID)

    itens_por_coluna = {coluna.id: [] for coluna in colunas}
    for item in itens:
        itens_por_coluna.setdefault(item.coluna_id, []).append(item)

    return templates.TemplateResponse(
        "quadro.html",
        {
            "request": request,
            "pilar": pilar,
            "colunas": colunas,
            "itens_por_coluna": itens_por_coluna,
            "contatos": contatos_para_vincular,
        },
    )


@app.get("/contatos")
def pagina_contatos(request: Request, conexao=Depends(get_conexao)):
    return _montar_quadro(request, conexao, "contato")


@app.get("/tarefas")
def pagina_tarefas(request: Request, conexao=Depends(get_conexao)):
    return _montar_quadro(request, conexao, "tarefa")


# --- Ações de Contato ------------------------------------------------------

# Cria um contato a partir do formulário do modal "+" do quadro.
@app.post("/contatos")
def criar_contato(
    nome: str = Form(...),
    telefone: str = Form(...),
    email: str = Form(...),
    nota: str = Form(None),
    coluna_id: int = Form(...),
    conexao=Depends(get_conexao),
):
    services.adicionar_contato(
        conexao, USUARIO_ID, nome, telefone, email, coluna_id=coluna_id, nota=nota or None
    )
    return RedirectResponse("/contatos", status_code=303)


# Chamada pelo JavaScript quando o usuário arrasta o card pra outra coluna.
@app.post("/contatos/{id_contato}/mover")
def mover_contato(id_contato: int, payload: MoverPayload, conexao=Depends(get_conexao)):
    services.mover_contato(conexao, id_contato, payload.coluna_id)
    return {"ok": True}


@app.post("/contatos/{id_contato}/resolver")
def resolver_contato(id_contato: int, conexao=Depends(get_conexao)):
    services.resolver_contato(conexao, id_contato)
    return RedirectResponse("/contatos", status_code=303)


@app.post("/contatos/{id_contato}/lixeira")
def contato_para_lixeira(id_contato: int, conexao=Depends(get_conexao)):
    services.mover_contato_para_lixeira(conexao, id_contato)
    return RedirectResponse("/contatos", status_code=303)


# --- Ações de Tarefa --------------------------------------------------------

def _texto_ou_none(valor: str | None) -> str | None:
    return valor if valor else None


# Cria uma tarefa — pode vir com contato_id vazio (tarefa solta) ou
# preenchido (o dropdown do modal manda o id do contato escolhido).
@app.post("/tarefas")
def criar_tarefa(
    titulo: str = Form(...),
    descricao: str = Form(None),
    coluna_id: int = Form(...),
    contato_id: int = Form(None),
    conexao=Depends(get_conexao),
):
    services.adicionar_tarefa(
        conexao, USUARIO_ID, titulo, _texto_ou_none(descricao),
        contato_id=contato_id, coluna_id=coluna_id,
    )
    return RedirectResponse("/tarefas", status_code=303)


@app.post("/tarefas/{id_tarefa}/mover")
def mover_tarefa(id_tarefa: int, payload: MoverPayload, conexao=Depends(get_conexao)):
    services.mover_tarefa(conexao, id_tarefa, payload.coluna_id)
    return {"ok": True}


@app.post("/tarefas/{id_tarefa}/resolver")
def resolver_tarefa(id_tarefa: int, conexao=Depends(get_conexao)):
    services.resolver_tarefa(conexao, id_tarefa)
    return RedirectResponse("/tarefas", status_code=303)


@app.post("/tarefas/{id_tarefa}/lixeira")
def tarefa_para_lixeira(id_tarefa: int, conexao=Depends(get_conexao)):
    services.mover_tarefa_para_lixeira(conexao, id_tarefa)
    return RedirectResponse("/tarefas", status_code=303)


# --- Voz -------------------------------------------------------------------

# Recebe o áudio gravado no navegador (via MediaRecorder), salva num
# arquivo temporário só pra passar pro Whisper, e devolve o texto
# transcrito — o JavaScript usa isso pra preencher o campo de texto do
# modal sozinho, sem o usuário digitar nada.
@app.post("/transcrever")
async def transcrever(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as arquivo_temporario:
        arquivo_temporario.write(await audio.read())
        caminho = arquivo_temporario.name

    try:
        texto = services.transcrever_audio(caminho)
    finally:
        os.remove(caminho)

    return {"texto": texto}
