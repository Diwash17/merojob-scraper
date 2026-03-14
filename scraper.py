"""
Merojob.com Job Scraper
=======================
Scrapes job listings from merojob.com (Nepal's leading job portal).
Extracts job title, company name, location, and more.
Saves data in JSON and CSV formats.

Usage:
    python scraper.py
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import re
import time
import sys
from datetime import datetime


# ─── Configuration ───────────────────────────────────────────────────────────

BASE_URL = "https://merojob.com"
SEARCH_URL = f"{BASE_URL}/search/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
TARGET_JOBS = 30       # Minimum number of jobs to scrape
MAX_PAGES = 5          # Maximum pages to crawl (safety limit)
REQUEST_DELAY = 1.5    # Polite delay between requests (seconds)
JSON_OUTPUT = "jobs.json"
CSV_OUTPUT = "jobs.csv"


# ─── Helper Functions ────────────────────────────────────────────────────────

def fetch_page(url, params=None):
    """Fetch a web page and return the response object."""
    try:
        print(f"  → Fetching: {url}" + (f"?page={params.get('page', '')}" if params else ""))
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout:
        print(f"  ✗ Request timed out for {url}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"  ✗ Connection error for {url}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"  ✗ HTTP error {e.response.status_code} for {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request failed: {e}")
        return None


def extract_jobs_from_rsc_data(html_content):
    """
    Extract job data from Next.js React Server Component (RSC) script tags.
    
    Merojob uses Next.js App Router which streams data via
    self.__next_f.push([...]) script blocks embedded in the HTML.
    The job data is JSON-encoded within these script blocks.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    jobs = []

    # Find all script tags containing RSC data
    scripts = soup.find_all("script")

    for script in scripts:
        if not script.string:
            continue

        text = script.string.strip()

        # Look for self.__next_f.push blocks that contain job data
        if "self.__next_f.push" not in text:
            continue

        # Extract JSON-like data from the push calls
        # Pattern: self.__next_f.push([1,"...json data..."])
        try:
            # Find all occurrences of job-related data in the script
            # Look for patterns with "title" and "slug" which indicate job objects
            job_matches = re.findall(
                r'\{[^{}]*"title"\s*:\s*"[^"]+?"[^{}]*"slug"\s*:\s*"[^"]+?"[^{}]*\}',
                text
            )

            for match in job_matches:
                try:
                    # Clean up the JSON string - handle escaped characters
                    cleaned = match.replace('\\"', '"')
                    job_data = json.loads(cleaned)

                    # Only process if it looks like a job listing
                    if "title" in job_data and "slug" in job_data:
                        job = parse_job_object(job_data)
                        if job and job not in jobs:
                            jobs.append(job)
                except (json.JSONDecodeError, KeyError):
                    continue

        except Exception:
            pass

    return jobs


