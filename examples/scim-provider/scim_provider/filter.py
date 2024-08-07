from types import NoneType
from typing import List

from scim2_filter_parser import ast as scim2ast
from scim2_models import BaseModel
from scim2_models import CaseExact
from scim2_models import Error

from scim_provider.utils import SCIMException
from scim_provider.utils import get_by_alias
from scim_provider.utils import parse_new_value


def evaluate_filter(
    obj: BaseModel | List[BaseModel], tree: scim2ast.AST
) -> bool | List[bool]:
    """This implementation is limited by the specifics of the
    scim2_filter_parser module.

    It works well enough for simple cases, though. It should be re-
    implemented in the future. Probably once
    https://github.com/yaal-coop/scim2-models/issues/17
    is implemented.
    """
    from scim_provider.operators import ResolveOperator
    from scim_provider.operators import ResolveResult

    match type(tree):
        case scim2ast.Filter:
            if tree.namespace is not None:
                obj = ResolveOperator(tree.namespace.attr_name)(obj).get_values()
            if isinstance(obj, List):
                return [
                    o
                    for o in obj
                    if bool(evaluate_filter(o, tree.expr)) != tree.negated
                ]
            return bool(evaluate_filter(obj, tree.expr)) != tree.negated
        case scim2ast.LogExpr:
            match tree.op:
                case "and":
                    return evaluate_filter(obj, tree.expr1) and evaluate_filter(
                        obj, tree.expr2
                    )
                case _:  # "or"
                    return evaluate_filter(obj, tree.expr1) or evaluate_filter(
                        obj, tree.expr2
                    )
        case _:  # scim2ast.AttrExpr
            path = tree.attr_path.attr_name
            sub_attribute_name = None
            if isinstance(path, scim2ast.Filter):
                resolved = evaluate_filter(obj, path)
                model = resolved[0]
                attribute_name = ""

                # FIXME: Best guesses since there is no way to know for sure by this point
                case_sensitivity = CaseExact.false
                sub_attribute_name = path.namespace.sub_attr.value
            else:
                if tree.attr_path.uri:
                    path = tree.attr_path.uri + ":" + path
                if tree.attr_path.sub_attr:
                    path += "." + tree.attr_path.sub_attr.value
                resolved = ResolveOperator(path)(obj)
                case_sensitivity = resolved.get_field_annotation(CaseExact)
                model = resolved.model
                attribute_name = resolved.attribute

            if isinstance(resolved, ResolveResult):
                value = resolved.get_values()
            else:
                value = [
                    getattr(v, get_by_alias(v, sub_attribute_name)) for v in resolved
                ]

            compare_value = None
            if tree.comp_value:
                if attribute_name:
                    compare_value = parse_new_value(
                        model, attribute_name, tree.comp_value.value
                    )
                else:
                    compare_value = tree.comp_value.value
            if not case_sensitivity and isinstance(value, str):
                value = value.lower()
                if compare_value:
                    compare_value = compare_value.lower()

            match tree.value:
                case "eq":
                    return value == compare_value
                case "ne":
                    return value != compare_value
                case "sw":
                    return value.startswith(compare_value)
                case "ew":
                    return value.endswith(compare_value)
                case "pr":
                    return bool(value)
                case "co":
                    if value is None:
                        return False
                    return compare_value in value
                case "gt":
                    check_comparable_value(value)
                    return value > compare_value
                case "lt":
                    check_comparable_value(value)
                    return value < compare_value
                case "ge":
                    check_comparable_value(value)
                    return value >= compare_value
                case _:  # "le"
                    check_comparable_value(value)
                    return value <= compare_value
    return False


def check_comparable_value(value):
    """Certain values may not be compared in a filter, see RFC 7644, section
    3.4.2.2:

    "Boolean and Binary attributes SHALL cause a failed response (HTTP
    status code 400) with "scimType" of "invalidFilter"."
    """
    if isinstance(value, (bytes, bool, NoneType)):
        raise SCIMException(Error.make_invalid_filter_error())
