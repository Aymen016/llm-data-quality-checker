"""CLI:  python cli.py check data/customers.csv [--no-llm]"""
import sys

from src.runner import check


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--no-llm"]
    use_llm = "--no-llm" not in sys.argv

    if len(args) < 2 or args[0] != "check":
        print('Usage: python cli.py check <path.csv> [--no-llm]')
        sys.exit(1)

    result = check(args[1], use_llm=use_llm)
    print(result["report"])
    print("\nSummary:", result["summary"])
    sys.exit(0 if result["summary"]["errors"] == 0 else 2)  # nonzero exit on errors


if __name__ == "__main__":
    main()
