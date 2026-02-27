# Google Jobs Scraper

This Python script scrapes job postings from Google Jobs using the [SerpAPI](https://serpapi.com) Google Jobs engine. It extracts structured job details and saves them to a JSON file.

## Features

- Scrapes job postings from Google Jobs.
- Extracts detailed information about each job posting, including title, publisher, description, and application links.
- Filters jobs posted today (optional).
- Customizable search term and job scraping limit.

## Prerequisites

- Python 3.6+
- pip (Python package manager)
- A free [SerpAPI](https://serpapi.com/users/sign_up) key (100 searches/month on the free tier)

## Installation

### 1. Clone the Repository

Start by cloning the repository to your local machine:

```bash
git clone https://github.com/ankhanhtran02/Job_Scraper.git
cd google_jobs_scraper
```

Replace `https://github.com/ankhanhtran02/Job_Scraper.git` with the actual URL of your repository and `google_jobs_scraper` with the name of the folder where you cloned the repository.

### 2. Create a Virtual Environment (Optional but Recommended)

It's a good practice to create a virtual environment for Python projects to manage dependencies effectively. Use the following commands to create and activate a virtual environment:

- For macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

- For Windows:

```bash
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install Dependencies

Install the required dependencies using pip:

```bash
pip install -r requirements.txt
```

### 4. Set your SerpAPI key

Get a free key at <https://serpapi.com/users/sign_up>, then add it to a `.env` file in the project root:

```bash
echo 'SERPAPI_KEY=your_key_here' > .env
```

The `.env` file is automatically loaded by `main.py` — no need to export anything or pass `--api_key` at runtime. It is already excluded from git via `.gitignore`.

## Usage

To run the script:

```bash
python main.py --search_term="Your Search Term" --limit=50 --city_state "City"
```

### All options

| Flag | Default | Description |
|---|---|---|
| `--search_term` | *(required)* | Job title / keywords |
| `--limit` | `50` | Max number of jobs to fetch |
| `--city_state` | — | Location (e.g. `"Hanoi"`, `"New York, NY"`) |
| `--is_today` | `False` | Only return jobs posted today |
| `--hl` | `en` | Language code (`vi` for Vietnamese, etc.) |
| `--gl` | — | Country code (`vn`, `us`, …) |
| `--api_key` | `$SERPAPI_KEY` | Override the key from `.env` at runtime |

### Examples

```bash
# English search, no location filter
python main.py --search_term="data scientist" --limit=100

# Vietnamese internships in Hanoi
python main.py --search_term="thực tập sinh" --limit=50 --city_state "Hà Nội" --hl=vi
```

## Output

The script saves the scraped job postings in a JSON file named `job_scrape_master.json` in the project directory.
