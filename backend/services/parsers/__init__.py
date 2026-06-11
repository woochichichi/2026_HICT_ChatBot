# 파서 패키지 — PDF(docling_pdf) / 위키 HTML(confluence_html)
#
# docling은 무거운 선택적 의존성(미설치 환경 존재)이라 즉시 import하지 않고
# 지연 로딩(PEP 562)한다. 즉시 import하면 docling 미설치 환경에서
# confluence_html 등 다른 파서까지 ImportError로 막히는 문제가 있었음.

__all__ = ["parse_pdf", "save_parsed_document"]


def __getattr__(name):
    # 기존 `from backend.services.parsers import parse_pdf` 호환 유지 (지연 import)
    if name in ("parse_pdf", "save_parsed_document"):
        from .docling_pdf import parse_pdf, save_parsed_document
        return {"parse_pdf": parse_pdf, "save_parsed_document": save_parsed_document}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
