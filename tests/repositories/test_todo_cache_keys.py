from app.repositories.todo_cache_keys import detail_key, list_data_key, list_version_key


def test_detail_key_format():
    assert detail_key("u1", "t1") == "todo:detail:u1:t1"


def test_list_version_key_format():
    assert list_version_key("u1") == "todo:list_version:u1"


def test_list_data_key_format():
    assert list_data_key("u1", 3) == "todo:list:u1:v3"
