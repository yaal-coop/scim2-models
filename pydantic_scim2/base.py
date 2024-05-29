from enum import Enum
from typing import Any
from typing import Optional
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError


class Mutability(str, Enum):
    read_only = "readOnly"
    read_write = "readWrite"
    immutable = "immutable"
    write_only = "writeOnly"


class Returned(str, Enum):
    always = "always"
    never = "never"
    default = "default"
    request = "request"


class Uniqueness(str, Enum):
    none = "none"
    server = "server"
    global_ = "global"


class Required(Enum):
    true = True
    false = False


class SCIM2Model(BaseModel):
    """Base Model for everything."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @field_validator("*")
    @classmethod
    def check_mutability(cls, value: Any, info: ValidationInfo) -> Any:
        """Check that the field mutability is expected according to the
        validation context.

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

        default_mutability = Mutability.read_write
        expected_mutability = info.context.get("mutability")
        field_metadata = cls.model_fields[info.field_name].metadata

        def mutability_filter(item):
            return isinstance(item, Mutability)

        field_mutability = next(
            filter(mutability_filter, field_metadata), default_mutability
        )

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
        validation context.

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

        default_returned = Returned.default
        expected_returned = info.context.get("returned")
        field_metadata = cls.model_fields[info.field_name].metadata

        def returned_filter(item):
            return isinstance(item, Returned)

        field_returned = next(filter(returned_filter, field_metadata), default_returned)

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


AnyModel = TypeVar("AnyModel", bound=SCIM2Model)


def int_to_str(status: Optional[int]) -> Optional[str]:
    return None if status is None else str(status)
