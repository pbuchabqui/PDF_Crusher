"""Command line entry point."""

from __future__ import annotations

import argparse
import os

from pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF_Crusher")
    parser.add_argument("pdf", help="PDF file to process")
    parser.add_argument("-o", "--output", default="outputs", help="Output directory")
    parser.add_argument("--groq", action="store_true", help="Use Groq to anonymize names")
    parser.add_argument("--groq-api-key", default=os.getenv("GROQ_API_KEY"), help="Groq API key")
    args = parser.parse_args()

    result = run_pipeline(args.pdf, args.output, use_groq=args.groq, groq_api_key=args.groq_api_key)
    print(f"Done: {result['output_dir']}")
    print("\nArquivos para anexar ao Claude:")
    for file_name in result["claude_files"]:
        print(f"- {file_name}")
    print("\nAuditoria local:")
    for file_name in result["audit_files"]:
        print(f"- {file_name}")


if __name__ == "__main__":
    main()
