"""Testes de donos (tabela `owners`), com o banco como oráculo."""

import re

import pytest

# Dono padrão do docs/casos-de-teste.md: nome e sobrenome só com letras, telefone com 10 dígitos.
OWNER = {
    "firstName": "Clara",
    "lastName": "Lima",
    "address": "Rua do Sol, 30",
    "city": "Olinda",
    "telephone": "8199990002",
}

# Pergunta: qual é a linha de `owners` com o id que a API devolveu no POST?
# A consulta deve trazer, nesta ordem, first_name, last_name, address, city e telephone,
# e receber o id como parâmetro (%s), sem montar o texto da consulta com o valor.
SELECT_OWNER_BY_ID = """ 
SELECT first_name, last_name, address, city, telephone FROM owners WHERE id = %s;
  """

def test_criar_dono_com_dados_validos_grava_os_dados_enviados(api, db, owners_to_delete):
    """CT-API-OWNERS-01: criar um dono com dados válidos grava no banco exatamente os dados enviados."""
    # Agir
    response = api.post("/owners", json=OWNER)
    body = response.json()
    # Registra o dono na limpeza antes de qualquer verificação: se uma delas falhar, ele é apagado mesmo assim
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /owners deveria responder 201, respondeu {response.status_code}"
    assert isinstance(body.get("id"), int), "a resposta deveria trazer o id numérico do dono criado"
    assert {field: body[field] for field in OWNER} == OWNER, "a resposta deveria trazer os campos enviados"

    # Verificar o banco: o esperado vem do que foi enviado, não da resposta da API
    row = db.execute(SELECT_OWNER_BY_ID, (body["id"],)).fetchone()
    assert row is not None, f"o banco deveria ter uma linha em owners com id {body['id']}"
    expected = (OWNER["firstName"], OWNER["lastName"], OWNER["address"], OWNER["city"], OWNER["telephone"])
    assert row == expected, f"a linha gravada deveria ser {expected}, é {row}"


# Pergunta: quantas linhas existem hoje na tabela `owners`?
# A consulta deve devolver uma linha só, com um único valor: o total de donos.
COUNT_OWNERS = """
SELECT COUNT(*) FROM owners; 
"""

@pytest.mark.parametrize("missing_field", ["firstName", "lastName", "address", "city", "telephone"])
def test_criar_dono_sem_campo_obrigatorio_e_recusado_sem_gravar(api, db, owners_to_delete, missing_field):
    """CT-API-OWNERS-02: criar um dono sem um dos campos obrigatórios responde 400 e não grava dono parcial."""
    # Preparar: o dono padrão sem o campo da vez, e o total de donos antes
    payload = {field: value for field, value in OWNER.items() if field != missing_field}
    count_before = db.execute(COUNT_OWNERS).fetchone()[0]

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    # Se a API criar o dono por engano, ele é apagado no fim
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo que faltou
    assert response.status_code == 400, f"POST /owners sem {missing_field} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {missing_field}, (
        f"o erro deveria apontar só {missing_field}, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: nenhum dono novo
    count_after = db.execute(COUNT_OWNERS).fetchone()[0]
    assert count_after == count_before, f"o total de donos deveria continuar {count_before}, ficou {count_after}"


def test_criar_dono_com_telefone_de_10_digitos_grava_o_telefone(api, db, owners_to_delete):
    """CT-API-OWNERS-03: telefone com exatamente 10 dígitos, o limite do contrato, é aceito e gravado igual."""
    # Preparar: o dono padrão com o telefone no limite
    payload = {**OWNER, "telephone": "8199990002"}
    assert payload["telephone"].isdigit() and len(payload["telephone"]) == 10, "o telefone do teste deveria ter 10 dígitos"

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /owners com 10 dígitos deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com o telefone enviado
    row = db.execute(SELECT_OWNER_BY_ID, (body["id"],)).fetchone()
    expected = (payload["firstName"], payload["lastName"], payload["address"], payload["city"], payload["telephone"])
    assert row == expected, f"a linha gravada deveria ser {expected}, é {row}"


