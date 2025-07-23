# GitHub Email Scraper

This project is a powerful and flexible tool for scraping email addresses from GitHub repositories. It features a web-based user interface for ease of use, as well as a command-line interface for more advanced users.

## Features

- **Web Interface**: A clean, modern, and intuitive web UI for running the scraper and extracting emails.
- **Command-Line Interface**: A powerful CLI for advanced users and automation.
- **Multithreaded**: Uses multithreading to scrape multiple repositories concurrently for maximum speed.
- **Email Extraction**: A feature to extract and clean email addresses from a CSV file.
- **Persistent Token Storage**: Securely saves your GitHub token in your browser's local storage for convenience.
- **Real-time Progress**: A real-time progress bar to monitor the scraping process.
- **Interactive Results**: Sortable results table and a "Copy to Clipboard" feature.
- **Robust Validation**: Advanced email validation and cleaning to ensure data quality.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd simple-gitbub-scrapper
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create a `.env` file:**
    Create a file named `.env` in the root of the project and add your GitHub personal access token:
    ```
    GITHUB_TOKEN=your_token_here
    ```

## Usage

### Web Interface

To use the web interface, run the following command:

```bash
python web_ui/app.py
```

Then, open your web browser and navigate to `http://127.0.0.1:5001`.

### Command-Line Interface

The `scrap.py` script can be run directly from the command line with various arguments:

```bash
python scrap.py --query "your query" --max-repos 50 --output my_leads.csv
```

For a full list of options, run:

```bash
python scrap.py --help
