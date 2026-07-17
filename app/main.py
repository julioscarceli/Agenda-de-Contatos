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


# Empresta uma conexão do pool pra cada requisição e devolve no final —
# bem mais rápido do que abrir uma conexão nova a cada clique, porque não
# paga o preço de rede/autenticação toda vez (isso ficava bem perceptível
# em dev local, com o banco do outro lado da internet no Zeabur).
def get_conexao():
    conexao = storage.obter_conexao()
    try:
        yield conexao
    finally:
        storage.devolver_conexao(conexao)


COOKIE_TOKEN_FIXO = "token_fixo"

# Só essa pessoa (o próprio Julio) enxerga a página /admin — o nome da
# variável é antigo (época do usuário de teste fixo), mas hoje é só o
# id do administrador de verdade.
ADMIN_USUARIO_ID = os.environ["USUARIO_ID_TESTE"]


# Sinaliza "essa pessoa não está logada" pra quem chamar a dependência
# abaixo — capturado pelo exception_handler logo depois, que manda todo
# mundo sem sessão válida de volta pra tela de login.
class NaoAutenticado(Exception):
    pass


# Dependência que toda rota protegida usa em vez do antigo USUARIO_ID
# fixo: lê o cookie do token, confere no nosso banco (nada de código por
# email, nada de Auth externo) e devolve o usuario_id de quem está
# navegando. Sem token válido, cai direto no login.
def usuario_id_atual(request: Request, conexao=Depends(get_conexao)) -> str:
    token = request.cookies.get(COOKIE_TOKEN_FIXO)
    usuario_id = storage.buscar_usuario_por_token_fixo(conexao, services.hash_token_fixo(token)) if token else None
    if usuario_id is None:
        raise NaoAutenticado()
    return usuario_id


# Trava extra só pra rotas de administração (/admin) — precisa estar
# logado E ser o administrador, não qualquer pessoa convidada.
def exigir_admin(usuario_id=Depends(usuario_id_atual)) -> str:
    if usuario_id != ADMIN_USUARIO_ID:
        raise NaoAutenticado()
    return usuario_id


# Roda uma vez, quando o servidor sobe: garante que as tabelas existem antes
# de qualquer requisição chegar.
@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    conexao = storage.obter_conexao()
    storage.criar_tabelas(conexao)
    storage.devolver_conexao(conexao)
    yield


app = FastAPI(lifespan=ciclo_de_vida)
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Qualquer rota que dependa de usuario_id_atual e não tenha sessão válida
# cai aqui — em vez de estourar erro 500, redireciona pro login.
@app.exception_handler(NaoAutenticado)
def redirecionar_para_login(request: Request, excecao: NaoAutenticado):
    return RedirectResponse("/login")


# O "corpo" que o JavaScript manda quando arrasta um card pra outra coluna —
# só o novo id da coluna, nada mais.
class MoverPayload(BaseModel):
    coluna_id: int


@app.get("/")
def raiz():
    return RedirectResponse("/contatos")


# --- Login por email + token fixo --------------------------------------
#
# Sem senha, sem código por email, sem depender de nenhum serviço externo:
# o admin cadastra a pessoa (cadastrar_usuario.py) e recebe um token — ela
# entra com email + esse token, igual usuário e senha. O token nunca
# expira sozinho; se precisar revogar, é só apagar a linha em
# tokens_fixos. Todas as rotas de Contatos/Tarefas/Colunas abaixo exigem
# essa sessão (usuario_id_atual).

@app.get("/login")
def pagina_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "erro": None})


@app.post("/login")
def entrar(
    request: Request, email: str = Form(...), token: str = Form(...), conexao=Depends(get_conexao)
):
    usuario_id = storage.buscar_usuario_por_token_fixo(conexao, services.hash_token_fixo(token), email)
    if usuario_id is None:
        return templates.TemplateResponse(
            "login.html", {"request": request, "erro": "Email ou token inválido."}
        )

    resposta = RedirectResponse("/contatos", status_code=303)
    resposta.set_cookie(
        COOKIE_TOKEN_FIXO, token,
        httponly=True, samesite="lax", secure=True, max_age=60 * 60 * 24 * 365 * 10,
    )
    return resposta


@app.get("/logout")
def logout():
    resposta = RedirectResponse("/login")
    resposta.delete_cookie(COOKIE_TOKEN_FIXO)
    return resposta


