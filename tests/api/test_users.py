"""Testes de usuários (tabelas `users` e `roles`), com o banco como oráculo.

A API só tem POST /api/users: o que o teste confere (ativo, papéis) só existe no banco, e a limpeza é feita
direto nele, pela fixture users_to_delete."""

# Usuário padrão: username que não existe no seed (só há `admin`), com até 20 caracteres, o limite do banco.
USER = {"username": "qaclara", "password": "Segredo123", "enabled": True, "roles": [{"name": "ROLE_OWNER_ADMIN"}]}

# Pergunta: qual é a linha de `users` com um username?
# Recebe o username (%s) e devolve uma linha com username e enabled, nesta ordem (sem a senha). Se o usuário não
# existir, não devolve linha.
SELECT_USER_BY_USERNAME = """
SELECT username, enabled FROM users WHERE username = %s;
"""

# Pergunta: quais papéis um usuário tem?
# Recebe o username (%s) e devolve uma linha por papel, com um valor só: o role, em ordem alfabética. Se o
# usuário não tiver papéis, não devolve linha.
SELECT_ROLES_BY_USERNAME = """
SELECT role FROM roles WHERE username = %s ORDER BY role ASC;
"""


def test_criar_usuario_com_papel_valido_grava_ativo_e_com_o_papel(api, db, users_to_delete):
    """CT-API-USERS-01: criar um usuário com o papel ROLE_OWNER_ADMIN responde 201, grava o usuário ativo e uma
    linha em `roles` com esse papel.

    A senha deveria ser gravada em hash (bcrypt), mas hoje fica em texto puro: é o BUG-18, coberto pelo
    CT-BUG-18-01."""
    # Preparar: o username é conhecido antes do POST, então já fica registrado para a limpeza
    payload = dict(USER)
    users_to_delete.append(payload["username"])

    # Agir
    response = api.post("/users", json=payload)

    # Verificar a resposta
    assert response.status_code == 201, f"POST /users deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: o usuário existe, ativo, e tem exatamente o papel enviado
    row = db.execute(SELECT_USER_BY_USERNAME, (payload["username"],)).fetchone()
    expected = (payload["username"], True)
    assert row == expected, f"a linha do usuário {payload['username']!r} deveria ser {expected}, é {row}"
    roles = db.execute(SELECT_ROLES_BY_USERNAME, (payload["username"],)).fetchall()
    assert roles == [("ROLE_OWNER_ADMIN",)], f"o usuário {payload['username']!r} deveria ter só ROLE_OWNER_ADMIN, tem {roles}"
