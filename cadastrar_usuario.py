import os
import secrets
import sys

import httpx
from dotenv import load_dotenv

from app import services, storage

load_dotenv()

# Script de administrador, só o Julio roda: cadastra um email novo e já
# gera o token fixo dele num passo só. É assim que a gente mantém o
# acesso fechado — ninguém entra sozinho, só quem o admin liberar aqui
# primeiro, e o jeito de entrar já nasce sendo email + token (sem
# código por email, sem Resend, sem nada expirando sozinho).
# Uso: python cadastrar_usuario.py email@da-pessoa.com

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

_CABECALHOS_ADMIN = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}


def _buscar_usuario_id(email: str) -> str | None:
    resposta = httpx.get(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        params={"email": email},
        headers=_CABECALHOS_ADMIN,
        timeout=10,
    )
    usuarios = resposta.json().get("users", [])
    return usuarios[0]["id"] if usuarios else None


# Cria o usuário no Auth se ainda não existir (só pra ter um usuario_id
# de verdade pra amarrar os dados dela) — se já existir, só reaproveita.
def _garantir_usuario_id(email: str) -> str:
    usuario_id = _buscar_usuario_id(email)
    if usuario_id:
        return usuario_id

    resposta = httpx.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        json={"email": email, "email_confirm": True},
        headers=_CABECALHOS_ADMIN,
        timeout=10,
    )
    resposta.raise_for_status()
    return resposta.json()["id"]


def cadastrar_usuario(email: str) -> None:
    usuario_id = _garantir_usuario_id(email)

    token = secrets.token_urlsafe(32)
    conexao = storage.conectar()
    storage.criar_tabelas(conexao)
    storage.inserir_token_fixo(conexao, usuario_id, email, services.hash_token_fixo(token))
    conexao.close()

    print(f"{email} cadastrado. Token gerado — guarda esse valor, ele não aparece de novo:")
    print(token)
    print("Pra entrar: acesse /login e preenche email + esse token.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python cadastrar_usuario.py email@da-pessoa.com")
        sys.exit(1)
    cadastrar_usuario(sys.argv[1])
