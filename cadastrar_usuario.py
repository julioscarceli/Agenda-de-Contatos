import sys

from dotenv import load_dotenv

from app import services, storage

load_dotenv()

# Script de administrador — mesma coisa que a página /admin faz, só que
# no terminal. Deixa aqui como plano B (se a página não estiver
# acessível por algum motivo), mas o normal agora é usar /admin direto
# no site. Uso: python cadastrar_usuario.py email@da-pessoa.com

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python cadastrar_usuario.py email@da-pessoa.com")
        sys.exit(1)

    email = sys.argv[1]
    conexao = storage.conectar()
    storage.criar_tabelas(conexao)
    token = services.criar_acesso_convidado(conexao, email)
    conexao.close()

    print(f"{email} cadastrado. Token gerado — guarda esse valor, ele não aparece de novo:")
    print(token)
