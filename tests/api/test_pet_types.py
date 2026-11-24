"""Testes de tipos de pet (tabela `types`), com o banco como oráculo."""

import pytest

# Tipo padrão: o contrato só aceita letras, espaços, hífen e apóstrofo no nome, então não há sufixo numérico.
# "coelho" não existe no populateDB.sql nem nas fixtures (chinchila e furão), e cada teste apaga o tipo que criou.
PET_TYPE = {"name": "coelho"}

# Pergunta: qual é o nome gravado na linha de `types` com o id que a API devolveu no POST?
# Recebe o id (%s) e devolve uma linha com um valor só: o name. Se o tipo não existir, não devolve linha.
SELECT_PET_TYPE_BY_ID = """
SELECT name
FROM types
WHERE id = %s;
"""

def test_criar_tipo_de_pet_com_nome_valido_grava_o_nome(api, db, pet_types_to_delete):
    """CT-API-PET-TYPES-01: criar um tipo de pet com nome válido responde 201 e grava em `types` o nome
    enviado."""
    # Preparar
    payload = dict(PET_TYPE)

    # Agir
    response = api.post("/pettypes", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pet_types_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /pettypes deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha do id devolvido tem o nome enviado
    row = db.execute(SELECT_PET_TYPE_BY_ID, (body["id"],)).fetchone()
    expected = (payload["name"],)
    assert row == expected, f"a linha do tipo {body['id']} deveria ser {expected}, é {row}"


# Pergunta: quantos tipos de pet existem hoje?
# Devolve uma linha só, com um único valor: o total de linhas de `types`.
COUNT_PET_TYPES = """
SELECT COUNT(*) FROM types;
"""


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="sem-name"),
        pytest.param({"name": None}, id="name-null"),
        pytest.param({"name": ""}, id="name-vazio"),
        pytest.param({"name": "   "}, id="name-so-espacos"),
    ],
)
def test_criar_tipo_de_pet_sem_nome_e_recusado_sem_gravar(api, db, pet_types_to_delete, payload):
    """CT-API-PET-TYPES-02: criar um tipo de pet sem nome, com nome nulo, vazio ou só com espaços responde 400
    apontando o campo `name` e não grava tipo nenhum.

    O banco aceitaria NULL e texto vazio: quem recusa é a validação da API."""
    # Preparar: o total de tipos antes do envio
    types_before = db.execute(COUNT_PET_TYPES).fetchone()[0]

    # Agir
    response = api.post("/pettypes", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pet_types_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo name
    assert response.status_code == 400, f"POST /pettypes com {payload} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"name"}, (
        f"o erro deveria apontar só name, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o total de tipos não muda
    types_after = db.execute(COUNT_PET_TYPES).fetchone()[0]
    assert types_after == types_before, f"o total de tipos deveria continuar {types_before}, ficou {types_after}"


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("a" * 80, id="80-letras"),
        pytest.param("é" * 80, id="80-acentuadas-160-bytes"),
    ],
)
def test_criar_tipo_de_pet_com_nome_de_80_caracteres_grava_inteiro(api, db, pet_types_to_delete, name):
    """CT-API-PET-TYPES-03: um nome de tipo com 80 caracteres, o limite do contrato, é aceito e gravado
    inteiro. O limite conta caracteres, não bytes: 80 letras acentuadas (160 bytes em UTF-8) também passam."""
    # Preparar
    assert len(name) == 80, f"o nome do teste deveria ter 80 caracteres, tem {len(name)}"
    payload = {"name": name}

    # Agir
    response = api.post("/pettypes", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pet_types_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /pettypes com nome de 80 caracteres deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: o nome gravado é o enviado, sem corte
    row = db.execute(SELECT_PET_TYPE_BY_ID, (body["id"],)).fetchone()
    expected = (payload["name"],)
    assert row == expected, f"o tipo {body['id']} deveria ter o nome enviado, de 80 caracteres; tem {row}"


def test_criar_tipo_de_pet_com_nome_de_81_caracteres_e_recusado_sem_gravar(api, db, pet_types_to_delete):
    """CT-API-PET-TYPES-03: um nome de tipo com 81 caracteres, um acima do limite do contrato, responde 400
    apontando o campo `name` e não grava tipo nenhum."""
    # Preparar
    payload = {"name": "a" * 81}
    assert len(payload["name"]) == 81, "o nome do teste deveria ter 81 caracteres"
    types_before = db.execute(COUNT_PET_TYPES).fetchone()[0]

    # Agir
    response = api.post("/pettypes", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pet_types_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo name
    assert response.status_code == 400, f"POST /pettypes com nome de 81 caracteres deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"name"}, (
        f"o erro deveria apontar só name, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o total de tipos não muda
    types_after = db.execute(COUNT_PET_TYPES).fetchone()[0]
    assert types_after == types_before, f"o total de tipos deveria continuar {types_before}, ficou {types_after}"
