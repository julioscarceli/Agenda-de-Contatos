import os
import tempfile
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import auth_cliente, services, storage

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


COOKIE_SESSAO = "sessao"
COOKIE_REFRESH = "sessao_refresh"
COOKIE_TOKEN_FIXO = "token_fixo"


# Sinaliza "essa pessoa não está logada" pra quem chamar a dependência
# abaixo — capturado pelo exception_handler logo depois, que manda todo
# mundo sem sessão válida de volta pra tela de login.
class NaoAutenticado(Exception):
    pass


# Grava os dois cookies de sessão (o token de 1 hora e o de renovação) —
# usado tanto no login quanto toda vez que a gente renova por trás.
def _gravar_cookies_sessao(resposta, resultado: dict) -> None:
    resposta.set_cookie(
        COOKIE_SESSAO, resultado["access_token"],
        httponly=True, samesite="lax", secure=True, max_age=60 * 60 * 24 * 30,
    )
    resposta.set_cookie(
        COOKIE_REFRESH, resultado["refresh_token"],
        httponly=True, samesite="lax", secure=True, max_age=60 * 60 * 24 * 30,
    )


# Dependência que toda rota protegida usa em vez do antigo USUARIO_ID
# fixo. Duas formas de provar quem é a pessoa, nessa ordem:
# 1. Cookie de token fixo (gerado por gerar_token_fixo.py) — checa
#    direto no nosso banco, sem depender do Auth.
# 2. Cookie de sessão normal (do login por email+código) — pergunta ao
#    Auth de quem é aquele token; se o de 1 hora já expirou, tenta
#    renovar por trás com o refresh_token antes de desistir.
# Só cai no login se nenhuma das duas funcionar.
def usuario_id_atual(request: Request, response: Response, conexao=Depends(get_conexao)) -> str:
    token_fixo = request.cookies.get(COOKIE_TOKEN_FIXO)
    if token_fixo:
        usuario_id = storage.buscar_usuario_por_token_fixo(
            conexao, services.hash_token_fixo(token_fixo)
        )
        if usuario_id:
            return usuario_id

    token = request.cookies.get(COOKIE_SESSAO)
    usuario = auth_cliente.obter_usuario(token) if token else None

    if usuario is None:
        refresh_token = request.cookies.get(COOKIE_REFRESH)
        if not refresh_token:
            raise NaoAutenticado()
        try:
            resultado = auth_cliente.renovar_sessao(refresh_token)
        except auth_cliente.FalhaNoLogin:
            raise NaoAutenticado()
        usuario = auth_cliente.obter_usuario(resultado["access_token"])
        if usuario is None:
            raise NaoAutenticado()
        _gravar_cookies_sessao(response, resultado)
        return usuario["id"]

    return usuario["id"]


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


# --- Login sem senha (email + código) ---------------------------------------
#
# A pessoa digita o email, recebe um código de 6 dígitos (via Resend) e usa
# esse código pra entrar — sem senha nenhuma. Todas as rotas de Contatos/
# Tarefas/Colunas abaixo exigem essa sessão (usuario_id_atual).

@app.get("/login")
def pagina_login(request: Request):
    return templates.TemplateResponse(
        "login.html", {"request": request, "erro": None, "email": None, "codigo_enviado": False}
    )


# Chamada via JavaScript (fetch), não recarrega a página — só pede pro Auth
# mandar o código, e devolve um JSON simples pro front saber se deu certo.
# Só manda código pra email que o admin já cadastrou antes (ver
# cadastrar_usuario.py); email desconhecido cai no "erro".
@app.post("/login/enviar-codigo")
def enviar_codigo_login(email: str = Form(...)):
    try:
        auth_cliente.enviar_codigo(email)
    except auth_cliente.FalhaNoLogin as erro:
        return {"ok": False, "erro": str(erro)}
    return {"ok": True}


@app.post("/login/verificar")
def verificar_codigo_login(request: Request, email: str = Form(...), codigo: str = Form(...)):
    try:
        resultado = auth_cliente.verificar_codigo(email, codigo)
    except auth_cliente.FalhaNoLogin as erro:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": str(erro), "email": email, "codigo_enviado": True},
        )

    resposta = RedirectResponse("/contatos", status_code=303)
    _gravar_cookies_sessao(resposta, resultado)
    return resposta


@app.get("/logout")
def logout():
    resposta = RedirectResponse("/login")
    resposta.delete_cookie(COOKIE_SESSAO)
    resposta.delete_cookie(COOKIE_REFRESH)
    resposta.delete_cookie(COOKIE_TOKEN_FIXO)
    return resposta


# Link de entrada direta, gerado por gerar_token_fixo.py — visitar essa
# URL uma vez grava um cookie que dura anos, sem nunca mais pedir código
# por email. É menos seguro que o código (o token nunca expira sozinho),
# então só o admin gera isso pra quem realmente precisa da praticidade.
@app.get("/entrar-com-token")
def entrar_com_token(token: str, conexao=Depends(get_conexao)):
    usuario_id = storage.buscar_usuario_por_token_fixo(conexao, services.hash_token_fixo(token))
    if usuario_id is None:
        return RedirectResponse("/login")

    resposta = RedirectResponse("/contatos", status_code=303)
    resposta.set_cookie(
        COOKIE_TOKEN_FIXO, token,
        httponly=True, samesite="lax", secure=True, max_age=60 * 60 * 24 * 365 * 10,
    )
    return resposta


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
        {"request": request, "pilar": pilar, "itens": itens},
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
