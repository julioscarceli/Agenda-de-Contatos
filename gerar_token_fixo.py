import os
import secrets
import sys

import httpx
from dotenv import load_dotenv

from app import services, storage

load_dotenv()

# Script de administrador, só o Julio roda: gera um link de entrada
# permanente pra um email já cadastrado (rodar cadastrar_usuario.py
# antes, se ainda não cadastrou). É menos seguro que o código por email
# — o token nunca expira sozinho — mas é bem mais prático: visita o
# link uma vez e nunca mais precisa pedir código de novo.
# Uso: python gerar_token_fixo.py email@da-pessoa.com

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
APP_URL = os.environ["APP_URL"]


def buscar_usuario_id(email: str) -> str | None:
    resposta = httpx.get(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        params={"email": email},
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        },
        timeout=10,
    )
    usuarios = resposta.json().get("users", [])
    return usuarios[0]["id"] if usuarios else None


def gerar_token_fixo(email: str) -> None:
    usuario_id = buscar_usuario_id(email)
    if usuario_id is None:
        print(f"{email} não está cadastrado — roda cadastrar_usuario.py primeiro.")
        return

    token = secrets.token_urlsafe(32)
    conexao = storage.conectar()
    storage.criar_tabelas(conexao)
    storage.inserir_token_fixo(conexao, usuario_id, services.hash_token_fixo(token))
    conexao.close()

    print("Token gerado — guarda esse link, ele não aparece de novo:")
    print(f"{APP_URL}/entrar-com-token?token={token}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python gerar_token_fixo.py email@da-pessoa.com")
        sys.exit(1)
    gerar_token_fixo(sys.argv[1])
