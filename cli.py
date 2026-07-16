from dotenv import load_dotenv

from app import services, storage
from app.services import ContatoInvalido, ContatoNaoEncontrado

load_dotenv()


def exibir_contato(contato) -> None:
    favorito = "⭐" if contato.favorito else " "
    print(f"[{contato.id}] {favorito} {contato.nome} - {contato.telefone} - {contato.email}")


def menu(conexao) -> None:
    while True:
        print("\nMenu da Agenda de Contatos:")
        print("1. Adicionar contato")
        print("2. Listar contatos")
        print("3. Editar contato")
        print("4. Marcar/desmarcar favorito")
        print("5. Listar favoritos")
        print("6. Deletar contato")
        print("7. Sair")

        escolha = input("Digite a sua escolha: ")

        try:
            if escolha == "1":
                nome = input("Nome: ")
                telefone = input("Telefone: ")
                email = input("Email: ")
                contato = services.adicionar_contato(conexao, nome, telefone, email)
                print(f"Contato {contato.nome} adicionado com sucesso!")

            elif escolha == "2":
                contatos = services.listar_contatos(conexao)
                if not contatos:
                    print("Nenhum contato cadastrado.")
                for contato in contatos:
                    exibir_contato(contato)

            elif escolha == "3":
                id_contato = int(input("ID do contato a editar: "))
                nome = input("Novo nome: ")
                telefone = input("Novo telefone: ")
                email = input("Novo email: ")
                services.editar_contato(conexao, id_contato, nome, telefone, email)
                print("Contato atualizado com sucesso!")

            elif escolha == "4":
                id_contato = int(input("ID do contato: "))
                contato = services.alternar_favorito(conexao, id_contato)
                estado = "marcado como favorito" if contato.favorito else "removido dos favoritos"
                print(f"Contato {contato.nome} {estado}.")

            elif escolha == "5":
                favoritos = services.listar_favoritos(conexao)
                if not favoritos:
                    print("Nenhum contato favorito.")
                for contato in favoritos:
                    exibir_contato(contato)

            elif escolha == "6":
                id_contato = int(input("ID do contato a deletar: "))
                services.deletar_contato(conexao, id_contato)
                print("Contato deletado com sucesso!")

            elif escolha == "7":
                break

            else:
                print("Opção inválida.")

        except (ContatoInvalido, ContatoNaoEncontrado) as erro:
            print(f"Erro: {erro}")
        except ValueError:
            print("Erro: ID precisa ser um número.")

    print("Programa encerrado. Até logo!")


if __name__ == "__main__":
    conexao = storage.conectar()
    storage.criar_tabela(conexao)
    try:
        menu(conexao)
    finally:
        conexao.close()
