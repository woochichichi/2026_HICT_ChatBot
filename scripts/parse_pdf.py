"""CLI: PDF 파싱 후 data/processed/{doc_id}/docling.json 저장."""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 path에 넣기
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.parsers.docling_pdf import parse_pdf, save_parsed_document


def main():
    parser = argparse.ArgumentParser(description="Docling으로 PDF 파싱 후 JSON 저장")
    parser.add_argument("--input", "-i", required=True, help="입력 PDF 경로")
    args = parser.parse_args()

    parsed = parse_pdf(args.input)
    out_path = save_parsed_document(parsed)

    print("doc_id:", parsed.doc_id)
    print("page_count:", parsed.page_count)
    print("block_count:", len(parsed.blocks))
    print("output_path:", out_path)


if __name__ == "__main__":
    main()
