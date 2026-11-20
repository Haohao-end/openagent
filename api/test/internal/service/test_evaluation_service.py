from types import SimpleNamespace
from uuid import uuid4
import pytest

from internal.exception import NotFoundException, ValidateErrorException
from internal.model import App, Evaluation, EvaluationCase
from internal.schema.evaluation_schema import CreateEvaluationReq, GetEvaluationsReq
from internal.service.evaluation_service import EvaluationService


class _QueryStub:
    def __init__(self, items=None):
        self._items = items or []

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def offset(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._items


def test_get_evaluations_should_return_list(monkeypatch):
    account = SimpleNamespace(id=uuid4())
    app_id = uuid4()
    app = SimpleNamespace(id=app_id, account_id=account.id)
    eval_record = SimpleNamespace(
        id=uuid4(),
        app_id=app_id,
        name="EvalSet",
        created_by=account.id,
        created_at=None,
        updated_at=None,
    )
    session = SimpleNamespace(query=lambda _cls: _QueryStub([eval_record]))
    service = EvaluationService(db=SimpleNamespace(session=session))
    monkeypatch.setattr(service, "get", lambda _cls, _id: app)

    req = SimpleNamespace(page=SimpleNamespace(data=1), limit=SimpleNamespace(data=20))
    result = service.get_evaluations(app_id, req, account)
    assert len(result) == 1
    assert result[0]["id"] == str(eval_record.id)
    assert result[0]["name"] == "EvalSet"


def test_get_evaluations_should_raise_when_app_not_owned(monkeypatch):
    account = SimpleNamespace(id=uuid4())
    service = EvaluationService(db=SimpleNamespace(session=SimpleNamespace()))
    monkeypatch.setattr(service, "get", lambda _cls, _id: None)

    req = SimpleNamespace(page=SimpleNamespace(data=1), limit=SimpleNamespace(data=20))
    with pytest.raises(NotFoundException, match="该应用不存在"):
        service.get_evaluations(uuid4(), req, account)


def test_create_evaluation_should_save_and_return(monkeypatch):
    account = SimpleNamespace(id=uuid4())
    app_id = uuid4()
    app = SimpleNamespace(id=app_id, account_id=account.id)
    added = []

    session = SimpleNamespace(
        add=lambda entity: added.append(entity),
        commit=lambda: None,
        rollback=lambda: None,
    )
    service = EvaluationService(db=SimpleNamespace(session=session))
    monkeypatch.setattr(service, "get", lambda _cls, _id: app)

    req = SimpleNamespace(name=SimpleNamespace(data="Test Benchmark"))
    result = service.create_evaluation(app_id, req, account)

    assert result["name"] == "Test Benchmark"
    assert len(added) == 1
    assert added[0].app_id == app_id
    assert added[0].name == "Test Benchmark"


def test_create_evaluation_should_validate_blank_name(monkeypatch):
    account = SimpleNamespace(id=uuid4())
    app_id = uuid4()
    app = SimpleNamespace(id=app_id, account_id=account.id)

    service = EvaluationService(db=SimpleNamespace())
    monkeypatch.setattr(service, "get", lambda _cls, _id: app)

    req = SimpleNamespace(name=SimpleNamespace(data="   "))
    with pytest.raises(ValidateErrorException, match="评测集名称不能为空"):
        service.create_evaluation(app_id, req, account)


def test_get_evaluation_should_return_record(monkeypatch):
    account = SimpleNamespace(id=uuid4())
    app_id = uuid4()
    eval_id = uuid4()
    app = SimpleNamespace(id=app_id, account_id=account.id)
    eval_record = SimpleNamespace(
        id=eval_id,
        app_id=app_id,
        name="EvalSet",
        created_by=account.id,
        created_at=None,
        updated_at=None,
    )
    mock_query = SimpleNamespace(
        filter=lambda *_a, **_kw: SimpleNamespace(first=lambda: eval_record)
    )
    service = EvaluationService(db=SimpleNamespace(session=SimpleNamespace(query=lambda _c: mock_query)))
    monkeypatch.setattr(service, "get", lambda _cls, _id: app)

    res = service.get_evaluation(app_id, eval_id, account)
    assert res["id"] == str(eval_id)
    assert res["name"] == "EvalSet"


def test_update_evaluation_should_modify_name(monkeypatch):
    account = SimpleNamespace(id=uuid4())
    app_id = uuid4()
    eval_id = uuid4()
    app = SimpleNamespace(id=app_id, account_id=account.id)
    eval_record = SimpleNamespace(
        id=eval_id,
        app_id=app_id,
        name="OldName",
        created_by=account.id,
        created_at=None,
        updated_at=None,
    )
    mock_query = SimpleNamespace(
        filter=lambda *_a, **_kw: SimpleNamespace(first=lambda: eval_record)
    )
    service = EvaluationService(db=SimpleNamespace(session=SimpleNamespace(
        query=lambda _c: mock_query,
        commit=lambda: None,
        rollback=lambda: None,
    )))
    monkeypatch.setattr(service, "get", lambda _cls, _id: app)

    req = SimpleNamespace(name=SimpleNamespace(data="NewName"))
    res = service.update_evaluation(app_id, eval_id, req, account)
    assert res["name"] == "NewName"
    assert eval_record.name == "NewName"


def test_delete_evaluation_should_remove_cases_and_record(monkeypatch):
    account = SimpleNamespace(id=uuid4())
    app_id = uuid4()
    eval_id = uuid4()
    app = SimpleNamespace(id=app_id, account_id=account.id)
    eval_record = SimpleNamespace(id=eval_id, app_id=app_id)
    deleted = []

    case_query = SimpleNamespace(
        filter=lambda *_a, **_kw: SimpleNamespace(delete=lambda: None)
    )
    eval_query = SimpleNamespace(
        filter=lambda *_a, **_kw: SimpleNamespace(first=lambda: eval_record)
    )

    def _query(cls):
        if cls is EvaluationCase:
            return case_query
        return eval_query

    session = SimpleNamespace(
        query=_query,
        delete=lambda entity: deleted.append(entity),
        commit=lambda: None,
        rollback=lambda: None,
    )
    service = EvaluationService(db=SimpleNamespace(session=session))
    monkeypatch.setattr(service, "get", lambda _cls, _id: app)

    res = service.delete_evaluation(app_id, eval_id, account)
    assert res["id"] == str(eval_id)
    assert len(deleted) == 1
    assert deleted[0] == eval_record
