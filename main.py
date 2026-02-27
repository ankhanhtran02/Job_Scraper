import json
import math
import datetime
import os
import re
import time
from dotenv import load_dotenv
from serpapi import GoogleSearch
from requests.exceptions import ConnectionError as RequestsConnectionError

load_dotenv()  # loads SERPAPI_KEY from .env file


class TimeKeeper:
    @property
    def now(self):
        return f"{datetime.datetime.now():%d-%b-%Y T%I:%M}"


def format_job(raw, timekeeper):
    """Normalise a SerpAPI job result into the output schema."""
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


OUTPUT_DIR = "output"

MAX_RETRIES = 3
RETRY_DELAY = 5   # seconds between retries


def _get_dict_with_retry(params):
    """Call SerpAPI with automatic retry on transient connection errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return GoogleSearch(params).get_dict()
        except RequestsConnectionError as exc:
            if attempt == MAX_RETRIES:
                raise
            print(f"  Network error (attempt {attempt}/{MAX_RETRIES}): {exc}. "
                  f"Retrying in {RETRY_DELAY}s…")
            time.sleep(RETRY_DELAY)


def make_output_filename(search_term, city_state):
    """Build a filepath like: output/data_scientist_Hanoi_2026-02-27_14-30.json"""
    parts = [search_term]
    if city_state:
        parts.append(city_state)
    slug = "_".join(parts)
    slug = re.sub(r"[^\w\s-]", "", slug)   # strip special chars
    slug = re.sub(r"[\s]+", "_", slug.strip())
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, f"{slug}_{timestamp}.json")


def scrape_jobs(search_term, limit, is_today, city_state, api_key, hl="en", gl=None):
    timekeeper = TimeKeeper()

    # Round limit UP to the nearest multiple of 10
    pages_needed = math.ceil(limit / 10)
    target = pages_needed * 10

    # SerpAPI's google_jobs engine reliably returns only ~10 results per query;
    # next_page_token consistently fails on page 2 regardless of params.
    # Workaround: run multiple queries with different date-range chips to
    # accumulate up to `target` unique results (deduplicated by title+company).
    date_chips = (
        ["date_posted:today"]
        if is_today
        else ["date_posted:today", "date_posted:3days",
              "date_posted:week", "date_posted:month", ""]
    )

    # Always embed the city in the query so SerpAPI geo-filters correctly.
    # Never fall back to a plain q without location — that returns global results.
    def queries_for_chip(chip):
        q = f"{search_term} {city_state}" if city_state else search_term
        yield (f"q='{q}', chips='{chip}'", q, chip)

    search_url = (
        f"https://www.google.com/search?q={search_term}&ibp=htl;jobs"
        + (f"&htichips=city;{city_state}" if city_state else "")
    )

    print(f"Searching Google Jobs for: '{search_term}'"
          + (f" in {city_state}" if city_state else ""))
    print(f"Requested limit: {limit}  →  collecting up to {target} unique results")

    seen = set()        # deduplicate by (title, company)
    scraped_jobs = []
    last_next_page_token = None

    for chip in date_chips:
        for label, q, chip_val in queries_for_chip(chip):
            if len(scraped_jobs) >= target:
                break

            params = {
                "engine": "google_jobs",
                "q": q,
                "hl": hl,
                "api_key": api_key,
            }
            if gl:
                params["gl"] = gl
            if chip_val:
                params["chips"] = chip_val

            results = _get_dict_with_retry(params)
            error = results.get("error", "")
            jobs = results.get("jobs_results", [])
            token = results.get("serpapi_pagination", {}).get("next_page_token")

            if error:
                print(f"  [{label}] error: {error}")
                continue
            if not jobs:
                print(f"  [{label}] no results")
                continue

            added = 0
            for job in jobs:
                if len(scraped_jobs) >= target:
                    break
                key = (job.get("title", ""), job.get("company_name", ""))
                if key not in seen:
                    seen.add(key)
                    scraped_jobs.append(format_job(job, timekeeper))
                    added += 1

            last_next_page_token = token
            print(f"  [{label}] {len(jobs)} results, {added} new (total unique: {len(scraped_jobs)})")

        if len(scraped_jobs) >= target:
            break

    # Build output filename and metadata
    output_filename = make_output_filename(search_term, city_state)

    resume_params = {
        "engine": "google_jobs",
        "q": f"{search_term} {city_state}" if city_state else search_term,
        "hl": hl,
    }
    if gl:
        resume_params["gl"] = gl
    if last_next_page_token:
        resume_params["next_page_token"] = last_next_page_token

    output_data = {
        "search_term": search_term,
        "location": city_state or None,
        "search_page_url": search_url,
        "query_params": resume_params,
        "total_jobs": len(scraped_jobs),
        "last_next_page_token": last_next_page_token,
        "jobs": scraped_jobs,
    }

    with open(output_filename, "w", encoding="utf-8") as outfile:
        json.dump(output_data, outfile, indent=4, ensure_ascii=False)

    print(f"\nDone. {len(scraped_jobs)} jobs saved to '{output_filename}'")
    return scraped_jobs


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Google Jobs via SerpAPI")
    parser.add_argument("--search_term", type=str, required=True,
                        help="Job title / keywords to search for")
    parser.add_argument("--limit", type=int, default=10,
                        help="Number of jobs to scrape (rounded up to next multiple of 10)")
    parser.add_argument("--is_today", action="store_true",
                        help="Only include jobs posted today")
    parser.add_argument("--city_state", type=str, default=None,
                        help="Location to filter by (e.g. 'Hanoi' or 'New York, NY')")
    parser.add_argument("--hl", type=str, default="en",
                        help="Language code (default: en). Use 'vi' for Vietnamese.")
    parser.add_argument("--gl", type=str, default=None,
                        help="Country code (e.g. 'vn' for Vietnam, 'us' for USA)")
    parser.add_argument("--api_key", type=str,
                        default=os.environ.get("SERPAPI_KEY", ""),
                        help="SerpAPI key (or set SERPAPI_KEY in .env)")

    args = parser.parse_args()

    if not args.api_key:
        parser.error(
            "SerpAPI key required. Pass --api_key=YOUR_KEY or add SERPAPI_KEY to .env\n"
            "Get a free key (250 searches/month) at https://serpapi.com/users/sign_up"
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
