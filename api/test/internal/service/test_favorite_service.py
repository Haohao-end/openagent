from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from internal.service.favorite_service import FavoriteService


class _Query:
    def __init__(self, *, all_result=None):
        self._all_result = all_result if all_result is not None else []

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all_result


class _Session:
    def __init__(self, queries):
        self._queries = list(queries)

    def query(self, *_args, **_kwargs):
        return self._queries.pop(0)


def _service(*, app_items=None, workflow_items=None, queries=None):
    return FavoriteService(
        db=SimpleNamespace(session=_Session(queries or [])),
        public_app_service=SimpleNamespace(get_my_favorites=lambda _account: app_items or []),
        public_workflow_service=SimpleNamespace(get_my_favorites=lambda _account: workflow_items or []),
    )


class TestFavoriteService:
    def test_get_favorites_should_merge_sort_and_normalize_types(self):
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        workflow_id = uuid4()
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        later = datetime(2026, 1, 2, tzinfo=UTC)
        service = _service(
            app_items=[
                {
                    "id": str(app_id),
                    "name": "应用A",
                    "description": "应用描述",
                    "creator_name": "Alice",
                    "creator_avatar": "",
                    "created_at": 10,
                }
            ],
            workflow_items=[
                {
                    "id": str(workflow_id),
                    "name": "工作流B",
                    "description": "工作流描述",
                    "account_name": "Bob",
                    "account_avatar": "",
                    "created_at": 20,
                }
            ],
            queries=[
                _Query(all_result=[SimpleNamespace(app_id=app_id, created_at=earlier)]),
                _Query(all_result=[SimpleNamespace(workflow_id=workflow_id, created_at=later)]),
            ],
        )

        items = service.get_favorites(account)

        assert [item["resource_type"] for item in items] == ["workflow", "app"]
        assert items[0]["creator_name"] == "Bob"
        assert items[1]["creator_name"] == "Alice"
        assert items[0]["action_at"] > items[1]["action_at"]

    def test_get_favorites_should_support_search_and_resource_type_filter(self):
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        workflow_id = uuid4()
        created_at = datetime(2026, 1, 1, tzinfo=UTC)
        service = _service(
            app_items=[
                {
                    "id": str(app_id),
                    "name": "天气应用",
                    "description": "查询天气",
                    "creator_name": "Alice",
                    "creator_avatar": "",
                    "created_at": 10,
                }
            ],
            workflow_items=[
                {
                    "id": str(workflow_id),
                    "name": "代码工作流",
                    "description": "自动生成代码",
                    "account_name": "Bob",
                    "account_avatar": "",
                    "created_at": 20,
                }
            ],
            queries=[
                _Query(all_result=[SimpleNamespace(app_id=app_id, created_at=created_at)]),
                _Query(all_result=[SimpleNamespace(workflow_id=workflow_id, created_at=created_at)]),
            ],
        )

        app_only = service.get_favorites(account, resource_type="app")
        workflow_search = service.get_favorites(account, search_word="代码")

        assert len(app_only) == 1
        assert app_only[0]["resource_type"] == "app"
        assert len(workflow_search) == 1
        assert workflow_search[0]["resource_type"] == "workflow"
