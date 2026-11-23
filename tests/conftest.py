"""Fixtures compartilhadas pelos testes: endereço da API, espera pela API e conexão com o banco.

Os valores padrão são os do docker-compose.yml. Para outro ambiente local, use as variáveis
API_BASE_URL, API_WAIT_SECONDS, PGHOST, PGPORT, PGDATABASE, PGUSER e PGPASSWORD.
"""

import os
import time

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