@pytest.mark.parametrize(
    "telephone",
    [pytest.param("819999000", id="9-digitos"), pytest.param("81999900021", id="11-digitos")],
)
def test_criar_dono_com_telefone_fora_do_limite_e_recusado_sem_gravar(api, db, owners_to_delete, telephone):
    """CT-API-OWNERS-03: telefone com 9 ou 11 dígitos responde 400 apontando telephone e não grava dono."""
    # Preparar: o dono padrão com o telefone fora do limite, e o total de donos antes
    payload = {**OWNER, "telephone": telephone}
    assert telephone.isdigit() and len(telephone) != 10, "o telefone do teste deveria ter só dígitos, mas não 10"
    count_before = db.execute(COUNT_OWNERS).fetchone()[0]

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o telefone
    assert response.status_code == 400, f"POST /owners com {len(telephone)} dígitos deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"telephone"}, (
        f"o erro deveria apontar só telephone, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: nenhum dono novo
    count_after = db.execute(COUNT_OWNERS).fetchone()[0]
    assert count_after == count_before, f"o total de donos deveria continuar {count_before}, ficou {count_after}"


@pytest.mark.parametrize(
    "telephone",
    [
        pytest.param("abc", id="letras"),
        pytest.param("60855510ab", id="10-caracteres-com-letras"),
        pytest.param("608 555 10", id="10-caracteres-com-espacos"),
        pytest.param("", id="vazio"),
    ],
)
def test_criar_dono_com_telefone_fora_do_formato_e_recusado_sem_gravar(api, db, owners_to_delete, telephone):
    """CT-API-OWNERS-04: telefone que não é só dígitos, ou vazio, responde 400 apontando telephone e não grava dono."""
    # Preparar: o dono padrão com o telefone fora do formato, e o total de donos antes
    payload = {**OWNER, "telephone": telephone}
    assert not re.fullmatch(r"[0-9]{10}", telephone), "o telefone do teste não deveria ser um telefone válido"
    count_before = db.execute(COUNT_OWNERS).fetchone()[0]

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o telefone
    assert response.status_code == 400, f"POST /owners com telefone {telephone!r} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"telephone"}, (
        f"o erro deveria apontar só telephone, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: nenhum dono novo
    count_after = db.execute(COUNT_OWNERS).fetchone()[0]
    assert count_after == count_before, f"o total de donos deveria continuar {count_before}, ficou {count_after}"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("firstName", "", id="firstName-vazio"),
        pytest.param("firstName", "   ", id="firstName-so-espacos"),
        pytest.param("lastName", "", id="lastName-vazio"),
        pytest.param("lastName", "   ", id="lastName-so-espacos"),
    ],
)
def test_criar_dono_com_nome_sem_conteudo_e_recusado_sem_gravar(api, db, owners_to_delete, field, value):
    """CT-API-OWNERS-05: nome ou sobrenome vazio ou só com espaços responde 400 apontando o campo e não grava dono."""
    # Preparar: o dono padrão com o campo sem conteúdo, e o total de donos antes
    payload = {**OWNER, field: value}
    assert value.strip() == "", "o valor do teste deveria estar vazio ou ter só espaços"
    count_before = db.execute(COUNT_OWNERS).fetchone()[0]

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo alterado
    assert response.status_code == 400, f"POST /owners com {field}={value!r} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {field}, (
        f"o erro deveria apontar só {field}, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: nenhum dono novo
    count_after = db.execute(COUNT_OWNERS).fetchone()[0]
    assert count_after == count_before, f"o total de donos deveria continuar {count_before}, ficou {count_after}"


@pytest.mark.parametrize("field", ["firstName", "lastName"])
def test_criar_dono_com_nome_de_30_letras_grava_o_nome_inteiro(api, db, owners_to_delete, field):
    """CT-API-OWNERS-06: nome ou sobrenome com 30 letras, o limite do contrato, é aceito e gravado inteiro."""
    # Preparar: o dono padrão com o campo no limite
    payload = {**OWNER, field: "a" * 30}
    assert re.fullmatch(r"[a-z]{30}", payload[field]), "o valor do teste deveria ter 30 letras"

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /owners com {field} de 30 letras deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com o valor de 30 letras sem corte
    row = db.execute(SELECT_OWNER_BY_ID, (body["id"],)).fetchone()
    expected = (payload["firstName"], payload["lastName"], payload["address"], payload["city"], payload["telephone"])
    assert row == expected, f"a linha gravada deveria ser {expected}, é {row}"


