import os

import httpx

# Fala com o Auth do Supabase self-hosted (o mesmo que já cuida do
# usuário de teste) pra fazer login sem senha: a pessoa digita o email,
# recebe um código de 6 dígitos por email (via Resend), e usa esse
# código pra entrar. Isso é o fluxo "OTP" que o Supabase Auth já traz
# pronto — a gente só chama as duas rotas dele, não guarda senha nenhuma.

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


class FalhaNoLogin(Exception):
    pass


# Pede pro Auth mandar o código de 6 dígitos pro email informado.
# create_user=False de propósito: acesso é só por convite — o admin
# cadastra o email antes (ver cadastrar_usuario.py), e só depois disso o
# código pode ser enviado. Email desconhecido nunca vira conta sozinho.
def enviar_codigo(email: str) -> None:
    resposta = httpx.post(
        f"{SUPABASE_URL}/auth/v1/otp",
        json={"email": email, "create_user": False},
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        timeout=10,
    )
    if resposta.status_code >= 400:
        raise FalhaNoLogin(
            "Esse email ainda não tem acesso liberado. Peça pro administrador cadastrar você primeiro."
        )


# Confere o código digitado. Se bater, o Auth devolve um token de acesso
# (JWT) que a gente guarda num cookie — é isso que prova, nas próximas
# requisições, quem é o usuário logado.
def verificar_codigo(email: str, codigo: str) -> dict:
    resposta = httpx.post(
        f"{SUPABASE_URL}/auth/v1/verify",
        json={"email": email, "token": codigo, "type": "email"},
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        timeout=10,
    )
    if resposta.status_code >= 400:
        raise FalhaNoLogin("Código inválido ou expirado. Tenta pedir um novo.")
    return resposta.json()


# O access_token que o Auth devolve só vale por 1 hora (de propósito,
# por segurança) — depois disso, em vez de pedir um código novo por
# email, a gente troca o refresh_token (que dura muito mais) por um
# access_token novo, por trás, sem a pessoa perceber nada.
def renovar_sessao(refresh_token: str) -> dict:
    resposta = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
        json={"refresh_token": refresh_token},
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        timeout=10,
    )
    if resposta.status_code >= 400:
        raise FalhaNoLogin("Sessão expirada, entra de novo.")
    return resposta.json()


# Usa o token guardado no cookie pra perguntar ao Auth "de quem é esse
# token, mesmo?" — é assim que a gente descobre o usuario_id de quem
# está navegando, em vez de usar o USUARIO_ID fixo de teste.
def obter_usuario(access_token: str) -> dict | None:
    resposta = httpx.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resposta.status_code >= 400:
        return None
    return resposta.json()
