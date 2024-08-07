import re
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type

from scim2_filter_parser.lexer import SCIMLexer
from scim2_filter_parser.parser import SCIMParser
from scim2_models import BaseModel
from scim2_models import CaseExact
from scim2_models import Error
from scim2_models import Mutability
from scim2_models import PatchOperation
from scim2_models import Required
from scim2_models import Resource
from scim2_models import Returned

from scim_provider.filter import evaluate_filter
from scim_provider.utils import SCIMException
from scim_provider.utils import get_by_alias
from scim_provider.utils import get_or_create
from scim_provider.utils import handle_extension
from scim_provider.utils import is_multi_valued
from scim_provider.utils import parse_new_value

ATTRIBUTE_PATH_REGEX = re.compile(
    r"^(?P<attribute>\w+)(\[(?P<condition>.*)\])?(\.(?P<sub_attribute>\w+))?$"
)


def patch_resource(resource: Resource, operation: PatchOperation):
    """Runs a patch operation against a resource."""
    match operation.op:
        case PatchOperation.Op.add:
            operator = AddOperator(operation.path, operation.value)
            operator(resource)
        case PatchOperation.Op.remove:
            operator = RemoveOperator(operation.path, None)
            operator(resource)
        case _:  # PatchOperation.Op.replace
            operator = ReplaceOperator(operation.path, operation.value)
            operator(resource)


def parse_attribute_path(attribute_path: Optional[str]) -> Optional[Dict[str, any]]:
    """Parses an attribute path and returns a dictionary of attributes.

    The attributes are the named captures in the regex
    ATTRIBUTE_PATH_REGEX.
    """
    if not attribute_path:
        return {}

    if not hasattr(parse_attribute_path, "cache"):
        parse_attribute_path.cache = {}
    if attribute_path in parse_attribute_path.cache:
        return parse_attribute_path.cache[attribute_path]

    match = ATTRIBUTE_PATH_REGEX.match(attribute_path)
    if not match:
        raise SCIMException(Error.make_invalid_path_error())
    parse_attribute_path.cache[attribute_path] = match.groupdict()
    return match.groupdict()


class Operator:
    """An operator operates on a resource and is constructed using a path and a
    value."""

    OPERATE_ON_ROOT = True  # Whether the operator may operate on the root of a resource (e.g. remove may not)
    REQUIRES_VALUE = True  # Whether the operator modifies the resource or not
    RETURNS_VALUE = False  # Whether the operator returns a result or not

    def __init__(self, path: Optional[str], value: Optional[any]):
        self.path = path
        self.value = value

    @classmethod
    def init_return(
        cls, model: BaseModel, attribute: str, sub_attribute: Optional[str], value: any
    ):
        """Initializes the return value if the operator returns something."""
        pass

    def do_return(self):
        """Returns the return value for the operator."""
        return None

    @classmethod
    def operation(
        cls, model: BaseModel, attribute: str, value: any, index: Optional[int] = None
    ):
        """Performs the actual operation of the operator."""
        raise NotImplementedError

    def parse_path(self, model: BaseModel):
        """Parses a path and optionally handles model extensions.

        :return: A tuple of the model to operate on and the parsed path.
        """
        path = self.path
        if isinstance(model, Resource):
            model, path = handle_extension(model, self.path)
        return model, parse_attribute_path(path)

    def __call__(self, model: BaseModel):
        """Executes the operator against a model."""
        if not self.path:
            self.call_on_root(model)
            return self.do_return()
        else:
            model, path = self.parse_path(model)

            match path:
                case {
                    "attribute": attribute,
                    "condition": None,
                    "sub_attribute": None,
                }:
                    self.match_attribute(attribute, model)
                    return self.do_return()
                case {
                    "attribute": attribute,
                    "condition": None,
                    "sub_attribute": sub_path,
                }:
                    self.match_complex_attribute(attribute, model, sub_path)
                    return self.do_return()
                case {
                    "attribute": attribute,
                    "condition": condition,
                    "sub_attribute": None,
                }:
                    self.match_multi_valued_attribute(attribute, condition, model)
                    return self.do_return()
                case {
                    "attribute": attribute,
                    "condition": condition,
                    "sub_attribute": sub_attribute,
                }:
                    self.match_multi_valued_attribute_sub(
                        attribute, condition, model, sub_attribute
                    )
                    return self.do_return()
                case _:
                    raise SCIMException(Error.make_invalid_path_error())

    def match_multi_valued_attribute_sub(
        self, attribute: str, condition: str, model: BaseModel, sub_attribute: str
    ):
        attribute_name = get_by_alias(model, attribute)
        multi_valued_attribute = get_or_create(model, attribute_name, True)
        if not isinstance(multi_valued_attribute, list):
            raise SCIMException(Error.make_invalid_path_error())
        token_stream = SCIMLexer().tokenize(condition)
        condition = SCIMParser().parse(token_stream)
        self.init_return(model, attribute_name, sub_attribute, self.value)
        for value in multi_valued_attribute:
            if evaluate_filter(value, condition):
                self.operation(value, sub_attribute, self.value)

    def match_multi_valued_attribute(
        self, attribute: str, condition: str, model: BaseModel
    ):
        if self.REQUIRES_VALUE and not isinstance(self.value, dict):
            raise SCIMException(Error.make_invalid_value_error())
        attribute_name = get_by_alias(model, attribute)
        multi_valued_attribute = get_or_create(
            model, attribute_name, self.REQUIRES_VALUE
        )
        if not isinstance(multi_valued_attribute, list):
            raise SCIMException(Error.make_invalid_path_error())
        token_stream = SCIMLexer().tokenize(condition)
        condition = SCIMParser().parse(token_stream)
        if self.REQUIRES_VALUE:
            for value in multi_valued_attribute:
                if evaluate_filter(value, condition):
                    for k, v in self.value.items():
                        self.operation(value, k, v)
        elif self.RETURNS_VALUE:
            self.init_return(model, attribute_name, None, self.value)
            for index, value in enumerate(multi_valued_attribute):
                if evaluate_filter(value, condition):
                    self.operation(model, attribute_name, self.value, index)
        else:
            new_value = [
                value
                for value in multi_valued_attribute
                if not evaluate_filter(value, condition)
            ]
            setattr(model, attribute_name, new_value)

    def match_complex_attribute(self, attribute: str, model: BaseModel, sub_path: str):
        complex_attribute = get_or_create(
            model, get_by_alias(model, attribute), self.REQUIRES_VALUE
        )
        if isinstance(complex_attribute, list) and complex_attribute:
            for value in complex_attribute:
                self.match_attribute(sub_path, value)
        else:
            if not isinstance(complex_attribute, BaseModel):
                raise SCIMException(Error.make_invalid_path_error())
            self.match_attribute(sub_path, complex_attribute)

    def match_attribute(self, attribute: str, model: BaseModel):
        self.init_return(model, attribute, None, self.value)
        self.operation(model, attribute, self.value)

    def call_on_root(self, model: Resource):
        if not self.OPERATE_ON_ROOT:
            raise SCIMException(Error.make_no_target_error())
        if not isinstance(self.value, dict):
            raise SCIMException(Error.make_invalid_value_error())
        for k, v in self.value.items():
            ext, scim_name = handle_extension(model, k)
            if ext == model:
                self.operation(model, scim_name, v)
            else:
                type(self)(self.path, v)(ext)


