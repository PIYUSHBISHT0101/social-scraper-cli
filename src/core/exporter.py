"""Multi-format dataset exporter (Excel .xlsx, CSV, JSONL, Parquet)."""
import os
import json
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)


class DatasetExporter:
    """Exports processed social media datasets to Excel, CSV, JSONL, and Parquet."""

    def __init__(self, output_dir: str = "data/exports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def export_all(
        self,
        comments: List[Dict[str, Any]],
        summary_stats: Optional[Dict[str, Any]] = None,
        emoji_stats: Optional[List[Dict[str, Any]]] = None,
        source_stats: Optional[List[Dict[str, Any]]] = None,
        formats: Optional[List[str]] = None,
        base_filename: str = "social_media_comments",
    ) -> Dict[str, str]:
        """Export dataset to requested formats.
        
        Args:
            comments: List of comment dictionaries.
            summary_stats: Overall dataset summary KPIs.
            emoji_stats: Frequency table of emojis.
            source_stats: Breakdown by channel/subreddit/account.
            formats: List of formats ('xlsx', 'csv', 'jsonl', 'parquet').
            base_filename: Prefix for output files.
            
        Returns:
            Dict mapping format to generated file path.
        """
        formats = [f.lower().strip() for f in (formats or ["xlsx", "csv", "jsonl"])]
        generated_files = {}

        if not comments:
            logger.warning("No comments provided for export.")
            return generated_files

        # Ensure directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        if "xlsx" in formats:
            xlsx_path = os.path.join(self.output_dir, f"{base_filename}.xlsx")
            self.export_excel(comments, summary_stats, emoji_stats, source_stats, xlsx_path)
            generated_files["xlsx"] = xlsx_path

        if "csv" in formats:
            csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")
            self.export_csv(comments, csv_path)
            generated_files["csv"] = csv_path

        if "jsonl" in formats:
            jsonl_path = os.path.join(self.output_dir, f"{base_filename}.jsonl")
            self.export_jsonl(comments, jsonl_path)
            generated_files["jsonl"] = jsonl_path

        if "parquet" in formats:
            parquet_path = os.path.join(self.output_dir, f"{base_filename}.parquet")
            self.export_parquet(comments, parquet_path)
            generated_files["parquet"] = parquet_path

        return generated_files

    def export_excel(
        self,
        comments: List[Dict[str, Any]],
        summary_stats: Optional[Dict[str, Any]] = None,
        emoji_stats: Optional[List[Dict[str, Any]]] = None,
        source_stats: Optional[List[Dict[str, Any]]] = None,
        output_path: str = "data/exports/social_comments.xlsx",
    ) -> str:
        """Create a professional multi-sheet Excel workbook with styled headers and auto-filters."""
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default sheet

        # Styles
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )

        # 1. Main Comments Sheet
        ws_data = wb.create_sheet(title="Comments")
        columns = [
            ("id", "ID", 10),
            ("platform", "Platform", 14),
            ("source_name", "Source / Channel", 24),
            ("comment", "Comment Text", 60),
            ("emoji_list", "Emojis", 24),
            ("emoji_count", "Emoji Count", 14),
            ("emoji_unique_count", "Unique Emojis", 14),
            ("emoji_only", "Emoji Only", 14),
            ("is_question", "Is Question", 14),
            ("char_count", "Char Count", 12),
            ("word_count", "Word Count", 12),
            ("like_count", "Likes / Score", 14),
            ("author", "Author", 20),
            ("language", "Language", 12),
            ("created_at", "Date Posted", 22),
            ("collected_at", "Date Collected", 22),
            ("source_url", "Comment URL", 45),
        ]

        # Write Headers
        for col_idx, (_, col_title, width) in enumerate(columns, 1):
            cell = ws_data.cell(row=1, column=col_idx, value=col_title)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False)
            ws_data.column_dimensions[get_column_letter(col_idx)].width = width

        ws_data.row_dimensions[1].height = 26

        # Write Rows
        for row_idx, c in enumerate(comments, 2):
            for col_idx, (col_key, _, _) in enumerate(columns, 1):
                val = c.get(col_key, "")
                if col_key == "id" and not val:
                    val = row_idx - 1
                elif col_key == "emoji_list" and isinstance(val, list):
                    val = " ".join(val)
                elif isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)

                cell = ws_data.cell(row=row_idx, column=col_idx, value=val)
                cell.border = thin_border
                cell.font = Font(name="Calibri", size=10)
                if col_key == "comment":
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                elif col_key in ["emoji_count", "like_count", "char_count", "word_count", "id"]:
                    cell.alignment = Alignment(horizontal="right", vertical="top")
                else:
                    cell.alignment = Alignment(vertical="top")

        ws_data.freeze_panes = "A2"
        ws_data.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(comments) + 1}"

        # 2. Summary Sheet
        if summary_stats:
            ws_summary = wb.create_sheet(title="Summary")
            ws_summary.column_dimensions["A"].width = 35
            ws_summary.column_dimensions["B"].width = 30
            ws_summary.append(["Metric", "Value"])
            ws_summary.cell(1, 1).fill = header_fill
            ws_summary.cell(1, 1).font = header_font
            ws_summary.cell(1, 2).fill = header_fill
            ws_summary.cell(1, 2).font = header_font
            ws_summary.row_dimensions[1].height = 24

            for k, v in summary_stats.items():
                k_clean = k.replace("_", " ").title()
                ws_summary.append([k_clean, str(v)])
            ws_summary.freeze_panes = "A2"

        # 3. Emoji Stats Sheet
        if emoji_stats:
            ws_emoji = wb.create_sheet(title="Emoji_Stats")
            ws_emoji.append(["Rank", "Emoji", "Frequency", "% of Comments", "% of Occurrences"])
            for c_idx in range(1, 6):
                c_cell = ws_emoji.cell(1, c_idx)
                c_cell.fill = header_fill
                c_cell.font = header_font
            ws_emoji.column_dimensions["A"].width = 10
            ws_emoji.column_dimensions["B"].width = 15
            ws_emoji.column_dimensions["C"].width = 18
            ws_emoji.column_dimensions["D"].width = 22
            ws_emoji.column_dimensions["E"].width = 22

            for rank, item in enumerate(emoji_stats, 1):
                ws_emoji.append([
                    rank,
                    item.get("emoji", ""),
                    item.get("frequency", 0),
                    item.get("percentage_of_comments", ""),
                    item.get("percentage_of_all_occurrences", ""),
                ])
            ws_emoji.freeze_panes = "A2"
            ws_emoji.auto_filter.ref = f"A1:E{len(emoji_stats) + 1}"

        # 4. Source Breakdown Sheet
        if source_stats:
            ws_source = wb.create_sheet(title="Source_Breakdown")
            headers = ["Source / Target", "Platform", "Total Comments", "Emoji Comments", "Questions", "Avg Emojis/Comment"]
            ws_source.append(headers)
            for c_idx in range(1, len(headers) + 1):
                c_cell = ws_source.cell(1, c_idx)
                c_cell.fill = header_fill
                c_cell.font = header_font
            ws_source.column_dimensions["A"].width = 30
            ws_source.column_dimensions["B"].width = 16
            ws_source.column_dimensions["C"].width = 18
            ws_source.column_dimensions["D"].width = 18
            ws_source.column_dimensions["E"].width = 16
            ws_source.column_dimensions["F"].width = 20

            for s in source_stats:
                ws_source.append([
                    s.get("source", ""),
                    s.get("platform", ""),
                    s.get("total_comments", 0),
                    s.get("emoji_comments", 0),
                    s.get("questions", 0),
                    s.get("avg_emojis", 0.0),
                ])
            ws_source.freeze_panes = "A2"
            ws_source.auto_filter.ref = f"A1:F{len(source_stats) + 1}"

        wb.save(output_path)
        logger.info(f"Successfully exported Excel workbook: {output_path}")
        return output_path

    def export_csv(self, comments: List[Dict[str, Any]], output_path: str) -> str:
        """Export comments to UTF-8 CSV."""
        df = pd.DataFrame(comments)
        for col in ["emoji_list", "hashtags"]:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: " ".join(x) if isinstance(x, list) else ("" if x is None or (isinstance(x, float) and pd.isna(x)) else str(x))
                )
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"Exported CSV: {output_path}")
        return output_path

    def export_jsonl(self, comments: List[Dict[str, Any]], output_path: str) -> str:
        """Export comments to line-delimited JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            for c in comments:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        logger.info(f"Exported JSONL: {output_path}")
        return output_path

    def export_parquet(self, comments: List[Dict[str, Any]], output_path: str) -> str:
        """Export comments to high-performance Parquet format."""
        try:
            df = pd.DataFrame(comments)
            # Flatten lists/dicts for parquet compatibility if needed
            for col in ["emoji_list", "hashtags"]:
                if col in df.columns:
                    df[col] = df[col].apply(
                        lambda x: " ".join(x) if isinstance(x, list) else ("" if x is None or (isinstance(x, float) and pd.isna(x)) else str(x))
                    )
            df.to_parquet(output_path, index=False)
            logger.info(f"Exported Parquet: {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"Could not export Parquet: {e}")
            return ""
