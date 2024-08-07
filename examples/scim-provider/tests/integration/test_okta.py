import datetime


class TestSCIMProviderOktaIntegration:
    """
    Tests based on Runscope Spec Test JSON from
    https://developer.okta.com/docs/guides/scim-provisioning-integration-prepare/main/#test-your-scim-api
    """

    OKTA_HEADERS = {
        "Accept-Charset": "utf-8",
        "Content-Type": "application/scim+json; charset=utf-8",
        "Accept": "application/scim+json",
        "User-Agent": "OKTA SCIM Integration",
    }

    def test_okta_integration(self, wsgi):
        # https://developer.okta.com/docs/guides/scim-provisioning-integration-prepare/main/#customize-the-imported-runscope-test-for-your-scim-integration
        invalid_user_email = "abcdefgh@example.com"
        random_email = "Runscope300Hfluaklab151@example.com"
        random_family_name = "Hfluaklab151"
        random_given_name = "Runscope300"
        random_user_name = "Runscope300Hfluaklab151@example.com"
        random_user_name_caps = "RUNSCOPE300HFLUAKLAB151@example.com"
        user_id_that_does_not_exist = "010101001010101011001010101011"

        # Setup: insert one user
        r = wsgi.post(
            "/v2/Users",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": "bjensen@example.com",
                "name": {
                    "givenName": "Barbara",
                    "familyName": "Jensen",
                },
                "emails": [
                    {"primary": True, "value": "bjensen@example.com", "type": "work"}
                ],
                "displayName": "Barbara Jensen",
                "active": True,
            },
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 201

        # Required Test: Test Users endpoint
        r = wsgi.get(
            "/v2/Users",
            params={"count": "1", "startIndex": "1"},
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 200
        j = r.json()
        assert j["Resources"]
        assert "urn:ietf:params:scim:api:messages:2.0:ListResponse" in j["schemas"]
        assert isinstance(j["itemsPerPage"], int)
        assert isinstance(j["startIndex"], int)
        assert isinstance(j["totalResults"], int)
        assert j["Resources"][0]["id"]
        assert j["Resources"][0]["name"]["familyName"]
        assert j["Resources"][0]["name"]["givenName"]
        assert j["Resources"][0]["userName"]
        assert j["Resources"][0]["active"] is not None
        assert j["Resources"][0]["emails"][0]["value"] is not None
        isv_user_id = j["Resources"][0]["id"]

        # Required Test: Get Users/{{id}}
        r = wsgi.get(f"/v2/Users/{isv_user_id}", headers=self.OKTA_HEADERS)
        assert r.status_code == 200
        j = r.json()
        assert j["id"]
        assert j["name"]["familyName"]
        assert j["name"]["givenName"]
        assert j["userName"]
        assert j["active"] is not None
        assert j["emails"][0]["value"] is not None
        assert j["id"] == isv_user_id

        # Required Test: Test invalid User by username
        r = wsgi.get(
            "/v2/Users",
            params={"filter": f'userName eq "{invalid_user_email}"'},
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 200
        j = r.json()
        assert "urn:ietf:params:scim:api:messages:2.0:ListResponse" in j["schemas"]
        assert j["totalResults"] == 0

        # Required Test: Test invalid User by ID
        r = wsgi.get(
            f"/v2/Users/{user_id_that_does_not_exist}", headers=self.OKTA_HEADERS
        )
        assert r.status_code == 404
        j = r.json()
        assert "detail" in j
        assert "urn:ietf:params:scim:api:messages:2.0:Error" in j["schemas"]

        # Required Test: Make sure random user doesn't exist
        r = wsgi.get(
            "/v2/Users",
            params={"filter": f'userName eq "{random_email}"'},
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 200
        j = r.json()
        assert "urn:ietf:params:scim:api:messages:2.0:ListResponse" in j["schemas"]
        assert j["totalResults"] == 0

        # Required Test: Create Okta user with realistic values
        r = wsgi.post(
            "/v2/Users",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": random_user_name,
                "name": {
                    "givenName": random_given_name,
                    "familyName": random_family_name,
                },
                "emails": [{"primary": True, "value": random_email, "type": "work"}],
                "displayName": f"{random_given_name} {random_family_name}",
                "active": True,
            },
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 201
        j = r.json()
        assert j["active"]
        assert j["name"]["familyName"] == random_family_name
        assert j["name"]["givenName"] == random_given_name
        assert "urn:ietf:params:scim:schemas:core:2.0:User" in j["schemas"]
        assert j["userName"] == random_user_name
        assert j["emails"][0]["value"] == random_email
        idUserOne = j["id"]

        # Required Test: Verify that user was created
        r = wsgi.get(f"/v2/Users/{idUserOne}", headers=self.OKTA_HEADERS)
        assert r.status_code == 200
        j = r.json()
        assert j["userName"] == random_user_name
        assert j["name"]["familyName"] == random_family_name
        assert j["name"]["givenName"] == random_given_name

        # Required Test: Expect failure when recreating user with same values
        r = wsgi.post(
            "/v2/Users",
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": random_user_name,
                "name": {
                    "givenName": random_given_name,
                    "familyName": random_family_name,
                },
                "emails": [
                    {"primary": True, "value": random_user_name, "type": "work"}
                ],
                "displayName": f"{random_given_name} {random_family_name}",
                "active": True,
            },
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 409

        # Required Test: Username Case Sensitivity Check
        r = wsgi.get(
            "/v2/Users",
            params={"filter": f'userName eq "{random_user_name_caps}"'},
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 200
        # Test not in SPEC test, but it probably should be:
        assert r.json()["totalResults"] == 1

        # Optional Test: Verify Groups endpoint
        r = wsgi.get(
            "/v2/Groups",
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 200
        assert r.elapsed < datetime.timedelta(seconds=0.6)
        j = r.json()
        assert isinstance(j["totalResults"], int)
        assert isinstance(j["Resources"], list)

        # Required Test: Check status 404
        r = wsgi.get(
            f"/v2/Users/{user_id_that_does_not_exist}",
            headers=self.OKTA_HEADERS,
        )
        assert r.status_code == 404
        j = r.json()
        assert "detail" in j
        assert j["status"] == "404"
        assert "urn:ietf:params:scim:api:messages:2.0:Error" in j["schemas"]
