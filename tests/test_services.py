import pytest

from app import services

# Testa services, nunca storage diretamente — é em services que a regra de
# negócio vive. Cobre os dois pilares (Contato e Tarefa), colunas
# personalizáveis, e os fluxos de soft delete (resolver / lixeira).


# --- Colunas -----------------------------------------------------------

def test_garantir_colunas_padrao_cria_quando_nao_existe(conexao, usuario_id):
    colunas = services.garantir_colunas_padrao(conexao, usuario_id, "contato")

    assert [c.nome for c in colunas] == [nome for nome, _cor in services.COLUNAS_PADRAO_CONTATO]


def test_garantir_colunas_padrao_nao_duplica(conexao, usuario_id):
    primeira_chamada = services.garantir_colunas_padrao(conexao, usuario_id, "tarefa")
    segunda_chamada = services.garantir_colunas_padrao(conexao, usuario_id, "tarefa")

    assert len(primeira_chamada) == len(segunda_chamada) == len(services.COLUNAS_PADRAO_TAREFA)


# --- Contatos ------------------------------------------------------------

def test_adicionar_contato(conexao, usuario_id):
    contato = services.adicionar_contato(conexao, usuario_id, "Ana", "11999990000", "ana@email.com")

    assert contato.id is not None
    assert contato.status == "ativo"

    contatos = services.listar_contatos(conexao, usuario_id)
    assert len(contatos) == 1
    assert contatos[0].nome == "Ana"


def test_adicionar_contato_email_invalido(conexao, usuario_id):
    with pytest.raises(services.ContatoInvalido):
        services.adicionar_contato(conexao, usuario_id, "Ana", "11999990000", "email-invalido")


def test_editar_contato(conexao, usuario_id):
    contato = services.adicionar_contato(conexao, usuario_id, "Ana", "11999990000", "ana@email.com")

    editado = services.editar_contato(
        conexao, contato.id, "Ana Souza", usuario_id, "11988887777", "ana.souza@email.com", nota="ligar sexta"
    )

    assert editado.nome == "Ana Souza"
    assert editado.nota == "ligar sexta"


def test_editar_contato_inexistente(conexao, usuario_id):
    with pytest.raises(services.ContatoNaoEncontrado):
        services.editar_contato(conexao, 999, "Nome", usuario_id, "0000", "email@email.com")


def test_mover_contato_de_coluna(conexao, usuario_id):
    colunas = services.garantir_colunas_padrao(conexao, usuario_id, "contato")
    contato = services.adicionar_contato(
        conexao, usuario_id, "Ana", "11999990000", "ana@email.com", coluna_id=colunas[0].id
    )

    movido = services.mover_contato(conexao, contato.id, colunas[1].id, usuario_id)

    assert movido.coluna_id == colunas[1].id


def test_resolver_contato_some_da_listagem(conexao, usuario_id):
    contato = services.adicionar_contato(conexao, usuario_id, "Ana", "11999990000", "ana@email.com")

    services.resolver_contato(conexao, contato.id, usuario_id)

    assert services.listar_contatos(conexao, usuario_id) == []


def test_mover_contato_para_lixeira_some_da_listagem(conexao, usuario_id):
    contato = services.adicionar_contato(conexao, usuario_id, "Ana", "11999990000", "ana@email.com")

    services.mover_contato_para_lixeira(conexao, contato.id, usuario_id)

    assert services.listar_contatos(conexao, usuario_id) == []


def test_resolver_contato_inexistente(conexao, usuario_id):
    with pytest.raises(services.ContatoNaoEncontrado):
        services.resolver_contato(conexao, 999, usuario_id)


# --- Tarefas ------------------------------------------------------------

def test_adicionar_tarefa_solta(conexao, usuario_id):
    tarefa = services.adicionar_tarefa(conexao, usuario_id, "Ligar pro fornecedor")

    assert tarefa.id is not None
    assert tarefa.contato_id is None

    tarefas = services.listar_tarefas(conexao, usuario_id)
    assert len(tarefas) == 1


def test_adicionar_tarefa_vinculada_a_contato(conexao, usuario_id):
    contato = services.adicionar_contato(conexao, usuario_id, "Ana", "11999990000", "ana@email.com")

    tarefa = services.adicionar_tarefa(
        conexao, usuario_id, "Enviar orçamento", contato_id=contato.id
    )

    tarefas_do_contato = services.listar_tarefas(conexao, usuario_id, contato_id=contato.id)
    assert len(tarefas_do_contato) == 1
    assert tarefas_do_contato[0].id == tarefa.id


def test_adicionar_tarefa_titulo_vazio(conexao, usuario_id):
    with pytest.raises(services.TarefaInvalida):
        services.adicionar_tarefa(conexao, usuario_id, "   ")


def test_mover_tarefa_de_coluna(conexao, usuario_id):
    colunas = services.garantir_colunas_padrao(conexao, usuario_id, "tarefa")
    tarefa = services.adicionar_tarefa(
        conexao, usuario_id, "Ligar pro fornecedor", coluna_id=colunas[0].id
    )

    movida = services.mover_tarefa(conexao, tarefa.id, colunas[1].id, usuario_id)

    assert movida.coluna_id == colunas[1].id


def test_resolver_tarefa_some_da_listagem(conexao, usuario_id):
    tarefa = services.adicionar_tarefa(conexao, usuario_id, "Ligar pro fornecedor")

    services.resolver_tarefa(conexao, tarefa.id, usuario_id)

    assert services.listar_tarefas(conexao, usuario_id) == []


def test_mover_tarefa_para_lixeira_some_da_listagem(conexao, usuario_id):
    tarefa = services.adicionar_tarefa(conexao, usuario_id, "Ligar pro fornecedor")

    services.mover_tarefa_para_lixeira(conexao, tarefa.id, usuario_id)

    assert services.listar_tarefas(conexao, usuario_id) == []


def test_editar_tarefa_inexistente(conexao, usuario_id):
    with pytest.raises(services.TarefaNaoEncontrada):
        services.editar_tarefa(conexao, 999, "Novo título", None, None, usuario_id)
