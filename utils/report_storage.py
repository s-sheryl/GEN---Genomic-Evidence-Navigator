"""
report_storage.py

Handles saving and loading Genome Variant Interpretation reports as JSON
files. Reports are stored in the local "reports" directory using a unique
UUID-based filename.

Functions
---------
save_report(data)
    Saves a report dictionary as a JSON file and returns its unique report ID.

load_report(report_id)
    Loads a previously saved report using its unique report ID.
"""

import json
import os
import uuid

REPORT_FOLDER = "reports"


def save_report(data):
    """
    Saves a report as a JSON file.

    Parameters
    ----------
    data : dict
        Report data to save.

    Returns
    -------
    str or None
        The generated report ID if successful, otherwise None.
    """

    os.makedirs(REPORT_FOLDER, exist_ok=True)

    report_id = str(uuid.uuid4())
    filename = os.path.join(REPORT_FOLDER, f"{report_id}.json")

    try:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

        return report_id

    except (OSError, TypeError) as error:
        print(f"Error saving report: {error}")
        return None


def load_report(report_id):
    """
    Loads a previously saved report.

    Parameters
    ----------
    report_id : str
        Unique report identifier.

    Returns
    -------
    dict or None
        Report dictionary if found and successfully loaded,
        otherwise None.
    """

    filename = os.path.join(REPORT_FOLDER, f"{report_id}.json")

    if not os.path.exists(filename):
        return None

    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError) as error:
        print(f"Error loading report: {error}")
        return None