"""Testes de especialidades (tabela `specialties`), com o banco como oráculo."""

import pytest

# Especialidade padrão: o contrato só aceita letras, espaço, `-`, `&` e `/` no nome, então não há sufixo
# numérico. "dermatologia" não existe no populateDB.sql, e cada teste apaga a especialidade que criou.
SPECIALTY = {"name": "dermatologia"}

# Pergunta: qual é o nome gravado na linha de `specialties` com o id que a API devolveu no POST?
# Recebe o id (%s) e devolve uma linha com um valor só: o name. Se a especialidade não existir, não devolve
# linha.
SELECT_SPECIALTY_BY_ID = """
SELECT name FROM specialties WHERE id = %s;
"""


def test_criar_especialidade_com_nome_valido_grava_o_nome(api, db, specialties_to_delete):
    """CT-API-SPECIALTIES-01: criar uma especialidade com nome válido responde 201 e grava em `specialties` o
    nome enviado."""
    # Preparar
    payload = dict(SPECIALTY)

    # Agir
    response = api.post("/specialties", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        specialties_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /specialties deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha do id devolvido tem o nome enviado
    row = db.execute(SELECT_SPECIALTY_BY_ID, (body["id"],)).fetchone()
    expected = (payload["name"],)
    assert row == expected, f"a linha da especialidade {body['id']} deveria ser {expected}, é {row}"


# Pergunta: quantas especialidades existem hoje?
# Devolve uma linha só, com um único valor: o total de linhas de `specialties`.
COUNT_SPECIALTIES = """
SELECT COUNT(*) FROM specialties;
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
def test_criar_especialidade_sem_nome_e_recusada_sem_gravar(api, db, specialties_to_delete, payload):
    """CT-API-SPECIALTIES-02: criar uma especialidade sem nome, com nome nulo, vazio ou só com espaços responde
    400 apontando o campo `name` e não grava especialidade nenhuma.

    O banco aceitaria NULL e texto vazio: quem recusa é a validação da API."""
    # Preparar: o total de especialidades antes do envio
    specialties_before = db.execute(COUNT_SPECIALTIES).fetchone()[0]

    # Agir
    response = api.post("/specialties", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        specialties_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo name
    assert response.status_code == 400, f"POST /specialties com {payload} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"name"}, (
        f"o erro deveria apontar só name, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o total de especialidades não muda
    specialties_after = db.execute(COUNT_SPECIALTIES).fetchone()[0]
    assert specialties_after == specialties_before, (
        f"o total de especialidades deveria continuar {specialties_before}, ficou {specialties_after}"
    )
