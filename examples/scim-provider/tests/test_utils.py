from typing import Annotated
from typing import List
from typing import Optional

import pytest
from scim2_filter_parser.lexer import SCIMLexer
from scim2_filter_parser.parser import SCIMParser
from scim2_models import Context
from scim2_models import EnterpriseUser
from scim2_models import Meta
from scim2_models import Mutability
from scim2_models import Name
from scim2_models import Resource
from scim2_models import User

from scim_provider.filter import evaluate_filter
from scim_provider.operators import ResolveOperator
from scim_provider.utils import SCIMException
from scim_provider.utils import get_or_create
from scim_provider.utils import is_multi_valued
from scim_provider.utils import merge_resources


class TestUtils:
    def test_case_sensitivity(self):
        u = User[EnterpriseUser].model_validate(
            {
                "userName": "abc",
                "displayName": "Barbara Jensen",
                "name": {
                    "formatted": "Barbara Jensen",
                },
                "active": True,
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "employeeNumber": "1234"
                },
            }
        )
        assert u.display_name == "Barbara Jensen"

        u.model_dump(
            scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
            attributes=[
                "displayname",
                "urn:IETF:params:scim:schemas:core:2.0:User:userName",
                "urn:IETF:params:scim:schemas:core:2.0:User:name.FORMATTED",
                "acTIVe",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:Employeenumber",
            ],
        )

    def test_match_filter(self, provider):
        user = provider.backend.get_model("User").model_validate(
            {
                "schemas": [
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                ],
                "userName": "ABC",
                "name": {"formatted": "DEF"},
                "password": "(Rtk_Nuyz5",
                "title": "Vice President",
                "userType": "Employee",
                "active": True,
                "emails": [
                    {"value": "foo@example.com", "type": "work"},
                    {"value": "bar@example.com", "type": "home"},
                    {"value": "home2@example.net", "type": "home"},
                ],
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "employeeNumber": "X",
                },
                "meta": {
                    "resourceType": "User",
                    "created": "2024-08-01T12:40:00Z",
                    "lastModified": "2024-08-02T15:15:00Z",
                },
            },
        )

        def evaluate(filter_str: str) -> bool:
            token_stream = SCIMLexer().tokenize(filter_str)
            tree = SCIMParser().parse(token_stream)
            return evaluate_filter(user, tree)

        assert evaluate("userName pr")
        assert not evaluate("not(userName pr)")
        assert evaluate('userName eq "ABC"')
        assert evaluate('urn:ietf:params:scim:schemas:core:2.0:User:userName eq "ABC"')
        assert evaluate(
            'urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:employeeNumber sw "X"'
        )
        assert evaluate('userName co "B"')
        assert evaluate('userName co "b"')
        assert evaluate('userName gt "A"')
        assert evaluate('userName ge "A"')
        assert not evaluate('userName lt "A"')
        assert not evaluate('userName le "A"')
        assert evaluate('userName eq "A" or userName eq "ABC"')
        assert not evaluate('not(userName gt "A")')
        assert not evaluate('userName gt "B"')
        assert evaluate('userName sw "ABC"')
        assert evaluate('userName eq "abc"')
        assert not evaluate('userName sw "C"')
        assert evaluate('userName sw "a"')
        assert evaluate('not (userName eq "DEF")')
        assert evaluate('name.formatted eq "DEF"')
        assert evaluate('name.formatted eq "def"')
        assert evaluate('meta.created ge "2019-05-13T04:42:34Z"')
        assert evaluate('meta.created gt "2019-05-13T04:42:34Z"')
        assert not evaluate('meta.created le "2019-05-13T04:42:34Z"')
        assert not evaluate('meta.created lt "2019-05-13T04:42:34Z"')
        assert evaluate('meta.created eq "2024-08-01T12:40:00Z"')
        assert evaluate('meta.created lt "2025-01-01T00:00:00Z"')

        with pytest.raises(SCIMException, match="sensitive"):
            # Password is sensitive (never returned), filter must not match
            # to not reveal any information about the value
            assert not evaluate('password sw "(Rtk_"')

        assert evaluate('emails[type eq "home"]')
        assert evaluate('not (emails[type eq "other"])')
        assert not evaluate("not (emails[value pr])")
        assert not evaluate('emails[type eq "foo"]')
        assert evaluate('emails[value pr].type co "home"')
        assert not evaluate('emails[value pr].value co "x@example.com"')

        with pytest.raises(SCIMException, match="noTarget"):
            assert not evaluate('name[type eq "foo"]')

        with pytest.raises(SCIMException, match="invalidFilter"):
            assert not evaluate("active gt 5")

        with pytest.raises(SCIMException, match="invalidFilter"):
            assert not evaluate("active lt 5")

        with pytest.raises(SCIMException, match="invalidFilter"):
            assert not evaluate("active ge 5")

        with pytest.raises(SCIMException, match="invalidFilter"):
            assert not evaluate("active le 5")

        # Filters based on examples from RFC 7644, Section 3.4.2.2
        assert not evaluate('userName eq "bjensen"')
        assert not evaluate('name.familyName co "O\'Malley"')
        assert not evaluate('userName sw "J"')
        assert not evaluate(
            'urn:ietf:params:scim:schemas:core:2.0:User:userName sw "J"'
        )
        assert evaluate('urn:ietf:params:scim:schemas:core:2.0:User:userName sw "A"')
        assert evaluate("title pr")
        assert evaluate('meta.lastModified gt "2011-05-13T04:42:34Z"')
        assert evaluate('meta.lastModified ge "2011-05-13T04:42:34Z"')
        assert not evaluate('meta.lastModified lt "2011-05-13T04:42:34Z"')
        assert not evaluate('meta.lastModified le "2011-05-13T04:42:34Z"')
        assert evaluate('title pr and userType eq "Employee"')
        assert evaluate('title pr or userType eq "Intern"')
        assert not evaluate(
            'schemas eq "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"'
        )
        assert not evaluate(
            'userType eq "Employee" and (emails co "example.com" or emails.value co "example.org")'
        )
        assert evaluate(
            'userType eq "Employee" and (emails co "example.com" or emails.value co "bar@example.com")'
        )
        assert not evaluate(
            'userType ne "Employee" and not (emails co "example.com" or emails.value co "example.org")'
        )
        assert not evaluate('userType eq "Employee" and (emails.type eq "work")')
        assert evaluate(
            'userType eq "Employee" and emails[type eq "work" and value co "@example.com"]'
        )
        assert evaluate(
            'emails[type eq "work" and value co "@example.com"] or ims[type eq "xmpp" and value co "@foo.com"]'
        )

    def test_attribute_resolving(self, provider):
        user = provider.backend.get_model("User").model_validate(
            {
                "schemas": [
                    "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                    "urn:ietf:params:scim:schemas:core:2.0:User",
                ],
                "userName": "ABC",
                "name": {"formatted": "DEF"},
                "emails": [
                    {"value": "foo@example.com", "type": "work"},
                    {"value": "bar@example.com", "type": "home"},
                    {"value": "home2@example.net", "type": "home"},
                ],
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "employeeNumber": "X",
                },
            },
            scim_ctx=Context.RESOURCE_CREATION_REQUEST,
        )

        def validate(
            path,
            expected_value,
            expected_attr_name,
            expected_sub_attribute_name,
            expected_class_name,
        ):
            result = ResolveOperator(path)(user)
            value = result.get_values()
            if expected_value is not None:
                assert value == expected_value
            assert expected_class_name in repr(result.model)
            assert result.attribute == expected_attr_name
            assert result.sub_attribute == expected_sub_attribute_name
            return value

        validate(
            "urn:ietf:params:scim:schemas:core:2.0:User:userName",
            "ABC",
            "user_name",
            None,
            "User[EnterpriseUser]",
        )
        validate("userName", "ABC", "user_name", None, "User[EnterpriseUser]")
        validate(
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:employeeNumber",
            "X",
            "employee_number",
            None,
            "EnterpriseUser[EnterpriseUser]",
        )
        emails = validate("emails", None, "emails", None, "User[EnterpriseUser]")
        assert len(emails) == 3
        assert emails[0].value == "foo@example.com"
        assert emails[0].type == "work"

        validate("name.formatted", "DEF", "formatted", None, "Name")
        assert validate("name.givenName", None, "given_name", None, "Name") is None

        emails = validate(
            'emails[type eq "work"]', None, "emails", None, "User[EnterpriseUser]"
        )
        assert emails.value == "foo@example.com"
        assert emails.type == "work"

        emails_fully_qualified = validate(
            'urn:ietf:params:scim:schemas:core:2.0:User:emails[type eq "work"]',
            None,
            "emails",
            None,
            "User[EnterpriseUser]",
        )
        assert emails == emails_fully_qualified

        validate(
            'emails[type eq "work"].value',
            "foo@example.com",
            "emails",
            "value",
            "Emails",
        )

        validate(
            'emails[type eq "work" or value ew "example.net"].value',
            [
                "foo@example.com",
                "home2@example.net",
            ],
            "emails",
            "value",
            "Emails",
        )

        validate(
            'emails[not (type eq "work") and value pr].value',
            ["bar@example.com", "home2@example.net"],
            "emails",
            "value",
            "Emails",
        )

    def test_dump_creation(self, provider):
        user = User(id="1", user_name="ABC")
        user.name = Name(formatted="Barbara")
        user.meta = Meta(
            resource_type="User",
            location="/v2/Users/foo",
        )
        user.mark_with_schema()
        user.model_dump(scim_ctx=Context.RESOURCE_CREATION_RESPONSE)

    def test_dump_extension(self, provider):
        user = User[EnterpriseUser].model_validate(
            {
                "userName": "thomas38@harding-herman.com",
                "displayName": "Misc. Michael Rodriguez",
                "name": {
                    "givenName": "Michael",
                    "familyName": "Rodriguez",
                    "formatted": "Misc. Michael Rodriguez",
                    "honorificPrefix": "Misc.",
                    "honorificSuffix": "",
                },
                "active": True,
                "password": "&U+VPTt%(3",
                "emails": [
                    {
                        "value": "thomas38@harding-herman.com",
                        "type": "work",
                        "primary": True,
                    },
                    {
                        "value": "christine08@gmail.com",
                        "type": "home",
                        "primary": False,
                    },
                ],
                "phoneNumbers": [],
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
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "employeeNumber": "80612",
                    "organization": "Randolph Group",
                },
            }
        )
        assert user.model_dump(
            scim_ctx=Context.RESOURCE_CREATION_RESPONSE, attributes=["userName"]
        ) == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "userName": "thomas38@harding-herman.com",
        }
        assert user.model_dump(
            scim_ctx=Context.RESOURCE_CREATION_RESPONSE,
            attributes=[
                "userName",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:employeeNumber",
            ],
        ) == {
            "schemas": [
                "urn:ietf:params:scim:schemas:core:2.0:User",
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
            ],
            "userName": "thomas38@harding-herman.com",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                "employeeNumber": "80612",
            },
        }

    def test_merge_resources_immutable(self):
        class Foo(Resource):
            schemas: List[str] = ["urn:example:2.0:Foo"]
            immutable_string: Annotated[Optional[str], Mutability.immutable] = None

        stored = Foo()
        merge_resources(stored, Foo(immutable_string="ABC"))
        assert stored.immutable_string == "ABC"
        merge_resources(stored, Foo(immutable_string="ABC"))
        with pytest.raises(SCIMException, match="mutability"):
            merge_resources(stored, Foo(immutable_string="D"))

    def test_is_multi_valued(self):
        class Foo(Resource):
            schemas: List[str] = ["urn:example:2.0:Foo"]
            some_string: Optional[str] = None
            multi_valued_string: Optional[List[str]] = None

        res = Foo()
        assert is_multi_valued(res, "schemas")
        assert not is_multi_valued(res, "some_string")
        assert is_multi_valued(res, "multi_valued_string")

    def test_get_or_create_mutability(self):
        u = User()
        with pytest.raises(SCIMException, match="immutable"):
            get_or_create(u, "groups", True)
