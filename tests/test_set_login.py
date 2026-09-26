import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import set_login  # noqa: E402


def test_control_characters_are_refused():
    problems = set_login.find_problems({"XC_URL": "http://h", "XC_USERNAME": "abc", "XC_PASSWORD": "\x16"})
    assert problems == ["XC_PASSWORD contains an invisible control character - paste with right-click, not Ctrl+V"]


def test_clean_login_has_no_problems():
    assert set_login.find_problems({"XC_URL": "http://h", "XC_USERNAME": "026a1fac9b", "XC_PASSWORD": "a1b2c3"}) == []
