# NFL Quarterback Analysis: A Multi-Faceted Approach to Defining Elite Play

## Executive Summary

This project analyzes NFL play-by-play data from 2019-2023 to move beyond traditional metrics and build a multi-faceted definition of "elite" quarterback performance. The analysis integrates three distinct methodologies: situational performance (1st vs. 3rd Down), longitudinal trend analysis, and unsupervised machine learning. The capstone of the project is the deployment of a KMeans clustering model, which successfully segments players into three distinct archetypes and reveals that "elite" status is defined by a rare combination of both high accuracy and high downfield aggressiveness.

## 📊 View Interactive Analysis

[![nbviewer](https://raw.githubusercontent.com/jupyter/design/master/logos/Badges/nbviewer_badge.svg)](https://nbviewer.org/github/bruddaondabeat/NFL_QB_ANALYSIS/blob/main/nfl-qb-analysis.ipynb)

## Key Features
* **Deep Situational Analysis:** Goes beyond the box score to analyze performance on crucial downs.
* **Time-Series Visualization:** Tracks QB performance over a 5-year period against the league average.
* **Unsupervised Machine Learning:** Implements KMeans clustering to identify data-driven QB archetypes.
* **Interactive Data Visualization:** Uses Plotly to create an interactive bubble chart for exploring the QB archetypes.

## Tech Stack
* **Data Manipulation & Analysis:** Python, pandas, NumPy
* **Data Visualization:** Matplotlib, Seaborn, Plotly
* **Machine Learning:** Scikit-learn
* **Data Sourcing:** `nfl_data_py` Python library

## Data Source
All data for this project was sourced programmatically using the excellent [nfl_data_py](https://github.com/nflverse/nfl_data_py) library, which pulls data from the nflverse project. No local CSV files are needed to run this notebook.

## Installation & Usage
To run this project yourself, follow these steps:

1.  Clone the repository:
    ```bash
    git clone [https://github.com/bruddaondabeat/NFL_QB_ANALYSIS.git](https://github.com/bruddaondabeat/NFL_QB_ANALYSIS.git)
    ```
2.  Navigate to the project directory:
    ```bash
    cd NFL_QB_ANALYSIS
    ```
3.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Launch Jupyter Notebook and open the notebook file.
    ```bash
    jupyter notebook
    ```