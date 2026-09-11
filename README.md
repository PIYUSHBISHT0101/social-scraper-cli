# ⚡ Social Scraper CLI

> **Universal Terminal Comment Extractor, NLP Filtering & Dataset Intelligence Studio**  
> Effortlessly scrape, filter, deduplicate, and analyze comments from **YouTube**, **Reddit**, and **Instagram** from your terminal.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/Platforms-YouTube%20%7C%20Reddit%20%7C%20Instagram-red.svg)](#supported-platforms)
[![Formats](https://img.shields.io/badge/Export-Excel%20%7C%20CSV%20%7C%20JSONL%20%7C%20Parquet-orange.svg)](#export-formats)

---

## 🚀 Key Features

* **Multi-Platform Support**: Seamlessly extract comments across **YouTube** (channels & video URLs), **Reddit** (subreddits & post URLs), and **Instagram** (profiles & post URLs).
* **Interactive Terminal Wizard**: Run `python run.py -i` for a guided step-by-step terminal UI with live progress bars and colored summary tables.
* **Custom Filter Engine**:
  * **Emoji Filtering**: `ALL`, `WITH_EMOJI` ($\ge 1$), `WITHOUT_EMOJI` (0 emojis), `EMOJI_ONLY`, or specific emoji matching.
  * **Keyword Filtering**: Must-contain inclusion lists and negative spam/bot exclusion lists.
  * **Question Extraction**: Flag or extract only audience inquiries containing `?`.
  * **Engagement Thresholds**: Filter by minimum likes, upvotes, or comment scores.
* **Double-Pass Deduplication**: Automatic deduplication by unique Comment ID and exact comment text to eliminate spam copypastas.
* **Built-in NLP & Language Tagging**: Detects Latin scripts (English), Devanagari (Hindi), Romanized Hindi (Hinglish), Arabic, and CJK characters.
* **Multi-Format Export Suite**: Export clean datasets directly to:
  * 📊 **Excel (`.xlsx`)**: 4 auto-styled sheets with frozen headers and filters (`Comments`, `Summary`, `Emoji_Stats`, `Source_Breakdown`).
  * 📄 **CSV (`.csv`)**: Clean UTF-8 comma-separated table.
  * 📦 **JSON Lines (`.jsonl`)**: Line-delimited raw JSON records.
  * ⚡ **Parquet (`.parquet`)**: High-performance columnar storage.

---

## 📦 Project Architecture

```text
social-scraper-cli/
├── src/
│   ├── cli.py                     # Rich terminal CLI & Interactive Wizard
│   ├── core/
│   │   ├── detector.py            # Unicode emoji & structural text analyzer
│   │   ├── filter_engine.py       # Configurable multi-dimensional filter
│   │   ├── deduplicator.py        # 2-pass ID & exact text deduplicator
│   │   ├── language.py            # Script & vocabulary language classifier
│   │   ├── stats.py               # Dataset summary KPIs & emoji frequency ranker
│   │   └── exporter.py            # Excel, CSV, JSONL & Parquet exporters
│   └── scrapers/
│       ├── base.py                # Abstract scraper & unified schema
│       ├── youtube.py             # Channel & video comment scraper
│       ├── reddit.py              # Subreddit & post comment scraper
│       └── instagram.py           # Profile & post scraper with session auth
├── data/
│   ├── raw/                       # Staged raw payloads
│   ├── processed/                 # Processed clean datasets
│   └── exports/                   # Final Excel, CSV, and JSONL workbooks
├── tests/
│   └── test_cli_pipeline.py       # Pytest automated test suite
├── config.example.yaml            # Batch pipeline configuration template
├── requirements.txt               # Dependencies list
├── setup.py                       # Pip console script configuration
├── run.py                         # Root launcher script
├── run_cli.bat                    # Windows double-click shortcut
└── README.md                      # Project documentation
```

---

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/social-scraper-cli.git
cd social-scraper-cli
```

### 2. Create and Activate a Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

*(Optional)* Install locally as a system command:
```bash
pip install -e .
social-scraper --help
```

---

## 🎯 Quick Start & Usage

### 1. Interactive Terminal Wizard
Run the interactive wizard without needing to remember any CLI flags:
```bash
python run.py -i
```
Or double-click `run_cli.bat` on Windows.

---

### 2. Command-Line Flag Mode

#### Scrape YouTube:
```bash
# Scrape top 500 comments from YouTube channel @CarryMinati with emojis only:
python run.py -p youtube -t "@CarryMinati" -l 500 -e WITH_EMOJI -o xlsx,csv

# Scrape comments from a specific YouTube video:
python run.py -p youtube -t "https://www.youtube.com/watch?v=VIDEO_ID" -l 200 -o xlsx
```

#### Scrape Reddit:
> **Note**: Reddit requires API credentials for reliable access. Get free API keys at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (create a "script" type app).

```bash
# Scrape 300 comments from r/technology using API credentials:
python run.py -p reddit -t "r/technology" -l 300 --reddit-client-id "YOUR_ID" --reddit-client-secret "YOUR_SECRET" -o xlsx,jsonl

# Scrape multiple subreddits simultaneously:
python run.py -p reddit -t "r/india,r/pcmasterrace" -l 500 --reddit-client-id "YOUR_ID" --reddit-client-secret "YOUR_SECRET" -o csv,xlsx

# Or set environment variables and skip the flags:
# set REDDIT_CLIENT_ID=your_client_id
# set REDDIT_CLIENT_SECRET=your_client_secret
python run.py -p reddit -t "r/technology" -l 300 -o xlsx
```

#### Scrape Instagram:
```bash
# Scrape comments from an Instagram account with an authenticated session:
python run.py -p instagram -t "@cockroachjantaparty" -l 500 --session-id "YOUR_SESSION_ID" -o xlsx
```

---

### 3. Automated Configuration Mode (`config.yaml`)
You can configure multi-platform batch runs using a YAML configuration file:

```bash
python run.py -c config.example.yaml
```

**`config.yaml` Example:**
```yaml
platforms:
  - youtube
  - reddit

targets:
  youtube:
    - "@CarryMinati"
    - "@TechnoGamerzOfficial"
  reddit:
    - "r/technology"
    - "r/india"

limit: 1000

filter:
  emoji_mode: "WITH_EMOJI"        # ALL, WITH_EMOJI, WITHOUT_EMOJI, EMOJI_ONLY
  only_questions: false
  min_likes: 2
  keywords_exclude:
    - "dm to promote"
    - "free crypto"
    - "telegram"

export_formats:
  - xlsx
  - csv
  - jsonl

output_dir: "data/exports"
```

---

## 📊 Exported Excel Structure

Every generated `.xlsx` workbook includes 4 styled sheets:

| Sheet Name | Description |
| :--- | :--- |
| **`Comments`** | Complete table with ID, Platform, Source, Comment text, Emojis, Counts, Likes/Score, Author, Language, and Direct URLs. Includes auto-filters and frozen top row. |
| **`Summary`** | High-level KPIs: total scraped, comments with emojis, question counts, unique emojis, average emojis/comment. |
| **`Emoji_Stats`** | Frequency ranking of every unique Unicode emoji detected, with percentage of comments and total occurrence distributions. |
| **`Source_Breakdown`** | Aggregated performance metrics broken down by individual channel, subreddit, or account. |

---

## 🧪 Testing

Run the automated test suite with pytest:
```bash
pytest
```

---

## 🛡️ License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
