"""Fixtures compartilhadas pelos testes: endereço da API, espera pela API e conexão com o banco.

Os valores padrão são os do docker-compose.yml. Para outro ambiente local, use as variáveis
API_BASE_URL, API_WAIT_SECONDS, PGHOST, PGPORT, PGDATABASE, PGUSER e PGPASSWORD.
"""

import os
import time
from datetime import date, datetime, timezone

import psycopg
import pytest
import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:9966/petclinic/api")
API_WAIT_SECONDS = float(os.environ.get("API_WAIT_SECONDS", "60"))
HTTP_TIMEOUT_SECONDS = 10

DB_SETTINGS = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": int(os.environ.get("PGPORT", "5432")),
    "dbname": os.environ.get("PGDATABASE", "petclinic"),
    "user": os.environ.get("PGUSER", "petclinic"),
    "password": os.environ.get("PGPASSWORD", "petclinic"),
}


class ApiClient:
    """Cliente HTTP da API: recebe o caminho relativo (ex.: "/owners") e usa sempre o mesmo timeout."""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", HTTP_TIMEOUT_SECONDS)
        return self.session.request(method, self.base_url + path, **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)


def today_utc():
    """Hoje no fuso da API (UTC), calculado na hora do teste."""
    return datetime.now(timezone.utc).date()


def wait_for_api(client, deadline_seconds):
    """Repete GET /vets até a API responder 200 ou o prazo acabar. Não é uma espera fixa:
    sai assim que a API fica pronta."""
    deadline = time.monotonic() + deadline_seconds
    last_problem = "nenhuma tentativa"
    while time.monotonic() < deadline:
        try:
            response = client.get("/vets", timeout=5)
            if response.status_code == 200:
                return
            last_problem = f"status {response.status_code}"
        except requests.RequestException as error:
            last_problem = type(error).__name__
        time.sleep(1)
    pytest.exit(
        f"A API em {client.base_url} não ficou pronta em {deadline_seconds:.0f} s "
        f"(último problema: {last_problem}). Suba o ambiente com `docker compose up -d --wait`.",
        returncode=3,
    )


@pytest.fixture(scope="session")
def api():
    """Cliente da API, entregue só depois de a API responder."""
    client = ApiClient(API_BASE_URL)
    wait_for_api(client, API_WAIT_SECONDS)
    return client


