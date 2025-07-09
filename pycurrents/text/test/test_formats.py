
from pycurrents.text.formats import _str, PrettyDict

def test_str_toml_bool():
    filename = "filename.toml"
    s_bool_true = True
    s_bool_false = False

    result_1 = _str(s_bool_true, filename)
    result_2 = _str(s_bool_false, filename)

    expected_1 = "True"
    expected_2 = "False"
    assert result_1 == expected_1, f"_str did not return {expected_1} when passed a filename {filename} and {result_1}"
    assert result_2 == expected_2, f"_str did not return {expected_2} when passed a filename {filename} and {result_2}"

def test_str_toml_tuple():
    filename = "filename.toml"
    s_tuple = ("David is amazing")
    result = _str(s_tuple, filename)

    expected = "David is amazing"
    assert result == expected


def test_str_toml_none():
    filename = "filename.toml"
    s_None = None
    result = _str(s_None, filename)

    expected = 'None'

    assert expected == result


def test_str_toml():
    thisdict = {
        "first_name": "David",
        "last_name": "Vadnais",
        "flaws": None
    }
    expected = '{ first_name = "David", last_name = "Vadnais", flaws = "None" }'

    result_dict = PrettyDict(thisdict)
    assert result_dict, "Failed to init PrettyDict"

    assert result_dict._str_toml() == expected

