import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import set_telegram  # noqa: E402


def test_find_chats_lists_private_chats_newest_first_once_each():
    updates = [
        {"update_id": 1, "message": {"chat": {"id": 42, "type": "private", "first_name": "Matt"}}},
        {"update_id": 2, "message": {"chat": {"id": -100, "type": "group", "title": "Family"}}},
        {"update_id": 3, "message": {"chat": {"id": 7, "type": "private", "username": "someone"}}},
        {"update_id": 4, "edited_message": {"chat": {"id": 42, "type": "private", "first_name": "Matt"}}},
    ]
    assert set_telegram.find_chats(updates) == [("42", "Matt"), ("7", "someone")]


def test_find_chats_handles_no_messages():
    assert set_telegram.find_chats([]) == []
    assert set_telegram.find_chats(None) == []
