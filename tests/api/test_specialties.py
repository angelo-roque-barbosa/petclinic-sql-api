"""Testes de especialidades (tabela `specialties`), com o banco como oráculo."""

import pytest

from conftest import SECOND_SPECIALTY_NAME

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


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("a" * 80, id="80-letras"),
        pytest.param(("ortopedia & clínica/cirúrgica " * 3)[:80], id="80-com-e-comercial-barra-e-acentos"),
    ],
)
def test_criar_especialidade_com_nome_de_80_caracteres_grava_inteiro(api, db, specialties_to_delete, name):
    """CT-API-SPECIALTIES-03: um nome de especialidade com 80 caracteres, o limite do contrato, é aceito e
    gravado inteiro, também com `&`, `/` e letras acentuadas (que ocupam mais de 80 bytes)."""
    # Preparar
    assert len(name) == 80, f"o nome do teste deveria ter 80 caracteres, tem {len(name)}"
    payload = {"name": name}

    # Agir
    response = api.post("/specialties", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        specialties_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /specialties com nome de 80 caracteres deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: o nome gravado é o enviado, sem corte
    row = db.execute(SELECT_SPECIALTY_BY_ID, (body["id"],)).fetchone()
    expected = (payload["name"],)
    assert row == expected, f"a especialidade {body['id']} deveria ter o nome enviado, de 80 caracteres; tem {row}"


def test_criar_especialidade_com_nome_de_81_caracteres_e_recusada_sem_gravar(api, db, specialties_to_delete):
    """CT-API-SPECIALTIES-03: um nome de especialidade com 81 caracteres, um acima do limite do contrato,
    responde 400 apontando o campo `name` e não grava especialidade nenhuma."""
    # Preparar
    payload = {"name": "a" * 81}
    assert len(payload["name"]) == 81, "o nome do teste deveria ter 81 caracteres"
    specialties_before = db.execute(COUNT_SPECIALTIES).fetchone()[0]

    # Agir
    response = api.post("/specialties", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        specialties_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo name
    assert response.status_code == 400, f"POST /specialties com nome de 81 caracteres deveria responder 400, respondeu {response.status_code}"
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


def test_atualizar_especialidade_grava_o_novo_nome_na_mesma_linha(api, db, prepared_specialty, second_specialty):
    """CT-API-SPECIALTIES-06: atualizar o nome de uma especialidade responde 204 e grava o nome novo na mesma
    linha, sem criar outra especialidade. A especialidade da fixture second_specialty é o controle e continua
    com o nome dela.

    Ao contrário do PUT de tipo, o contrato não exige o id no corpo (`readOnly` em `Specialty`)."""
    # Preparar: o corpo leva só o nome novo; os totais antes
    specialty_id = prepared_specialty
    payload = dict(SPECIALTY)
    specialties_before = db.execute(COUNT_SPECIALTIES).fetchone()[0]

    # Agir
    response = api.put(f"/specialties/{specialty_id}", json=payload)

    # Verificar a resposta
    assert response.status_code == 204, f"PUT /specialties/{specialty_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: a mesma linha com o nome novo, nenhuma especialidade a mais e o controle sem mudança
    row = db.execute(SELECT_SPECIALTY_BY_ID, (specialty_id,)).fetchone()
    expected = (payload["name"],)
    assert row == expected, f"a especialidade {specialty_id} deveria se chamar {expected}, é {row}"
    specialties_after = db.execute(COUNT_SPECIALTIES).fetchone()[0]
    assert specialties_after == specialties_before, (
        f"o total de especialidades deveria continuar {specialties_before}, ficou {specialties_after}"
    )
    control = db.execute(SELECT_SPECIALTY_BY_ID, (second_specialty,)).fetchone()
    assert control == (SECOND_SPECIALTY_NAME,), (
        f"a especialidade de controle {second_specialty} deveria continuar ({SECOND_SPECIALTY_NAME!r},), é {control}"
    )