@pytest.mark.parametrize("field", ["firstName", "lastName"])
def test_criar_dono_com_nome_de_31_letras_e_recusado_sem_gravar(api, db, owners_to_delete, field):
    """CT-API-OWNERS-06: nome ou sobrenome com 31 letras, um acima do limite, responde 400 e não grava dono."""
    # Preparar: o dono padrão com o campo acima do limite, e o total de donos antes
    payload = {**OWNER, field: "a" * 31}
    assert re.fullmatch(r"[a-z]{31}", payload[field]), "o valor do teste deveria ter 31 letras"
    count_before = db.execute(COUNT_OWNERS).fetchone()[0]

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo alterado
    assert response.status_code == 400, f"POST /owners com {field} de 31 letras deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {field}, (
        f"o erro deveria apontar só {field}, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: nenhum dono novo
    count_after = db.execute(COUNT_OWNERS).fetchone()[0]
    assert count_after == count_before, f"o total de donos deveria continuar {count_before}, ficou {count_after}"


# Valores novos para todos os campos do dono preparado pela fixture owner_with_pet.
UPDATED_OWNER = {
    "firstName": "Rafaela",
    "lastName": "Souza Lima",
    "address": "Avenida Boa Viagem, 1000",
    "city": "Olinda",
    "telephone": "8133334444",
}

# Pergunta: qual é o dono (owner_id) do pet com um id?
# Recebe o id do pet (%s) e devolve uma linha com um valor só: o owner_id.
SELECT_PET_OWNER_ID = """
SELECT owner_id FROM pets WHERE id = %s;
"""


def test_atualizar_dono_com_dados_validos_grava_na_mesma_linha_e_mantem_o_pet(api, db, owner_with_pet):
    """CT-API-OWNERS-07: atualizar um dono com dados válidos grava os novos valores na mesma linha,
    sem criar outro dono nem mexer no pet dele."""
    # Preparar: o dono e o pet vêm da fixture, gravados por SQL; aqui só o total de donos antes
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    count_before = db.execute(COUNT_OWNERS).fetchone()[0]

    # Agir
    response = api.put(f"/owners/{owner_id}", json=UPDATED_OWNER)

    # Verificar a resposta
    assert response.status_code == 204, f"PUT /owners/{owner_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: os valores novos na mesma linha, nenhum dono a mais e o pet com o mesmo dono
    row = db.execute(SELECT_OWNER_BY_ID, (owner_id,)).fetchone()
    expected = (
        UPDATED_OWNER["firstName"], UPDATED_OWNER["lastName"], UPDATED_OWNER["address"],
        UPDATED_OWNER["city"], UPDATED_OWNER["telephone"],
    )
    assert row == expected, f"a linha do dono {owner_id} deveria ser {expected}, é {row}"
    count_after = db.execute(COUNT_OWNERS).fetchone()[0]
    assert count_after == count_before, f"o total de donos deveria continuar {count_before}, ficou {count_after}"
    pet_owner = db.execute(SELECT_PET_OWNER_ID, (pet_id,)).fetchone()
    assert pet_owner == (owner_id,), f"o pet {pet_id} deveria continuar com o dono {owner_id}, está com {pet_owner}"


