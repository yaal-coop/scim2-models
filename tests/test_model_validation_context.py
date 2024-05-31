from typing import Annotated
from typing import Optional

import pytest
from pydantic import ValidationError

from pydantic_scim2 import SCIM2Model
from pydantic_scim2.base import Mutability
from pydantic_scim2.base import Returned


class MutabilityModel(SCIM2Model):
    read_only: Annotated[Optional[str], Mutability.read_only] = None
    read_write: Annotated[Optional[str], Mutability.read_write] = None
    immutable: Annotated[Optional[str], Mutability.immutable] = None
    write_only: Annotated[Optional[str], Mutability.write_only] = None


def test_mutability_validation():
    mod = MutabilityModel.model_validate(
        {
            "readOnly": "ro",
            "readWrite": "rw",
            "immutable": "im",
            "writeOnly": "wo",
        }
    )
    assert mod == MutabilityModel(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityModel.model_validate(
        {
            "readOnly": "ro",
            "readWrite": "rw",
            "immutable": "im",
            "writeOnly": "wo",
        },
        context={"mutability": None},
    )
    assert mod == MutabilityModel(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityModel.model_validate(
        {
            "readOnly": "ro",
            "readWrite": "rw",
            "immutable": "im",
            "writeOnly": "wo",
        },
        context={"mutability": []},
    )
    assert mod == MutabilityModel(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityModel.model_validate(
        {
            "readOnly": "ro",
            "readWrite": "rw",
        },
        context={"mutability": [Mutability.read_only, Mutability.read_write]},
    )
    assert mod == MutabilityModel(read_only="ro", read_write="rw")

    with pytest.raises(ValidationError):
        MutabilityModel.model_validate(
            {
                "readOnly": "ro",
                "readWrite": "rw",
                "immutable": "im",
            },
            context={"mutability": [Mutability.read_only, Mutability.read_write]},
        )


class ReturnedModel(SCIM2Model):
    always: Annotated[Optional[str], Returned.always] = None
    never: Annotated[Optional[str], Returned.never] = None
    default: Annotated[Optional[str], Returned.default] = None
    request: Annotated[Optional[str], Returned.request] = None


def test_returnability_validation():
    mod = ReturnedModel.model_validate(
        {
            "always": "always",
            "never": "never",
            "default": "default",
            "request": "request",
        }
    )
    assert mod == ReturnedModel(
        always="always", never="never", default="default", request="request"
    )

    mod = ReturnedModel.model_validate(
        {
            "always": "always",
            "never": "never",
            "default": "default",
            "request": "request",
        },
        context={"returned": None},
    )
    assert mod == ReturnedModel(
        always="always", never="never", default="default", request="request"
    )

    mod = ReturnedModel.model_validate(
        {
            "always": "always",
            "never": "never",
            "default": "default",
            "request": "request",
        },
        context={"returned": []},
    )
    assert mod == ReturnedModel(
        always="always", never="never", default="default", request="request"
    )

    mod = ReturnedModel.model_validate(
        {
            "always": "always",
            "never": "never",
        },
        context={"returned": [Returned.always, Returned.never]},
    )
    assert mod == ReturnedModel(always="always", never="never")

    with pytest.raises(ValidationError):
        ReturnedModel.model_validate(
            {
                "always": "always",
                "never": "never",
                "default": "default",
            },
            context={"returned": [Returned.always, Returned.never]},
        )
