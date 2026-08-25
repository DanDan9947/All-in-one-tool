from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.errors import AppError
from app.services.pdf_conversion import PdfConversionService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--format", required=True, choices=("xlsx", "docx"))
    parser.add_argument("--max-pages", required=True, type=int)
    args = parser.parse_args()

    service = PdfConversionService(max_pages=args.max_pages)
    try:
        service.convert(
            Path(args.input),
            Path(args.output),
            args.format,
        )
        return 0
    except AppError as exc:
        print(
            json.dumps(
                {
                    "code": exc.code,
                    "message": exc.message,
                    "statusCode": exc.status_code,
                },
                ensure_ascii=True,
            )
        )
        return 2
    except Exception:
        print(
            json.dumps(
                {
                    "code": "INTERNAL_ERROR",
                    "message": "PDF 轉換失敗，請稍後重試",
                    "statusCode": 500,
                },
                ensure_ascii=True,
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
