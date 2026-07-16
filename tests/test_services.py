import pytest

from app import services


def test_adicionar_contato(conexao):
    contato = services.adicionar_contato(conexao, "Ana", "11999990000", "ana@email.com")

    assert contato.id is not None
    assert contato.favorito is False

    contatos = services.listar_contatos(conexao)
    assert len(contatos) == 1
    assert contatos[0].nome == "Ana"


def test_adicionar_contato_email_invalido(conexao):
    with pytest.raises(services.ContatoInvalido):
        services.adicionar_contato(conexao, "Ana", "11999990000", "email-invalido")


def test_editar_contato(conexao):
    contato = services.adicionar_contato(conexao, "Ana", "11999990000", "ana@email.com")

    editado = services.editar_contato(
        conexao, contato.id, "Ana Souza", "11988887777", "ana.souza@email.com"
    )

    assert editado.nome == "Ana Souza"
    assert editado.telefone == "11988887777"


def test_editar_contato_inexistente(conexao):
    with pytest.raises(services.ContatoNaoEncontrado):
        services.editar_contato(conexao, 999, "Nome", "0000", "email@email.com")


def test_alternar_favorito(conexao):
    contato = services.adicionar_contato(conexao, "Ana", "11999990000", "ana@email.com")

    marcado = services.alternar_favorito(conexao, contato.id)
    assert marcado.favorito is True

    favoritos = services.listar_favoritos(conexao)
    assert len(favoritos) == 1

    desmarcado = services.alternar_favorito(conexao, contato.id)
    assert desmarcado.favorito is False
    assert services.listar_favoritos(conexao) == []


def test_deletar_contato(conexao):
    contato = services.adicionar_contato(conexao, "Ana", "11999990000", "ana@email.com")

    services.deletar_contato(conexao, contato.id)

    assert services.listar_contatos(conexao) == []


def test_deletar_contato_inexistente(conexao):
    with pytest.raises(services.ContatoNaoEncontrado):
        services.deletar_contato(conexao, 999)
