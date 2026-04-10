from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import nltk


COLUMN_ALIASES = {
    "age": [
        "Age / Edad",
        "age",
    ],
    "weight": [
        "Weight / Timbang (kg)  (must be a number)",
        "weight",
    ],
    "sex": [
        "Sex / Kasarian ",
        "sex",
    ],
    "medicine_checkbox": [
        "Which of the following medicine(s) is mentioned in your report? (Select all that apply.) No prescription details needed. / Alin sa mga sumusunod na (mga) gamot ang nabanggit sa iyong report? (Piliin lahat ng naaangkop.) Hindi kailangan ang detalye ng reseta.",
        "medicine_checkbox",
    ],
    "text_report": [
        "English: In your own words, tell us what you took, when you took it, and what you felt. Taglish is okay. Please avoid names, phone numbers, or exact addresses. \n\nTagalog: Sa sarili mong salita, ikuwento kung ano ang ininom o ginamit mo, kailan mo ito kinuha, at ano ang naramdaman mo. Puwede ang Taglish. Iwasan ang pangalan, numero ng telepono, o eksaktong address. \n\nExamples: “Uminom ako ng Diatabs kagabi, tapos nagsuka ako at fever.” / “Nag-Advil ako kaninang umaga, nahilo ako.” / “nag metformin ako last night and had stomach pain.”  ",
        "text_report",
    ],
    "post_action": [
        "What did you do after you experienced these symptoms? (Select all that apply.) / Ano ang ginawa mo pagkatapos mong maranasan ang mga sintomas? (Piliin lahat ng naaangkop.) ",
        "post_action",
    ],
    "dosage": [
        "Dosage / Dosis",
        "dosage",
    ],
    "route": [
        "Drug Admininistration / Ruta ng Administrasyon",
        "route",
    ],
    "reason": [
        "Reasons for Taking / Dahilan ng pag gagamot",
        "reason",
    ],
    "meals": [
        "Meals you took before taking the medicine / Mga huling kinain bago nag gamot",
        "meals",
    ],
    "activities": [
        "Recent activities before taking the medicine / Mga aktibidad bago uminom ng gamot   ",
        "activities",
    ],
    "other_medications": [
        "Other medications / Iba pang mga Gamot",
        "other_medications",
    ],
    "illnesses": [
        "Current and previous illnesses / \nKasalukuyan at dating mga sakit",
        "illnesses",
    ],
    "valid": [
        "Valid",
        "valid",
    ],
    "reporting_channel": [
        "reporting_channel",
    ],
}

TOKEN_PATTERN = re.compile(r"\w+(?:-\w+)*|[^\w\s]", flags=re.UNICODE)
MULTISPACE_PATTERN = re.compile(r"\s+")

SYMPTOM_CUES = [
    "nahilo",
    "hilo",
    "lightheaded",
    "dizzy",
    "dizziness",
    "rash",
    "rashes",
    "pantal",
    "itch",
    "itching",
    "kati",
    "nausea",
    "nasusuka",
    "nagsuka",
    "vomit",
    "vomiting",
    "sumakit",
    "sakit",
    "pain",
    "stomach pain",
    "headache",
    "hirap huminga",
    "nahihirapan huminga",
    "difficulty breathing",
    "throat tightness",
    "fever",
    "lagnat",
    "diarrhea",
    "pagtatae",
    "dry mouth",
]

ONSET_CUES = [
    "after",
    "pagkalipas",
    "kagabi",
    "kanina",
    "kahapon",
    "before breakfast",
    "before lunch",
    "before dinner",
    "bandang",
    "hours",
    "hour",
    "oras",
    "minutes",
    "minuto",
    "last night",
]

TAGALOG_CUES = {
    "ang", "ng", "sa", "si", "mga", "ako", "ikaw", "siya", "kami", "tayo", "nila",
    "namin", "amin", "ito", "iyan", "iyon", "lang", "din", "daw", "raw", "naman",
    "kasi", "kapag", "bago", "pagkatapos", "kahapon", "kanina", "kagabi", "umaga",
    "hapon", "gabi", "gamot", "uminom", "inom", "pakiramdam", "nahilo", "sumakit",
    "pantal", "kati", "ubo", "lagnat", "sakit", "tiyan", "sikmura", "huminga",
}

