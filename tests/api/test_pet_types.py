"""Testes de tipos de pet (tabela `types`), com o banco como oráculo."""

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
