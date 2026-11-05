"""Command line: ``python -m zaldi`` (terminal chat) and ``python -m zaldi ingest`` (rebuild the product index)."""
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
    else:
        chat()


if __name__ == "__main__":
    main()