def extract_jobs_from_html(html_content):
    """
    Fallback: Extract job data directly from the rendered HTML structure.
    Parses the homepage 'Top Jobs' section which has job listings
    grouped by company.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    jobs = []

    # Find all job links on the page
    # Job links follow the pattern: /job-slug-name
    all_links = soup.find_all("a", href=True)

    seen_slugs = set()

    for link in all_links:
        href = link.get("href", "")

        # Skip non-job links
        if not href.startswith("/") or any(
            skip in href
            for skip in [
                "/employer/", "/search", "/category", "/blog", "/login",
                "/register", "/faq", "/about", "/contact", "/training",
                "/terms", "/privacy", "/online", "/recruitment", "/etender",
                "/location", "/designation", "/company", "/industry",
                "/jobseeker", "/employer", "/cdn-cgi", "/events",
            ]
        ):
            continue

        # Must have reasonable slug length
        slug = href.strip("/")
        if len(slug) < 3 or slug in seen_slugs:
            continue

        seen_slugs.add(slug)

        # Get job title from link text
        title_span = link.find("span")
        title = (
            title_span.get_text(strip=True) if title_span
            else link.get_text(strip=True)
        )

        if not title or len(title) < 2:
            continue

        # Try to find the nearest company name
        company = find_company_for_link(link)

        jobs.append({
            "title": title,
            "company": company if company else "Not Specified",
            "location": "Nepal",
            "job_url": f"{BASE_URL}{href}",
            "slug": slug,
        })

    return jobs


def find_company_for_link(link_element):
    """
    Walk up the DOM to find the company name associated with a job link.
    On the homepage, jobs are grouped under company headings (h3 tags).
    """
    # Check for nearest employer link in the parent container
    parent = link_element.parent
    for _ in range(5):  # Walk up to 5 levels
        if parent is None:
            break

        # Look for employer link
        employer_link = parent.find("a", href=re.compile(r"/employer/"))
        if employer_link:
            return employer_link.get_text(strip=True)

        # Look for h3 heading (company name on homepage)
        h3 = parent.find("h3")
        if h3 and h3 != link_element.parent:
            return h3.get_text(strip=True)

        parent = parent.parent

    return None


def parse_job_object(data):
    """Parse a raw job data object into a clean dictionary."""
    title = data.get("title", "").strip()
    slug = data.get("slug", "").strip()

    if not title or not slug:
        return None

    # Extract company info
    company = "Not Specified"
    if "company" in data:
        if isinstance(data["company"], dict):
            company = data["company"].get("name", "Not Specified")
        elif isinstance(data["company"], str):
            company = data["company"]

    # Extract location
    location = "Nepal"
    if "location" in data:
        if isinstance(data["location"], list):
            location = ", ".join(str(loc) for loc in data["location"] if loc)
        elif isinstance(data["location"], str):
            location = data["location"]

    if "address" in data:
        location = data["address"]

    return {
        "title": title,
        "company": company if company else "Not Specified",
        "location": location if location else "Nepal",
        "job_url": f"{BASE_URL}/{slug}",
        "slug": slug,
    }


def scrape_job_details(job_url):
    """
    Scrape additional details from an individual job page.
    Extracts location, company, and other metadata.
    """
    response = fetch_page(job_url)
    if not response:
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    details = {}

    # Try to extract location from meta tags or page content
    # Look for common patterns in the page
    text_content = soup.get_text()

    # Search for location patterns
    location_patterns = [
        r"Location[:\s]+([A-Za-z\s,]+(?:Nepal|Kathmandu|Pokhara|Lalitpur|Bhaktapur|Biratnagar|Birgunj|Bharatpur|Hetauda|Dharan|Butwal|Nepalgung|Janakpur|Itahari)[A-Za-z\s,]*)",
        r"(Kathmandu|Lalitpur|Bhaktapur|Pokhara|Biratnagar|Birgunj|Bharatpur|Hetauda|Dharan|Butwal|Nepalgung|Janakpur|Itahari)",
    ]

    for pattern in location_patterns:
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            details["location"] = match.group(1).strip().rstrip(",")
            break

    return details


def enrich_jobs_with_details(jobs, max_enrich=10):
    """
    Enrich job listings that are missing location data
    by visiting individual job pages.
    """
    enriched_count = 0

    for job in jobs:
        if job.get("location") in ("Nepal", "Not Specified", ""):
            if enriched_count >= max_enrich:
                break

            print(f"  → Enriching: {job['title']}")
            details = scrape_job_details(job["job_url"])

            if details.get("location"):
                job["location"] = details["location"]
                enriched_count += 1

            time.sleep(REQUEST_DELAY)

    return jobs


def save_to_json(jobs, filename):
    """Save job listings to a JSON file."""
    output = {
        "metadata": {
            "source": "merojob.com",
            "scraped_at": datetime.now().isoformat(),
            "total_jobs": len(jobs),
        },
        "jobs": jobs,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved {len(jobs)} jobs to {filename}")


def save_to_csv(jobs, filename):
    """Save job listings to a CSV file."""
    if not jobs:
        print("  ✗ No jobs to save to CSV")
        return

    fieldnames = ["title", "company", "location", "job_url"]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)

    print(f"  ✓ Saved {len(jobs)} jobs to {filename}")


def remove_duplicates(jobs):
    """Remove duplicate job listings based on slug/URL."""
    seen = set()
    unique_jobs = []

    for job in jobs:
        key = job.get("slug", job.get("job_url", ""))
        if key and key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    return unique_jobs


# ─── Main Scraper ────────────────────────────────────────────────────────────

def main():
    """Main entry point for the scraper."""
    print("=" * 60)
    print("  Merojob.com Job Scraper")
    print("  Nepal's Leading Job Portal")
    print("=" * 60)
    print()

    all_jobs = []

    # ── Step 1: Scrape the homepage ──────────────────────────────
    print("[1/4] Scraping homepage for job listings...")
    response = fetch_page(BASE_URL)

    if response:
        # Try RSC data extraction first (more structured)
        rsc_jobs = extract_jobs_from_rsc_data(response.text)
        if rsc_jobs:
            print(f"  ✓ Found {len(rsc_jobs)} jobs from embedded data")
            all_jobs.extend(rsc_jobs)

        # Also extract from HTML structure
        html_jobs = extract_jobs_from_html(response.text)
        if html_jobs:
            print(f"  ✓ Found {len(html_jobs)} jobs from HTML structure")
            all_jobs.extend(html_jobs)
    else:
        print("  ✗ Failed to fetch homepage")

    # ── Step 2: Scrape search pages if needed ────────────────────
    print()
    print("[2/4] Scraping search pages for more listings...")

    page = 1
    while len(all_jobs) < TARGET_JOBS and page <= MAX_PAGES:
        time.sleep(REQUEST_DELAY)

        response = fetch_page(SEARCH_URL, params={"q": "", "page": page})
        if not response:
            break

        # Try RSC extraction on search pages too
        rsc_jobs = extract_jobs_from_rsc_data(response.text)
        if rsc_jobs:
            print(f"  ✓ Page {page}: Found {len(rsc_jobs)} jobs")
            all_jobs.extend(rsc_jobs)
        else:
            # Try HTML extraction as fallback
            html_jobs = extract_jobs_from_html(response.text)
            if html_jobs:
                print(f"  ✓ Page {page}: Found {len(html_jobs)} jobs (HTML)")
                all_jobs.extend(html_jobs)
            else:
                print(f"  ○ Page {page}: No new jobs found, stopping.")
                break

        page += 1

    # ── Step 3: Clean and deduplicate ────────────────────────────
    print()
    print("[3/4] Processing and cleaning data...")

    all_jobs = remove_duplicates(all_jobs)
    print(f"  ✓ {len(all_jobs)} unique jobs after deduplication")

    # Try to enrich jobs missing location data
    jobs_missing_location = sum(
        1 for j in all_jobs if j.get("location") in ("Nepal", "Not Specified", "")
    )
    if jobs_missing_location > 0:
        print(f"  → {jobs_missing_location} jobs missing specific location")
        print("  → Enriching top jobs with location details...")
        all_jobs = enrich_jobs_with_details(all_jobs, max_enrich=10)

    # Remove the slug field from final output (internal use only)
    for job in all_jobs:
        job.pop("slug", None)

    # ── Step 4: Save results ─────────────────────────────────────
    print()
    print("[4/4] Saving results...")

    if not all_jobs:
        print("  ✗ No jobs were scraped! The website structure may have changed.")
        print("  → Please check if merojob.com is accessible and try again.")
        sys.exit(1)

    save_to_json(all_jobs, JSON_OUTPUT)
    save_to_csv(all_jobs, CSV_OUTPUT)

    # ── Summary ──────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  Scraping Complete!")
    print(f"  Total jobs scraped: {len(all_jobs)}")
    print(f"  Output files: {JSON_OUTPUT}, {CSV_OUTPUT}")
    print("=" * 60)
    print()
    print("Sample jobs:")
    print("-" * 60)

    for i, job in enumerate(all_jobs[:5], 1):
        print(f"  {i}. {job['title']}")
        print(f"     Company:  {job['company']}")
        print(f"     Location: {job['location']}")
        print(f"     URL:      {job['job_url']}")
        print()


if __name__ == "__main__":
    main()
