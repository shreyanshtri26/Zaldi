"""Command line: ``python -m zaldi`` (terminal chat) and ``python -m zaldi ingest`` (rebuild the product index),
and ``python -m zaldi import-images <folder>`` (link photos named after product codes)."""
import sys

from zaldi.db import init_db
from zaldi.services.chat_service import handle_query


def chat() -> None:
    init_db()
    print("Welcome to Zaldi! Type 'exit' to quit.")
    while (message := input("\nYou: ").strip()).lower() != "exit":
        if not message:
            continue
        try:
            result = handle_query(message, session_id="terminal")
            print(f"Zaldi ({result['type']}): {result['response']}")
        except Exception as exc:
            print(f"An error occurred: {exc}")


def main() -> None:
    if sys.argv[1:2] == ["ingest"]:
        from zaldi.search.ingest import ingest

        print(f"Indexed {ingest()} products.")
    elif sys.argv[1:2] == ["import-images"]:
        from pathlib import Path

        from zaldi.errors import ValidationError
        from zaldi.services.product_images import import_folder

        init_db()
        try:
            report = import_folder(Path(sys.argv[2])) if len(sys.argv) > 2 else None
        except ValidationError as exc:
            sys.exit(str(exc))
        if report is None:
            sys.exit("usage: python -m zaldi import-images <folder with files named like P001.jpg>")
        print(f"Linked {len(report['linked'])} photos.")
        for name, why in report["rejected"]:
            print(f"  skipped {name}: {why}")
        if report["unmatched"]:
            print(f"  no product with that code: {', '.join(report['unmatched'])}")
        print(f"{len(report['without_photo'])} products still have no photo.")
    else:
        chat()


if __name__ == "__main__":
    main()
