from enum import Enum
from typing import Optional
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel


class SCIM2Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def int_to_str(status: Optional[int]) -> Optional[str]:
    return None if status is None else str(status)


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


AnyModel = TypeVar("AnyModel", bound=SCIM2Model)