@pytest.mark.parametrize(
    "telephone",
    [pytest.param("abc", id="letras"), pytest.param("81999900021", id="11-digitos")],
)
def test_atualizar_dono_com_telefone_invalido_e_recusado_sem_mudar_a_linha(api, db, owner_with_pet, telephone):
    """CT-API-OWNERS-08: atualizar um dono com telefone inválido responde 400 e deixa a linha como estava,
    sem gravar nem os outros campos do corpo."""
    # Preparar: o dono vem da fixture; a linha de antes, lida do banco, é o valor esperado
    owner_id = owner_with_pet["owner_id"]
    row_before = db.execute(SELECT_OWNER_BY_ID, (owner_id,)).fetchone()
    payload = {**UPDATED_OWNER, "telephone": telephone}
    assert not re.fullmatch(r"[0-9]{10}", telephone), "o telefone do teste não deveria ser um telefone válido"

    # Agir
    response = api.put(f"/owners/{owner_id}", json=payload)

    # Verificar a resposta: 400, e o erro aponta só o telefone
    assert response.status_code == 400, f"PUT /owners/{owner_id} com telefone {telephone!r} deveria responder 400, respondeu {response.status_code}"
    errors = response.json().get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"telephone"}, (
        f"o erro deveria apontar só telephone, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: a linha inteira igual à de antes, nem o telefone nem os outros campos mudaram
    row_after = db.execute(SELECT_OWNER_BY_ID, (owner_id,)).fetchone()
    assert row_after == row_before, f"a linha do dono {owner_id} deveria continuar {row_before}, ficou {row_after}"


def test_apagar_dono_sem_pets_remove_a_linha(api, db, prepared_owner):
    """CT-API-OWNERS-09: apagar um dono sem pets responde 204 e remove só a linha dele."""
    # Preparar: o dono vem da fixture, gravado por SQL; aqui só o total de donos antes
    owner_id = prepared_owner
    count_before = db.execute(COUNT_OWNERS).fetchone()[0]

    # Agir
    response = api.delete(f"/owners/{owner_id}")

    # Verificar a resposta
    assert response.status_code == 204, f"DELETE /owners/{owner_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: a linha do dono não existe mais, e saiu exatamente um dono
    row = db.execute(SELECT_OWNER_BY_ID, (owner_id,)).fetchone()
    assert row is None, f"o dono {owner_id} não deveria mais existir no banco, mas existe: {row}"
    count_after = db.execute(COUNT_OWNERS).fetchone()[0]
    assert count_after == count_before - 1, f"o total de donos deveria cair para {count_before - 1}, ficou {count_after}"


# Pergunta: quantas linhas existem hoje na tabela `pets`?
# Devolve uma linha só, com um único valor: o total de pets.
COUNT_PETS = """
SELECT COUNT(*) FROM pets;
"""

# Pergunta: quantas linhas existem hoje na tabela `visits`?
# Devolve uma linha só, com um único valor: o total de visitas.
COUNT_VISITS = """
SELECT COUNT(*) FROM visits;
"""

# Pergunta: de qual pet (pet_id) é a visita com um id?
# Recebe o id da visita (%s) e devolve uma linha com um valor só: o pet_id. Se a visita não existir,
# não devolve nenhuma linha.
SELECT_VISIT_PET_ID = """
SELECT pet_id FROM visits WHERE id = %s;
"""


def test_apagar_dono_com_pet_apaga_junto_o_pet_e_a_visita(api, db, owner_with_pet_and_visit):
    """CT-API-OWNERS-10: apagar um dono que tem pet responde 204 e remove junto o pet e a visita dele,
    exatamente um registro de cada."""
    # Preparar: dono, pet e visita vêm da fixture, gravados por SQL; aqui só os totais antes
    owner_id = owner_with_pet_and_visit["owner_id"]
    pet_id = owner_with_pet_and_visit["pet_id"]
    visit_id = owner_with_pet_and_visit["visit_id"]
    owners_before = db.execute(COUNT_OWNERS).fetchone()[0]
    pets_before = db.execute(COUNT_PETS).fetchone()[0]
    visits_before = db.execute(COUNT_VISITS).fetchone()[0]

    # Agir
    response = api.delete(f"/owners/{owner_id}")

    # Verificar a resposta
    assert response.status_code == 204, f"DELETE /owners/{owner_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: dono, pet e visita não existem mais (o tipo fica de fora: é o BUG-03)
    assert db.execute(SELECT_OWNER_BY_ID, (owner_id,)).fetchone() is None, f"o dono {owner_id} não deveria mais existir"
    assert db.execute(SELECT_PET_OWNER_ID, (pet_id,)).fetchone() is None, f"o pet {pet_id} não deveria mais existir"
    assert db.execute(SELECT_VISIT_PET_ID, (visit_id,)).fetchone() is None, f"a visita {visit_id} não deveria mais existir"

    # e saiu exatamente um registro de cada
    owners_after = db.execute(COUNT_OWNERS).fetchone()[0]
    pets_after = db.execute(COUNT_PETS).fetchone()[0]
    visits_after = db.execute(COUNT_VISITS).fetchone()[0]
    assert owners_after == owners_before - 1, f"o total de donos deveria cair para {owners_before - 1}, ficou {owners_after}"
    assert pets_after == pets_before - 1, f"o total de pets deveria cair para {pets_before - 1}, ficou {pets_after}"
    assert visits_after == visits_before - 1, f"o total de visitas deveria cair para {visits_before - 1}, ficou {visits_after}"


# Pergunta: qual é o maior id da tabela `owners` hoje?
# Devolve uma linha só, com um único valor: o maior id.
SELECT_MAX_OWNER_ID = """
SELECT MAX(id) FROM owners;
"""


def test_consultar_dono_inexistente_responde_404(api, db):
    """CT-API-OWNERS-11: consultar um id numérico que não existe responde 404."""
    # Preparar: um id que não existe, lido do banco na hora (o maior id + 1)
    missing_id = db.execute(SELECT_MAX_OWNER_ID).fetchone()[0] + 1
    assert db.execute(SELECT_OWNER_BY_ID, (missing_id,)).fetchone() is None, f"o id {missing_id} não deveria existir"

    # Agir
    response = api.get(f"/owners/{missing_id}")

    # Verificar a resposta: 404, sem dados de dono
    assert response.status_code == 404, f"GET /owners/{missing_id} deveria responder 404, respondeu {response.status_code}"
    assert "firstName" not in response.text, "a resposta não deveria trazer dados de dono"


# Pergunta: quais são os ids dos donos cujo last_name casa com um padrão de texto?
# Recebe o padrão como parâmetro (%s), por exemplo 'Zylber%' (o teste já manda com o %), e devolve
# uma linha por dono, cada uma com um valor só: o id.
SELECT_OWNER_IDS_BY_LAST_NAME_PATTERN = """
SELECT id FROM owners WHERE last_name LIKE %s;
"""


def test_buscar_donos_por_sobrenome_devolve_os_que_comecam_com_o_termo(api, db, owner_factory):
    """CT-API-OWNERS-12: a busca por sobrenome devolve exatamente os donos do banco cujo sobrenome começa
    com o termo, e não os que só o contêm no meio."""
    # Preparar: dois donos com o prefixo único e um que só o contém no meio, gravados por SQL
    prefix = "Zylber"
    starts_with = {owner_factory(last_name="Zylberman"), owner_factory(last_name="Zylberstein")}
    contains_only = owner_factory(last_name="Azylber")

    # Agir
    response = api.get("/owners", params={"lastName": prefix})

    # Verificar a resposta
    assert response.status_code == 200, f"GET /owners?lastName={prefix} deveria responder 200, respondeu {response.status_code}"
    response_ids = {owner["id"] for owner in response.json()}

    # Verificar contra o banco: o conjunto esperado vem do banco, não da resposta
    rows = db.execute(SELECT_OWNER_IDS_BY_LAST_NAME_PATTERN, (prefix + "%",)).fetchall()
    db_ids = {row[0] for row in rows}
    assert db_ids == starts_with, f"o banco deveria ter só os donos criados com o prefixo {sorted(starts_with)}, tem {sorted(db_ids)}"
    assert response_ids == db_ids, f"a busca deveria devolver {sorted(db_ids)}, devolveu {sorted(response_ids)}"
    assert contains_only not in response_ids, "a busca não deveria devolver quem só contém o termo no meio do sobrenome"


def test_criar_dono_com_id_de_outro_dono_no_corpo_nao_sobrescreve_o_outro(api, db, prepared_owner, owners_to_delete):
    """CT-API-OWNERS-13: o id de um dono existente, enviado no corpo do POST, é ignorado: o banco gera outro
    id e o dono existente fica intacto."""
    # Preparar: o dono A vem da fixture; a linha dele, lida do banco, é o valor esperado depois
    existing_id = prepared_owner
    existing_before = db.execute(SELECT_OWNER_BY_ID, (existing_id,)).fetchone()
    payload = {**OWNER, "id": existing_id}

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta: 201, com um id gerado pelo banco
    assert response.status_code == 201, f"POST /owners com id no corpo deveria responder 201, respondeu {response.status_code}"
    assert body["id"] != existing_id, f"o id devolvido deveria ser outro, não o {existing_id} enviado no corpo"

    # Verificar o banco: o dono A intacto, e a linha nova com os dados enviados
    existing_after = db.execute(SELECT_OWNER_BY_ID, (existing_id,)).fetchone()
    assert existing_after == existing_before, f"o dono {existing_id} deveria continuar {existing_before}, ficou {existing_after}"
    new_row = db.execute(SELECT_OWNER_BY_ID, (body["id"],)).fetchone()
    expected = (OWNER["firstName"], OWNER["lastName"], OWNER["address"], OWNER["city"], OWNER["telephone"])
    assert new_row == expected, f"a linha nova {body['id']} deveria ser {expected}, é {new_row}"


def test_criar_dono_com_id_inexistente_no_corpo_ignora_o_id(api, db, owners_to_delete):
    """CT-API-OWNERS-13: um id que não existe, enviado no corpo do POST, é ignorado: o banco gera outro id e
    nenhuma linha fica com o id enviado."""
    # Preparar: um id longe do maior id, para o banco não gerar justamente esse número
    sent_id = db.execute(SELECT_MAX_OWNER_ID).fetchone()[0] + 1000
    assert db.execute(SELECT_OWNER_BY_ID, (sent_id,)).fetchone() is None, f"o id {sent_id} não deveria existir"
    payload = {**OWNER, "id": sent_id}

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta: 201, com um id gerado pelo banco
    assert response.status_code == 201, f"POST /owners com id no corpo deveria responder 201, respondeu {response.status_code}"
    assert body["id"] != sent_id, f"o id devolvido deveria ser outro, não o {sent_id} enviado no corpo"

    # Verificar o banco: a linha nova com os dados enviados, e nenhuma linha com o id enviado
    new_row = db.execute(SELECT_OWNER_BY_ID, (body["id"],)).fetchone()
    expected = (OWNER["firstName"], OWNER["lastName"], OWNER["address"], OWNER["city"], OWNER["telephone"])
    assert new_row == expected, f"a linha nova {body['id']} deveria ser {expected}, é {new_row}"
    assert db.execute(SELECT_OWNER_BY_ID, (sent_id,)).fetchone() is None, f"nenhuma linha deveria ter o id {sent_id}"


@pytest.mark.parametrize("field", ["firstName", "lastName"])
def test_criar_dono_com_digito_no_nome_e_recusado_sem_gravar(api, db, owners_to_delete, field):
    """CT-API-OWNERS-14: nome ou sobrenome com dígito, com tamanho válido, responde 400 apontando o campo e
    não grava dono."""
    # Preparar: o dono padrão com o dígito no campo, e o total de donos antes
    payload = {**OWNER, field: "Ana2"}
    assert re.search(r"\d", payload[field]) and 1 <= len(payload[field]) <= 30, (
        "o valor do teste deveria ter um dígito e tamanho válido, para isolar a regra de formato"
    )
    count_before = db.execute(COUNT_OWNERS).fetchone()[0]

    # Agir
    response = api.post("/owners", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo alterado
    assert response.status_code == 400, f"POST /owners com {field}='Ana2' deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {field}, (
        f"o erro deveria apontar só {field}, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: nenhum dono novo
    count_after = db.execute(COUNT_OWNERS).fetchone()[0]
    assert count_after == count_before, f"o total de donos deveria continuar {count_before}, ficou {count_after}"
