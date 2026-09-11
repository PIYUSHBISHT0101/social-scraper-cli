"""Universal Terminal CLI for Social Media Scraping (YouTube, Reddit, Instagram)."""
import os
import sys
import yaml
import argparse
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm

from .core.detector import TextAnalyzer
from .core.filter_engine import FilterEngine, FilterConfig
from .core.deduplicator import Deduplicator
from .core.language import LanguageDetector
from .core.stats import DatasetStatistics
from .core.exporter import DatasetExporter

from .scrapers.youtube import YouTubeScraper
from .scrapers.reddit import RedditScraper
from .scrapers.instagram import InstagramScraper

# Ensure utf-8 encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=True)

BANNER = """[bold cyan]
  ================================================================================
  SOCIAL SCRAPER CLI : Multi-Platform Terminal Comment Extractor & NLP Studio
  ================================================================================
[/bold cyan]
[bold white]Universal Terminal Comment Extractor & NLP Intelligence Suite[/bold white]
[dim]Platforms: YouTube • Reddit • Instagram | Multi-Format Export: Excel • CSV • JSONL[/dim]
"""


def print_banner():
    try:
        console.print(BANNER)
    except Exception:
        print("SOCIAL SCRAPER CLI - Universal Social Media Scraper")


def setup_logger(verbose: bool = False) -> logging.Logger:
    """Setup structured logger."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    return logging.getLogger("cli")


def run_pipeline(
    platforms: List[str],
    targets_dict: Dict[str, List[str]],
    limit_per_target: int,
    filter_config: FilterConfig,
    export_formats: List[str],
    output_dir: str = "data/exports",
    instagram_session_id: Optional[str] = None,
    instagram_username: Optional[str] = None,
    instagram_password: Optional[str] = None,
    reddit_username: Optional[str] = None,
    reddit_password: Optional[str] = None,
    output_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute scraping, enrichment, filtering, deduplication, and export."""
    console.print(Panel("[bold green]Starting Data Pipeline[/bold green]", border_style="green"))

    raw_comments = []
    scrapers = {}

    # Initialize Scrapers
    if "youtube" in platforms:
        scrapers["youtube"] = YouTubeScraper()
    if "reddit" in platforms:
        scrapers["reddit"] = RedditScraper(username=reddit_username, password=reddit_password)
    if "instagram" in platforms:
        scrapers["instagram"] = InstagramScraper(
            session_id=instagram_session_id,
            username=instagram_username,
            password=instagram_password,
        )

    # Scrape Phase with Progress Display
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        for plat, scraper in scrapers.items():
            t_list = targets_dict.get(plat, [])
            if not t_list:
                continue

            task_id = progress.add_task(f"[cyan]{plat.capitalize()}[/cyan] ({len(t_list)} targets)", total=len(t_list) * limit_per_target)

            def progress_cb(name, current, total):
                progress.update(task_id, description=f"[cyan]{plat.capitalize()}[/cyan] -> [yellow]{name}[/yellow]")

            comments = scraper.scrape(t_list, limit_per_target=limit_per_target, progress_callback=progress_cb)
            raw_comments.extend(comments)
            progress.update(task_id, completed=len(t_list) * limit_per_target)

    console.print(f"\n[bold green]✓ Scraped {len(raw_comments)} raw comments across {len(platforms)} platform(s)[/bold green]")

    if not raw_comments:
        console.print("[bold red]No comments collected. Check your targets or credentials.[/bold red]")
        return {}

    # Enrichment & NLP Phase
    with console.status("[bold blue]Enriching with Unicode emoji & language detection...[/bold blue]"):
        analyzer = TextAnalyzer()
        lang_detector = LanguageDetector()
        enriched = []
        for c in raw_comments:
            e = analyzer.enrich_comment(c)
            e["language"] = lang_detector.detect(e.get("comment", ""))
            enriched.append(e)

    # Filtering Phase
    with console.status("[bold blue]Evaluating custom filter rules...[/bold blue]"):
        engine = FilterEngine(filter_config)
        filtered, filter_stats = engine.filter_batch(enriched)

    console.print(f"[bold cyan]✓ Filtered:[/bold cyan] Kept [green]{len(filtered)}[/green] / {len(enriched)} (Filtered out {filter_stats['rejected']})")

    # Deduplication Phase
    with console.status("[bold blue]Deduplicating comment IDs and exact text...[/bold blue]"):
        dedup = Deduplicator(by_comment_id=True, by_exact_text=True)
        final_comments, dedup_stats = dedup.deduplicate(filtered)

    console.print(f"[bold cyan]✓ Deduplicated:[/bold cyan] Kept [green]{len(final_comments)}[/green] clean comments (Purged {dedup_stats['total_removed']} duplicates)")

    # Statistics Calculation
    stats_calc = DatasetStatistics()
    summary_stats = stats_calc.calculate_summary(final_comments)
    emoji_stats = stats_calc.calculate_emoji_frequency(final_comments)
    source_stats = stats_calc.calculate_source_breakdown(final_comments)

    # Export Phase
    if not output_filename:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"social_comments_{timestamp_str}"

    exporter = DatasetExporter(output_dir=output_dir)
    generated_files = exporter.export_all(
        comments=final_comments,
        summary_stats=summary_stats,
        emoji_stats=emoji_stats,
        source_stats=source_stats,
        formats=export_formats,
        base_filename=output_filename,
    )

    # Print Summary Tables
    display_summary_table(summary_stats, generated_files)
    if emoji_stats:
        display_emoji_table(emoji_stats[:10])

    return {
        "final_comments": final_comments,
        "summary": summary_stats,
        "files": generated_files,
    }