@pytest.fixture(scope="session")
def db():
    """Conexão com o banco, o oráculo dos testes. Em autocommit, cada consulta enxerga o que a API
    já gravou."""
    try:
        connection = psycopg.connect(**DB_SETTINGS, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as error:
        pytest.exit(
            f"Não foi possível conectar ao banco em {DB_SETTINGS['host']}:{DB_SETTINGS['port']} ({error}). "
            "Suba o ambiente com `docker compose up -d --wait`.",
            returncode=3,
        )
    yield connection
    connection.close()


@pytest.fixture
def owners_to_delete(api):
    """Lista de ids de donos criados pelo teste. No fim, cada um é apagado pela API; 404 também
    serve, porque o dono pode já ter sido removido."""
    ids = []
    yield ids
    for owner_id in ids:
        response = api.delete(f"/owners/{owner_id}")
        assert response.status_code in (204, 404), (
            f"limpeza: DELETE /owners/{owner_id} respondeu {response.status_code}"
        )
        
# Consultas usadas por mais de um arquivo de teste.

# Pergunta: qual é a linha de `owners` com o id que a API devolveu no POST?
# A consulta deve trazer, nesta ordem, first_name, last_name, address, city e telephone,
# e receber o id como parâmetro (%s), sem montar o texto da consulta com o valor.
SELECT_OWNER_BY_ID = """ 
SELECT first_name, last_name, address, city, telephone FROM owners WHERE id = %s;
  """

# Pergunta: quantas linhas existem hoje na tabela `pets`?
# Devolve uma linha só, com um único valor: o total de pets.
COUNT_PETS = """
SELECT COUNT(*) FROM pets;
"""

# Pergunta: qual é o maior id da tabela `owners` hoje?
# Devolve uma linha só, com um único valor: o maior id.
SELECT_MAX_OWNER_ID = """
SELECT MAX(id) FROM owners;
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

# Pergunta: quantas ligações entre veterinário e especialidade existem hoje?
# Devolve uma linha só, com um único valor: o total de linhas de `vet_specialties`.
COUNT_VET_SPECIALTIES = """
SELECT COUNT(*) FROM vet_specialties;
"""


# Dados que a fixture owner_with_pet grava direto no banco. São do próprio teste: nenhum vem do seed,
# então a limpeza não mexe em dado do populateDB.sql.
PREPARED_PET_TYPE_NAME = "chinchila"
SECOND_PET_TYPE_NAME = "furão"
PREPARED_SPECIALTY_NAME = "cardiologia"
SECOND_SPECIALTY_NAME = "oncologia"
THIRD_SPECIALTY_NAME = "neurologia"
PREPARED_OWNER = {
    "first_name": "Rafael",
    "last_name": "Souza",
    "address": "Rua B, 2",
    "city": "Recife",
    "telephone": "8199990001",
}
PREPARED_PET = {"name": "Thor", "birth_date": date(2020, 5, 10)}
PREPARED_VISIT = {"visit_date": date(2026, 11, 1), "description": "Consulta de rotina"}
SECOND_VISIT = {"visit_date": date(2026, 11, 2), "description": "Retorno"}
PREPARED_VET = {"first_name": "Helena", "last_name": "Costa"}

# Pergunta: como gravar um tipo de pet novo e receber o id que o banco gerou para ele?
# Recebe o nome como parâmetro (%s) e devolve uma linha com um valor só: o id criado.
INSERT_PET_TYPE = """
INSERT INTO types (name)
VALUES (%s)
RETURNING id;
"""

# Pergunta: como gravar um dono novo e receber o id gerado?
# Recebe, nesta ordem, first_name, last_name, address, city e telephone (cinco %s)
# e devolve uma linha com um valor só: o id criado.
INSERT_OWNER = """
INSERT INTO owners (first_name, last_name, address, city, telephone)
VALUES (%s, %s, %s, %s, %s)
RETURNING id;
"""

# Pergunta: como gravar um pet novo, ligado a um tipo e a um dono, e receber o id gerado?
# Recebe, nesta ordem, name, birth_date, type_id e owner_id (quatro %s)
# e devolve uma linha com um valor só: o id criado.
INSERT_PET = """
INSERT INTO pets (name, birth_date, type_id, owner_id)
VALUES (%s, %s, %s, %s)
RETURNING id;
"""

# Pergunta: como apagar o pet com um id? Recebe o id (%s).
DELETE_PET = """
DELETE FROM pets WHERE id = %s;
"""

# Pergunta: como apagar o dono com um id? Recebe o id (%s).
DELETE_OWNER = """
DELETE FROM owners WHERE id = %s;
"""

# Pergunta: como apagar o tipo de pet com um id? Recebe o id (%s).
DELETE_PET_TYPE = """
DELETE FROM types WHERE id = %s;
"""

# Pergunta: como gravar uma especialidade nova e receber o id que o banco gerou para ela?
# Recebe o nome como parâmetro (%s) e devolve uma linha com um valor só: o id criado.
INSERT_SPECIALTY = """ 
INSERT INTO specialties (name)
VALUES (%s)
RETURNING id;
"""

# Pergunta: como apagar a especialidade com um id? Recebe o id (%s).
DELETE_SPECIALTY = """
DELETE FROM specialties WHERE id = %s;
"""

# Pergunta: como gravar um veterinário novo e receber o id que o banco gerou para ele?
# Recebe, nesta ordem, first_name e last_name (dois %s) e devolve uma linha com um valor só: o id criado.
INSERT_VET = """
INSERT INTO vets (first_name, last_name)
VALUES (%s, %s)
RETURNING id;
"""

# Pergunta: como ligar um veterinário a uma especialidade? Recebe, nesta ordem, vet_id e specialty_id (dois %s)
# e grava uma linha em `vet_specialties`. Não precisa devolver nada, porque a tabela não tem id próprio.
INSERT_VET_SPECIALTY = """
INSERT INTO vet_specialties (vet_id, specialty_id)
VALUES (%s, %s);
"""

# Pergunta: como apagar todas as ligações de um veterinário com especialidades? Recebe o id do veterinário (%s)
# e apaga as linhas de `vet_specialties` dele, quantas forem (zero também serve).
DELETE_VET_SPECIALTIES_BY_VET = """
DELETE FROM vet_specialties WHERE vet_id = %s;
"""

# Pergunta: como apagar o veterinário com um id? Recebe o id (%s).
DELETE_VET = """
DELETE FROM vets WHERE id = %s;
"""

# Pergunta: como gravar uma visita nova de um pet e receber o id gerado?
# Recebe, nesta ordem, pet_id, visit_date e description (três %s)
# e devolve uma linha com um valor só: o id criado.
INSERT_VISIT = """
INSERT INTO visits (pet_id, visit_date, description)
VALUES (%s, %s, %s)
RETURNING id;
"""

# Pergunta: como apagar a visita com um id? Recebe o id (%s).
DELETE_VISIT = """
DELETE FROM visits WHERE id = %s;
"""


@pytest.fixture
def prepared_owner(db):
    """Grava direto no banco um dono, sem pets, e entrega o id. No fim, apaga o dono; apagar zero linhas
    também serve, porque ele pode já ter sido removido."""
    owner = PREPARED_OWNER
    owner_id = db.execute(
        INSERT_OWNER,
        (owner["first_name"], owner["last_name"], owner["address"], owner["city"], owner["telephone"]),
    ).fetchone()[0]
    yield owner_id
    db.execute(DELETE_OWNER, (owner_id,))


@pytest.fixture
def owner_factory(db):
    """Fábrica de donos gravados direto no banco: owner_factory(last_name="Lima") cria um dono com os dados
    de PREPARED_OWNER e o sobrenome pedido, e devolve o id. No fim, apaga todos os que criou; apagar zero
    linhas também serve."""
    created = []

    def create(**overrides):
        owner = {**PREPARED_OWNER, **overrides}
        owner_id = db.execute(
            INSERT_OWNER,
            (owner["first_name"], owner["last_name"], owner["address"], owner["city"], owner["telephone"]),
        ).fetchone()[0]
        created.append(owner_id)
        return owner_id

    yield create
    for owner_id in created:
        db.execute(DELETE_OWNER, (owner_id,))


@pytest.fixture
def prepared_pet_type(db):
    """Grava direto no banco um tipo de pet e entrega o id. No fim, apaga o tipo; apagar zero linhas também
    serve, porque ele pode já ter sido removido."""
    type_id = db.execute(INSERT_PET_TYPE, (PREPARED_PET_TYPE_NAME,)).fetchone()[0]
    yield type_id
    db.execute(DELETE_PET_TYPE, (type_id,))


@pytest.fixture
def pet_types_to_delete(db):
    """Lista de ids de tipos de pet criados pela API no teste. No fim, cada um é apagado por SQL; apagar zero
    linhas também serve, porque o tipo pode já ter sido removido."""
    ids = []
    yield ids
    for type_id in ids:
        db.execute(DELETE_PET_TYPE, (type_id,))


@pytest.fixture
def prepared_specialty(db):
    """Grava direto no banco uma especialidade, sem veterinários, e entrega o id. No fim, apaga a
    especialidade; apagar zero linhas também serve, porque ela pode já ter sido removida."""
    specialty_id = db.execute(INSERT_SPECIALTY, (PREPARED_SPECIALTY_NAME,)).fetchone()[0]
    yield specialty_id
    db.execute(DELETE_SPECIALTY, (specialty_id,))


@pytest.fixture
def second_specialty(db):
    """Grava direto no banco uma segunda especialidade, sem veterinários, e entrega o id. Serve de controle:
    o teste confere que ela não muda. No fim, apaga a especialidade; apagar zero linhas também serve."""
    specialty_id = db.execute(INSERT_SPECIALTY, (SECOND_SPECIALTY_NAME,)).fetchone()[0]
    yield specialty_id
    db.execute(DELETE_SPECIALTY, (specialty_id,))


@pytest.fixture
def third_specialty(db):
    """Grava direto no banco uma terceira especialidade, sem veterinários, e entrega o id. No fim, apaga a
    especialidade; apagar zero linhas também serve."""
    specialty_id = db.execute(INSERT_SPECIALTY, (THIRD_SPECIALTY_NAME,)).fetchone()[0]
    yield specialty_id
    db.execute(DELETE_SPECIALTY, (specialty_id,))


@pytest.fixture
def specialties_to_delete(db):
    """Lista de ids de especialidades criadas pela API no teste. No fim, cada uma é apagada por SQL; apagar
    zero linhas também serve, porque a especialidade pode já ter sido removida."""
    ids = []
    yield ids
    for specialty_id in ids:
        db.execute(DELETE_SPECIALTY, (specialty_id,))


@pytest.fixture
def prepared_vet(db):
    """Grava direto no banco um veterinário, sem especialidades, com os dados de PREPARED_VET, e entrega o id.
    No fim, apaga as ligações dele em `vet_specialties` (um teste pode ter acrescentado) e depois o
    veterinário; apagar zero linhas também serve, porque ele pode já ter sido removido."""
    vet_id = db.execute(INSERT_VET, (PREPARED_VET["first_name"], PREPARED_VET["last_name"])).fetchone()[0]
    yield vet_id
    db.execute(DELETE_VET_SPECIALTIES_BY_VET, (vet_id,))
    db.execute(DELETE_VET, (vet_id,))


@pytest.fixture
def vets_to_delete(db):
    """Lista de ids de veterinários criados pela API no teste. No fim, apaga por SQL as ligações de cada um em
    `vet_specialties` e depois o veterinário, nessa ordem por causa da chave estrangeira; apagar zero linhas
    também serve.

    Quando o veterinário usa especialidades de fixtures, ele tem de ser apagado antes delas: peça esta fixture
    depois das de especialidade (por exemplo, `prepared_specialty, second_specialty, vets_to_delete`), porque
    o pytest desmonta as fixtures na ordem inversa em que foram pedidas."""
    ids = []
    yield ids
    for vet_id in ids:
        db.execute(DELETE_VET_SPECIALTIES_BY_VET, (vet_id,))
        db.execute(DELETE_VET, (vet_id,))


@pytest.fixture
def second_pet_type(db):
    """Grava direto no banco um segundo tipo de pet e entrega o id. No fim, apaga o tipo.

    Quando um pet passa a usar este tipo no teste, ele tem de ser apagado antes do tipo: peça esta fixture
    antes da que cria o pet (por exemplo, `second_pet_type, owner_with_pet`), porque o pytest desmonta as
    fixtures na ordem inversa em que foram pedidas."""
    type_id = db.execute(INSERT_PET_TYPE, (SECOND_PET_TYPE_NAME,)).fetchone()[0]
    yield type_id
    db.execute(DELETE_PET_TYPE, (type_id,))


@pytest.fixture
def pets_to_delete(db, prepared_owner, prepared_pet_type):
    """Lista de ids de pets criados pela API no teste. No fim, cada um é apagado por SQL; apagar zero linhas
    também serve. Depende do dono e do tipo para o pytest apagar os pets antes deles."""
    ids = []
    yield ids
    for pet_id in ids:
        db.execute(DELETE_PET, (pet_id,))


@pytest.fixture
def owner_with_pet(db, prepared_owner, prepared_pet_type):
    """Acrescenta ao dono e ao tipo das fixtures prepared_owner e prepared_pet_type um pet desse dono, gravado
    direto no banco, e entrega os ids.

    No fim, apaga o pet; o dono e o tipo são apagados depois, pelas fixtures de que esta depende, porque o
    pytest desmonta primeiro a fixture que depende das outras. Apagar zero linhas também serve."""
    created = {"owner_id": prepared_owner, "type_id": prepared_pet_type}
    created["pet_id"] = db.execute(
        INSERT_PET,
        (PREPARED_PET["name"], PREPARED_PET["birth_date"], created["type_id"], created["owner_id"]),
    ).fetchone()[0]
    yield created
    db.execute(DELETE_PET, (created["pet_id"],))


@pytest.fixture
def visits_to_delete(db, owner_with_pet):
    """Lista de ids de visitas criadas pela API no teste. No fim, cada uma é apagada por SQL; apagar zero
    linhas também serve. Depende da owner_with_pet para o pytest apagar as visitas antes do pet."""
    ids = []
    yield ids
    for visit_id in ids:
        db.execute(DELETE_VISIT, (visit_id,))


@pytest.fixture
def owner_with_pet_and_visit(db, owner_with_pet):
    """Acrescenta ao pet da fixture owner_with_pet uma visita gravada direto no banco, e entrega os ids.

    No fim, apaga a visita; o pet, o tipo e o dono são apagados depois, pelas fixtures de que esta depende.
    Apagar zero linhas também serve, porque a visita pode já ter sido removida."""
    created = dict(owner_with_pet)
    created["visit_id"] = db.execute(
        INSERT_VISIT,
        (created["pet_id"], PREPARED_VISIT["visit_date"], PREPARED_VISIT["description"]),
    ).fetchone()[0]
    yield created
    db.execute(DELETE_VISIT, (created["visit_id"],))


@pytest.fixture
def pet_with_two_visits(db, owner_with_pet_and_visit):
    """Acrescenta ao pet da fixture owner_with_pet_and_visit uma segunda visita, gravada direto no banco com os
    dados de SECOND_VISIT, e entrega os ids, com o da segunda visita em `second_visit_id`.

    No fim, apaga a segunda visita; a primeira, o pet, o tipo e o dono são apagados depois, pelas fixtures de
    que esta depende. Apagar zero linhas também serve."""
    created = dict(owner_with_pet_and_visit)
    created["second_visit_id"] = db.execute(
        INSERT_VISIT,
        (created["pet_id"], SECOND_VISIT["visit_date"], SECOND_VISIT["description"]),
    ).fetchone()[0]
    yield created
    db.execute(DELETE_VISIT, (created["second_visit_id"],))
