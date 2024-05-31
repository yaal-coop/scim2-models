from typing import Annotated
from typing import Optional

import pytest
from pydantic import ValidationError

from pydantic_scim2 import SCIM2Model
from pydantic_scim2.base import Mutability


class MutabilityModel(SCIM2Model):
    read_only: Annotated[Optional[str], Mutability.read_only] = None
    read_write: Annotated[Optional[str], Mutability.read_write] = None
    immutable: Annotated[Optional[str], Mutability.immutable] = None
    write_only: Annotated[Optional[str], Mutability.write_only] = None


def test_mutability_validation():
    mod = MutabilityModel.model_validate(
        {
            "read_only": "ro",
            "read_write": "rw",
            "immutable": "im",
            "write_only": "wo",
        }
    )
    assert mod == MutabilityModel(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityModel.model_validate(
        {
            "read_only": "ro",
            "read_write": "rw",
            "immutable": "im",
            "write_only": "wo",
        },
        context={"mutability": None},
    )
    assert mod == MutabilityModel(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityModel.model_validate(
        {
            "read_only": "ro",
            "read_write": "rw",
            "immutable": "im",
            "write_only": "wo",
        },
        context={"mutability": []},
    )
    assert mod == MutabilityModel(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )

    mod = MutabilityModel.model_validate(
        {
            "read_only": "ro",
            "read_write": "rw",
        },
        context={"mutability": [Mutability.read_only, Mutability.read_write]},
    )
    assert mod == MutabilityModel(read_only="ro", read_write="rw")

    with pytest.raises(ValidationError):
        MutabilityModel.model_validate(
            {
                "read_only": "ro",
                "read_write": "rw",
                "immutable": "im",
            },
            context={"mutability": [Mutability.read_only, Mutability.read_write]},
        )
