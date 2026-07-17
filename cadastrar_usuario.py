import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

# Script de administrador, só o Julio roda: cadastra um email novo direto no
# Auth (sem mandar nada por email ainda), pra essa pessoa passar a poder
# pedir o código de login. É assim que a gente mantém o acesso fechado —
# ninguém entra sozinho, só quem o admin liberar aqui primeiro.
# Uso: python cadastrar_usuario.py email@da-pessoa.com

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def cadastrar_usuario(email: str) -> None:
    resposta = httpx.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        json={"email": email, "email_confirm": True},
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    if resposta.status_code >= 400:
        print(f"Erro ao cadastrar {email}: {resposta.status_code} {resposta.text}")
        return
    print(f"{email} cadastrado — já pode pedir o código de login em /login.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python cadastrar_usuario.py email@da-pessoa.com")
        sys.exit(1)
    cadastrar_usuario(sys.argv[1])