def display_summary_table(summary: Dict[str, Any], files: Dict[str, str]):
    """Print clean summary table in terminal."""
    table = Table(title="[bold green]📊 DATASET SUMMARY[/bold green]", border_style="cyan")
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="bold yellow")

    for k, v in summary.items():
        table.add_row(k.replace("_", " ").title(), str(v))

    console.print(table)

    file_table = Table(title="[bold green]📁 EXPORTED FILES[/bold green]", border_style="green")
    file_table.add_column("Format", style="bold cyan")
    file_table.add_column("File Path", style="bold white")

    for fmt, path in files.items():
        file_table.add_row(fmt.upper(), os.path.abspath(path))

    console.print(file_table)


def display_emoji_table(top_emojis: List[Dict[str, Any]]):
    """Print top emojis table in terminal."""
    table = Table(title="[bold magenta]🏆 TOP EMOJIS DETECTED[/bold magenta]", border_style="magenta")
    table.add_column("Rank", justify="center")
    table.add_column("Emoji", justify="center")
    table.add_column("Frequency", justify="right")
    table.add_column("% of Comments", justify="right")
    table.add_column("% of Occurrences", justify="right")

    for i, e in enumerate(top_emojis, 1):
        table.add_row(str(i), e["emoji"], str(e["frequency"]), e["percentage_of_comments"], e["percentage_of_all_occurrences"])

    console.print(table)


