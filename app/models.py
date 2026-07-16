from dataclasses import dataclass


@dataclass
class Contato:
    nome: str
    telefone: str
    email: str
    favorito: bool = False
    id: int | None = None
