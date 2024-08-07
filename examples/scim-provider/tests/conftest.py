import importlib
import json
from typing import List

import httpx
import pytest

from scim_provider.backend import InMemoryBackend
from scim_provider.provider import SCIMProvider
from scim_provider.utils import load_default_resource_types
from scim_provider.utils import load_default_schemas


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture(scope="session")
def static_data():
    return load_default_schemas(), load_default_resource_types()


def load_json_resource(json_name: str) -> List:
    fp = importlib.resources.files("tests") / json_name
    with open(fp) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def fake_user_data():
    return load_json_resource("fake_user_data.json")


@pytest.fixture
def provider(backend, static_data):
    provider = SCIMProvider(backend)
    for schema in static_data[0].values():
        provider.register_schema(schema)
    for resource_type in static_data[1].values():
        provider.register_resource_type(resource_type)
    return provider


@pytest.fixture
def wsgi(provider):
    transport = httpx.WSGITransport(app=provider)
    client = httpx.Client(transport=transport, base_url="https://scim.example.com")
    client.__enter__()
    yield client
    provider.backend.resources = []
    client.__exit__(None, None, None)


@pytest.fixture
def first_fake_user(wsgi, fake_user_data):
    r = wsgi.post("/v2/Users", json=fake_user_data[0])
    return r.json()["id"]
