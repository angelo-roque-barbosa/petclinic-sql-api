"""Testes de usuários (tabelas `users` e `roles`), com o banco como oráculo.

A API só tem POST /api/users: o que o teste confere (ativo, papéis) só existe no banco, e a limpeza é feita
direto nele, pela fixture users_to_delete."""

import pytest

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


# Pergunta: quantos usuários existem hoje?
# Devolve uma linha só, com um único valor: o total de linhas de `users`.
COUNT_USERS = """
SELECT COUNT(*) FROM users;
"""


@pytest.mark.parametrize(
    "username",
    [
        pytest.param(None, id="sem-username"),
        pytest.param("", id="username-vazio"),
    ],
)
def test_criar_usuario_sem_username_e_recusado_sem_gravar(api, db, users_to_delete, username):
    """CT-API-USERS-02: criar um usuário sem username ou com username vazio responde 400 apontando o campo
    `username` e não grava usuário nenhum.

    Username só com espaços também deveria ser recusado, mas hoje é aceito: é o BUG-19, coberto pelo
    CT-BUG-19-01."""
    # Preparar: o usuário padrão sem o campo (None) ou com ele vazio; um username enviado fica registrado para a
    # limpeza, caso a API o grave
    payload = dict(USER)
    if username is None:
        del payload["username"]
    else:
        payload["username"] = username
        users_to_delete.append(username)
    users_before = db.execute(COUNT_USERS).fetchone()[0]

    # Agir
    response = api.post("/users", json=payload)
    body = response.json()

    # Verificar a resposta: 400, e o erro aponta só o campo username
    assert response.status_code == 400, f"POST /users com username {username!r} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"username"}, (
        f"o erro deveria apontar só username, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o total de usuários não muda
    users_after = db.execute(COUNT_USERS).fetchone()[0]
    assert users_after == users_before, f"o total de usuários deveria continuar {users_before}, ficou {users_after}"


def test_criar_usuario_com_username_de_20_caracteres_grava_inteiro(api, db, users_to_delete):
    """CT-API-USERS-03: um username com 20 caracteres, o limite do banco (`varchar(20)`), é aceito com 201 e
    gravado inteiro."""
    # Preparar: o username padrão completado até 20 caracteres, registrado para a limpeza antes do POST
    username = USER["username"].ljust(20, "a")
    assert len(username) == 20, f"o username do teste deveria ter 20 caracteres, tem {len(username)}"
    payload = {**USER, "username": username}
    users_to_delete.append(username)

    # Agir
    response = api.post("/users", json=payload)

    # Verificar a resposta
    assert response.status_code == 201, f"POST /users com username de 20 caracteres deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: o username gravado é o enviado, sem corte, e o usuário está ativo
    row = db.execute(SELECT_USER_BY_USERNAME, (username,)).fetchone()
    expected = (username, True)
    assert row == expected, f"a linha do usuário deveria ser {expected}, é {row}"


def test_criar_usuario_com_username_de_81_caracteres_e_recusado_sem_gravar(api, db, users_to_delete):
    """CT-API-USERS-03: um username com 81 caracteres, acima do limite do contrato, responde 400 apontando o
    campo `username` e não grava usuário nenhum.

    De 21 a 80 caracteres a resposta deveria ser a mesma, mas hoje é 404, porque quem recusa é o banco: é o
    BUG-20, coberto pelo CT-BUG-20-01."""
    # Preparar
    username = USER["username"].ljust(81, "a")
    assert len(username) == 81, f"o username do teste deveria ter 81 caracteres, tem {len(username)}"
    payload = {**USER, "username": username}
    users_to_delete.append(username)
    users_before = db.execute(COUNT_USERS).fetchone()[0]

    # Agir
    response = api.post("/users", json=payload)
    body = response.json()

    # Verificar a resposta: 400, e o erro aponta só o campo username
    assert response.status_code == 400, f"POST /users com username de 81 caracteres deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"username"}, (
        f"o erro deveria apontar só username, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o total de usuários não muda
    users_after = db.execute(COUNT_USERS).fetchone()[0]
    assert users_after == users_before, f"o total de usuários deveria continuar {users_before}, ficou {users_after}"
