import json
import datetime
import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()  # loads SERPAPI_KEY from .env file

OUTPUT_FILE_DIR = "job_scrape_master.json"


class TimeKeeper:
    @property
    def now(self):
        return f"{datetime.datetime.now():%d-%b-%Y T%I:%M}"


def format_job(raw, timekeeper):
    """Normalise a SerpAPI job result into the original output schema."""
    extensions = raw.get("detected_extensions", {})
    highlights = raw.get("job_highlights", [])

    desc_parts = []
    for h in highlights:
        title = h.get("title", "")
        items = h.get("items", [])
        if title:
            desc_parts.append(title)
        desc_parts.extend(items)
    desc = "\n".join(desc_parts) if desc_parts else raw.get("description", "")

    apply_options = raw.get("apply_options", [])
    application_links = [
        {"url": opt.get("link", ""), "platform": opt.get("title", "Unknown Platform")}
        for opt in apply_options
    ]

    return {
        "scrape_time": timekeeper.now,
        "job_title": raw.get("title", "Title not found"),
        "publisher": raw.get("company_name", "Not specified"),
        "time_posted": extensions.get("posted_at", "Not specified"),
        "salary": extensions.get("salary", "Not specified"),
        "benefits": [],
        "job_type": extensions.get("schedule_type", "Not specified"),
        "desc": desc,
        "application_links": application_links,
    }


def build_params(q, api_key, location=None, is_today=False, hl="en", gl=None, next_page_token=None):
    params = {
        "engine": "google_jobs",
        "q": q,
        "api_key": api_key,
        "hl": hl,
    }
    if gl:
        params["gl"] = gl
    if location:
        params["location"] = location
    if is_today:
        params["chips"] = "date_posted:today"
    if next_page_token:
        params["next_page_token"] = next_page_token
    return params


def fetch_page(params):
    search = GoogleSearch(params)
    results = search.get_dict()
    error = results.get("error", "")
    jobs = results.get("jobs_results", [])
    next_page_token = results.get("serpapi_pagination", {}).get("next_page_token")
    return jobs, error, next_page_token


def scrape_jobs(search_term, limit, is_today, city_state, api_key, hl="en", gl=None):
    timekeeper = TimeKeeper()
    scraped_jobs = []
    jobs_per_page = 10

    strategies = []
    if city_state:
        strategies.append({
            "label": f"location='{city_state}'",
            "q": search_term,
            "location": city_state,
        })
        strategies.append({
            "label": f"q embedded ('{search_term} {city_state}')",
            "q": f"{search_term} {city_state}",
            "location": None,
        })
    else:
        strategies.append({
            "label": "no location filter",
            "q": search_term,
            "location": None,
        })

    search_url = f"https://www.google.com/search?q={search_term}&ibp=htl;jobs"
    if city_state:
        search_url += f"&htichips=city;{city_state}"

    print(f"Searching Google Jobs for: '{search_term}'" + (f" in {city_state}" if city_state else ""))

    for strategy in strategies:
        print(f"  Trying strategy: {strategy['label']} ...")
        strategy_jobs = []
        next_page_token = None
        page_num = 1

        while len(strategy_jobs) < limit:
            params = build_params(
                q=strategy["q"],
                api_key=api_key,
                location=strategy["location"],
                is_today=is_today,
                hl=hl,
                gl=gl,
                next_page_token=next_page_token,
            )
            jobs, error, next_page_token = fetch_page(params)

            if error:
                print(f"    SerpAPI error: {error}")
                break

            if not jobs:
                print(f"    No more results on page {page_num}.")
                break

            for job in jobs:
                if len(strategy_jobs) >= limit:
                    break
                strategy_jobs.append(format_job(job, timekeeper))

            print(f"    Page {page_num}: {len(jobs)} jobs (strategy total: {len(strategy_jobs)})")

            if not next_page_token or len(jobs) < jobs_per_page:
                break
            page_num += 1

        if strategy_jobs:
            scraped_jobs = strategy_jobs
            print(f"  ✓ Strategy succeeded with {len(scraped_jobs)} jobs.")
            break
        else:
            print(f"  ✗ Strategy returned no results, trying next...")

    output_data = {"search_page_url": search_url, "jobs": scraped_jobs}
    with open(OUTPUT_FILE_DIR, "w") as outfile:
        json.dump(output_data, outfile, indent=4)

    print(f"\nDone. {len(scraped_jobs)} jobs saved to {OUTPUT_FILE_DIR}")
    return scraped_jobs


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Google Jobs via SerpAPI")
    parser.add_argument("--search_term", type=str, required=True,
                        help="Job title / keywords to search for")
    parser.add_argument("--limit", type=int, default=50,
                        help="Maximum number of jobs to scrape")
    parser.add_argument("--is_today", action="store_true",
                        help="Only include jobs posted today")
    parser.add_argument("--city_state", type=str, default=None,
                        help="Location to filter by (e.g. 'Hanoi' or 'New York, NY')")
    parser.add_argument("--hl", type=str, default="en",
                        help="Language code for results (default: en). Use 'vi' for Vietnamese.")
    parser.add_argument("--gl", type=str, default=None,
                        help="Country code (e.g. 'vn' for Vietnam, 'us' for USA)")
    parser.add_argument("--api_key", type=str,
                        default=os.environ.get("SERPAPI_KEY", ""),
                        help="SerpAPI key (or set SERPAPI_KEY env var). "
                             "Get a free key at https://serpapi.com/users/sign_up")

    args = parser.parse_args()

    if not args.api_key:
        parser.error(
            "SerpAPI key required. Pass --api_key=YOUR_KEY or set the SERPAPI_KEY "
            "environment variable.\nGet a free key (100 searches/month) at "
            "https://serpapi.com/users/sign_up"
        )

    scrape_jobs(
        search_term=args.search_term,
        limit=args.limit,
        is_today=args.is_today,
        city_state=args.city_state,
        api_key=args.api_key,
        hl=args.hl,
        gl=args.gl,
    )
