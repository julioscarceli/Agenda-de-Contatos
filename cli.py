import os

from dotenv import load_dotenv

from app import services, storage
from app.services import ContatoInvalido, ContatoNaoEncontrado, TarefaInvalida, TarefaNaoEncontrada

load_dotenv()

# Enquanto não existe tela de login (isso é frontend, fica pro final), todo
# mundo que roda o CLI age como esse usuário de teste fixo.
USUARIO_ID = os.environ["USUARIO_ID_TESTE"]


# Monta um dicionário {id_da_coluna: nome_da_coluna} pra mostrar o nome da
# etapa em vez de um número solto quando listamos contato/tarefa.
def _mapa_de_colunas(conexao, pilar: str) -> dict:
    colunas = services.listar_colunas(conexao, USUARIO_ID, pilar)
    return {coluna.id: coluna.nome for coluna in colunas}


def exibir_contato(contato, nomes_coluna: dict) -> None:
    coluna = nomes_coluna.get(contato.coluna_id, "sem coluna")
    print(f"[{contato.id}] {contato.nome} - {contato.telefone} - {contato.email} ({coluna})")
    if contato.nota:
        print(f"      nota: {contato.nota}")


def exibir_tarefa(tarefa, nomes_coluna: dict) -> None:
    coluna = nomes_coluna.get(tarefa.coluna_id, "sem coluna")
    vinculo = f", contato #{tarefa.contato_id}" if tarefa.contato_id else ""
    print(f"[{tarefa.id}] {tarefa.titulo} ({coluna}){vinculo}")
    if tarefa.descricao:
        print(f"      {tarefa.descricao}")


# --- Pilar Contatos -------------------------------------------------------

def menu_contatos(conexao) -> None:
    colunas = services.garantir_colunas_padrao(conexao, USUARIO_ID, "contato")

    while True:
        print("\n--- Contatos ---")
        print("1. Adicionar contato")
        print("2. Listar contatos")
        print("3. Editar contato")
        print("4. Mover contato de coluna")
        print("5. Marcar contato como resolvido")
        print("6. Mover contato pra lixeira")
        print("7. Voltar")

        escolha = input("Escolha: ")

        try:
            if escolha == "1":
                nome = input("Nome: ")
                telefone = input("Telefone: ")
                email = input("Email: ")
                nota = input("Nota (opcional): ") or None
                contato = services.adicionar_contato(
                    conexao, USUARIO_ID, nome, telefone, email,
                    coluna_id=colunas[0].id, nota=nota,
                )
                print(f"Contato {contato.nome} adicionado na coluna '{colunas[0].nome}'.")

            elif escolha == "2":
                nomes_coluna = _mapa_de_colunas(conexao, "contato")
                contatos = services.listar_contatos(conexao, USUARIO_ID)
                if not contatos:
                    print("Nenhum contato cadastrado.")
                for contato in contatos:
                    exibir_contato(contato, nomes_coluna)

            elif escolha == "3":
                id_contato = int(input("ID do contato a editar: "))
                nome = input("Novo nome: ")
                telefone = input("Novo telefone: ")
                email = input("Novo email: ")
                nota = input("Nova nota (opcional): ") or None
                services.editar_contato(conexao, id_contato, nome, telefone, email, nota)
                print("Contato atualizado com sucesso!")

            elif escolha == "4":
                id_contato = int(input("ID do contato: "))
                print("Colunas disponíveis:", ", ".join(f"{c.id}={c.nome}" for c in colunas))
                id_coluna = int(input("Mover pra qual coluna (ID): "))
                services.mover_contato(conexao, id_contato, id_coluna)
                print("Contato movido de coluna.")

            elif escolha == "5":
                id_contato = int(input("ID do contato: "))
                services.resolver_contato(conexao, id_contato)
                print("Contato marcado como resolvido.")

            elif escolha == "6":
                id_contato = int(input("ID do contato: "))
                services.mover_contato_para_lixeira(conexao, id_contato)
                print("Contato movido pra lixeira.")

            elif escolha == "7":
                break

            else:
                print("Opção inválida.")

        except (ContatoInvalido, ContatoNaoEncontrado) as erro:
            print(f"Erro: {erro}")
        except ValueError:
            print("Erro: ID precisa ser um número.")


