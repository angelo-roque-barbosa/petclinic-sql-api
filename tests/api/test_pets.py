"""Testes de pets (tabela `pets`), com o banco como oráculo."""

from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import (
    COUNT_PETS,
    PREPARED_PET_TYPE_NAME,
    SECOND_PET_TYPE_NAME,
    SELECT_MAX_OWNER_ID,
    SELECT_OWNER_BY_ID,
)

# Pet padrão do docs/casos-de-teste.md: nome com letras, nascimento no passado. O tipo é o da fixture.
PET = {"name": "Rex", "birthDate": "2020-05-10"}

# Pergunta: qual é a linha de `pets` com o id que a API devolveu no POST?
# A consulta deve trazer, nesta ordem, name, birth_date, owner_id e type_id,
# e receber o id como parâmetro (%s).
SELECT_PET_BY_ID = """
SELECT name, birth_date, owner_id, type_id
FROM pets
WHERE id = %s;
"""


def test_criar_pet_com_dados_validos_grava_o_pet_ligado_ao_dono_e_ao_tipo(
    api, db, prepared_owner, prepared_pet_type, pets_to_delete
):
    """CT-API-PETS-01: criar um pet com dados válidos grava os dados enviados, ligado ao dono e ao tipo certos."""
    # Preparar: o dono e o tipo vêm das fixtures, gravados por SQL
    owner_id = prepared_owner
    type_id = prepared_pet_type
    payload = {**PET, "type": {"id": type_id, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /owners/{owner_id}/pets deveria responder 201, respondeu {response.status_code}"
    assert isinstance(body.get("id"), int), "a resposta deveria trazer o id numérico do pet criado"

    # Verificar o banco: nome e nascimento enviados, ligado ao dono e ao tipo da preparação
    row = db.execute(SELECT_PET_BY_ID, (body["id"],)).fetchone()
    expected = (PET["name"], date.fromisoformat(PET["birthDate"]), owner_id, type_id)
    assert row == expected, f"a linha do pet {body['id']} deveria ser {expected}, é {row}"


# Pergunta: quantos pets um dono tem hoje?
# Recebe o id do dono (%s) e devolve uma linha só, com um único valor: a quantidade de pets dele.
COUNT_PETS_BY_OWNER = """
SELECT COUNT(*) FROM pets WHERE owner_id = %s;
"""


@pytest.mark.parametrize("missing_field", ["name", "birthDate", "type"])
def test_criar_pet_sem_campo_obrigatorio_e_recusado_sem_gravar(
    api, db, prepared_owner, prepared_pet_type, pets_to_delete, missing_field
):
    """CT-API-PETS-02: criar um pet sem nome, sem data de nascimento ou sem tipo responde 400 apontando o
    campo e não grava pet para o dono."""
    # Preparar: o pet padrão sem o campo da vez; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    full_payload = {**PET, "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}
    payload = {field: value for field, value in full_payload.items() if field != missing_field}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo que faltou
    assert response.status_code == 400, f"POST de pet sem {missing_field} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {missing_field}, (
        f"o erro deveria apontar só {missing_field}, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o dono, criado sem pets, continua sem pets
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"


def test_criar_pet_com_nome_vazio_e_recusado_sem_gravar(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-03: criar um pet com nome vazio responde 400 apontando name e não grava pet para o dono.

    O nome só com espaços também deveria ser recusado, mas hoje é aceito: é o BUG-06, coberto pelo CT-BUG-06-01."""
    # Preparar: o pet padrão com o nome vazio; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    payload = {**PET, "name": "", "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o nome
    assert response.status_code == 400, f"POST de pet com nome vazio deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"name"}, (
        f"o erro deveria apontar só name, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o dono, criado sem pets, continua sem pets
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"


def test_criar_pet_com_nome_de_30_caracteres_grava_o_nome_inteiro(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-04: nome do pet com 30 caracteres, o limite do contrato, é aceito e gravado inteiro."""
    # Preparar: o pet padrão com o nome no limite; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    payload = {**PET, "name": "a" * 30, "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}
    assert len(payload["name"]) == 30, "o nome do teste deveria ter 30 caracteres"

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST de pet com nome de 30 caracteres deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com o nome de 30 caracteres sem corte
    row = db.execute(SELECT_PET_BY_ID, (body["id"],)).fetchone()
    expected = (payload["name"], date.fromisoformat(PET["birthDate"]), owner_id, prepared_pet_type)
    assert row == expected, f"a linha do pet {body['id']} deveria ser {expected}, é {row}"


def test_criar_pet_com_nome_de_31_caracteres_e_recusado_sem_gravar(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-04: nome do pet com 31 caracteres, um acima do limite, responde 400 e não grava pet."""
    # Preparar: o pet padrão com o nome acima do limite; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    payload = {**PET, "name": "a" * 31, "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}
    assert len(payload["name"]) == 31, "o nome do teste deveria ter 31 caracteres"

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o nome
    assert response.status_code == 400, f"POST de pet com nome de 31 caracteres deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"name"}, (
        f"o erro deveria apontar só name, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o dono, criado sem pets, continua sem pets
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"


def today_utc():
    """Hoje no fuso da API (UTC), calculado na hora do teste."""
    return datetime.now(timezone.utc).date()


def test_criar_pet_nascido_hoje_grava_a_data(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-05: um pet nascido hoje, o último dia permitido, é aceito e gravado com a data enviada."""
    # Preparar: o pet padrão nascido hoje, em UTC; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    birth = today_utc()
    payload = {**PET, "birthDate": birth.isoformat(), "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST de pet nascido hoje ({birth}) deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com a data de hoje
    row = db.execute(SELECT_PET_BY_ID, (body["id"],)).fetchone()
    expected = (PET["name"], birth, owner_id, prepared_pet_type)
    assert row == expected, f"a linha do pet {body['id']} deveria ser {expected}, é {row}"


@pytest.mark.parametrize(
    "birth",
    [
        pytest.param(lambda: today_utc() + timedelta(days=1), id="amanha"),
        pytest.param(lambda: date(2099, 1, 1), id="2099-01-01"),
    ],
)
def test_criar_pet_nascido_no_futuro_e_recusado_sem_gravar(api, db, prepared_owner, prepared_pet_type, pets_to_delete, birth):
    """CT-API-PETS-05: um pet nascido depois de hoje responde 400 apontando birthDate e não grava pet."""
    # Preparar: a data calculada na hora do teste (por isso o parâmetro é uma função), sempre depois de hoje
    owner_id = prepared_owner
    birth_date = birth()
    assert birth_date > today_utc(), "a data do teste deveria estar no futuro"
    payload = {**PET, "birthDate": birth_date.isoformat(), "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só a data
    assert response.status_code == 400, f"POST de pet nascido em {birth_date} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"birthDate"}, (
        f"o erro deveria apontar só birthDate, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o dono, criado sem pets, continua sem pets
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"


def fifty_years_ago_utc():
    """A data de exatamente 50 anos atrás, em UTC. Num 29 de fevereiro, volta para o 28, porque o ano de 50
    anos atrás pode não ser bissexto."""
    today = today_utc()
    try:
        return today.replace(year=today.year - 50)
    except ValueError:
        return today.replace(year=today.year - 50, day=28)


def test_criar_pet_com_exatamente_50_anos_grava_a_data(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-06: um pet com exatamente 50 anos, o limite da API, é aceito e gravado com a data enviada."""
    # Preparar: o pet padrão nascido há exatamente 50 anos, em UTC; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    birth = fifty_years_ago_utc()
    payload = {**PET, "birthDate": birth.isoformat(), "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST de pet nascido em {birth} deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com a data de 50 anos atrás
    row = db.execute(SELECT_PET_BY_ID, (body["id"],)).fetchone()
    expected = (PET["name"], birth, owner_id, prepared_pet_type)
    assert row == expected, f"a linha do pet {body['id']} deveria ser {expected}, é {row}"


@pytest.mark.parametrize(
    "birth",
    [
        pytest.param(lambda: fifty_years_ago_utc() - timedelta(days=1), id="50-anos-e-1-dia"),
        pytest.param(lambda: date(1800, 1, 1), id="1800-01-01"),
    ],
)
def test_criar_pet_com_mais_de_50_anos_e_recusado_sem_gravar(api, db, prepared_owner, prepared_pet_type, pets_to_delete, birth):
    """CT-API-PETS-06: um pet com mais de 50 anos responde 400 apontando birthDate e não grava pet."""
    # Preparar: a data calculada na hora do teste, sempre antes do limite de 50 anos
    owner_id = prepared_owner
    birth_date = birth()
    assert birth_date < fifty_years_ago_utc(), "a data do teste deveria ser anterior ao limite de 50 anos"
    payload = {**PET, "birthDate": birth_date.isoformat(), "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só a data
    assert response.status_code == 400, f"POST de pet nascido em {birth_date} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"birthDate"}, (
        f"o erro deveria apontar só birthDate, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o dono, criado sem pets, continua sem pets
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"


def test_criar_pet_para_dono_inexistente_responde_404_sem_gravar(api, db, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-08: criar um pet para um dono que não existe responde 404 e não grava pet nem cria o dono."""
    # Preparar: um id de dono que não existe, lido do banco na hora (o maior id + 1), e o total de pets antes
    missing_owner_id = db.execute(SELECT_MAX_OWNER_ID).fetchone()[0] + 1
    assert db.execute(SELECT_OWNER_BY_ID, (missing_owner_id,)).fetchone() is None, f"o dono {missing_owner_id} não deveria existir"
    pets_before = db.execute(COUNT_PETS).fetchone()[0]
    payload = {**PET, "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{missing_owner_id}/pets", json=payload)
    body = response.json() if response.content else {}
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 404, f"POST /owners/{missing_owner_id}/pets deveria responder 404, respondeu {response.status_code}"
    assert "birthDate" not in response.text, "a resposta não deveria trazer dados de pet"

    # Verificar o banco: nenhum pet para esse id, nenhum pet a mais e o dono continua sem existir
    assert db.execute(COUNT_PETS_BY_OWNER, (missing_owner_id,)).fetchone()[0] == 0, f"nenhum pet deveria apontar para o dono {missing_owner_id}"
    pets_after = db.execute(COUNT_PETS).fetchone()[0]
    assert pets_after == pets_before, f"o total de pets deveria continuar {pets_before}, ficou {pets_after}"
    assert db.execute(SELECT_OWNER_BY_ID, (missing_owner_id,)).fetchone() is None, f"o POST não deveria criar o dono {missing_owner_id}"


# Pergunta: qual é o maior id da tabela `types` hoje?
# Devolve uma linha só, com um único valor: o maior id.
SELECT_MAX_PET_TYPE_ID = """
SELECT MAX(id) FROM types;
"""


def test_criar_pet_com_tipo_inexistente_e_recusado_sem_gravar(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-09: criar um pet com um tipo que não existe responde 4xx e não grava pet nem cria o tipo.

    Hoje a resposta é 404, mas a recusa vem do banco, e não de uma validação da API: é a OBS-02."""
    # Preparar: um id de tipo que não existe, lido do banco na hora (o maior id + 1); o dono vem da fixture
    owner_id = prepared_owner
    max_type_before = db.execute(SELECT_MAX_PET_TYPE_ID).fetchone()[0]
    missing_type_id = max_type_before + 1
    payload = {**PET, "type": {"id": missing_type_id, "name": "fantasma"}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json() if response.content else {}
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: erro do cliente (o caso aceita 400 ou 404)
    assert response.status_code in (400, 404), f"POST de pet com tipo inexistente deveria responder 400 ou 404, respondeu {response.status_code}"

    # Verificar o banco: o dono continua sem pets, e nenhum tipo novo foi criado
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"
    max_type_after = db.execute(SELECT_MAX_PET_TYPE_ID).fetchone()[0]
    assert max_type_after == max_type_before, f"nenhum tipo deveria ser criado: o maior id era {max_type_before}, ficou {max_type_after}"


# Valores novos para o pet da fixture owner_with_pet: outro nome, outra data no passado e o segundo tipo.
UPDATED_PET = {"name": "Bidu", "birthDate": "2019-03-15"}


def test_atualizar_pet_com_dados_validos_grava_os_valores_e_mantem_o_dono(api, db, second_pet_type, owner_with_pet):
    """CT-API-PETS-10: atualizar um pet com dados válidos grava o novo nome, a nova data e o novo tipo, e o pet
    continua com o mesmo dono.

    O second_pet_type vem antes do owner_with_pet: depois do PUT o pet aponta para o segundo tipo, então o pet
    tem de ser apagado antes dele."""
    # Preparar: o pet, o dono e o primeiro tipo vêm da fixture; o segundo tipo, da second_pet_type
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    row_before = db.execute(SELECT_PET_BY_ID, (pet_id,)).fetchone()
    payload = {**UPDATED_PET, "type": {"id": second_pet_type, "name": SECOND_PET_TYPE_NAME}}
    assert (payload["name"], date.fromisoformat(payload["birthDate"]), second_pet_type) != (row_before[0], row_before[1], row_before[3]), (
        "os valores novos deveriam ser diferentes dos atuais"
    )

    # Agir
    response = api.put(f"/owners/{owner_id}/pets/{pet_id}", json=payload)

    # Verificar a resposta
    assert response.status_code == 204, f"PUT /owners/{owner_id}/pets/{pet_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: nome, data e tipo novos, e o mesmo dono de antes
    row = db.execute(SELECT_PET_BY_ID, (pet_id,)).fetchone()
    expected = (payload["name"], date.fromisoformat(payload["birthDate"]), row_before[2], second_pet_type)
    assert row == expected, f"a linha do pet {pet_id} deveria ser {expected}, é {row}"


def test_mover_pet_para_dono_inexistente_responde_404_sem_mudar_o_pet(api, db, owner_with_pet):
    """CT-API-PETS-11: o PUT de um pet pelo caminho de um dono que não existe responde 404 e deixa a linha do
    pet como estava, com o mesmo dono, sem gravar nem os outros campos do corpo."""
    # Preparar: o pet vem da fixture; a linha de antes, lida do banco, é o valor esperado
    pet_id = owner_with_pet["pet_id"]
    row_before = db.execute(SELECT_PET_BY_ID, (pet_id,)).fetchone()
    missing_owner_id = db.execute(SELECT_MAX_OWNER_ID).fetchone()[0] + 1
    assert db.execute(SELECT_OWNER_BY_ID, (missing_owner_id,)).fetchone() is None, f"o dono {missing_owner_id} não deveria existir"
    payload = {**UPDATED_PET, "type": {"id": owner_with_pet["type_id"], "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.put(f"/owners/{missing_owner_id}/pets/{pet_id}", json=payload)

    # Verificar a resposta
    assert response.status_code == 404, f"PUT /owners/{missing_owner_id}/pets/{pet_id} deveria responder 404, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira igual à de antes, e o dono inexistente continua sem existir
    row_after = db.execute(SELECT_PET_BY_ID, (pet_id,)).fetchone()
    assert row_after == row_before, f"a linha do pet {pet_id} deveria continuar {row_before}, ficou {row_after}"
    assert db.execute(SELECT_OWNER_BY_ID, (missing_owner_id,)).fetchone() is None, f"o PUT não deveria criar o dono {missing_owner_id}"


def test_apagar_pet_sem_visitas_remove_so_o_pet(api, db, owner_with_pet):
    """CT-API-PETS-12: apagar um pet sem visitas responde 204, remove só esse pet e mantém o dono."""
    # Preparar: o dono e o pet vêm da fixture; aqui só o total de pets antes
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    pets_before = db.execute(COUNT_PETS).fetchone()[0]

    # Agir
    response = api.delete(f"/pets/{pet_id}")

    # Verificar a resposta
    assert response.status_code == 204, f"DELETE /pets/{pet_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: o pet não existe mais, saiu exatamente um pet e o dono continua
    assert db.execute(SELECT_PET_BY_ID, (pet_id,)).fetchone() is None, f"o pet {pet_id} não deveria mais existir"
    pets_after = db.execute(COUNT_PETS).fetchone()[0]
    assert pets_after == pets_before - 1, f"o total de pets deveria cair para {pets_before - 1}, ficou {pets_after}"
    assert db.execute(SELECT_OWNER_BY_ID, (owner_id,)).fetchone() is not None, f"o dono {owner_id} deveria continuar no banco"
