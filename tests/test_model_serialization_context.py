from typing import Annotated
from typing import Optional

from pydantic_scim2 import SCIM2Model
from pydantic_scim2.base import Mutability
from pydantic_scim2.base import Returned


class MutabilityModel(SCIM2Model):
    read_only: Annotated[Optional[str], Mutability.read_only] = None
    read_write: Annotated[Optional[str], Mutability.read_write] = None
    immutable: Annotated[Optional[str], Mutability.immutable] = None
    write_only: Annotated[Optional[str], Mutability.write_only] = None


def test_serialize_by_mutability():
    obj = MutabilityModel(
        read_only="ro", read_write="rw", immutable="im", write_only="wo"
    )
    assert obj.model_dump() == {
        "readOnly": "ro",
        "readWrite": "rw",
        "immutable": "im",
        "writeOnly": "wo",
    }

    assert obj.model_dump(context={"mutability": None}) == {
        "readOnly": "ro",
        "readWrite": "rw",
        "immutable": "im",
        "writeOnly": "wo",
    }

    assert obj.model_dump(context={"mutability": []}) == {
        "readOnly": "ro",
        "readWrite": "rw",
        "immutable": "im",
        "writeOnly": "wo",
    }

    assert obj.model_dump(
        context={"mutability": [Mutability.read_only, Mutability.read_write]},
    ) == {
        "readOnly": "ro",
        "readWrite": "rw",
    }


class ReturnedModel(SCIM2Model):
    always: Annotated[Optional[str], Returned.always] = None
    never: Annotated[Optional[str], Returned.never] = None
    default: Annotated[Optional[str], Returned.default] = None
    request: Annotated[Optional[str], Returned.request] = None


def test_serialize_by_returnability():
    obj = ReturnedModel(
        always="always", never="never", default="default", request="request"
    )
    assert obj.model_dump() == {
        "always": "always",
        "never": "never",
        "default": "default",
        "request": "request",
    }

    assert obj.model_dump(context={"returned": None}) == {
        "always": "always",
        "never": "never",
        "default": "default",
        "request": "request",
    }

    assert obj.model_dump(context={"returned": []}) == {
        "always": "always",
        "never": "never",
        "default": "default",
        "request": "request",
    }

    assert obj.model_dump(
        context={"returned": [Returned.always, Returned.never]},
    ) == {
        "always": "always",
        "never": "never",
    }