# --- Pilar Tarefas ---------------------------------------------------------

def menu_tarefas(conexao) -> None:
    colunas = services.garantir_colunas_padrao(conexao, USUARIO_ID, "tarefa")

    while True:
        print("\n--- Tarefas ---")
        print("1. Adicionar tarefa")
        print("2. Listar tarefas")
        print("3. Editar tarefa")
        print("4. Mover tarefa de coluna")
        print("5. Marcar tarefa como resolvida")
        print("6. Mover tarefa pra lixeira")
        print("7. Voltar")

        escolha = input("Escolha: ")

        try:
            if escolha == "1":
                titulo = input("Título: ")
                descricao = input("Descrição (opcional): ") or None
                contato_texto = input("Vincular a um contato? (ID ou vazio): ")
                contato_id = int(contato_texto) if contato_texto else None
                tarefa = services.adicionar_tarefa(
                    conexao, USUARIO_ID, titulo, descricao,
                    contato_id=contato_id, coluna_id=colunas[0].id,
                )
                print(f"Tarefa '{tarefa.titulo}' adicionada na coluna '{colunas[0].nome}'.")

            elif escolha == "2":
                nomes_coluna = _mapa_de_colunas(conexao, "tarefa")
                tarefas = services.listar_tarefas(conexao, USUARIO_ID)
                if not tarefas:
                    print("Nenhuma tarefa cadastrada.")
                for tarefa in tarefas:
                    exibir_tarefa(tarefa, nomes_coluna)

            elif escolha == "3":
                id_tarefa = int(input("ID da tarefa a editar: "))
                titulo = input("Novo título: ")
                descricao = input("Nova descrição (opcional): ") or None
                services.editar_tarefa(conexao, id_tarefa, titulo, descricao, prazo=None)
                print("Tarefa atualizada com sucesso!")

            elif escolha == "4":
                id_tarefa = int(input("ID da tarefa: "))
                print("Colunas disponíveis:", ", ".join(f"{c.id}={c.nome}" for c in colunas))
                id_coluna = int(input("Mover pra qual coluna (ID): "))
                services.mover_tarefa(conexao, id_tarefa, id_coluna)
                print("Tarefa movida de coluna.")

            elif escolha == "5":
                id_tarefa = int(input("ID da tarefa: "))
                services.resolver_tarefa(conexao, id_tarefa)
                print("Tarefa marcada como resolvida.")

            elif escolha == "6":
                id_tarefa = int(input("ID da tarefa: "))
                services.mover_tarefa_para_lixeira(conexao, id_tarefa)
                print("Tarefa movida pra lixeira.")

            elif escolha == "7":
                break

            else:
                print("Opção inválida.")

        except (TarefaInvalida, TarefaNaoEncontrada) as erro:
            print(f"Erro: {erro}")
        except ValueError:
            print("Erro: ID precisa ser um número.")


# --- Menu principal ---------------------------------------------------------

def menu(conexao) -> None:
    while True:
        print("\nAgenda de Contatos + Tarefas")
        print("1. Contatos")
        print("2. Tarefas")
        print("3. Sair")

        escolha = input("Escolha: ")

        if escolha == "1":
            menu_contatos(conexao)
        elif escolha == "2":
            menu_tarefas(conexao)
        elif escolha == "3":
            break
        else:
            print("Opção inválida.")

    print("Programa encerrado. Até logo!")


if __name__ == "__main__":
    conexao = storage.conectar()
    storage.criar_tabelas(conexao)
    try:
        menu(conexao)
    finally:
        conexao.close()
