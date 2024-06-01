from enum import Enum
from enum import auto
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Type
from typing import TypeVar
from typing import Union
from typing import get_args
from typing import get_origin

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import SerializationInfo
from pydantic import SerializerFunctionWrapHandler
from pydantic import ValidationInfo
from pydantic import field_serializer
from pydantic import field_validator
from pydantic import model_serializer
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError

from pydantic_scim2.attributes import contains_attribute_or_subattributes
from pydantic_scim2.attributes import validate_attribute_urn


class SCIM2AttributeURN(str):
    pass


class SCIM2Context(Enum):
    """Represent the different HTTP contexts detailed in :rfc:`RFC7644 §3.2
    <7644#section-3.2>`

    Contexts are intented to be used during model validation and serialization.
    For instance a client preparing a resource creation POST request can use
    :code:`resource.model_dump(SCIM2Context.RESOURCE_CREATION_REQUEST)` and
    the server can then validate it with
    :code:`resource.model_validate(SCIM2Context.RESOURCE_CREATION_REQUEST)`.
    """

    DEFAULT = auto()
    """The default context.

    All fields are accepted during validation, and all fields are
    serialized during a dump.
    """

    RESOURCE_CREATION_REQUEST = auto()
    RESOURCE_CREATION_RESPONSE = auto()
    RESOURCE_QUERY_REQUEST = auto()
    RESOURCE_QUERY_RESPONSE = auto()
    RESOURCE_REPLACEMENT_REQUEST = auto()
    RESOURCE_REPLACEMENT_RESPONSE = auto()
    RESOURCE_MODIFICATION_REQUEST = auto()
    RESOURCE_MODIFICATION_RESPONSE = auto()
    SEARCH_REQUEST = auto()
    SEARCH_RESPONSE = auto()

    @classmethod
    def is_request(cls, ctx: "SCIM2Context") -> bool:
        return ctx in (
            cls.RESOURCE_CREATION_REQUEST,
            cls.RESOURCE_QUERY_REQUEST,
            cls.RESOURCE_REPLACEMENT_REQUEST,
            cls.RESOURCE_MODIFICATION_REQUEST,
            cls.SEARCH_REQUEST,
        )

    @classmethod
    def is_response(cls, ctx: "SCIM2Context") -> bool:
        return ctx in (
            cls.RESOURCE_CREATION_RESPONSE,
            cls.RESOURCE_QUERY_RESPONSE,
            cls.RESOURCE_REPLACEMENT_RESPONSE,
            cls.RESOURCE_MODIFICATION_RESPONSE,
            cls.SEARCH_RESPONSE,
        )


class Mutability(str, Enum):
    """A single keyword indicating the circumstances under which the value of
    the attribute can be (re)defined:"""

    read_only = "readOnly"
    """The attribute SHALL NOT be modified."""

    read_write = "readWrite"
    """The attribute MAY be updated and read at any time."""

    immutable = "immutable"
    """The attribute MAY be defined at resource creation (e.g., POST) or at
    record replacement via a request (e.g., a PUT).

    The attribute SHALL NOT be updated.
    """

    write_only = "writeOnly"
    """The attribute MAY be updated at any time.

    Attribute values SHALL NOT be returned (e.g., because the value is a
    stored hash).  Note: An attribute with a mutability of "writeOnly"
    usually also has a returned setting of "never".
    """


class Returned(str, Enum):
    """A single keyword that indicates when an attribute and associated values
    are returned in response to a GET request or in response to a PUT, POST, or
    PATCH request."""

    always = "always"  # cannot be excluded
    """The attribute is always returned, regardless of the contents of the
    "attributes" parameter.

    For example, "id" is always returned to identify a SCIM resource.
    """

    never = "never"  # always excluded
    """The attribute is never returned, regardless of the contents of the
    "attributes" parameter."""

    default = "default"  # included by default but can be excluded
    """The attribute is returned by default in all SCIM operation responses
    where attribute values are returned, unless it is explicitly excluded."""

    request = "request"  # excluded by default but can be included
    """The attribute is returned in response to any PUT, POST, or PATCH
    operations if specified in the "attributes" parameter."""


class Uniqueness(str, Enum):
    """A single keyword value that specifies how the service provider enforces
    uniqueness of attribute values."""

    none = "none"
    """The values are not intended to be unique in any way."""

    server = "server"
    """The value SHOULD be unique within the context of the current SCIM
    endpoint (or tenancy) and MAY be globally unique (e.g., a "username", email
    address, or other server-generated key or counter).

    No two resources on the same server SHOULD possess the same value.
    """

    global_ = "global"
    """The value SHOULD be globally unique (e.g., an email address, a GUID, or
    other value).

    No two resources on any server SHOULD possess the same value.
    """


class Required(Enum):
    true = True
    false = False


