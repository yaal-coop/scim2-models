from typing import Annotated
from typing import List
from typing import Optional

import pytest

from pydantic_scim2 import SCIM2Model
from pydantic_scim2.attributes import scim_attributes_to_pydantic
from pydantic_scim2.attributes import validate_attribute_urn
from pydantic_scim2.base import Returned
from pydantic_scim2.rfc7643.resource import Resource
from pydantic_scim2.rfc7643.user import User


def test_get_attribute_urn():
    class Sub(SCIM2Model):
        _attribute_urn = "urn:example:2.0:Sup:sub"
        dummy: str

    class Sup(Resource):
        schemas: List[str] = ["urn:example:2.0:Sup"]
        dummy: str
        sub: Sub
        subs: List[Sub]

    sup = Sup(dummy="x", sub=Sub(dummy="x"), subs=[Sub(dummy="x")])

    assert sup.get_attribute_urn("dummy") == "urn:example:2.0:Sup:dummy"
    assert sup.get_attribute_urn("sub") == "urn:example:2.0:Sup:sub"
    assert sup.sub.get_attribute_urn("dummy") == "urn:example:2.0:Sup:sub.dummy"

    # TODO: fix this by dynamically guess attribute urns
    # assert sup.subs[0].get_attribute_urn("dummy") == "urn:example:2.0:Bar:subs.dummy"


class ReturnedModel(SCIM2Model):
    always: Annotated[Optional[str], Returned.always] = None
    never: Annotated[Optional[str], Returned.never] = None
    default: Annotated[Optional[str], Returned.default] = None
    request: Annotated[Optional[str], Returned.request] = None


class Baz(SCIM2Model):
    baz_snake_case: str


class Foo(Resource):
    schemas: List[str] = ["urn:example:2.0:Foo"]
    sub: Annotated[ReturnedModel, Returned.default]
    bar: str
    snake_case: str
    baz: Optional[Baz] = None


class Bar(Resource):
    schemas: List[str] = ["urn:example:2.0:Bar"]
    sub: Annotated[ReturnedModel, Returned.default]
    bar: str
    snake_case: str
    baz: Optional[Baz] = None


class Extension(Resource):
    schemas: List[str] = ["urn:example:2.0:Extension"]
    baz: str


def test_validate_attribute_urn():
    """Test the method that validates and normalizes attribute URNs."""

    assert validate_attribute_urn("bar", Foo) == "urn:example:2.0:Foo:bar"
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:bar", Foo)
        == "urn:example:2.0:Foo:bar"
    )
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:bar", User, resource_types=[Foo])
        == "urn:example:2.0:Foo:bar"
    )

    assert validate_attribute_urn("sub", Foo) == "urn:example:2.0:Foo:sub"
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:sub", Foo)
        == "urn:example:2.0:Foo:sub"
    )
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:sub", User, resource_types=[Foo])
        == "urn:example:2.0:Foo:sub"
    )

    assert validate_attribute_urn("sub.always", Foo) == "urn:example:2.0:Foo:sub.always"
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:sub.always", Foo)
        == "urn:example:2.0:Foo:sub.always"
    )
    assert (
        validate_attribute_urn(
            "urn:example:2.0:Foo:sub.always", User, resource_types=[Foo]
        )
        == "urn:example:2.0:Foo:sub.always"
    )

    assert validate_attribute_urn("snakeCase", Foo) == "urn:example:2.0:Foo:snakeCase"
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:snakeCase", Foo)
        == "urn:example:2.0:Foo:snakeCase"
    )

    assert (
        validate_attribute_urn("urn:example:2.0:Extension:baz", Foo[Extension])
        == "urn:example:2.0:Extension:baz"
    )
    assert (
        validate_attribute_urn(
            "urn:example:2.0:Extension:baz", resource_types=[Foo[Extension]]
        )
        == "urn:example:2.0:Extension:baz"
    )

    with pytest.raises(ValueError, match="No default schema and relative URN"):
        validate_attribute_urn("bar", resource_types=[Foo])

    with pytest.raises(
        ValueError, match="No resource matching schema 'urn:InvalidResource'"
    ):
        validate_attribute_urn("urn:InvalidResource:bar", Foo)

    with pytest.raises(
        ValueError, match="No resource matching schema 'urn:example:2.0:Foo'"
    ):
        validate_attribute_urn("urn:example:2.0:Foo:bar")

    with pytest.raises(
        ValueError, match="Model 'Foo' has no attribute named 'invalid'"
    ):
        validate_attribute_urn("urn:example:2.0:Foo:invalid", Foo)

    with pytest.raises(
        ValueError,
        match="Attribute 'bar' is not a complex attribute, and cannot have a 'invalid' sub-attribute",
    ):
        validate_attribute_urn("bar.invalid", Foo)


def test_scim_attributes_to_pydantic():
    """Test transforming SCIM attributes to pydantic attributes in simple
    conditions."""

    assert scim_attributes_to_pydantic(["bar"], Foo) == {Foo: {"bar": True}}
    assert scim_attributes_to_pydantic(["bar"], Foo, fill_value=False) == {
        Foo: {"bar": False}
    }
    assert scim_attributes_to_pydantic(["urn:example:2.0:Foo:bar"], Foo) == {
        Foo: {"bar": True}
    }

    assert scim_attributes_to_pydantic(["sub.always"], Foo) == {
        Foo: {"sub": {"always": True}}
    }

    with pytest.raises(ValueError):
        scim_attributes_to_pydantic(["urn:invalid:bar"], Foo) == {Foo: {"bar": True}}


def test_scim_attributes_to_pydantic_nested():
    """Test transforming SCIM sub-attributes to pydantic attributes tree."""

    assert scim_attributes_to_pydantic(["urn:example:2.0:Foo:sub.always"], Foo) == {
        Foo: {"sub": {"always": True}}
    }

    with pytest.raises(ValueError):
        scim_attributes_to_pydantic(["urn:example:2.0:Foo:bar"]) == {
            Foo: {"sub": {"always": True}}
        }

    assert scim_attributes_to_pydantic(
        ["urn:example:2.0:Foo:bar", "urn:example:2.0:Bar:bar"],
        resource_types=[Foo, Bar],
    ) == {
        Foo: {"bar": True},
        Bar: {"bar": True},
    }

    assert scim_attributes_to_pydantic(["bar", "sub.always"], Foo) == {
        Foo: {"bar": True, "sub": {"always": True}}
    }


def test_scim_attributes_to_pydantic_alias():
    """Test transforming SCIM attributes to pydantic attribute tree when there
    are aliases."""

    assert scim_attributes_to_pydantic(["snakeCase"], Foo) == {
        Foo: {"snake_case": True}
    }
    assert scim_attributes_to_pydantic(["urn:example:2.0:Foo:snakeCase"], Foo) == {
        Foo: {"snake_case": True}
    }

    assert scim_attributes_to_pydantic(["baz.bazSnakeCase"], Foo) == {
        Foo: {"baz": {"baz_snake_case": True}}
    }
    assert scim_attributes_to_pydantic(
        ["urn:example:2.0:Foo:baz.bazSnakeCase"], Foo
    ) == {Foo: {"baz": {"baz_snake_case": True}}}


@pytest.mark.skip
def test_scim_attributes_to_pydantic_extension():
    """Test transforming SCIM extension attributes to pydantic attribute
    tree."""

    assert scim_attributes_to_pydantic(
        ["urn:example:2.0:Extension:baz"], Foo[Extension]
    ) == {Foo: {"urn:example:2.0:Extension": {"baz": True}}}
