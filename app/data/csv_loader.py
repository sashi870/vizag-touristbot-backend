from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import pandas as pd


APP_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = APP_DIR / "datasets"


def load_csv(filename: str) -> pd.DataFrame:
    """Load a dataset CSV with UTF-8 first and Latin-1 as a fallback."""
    path = DATASETS_DIR / filename

    if not path.exists():
        print(f"File not found: app/datasets/{filename}")
        return pd.DataFrame()

    try:
        dataframe = pd.read_csv(
            path,
            encoding="utf-8-sig",
            engine="python",
            on_bad_lines="skip",
        )
    except Exception:
        try:
            dataframe = pd.read_csv(
                path,
                encoding="latin1",
                engine="python",
                on_bad_lines="skip",
            )
        except Exception as exc:
            print(f"CSV Error in {filename}: {exc}")
            return pd.DataFrame()

    dataframe.columns = [
        str(column).strip().replace("\ufeff", "")
        for column in dataframe.columns
    ]
    return dataframe


def load_first_existing_csv(filenames: Iterable[str]) -> pd.DataFrame:
    """Load the first available filename from app/datasets."""
    candidate_names = list(filenames)

    for filename in candidate_names:
        if (DATASETS_DIR / filename).exists():
            return load_csv(filename)

    print(f"Missing speciality file. Tried: {', '.join(candidate_names)}")
    return pd.DataFrame()


def _clean_column_name(value: object) -> str:
    return (
        str(value)
        .strip()
        .replace("\ufeff", "")
        .replace("ï»¿", "")
        .strip()
        .strip('"')
    )


def _parse_wrapped_csv_rows(
    values: Iterable[object],
    headers: list[str],
) -> pd.DataFrame:
    fixed_rows: list[list[str]] = []

    for raw_value in values:
        value = str(raw_value).strip()

        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        value = value.replace('""', '"')
        row = next(csv.reader([value]))

        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        elif len(row) > len(headers):
            row = row[: len(headers)]

        fixed_rows.append(row)

    dataframe = pd.DataFrame(fixed_rows, columns=headers)
    dataframe.columns = [
        _clean_column_name(column)
        for column in dataframe.columns
    ]
    return dataframe


def fix_single_column_csv_df(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Repair CSV data where complete rows were loaded into one column."""
    if dataframe is None or dataframe.empty:
        return dataframe

    dataframe = dataframe.copy()
    dataframe.columns = [
        _clean_column_name(column)
        for column in dataframe.columns
    ]

    if len(dataframe.columns) > 1:
        try:
            first_column = dataframe.columns[0]
            other_columns = dataframe.columns[1:]

            other_empty_ratio = dataframe[other_columns].isna().mean().mean()
            first_has_csv_rows = (
                dataframe[first_column]
                .astype(str)
                .str.contains(",", regex=False)
                .mean()
            )

            if other_empty_ratio > 0.80 and first_has_csv_rows > 0.50:
                headers = [
                    _clean_column_name(column)
                    for column in dataframe.columns
                ]
                return _parse_wrapped_csv_rows(
                    dataframe[first_column].dropna().tolist(),
                    headers,
                )

        except Exception as exc:
            print(f"CSV MULTI-COLUMN FIX ERROR: {exc}")

    if len(dataframe.columns) != 1:
        return dataframe

    first_column = dataframe.columns[0]

    if "," not in first_column:
        return dataframe

    try:
        headers = next(csv.reader([_clean_column_name(first_column)]))
        return _parse_wrapped_csv_rows(
            dataframe[first_column].dropna().tolist(),
            headers,
        )
    except Exception as exc:
        print(f"CSV FIX ERROR: {exc}")
        return dataframe


def safe_get(row, keys: Iterable[str], default: str = "") -> str:
    """Return the first non-empty, non-NaN value from the requested columns."""
    for key in keys:
        if key in row and pd.notna(row[key]):
            value = str(row[key]).strip()
            if value and value.lower() != "nan":
                return value

    return default