TAGALOG_PREFIXES = (
    "mag", "nag", "pag", "pang", "ipa", "pinag", "nakaka", "nakapag", "ma", "na"
)

ENGLISH_HINT_PREFIXES = ("anti", "post", "pre", "re")

FALLBACK_ENGLISH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "hers", "him", "his", "i", "in",
    "is", "it", "its", "me", "my", "of", "on", "or", "our", "ours", "she", "that",
    "the", "their", "them", "they", "this", "to", "was", "we", "were", "with", "you",
    "your", "yours",
}


def find_column(df: pd.DataFrame, aliases: List[str]) -> str | None:
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None


def read_csv_robust(csv_path: str | Path) -> pd.DataFrame:
    csv_path = Path(csv_path)

    encodings_to_try = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1",
    ]

    last_error = None
    for encoding in encodings_to_try:
        try:
            return pd.read_csv(csv_path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    try:
        return pd.read_csv(csv_path, encoding="latin1", engine="python")
    except Exception as exc:
        last_error = exc

    raise RuntimeError(
        f"Failed to read CSV file: {csv_path}. "
        f"Tried encodings: {', '.join(encodings_to_try)} and latin1 with python engine."
    ) from last_error


def load_dataset(csv_path: str | Path) -> pd.DataFrame:
    raw_df = read_csv_robust(csv_path)
    normalized = {}

    for internal_name, aliases in COLUMN_ALIASES.items():
        actual = find_column(raw_df, aliases)
        if actual is not None:
            normalized[internal_name] = raw_df[actual]
        else:
            normalized[internal_name] = pd.Series([np.nan] * len(raw_df), index=raw_df.index)

    df = pd.DataFrame(normalized)
    df.insert(0, "case_id", [f"case_{i + 1:05d}" for i in range(len(df))])
    df["reporting_channel"] = df["reporting_channel"].fillna("google_form")
    df["text_report"] = df["text_report"].fillna("").astype(str)
    return df


def save_dataframe(df: pd.DataFrame, output_path: str | Path) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")


def load_english_stopwords() -> set[str]:
    try:
        from nltk.corpus import stopwords
        return set(stopwords.words("english"))
    except LookupError:
        try:
            nltk.download("stopwords", quiet=True)
            from nltk.corpus import stopwords
            return set(stopwords.words("english"))
        except Exception:
            return set(FALLBACK_ENGLISH_STOPWORDS)
    except Exception:
        return set(FALLBACK_ENGLISH_STOPWORDS)


def load_tagalog_stopwords(path: str | Path) -> set[str]:
    stopword_path = Path(path)
    if not stopword_path.exists():
        return set()
    return {
        line.strip().lower()
        for line in stopword_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = MULTISPACE_PATTERN.sub(" ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    return [match.group(0) for match in TOKEN_PATTERN.finditer(text)]


def detect_language(token: str, english_stopwords: set[str], tagalog_stopwords: set[str]) -> str:
    text = token.lower()

    if re.fullmatch(r"[^\w]+", text):
        return "OTHER"
    if text in tagalog_stopwords or text in TAGALOG_CUES:
        return "TL"
    if text in english_stopwords:
        return "EN"
    if any(text.startswith(prefix) and len(text) > len(prefix) + 2 for prefix in TAGALOG_PREFIXES):
        return "TL"
    if any(text.startswith(prefix) and len(text) > len(prefix) + 2 for prefix in ENGLISH_HINT_PREFIXES):
        return "EN"
    if re.search(r"\d", text):
        return "OTHER"
    if re.search(r"[a-z]", text):
        return "EN"
    return "OTHER"


def split_multiselect(value: object) -> List[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def clean_frequency_label(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def compute_text_features(
    text: str,
    english_stopwords: set[str],
    tagalog_stopwords: set[str],
) -> Dict[str, float | int]:
    clean_text = normalize_text(text)
    tokens = tokenize(clean_text)
    word_tokens = [token for token in tokens if re.search(r"\w", token)]
    lowered_tokens = [token.lower() for token in word_tokens]

    language_labels = [detect_language(token, english_stopwords, tagalog_stopwords) for token in word_tokens]
    en_tokens = sum(label == "EN" for label in language_labels)
    tl_tokens = sum(label == "TL" for label in language_labels)
    other_tokens = sum(label == "OTHER" for label in language_labels)

    switch_points = 0
    previous = None
    for label in language_labels:
        if label not in {"EN", "TL"}:
            continue
        if previous is not None and label != previous:
            switch_points += 1
        previous = label

    text_lower = clean_text.lower()
    symptom_hits = sum(1 for cue in SYMPTOM_CUES if cue in text_lower)
    onset_hits = sum(1 for cue in ONSET_CUES if cue in text_lower)

    sentence_count = len([chunk for chunk in re.split(r"[.!?]+", clean_text) if chunk.strip()])
    word_count = len(word_tokens)
    unique_word_count = len(set(lowered_tokens))

    return {
        "char_count": len(clean_text),
        "word_count": word_count,
        "unique_word_count": unique_word_count,
        "sentence_count": sentence_count,
        "avg_word_length": float(np.mean([len(token) for token in word_tokens])) if word_tokens else 0.0,
        "en_tokens": en_tokens,
        "tl_tokens": tl_tokens,
        "other_tokens": other_tokens,
        "en_ratio": en_tokens / word_count if word_count else 0.0,
        "tl_ratio": tl_tokens / word_count if word_count else 0.0,
        "other_ratio": other_tokens / word_count if word_count else 0.0,
        "code_switch_points": switch_points,
        "code_switch_ratio": switch_points / max(word_count - 1, 1) if word_count else 0.0,
        "symptom_cue_hits": symptom_hits,
        "onset_cue_hits": onset_hits,
        "contains_numeric": int(bool(re.search(r"\d", clean_text))),
        "contains_time_expression": int(onset_hits > 0),
    }


def compute_text_feature_frame(
    reports: Iterable[str],
    english_stopwords: set[str],
    tagalog_stopwords: set[str],
) -> pd.DataFrame:
    rows = [compute_text_features(str(text), english_stopwords, tagalog_stopwords) for text in reports]
    return pd.DataFrame(rows)


def make_frequency_table(values: Iterable[str], column_name: str) -> pd.DataFrame:
    counter = Counter(clean_frequency_label(value) for value in values if str(value).strip())
    freq_df = pd.DataFrame(counter.items(), columns=[column_name, "count"])
    if freq_df.empty:
        return freq_df
    freq_df = freq_df.sort_values(["count", column_name], ascending=[False, True]).reset_index(drop=True)
    freq_df["percentage"] = (freq_df["count"] / freq_df["count"].sum()) * 100.0
    return freq_df


def make_token_frequency(
    reports: Iterable[str],
    english_stopwords: set[str],
    tagalog_stopwords: set[str],
) -> pd.DataFrame:
    stopwords = english_stopwords.union(tagalog_stopwords)
    counter: Counter[str] = Counter()

    for text in reports:
        normalized = normalize_text(str(text)).lower()
        for token in tokenize(normalized):
            if not re.fullmatch(r"\w+(?:-\w+)*", token):
                continue
            if len(token) <= 1:
                continue
            if token in stopwords:
                continue
            counter[token] += 1

    token_df = pd.DataFrame(counter.items(), columns=["token", "count"])
    if token_df.empty:
        return token_df
    token_df = token_df.sort_values(["count", "token"], ascending=[False, True]).reset_index(drop=True)
    token_df["percentage"] = (token_df["count"] / token_df["count"].sum()) * 100.0
    return token_df


def make_categorical_summary(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    rows = []
    for column in columns:
        if column not in df.columns:
            continue
        value_counts = df[column].fillna("<MISSING>").astype(str).value_counts(dropna=False)
        total = value_counts.sum()
        for value, count in value_counts.items():
            rows.append(
                {
                    "column": column,
                    "value": value,
                    "count": int(count),
                    "percentage": float((count / total) * 100.0) if total else 0.0,
                }
            )
    return pd.DataFrame(rows)


def save_dataframe(df: pd.DataFrame, output_path: str | Path) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)


def plot_bar_from_frame(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
    output_path: str | Path,
    top_n: int | None = None,
    rotation: int = 45,
) -> None:
    if df.empty or label_col not in df.columns or value_col not in df.columns:
        return

    plot_df = df.copy()
    if top_n is not None:
        plot_df = plot_df.head(top_n)

    plt.figure(figsize=(11, 6))
    plt.bar(plot_df[label_col].astype(str), plot_df[value_col].astype(float))
    plt.title(title)
    plt.xticks(rotation=rotation, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_series_bar(series: pd.Series, title: str, output_path: str | Path, rotation: int = 45) -> None:
    counts = series.fillna("<MISSING>").astype(str).value_counts()
    if counts.empty:
        return

    plt.figure(figsize=(10, 6))
    plt.bar(counts.index.astype(str), counts.values)
    plt.title(title)
    plt.xticks(rotation=rotation, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_hist(series: pd.Series, title: str, xlabel: str, output_path: str | Path, bins: int = 20) -> None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return

    plt.figure(figsize=(10, 6))
    plt.hist(clean, bins=bins)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_boxplot_by_group(
    df: pd.DataFrame,
    value_col: str,
    group_col: str,
    title: str,
    output_path: str | Path,
) -> None:
    if value_col not in df.columns or group_col not in df.columns:
        return

    working = df[[value_col, group_col]].copy()
    working[value_col] = pd.to_numeric(working[value_col], errors="coerce")
    working[group_col] = working[group_col].astype(str)
    working = working.dropna(subset=[value_col])

    if working.empty or working[group_col].nunique() < 2:
        return

    grouped = [group[value_col].to_numpy() for _, group in working.groupby(group_col)]
    labels = list(working.groupby(group_col).groups.keys())

    plt.figure(figsize=(11, 6))
    plt.boxplot(grouped, tick_labels=labels)
    plt.title(title)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_heatmap(crosstab_df: pd.DataFrame, title: str, output_path: str | Path) -> None:
    if crosstab_df.empty:
        return

    plt.figure(figsize=(10, 7))
    plt.imshow(crosstab_df.values, aspect="auto")
    plt.title(title)
    plt.xticks(range(len(crosstab_df.columns)), crosstab_df.columns.astype(str), rotation=45, ha="right")
    plt.yticks(range(len(crosstab_df.index)), crosstab_df.index.astype(str))

    for i in range(crosstab_df.shape[0]):
        for j in range(crosstab_df.shape[1]):
            plt.text(j, i, int(crosstab_df.iloc[i, j]), ha="center", va="center")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def build_markdown_report(
    overview: Dict[str, object],
    output_dir: str | Path,
    top_medicine: str,
    top_action: str,
    top_token: str,
) -> None:
    report_path = Path(output_dir) / "eda_report.md"
    lines = [
        "# Exploratory Data Analysis Report",
        "",
        "## Dataset Overview",
        f"- Total responses: {overview['n_rows']}",
        f"- Total columns after normalization: {overview['n_columns']}",
        f"- Valid responses: {overview['valid_count']} ({overview['valid_rate']:.2f}%)",
        f"- Missing text reports: {overview['missing_text_reports']}",
        f"- Median report word count: {overview['median_word_count']:.2f}",
        f"- Median code-switch ratio: {overview['median_code_switch_ratio']:.4f}",
        f"- Top medicine mention from checkboxes: {top_medicine or 'N/A'}",
        f"- Top post-action response: {top_action or 'N/A'}",
        f"- Top non-stopword token in narratives: {top_token or 'N/A'}",
        "",
        "## Saved Outputs",
        "- Tabular summaries are stored as CSV and JSON files in the EDA folder.",
        "- Visualization files are stored as PNG files in the EDA folder.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_eda(
    input_csv: str,
    output_dir: str = "EDA",
    tagalog_stopwords_path: str = "tagalog_stop_words.txt",
    top_n: int = 20,
) -> None:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(input_csv)
    english_stopwords = load_english_stopwords()
    tagalog_stopwords = load_tagalog_stopwords(tagalog_stopwords_path)

    text_features = compute_text_feature_frame(df["text_report"], english_stopwords, tagalog_stopwords)
    analysis_df = pd.concat([df, text_features], axis=1)

    if "weight" in analysis_df.columns:
        analysis_df["weight_numeric"] = pd.to_numeric(analysis_df["weight"], errors="coerce")
    if "valid" in analysis_df.columns:
        analysis_df["valid_numeric"] = pd.to_numeric(analysis_df["valid"], errors="coerce")

    missing_summary = pd.DataFrame(
        {
            "column": analysis_df.columns,
            "missing_count": [int(analysis_df[column].isna().sum()) for column in analysis_df.columns],
            "missing_percentage": [float(analysis_df[column].isna().mean() * 100.0) for column in analysis_df.columns],
        }
    ).sort_values(["missing_count", "column"], ascending=[False, True])
    save_dataframe(missing_summary, out_dir / "missing_values.csv")

    text_features_export = analysis_df[
        [
            "case_id",
            "char_count",
            "word_count",
            "unique_word_count",
            "sentence_count",
            "avg_word_length",
            "en_tokens",
            "tl_tokens",
            "other_tokens",
            "en_ratio",
            "tl_ratio",
            "other_ratio",
            "code_switch_points",
            "code_switch_ratio",
            "symptom_cue_hits",
            "onset_cue_hits",
            "contains_numeric",
            "contains_time_expression",
        ]
    ]
    save_dataframe(text_features_export, out_dir / "text_features.csv")

    numeric_cols = analysis_df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        numeric_summary = analysis_df[numeric_cols].describe().T.reset_index().rename(columns={"index": "feature"})
        save_dataframe(numeric_summary, out_dir / "numeric_summary.csv")

        correlation = analysis_df[numeric_cols].corr(numeric_only=True).reset_index().rename(columns={"index": "feature"})
        save_dataframe(correlation, out_dir / "numeric_correlation.csv")

    categorical_columns = [
        "age",
        "sex",
        "route",
        "valid",
        "reporting_channel",
        "reason",
    ]
    categorical_summary = make_categorical_summary(analysis_df, categorical_columns)
    save_dataframe(categorical_summary, out_dir / "categorical_summary.csv")

    medicine_values = []
    for value in analysis_df["medicine_checkbox"]:
        medicine_values.extend(split_multiselect(value))
    medicine_freq = make_frequency_table(medicine_values, "medicine")
    save_dataframe(medicine_freq, out_dir / "medicine_frequency.csv")

    action_values = []
    for value in analysis_df["post_action"]:
        action_values.extend(split_multiselect(value))
    action_freq = make_frequency_table(action_values, "post_action")
    save_dataframe(action_freq, out_dir / "post_action_frequency.csv")

    token_freq = make_token_frequency(analysis_df["text_report"], english_stopwords, tagalog_stopwords)
    save_dataframe(token_freq.head(100), out_dir / "top_tokens.csv")

    symptom_counter = Counter()
    onset_counter = Counter()
    for text in analysis_df["text_report"].astype(str):
        lowered = normalize_text(text).lower()
        for cue in SYMPTOM_CUES:
            if cue in lowered:
                symptom_counter[cue] += 1
        for cue in ONSET_CUES:
            if cue in lowered:
                onset_counter[cue] += 1

    symptom_freq = make_frequency_table(symptom_counter.elements(), "symptom_cue")
    onset_freq = make_frequency_table(onset_counter.elements(), "onset_cue")
    save_dataframe(symptom_freq, out_dir / "symptom_cue_frequency.csv")
    save_dataframe(onset_freq, out_dir / "onset_cue_frequency.csv")

    overview = {
        "n_rows": int(len(analysis_df)),
        "n_columns": int(len(analysis_df.columns)),
        "valid_count": int(pd.to_numeric(analysis_df.get("valid"), errors="coerce").fillna(0).sum()) if "valid" in analysis_df.columns else 0,
        "valid_rate": float(pd.to_numeric(analysis_df.get("valid"), errors="coerce").fillna(0).mean() * 100.0) if "valid" in analysis_df.columns else 0.0,
        "missing_text_reports": int((analysis_df["text_report"].astype(str).str.strip() == "").sum()),
        "median_word_count": float(analysis_df["word_count"].median()) if "word_count" in analysis_df.columns else 0.0,
        "median_code_switch_ratio": float(analysis_df["code_switch_ratio"].median()) if "code_switch_ratio" in analysis_df.columns else 0.0,
    }
    (out_dir / "eda_summary.json").write_text(json.dumps(overview, indent=2), encoding="utf-8")

    plot_bar_from_frame(
        missing_summary.head(top_n),
        "column",
        "missing_count",
        "Missing Values by Column",
        out_dir / "missing_values_bar.png",
        rotation=60,
    )
    plot_series_bar(analysis_df["age"], "Age Distribution", out_dir / "age_distribution.png")
    plot_series_bar(analysis_df["sex"], "Sex Distribution", out_dir / "sex_distribution.png")
    plot_series_bar(analysis_df["route"], "Route of Administration Distribution", out_dir / "route_distribution.png")
    plot_series_bar(analysis_df["valid"], "Valid Flag Distribution", out_dir / "valid_distribution.png")

    plot_hist(analysis_df["weight"], "Weight Distribution", "Weight (kg)", out_dir / "weight_distribution.png")
    plot_hist(analysis_df["word_count"], "Report Word Count Distribution", "Word Count", out_dir / "report_word_count_hist.png")
    plot_hist(analysis_df["char_count"], "Report Character Count Distribution", "Character Count", out_dir / "report_char_count_hist.png")
    plot_hist(analysis_df["code_switch_ratio"], "Code-Switch Ratio Distribution", "Code-Switch Ratio", out_dir / "code_switch_ratio_hist.png")

    plot_boxplot_by_group(
        analysis_df,
        "word_count",
        "valid",
        "Report Word Count by Valid Flag",
        out_dir / "report_word_count_by_valid.png",
    )
    plot_boxplot_by_group(
        analysis_df,
        "weight",
        "sex",
        "Weight by Sex",
        out_dir / "weight_by_sex.png",
    )

    plot_bar_from_frame(
        medicine_freq,
        "medicine",
        "count",
        "Top Medicines Mentioned",
        out_dir / "top_medicines.png",
        top_n=top_n,
        rotation=70,
    )
    plot_bar_from_frame(
        action_freq,
        "post_action",
        "count",
        "Top Post-Action Responses",
        out_dir / "top_post_actions.png",
        top_n=top_n,
        rotation=70,
    )
    plot_bar_from_frame(
        symptom_freq,
        "symptom_cue",
        "count",
        "Top Symptom Cues in Narratives",
        out_dir / "top_symptom_cues.png",
        top_n=top_n,
        rotation=45,
    )
    plot_bar_from_frame(
        onset_freq,
        "onset_cue",
        "count",
        "Top Onset Cues in Narratives",
        out_dir / "top_onset_cues.png",
        top_n=top_n,
        rotation=45,
    )
    plot_bar_from_frame(
        token_freq,
        "token",
        "count",
        "Top Narrative Tokens",
        out_dir / "top_tokens.png",
        top_n=top_n,
        rotation=60,
    )

    if {"age", "sex"}.issubset(analysis_df.columns):
        age_sex = pd.crosstab(analysis_df["age"].fillna("<MISSING>"), analysis_df["sex"].fillna("<MISSING>"))
        save_dataframe(age_sex.reset_index(), out_dir / "age_by_sex_crosstab.csv")
        plot_heatmap(age_sex, "Age by Sex Crosstab", out_dir / "age_by_sex_heatmap.png")

    if {"age", "valid"}.issubset(analysis_df.columns):
        age_valid = pd.crosstab(analysis_df["age"].fillna("<MISSING>"), analysis_df["valid"].fillna("<MISSING>"))
        save_dataframe(age_valid.reset_index(), out_dir / "age_by_valid_crosstab.csv")
        plot_heatmap(age_valid, "Age by Valid Flag Crosstab", out_dir / "age_by_valid_heatmap.png")

    top_medicine = medicine_freq.iloc[0]["medicine"] if not medicine_freq.empty else ""
    top_action = action_freq.iloc[0]["post_action"] if not action_freq.empty else ""
    top_token = token_freq.iloc[0]["token"] if not token_freq.empty else ""
    build_markdown_report(overview, out_dir, top_medicine, top_action, top_token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone EDA generator for the ADR survey dataset.")
    parser.add_argument("--input-csv", required=True, help="Path to the source survey CSV file.")
    parser.add_argument("--output-dir", default="EDA", help="Directory where EDA outputs will be saved.")
    parser.add_argument(
        "--tagalog-stopwords",
        default="tagalog_stop_words.txt",
        help="Path to the curated Tagalog stopword list.",
    )
    parser.add_argument("--top-n", type=int, default=20, help="Number of top items to include in frequency plots.")
    args = parser.parse_args()

    run_eda(
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        tagalog_stopwords_path=args.tagalog_stopwords,
        top_n=args.top_n,
    )


if __name__ == "__main__":
    main()

# python eda.py --input-csv "Community Medicine Experience Survey _ Ulat sa Epekto ng Gamot (Responses) - Form Responses 1.csv" --output-dir EDA --tagalog-stopwords tagalog_stop_words.txt