class AddOperator(Operator):
    """The implementation for the PATCH "add" operator."""

    @classmethod
    def operation(cls, model: BaseModel, attribute: str, value: any):
        alias = get_by_alias(model, attribute)
        if is_multi_valued(model, alias) and isinstance(value, list):
            for v in value:
                cls.operation(model, attribute, v)
            return

        existing_value = getattr(model, alias)
        new_value = parse_new_value(model, alias, value)
        if new_value == existing_value:
            return

        if model.get_field_annotation(alias, Mutability) == Mutability.read_only:
            raise SCIMException(Error.make_mutability_error())

        if is_multi_valued(model, alias):
            if getattr(model, alias) is None:
                setattr(model, alias, [])
            if getattr(new_value, "primary", False):
                for value in getattr(model, alias):
                    value.primary = False
            getattr(model, alias).append(new_value)
        else:
            if (
                model.get_field_annotation(alias, Required) == Required.true
                and not new_value
            ):
                raise SCIMException(Error.make_invalid_value_error())
            setattr(model, alias, new_value)


class RemoveOperator(Operator):
    """The implementation for the PATCH "remove" operator."""

    OPERATE_ON_ROOT = False
    REQUIRES_VALUE = False

    @classmethod
    def operation(cls, model: BaseModel, attribute: str, value: any):
        alias = get_by_alias(model, attribute)
        existing_value = getattr(model, alias)
        if not existing_value:
            return

        if model.get_field_annotation(alias, Mutability) in (
            Mutability.read_only,
            Mutability.immutable,
        ):
            raise SCIMException(Error.make_mutability_error())

        if model.get_field_annotation(alias, Required) == Required.true:
            raise SCIMException(Error.make_invalid_value_error())

        setattr(model, alias, None)


class ReplaceOperator(Operator):
    """The implementation for the PATCH "replace" operator."""

    @classmethod
    def operation(cls, model: BaseModel, attribute: str, value: any):
        alias = get_by_alias(model, attribute)
        if is_multi_valued(model, alias) and not isinstance(value, list):
            raise SCIMException(Error.make_invalid_value_error())

        existing_value = getattr(model, alias)
        new_value = parse_new_value(model, alias, value)
        if new_value == existing_value:
            return

        if model.get_field_annotation(alias, Mutability) == Mutability.read_only:
            raise SCIMException(Error.make_mutability_error())

        if (
            model.get_field_annotation(alias, Required) == Required.true
            and not new_value
        ):
            raise SCIMException(Error.make_invalid_value_error())
        setattr(model, alias, new_value)


