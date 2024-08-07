from scim2_models import Context


class TestProvider:
    def test_user_creation(self, provider):
        user_model = provider.backend.get_model("User").model_validate(
            {
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
            scim_ctx=Context.RESOURCE_CREATION_REQUEST,
        )
        ret = provider.backend.create_resource("User", user_model)
        assert ret.id is not None
