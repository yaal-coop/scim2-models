from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type

from pydantic_scim2.utils import merge_dicts


def validate_model_attribute(model: Type, attribute_base: str) -> None:
    """Validate that an attribute name or a sub-attribute path exist for a
    given model."""

    from pydantic_scim2.base import SCIM2Model

    attribute_name, *sub_attribute_blocks = attribute_base.split(".")
    sub_attribute_base = ".".join(sub_attribute_blocks)

    aliases = {field.alias for field in model.model_fields.values()}

    if attribute_name not in aliases:
        raise ValueError(
            f"Model '{model.__name__}' has no attribute named '{attribute_name}'"
        )

    if sub_attribute_base:
        attribute_type = model.get_field_root_type(attribute_name)

        if not issubclass(attribute_type, SCIM2Model):
            raise ValueError(
                f"Attribute '{attribute_name}' is not a complex attribute, and cannot have a '{sub_attribute_base}' sub-attribute"
            )

        validate_model_attribute(attribute_type, sub_attribute_base)


def extract_schema_and_attribut_base(attribute_urn: str) -> Tuple[str, str]:
    """Extract the schema urn part and the attribute name part from attribute
    name, as defined in :rfc:`RFC7644 §3.10 <7644#section-3.10>`."""

    *urn_blocks, attribute_base = attribute_urn.split(":")
    schema = ":".join(urn_blocks)
    return schema, attribute_base


def validate_attribute_urn(
    attribute_name: str,
    default_resource: Optional[Type] = None,
    resource_types: Optional[List[Type]] = None,
) -> str:
    """Validate that an attribute urn is valid or not.

    :parm attribute_name: The attribute urn to check.
    :default_resource: The default resource if `attribute_name` is not an absolute urn.
    :resource_types: The available resources in which to look for the attribute.
    :return: The normalized attribute URN.
    """

    from pydantic_scim2.rfc7643.resource import Resource

    if not resource_types:
        resource_types = []

    if default_resource and default_resource not in resource_types:
        resource_types.append(default_resource)

    default_schema = (
        default_resource.model_fields["schemas"].default[0]
        if default_resource
        else None
    )

    schema, attribute_base = extract_schema_and_attribut_base(attribute_name)
    if not schema:
        schema = default_schema

    if not schema:
        raise ValueError("No default schema and relative URN")

    resource = Resource.get_by_schema(resource_types, schema)
    if not resource:
        raise ValueError(f"No resource matching schema '{schema}'")

    validate_model_attribute(resource, attribute_base)

    return f"{schema}:{attribute_base}"


def build_nested_dict(
    model: Type, attribute_base_blocks: Optional[str], fill_value: bool = True
) -> Dict[str, Any]:
    """Build a dict tree structure based on a list of strings.

    e.g. :code:`build_nested_dict(["foo", "bar", "baz"], True)` will
    return :code:`{"foo": {"bar": {"baz": True}}}`
    """

    attribute_name, *sub_blocks = attribute_base_blocks
    attribute_name = model.get_field_name_by_alias(attribute_name) or attribute_name
    if sub_blocks:
        sub_model = model.get_field_root_type(attribute_name)
        return {attribute_name: build_nested_dict(sub_model, sub_blocks, fill_value)}

    return {attribute_name: fill_value}


def build_merged_nested_dict(
    model: Type, attribute_bases: List[str], fill_value: bool = True
) -> Dict[str, Any]:
    # Maybe this could be done in one shot without merging dicts afterward?

    to_merge = [
        build_nested_dict(model, attribute_base.split("."), fill_value)
        for attribute_base in attribute_bases
    ]

    merged = merge_dicts(*to_merge)
    return merged


def scim_attributes_to_pydantic(
    attributes: List["str"],
    default_resource: Optional[Type] = None,
    resource_types: Optional[List[Type]] = None,
    fill_value: bool = True,
) -> Dict:
    """Convert attribute list of SCIM attributes payloads as defined in
    :rfc:`RFC7644 §3.10 <https://datatracker.ietf.org/doc/html/rfc7644#section-3.10>`, in nested attribute directories usable by pydantic.

    The produced dict is intended to be used as the `include` parameter in pydantic `BaseModel.dump_model` methode."""
    from pydantic_scim2.rfc7643.resource import Resource

    if not resource_types:
        resource_types = []

    if default_resource and default_resource not in resource_types:
        resource_types.append(default_resource)

    normalized_attribute_urns = [
        validate_attribute_urn(attribute_name, default_resource, resource_types)
        for attribute_name in attributes
    ]

    extracted = [
        extract_schema_and_attribut_base(attribute_urn)
        for attribute_urn in normalized_attribute_urns
    ]

    attribute_urns_by_model = {}
    for schema, attribute_base in extracted:
        model = Resource.get_by_schema(resource_types, schema)
        attribute_urns_by_model.setdefault(model, []).append(attribute_base)

    attribute_trees_by_model = {
        model: build_merged_nested_dict(
            model=model,
            attribute_bases=attribute_bases,
            fill_value=fill_value,
        )
        for model, attribute_bases in attribute_urns_by_model.items()
    }
    return attribute_trees_by_model


def contains_attribute_or_subattributes(attribute_urns: List[str], attribute_urn):
    return attribute_urn in attribute_urns or any(
        item.startswith(f"{attribute_urn}.") for item in attribute_urns
    )
