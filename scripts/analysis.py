# This Python script fetches energy and economic data for a selection of
# countries from the World Bank API, cleans and combines the data
# into a tidy format, computes a few derived metrics, and produces
# several visualisations.  The resulting processed dataset and plots
# can be used both in R (see `analysis.R`) and in Power BI.  The script
# is written to be self‑contained; running it will recreate the
# `data/processed_data.csv` and all figures in the `figures` folder.

import os
import json
from functools import reduce
from typing import List

import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
from sklearn.cluster import KMeans
from statsmodels.tsa.arima.model import ARIMA


def fetch_indicator(indicator: str) -> pd.DataFrame:
    """Fetch an indicator from the World Bank API for all countries.

    Parameters
    ----------
    indicator: str
        The World Bank indicator code (e.g. 'EG.FEC.RNEW.ZS').

    Returns
    -------
    pd.DataFrame
        A tidy DataFrame with columns country_code, country, year and the
        indicator value.  Years are integers.
    """
    url = (
        f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
        f"?format=json&per_page=20000"
    )
    response = requests.get(url)
    response.raise_for_status()
    json_data = response.json()
    # The second element in the returned JSON is the list of observations
    records = json_data[1]
    rows = []
    for rec in records:
        rows.append(
            {
                "country_code": rec["countryiso3code"],
                "country": rec["country"]["value"],
                "year": int(rec["date"]),
                indicator: rec["value"],
            }
        )
    return pd.DataFrame(rows)


def build_dataset(countries: List[str]) -> pd.DataFrame:
    """Download and merge the chosen indicators into a single DataFrame.

    The indicators used here capture renewable energy share, energy use
    intensity, population and GDP per capita.

    Parameters
    ----------
    countries: list of str
        ISO 3166‑1 alpha‑3 country codes to include.

    Returns
    -------
    pd.DataFrame
        A tidy DataFrame with one row per country per year and columns
        for each indicator and derived metrics.
    """
    indicators = [
        "EG.FEC.RNEW.ZS",  # Renewable energy consumption (% of total final energy consumption)
        "EG.USE.PCAP.KG.OE",  # Energy use (kg of oil equivalent per capita)
        "SP.POP.TOTL",  # Population, total
        "NY.GDP.PCAP.KD",  # GDP per capita (constant 2015 US$)
    ]

    # Fetch each indicator and merge them on country_code, country and year
    frames = [fetch_indicator(code) for code in indicators]
    merged = reduce(
        lambda left, right: pd.merge(
            left, right, on=["country_code", "country", "year"], how="outer"
        ),
        frames,
    )

    # Only consider years from 1990 onward and restrict to three‑letter country codes
    merged = merged[(merged["year"] >= 1990) & (merged["country_code"].str.len() == 3)]
    # Filter to selected countries
    merged = merged[merged["country_code"].isin(countries)]

    # Drop rows without values for renewable share or energy use
    merged = merged.dropna(subset=["EG.FEC.RNEW.ZS", "EG.USE.PCAP.KG.OE"])

    # Rename columns to more friendly names
    merged = merged.rename(
        columns={
            "EG.FEC.RNEW.ZS": "renewable_share",
            "EG.USE.PCAP.KG.OE": "energy_use_per_capita",
            "SP.POP.TOTL": "population",
            "NY.GDP.PCAP.KD": "gdp_per_capita",
        }
    )

    # Compute derived metrics
    merged["total_energy_use"] = merged["energy_use_per_capita"] * merged["population"]
    merged["energy_intensity"] = merged["energy_use_per_capita"] / merged["gdp_per_capita"]
    return merged


