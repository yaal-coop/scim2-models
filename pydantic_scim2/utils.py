from functools import reduce
from typing import Dict
from typing import Optional


def int_to_str(status: Optional[int]) -> Optional[str]:
    return None if status is None else str(status)


def merge_dicts(*dicts):
    def merge(a: Dict, b: Dict, path=[]):
        for key in b:
            if key in a:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    merge(a[key], b[key], path + [str(key)])
                elif a[key] != b[key]:
                    raise Exception("Conflict at " + ".".join(path + [str(key)]))
            else:
                a[key] = b[key]
        return a

    return reduce(merge, dicts)