# --- Administração de acesso (só o admin vê) --------------------------------
#
# Substitui o script `cadastrar_usuario.py` rodado no terminal: a mesma
# lógica (services.criar_acesso_convidado), só que numa página — cola o
# email, clica, e o token aparece na tela pra copiar.

@app.get("/admin")
def pagina_admin(request: Request, conexao=Depends(get_conexao), usuario_id=Depends(exigir_admin)):
    usuarios = storage.listar_tokens_fixos(conexao)
    return templates.TemplateResponse(
        "admin.html", {"request": request, "usuarios": usuarios, "token_gerado": None, "email_gerado": None}
    )


@app.post("/admin/convidar")
def convidar_usuario(
    request: Request, email: str = Form(...), conexao=Depends(get_conexao), usuario_id=Depends(exigir_admin)
):
    token = services.criar_acesso_convidado(conexao, email)
    usuarios = storage.listar_tokens_fixos(conexao)
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "usuarios": usuarios, "token_gerado": token, "email_gerado": email},
    )


@app.post("/admin/{token_id}/revogar")
def revogar_usuario(token_id: int, conexao=Depends(get_conexao), usuario_id=Depends(exigir_admin)):
    storage.apagar_token_fixo(conexao, token_id)
    return RedirectResponse("/admin", status_code=303)


# Monta os dados de um quadro (Contatos ou Tarefas) pro template desenhar:
# as colunas do usuário e os cards já agrupados dentro de cada uma.
def _montar_quadro(request: Request, conexao, usuario_id: str, pilar: str):
    colunas = services.garantir_colunas_padrao(conexao, usuario_id, pilar)

    if pilar == "contato":
        itens = services.listar_contatos(conexao, usuario_id)
        contatos_para_vincular = None
    else:
        itens = services.listar_tarefas(conexao, usuario_id)
        contatos_para_vincular = services.listar_contatos(conexao, usuario_id)

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
            "eh_admin": usuario_id == ADMIN_USUARIO_ID,
        },
    )


