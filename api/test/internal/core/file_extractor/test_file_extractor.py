from pathlib import Path
from types import SimpleNamespace

import pytest

from internal.core.file_extractor.file_extractor import FileExtractor
import internal.core.file_extractor.file_extractor as extractor_module


def _patch_all_loaders(monkeypatch):
    def _loader_factory(label):
        class _Loader:
            def __init__(self, _file_path):
                self.label = label

            def load(self):
                return [
                    SimpleNamespace(page_content=f"{self.label}-part-1"),
                    SimpleNamespace(page_content=f"{self.label}-part-2"),
                ]

        return _Loader

    monkeypatch.setattr(extractor_module, "UnstructuredExcelLoader", _loader_factory("excel"))
    monkeypatch.setattr(extractor_module, "UnstructuredPDFLoader", _loader_factory("pdf"))
    monkeypatch.setattr(extractor_module, "UnstructuredMarkdownLoader", _loader_factory("markdown"))
    monkeypatch.setattr(extractor_module, "UnstructuredHTMLLoader", _loader_factory("html"))
    monkeypatch.setattr(extractor_module, "UnstructuredCSVLoader", _loader_factory("csv"))
    monkeypatch.setattr(extractor_module, "UnstructuredPowerPointLoader", _loader_factory("ppt"))
    monkeypatch.setattr(extractor_module, "UnstructuredWordDocumentLoader", _loader_factory("word"))
    monkeypatch.setattr(extractor_module, "UnstructuredXMLLoader", _loader_factory("xml"))
    monkeypatch.setattr(extractor_module, "UnstructuredFileLoader", _loader_factory("unstructured_file"))
    monkeypatch.setattr(extractor_module, "TextLoader", _loader_factory("text"))


@pytest.mark.parametrize(
    "file_name,is_unstructured,expected_prefix",
    [
        ("demo.xlsx", True, "excel"),
        ("demo.xls", True, "excel"),
        ("demo.pdf", True, "pdf"),
        ("demo.md", True, "markdown"),
        ("demo.markdown", True, "markdown"),
        ("demo.htm", True, "html"),
        ("demo.html", True, "html"),
        ("demo.csv", True, "csv"),
        ("demo.ppt", True, "ppt"),
        ("demo.pptx", True, "ppt"),
        ("demo.doc", True, "word"),
        ("demo.docx", True, "word"),
        ("demo.xml", True, "xml"),
        ("demo.txt", True, "unstructured_file"),
        ("demo.txt", False, "text"),
    ],
)
def test_load_from_file_should_pick_loader_by_extension(monkeypatch, file_name, is_unstructured, expected_prefix):
    _patch_all_loaders(monkeypatch)

    docs = FileExtractor.load_from_file(
        file_path=f"/tmp/{file_name}",
        return_text=False,
        is_unstructured=is_unstructured,
    )

    assert docs[0].page_content.startswith(expected_prefix)


def test_load_from_file_should_join_text_when_return_text(monkeypatch):
    _patch_all_loaders(monkeypatch)

    text = FileExtractor.load_from_file(
        file_path="/tmp/demo.txt",
        return_text=True,
        is_unstructured=False,
    )

    assert text == "text-part-1\n\ntext-part-2"


def test_load_should_download_file_and_delegate_to_load_from_file(monkeypatch):
    calls = {}

    class _FakeCosService:
        @staticmethod
        def download_file(key, file_path):
            calls["download"] = (key, file_path)
            Path(file_path).write_text("ok", encoding="utf-8")

    def _fake_load_from_file(cls, file_path, return_text=False, is_unstructured=True):
        calls["load_from_file"] = (file_path, return_text, is_unstructured)
        return "parsed"

    monkeypatch.setattr(FileExtractor, "load_from_file", classmethod(_fake_load_from_file))
    extractor = FileExtractor(cos_service=_FakeCosService())

    result = extractor.load(
        upload_file=SimpleNamespace(key="folder/a.md"),
        return_text=True,
        is_unstructured=False,
    )

    assert result == "parsed"
    assert calls["download"][0] == "folder/a.md"
    assert Path(calls["download"][1]).name == "a.md"
    assert calls["load_from_file"] == (calls["download"][1], True, False)