def run_interactive_wizard():
    """Step-by-step interactive command-line onboarding and scraping wizard."""
    print_banner()
    console.print(Panel(
        "[bold yellow]⚡ Interactive Social Scraper Studio[/bold yellow]\n"
        "Configure platform selection, credentials, targets, filters, and exports in 5 quick steps.",
        border_style="yellow",
    ))

    # STEP 1: What do you want to scrape? (Platform Selection)
    console.print("\n[bold cyan]▶ STEP 1: Select Platform[/bold cyan]")
    console.print("  [1] YouTube (Channels / Videos)")
    console.print("  [2] Reddit (Subreddits / Posts)")
    console.print("  [3] Instagram (Profiles / Posts)")
    console.print("  [4] All Platforms (Multi-Platform Combined)")

    plat_choice = Prompt.ask("Choose option", choices=["1", "2", "3", "4"], default="1")
    plat_map = {
        "1": ["youtube"],
        "2": ["reddit"],
        "3": ["instagram"],
        "4": ["youtube", "reddit", "instagram"],
    }
    platforms = plat_map[plat_choice]

    # STEP 2: Platform Authentication & Live Verification
    console.print("\n[bold cyan]▶ STEP 2: Authentication & Account Verification[/bold cyan]")
    ig_session_id = None
    ig_username = None
    ig_password = None
    reddit_username = None
    reddit_password = None

    # 2A. Instagram Authentication
    if "instagram" in platforms:
        console.print("\n[bold magenta]📸 Instagram Authentication Setup:[/bold magenta]")
        console.print("  [1] Browser Session ID Cookie (Recommended - Quick & Safe)")
        console.print("  [2] Username & Password (Direct Login)")
        console.print("  [3] Skip Authentication (Public Posts Only)")

        ig_auth_choice = Prompt.ask("Select Instagram login method", choices=["1", "2", "3"], default="1")

        if ig_auth_choice == "1":
            ig_session_id = Prompt.ask("Paste your Instagram sessionid cookie")
            with console.status("[bold blue]Verifying Instagram session cookie...[/bold blue]"):
                temp_ig = InstagramScraper()
                success, msg = temp_ig.login_with_session_id(ig_session_id)
                if success:
                    console.print(f"[bold green]✓ {msg}![/bold green]")
                else:
                    console.print(f"[bold yellow]⚠ Warning: {msg}. Continuing with fallback.[/bold yellow]")

        elif ig_auth_choice == "2":
            ig_username = Prompt.ask("Instagram Username (e.g. your_username)")
            ig_password = Prompt.ask("Instagram Password", password=True)
            with console.status("[bold blue]Logging into Instagram...[/bold blue]"):
                temp_ig = InstagramScraper()
                success, msg = temp_ig.login_with_credentials(ig_username, ig_password)
                if success:
                    console.print(f"[bold green]✓ {msg}![/bold green]")
                else:
                    console.print(f"[bold red]✗ {msg}.[/bold red]")
                    retry = Confirm.ask("Would you like to continue anyway?", default=True)
                    if not retry:
                        sys.exit(0)
        else:
            console.print("[dim]Continuing in unauthenticated public mode.[/dim]")

    # 2B. Reddit Authentication
    if "reddit" in platforms:
        console.print("\n[bold orange3]🤖 Reddit Authentication Setup:[/bold orange3]")
        console.print("  [1] Authenticated Account (Username & Password)")
        console.print("  [2] Anonymous / Public Web Mode (No login required - High Speed)")

        rd_auth_choice = Prompt.ask("Select Reddit login mode", choices=["1", "2"], default="2")

        if rd_auth_choice == "1":
            reddit_username = Prompt.ask("Reddit Username (e.g. my_reddit_user)")
            reddit_password = Prompt.ask("Reddit Password", password=True)
            with console.status("[bold blue]Verifying Reddit credentials...[/bold blue]"):
                temp_rd = RedditScraper()
                success, msg = temp_rd.authenticate(reddit_username, reddit_password)
                if success:
                    console.print(f"[bold green]✓ {msg}![/bold green]")
                else:
                    console.print(f"[bold yellow]⚠ {msg}. Falling back to public web mode.[/bold yellow]")
        else:
            console.print("[bold green]✓ Public Web Mode active (No login or API keys needed)![/bold green]")

    # 2C. YouTube Authentication
    if "youtube" in platforms:
        console.print("\n[bold red]▶ YouTube Status:[/bold red]")
        console.print("[bold green]✓ Public high-speed extraction active (Zero login or API keys required)![/bold green]")

    # STEP 3: Targets Specification ("What do you want to scrape?")
    console.print("\n[bold cyan]▶ STEP 3: Target Specification[/bold cyan]")
    targets_dict = {}

    if "youtube" in platforms:
        yt_input = Prompt.ask(
            "Enter YouTube channel handles (e.g. @CarryMinati, @MrBeast) or video URLs (comma-separated)",
            default="@CarryMinati"
        )
        targets_dict["youtube"] = [t.strip() for t in yt_input.split(",") if t.strip()]

    if "reddit" in platforms:
        rd_input = Prompt.ask(
            "Enter Subreddits (e.g. r/technology, r/india) or post URLs (comma-separated)",
            default="r/technology"
        )
        targets_dict["reddit"] = [t.strip() for t in rd_input.split(",") if t.strip()]

    if "instagram" in platforms:
        ig_input = Prompt.ask(
            "Enter Instagram accounts (e.g. @dhruvrathee, cockroachjantaparty) or post URLs (comma-separated)",
            default="cockroachjantaparty"
        )
        targets_dict["instagram"] = [t.strip() for t in ig_input.split(",") if t.strip()]

    limit = int(Prompt.ask("\nHow many comments to scrape per target?", default="500"))

    # STEP 4: What kind of thing do you want to scrape? (Filtering)
    console.print("\n[bold cyan]▶ STEP 4: Content & Modality Filtering[/bold cyan]")
    console.print("  [1] All Comments (Normal text + Emojis)")
    console.print("  [2] Comments WITH EMOJIS only (Must contain ≥ 1 emoji)")
    console.print("  [3] Comments WITHOUT emojis (Pure text only)")
    console.print("  [4] EMOJI-ONLY comments (Pure emoji reactions, no words)")
    console.print("  [5] Only Questions (Comments containing '?')")
    console.print("  [6] Custom Filter (Keywords, minimum likes)")

    filter_choice = Prompt.ask("Choose filter option", choices=["1", "2", "3", "4", "5", "6"], default="1")

    emoji_mode = "ALL"
    only_questions = False
    min_likes = 0
    kw_include = []
    kw_exclude = []

    if filter_choice == "2":
        emoji_mode = "WITH_EMOJI"
    elif filter_choice == "3":
        emoji_mode = "WITHOUT_EMOJI"
    elif filter_choice == "4":
        emoji_mode = "EMOJI_ONLY"
    elif filter_choice == "5":
        only_questions = True
    elif filter_choice == "6":
        emoji_mode = Prompt.ask("Emoji mode", choices=["ALL", "WITH_EMOJI", "WITHOUT_EMOJI", "EMOJI_ONLY"], default="ALL")
        only_questions = Confirm.ask("Only extract questions containing '?'?", default=False)
        min_likes = int(Prompt.ask("Minimum likes/score required", default="0"))
        inc_str = Prompt.ask("Must contain keywords (comma-separated, leave blank for none)", default="")
        exc_str = Prompt.ask("Exclude keywords (comma-separated, leave blank for none)", default="")
        kw_include = [k.strip() for k in inc_str.split(",") if k.strip()]
        kw_exclude = [k.strip() for k in exc_str.split(",") if k.strip()]

    filter_cfg = FilterConfig(
        emoji_mode=emoji_mode,
        keywords_include=kw_include,
        keywords_exclude=kw_exclude,
        only_questions=only_questions,
        min_likes=min_likes,
        remove_bots=True,
    )

    # STEP 5: Export Format Selection
    console.print("\n[bold cyan]▶ STEP 5: Export Format Selection[/bold cyan]")
    console.print("  [1] Excel Workbook (.xlsx) [4 Sheets: Comments, Summary, Emoji Stats, Sources]")
    console.print("  [2] CSV File (.csv)")
    console.print("  [3] JSON Lines (.jsonl)")
    console.print("  [4] All Formats (.xlsx + .csv + .jsonl)")

    fmt_choice = Prompt.ask("Choose export format", choices=["1", "2", "3", "4"], default="4")
    fmt_map = {
        "1": ["xlsx"],
        "2": ["csv"],
        "3": ["jsonl"],
        "4": ["xlsx", "csv", "jsonl"],
    }
    export_formats = fmt_map[fmt_choice]

    # Execute Pipeline
    run_pipeline(
        platforms=platforms,
        targets_dict=targets_dict,
        limit_per_target=limit,
        filter_config=filter_cfg,
        export_formats=export_formats,
        instagram_session_id=ig_session_id,
        instagram_username=ig_username,
        instagram_password=ig_password,
        reddit_username=reddit_username,
        reddit_password=reddit_password,
    )


