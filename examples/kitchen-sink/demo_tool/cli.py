import argparse


def build_parser() -> argparse.ArgumentParser:
    # begin-parser
    parser = argparse.ArgumentParser(prog="demo-tool", description="Summarize directories.")
    parser.add_argument("path", help="directory to summarize")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    # end-parser
    return parser


def main() -> None:
    build_parser().parse_args()


if __name__ == "__main__":
    main()
