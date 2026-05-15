"""Command line entry point with enhanced options and progress tracking."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from config import PipelineConfig, Settings, GROQ_API_KEY_PATTERN, __version__
from pipeline import run_pipeline

console = Console()


def validate_groq_key(key: str | None) -> str | None:
    """Validate Groq API key format."""
    if key is None:
        return None
    if not GROQ_API_KEY_PATTERN.match(key):
        console.print(
            "[red]Erro:[/red] Formato inválido de Groq API Key. "
            "Esperado formato: gsk_XXXXXXXXXXXXXXXXXXXX"
        )
        sys.exit(1)
    return key


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PDF_Crusher - Transforma PDFs jurídicos em contexto para LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  %(prog)s documento.pdf                          Processa com configurações padrão
  %(prog)s documento.pdf --groq --groq-api-key gsk_...  Com anonimização Groq
  %(prog)s documento.pdf -o ./saida --verbose     Saída customizada com logs detalhados
  %(prog)s documento.pdf --format json            Exporta em formato JSON
  %(prog)s documento.pdf --language en            Processa em inglês

Variáveis de ambiente:
  PDF_CRUSHER_GROQ_API_KEY         Chave da API Groq
  PDF_CRUSHER_OUTPUT_FORMAT        Formato de saída (markdown, json, html, txt)
  PDF_CRUSHER_LANGUAGE             Idioma (pt-BR, en, es)
  PDF_CRUSHER_DATA_RESIDENCY       Residência de dados (brazil, us, eu)
        """,
    )
    
    parser.add_argument("pdf", type=Path, help="Arquivo PDF para processar")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Diretório de saída (padrão: outputs/ ou PDF_CRUSHER_OUTPUT_DIRECTORY)",
    )
    parser.add_argument(
        "--groq",
        action="store_true",
        help="Usar Groq para anonimizar nomes de pessoas",
    )
    parser.add_argument(
        "--groq-api-key",
        default=os.getenv("GROQ_API_KEY"),
        help="Groq API key (ou use PDF_CRUSHER_GROQ_API_KEY)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "html", "txt"],
        default="markdown",
        dest="output_format",
        help="Formato de exportação (padrão: markdown)",
    )
    parser.add_argument(
        "--language",
        choices=["pt-BR", "en", "es"],
        default="pt-BR",
        dest="language",
        help="Idioma de processamento (padrão: pt-BR)",
    )
    parser.add_argument(
        "--data-residency",
        choices=["brazil", "us", "eu"],
        default="brazil",
        dest="data_residency",
        help="Requisito de residência de dados para conformidade (padrão: brazil)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="Dias de retenção dos dados processados (padrão: indefinido)",
    )
    parser.add_argument(
        "--no-audit-log",
        action="store_true",
        help="Desabilitar logs de auditoria detalhados",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Habilitar logging detalhado",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Modo silencioso (apenas erros)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not args.pdf.exists():
        console.print(f"[red]Erro:[/red] Arquivo não encontrado: {args.pdf}")
        sys.exit(1)
    
    if not args.pdf.suffix.lower() == ".pdf":
        console.print(f"[red]Erro:[/red] Arquivo deve ser PDF: {args.pdf}")
        sys.exit(1)
    
    # Setup logging
    log_level = logging.ERROR if args.quiet else (logging.DEBUG if args.verbose else logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    logger = logging.getLogger(__name__)
    
    # Validate Groq key if enabled
    groq_key = validate_groq_key(args.groq_api_key) if args.groq else None
    
    if args.groq and not groq_key:
        console.print(
            "[red]Erro:[/red] Groq API key necessária. Use --groq-api-key "
            "ou defina PDF_CRUSHER_GROQ_API_KEY"
        )
        sys.exit(1)
    
    # Create configuration
    config = PipelineConfig(
        use_groq=args.groq,
        groq_api_key=groq_key,
    )
    
    # Determine output directory
    output_dir = args.output
    if output_dir is None:
        # Try to get from environment via Settings
        try:
            settings = Settings()
            output_dir = settings.output_directory
        except Exception:
            output_dir = Path("outputs")
    
    console.print(f"\n[bold blue]⚡ PDF_Crusher v{__version__}[/bold blue]\n")
    console.print(f"📄 Arquivo: [cyan]{args.pdf.name}[/cyan]")
    console.print(f"📁 Saída: [cyan]{output_dir}[/cyan]")
    console.print(f"🔒 Modo Groq: {'[green]Ativado[/green]' if args.groq else '[yellow]Desativado[/yellow]'}")
    console.print(f"🌐 Idioma: [cyan]{args.language}[/cyan]")
    console.print(f"📊 Formato: [cyan]{args.output_format}[/cyan]\n")
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            
            task = progress.add_task("Processando PDF...", total=None)
            
            result = run_pipeline(args.pdf, output_dir, config=config)
            
            progress.update(task, completed=True)
        
        # Success output
        console.print("\n[bold green]✅ Processamento concluído![/bold green]\n")
        
        console.print("[bold]Arquivos para anexar ao Claude:[/bold]")
        for file_name in result["claude_files"]:
            console.print(f"  [green]✓[/green] {file_name}")
        
        console.print("\n[bold]Arquivos de auditoria local:[/bold]")
        for file_name in result["audit_files"]:
            console.print(f"  📋 {file_name}")
        
        console.print(f"\n💾 Diretório de saída: [cyan]{result['output_dir']}[/cyan]\n")
        
    except FileNotFoundError as exc:
        console.print(f"\n[red]❌ Erro de arquivo:[/red] {exc}")
        sys.exit(1)
    except ValueError as exc:
        console.print(f"\n[red]❌ Erro de validação:[/red] {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        error_type = "Groq" if "Groq" in str(exc) else "Processamento"
        console.print(f"\n[red]❌ Erro em {error_type}:[/red] {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error")
        console.print(f"\n[red]❌ Erro inesperado:[/red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