class ResolveResult:
    """A descriptor for the result returned from the "ResolveOperator", used to
    resolve attributes from a model."""

    def __init__(self):
        self.records = []
        self.result_idx = 0
        self.model = None
        self.attribute = None
        self.sub_attribute = None

    def add_result(self, model: BaseModel, attribute_name: str):
        """Adds a result to the descriptor."""
        self.records.append((model, attribute_name))

    def add_result_index(self, model: BaseModel, attribute_name: str, index: int):
        """Adds a result to the descriptor.

        The resulting attribute is part of a multi-valued attribute
        described by its index.
        """
        self.records.append((model, attribute_name, index))

    def _evaluate_result(self, record: Tuple[str, str] | Tuple[str, str, int]):
        if len(record) == 2:
            return getattr(*record)
        else:
            return getattr(record[0], record[1])[record[2]]

    def get_field_annotation(self, annotation_type: Type):
        if not self.model:
            return None
        return self.model.get_field_annotation(self.attribute, annotation_type)

    def get_values(self):
        if not self.records:
            return None
        if len(self.records) == 1:
            return self._evaluate_result(self.records[0])
        return [self._evaluate_result(record) for record in self.records]


class ResolveOperator(Operator):
    """An operator that resolves attribute values from a model."""

    REQUIRES_VALUE = False
    RETURNS_VALUE = True

    def __init__(self, path: Optional[str]):
        super().__init__(path, ResolveResult())

    def do_return(self):
        ret = self.value
        self.value = ResolveResult()
        return ret

    @classmethod
    def init_return(
        cls,
        model: BaseModel,
        attribute: str,
        sub_attribute: Optional[str],
        value: ResolveResult,
    ):
        alias = get_by_alias(model, attribute)
        value.model = model
        value.attribute = alias
        value.sub_attribute = sub_attribute
        if (
            model.get_field_annotation(alias, Mutability) == Mutability.write_only
            or model.get_field_annotation(alias, Returned) == Returned.never
        ):
            raise SCIMException(Error.make_sensitive_error())

    @classmethod
    def operation(
        cls, model: BaseModel, attribute: str, value: any, index: Optional[int] = None
    ):
        alias = get_by_alias(model, attribute)
        if index is None:
            value.add_result(model, alias)
        else:
            value.add_result_index(model, alias, index)


class ResolveSortOperator(ResolveOperator):
    """
    Helper-Operator that implements sorting, according to RFC 7644, Section 3.4.2.3
    The ResolveResult returned by this operator contains at most 1 value, according to
    the specification:
    "[...] if it's a multi-valued attribute, resources are sorted by the value of the
    primary attribute (see Section 2.4 of [RFC7643]), if any, or else the first value
    in the list, if any. [...]"

    Since a Query can result in resources of different types, sorting by an attribute
    that is not defined for a certain resource type does not result in an error. No
    value is returned and the resource is sorted as if the attribute on the resource
    is not set.
    """

    def __init__(self, path: Optional[str]):
        super().__init__(path)

    def alias_forbidden(self, model: BaseModel, alias: Optional[str]) -> bool:
        return (
            not alias
            or model.get_field_annotation(alias, Mutability) == Mutability.write_only
            or model.get_field_annotation(alias, Returned) == Returned.never
        )

    def set_value_case_exact(self, value: any, case_exact: CaseExact):
        if isinstance(value, str) and case_exact == CaseExact.false:
            value = value.lower()
        self.value = value

    def evaluate_value_for_complex(self, model: BaseModel, alias: str):
        sub_attribute_alias = get_by_alias(model, alias, True)
        if self.alias_forbidden(model, sub_attribute_alias):
            return
        case_exact = model.get_field_annotation(sub_attribute_alias, CaseExact)
        sub_attribute_value = getattr(model, sub_attribute_alias)
        self.set_value_case_exact(sub_attribute_value, case_exact)

    def __call__(self, model: BaseModel):
        self.value = None
        if self.path:
            model, path = self.parse_path(model)
            if not path:
                return
            sub_attribute = path["sub_attribute"] or "value"

            attribute_alias = get_by_alias(model, path["attribute"], True)
            if self.alias_forbidden(model, attribute_alias):
                return

            case_exact = model.get_field_annotation(attribute_alias, CaseExact)
            attribute_value = getattr(model, attribute_alias)
            if not attribute_value:
                return

            if isinstance(attribute_value, list):
                if path["condition"]:
                    token_stream = SCIMLexer().tokenize(path["condition"])
                    condition = SCIMParser().parse(token_stream)
                    attribute_value = [
                        model
                        for model in attribute_value
                        if evaluate_filter(model, condition)
                    ]
                candidate = self.select_candidate(attribute_value)
                if isinstance(candidate, BaseModel):
                    self.evaluate_value_for_complex(candidate, sub_attribute)
                else:
                    self.set_value_case_exact(candidate, case_exact)
            elif isinstance(attribute_value, BaseModel):
                if not path["condition"]:
                    self.evaluate_value_for_complex(attribute_value, sub_attribute)
            else:
                if not path["condition"] and not path["sub_attribute"]:
                    self.set_value_case_exact(attribute_value, case_exact)
        return self.value

    def select_candidate(self, values: List[any]) -> Tuple[Optional[any], int]:
        """Selects a viable candidate from a list of possible values."""
        for value in values:
            primary = getattr(value, "primary", False)
            if primary:
                return value
        if values:
            return values[0]
        return None
