"""Command line entry point."""

from __future__ import annotations

import argparse
import logging
import os

from config import PipelineConfig
from pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF_Crusher")
    parser.add_argument("pdf", help="PDF file to process")
    parser.add_argument("-o", "--output", default="outputs", help="Output directory")
    parser.add_argument("--groq", action="store_true", help="Use Groq to anonymize names")
    parser.add_argument("--groq-api-key", default=os.getenv("GROQ_API_KEY"), help="Groq API key")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = PipelineConfig(use_groq=args.groq, groq_api_key=args.groq_api_key)

    try:
        result = run_pipeline(args.pdf, args.output, config=config)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Done: {result['output_dir']}")
    print("\nArquivos para anexar ao Claude:")
    for file_name in result["claude_files"]:
        print(f"- {file_name}")
    print("\nAuditoria local:")
    for file_name in result["audit_files"]:
        print(f"- {file_name}")


if __name__ == "__main__":
    main()
