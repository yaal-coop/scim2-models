import pytest
from scim2_models import PatchOperation

from scim_provider.operators import patch_resource
from scim_provider.utils import SCIMException


class TestPatch:
    def test_patch_operation_add_simple(self, provider):
        user = provider.backend.get_model("User")(id="123")
        patch_resource(
            user,
            PatchOperation(
                op=PatchOperation.Op.add,
                value={
                    "userName": "Foo",
                },
            ),
        )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "userName": "Foo",
        }
        patch_resource(
            user,
            PatchOperation(
                op=PatchOperation.Op.add,
                value={
                    "userName": "Bar",
                },
            ),
        )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "userName": "Bar",
        }
        with pytest.raises(SCIMException, match="mutability"):
            patch_resource(
                user,
                PatchOperation(
                    op=PatchOperation.Op.add,
                    value={
                        "id": "4",
                    },
                ),
            )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "userName": "Bar",
        }

    def test_patch_operation_add_complex(self, provider):
        user = provider.backend.get_model("User")(id="123")
        patch_resource(
            user,
            PatchOperation(
                op=PatchOperation.Op.add,
                value={
                    "name": {"formatted": "Mr. Foo"},
                },
            ),
        )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "name": {
                "formatted": "Mr. Foo",
            },
        }
        patch_resource(
            user,
            PatchOperation(
                op=PatchOperation.Op.add,
                value={
                    "name": {"givenName": "Baz"},
                },
            ),
        )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "name": {
                "givenName": "Baz",
            },
        }
        patch_resource(
            user,
            PatchOperation(
                op=PatchOperation.Op.add,
                path="name",
                value={
                    "formatted": "Mr. Foo",
                },
            ),
        )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "name": {
                "formatted": "Mr. Foo",
            },
        }
        patch_resource(
            user,
            PatchOperation(
                op=PatchOperation.Op.add,
                path="name.familyName",
                value="Jensen",
            ),
        )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "name": {
                "formatted": "Mr. Foo",
                "familyName": "Jensen",
            },
        }

    def test_patch_operation_add_multi_valued(self, provider):
        user = provider.backend.get_model("User")(id="123")
        patch_resource(
            user,
            PatchOperation(
                op=PatchOperation.Op.add,
                path="emails",
                value={
                    "value": "foo@example.com",
                    "type": "work",
                    "primary": True,
                },
            ),
        )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "emails": [
                {
                    "value": "foo@example.com",
                    "type": "work",
                    "primary": True,
                }
            ],
        }
        patch_resource(
            user,
            PatchOperation(
                op=PatchOperation.Op.add,
                path="emails",
                value={
                    "value": "bar@example.com",
                    "type": "home",
                    "primary": True,
                },
            ),
        )
        assert user.model_dump() == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "123",
            "emails": [
                {
                    "value": "foo@example.com",
                    "type": "work",
                    "primary": False,
                },
                {
                    "value": "bar@example.com",
                    "type": "home",
                    "primary": True,
                },
            ],
        }
