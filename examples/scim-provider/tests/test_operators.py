import base64
import datetime
from typing import List
from typing import Optional

import pytest
from scim2_models import BaseModel
from scim2_models import CaseExact
from scim2_models import Email
from scim2_models import EnterpriseUser
from scim2_models import GroupMembership
from scim2_models import Name
from scim2_models import Resource
from scim2_models import User
from scim2_models import X509Certificate

from scim_provider.operators import AddOperator
from scim_provider.operators import RemoveOperator
from scim_provider.operators import ReplaceOperator
from scim_provider.operators import ResolveOperator
from scim_provider.operators import ResolveResult
from scim_provider.operators import ResolveSortOperator
from scim_provider.operators import parse_attribute_path
from scim_provider.utils import SCIMException


class TestOperators:
    def test_path_resolving(self):
        assert parse_attribute_path("") == {}
        assert parse_attribute_path("a") == {
            "attribute": "a",
            "condition": None,
            "sub_attribute": None,
        }
        assert parse_attribute_path("a.b") == {
            "attribute": "a",
            "condition": None,
            "sub_attribute": "b",
        }
        assert parse_attribute_path("a[x eq 5]") == {
            "attribute": "a",
            "condition": "x eq 5",
            "sub_attribute": None,
        }
        assert parse_attribute_path("a[x eq 5].b") == {
            "attribute": "a",
            "condition": "x eq 5",
            "sub_attribute": "b",
        }
        with pytest.raises(SCIMException, match="invalidPath"):
            assert parse_attribute_path("%invalid$$path")
        with pytest.raises(SCIMException, match="invalidPath"):
            assert parse_attribute_path(".a..b[x]")
        with pytest.raises(SCIMException, match="invalidPath"):
            assert parse_attribute_path("\\x")

    def test_simple_add_operator_unset_single_valued(self):
        u = User()
        AddOperator.operation(u, "userName", "foo")
        assert u.user_name == "foo"

    def test_simple_add_operator_single_valued(self):
        u = User(user_name="foo")
        AddOperator.operation(u, "userName", "bar")
        assert u.user_name == "bar"

    def test_simple_add_operator_multi_valued(self):
        u = User()
        AddOperator.operation(
            u, "emails", {"type": "work", "primary": True, "value": "work@example.com"}
        )
        assert u.emails == [Email(type="work", value="work@example.com", primary=True)]

    def test_simple_add_operator_multi_valued_primary(self):
        u = User()
        AddOperator.operation(
            u, "emails", {"type": "work", "primary": True, "value": "work@example.com"}
        )
        AddOperator.operation(
            u, "emails", {"type": "home", "primary": True, "value": "home@example.com"}
        )
        assert u.emails == [
            Email(type="work", value="work@example.com", primary=False),
            Email(type="home", value="home@example.com", primary=True),
        ]

    def test_simple_add_operator_immutable(self):
        u = User()
        with pytest.raises(SCIMException, match="mutability"):
            AddOperator.operation(u, "id", "123")
        u.id = "123"
        AddOperator.operation(u, "id", "123")
        assert u.id == "123"

    def test_simple_add_operator_invalid_value(self):
        u = User()
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator.operation(u, "userName", {})
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator.operation(u, "emails", "abc")
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator.operation(u, "emails", {"foo": 123})

    def test_simple_add_operator_bool_value_parsing(self):
        u = User()
        AddOperator.operation(u, "active", "True")
        assert u.active

        AddOperator.operation(u, "active", 1)
        assert u.active

        AddOperator.operation(u, "active", 0)
        assert not u.active

        AddOperator.operation(u, "active", "False")
        assert not u.active

    def test_add_operator_root_object(self):
        u = User()
        AddOperator(
            None,
            {
                "userName": "foo",
                "name": {
                    "formatted": "Mr. Foo",
                },
            },
        )(u)
        assert u.user_name == "foo"
        assert u.name == Name(formatted="Mr. Foo")

    def test_add_operator_fully_qualified_attribute_name(self):
        u = User()
        AddOperator(
            None, {"urn:ietf:params:scim:schemas:core:2.0:User:userName": "foo"}
        )(u)
        assert u.user_name == "foo"

    def test_add_operator_overwrite_required_attribute(self):
        u = User(user_name="A")
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator("userName", "")(u)

    def test_add_operator_multi_valued_list(self):
        u = User()
        AddOperator(
            None,
            {
                "emails": [
                    {"type": "work", "primary": True, "value": "work@example.com"},
                    {"type": "other", "primary": False, "value": "other@example.com"},
                ]
            },
        )(u)
        assert u.emails == [
            Email(type="work", value="work@example.com", primary=True),
            Email(type="other", value="other@example.com", primary=False),
        ]

    def test_add_operator_root_object_invalid_value(self):
        u = User()
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator(None, "abc")(u)
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator(None, 1)(u)
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator(None, [1, 2, 3])(u)

    def test_add_operator_simple_attribute(self):
        u = User()
        AddOperator("userName", "foo")(u)
        assert u.user_name == "foo"

    def test_add_operator_complex_attribute(self):
        u = User()
        AddOperator("name.formatted", "foo")(u)
        assert u.name == Name(formatted="foo")

        AddOperator("name.givenName", "bar")(u)
        assert u.name == Name(formatted="foo", givenName="bar")

    def test_add_operator_complex_attribute_invalid_path(self):
        u = User()
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator('name[givenName eq "Foo"]', "foo")(u)

        with pytest.raises(SCIMException, match="invalidPath"):
            AddOperator('name[givenName eq "Foo"].formatted', "foo")(u)

        with pytest.raises(SCIMException, match="invalidPath"):
            AddOperator('name[givenName eq "Foo"]', {"formatted": "foo"})(u)

    def test_add_operator_multi_valued_attribute_invalid_path(self):
        u = User()
        with pytest.raises(SCIMException, match="invalidPath"):
            AddOperator("emails.value", "work@example.com")(u)

    def test_add_operator_multi_valued_attribute_mutability(self):
        u = User()
        with pytest.raises(SCIMException, match="immutable"):
            AddOperator(
                "groups",
                {
                    "value": "x",
                    "type": "direct",
                },
            )(u)

    def test_add_operator_multi_valued_complex_attribute(self):
        u = User(
            emails=[
                Email(value="work@example.com", primary=True),
                Email(value="home@example.com", type="home", primary=False),
            ]
        )
        AddOperator('emails[value eq "work@example.com"]', {"type": "work"})(u)
        assert u.emails == [
            Email(value="work@example.com", type="work", primary=True),
            Email(value="home@example.com", type="home", primary=False),
        ]

    def test_add_operator_multi_valued_complex_attribute_multiple_matches(self):
        u = User(
            emails=[
                Email(value="work@example.com", primary=True),
                Email(value="home@example.com", type="home", primary=False),
            ]
        )
        AddOperator('emails[value ew "@example.com"]', {"type": "home"})(u)
        assert u.emails == [
            Email(value="work@example.com", type="home", primary=True),
            Email(value="home@example.com", type="home", primary=False),
        ]

    def test_add_operator_multi_valued_complex_attribute_sub_attribute(self):
        u = User(
            emails=[
                Email(value="work@example.com", primary=True),
                Email(value="home@example.com", type="home", primary=False),
            ]
        )
        AddOperator('emails[value eq "work@example.com"].type', "work")(u)
        assert u.emails == [
            Email(value="work@example.com", type="work", primary=True),
            Email(value="home@example.com", type="home", primary=False),
        ]

    def test_add_operator_multi_valued_complex_attribute_sub_attribute_multiple_matches(
        self,
    ):
        u = User(
            emails=[
                Email(value="work@example.com", primary=False),
                Email(value="home@example.com", type="home", primary=False),
            ]
        )
        AddOperator("emails[value pr].type", "home")(u)
        assert u.emails == [
            Email(value="work@example.com", type="home", primary=False),
            Email(value="home@example.com", type="home", primary=False),
        ]

    def test_add_operator_multi_valued_complex_attribute_value_only(self):
        u = User()
        AddOperator("emails", "work@example.com")(u)
        assert u.emails == [
            Email(value="work@example.com"),
        ]
        with pytest.raises(SCIMException, match="invalidValue"):
            AddOperator("name", "Mr. Foo")(u)

    def test_add_operator_binary_data(self):
        u = User()
        AddOperator("x509Certificates", {"value": base64.b64encode(b"1234567")})(u)
        assert u.x509_certificates == [
            # https://github.com/yaal-coop/scim2-models/issues/31
            # Should be value=b"1234567"
            X509Certificate(value=b"MTIzNDU2Nw==")
        ]

    def test_add_operator_datetime(self):
        class Foo(Resource):
            schemas: List[str] = ["urn:example:2.0:Foo"]
            dt: Optional[datetime.datetime] = None

        f = Foo()
        AddOperator("dt", "2010-01-23T04:56:22Z")(f)
        assert f.dt == datetime.datetime(
            2010, 1, 23, 4, 56, 22, tzinfo=datetime.timezone.utc
        )

    def test_add_operator_extension_simple(self):
        u = User[EnterpriseUser]()
        AddOperator(
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:employeeNumber",
            "1234",
        )(u)
        assert u.schemas == [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        ]
        assert u.EnterpriseUser.employee_number == "1234"

    def test_add_operator_extension_complex(self):
        u = User[EnterpriseUser]()
        AddOperator(
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:manager.value",
            "1234",
        )(u)
        assert u.schemas == [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        ]
        assert u.EnterpriseUser.manager.value == "1234"

    def test_add_operator_extension_path(self):
        u = User[EnterpriseUser]()
        AddOperator(
            None,
            {
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "employeeNumber": "1234"
                }
            },
        )(u)
        assert u.schemas == [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        ]
        assert u.EnterpriseUser.employee_number == "1234"

    def test_add_operator_extension_path_complex(self):
        u = User[EnterpriseUser]()
        AddOperator(
            None,
            {
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "manager": {
                        "value": "1234",
                        "ref": "./26118915-6090-4610-87e4-49d8ca9f808d",
                    },
                    "employeeNumber": "0000",
                }
            },
        )(u)
        AddOperator(
            None,
            {
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "employeeNumber": "5678"
                }
            },
        )(u)
        assert u.schemas == [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
        ]
        assert u.EnterpriseUser.employee_number == "5678"
        assert u.EnterpriseUser.manager.value == "1234"

    def test_simple_replace_operator_unset_single_valued(self):
        u = User()
        ReplaceOperator.operation(u, "displayName", "newName")
        assert u.display_name == "newName"

    def test_simple_replace_operator_single_valued(self):
        u = User(display_name="Foo")
        ReplaceOperator.operation(u, "displayName", "Bar")
        assert u.display_name == "Bar"

    def test_simple_replace_operator_unset_multi_valued(self):
        u = User()
        ReplaceOperator.operation(
            u,
            "emails",
            [{"type": "work", "primary": True, "value": "work@example.com"}],
        )
        assert u.emails == [Email(type="work", value="work@example.com", primary=True)]

    def test_simple_replace_operator_multi_valued(self):
        u = User(
            emails=[
                Email(type="work", value="work@example.org", primary=False),
                Email(type="home", value="home@example.org", primary=True),
            ]
        )
        ReplaceOperator.operation(
            u,
            "emails",
            [{"type": "work", "primary": True, "value": "work@example.com"}],
        )
        assert u.emails == [
            Email(type="work", value="work@example.com", primary=True),
        ]

    def test_simple_replace_operator_multi_valued_invalid_value(self):
        u = User(emails=[])
        with pytest.raises(SCIMException, match="invalidValue"):
            ReplaceOperator.operation(
                u,
                "emails",
                {"type": "work", "primary": True, "value": "work@example.com"},
            )

    def test_simple_replace_operator_immutable(self):
        u = User()
        with pytest.raises(SCIMException, match="mutability"):
            ReplaceOperator.operation(u, "id", "123")
        u.id = "123"
        ReplaceOperator.operation(u, "id", "123")
        assert u.id == "123"

    def test_replace_operator_root_object(self):
        u = User(user_name="bar", name=Name(family_name="Foo"))
        ReplaceOperator(
            None,
            {
                "userName": "foo",
                "name": {
                    "formatted": "Mr. Foo",
                },
            },
        )(u)
        assert u.user_name == "foo"
        assert u.name == Name(formatted="Mr. Foo")

    def test_replace_operator_overwrite_required_attribute(self):
        u = User(user_name="A")
        with pytest.raises(SCIMException, match="invalidValue"):
            ReplaceOperator("userName", "")(u)

    def test_simple_remove_operator_unset_single_valued(self):
        u = User()
        RemoveOperator.operation(u, "userName", None)
        assert u.user_name is None

    def test_simple_remove_operator_single_valued(self):
        u = User(display_name="Foo")
        RemoveOperator.operation(u, "displayName", None)
        assert u.display_name is None

    def test_simple_remove_operator_multi_valued(self):
        u = User(
            emails=[Email(value="work@example.com"), Email(value="home@example.com")]
        )
        RemoveOperator.operation(u, "emails", None)
        assert u.emails is None

    def test_simple_remove_operator_immutable(self):
        u = User(id="123", groups=[GroupMembership()])
        with pytest.raises(SCIMException, match="immutable"):
            RemoveOperator.operation(u, "id", None)
        with pytest.raises(SCIMException, match="immutable"):
            RemoveOperator.operation(u, "groups", None)

    def test_remove_operator_root_object(self):
        u = User()
        with pytest.raises(SCIMException, match="noTarget"):
            RemoveOperator("", None)(u)

    def test_remove_operator_required_attribute(self):
        u = User(user_name="A")
        with pytest.raises(SCIMException, match="invalidValue"):
            RemoveOperator("userName", None)(u)

    def test_remove_operator_complex_attribute(self):
        u = User(id="123", user_name="A", name=Name(formatted="Mr. Foo"))
        RemoveOperator("name", None)(u)
        assert u.name is None

    def test_remove_operator_complex_attribute_sub_attribute(self):
        u = User(
            id="123", user_name="A", name=Name(formatted="Mr. Foo", family_name="Foo")
        )
        RemoveOperator("name.formatted", None)(u)
        assert u.name == Name(family_name="Foo")

    def test_remove_operator_multi_valued_filter(self):
        u = User(
            emails=[
                Email(value="work@example.com", primary=False),
                Email(value="home@example.com", type="home", primary=False),
            ]
        )
        RemoveOperator('emails[type eq "home"]', None)(u)
        assert u.emails == [Email(value="work@example.com", primary=False)]

    def test_remove_operator_multi_valued_filter_sub_attribute(self):
        u = User(
            emails=[
                Email(value="work@example.com", primary=False),
                Email(value="home@example.com", type="home", primary=False),
            ]
        )
        RemoveOperator('emails[type eq "home"].type', None)(u)
        assert u.emails == [
            Email(value="work@example.com", primary=False),
            Email(value="home@example.com", primary=False),
        ]

    def test_remove_operator_extension(self):
        u = User[EnterpriseUser]()
        u.EnterpriseUser = EnterpriseUser(employee_number="123")
        with pytest.raises(SCIMException, match="invalidPath"):
            RemoveOperator(
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", None
            )(u)

    def test_remove_operator_extension_simple_attribute(self):
        u = User[EnterpriseUser]()
        u.EnterpriseUser = EnterpriseUser(employee_number="123")
        RemoveOperator(
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:employeeNumber",
            None,
        )(u)
        assert u.EnterpriseUser.employee_number is None

    def test_resolve_operator_result(self):
        result = ResolveResult()
        assert result.get_field_annotation(CaseExact) is None

    def _resolve_value(self, path: str, model: BaseModel):
        result = ResolveOperator(path)(model)
        return result.get_values()

    def test_resolve_operator_unset_simple_attribute(self):
        u = User()
        assert self._resolve_value("userName", u) is None
        assert self._resolve_value("active", u) is None
        with pytest.raises(SCIMException, match="noTarget"):
            self._resolve_value("invalidAttribute", u)

    def test_resolve_operator_simple_attribute(self):
        u = User(user_name="ABC")
        assert self._resolve_value("userName", u) == "ABC"

    def test_resolve_operator_complex_attribute(self):
        u = User(name=Name(formatted="Mr. Foo"))
        assert self._resolve_value("name", u) == Name(formatted="Mr. Foo")
        assert self._resolve_value("name.formatted", u) == "Mr. Foo"
        assert self._resolve_value("name.givenName", u) is None

    def test_resolve_operator_complex_multi_valued_attribute(self):
        work_email = Email(value="work@example.com", primary=True)
        home_email = Email(value="home@example.com", type="home", primary=False)
        u = User(emails=[work_email, home_email])
        assert self._resolve_value("emails", u) == [work_email, home_email]
        assert self._resolve_value('emails[type eq "home"]', u) == home_email
        assert self._resolve_value('emails[type eq "other"]', u) is None
        assert self._resolve_value("emails[type pr]", u) == home_email
        assert self._resolve_value("emails[not (type pr)]", u) == work_email
        assert self._resolve_value("emails[primary eq true]", u) == work_email

    def _resolve_sort_value(self, path: str, model: BaseModel):
        operator = ResolveSortOperator(path)
        return operator(model)

    def test_resolve_sort_operator(self):
        u = User[EnterpriseUser](
            id="123",
            user_name="foo",
            name=Name(formatted="Mr. Foo"),
            emails=[
                Email(value="home@example.com", type="home", primary=False),
                Email(value="work@example.com", type="work", primary=True),
            ],
        )
        u.EnterpriseUser = EnterpriseUser(employee_number="123")
        assert self._resolve_sort_value("", u) is None
        assert self._resolve_sort_value("id", u) == "123"
        assert self._resolve_sort_value("externalId", u) is None
        assert self._resolve_sort_value("userName", u) == "foo"
        assert self._resolve_sort_value("USERNAME", u) == "foo"
        assert self._resolve_sort_value("name.formatted", u) == "mr. foo"
        assert self._resolve_sort_value("name.givenName", u) is None
        assert self._resolve_sort_value("emails", u) == "work@example.com"
        assert (
            self._resolve_sort_value(
                "urn:ietf:params:scim:schemas:core:2.0:User:emails", u
            )
            == "work@example.com"
        )
        assert self._resolve_sort_value("emails.value", u) == "work@example.com"
        assert (
            self._resolve_sort_value('emails[type eq "home"]', u) == "home@example.com"
        )
        assert (
            self._resolve_sort_value('emails[type eq "home"].value', u)
            == "home@example.com"
        )
        assert self._resolve_sort_value('emails[type eq "home"].type', u) == "home"
        assert self._resolve_sort_value('emails[type eq "other"]', u) is None
        assert self._resolve_sort_value('emails[type eq "other"].value', u) is None
        assert self._resolve_sort_value('emails[primary eq "True"].type', u) == "work"
        assert self._resolve_sort_value('emails[primary eq "False"].type', u) == "home"
        assert (
            self._resolve_sort_value(
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:employeeNumber",
                u,
            )
            == "123"
        )
        assert (
            self._resolve_sort_value(
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:division", u
            )
            is None
        )

        assert self._resolve_sort_value("invalidAttribute", u) is None
        assert (
            self._resolve_sort_value("invalidAttribute.invalidSubAttribute", u) is None
        )
        assert self._resolve_sort_value("name", u) is None
        assert self._resolve_sort_value("name.invalidSubAttribute", u) is None
        assert (
            self._resolve_sort_value("name[invalidSubAttribute pr].formatted", u)
            is None
        )
        assert self._resolve_sort_value("name[invalidSubAttribute pr]", u) is None
        assert self._resolve_sort_value("id.formatted", u) is None
        assert self._resolve_sort_value("id[invalidSubAttribute pr]", u) is None
        assert (
            self._resolve_sort_value("id[invalidSubAttribute pr].formatted", u) is None
        )
        assert (
            self._resolve_sort_value(
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", u
            )
            is None
        )
        assert (
            self._resolve_sort_value(
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:invalidAttribute",
                u,
            )
            is None
        )
