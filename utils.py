import json

import pandas as pd


def load_hypotheses_outcomes(file_path) -> dict[str, pd.DataFrame]:
    """Load hypothesis outcome rows keyed by hypothesis ID."""

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    final_result = {}
    for data_item in data:
        for hypothesis_id, rows in data_item.items():
            final_result[hypothesis_id] = pd.DataFrame(rows)
    return final_result
