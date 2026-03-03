from contextlib import contextmanager

import pytest

from internal.exception import FailException
from internal.service.base_service import BaseService


class _DummySession:
    def __init__(self):
        self.added = []
        self.deleted = []
        self.query_model = None
        self.query_primary_key = None
        self.query_return_value = None

    def add(self, model_instance):
        self.added.append(model_instance)

    def delete(self, model_instance):
        self.deleted.append(model_instance)

    def query(self, model):
        self.query_model = model
        session = self

        class _Query:
            @staticmethod
            def get(primary_key):
                session.query_primary_key = primary_key
                return session.query_return_value

        return _Query()


class _DummyDB:
    def __init__(self):
        self.session = _DummySession()

    @contextmanager
    def auto_commit(self):
        yield


class _DummyModel:
    def __init__(self, name="", age=0):
        self.name = name
        self.age = age


class TestBaseService:
    def test_create_should_add_model_instance(self):
        service = BaseService()
        service.db = _DummyDB()

        model_instance = service.create(_DummyModel, name="alice", age=18)

        assert isinstance(model_instance, _DummyModel)
        assert model_instance.name == "alice"
        assert model_instance.age == 18
        assert service.db.session.added == [model_instance]

    def test_update_should_change_existing_fields(self):
        service = BaseService()
        service.db = _DummyDB()
        model_instance = _DummyModel(name="before", age=1)

        updated = service.update(model_instance, name="after", age=2)

        assert updated is model_instance
        assert model_instance.name == "after"
        assert model_instance.age == 2

    def test_update_should_raise_when_field_not_exists(self):
        service = BaseService()
        service.db = _DummyDB()
        model_instance = _DummyModel(name="before", age=1)

        with pytest.raises(FailException):
            service.update(model_instance, unknown_field="x")

    def test_delete_should_call_session_delete(self):
        service = BaseService()
        service.db = _DummyDB()
        model_instance = _DummyModel(name="demo")

        deleted = service.delete(model_instance)

        assert deleted is model_instance
        assert service.db.session.deleted == [model_instance]

    def test_get_should_delegate_to_query_get(self):
        service = BaseService()
        service.db = _DummyDB()
        expected = _DummyModel(name="found")
        service.db.session.query_return_value = expected

        result = service.get(_DummyModel, "pk-1")

        assert result is expected
        assert service.db.session.query_model is _DummyModel
        assert service.db.session.query_primary_key == "pk-1"