class SCIM2Model(BaseModel):
    """Base Model for everything."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    _schema: Optional[str] = None

    @classmethod
    def get_field_mutability(cls, field_name: str) -> Mutability:
        field_metadata = cls.model_fields[field_name].metadata

        default_mutability = Mutability.read_write

        def mutability_filter(item):
            return isinstance(item, Mutability)

        field_mutability = next(
            filter(mutability_filter, field_metadata), default_mutability
        )
        return field_mutability

    @classmethod
    def get_field_returnability(cls, field_name: str) -> Returned:
        field_metadata = cls.model_fields[field_name].metadata
        default_returned = Returned.default

        def returned_filter(item):
            return isinstance(item, Returned)

        field_returned = next(filter(returned_filter, field_metadata), default_returned)
        return field_returned

    def get_attribute_urn(self, field_name: str) -> Returned:
        """Build the full URN of the attribute.

        See :rfc:`RFC7644 §3.12 <7644#section-3.12>`.

        .. todo:: Actually *guess* the URN instead of using the hacky `_schema` attribute.
        """
        alias = self.model_fields[field_name].alias or field_name
        return f"{self._attribute_urn}.{alias}"

    @classmethod
    def get_field_name_by_alias(cls, alias: str) -> str:
        """Find a field name by its alias."""

        by_alias = {
            field.alias: field_name for field_name, field in cls.model_fields.items()
        }
        return by_alias.get(alias)

    @classmethod
    def get_field_root_type(cls, attribute_name: str) -> Type:
        """Extract the root type from a model field.

        For example, return 'GroupMember' for
        'Optional[List[GroupMember]]'
        """

        attribute_type = cls.model_fields[attribute_name].annotation

        # extract 'x' from 'Optional[x]'
        if get_origin(attribute_type) is Union:
            attribute_type = get_args(attribute_type)[0]

        # extract 'x' from 'List[x]'
        if get_origin(attribute_type) is List:
            attribute_type = get_args(attribute_type)[0]

        return attribute_type

    @field_validator("*")
    @classmethod
    def check_mutability(cls, value: Any, info: ValidationInfo) -> Any:
        """Check that the field mutability is expected according to the
        validation context, as defined in :rfc:`RFC7643 §7 <7653#section-7>`.

        If not passed in the validation context, this validator does nothing.
        If mutability is set in the validation context,
        a :class:`~pydantic.ValidationError` will be raised ifa field is present but does not have the expected mutability.

        .. code-block:: python

            >>> from typing import List, Annotated
            >>> class Pet(Resource):
            ...     schemas : List[str] = ["org:example:Pet"]
            ...
            ...     name : Annotated[str, Mutability.read_write]
            ...
            >>> Pet.model_validate(
            ...     {"name": "Pluto"},
            ...     context={"mutability": [Mutability.read_only]},
            ... )
            Traceback (most recent call last):
                ...
            pydantic_core._pydantic_core.ValidationError: 1 validation error for Pet name
              Field 'name' has mutability 'readWrite' but expected any of ['readOnly'] [type=mutability_error, input_value='Pluto', input_type=str]
        """
        if not info.context or not info.context.get("mutability"):
            return value

        expected_mutability = info.context.get("mutability")
        field_mutability = cls.get_field_mutability(info.field_name)
        if field_mutability not in expected_mutability:
            raise PydanticCustomError(
                "mutability_error",
                "Field '{field_name}' has mutability '{field_mutability}' but expected any of {expected_mutability}",
                {
                    "field_name": info.field_name,
                    "field_mutability": field_mutability,
                    "expected_mutability": [item.value for item in expected_mutability],
                },
            )

        return value

    @field_validator("*")
    @classmethod
    def check_returnability(cls, value: Any, info: ValidationInfo) -> Any:
        """Check that the field returnability is expected according to the
        validation context, as defined in :rfc:`RFC7643 §7 <7653#section-7>`.

        If not passed in the validation context, this validator does nothing.
        If returnability is set in the validation context,
        a :class:`~pydantic.ValidationError` will be raised if a field is present but does not have the expected mutability.

        .. code-block:: python

            >>> from typing import List, Annotated
            >>> class Pet(Resource):
            ...     schemas : List[str] = ["org:example:Pet"]
            ...
            ...     name : Annotated[str, Returned.always]
            ...
            >>> Pet.model_validate(
            ...     {"name": "Pluto"},
            ...     context={"mutability": [Returned.never]},
            ... )
            Traceback (most recent call last):
                ...
            pydantic_core._pydantic_core.ValidationError: 1 validation error for Pet name
              Field 'name' has returnability 'always' but expected any of ['never'] [type=returned_error, input_value='Pluto', input_type=str]
        """

        if not info.context or not info.context.get("returned"):
            return value

        expected_returned = info.context.get("returned")
        field_returned = cls.get_field_returnability(info.field_name)
        if field_returned not in expected_returned:
            raise PydanticCustomError(
                "returned_error",
                "Field '{field_name}' has returnability '{field_returned}' but expected any of {expected_returned}",
                {
                    "field_name": info.field_name,
                    "field_returned": field_returned,
                    "expected_returned": [item.value for item in expected_returned],
                },
            )

        return value

    @classmethod
    def filter_attributes(
        cls,
        mutability: Optional[List[Mutability]] = None,
        returned: Optional[List[Returned]] = None,
    ) -> Set[str]:
        """Return a list of attributes matching mutability and returnability
        criterias."""

        def match(
            field: str,
            mutability: Optional[List[Mutability]] = None,
            returned: Optional[List[Returned]] = None,
        ):
            return (
                not mutability or cls.get_field_mutability(field) in mutability
            ) and (not returned or cls.get_field_returnability(field) in returned)

        return {
            field for field in cls.model_fields if match(field, mutability, returned)
        }

    @field_serializer("*", mode="wrap")
    def scim_serializer(
        self,
        value: Any,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """Serialize the fields according to mutability indications passed in
        the serialization context."""

        value = handler(value)

        if info.context.get("scim") and SCIM2Context.is_request(info.context["scim"]):
            value = self.scim_mutability_serializer(value, info)

        if info.context.get("scim") and SCIM2Context.is_response(info.context["scim"]):
            value = self.scim_returnability_serializer(value, info)

        return value

    def scim_mutability_serializer(self, value: Any, info: SerializationInfo) -> Any:
        """Serialize the fields according to mutability indications passed in
        the serialization context."""

        mutability = self.get_field_mutability(info.field_name)
        context = info.context.get("scim")

        if (
            context == SCIM2Context.RESOURCE_CREATION_REQUEST
            and mutability == Mutability.read_only
        ):
            return None

        if (
            context
            in (
                SCIM2Context.RESOURCE_QUERY_REQUEST,
                SCIM2Context.SEARCH_REQUEST,
            )
            and mutability == Mutability.write_only
        ):
            return None

        if context in (
            SCIM2Context.RESOURCE_MODIFICATION_REQUEST,
            SCIM2Context.RESOURCE_REPLACEMENT_REQUEST,
        ) and mutability in (Mutability.immutable, Mutability.read_only):
            return None

        return value

    def scim_returnability_serializer(self, value: Any, info: SerializationInfo) -> Any:
        """Serialize the fields according to returability indications passed in
        the serialization context."""

        returnability = self.get_field_returnability(info.field_name)
        attribute_urn = self.get_attribute_urn(info.field_name)
        included_urns = info.context.get("scim_attributes", [])
        excluded_urns = info.context.get("scim_excluded_attributes", [])

        if returnability == Returned.never:
            return None

        if returnability == Returned.default and (
            (
                included_urns
                and not contains_attribute_or_subattributes(
                    included_urns, attribute_urn
                )
            )
            or attribute_urn in excluded_urns
        ):
            return None

        if returnability == Returned.request and attribute_urn not in included_urns:
            return None

        return value

    @model_serializer(mode="wrap")
    def model_serializer_exclude_none(
        self, handler, info: SerializationInfo
    ) -> Dict[str, Any]:
        """Remove `None` values inserted by the
        :meth:`~pydantic_scim2.base.SCIM2Model.scim_field_serializer`."""

        result = handler(self)
        return {key: value for key, value in result.items() if value is not None}

    @classmethod
    def model_validate(
        cls, *args, scim_ctx: Optional[SCIM2Context] = SCIM2Context.DEFAULT, **kwargs
    ) -> "SCIM2Model":
        """Validate SCIM payloads and generate model representation by using
        Pydantic :code:`BaseModel.model_validate`."""

        kwargs.setdefault("context", {}).setdefault("scim", scim_ctx)
        return super().model_validate(*args, **kwargs)

    def model_dump(
        self,
        scim_ctx: Optional[SCIM2Context] = SCIM2Context.DEFAULT,
        *args,
        attributes: Optional[List[str]] = None,
        excluded_attributes: Optional[List[str]] = None,
        **kwargs,
    ):
        """Create a model representation that can be included in SCIM messages
        by using Pydantic :code:`BaseModel.model_dump`.

        :param scim_ctx: If a SCIM context is passed, some default values of
        Pydantic :code:`BaseModel.model_dump` are tuned to generate valid SCIM
        messages. Pass :data:`None` to get the default Pydantic behavior.
        """

        kwargs.setdefault("context", {}).setdefault("scim", scim_ctx)
        kwargs["context"]["scim_attributes"] = [
            validate_attribute_urn(attribute, self.__class__)
            for attribute in (attributes or [])
        ]
        kwargs["context"]["scim_excluded_attributes"] = [
            validate_attribute_urn(attribute, self.__class__)
            for attribute in (excluded_attributes or [])
        ]

        if scim_ctx:
            kwargs.setdefault("exclude_none", True)
            kwargs.setdefault("by_alias", True)
            kwargs.setdefault("mode", "json")

        return super().model_dump(*args, **kwargs)


AnyModel = TypeVar("AnyModel", bound=SCIM2Model)
