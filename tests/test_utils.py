from pydantic_scim2.utils import merge_dicts


def test_merge_dicts():
    assert merge_dicts({"bar": True}, {"sub": {"always": True}}) == {
        "bar": True,
        "sub": {"always": True},
    }
