from flask import Flask
from flask_weaviate import FlaskWeaviate

from config import Config


def test_weaviate_client_should_send_integration_header():
    app = Flask(__name__)
    app.config.from_object(Config())
    weaviate = FlaskWeaviate()
    weaviate.init_app(app)

    with app.app_context():
        headers = weaviate.weaviate_config["additional_headers"]

    assert headers["X-Weaviate-Client-Integration"] == "openagent/unknown"
