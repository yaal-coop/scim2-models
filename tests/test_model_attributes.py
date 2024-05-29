from typing import Annotated
from typing import List
from typing import Optional

import pytest
from pydantic import ValidationError

from pydantic_scim2 import Resource
from pydantic_scim2.base import Mutability
from pydantic_scim2.base import Returned


class MutabilityResource(Resource):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:MutabilityResource"]

    read_only: Annotated[Optional[str], Mutability.read_only] = None
    read_write: Annotated[Optional[str], Mutability.read_write] = None
    immutable: Annotated[Optional[str], Mutability.immutable] = None
    write_only: Annotated[Optional[str], Mutability.write_only] = None


def test_mutability_validation():
    mod = MutabilityResource.model_validate(
        {
            "read_only": "ro",
            "read_write": "rw",
            "immutable": "im",
            "write_only": "wo",
        }
    )
    assert mod == MutabilityResource(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityResource.model_validate(
        {
            "read_only": "ro",
            "read_write": "rw",
            "immutable": "im",
            "write_only": "wo",
        },
        context={"mutability": None},
    )
    assert mod == MutabilityResource(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityResource.model_validate(
        {
            "read_only": "ro",
            "read_write": "rw",
            "immutable": "im",
            "write_only": "wo",
        },
        context={"mutability": []},
    )
    assert mod == MutabilityResource(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityResource.model_validate(
        {
            "read_only": "ro",
            "read_write": "rw",
        },
        context={"mutability": [Mutability.read_only, Mutability.read_write]},
    )
    assert mod == MutabilityResource(read_only="ro", read_write="rw")

    with pytest.raises(ValidationError):
        MutabilityResource.model_validate(
            {
                "read_only": "ro",
                "read_write": "rw",
                "immutable": "im",
            },
            context={"mutability": [Mutability.read_only, Mutability.read_write]},
        )


class ReturnedResource(Resource):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:ReturnedResource"]

    always: Annotated[Optional[str], Returned.always] = None
    never: Annotated[Optional[str], Returned.never] = None
    default: Annotated[Optional[str], Returned.default] = None
    request: Annotated[Optional[str], Returned.request] = None


def test_returnability_validation():
    mod = ReturnedResource.model_validate(
        {
            "always": "always",
            "never": "never",
            "default": "default",
            "request": "request",
        }
    )
    assert mod == ReturnedResource(
        always="always", never="never", default="default", request="request"
    )

    mod = ReturnedResource.model_validate(
        {
            "always": "always",
            "never": "never",
            "default": "default",
            "request": "request",
        },
        context={"returned": None},
    )
    assert mod == ReturnedResource(
        always="always", never="never", default="default", request="request"
    )

    mod = ReturnedResource.model_validate(
        {
            "always": "always",
            "never": "never",
            "default": "default",
            "request": "request",
        },
        context={"returned": []},
    )
    assert mod == ReturnedResource(
        always="always", never="never", default="default", request="request"
    )

    mod = ReturnedResource.model_validate(
        {
            "always": "always",
            "never": "never",
        },
        context={"returned": [Returned.always, Returned.never]},
    )
    assert mod == ReturnedResource(always="always", never="never")

    with pytest.raises(ValidationError):
        ReturnedResource.model_validate(
            {
                "always": "always",
                "never": "never",
                "default": "default",
            },
            context={"returned": [Returned.always, Returned.never]},
        )