@app.get("/contatos")
def pagina_contatos(request: Request, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    return _montar_quadro(request, conexao, usuario_id, "contato")


@app.get("/tarefas")
def pagina_tarefas(request: Request, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    return _montar_quadro(request, conexao, usuario_id, "tarefa")


# Vista simples (sem Kanban, sem arrastar) dos itens já resolvidos — eles
# nunca são apagados de verdade, só saem do quadro ativo. Aqui dá pra ver
# de novo, e "reabrir" se precisar voltar a mexer naquele contato/tarefa.
def _montar_resolvidos(request: Request, conexao, usuario_id: str, pilar: str):
    if pilar == "contato":
        itens = services.listar_contatos(conexao, usuario_id, status="resolvido")
    else:
        itens = services.listar_tarefas(conexao, usuario_id, status="resolvido")

    return templates.TemplateResponse(
        "resolvidos.html",
        {"request": request, "pilar": pilar, "itens": itens, "eh_admin": usuario_id == ADMIN_USUARIO_ID},
    )


@app.get("/contatos/resolvidos")
def pagina_contatos_resolvidos(request: Request, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    return _montar_resolvidos(request, conexao, usuario_id, "contato")


@app.get("/tarefas/resolvidas")
def pagina_tarefas_resolvidas(request: Request, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    return _montar_resolvidos(request, conexao, usuario_id, "tarefa")


# --- Ações de Coluna (fase) --------------------------------------------------

def _pagina_do_pilar(pilar: str) -> str:
    return "/contatos" if pilar == "contato" else "/tarefas"


# Renomear uma fase — chamado pelo lápis pequeno ao lado do nome da coluna.
@app.post("/colunas/{id_coluna}/renomear")
def renomear_coluna(
    id_coluna: int, nome: str = Form(...), pilar: str = Form(...),
    conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual),
):
    services.renomear_coluna(conexao, id_coluna, nome)
    return RedirectResponse(_pagina_do_pilar(pilar), status_code=303)


# Criar uma fase nova — chamado pelo "+ nova fase" no final do quadro.
@app.post("/colunas")
def criar_coluna(
    pilar: str = Form(...), nome: str = Form(...),
    conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual),
):
    services.criar_coluna(conexao, usuario_id, pilar, nome)
    return RedirectResponse(_pagina_do_pilar(pilar), status_code=303)


# --- Ações de Contato ------------------------------------------------------

# Cria um contato a partir do formulário manual (plano B).
@app.post("/contatos")
def criar_contato(
    nome: str = Form(...),
    telefone: str = Form(None),
    email: str = Form(None),
    nota: str = Form(None),
    coluna_id: int = Form(...),
    conexao=Depends(get_conexao),
    usuario_id=Depends(usuario_id_atual),
):
    services.adicionar_contato(
        conexao, usuario_id, nome, telefone or None, email or None,
        coluna_id=coluna_id, nota=nota or None,
    )
    return RedirectResponse("/contatos", status_code=303)


# Chamada pelo formulário de edição, que abre ao clicar num card — é aqui
# que telefone/email/nota (o que a voz não dita) são digitados.
@app.post("/contatos/{id_contato}/editar")
def editar_contato(
    id_contato: int,
    nome: str = Form(...),
    telefone: str = Form(None),
    email: str = Form(None),
    nota: str = Form(None),
    conexao=Depends(get_conexao),
    usuario_id=Depends(usuario_id_atual),
):
    services.editar_contato(
        conexao, id_contato, nome, usuario_id, telefone or None, email or None, nota or None
    )
    return RedirectResponse("/contatos", status_code=303)


# Chamada pelo JavaScript quando o usuário arrasta o card pra outra coluna.
@app.post("/contatos/{id_contato}/mover")
def mover_contato(
    id_contato: int, payload: MoverPayload,
    conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual),
):
    services.mover_contato(conexao, id_contato, payload.coluna_id, usuario_id)
    return {"ok": True}


@app.post("/contatos/{id_contato}/resolver")
def resolver_contato(id_contato: int, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    services.resolver_contato(conexao, id_contato, usuario_id)
    return RedirectResponse("/contatos", status_code=303)


@app.post("/contatos/{id_contato}/lixeira")
def contato_para_lixeira(id_contato: int, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    services.mover_contato_para_lixeira(conexao, id_contato, usuario_id)
    return RedirectResponse("/contatos", status_code=303)


# Chamada na vista de "Resolvidos" — volta o contato pro quadro ativo.
@app.post("/contatos/{id_contato}/reabrir")
def reabrir_contato(id_contato: int, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    services.reabrir_contato(conexao, id_contato, usuario_id)
    return RedirectResponse("/contatos/resolvidos", status_code=303)


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
    usuario_id=Depends(usuario_id_atual),
):
    services.adicionar_tarefa(
        conexao, usuario_id, titulo, _texto_ou_none(descricao),
        contato_id=contato_id, coluna_id=coluna_id,
    )
    return RedirectResponse("/tarefas", status_code=303)


# Edição por clique no card — diferente de Contato, aqui título e descrição
# também podem ser digitados de novo, já que na Tarefa a voz também dita
# tudo isso; é só uma forma alternativa de corrigir/completar.
@app.post("/tarefas/{id_tarefa}/editar")
def editar_tarefa(
    id_tarefa: int,
    titulo: str = Form(...),
    descricao: str = Form(None),
    conexao=Depends(get_conexao),
    usuario_id=Depends(usuario_id_atual),
):
    services.editar_tarefa(conexao, id_tarefa, titulo, _texto_ou_none(descricao), None, usuario_id)
    return RedirectResponse("/tarefas", status_code=303)


@app.post("/tarefas/{id_tarefa}/mover")
def mover_tarefa(
    id_tarefa: int, payload: MoverPayload,
    conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual),
):
    services.mover_tarefa(conexao, id_tarefa, payload.coluna_id, usuario_id)
    return {"ok": True}


@app.post("/tarefas/{id_tarefa}/resolver")
def resolver_tarefa(id_tarefa: int, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    services.resolver_tarefa(conexao, id_tarefa, usuario_id)
    return RedirectResponse("/tarefas", status_code=303)


@app.post("/tarefas/{id_tarefa}/lixeira")
def tarefa_para_lixeira(id_tarefa: int, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    services.mover_tarefa_para_lixeira(conexao, id_tarefa, usuario_id)
    return RedirectResponse("/tarefas", status_code=303)


# Chamada na vista de "Resolvidas" — volta a tarefa pro quadro ativo.
@app.post("/tarefas/{id_tarefa}/reabrir")
def reabrir_tarefa(id_tarefa: int, conexao=Depends(get_conexao), usuario_id=Depends(usuario_id_atual)):
    services.reabrir_tarefa(conexao, id_tarefa, usuario_id)
    return RedirectResponse("/tarefas/resolvidas", status_code=303)


# --- Voz -------------------------------------------------------------------

# Acha a coluna certa pelo nome que a pessoa falou (ex: "lead"), tentando
# um match exato primeiro e depois um match "parecido". Se não achar nada
# (ou a pessoa não mencionou coluna nenhuma), cai na primeira coluna —
# sempre cria em algum lugar, nunca falha por causa disso.
def _resolver_coluna_id(nome_mencionado: str | None, colunas: list) -> int:
    if nome_mencionado:
        alvo = nome_mencionado.strip().lower()
        for coluna in colunas:
            if coluna.nome.lower() == alvo:
                return coluna.id
        for coluna in colunas:
            if alvo in coluna.nome.lower() or coluna.nome.lower() in alvo:
                return coluna.id
    return colunas[0].id


# Acha o contato que a pessoa mencionou pra vincular a uma tarefa (ex:
# "pro Fulano"). Se não mencionou ninguém, ou não achou ninguém parecido,
# a tarefa simplesmente nasce solta — não é erro, é só "sem vínculo".
def _resolver_contato_id(nome_mencionado: str | None, contatos: list) -> int | None:
    if not nome_mencionado:
        return None
    alvo = nome_mencionado.strip().lower()
    for contato in contatos:
        if alvo in contato.nome.lower():
            return contato.id
    return None


# A rota principal do jeito novo de usar o sistema: recebe um áudio com um
# comando falado, transcreve, manda pro GPT entender a intenção, e já cria
# o Contato ou a Tarefa sozinho. Em Contato, só o nome é aproveitado da
# voz (telefone/email/nota ficam pra digitar depois, clicando no card); em
# Tarefa, título e descrição podem vir inteiros do que foi falado.
@app.post("/comando-de-voz")
async def comando_de_voz(
    audio: UploadFile = File(...),
    conexao=Depends(get_conexao),
    usuario_id=Depends(usuario_id_atual),
):
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as arquivo_temporario:
        arquivo_temporario.write(await audio.read())
        caminho = arquivo_temporario.name

    try:
        texto = services.transcrever_audio(caminho)
    finally:
        os.remove(caminho)

    colunas_contato = services.listar_colunas(conexao, usuario_id, "contato")
    colunas_tarefa = services.listar_colunas(conexao, usuario_id, "tarefa")
    contatos_existentes = services.listar_contatos(conexao, usuario_id)

    intencao = services.interpretar_comando_de_voz(
        texto,
        [coluna.nome for coluna in colunas_contato],
        [coluna.nome for coluna in colunas_tarefa],
        [contato.nome for contato in contatos_existentes],
    )

    try:
        if intencao.get("pilar") == "tarefa":
            coluna_id = _resolver_coluna_id(intencao.get("coluna_nome"), colunas_tarefa)
            contato_id = _resolver_contato_id(intencao.get("contato_nome"), contatos_existentes)
            tarefa = services.adicionar_tarefa(
                conexao, usuario_id, intencao.get("titulo") or texto,
                intencao.get("descricao"), contato_id=contato_id,
                coluna_id=coluna_id, origem="voz",
            )
            return {
                "texto_transcrito": texto,
                "mensagem": f"Tarefa \"{tarefa.titulo}\" criada.",
                "pilar": "tarefa",
            }

        coluna_id = _resolver_coluna_id(intencao.get("coluna_nome"), colunas_contato)
        contato = services.adicionar_contato(
            conexao, usuario_id, intencao.get("nome") or texto,
            coluna_id=coluna_id, origem="voz",
        )
        return {
            "texto_transcrito": texto,
            "mensagem": f"Contato {contato.nome} criado — clique no card pra completar telefone/email.",
            "pilar": "contato",
        }

    except (services.ContatoInvalido, services.TarefaInvalida) as erro:
        return {"texto_transcrito": texto, "mensagem": f"Não consegui criar: {erro}", "erro": True}
