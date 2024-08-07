import datetime
import importlib
import json
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union
from typing import get_args
from typing import get_origin

from pydantic import EmailStr
from pydantic import ValidationError
from scim2_models import BaseModel
from scim2_models import Error
from scim2_models import Mutability
from scim2_models import Resource
from scim2_models import ResourceType
from scim2_models import Schema


class SCIMException(Exception):
    """A wrapper class, because an "Error" does not inherit from Exception and
    should not be raised."""

    def __init__(self, scim_error: Error):
        self.scim_error = scim_error


def load_json_resource(json_name: str) -> List:
    """Loads a JSON document from the scim_provider package resources."""
    fp = importlib.resources.files("scim_provider") / "resources" / json_name
    with open(fp) as f:
        return json.load(f)


def load_scim_resource(json_name: str, type_: type[Resource]):
    """Loads and validates a JSON document from the scim_provider package
    resources."""
    ret = {}
    definitions = load_json_resource(json_name)
    for d in definitions:
        model = type_.model_validate(d)
        ret[model.id] = model
    return ret


def load_default_schemas() -> Dict[str, Schema]:
    """Loads the default schemas from RFC 7643."""
    return load_scim_resource("default-schemas.json", Schema)


def load_default_resource_types() -> Dict[str, ResourceType]:
    """Loads the default resource types from RFC 7643."""
    return load_scim_resource("default-resource-types.json", ResourceType)


def merge_resources(target: Resource, updates: BaseModel):
    """Merges a resource with another resource as specified for HTTP PUT (RFC
    7644, section 3.5.1)"""
    for set_attribute in updates.model_fields_set:
        mutability = target.get_field_annotation(set_attribute, Mutability)
        if mutability == Mutability.read_only:
            continue
        if isinstance(getattr(updates, set_attribute), Resource):
            # This is a model extension, handle it as its own resource
            # and don't simply overwrite it
            merge_resources(
                getattr(target, set_attribute), getattr(updates, set_attribute)
            )
            continue
        new_value = getattr(updates, set_attribute)
        if mutability == Mutability.immutable and getattr(
            target, set_attribute
        ) not in (None, new_value):
            raise SCIMException(Error.make_mutability_error())
        setattr(target, set_attribute, new_value)


def get_by_alias(
    r: BaseModel, scim_name: str, allow_none: bool = False
) -> Optional[str]:
    """Returns the pydantic attribute name for a BaseModel and given SCIM
    attribute name.

    :param r: BaseModel
    :param scim_name: SCIM attribute name
    :param allow_none: Allow returning None if attribute is not found
    :return: pydantic attribute name
    :raises SCIMException: If no attribute is found and allow_none is
        False
    """
    try:
        return next(
            k
            for k, v in r.model_fields.items()
            if v.serialization_alias.lower() == scim_name.lower()
        )
    except StopIteration as e:
        if allow_none:
            return None
        raise SCIMException(Error.make_no_target_error()) from e


def is_multi_valued(model: BaseModel, attribute_name: str) -> bool:
    """Checks whether a given attribute of a model is multi-valued."""
    attribute_type = model.model_fields[attribute_name].annotation

    if get_origin(attribute_type) is Union:
        attribute_type = get_args(attribute_type)[0]

    origin = get_origin(attribute_type)
    return isinstance(origin, Type) and issubclass(origin, List)


def get_schemas(resource: Resource) -> List[str]:
    """Returns a list of all schemas possible for a given resource.

    Note that this may include schemas the resource does not currently
    have (such as missing optional schema extensions).
    """
    return resource.model_fields["schemas"].default


def get_or_create(
    model: BaseModel, attribute_name: str, check_mutability: bool = False
):
    """Gets or creates a complex attribute model for a given resource.

    :param model: The model
    :param attribute_name: The attribute name
    :param check_mutability: If True, validate that the attribute is
        mutable
    :return: A complex attribute model
    :raises SCIMException: If attribute is not mutable and
        check_mutability is True
    """
    if check_mutability:
        if model.get_field_annotation(attribute_name, Mutability) in (
            Mutability.read_only,
            Mutability.immutable,
        ):
            raise SCIMException(Error.make_mutability_error())
    ret = getattr(model, attribute_name, None)
    if not ret:
        if is_multi_valued(model, attribute_name):
            ret = []
            setattr(model, attribute_name, ret)
        else:
            field_root_type = model.get_field_root_type(attribute_name)
            ret = field_root_type()
            setattr(model, attribute_name, ret)
    return ret


def handle_extension(resource: Resource, scim_name: str) -> Tuple[BaseModel, str]:
    default_schema = get_schemas(resource)[0].lower()
    if scim_name.lower().startswith(default_schema):
        scim_name = scim_name[len(default_schema) :].lstrip(":")
        return resource, scim_name

    for extension_model in resource.get_extension_models():
        extension_prefix = extension_model.lower()
        if scim_name.lower().startswith(extension_prefix):
            scim_name = scim_name[len(extension_prefix) :]
            scim_name = scim_name.lstrip(":")
            if extension_model.lower() not in [s.lower() for s in resource.schemas]:
                resource.schemas.append(extension_model)
            ext = get_or_create(resource, get_by_alias(resource, extension_model))
            return ext, scim_name
    return resource, scim_name


def model_validate_from_dict(field_root_type: BaseModel, value: dict) -> any:
    """Workaround for some of the "special" requirements for MS Entra, mixing
    display and displayName in some cases."""
    if (
        "display" not in value
        and "display" in field_root_type.model_fields
        and "displayName" in value
    ):
        value["display"] = value["displayName"]
        del value["displayName"]
    return field_root_type.model_validate(value)


def parse_new_value(model: BaseModel, attribute_name: str, value: any) -> any:
    """Given a model and attribute name, attempt to parse a new value so that
    the type matches the type expected by the model.

    :raises SCIMException: If attribute can not be mapped to the
        required type
    """
    field_root_type = model.get_field_root_type(attribute_name)
    try:
        if isinstance(value, dict):
            new_value = model_validate_from_dict(field_root_type, value)
        elif isinstance(value, list):
            new_value = [model_validate_from_dict(field_root_type, v) for v in value]
        else:
            if field_root_type is bool and isinstance(value, str):
                new_value = not value.lower() == "false"
            elif field_root_type is datetime.datetime and isinstance(value, str):
                new_value = datetime.datetime.fromisoformat(value)
            elif field_root_type is EmailStr and isinstance(value, str):
                new_value = value
            elif hasattr(field_root_type, "model_fields"):
                primary_value = get_by_alias(field_root_type, "value", True)
                if primary_value is not None:
                    new_value = field_root_type(value=value)
                else:
                    raise TypeError
            else:
                new_value = field_root_type(value)
    except (AttributeError, TypeError, ValueError, ValidationError) as e:
        raise SCIMException(Error.make_invalid_value_error()) from e
    return new_value
