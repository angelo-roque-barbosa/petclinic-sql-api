"""Testes de donos (tabela `owners`), com o banco como oráculo."""

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