def plot_line_trends(df: pd.DataFrame, value_col: str, title: str, ylabel: str, output_path: str) -> None:
    """Plot a line chart for each country showing the trend of a given variable."""
    plt.figure(figsize=(12, 7))
    for country_code, group in df.groupby("country_code"):
        plt.plot(group["year"], group[value_col], label=country_code)
    plt.title(title)
    plt.xlabel("Year")
    plt.ylabel(ylabel)
    plt.legend(title="Country", fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_scatter_clusters(
    df: pd.DataFrame, x_col: str, y_col: str, n_clusters: int, output_path: str
) -> None:
    """Perform k‑means clustering on two variables and plot the results."""
    # Drop rows with NaNs
    data = df[[x_col, y_col]].dropna()
    # Normalise variables to improve clustering
    x_norm = (data[x_col] - data[x_col].mean()) / data[x_col].std()
    y_norm = (data[y_col] - data[y_col].mean()) / data[y_col].std()
    X = pd.concat([x_norm, y_norm], axis=1).values
    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
    clusters = kmeans.fit_predict(X)

    plt.figure(figsize=(8, 6))
    palette = sns.color_palette("Set2", n_clusters)
    for i in range(n_clusters):
        cluster_points = data[clusters == i]
        plt.scatter(
            cluster_points[x_col],
            cluster_points[y_col],
            s=60,
            color=palette[i],
            label=f"Cluster {i+1}",
            edgecolor="k",
            alpha=0.8,
        )
    plt.title(
        f"K‑means clustering ({n_clusters} clusters) on {y_col} vs. {x_col} (latest year)"
    )
    plt.xlabel(x_col.replace("_", " ").title())
    plt.ylabel(y_col.replace("_", " ").title())
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_scatter(df: pd.DataFrame, x_col: str, y_col: str, output_path: str) -> None:
    """Generate a scatter plot for two variables across countries for the latest year."""
    plt.figure(figsize=(8, 6))
    sns.scatterplot(data=df, x=x_col, y=y_col, hue="country_code", s=80, palette="tab10")
    for _, row in df.iterrows():
        plt.text(row[x_col], row[y_col], row["country_code"], fontsize=8, ha="right")
    plt.title(
        f"{y_col.replace('_',' ').title()} vs. {x_col.replace('_',' ').title()} (latest year)"
    )
    plt.xlabel(x_col.replace("_", " ").title())
    plt.ylabel(y_col.replace("_", " ").title())
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left", borderaxespad=0.)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def forecast_renewable_share(
    df: pd.DataFrame, country_code: str, steps: int, output_path: str
) -> None:
    """Fit an ARIMA model to renewable energy share and forecast future values."""
    series = (
        df[df["country_code"] == country_code]
        .sort_values("year")
        .set_index("year")["renewable_share"]
        .dropna()
    )
    model = ARIMA(series, order=(1, 1, 1))
    model_fit = model.fit()
    forecast = model_fit.forecast(steps=steps)
    forecast_index = range(series.index.max() + 1, series.index.max() + 1 + steps)

    plt.figure(figsize=(10, 6))
    plt.plot(series.index, series.values, label="Historical")
    plt.plot(forecast_index, forecast.values, label="Forecast", linestyle="--")
    plt.title(
        f"Forecast of Renewable Energy Share for {country_code} ({steps} years ahead)"
    )
    plt.xlabel("Year")
    plt.ylabel("Renewable Share (% of final energy consumption)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def main():
    # Define the countries to analyse.  These include major economies and
    # large energy consumers across different regions.
    countries = [
        "USA",  # United States
        "CHN",  # China
        "IND",  # India
        "JPN",  # Japan
        "RUS",  # Russian Federation
        "DEU",  # Germany
        "GBR",  # United Kingdom
        "FRA",  # France
        "BRA",  # Brazil
        "CAN",  # Canada
        "AUS",  # Australia
        "ZAF",  # South Africa
        "MEX",  # Mexico
        "SAU",  # Saudi Arabia
        "IDN",  # Indonesia
        "KOR",  # Korea, Rep.
        "ITA",  # Italy
        "ESP",  # Spain
        "TUR",  # Turkey
    ]

    # Directory paths relative to this file
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(root_dir, "data")
    fig_dir = os.path.join(root_dir, "figures")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(fig_dir, exist_ok=True)

    # Build dataset and save to CSV
    dataset = build_dataset(countries)
    csv_path = os.path.join(data_dir, "processed_data.csv")
    dataset.to_csv(csv_path, index=False)

    # Plot trends
    plot_line_trends(
        dataset,
        value_col="renewable_share",
        title="Renewable energy share over time",
        ylabel="Renewable share (% of final energy consumption)",
        output_path=os.path.join(fig_dir, "renewable_share_trends.png"),
    )
    plot_line_trends(
        dataset,
        value_col="energy_use_per_capita",
        title="Energy use per capita over time",
        ylabel="Energy use per capita (kg of oil equivalent)",
        output_path=os.path.join(fig_dir, "energy_use_per_capita_trends.png"),
    )

    # Latest year data
    latest_year = dataset["year"].max()
    latest_data = dataset[dataset["year"] == latest_year]
    plot_scatter(
        latest_data,
        x_col="energy_use_per_capita",
        y_col="renewable_share",
        output_path=os.path.join(fig_dir, "renewable_vs_energyuse_scatter.png"),
    )
    plot_scatter_clusters(
        latest_data,
        x_col="energy_use_per_capita",
        y_col="renewable_share",
        n_clusters=3,
        output_path=os.path.join(fig_dir, "kmeans_clusters.png"),
    )
    forecast_renewable_share(
        dataset,
        country_code="USA",
        steps=10,
        output_path=os.path.join(fig_dir, "usa_renewable_share_forecast.png"),
    )


if __name__ == "__main__":
    main()
