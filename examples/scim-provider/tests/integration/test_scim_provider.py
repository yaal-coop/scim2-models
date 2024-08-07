import datetime

import httpx
import time_machine
from scim2_models import SearchRequest

from tests.utils import compare_dicts


class TestSCIMProvider:
    """End-to-end tests for the SCIMProvider."""

    def test_location_mapping(self, provider):
        transport = httpx.WSGITransport(app=provider, script_name="/foo/bar")
        with httpx.Client(
            transport=transport, base_url="https://sub.testserver.company:1234"
        ) as client:
            r = client.get("/v2/ServiceProviderConfig")
            assert (
                r.request.url
                == "https://sub.testserver.company:1234/v2/ServiceProviderConfig"
            )
            assert (
                r.headers["Location"]
                == "https://sub.testserver.company:1234/foo/bar/v2/ServiceProviderConfig"
            )
            assert (
                r.json()["meta"]["location"]
                == "https://sub.testserver.company:1234/foo/bar/v2/ServiceProviderConfig"
            )

    def test_service_provider_configuration(self, wsgi):
        r = wsgi.get("/v2/ServiceProviderConfig")
        assert r.status_code == 200
        assert (
            r.headers["Location"] == "https://scim.example.com/v2/ServiceProviderConfig"
        )
        assert r.json() == {
            "authenticationSchemes": [],
            "bulk": {
                "supported": False,
            },
            "changePassword": {"supported": True},
            "documentationUri": "https://www.example.com/",
            "etag": {"supported": True},
            "filter": {"maxResults": 1000, "supported": True},
            "meta": {
                "location": "https://scim.example.com/v2/ServiceProviderConfig",
                "resourceType": "ServiceProviderConfig",
            },
            "patch": {"supported": True},
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "sort": {"supported": True},
        }

    def test_schemas(self, wsgi):
        r = wsgi.get("/v2/Schemas")
        assert r.status_code == 200
        j = r.json()
        assert j["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
        assert j["totalResults"] == 3
        assert len(j["Resources"]) == 3
        schema_ids = set(s["id"] for s in j["Resources"])
        assert schema_ids == {
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:core:2.0:Group",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        }

        r = wsgi.get("/v2/Schemas?filter=id sw 'urn'")
        assert r.status_code == 403

        r = wsgi.get("/v2/Schemas/urn:ietf:params:scim:schemas:core:2.0:User")
        assert r.status_code == 200
        j = r.json()
        assert j["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:Schema"]

        r = wsgi.get("/v2/Schemas/urn:foo:UnknownSchema")
        assert r.status_code == 404
        j = r.json()
        assert j["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]
        assert j["status"] == "404"
        assert "not found" in j["detail"]

    def test_resource_types(self, wsgi):
        r = wsgi.get("/v2/ResourceTypes")
        assert r.status_code == 200
        j = r.json()
        assert j["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
        assert j["totalResults"] == 2
        assert len(j["Resources"]) == 2
        resource_types = set(s["id"] for s in j["Resources"])
        assert resource_types == {
            "User",
            "Group",
        }

        r = wsgi.get("/v2/ResourceTypes/User")
        assert r.status_code == 200
        j = r.json()
        assert j["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"]
        assert j["schema"] == "urn:ietf:params:scim:schemas:core:2.0:User"
        assert len(j["schemaExtensions"]) == 1
        assert j["meta"]["location"] == "https://scim.example.com/v2/ResourceTypes/User"

        # RFC7644, Section 4
        r = wsgi.get("/v2/ResourceTypes?filter=id sw 'urn'")
        assert r.status_code == 403

        r = wsgi.get("/v2/ResourceTypes/Unknown")
        assert r.status_code == 404
        j = r.json()
        assert j["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]
        assert j["status"] == "404"
        assert "not found" in j["detail"]

    def test_me(self, wsgi):
        r = wsgi.get("/v2/Me")
        assert r.status_code == 501

    def test_data_output_uri_suffix(self, wsgi):
        # RFC 7644, Section 3.8
        r = wsgi.get("/v2/ResourceTypes.scim")
        assert r.status_code == 200

        r = wsgi.get("/v2/ResourceTypes/User.scim")
        assert r.status_code == 200

        r = wsgi.get("/v2/Users.scim")
        assert r.status_code == 200

    def test_resource_invalid_type(self, wsgi):
        r = wsgi.get("/v2/InvalidResourceType")
        assert r.status_code == 404

        r = wsgi.get("/v2/InvalidResourceType/InvalidID")
        assert r.status_code == 404

    def test_resource_creation(self, wsgi, fake_user_data):
        user_data = fake_user_data[0]

        r = wsgi.post("/v2/Users", json=user_data)
        assert r.status_code == 201
        j = r.json()
        user_id = j["id"]
        assert (
            r.headers["Location"]
            == j["meta"]["location"]
            == f"https://scim.example.com/v2/Users/{user_id}"
        )
        assert j["meta"]["resourceType"] == "User"
        assert j["schemas"] == [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        ]
        compare_dicts(user_data, j, ["password"])

    def test_resource_get(self, wsgi, fake_user_data, first_fake_user):
        r = wsgi.get(f"/v2/Users/{first_fake_user}")
        assert r.status_code == 200
        j = r.json()
        assert (
            r.headers["Location"]
            == j["meta"]["location"]
            == f"https://scim.example.com/v2/Users/{first_fake_user}"
        )
        assert j["meta"]["resourceType"] == "User"
        assert j["schemas"] == [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        ]
        compare_dicts(fake_user_data[0], j, ["password"])

    def test_resource_get_attributes(self, wsgi, first_fake_user):
        r = wsgi.get(f"/v2/Users/{first_fake_user}", params={"attributes": "userName"})
        assert r.status_code == 200
        assert r.json() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": first_fake_user,
            "userName": "joseph96@williams-brown.com",
        }

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}.scim",
            params={
                "attributes": ",".join(
                    [
                        "urn:ietf:params:scim:schemas:core:2.0:User:userName",
                        "active",
                        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:employeeNumber",
                    ]
                )
            },
        )
        assert r.status_code == 200
        assert r.json() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": first_fake_user,
            "active": True,
            "userName": "joseph96@williams-brown.com",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                "employeeNumber": "43660",
            },
        }

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}.scim",
            params={
                "excludedAttributes": ",".join(
                    [
                        "urn:ietf:params:scim:schemas:core:2.0:User:userName",
                        "active",
                        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:employeeNumber",
                    ]
                )
            },
        )
        assert r.status_code == 200
        j = r.json()
        assert "userName" not in j
        assert "active" not in j
        assert (
            "employeeNumber"
            not in j["urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"]
        )

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}.scim",
            params={"attributes": "active", "excludedAttributes": "userName"},
        )
        assert r.status_code == 400

    def test_resource_get_conflicting_attributes(self, wsgi, first_fake_user):
        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
            params={
                "attributes": "displayName",
                "excludedAttributes": "active",
            },
        )
        assert r.status_code == 400

    def test_resource_get_attributes_case_insensitive(self, wsgi, first_fake_user):
        # Specified attributes should be case-insensitive
        r = wsgi.get(
            f"/v2/Users/{first_fake_user}.scim",
            params={
                "attributes": ",".join(
                    [
                        "urn:IETF:params:scim:schemas:core:2.0:User:userName",
                        "actIVE",
                        "urn:ietf:params:scim:schemas:extension:Enterprise:2.0:User:employeenumber",
                    ]
                )
            },
        )
        assert r.status_code == 200
        assert r.json() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": first_fake_user,
            "active": True,
            "userName": "joseph96@williams-brown.com",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                "employeeNumber": "43660",
            },
        }

    def test_resource_put(self, wsgi, first_fake_user):
        r = wsgi.put(
            f"/v2/Users/{first_fake_user}",
            json={
                "id": first_fake_user,
                "active": False,
                "userName": "foo@example.com",
                "name": {
                    "givenName": "foo",
                },
                "password": "RandomSecurePassword!12345",
                "phoneNumbers": [
                    {"value": "001-767-633-4744", "type": "home", "primary": True}
                ],
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "employeeNumber": "512"
                },
            },
        )
        assert r.status_code == 200
        j = r.json()
        compare_dicts(
            {
                "id": first_fake_user,
                "displayName": "Mx. Larry Hunt",
                "active": False,
                "userName": "foo@example.com",
                "name": {
                    "givenName": "foo",
                },
                "phoneNumbers": [
                    {"value": "001-767-633-4744", "type": "home", "primary": True}
                ],
                "addresses": [],
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "employeeNumber": "512",
                    "organization": "Blake PLC",
                },
            },
            j,
        )

    def test_resource_put_not_found(self, wsgi):
        r = wsgi.put("/v2/Users/123", json={"name": "ABC"})
        assert r.status_code == 404

    def test_resource_put_remove(self, wsgi, first_fake_user):
        r = wsgi.put(
            f"/v2/Users/{first_fake_user}",
            json={
                "name": None,
                "phoneNumbers": [],
            },
        )
        assert r.status_code == 200
        j = r.json()
        assert not j.get("name")
        assert not j.get("phoneNumbers")

    def test_resource_delete(self, wsgi, first_fake_user):
        r = wsgi.delete(f"/v2/Users/{first_fake_user}")
        assert r.status_code == 204

        r = wsgi.get(f"/v2/Users/{first_fake_user}")
        assert r.status_code == 404

        r = wsgi.delete(f"/v2/Users/{first_fake_user}")
        assert r.status_code == 404

    def test_resource_patch(self, wsgi, first_fake_user):
        r = wsgi.patch(
            f"/v2/Users/{first_fake_user}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "op": "add",
                        "value": {
                            "displayName": "Replaced displayName",
                            "nickName": "Larr",
                        },
                    },
                    {
                        "op": "add",
                        "path": "addresses",
                        "value": [
                            {
                                "streetAddress": "910 Armstrong Garden",
                                "locality": "Collinsmouth",
                                "postalCode": "70055",
                                "country": "Falkland Islands (Malvinas)",
                                "type": "work",
                                "formatted": "910 Armstrong Garden\nCollinsmouth\n70055 Falkland Islands (Malvinas)",
                            }
                        ],
                    },
                    {
                        "op": "replace",
                        "path": 'emails[type eq "home"]',
                        "value": {"value": "lhunt@hotmail.com"},
                    },
                    {
                        "op": "remove",
                        "path": 'phoneNumbers[type ne "mobile"]',
                    },
                ],
            },
        )
        assert r.status_code == 204

        r = wsgi.get(f"/v2/Users/{first_fake_user}")
        assert r.status_code == 200
        compare_dicts(
            {
                "id": first_fake_user,
                "displayName": "Replaced displayName",
                "nickName": "Larr",
                "emails": [
                    {
                        "value": "joseph96@williams-brown.com",
                        "type": "work",
                        "primary": True,
                    },
                    {"value": "lhunt@hotmail.com", "type": "home", "primary": False},
                ],
                "phoneNumbers": [
                    {"value": "635-220-2551x11555", "type": "mobile", "primary": False}
                ],
                "addresses": [
                    {
                        "streetAddress": "910 Armstrong Garden",
                        "locality": "Collinsmouth",
                        "postalCode": "70055",
                        "country": "Falkland Islands (Malvinas)",
                        "type": "work",
                        "formatted": "910 Armstrong Garden\nCollinsmouth\n70055 Falkland Islands (Malvinas)",
                    }
                ],
            },
            r.json(),
        )

    def test_resource_patch_request_attributes(self, wsgi, first_fake_user):
        r = wsgi.patch(
            f"/v2/Users/{first_fake_user}",
            params={"attributes": "nickName"},
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "op": "add",
                        "value": {
                            "nickName": "Larr",
                        },
                    }
                ],
            },
        )
        assert r.status_code == 200
        assert r.json() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": first_fake_user,
            "nickName": "Larr",
        }

    def test_resource_patch_non_existing(self, wsgi):
        r = wsgi.patch(
            "/v2/Users/123",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "op": "add",
                        "value": {
                            "displayName": "Replaced displayName",
                            "nickName": "Larr",
                        },
                    },
                ],
            },
        )
        assert r.status_code == 404

    def test_resource_search_non_existing(self, wsgi):
        r = wsgi.get("/v2/InvalidResourceType")
        assert r.status_code == 404

    def test_resource_search(self, wsgi, first_fake_user):
        r = wsgi.get("/v2/Users", params={"attributes": "userName"})
        assert r.status_code == 200
        assert "userName" in r.json()["Resources"][0]

        r = wsgi.get("/v2/Users", params={"excludedAttributes": "userName"})
        assert r.status_code == 200
        assert "userName" not in r.json()["Resources"][0]

        r = wsgi.get("/v2/", params={"attributes": "userName"})
        assert r.status_code == 200
        assert "userName" in r.json()["Resources"][0]

        r = wsgi.get("/v2/", params={"excludedAttributes": "userName"})
        assert r.status_code == 200
        assert "userName" not in r.json()["Resources"][0]

        r = wsgi.get(
            "/v2/", params={"attributes": "active", "excludedAttributes": "userName"}
        )
        assert r.status_code == 400

    def test_resource_search_post(self, wsgi, first_fake_user):
        r = wsgi.post(
            "/v2/Users/.search",
            json=SearchRequest(attributes=["userName"]).model_dump(),
        )
        assert r.status_code == 200, r.text
        assert "userName" in r.json()["Resources"][0]

        r = wsgi.post(
            "/v2/Users/.search",
            json=SearchRequest(excluded_attributes=["userName"]).model_dump(),
        )
        assert r.status_code == 200
        assert "userName" not in r.json()["Resources"][0]

        r = wsgi.post(
            "/v2/.search", json=SearchRequest(attributes=["userName"]).model_dump()
        )
        assert r.status_code == 200, r.text
        assert "userName" in r.json()["Resources"][0]

        r = wsgi.post(
            "/v2/.search",
            json=SearchRequest(excluded_attributes=["userName"]).model_dump(),
        )
        assert r.status_code == 200
        assert "userName" not in r.json()["Resources"][0]

        r = wsgi.post(
            "/v2/InvalidResourceType/.search",
            json=SearchRequest().model_dump(),
        )
        assert r.status_code == 404

    def test_resource_meta_dates(self, wsgi, fake_user_data):
        @time_machine.travel(
            datetime.datetime(2024, 3, 14, 6, 00, tzinfo=datetime.timezone.utc)
        )
        def create_user():
            r = wsgi.post("/v2/Users", json=fake_user_data[1])
            assert r.status_code == 201
            return r.json()

        @time_machine.travel(
            datetime.datetime(2024, 3, 16, 8, 30, tzinfo=datetime.timezone.utc)
        )
        def update_user(user_id):
            r = wsgi.put(f"/v2/Users/{user_id}", json={"userName": "Foo"})
            assert r.status_code == 200
            return r.json()

        j = create_user()
        assert j["meta"]["created"] == "2024-03-14T06:00:00Z"
        assert j["meta"]["lastModified"] == "2024-03-14T06:00:00Z"

        j = update_user(j["id"])
        assert j["meta"]["created"] == "2024-03-14T06:00:00Z"
        assert j["meta"]["lastModified"] == "2024-03-16T08:30:00Z"

    def test_authentication(self, first_fake_user, provider, wsgi):
        r = wsgi.get("/v2/ServiceProviderConfig")
        assert "WWW-Authenticate" not in r.headers
        provider.register_bearer_token("SuperSecretToken")

        r = wsgi.get("/v2/ServiceProviderConfig")
        assert "WWW-Authenticate" in r.headers

        r = wsgi.get(f"/v2/Users/{first_fake_user}")
        assert r.status_code == 401

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
            headers={"Authorization": "Bearer IncorrectToken"},
        )
        assert r.status_code == 401

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
            headers={"Authorization": "Bearer SuperSecretToken"},
        )
        assert r.status_code == 200

    def test_redirect(self, wsgi):
        r = wsgi.get("/v2", follow_redirects=False)
        assert r.is_redirect
        assert r.headers["Location"] == "https://scim.example.com/v2/"