def main():
    parser = argparse.ArgumentParser(description="Universal Social Media Scraper CLI (YouTube, Reddit, Instagram)")
    parser.add_argument("-p", "--platform", choices=["youtube", "reddit", "instagram", "all"], help="Platform to scrape")
    parser.add_argument("-t", "--targets", help="Comma-separated channels, subreddits, profiles, or URLs")
    parser.add_argument("-l", "--limit", type=int, default=500, help="Comment limit per target (default: 500)")
    parser.add_argument("-e", "--emoji-mode", choices=["ALL", "WITH_EMOJI", "WITHOUT_EMOJI", "EMOJI_ONLY"], default="ALL", help="Emoji filter rule")
    parser.add_argument("--keywords-include", help="Must contain keywords (comma-separated)")
    parser.add_argument("--keywords-exclude", help="Exclude keywords (comma-separated)")
    parser.add_argument("--only-questions", action="store_true", help="Filter for comments containing '?'")
    parser.add_argument("--min-likes", type=int, default=0, help="Minimum likes or score")
    parser.add_argument("-o", "--export", default="xlsx,csv,jsonl", help="Export formats (xlsx, csv, jsonl, parquet)")
    parser.add_argument("--output-dir", default="data/exports", help="Output directory")
    parser.add_argument("--output-name", help="Custom output base filename")
    parser.add_argument("--session-id", help="Instagram sessionid cookie")
    parser.add_argument("--ig-user", help="Instagram username")
    parser.add_argument("--ig-pass", help="Instagram password")
    parser.add_argument("--reddit-user", help="Reddit username")
    parser.add_argument("--reddit-pass", help="Reddit password")
    parser.add_argument("-c", "--config", help="Path to YAML configuration file")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run interactive terminal wizard")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose debug logging")

    args = parser.parse_args()

    if args.interactive or len(sys.argv) == 1:
        run_interactive_wizard()
        return

    print_banner()

    # Load from config YAML if provided
    if args.config and os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        platforms = cfg.get("platforms", ["youtube"])
        targets_dict = cfg.get("targets", {})
        limit = cfg.get("limit", 500)
        filter_data = cfg.get("filter", {})
        filter_cfg = FilterConfig(
            emoji_mode=filter_data.get("emoji_mode", "ALL"),
            keywords_include=filter_data.get("keywords_include", []),
            keywords_exclude=filter_data.get("keywords_exclude", []),
            only_questions=filter_data.get("only_questions", False),
            min_likes=filter_data.get("min_likes", 0),
        )
        export_formats = cfg.get("export_formats", ["xlsx", "csv", "jsonl"])
        output_dir = cfg.get("output_dir", "data/exports")
        session_id = cfg.get("instagram_session_id", args.session_id)
        ig_user = cfg.get("instagram_username", args.ig_user)
        ig_pass = cfg.get("instagram_password", args.ig_pass)
        rd_user = cfg.get("reddit_username", args.reddit_user)
        rd_pass = cfg.get("reddit_password", args.reddit_pass)
    else:
        if not args.platform or not args.targets:
            console.print("[bold red]Error:[/bold red] --platform and --targets are required in CLI mode, or run with -i for wizard.")
            sys.exit(1)

        platforms = ["youtube", "reddit", "instagram"] if args.platform == "all" else [args.platform]
        target_list = [t.strip() for t in args.targets.split(",") if t.strip()]
        targets_dict = {plat: target_list for plat in platforms}
        limit = args.limit

        kw_include = [k.strip() for k in args.keywords_include.split(",")] if args.keywords_include else []
        kw_exclude = [k.strip() for k in args.keywords_exclude.split(",")] if args.keywords_exclude else []

        filter_cfg = FilterConfig(
            emoji_mode=args.emoji_mode,
            keywords_include=kw_include,
            keywords_exclude=kw_exclude,
            only_questions=args.only_questions,
            min_likes=args.min_likes,
        )
        export_formats = [f.strip() for f in args.export.split(",") if f.strip()]
        output_dir = args.output_dir
        session_id = args.session_id
        ig_user = args.ig_user
        ig_pass = args.ig_pass
        rd_user = args.reddit_user
        rd_pass = args.reddit_pass

    run_pipeline(
        platforms=platforms,
        targets_dict=targets_dict,
        limit_per_target=limit,
        filter_config=filter_cfg,
        export_formats=export_formats,
        output_dir=output_dir,
        instagram_session_id=session_id,
        instagram_username=ig_user,
        instagram_password=ig_pass,
        reddit_username=rd_user,
        reddit_password=rd_pass,
        output_filename=args.output_name,
    )


if __name__ == "__main__":
    main()
