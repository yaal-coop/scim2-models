import uuid

import pytest


class TestSCIMProviderMSEntraIntegration:
    """
    Tests based on Postman tests from
    https://learn.microsoft.com/en-us/entra/identity/app-provisioning/scim-validator-tutorial#use-postman-to-test-endpoints-optional
    """

    def test_endpoints(self, wsgi):
        # Endpoint tests
        # Get empty Users
        r = wsgi.get("/v2/users")
        assert r.status_code == 200

        # Get empty Groups
        r = wsgi.get("/v2/Groups")
        assert r.status_code == 200

        # Get ResourceTypes
        r = wsgi.get("/v2/ResourceTypes")
        assert r.status_code == 200
        assert r.json()["Resources"][0]["endpoint"] == "/Users"

        # Get ServiceProviderConfig
        r = wsgi.get("/v2/ServiceProviderConfig")
        assert r.status_code == 200

        # Get Schemas
        r = wsgi.get("/v2/Schemas")
        assert r.status_code == 200
        assert "User Account" in r.text

    def test_users(self, wsgi):
        # Post User
        r = wsgi.post(
            "/v2/Users",
            json={
                "UserName": "UserName123",
                "Active": True,
                "DisplayName": "BobIsAmazing",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "externalId": uuid.uuid4().hex,
                "name": {
                    "formatted": "Ryan Leenay",
                    "familyName": "Leenay",
                    "givenName": "Ryan",
                },
                "emails": [
                    {"Primary": True, "type": "work", "value": "testing@bob.com"},
                    {
                        "Primary": False,
                        "type": "home",
                        "value": "testinghome@bob.com",
                    },
                ],
            },
        )
        assert r.status_code == 201
        id1 = r.json()["id"]

        # Post EnterpriseUser
        r = wsgi.post(
            "/v2/Users",
            json={
                "UserName": "UserName222",
                "Active": True,
                "DisplayName": "lennay",
                "schemas": [
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                ],
                "externalId": uuid.uuid4().hex,
                "name": {
                    "formatted": "Adrew Ryan",
                    "familyName": "Ryan",
                    "givenName": "Andrew",
                },
                "emails": [
                    {"Primary": True, "type": "work", "value": "testing@bob2.com"},
                    {"Primary": False, "type": "home", "value": "testinghome@bob3.com"},
                ],
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "Department": "bob",
                    "Manager": {"Value": "SuzzyQ"},
                },
            },
        )
        assert r.status_code == 201
        id2 = r.json()["id"]

        # Get user1
        r = wsgi.get(f"/v2/Users/{id1}")
        assert r.status_code == 200
        assert r.json()["id"] == id1

        # Get user2
        r = wsgi.get(f"/v2/Users/{id2}")
        assert r.status_code == 200
        assert r.json()["id"] == id2

        # Get User Attributes
        r = wsgi.get("/v2/Users", params={"attributes": "userName,emails"})
        assert r.status_code == 200
        assert id1 in r.text

        # Get User Filters
        r = wsgi.get("/v2/Users", params={"filter": 'DisplayName eq "BobIsAmazing"'})
        assert r.status_code == 200
        assert id1 in r.text

        # Patch user1
        wsgi.patch(
            f"/v2/Users/{id1}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "replace", "path": "userName", "value": "ryan3"}],
            },
        )

        # Get User1 Check Patch
        r = wsgi.get(f"/v2/Users/{id1}")
        assert r.status_code == 200
        assert r.json()["id"] == id1
        assert r.json()["userName"] == "ryan3"

        # User 2 replace test
        r = wsgi.put(
            f"/v2/Users/{id2}",
            json={
                "UserName": "UserNameReplace2",
                "Active": True,
                "DisplayName": "BobIsAmazing",
                "schemas": [
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                ],
                "id": id2,
                "externalId": uuid.uuid4().hex,
                "name": {
                    "formatted": "NewName",
                    "familyName": "Leenay",
                    "givenName": "Ryan",
                },
                "emails": [
                    {
                        "Primary": True,
                        "type": "work",
                        "value": "testing@bobREPLACE.com",
                    },
                    {"Primary": False, "type": "home", "value": "testinghome@bob.com"},
                ],
            },
        )
        assert r.status_code == 200

        # Get user2 Check replace
        r = wsgi.get(f"/v2/Users/{id2}")
        assert r.status_code == 200
        assert r.json()["id"] == id2
        assert r.json()["name"]["formatted"] == "NewName"

        # Delete user1
        r = wsgi.delete(f"/v2/Users/{id1}")
        assert r.status_code == 204

        # Delete user2
        r = wsgi.delete(f"/v2/Users/{id2}")
        assert r.status_code == 204

    def test_groups(self, wsgi):
        # Create empty group
        r = wsgi.post(
            "/v2/Groups",
            json={
                "externalId": uuid.uuid4().hex,
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "Group1DisplayName",
                "members": [],
            },
        )
        assert r.status_code == 201
        group_id = r.json()["id"]

        # Create user for group 2
        r = wsgi.post(
            "/v2/Users",
            json={
                "UserName": "UserName333",
                "Active": True,
                "DisplayName": "lennay",
                "schemas": [
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                ],
                "externalId": uuid.uuid4().hex,
                "name": {
                    "formatted": "Adrew Ryan",
                    "familyName": "Ryan",
                    "givenName": "Andrew",
                },
                "emails": [
                    {"Primary": True, "type": "work", "value": "testing@bob2.com"},
                    {"Primary": False, "type": "home", "value": "testinghome@bob3.com"},
                ],
            },
        )
        assert r.status_code == 201
        id3 = r.json()["id"]

        # Create user 4 for group 2
        r = wsgi.post(
            "/v2/Users",
            json={
                "UserName": "UserName444",
                "Active": True,
                "DisplayName": "lennay",
                "schemas": [
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                ],
                "externalId": uuid.uuid4().hex,
                "name": {
                    "formatted": "Adrew Ryan",
                    "familyName": "Ryan",
                    "givenName": "Andrew",
                },
                "emails": [
                    {"Primary": True, "type": "work", "value": "testing@bob2.com"},
                    {"Primary": False, "type": "home", "value": "testinghome@bob3.com"},
                ],
            },
        )
        assert r.status_code == 201
        id4 = r.json()["id"]

        # Create filled group 2
        r = wsgi.post(
            "/v2/Groups",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "externalId": uuid.uuid4().hex,
                "displayName": "GroupDisplayName2",
                "members": [{"value": id3, "display": "VP"}],
            },
        )
        assert r.status_code == 201
        group_id_2 = r.json()["id"]

        # Get Groups
        r = wsgi.get("/v2/Groups")
        assert r.status_code == 200

        # Create group 3
        r = wsgi.post(
            "/v2/Groups",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "externalId": uuid.uuid4().hex,
                "displayName": "GroupDisplayName3",
                "members": [],
            },
        )
        assert r.status_code == 201
        group_id_3 = r.json()["id"]

        # Put replace group3
        r = wsgi.put(
            f"/v2/Groups/{group_id_3}",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": group_id_3,
                "displayName": "putName",
                "members": [
                    {"value": id3, "display": "VP"},
                    {"value": id4, "display": "SenorVP"},
                ],
            },
        )
        assert r.status_code == 200

        # Validate group 3
        r = wsgi.get(f"/v2/Groups/{group_id_3}")
        assert r.status_code == 200
        assert r.json()["id"] == group_id_3
        assert id3 in r.text

        # Patch add user4 to group1
        r = wsgi.patch(
            f"/v2/Groups/{group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "name": "addMember",
                        "op": "add",
                        "path": "members",
                        "value": [{"displayName": "new User", "value": f"{id4}"}],
                    }
                ],
            },
        )

        # Patch remove user4 to group1
        r = wsgi.patch(
            f"/v2/Groups/{group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "remove", "path": f'members[value eq "{id4}"]'}],
            },
        )

        # Patch add user4 to group1
        r = wsgi.patch(
            f"/v2/Groups/{group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "name": "addMember",
                        "op": "add",
                        "path": "members",
                        "value": [{"displayName": "new User", "value": id4}],
                    }
                ],
            },
        )

        # Get group by id
        r = wsgi.get(f"/v2/Groups/{group_id}")
        assert r.status_code == 200
        assert r.json()["id"] == group_id
        assert "new User" in r.text

        # Patch remove all users
        r = wsgi.patch(
            f"/v2/Groups/{group_id}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "remove", "path": "members"}],
            },
        )

        # Get group by id
        r = wsgi.get(f"/v2/Groups/{group_id}")
        assert r.status_code == 200
        assert r.json()["id"] == group_id
        assert "new User" not in r.text

        # Delete user3
        r = wsgi.delete(f"/v2/Users/{id3}")
        assert r.status_code == 204

        # Delete user4
        r = wsgi.delete(f"/v2/Users/{id4}")
        assert r.status_code == 204

        # Delete group 1
        r = wsgi.delete(f"/v2/Groups/{group_id}")
        assert r.status_code == 204

        # Delete group 2
        r = wsgi.delete(f"/v2/Groups/{group_id_2}")
        assert r.status_code == 204

        # Delete group 3
        r = wsgi.delete(f"/v2/Groups/{group_id_3}")
        assert r.status_code == 204

    @pytest.mark.xfail(reason="Microsoft Entra violates the SCIM protocol", strict=True)
    def test_complex_attributes(self, wsgi):
        # Create user1
        r = wsgi.post(
            "/v2/Users",
            json={
                "UserName": "UserName111",
                "Active": True,
                "DisplayName": "BobIsAmazing",
                "schemas": [
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                ],
                "externalId": uuid.uuid4().hex,
                "name": {
                    "formatted": "Ryan Leenay",
                    "familyName": "Leenay",
                    "givenName": "Ryan",
                },
                "emails": [
                    {"Primary": True, "type": "work", "value": "emailName357"},
                    {"Primary": False, "type": "home", "value": "testinghome@bob.com"},
                ],
            },
        )
        assert r.status_code == 201
        id1 = r.json()["id"]

        # Create user2
        r = wsgi.post(
            "/v2/Users",
            json={
                "UserName": "UserName222",
                "Active": True,
                "DisplayName": "BobIsAmazing",
                "schemas": [
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                ],
                "externalId": uuid.uuid4().hex,
                "name": {
                    "formatted": "Ryan Leenay",
                    "familyName": "Leenay",
                    "givenName": "Ryan",
                },
                "emails": [
                    {"Primary": True, "type": "work", "value": "jump@bob.com"},
                    {"Primary": False, "type": "home", "value": "testinghome@bob.com"},
                ],
            },
        )
        assert r.status_code == 201
        id2 = r.json()["id"]

        # Get user attributes
        r = wsgi.get("/v2/Users", params={"attributes": 'emails[type eq "work"]'})
        assert r.status_code == 200
        assert "emailName357" in r.text

        # Get user via attributes filter
        r = wsgi.get(
            "/v2/Users", params={"attributes": 'emails[value eq "emailName357"]'}
        )
        assert r.status_code == 200
        assert "emailName357" in r.text

        # Delete User1
        r = wsgi.delete(f"/v2/Users/{id1}")
        assert r.status_code == 204

        # Delete User2
        r = wsgi.delete(f"/v2/Users/{id2}")
        assert r.status_code == 204

    @pytest.mark.xfail(reason="Microsoft Entra violates the SCIM protocol", strict=True)
    def test_users_with_garbage(self, wsgi):
        # Post user "OMalley"
        r = wsgi.post(
            "/v2/Users",
            json={
                "userName": "OMalley",
                "active": True,
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@example.com"},
                    {"type": "other", "primary": False, "value": "anna33@gmail.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "OMalley",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 201
        j = r.json()
        assert j["userName"] == "OMalley"
        assert j["active"]
        id1 = j["id"]

        # Post emp1 with string "True"
        r = wsgi.post(
            "/v2/Users",
            json={
                "userName": "emp1",
                "active": "True",
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@gmail.com"},
                    {"type": "work", "primary": False, "value": "anna33@example.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "Employee",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": None, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 201
        j = r.json()
        assert j["active"]
        id2 = j["id"]

        # Get all users
        r = wsgi.get("/v2/Users")
        assert r.status_code == 200
        j = r.json()
        assert j["totalResults"] == 2
        assert "OMalley" in r.text

        # Post emp2
        r = wsgi.post(
            "/v2/Users",
            json={
                "userName": "emp2",
                "active": True,
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@gmail.com"},
                    {"type": "work", "primary": False, "value": "anna33@example.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "Employee",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 201
        id3 = r.json()["id"]

        # Post emp3
        r = wsgi.post(
            "/v2/Users",
            json={
                "userName": "emp3",
                "active": True,
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@gmail.com"},
                    {"type": "work", "primary": False, "value": "anna33@example.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "Employee",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 201
        id4 = r.json()["id"]

        # Post no username
        r = wsgi.post(
            "/v2/Users",
            json={
                "active": True,
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@gmail.com"},
                    {"type": "work", "primary": False, "value": "anna33@example.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "Employee",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 400

        # Post junk
        r = wsgi.post(
            "/v2/Users",
            headers={"Content-Type": "application/json"},
            content='{\r\n    "acve": tre,\r\n    "adadfdresses": [\r\n        {\r\n            "coudftry": "Beruda",\r\n            "formatted": "9132 Jennifer Way Suite 040\\nSouth Nancy, MI 55645",\r\n            "locality": "West Mercedes",\r\n            "postalCode": "99265",\r\n            "region": "Montana",\r\n            "streetAddress": "4939 Hess Fork",\r\n            "type": "work",\r\n            "primary": false\r\n        },\r\n        {\r\n            "country": null,\r\n            "formatted": "18522 Lisa Unions\\nEast Gregory, CT 52311",\r\n            "locality": null,\r\n          les": [],\r\n    "title": "Site engineer",\r\n    "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",\r\n    "schemas": [\r\n        "urn:ietf:params:scim:schemas:core:2.0:User"\r\n    ]\r\n}',
        )
        assert r.status_code == 400

        # Post emp3 exists
        r = wsgi.post(
            "/v2/Users",
            json={
                "userName": "emp3",
                "active": True,
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@gmail.com"},
                    {"type": "work", "primary": False, "value": "anna33@example.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "Employee",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 409
        assert "detail" in r.json()

        # Post emp3 exists try again
        r = wsgi.post(
            "/v2/Users",
            json={
                "userName": "emp3",
                "active": True,
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@gmail.com"},
                    {"type": "work", "primary": False, "value": "anna33@example.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "Employee",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 409
        assert "detail" in r.json()

        # Put a user no username
        r = wsgi.put(
            f"/v2/Users/{id1}",
            json={
                "id": id1,
                "userame": "OMalley",
                "active": False,
                "addresses": [
                    {
                        "country": "Germany",
                        "formatted": "1923 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "East Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": "bahams",
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@example.com"},
                    {"type": "other", "primary": False, "value": "anna33@gmail.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "OMalley",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 400

        # Put a user misspelled attribute
        r = wsgi.put(
            f"/v2/Users/{id1}",
            json={
                "id": id1,
                "userName": "OMalley",
                "active": False,
                "adreses": [
                    {
                        "country": "Germany",
                        "formatted": "1923 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "East Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": "bahams",
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@example.com"},
                    {"type": "other", "primary": False, "value": "anna33@gmail.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "OMalley",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 200
        assert "Addresses" not in r.text

        # Post enterprise user
        r = wsgi.post(
            "/v2/Users",
            json={
                "userName": "enterprise",
                "active": True,
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "Department": "some department",
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@gmail.com"},
                    {"type": "work", "primary": False, "value": "anna33@example.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "Employee",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": [
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                ],
            },
        )
        assert r.status_code == 201
        enteruserid = r.json()["id"]

        # Patch user omalley new username
        r = wsgi.patch(
            f"/v2/Users/{id1}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {"op": "Replace", "path": "userName", "value": "newusername"}
                ],
            },
        )
        assert r.status_code == 204

        # patch user omalley active with boolean
        r = wsgi.patch(
            f"/v2/Users/{id1}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "Replace", "path": "active", "value": False}],
            },
        )
        assert r.status_code == 204

        # get user1
        r = wsgi.get(f"/v2/Users/{id1}")
        assert r.status_code == 200
        j = r.json()
        assert j["userName"] == "newusername"
        assert not j["active"]

        # Put a user OMalley
        r = wsgi.put(
            f"/v2/Users/{id1}",
            json={
                "id": id1,
                "userName": "OMalley",
                "active": False,
                "addresses": [
                    {
                        "country": "Germany",
                        "formatted": "1923 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "East Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": "bahams",
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@example.com"},
                    {"type": "other", "primary": False, "value": "anna33@gmail.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "OMalley",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 200
        j = r.json()
        assert j["userName"] == "OMalley"
        assert not j["active"]
        assert "Germany" in r.text

        # Paginate
        r = wsgi.get("/v2/Users", params={"startIndex": "1", "count": "2"})
        j = r.json()
        assert r["totalResults"] == 5
        assert r["itemsPerPage"] == 2

        # get user attributes
        r = wsgi.get("/v2/Users", params={"attributes": "userName,emails"})
        assert r.json()["totalResults"] == 5

        # Post emp3 exists try again
        r = wsgi.post(
            "/v2/Users",
            json={
                "userName": "emp3",
                "active": True,
                "addresses": [
                    {
                        "country": "Bermuda",
                        "formatted": "9132 Jennifer Way Suite 040\nSouth Nancy, MI 55645",
                        "locality": "West Mercedes",
                        "postalCode": "99265",
                        "region": "Montana",
                        "streetAddress": "4939 Hess Fork",
                        "type": "work",
                        "primary": False,
                    },
                    {
                        "country": None,
                        "formatted": "18522 Lisa Unions\nEast Gregory, CT 52311",
                        "locality": None,
                        "postalCode": None,
                        "region": None,
                        "streetAddress": None,
                        "type": "other",
                        "primary": False,
                    },
                ],
                "displayName": "Kimberly Baker",
                "emails": [
                    {"type": "work", "primary": True, "value": "anna33@gmail.com"},
                    {"type": "work", "primary": False, "value": "anna33@example.com"},
                ],
                "meta": {
                    "created": "2019-09-18T18:15:26.5788954+00:00",
                    "lastModified": "2019-09-18T18:15:26.5788976+00:00",
                    "resourceType": "User",
                },
                "name": {
                    "formatted": "Daniel Mcgee",
                    "familyName": "Employee",
                    "givenName": "Darl",
                    "honorificPrefix": None,
                    "honorificSuffix": None,
                },
                "phoneNumbers": [
                    {"type": "fax", "primary": False, "value": "312-320-0500"},
                    {"type": "mobile", "primary": False, "value": "312-320-1707"},
                    {"type": "work", "primary": True, "value": "312-320-0932"},
                ],
                "preferredLanguage": "xh",
                "roles": [],
                "title": "Site engineer",
                "externalId": "22fbc523-6032-4c5f-939d-5d4850cf3e52",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            },
        )
        assert r.status_code == 409
        assert "detail" in j.json()

        # filter eq and (val or val)
        r = wsgi.get(
            "/v2/Users",
            params={
                "filter": "name.FamilyName eq Employee and (emails.Value co example.com or emails.Value co example.org)"
            },
        )
        assert r.json()["totalResults"] == 4

        # filter starts with
        r = wsgi.get("/v2/Users", params={"filter": "userName sw O"})
        assert r.json()["totalResults"] == 1

        # filter greater than
        r = wsgi.get(
            "/v2/Users",
            params={"filter": "meta.Created gt 2015-10-10T14:38:21.8617979-07:00"},
        )
        assert r.json()["totalResults"] == 5

        # = Teardown garbage =
        # Delete user 1
        r = wsgi.delete(f"/v2/Users/{id1}")
        assert r.status_code == 204

        # Delete user 2
        r = wsgi.delete(f"/v2/Users/{id2}")
        assert r.status_code == 204

        # Delete user3 emp2
        r = wsgi.delete(f"/v2/Users/{id3}")
        assert r.status_code == 204

        # Delete user4 emp3
        r = wsgi.delete(f"/v2/Users/{id4}")
        assert r.status_code == 204

        # Delete enterprise user
        r = wsgi.delete(f"/v2/Users/{enteruserid}")
        assert r.status_code == 204

        # Get all users
        r = wsgi.get("/v2/Users", params={"attributes": "userName"})
        assert r.status_code == 200
        assert r.json()["Resources"] == []

    def test_groups_with_garbage(self, wsgi):
        # Post group
        r = wsgi.post(
            "/v2/Groups",
            json={
                "displayName": "Group 1",
                "externalId": "015489ea-9410-4306-b583-9f002b2446f7",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            },
        )
        assert r.status_code == 201
        group1 = r.json()["id"]

        # Group patch add member
        r = wsgi.patch(
            f"/v2/Groups/{group1}",
            json={
                "id": group1,
                "Operations": [
                    {"op": "add", "path": "members", "value": "string id 1"}
                ],
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            },
        )
        assert r.status_code == 204

        # Group patch add member2
        r = wsgi.patch(
            f"/v2/Groups/{group1}",
            json={
                "id": group1,
                "Operations": [
                    {"op": "add", "path": "members", "value": "string id 2"}
                ],
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            },
        )
        assert r.status_code == 204

        # Get group
        r = wsgi.get(f"/v2/Groups/{group1}")
        assert r.status_code == 200

        # Get group exclude members
        r = wsgi.get(f"/v2/Groups/{group1}", params={"excludedAttributes": "members"})
        assert r.status_code == 200

        # group put
        r = wsgi.put(
            f"/v2/Groups/{group1}",
            json={
                "id": group1,
                "displayName": "Tiffany Ortiz",
                "externalId": "6c6b54c2-fa81-4234-ad4f-420ec6808049",
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            },
        )
        assert r.status_code == 200
        assert r.json()["displayName"] == "Tiffany Ortiz"

        # = Teardown garbage =
        # Delete group 1
        r = wsgi.delete(f"/v2/Groups/{group1}")
        assert r.status_code == 204

        # Get all groups
        r = wsgi.get("/v2/Groups")
        assert r.status_code == 200
        assert r.json()["Resources"] == []
