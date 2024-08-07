class TestSCIMProviderETags:
    def test_resource_get_etag_match(self, wsgi, first_fake_user):
        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
        )
        assert r.status_code == 200
        j = r.json()
        initial_version = j["meta"]["version"]
        assert r.headers["etag"] == initial_version

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}", headers={"If-None-Match": initial_version}
        )
        assert r.status_code == 304

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}", headers={"If-None-Match": 'W/"abc", *'}
        )
        assert r.status_code == 304

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}", headers={"If-None-Match": 'W/"abc"'}
        )
        assert r.status_code == 200

        r = wsgi.get(f"/v2/Users/{first_fake_user}", headers={"If-Match": 'W/"abc"'})
        assert r.status_code == 304

        r = wsgi.get(f"/v2/Users/{first_fake_user}", headers={"If-Match": "*"})
        assert r.status_code == 200

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
            headers={
                "If-Match": "*",
                "If-None-Match": "*",
            },
        )
        assert r.status_code == 304

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
            headers={
                "If-Match": initial_version,
                "If-None-Match": initial_version,
            },
        )
        assert r.status_code == 304

    def test_resource_put_etag_match(self, wsgi, first_fake_user):
        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
        )
        assert r.status_code == 200
        j = r.json()
        initial_version = j["meta"]["version"]
        assert r.headers["etag"] == initial_version

        r = wsgi.put(
            f"/v2/Users/{first_fake_user}",
            json={
                "userName": "Foo",
            },
            headers={
                "If-Match": initial_version,
            },
        )
        assert r.status_code == 200
        j = r.json()
        assert j["userName"] == "Foo"
        new_version = r.headers["etag"]
        assert j["meta"]["version"] == new_version
        assert new_version != initial_version

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
        )
        assert r.status_code == 200
        j = r.json()
        assert new_version == j["meta"]["version"]

        r = wsgi.put(
            f"/v2/Users/{first_fake_user}",
            json={
                "userName": "Bar",
            },
            headers={
                "If-Match": initial_version,
            },
        )
        assert r.status_code == 412

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
        )
        assert r.json()["userName"] == "Foo"

    def test_resource_patch_etag_match(self, wsgi, first_fake_user):
        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
        )
        assert r.status_code == 200
        j = r.json()
        initial_version = j["meta"]["version"]
        assert r.headers["etag"] == initial_version

        r = wsgi.patch(
            f"/v2/Users/{first_fake_user}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "add", "path": "userName", "value": "Foo"}],
            },
            headers={
                "If-Match": initial_version,
            },
        )
        assert r.status_code == 204
        new_version = r.headers["etag"]
        assert new_version != initial_version

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
        )
        assert r.status_code == 200
        j = r.json()
        assert new_version == j["meta"]["version"]

        r = wsgi.patch(
            f"/v2/Users/{first_fake_user}",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "add", "path": "userName", "value": "Bar"}],
            },
            headers={
                "If-Match": initial_version,
            },
        )
        assert r.status_code == 412

        r = wsgi.get(
            f"/v2/Users/{first_fake_user}",
        )
        assert r.json()["userName"] == "Foo"
