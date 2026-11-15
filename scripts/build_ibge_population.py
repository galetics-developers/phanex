"""Download IBGE 2018 population estimates (SIDRA table 6579) for the 27 UFs.

Source: IBGE, SIDRA table 6579, variable 9324 (Populacao residente estimada),
reference date 2018-07-01.
Output: data/raw/external/ibge_population_2018.csv (uf,state_name,population_2018)
"""

import json
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://apisidra.ibge.gov.br/values/t/6579/n3/all/v/9324/p/2018"
OUTPUT = Path("data/raw/external/ibge_population_2018.csv")

UF_CODE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}


def main() -> None:
    request = urllib.request.Request(URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        rows = json.loads(response.read().decode("utf-8"))

    raw = pd.DataFrame(rows[1:])  # the first row holds the column labels
    df = pd.DataFrame(
        {
            "uf": raw["D1C"].map(UF_CODE),
            "state_name": raw["D1N"],
            "population_2018": raw["V"].astype(int),
        }
    ).sort_values("uf")

    assert len(df) == 27, f"Expected 27 UF, got {len(df)}"
    assert df["uf"].notna().all(), "Unknown UF code in source"
    assert df["uf"].is_unique, "Duplicated UF"
    assert (df["population_2018"] > 0).all(), "Population must be > 0"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False, encoding="utf-8")
    total = df["population_2018"].sum()
    print(f"OK: {len(df)} UF, total {total:,} -> {OUTPUT}")


if __name__ == "__main__":
    main()
