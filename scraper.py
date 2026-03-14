"""
Merojob.com Job Scraper (Interview Edition)
===========================================
A professional-grade scraper for merojob.com.
Demonstrates: Type hints, advanced regex parsing, RSC data extraction,
polite crawling, and dual-format data export.

Author: Diwash Adhikari
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import re
import time
import sys
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Set
from pathlib import Path

# ─── Professional Logging Configuration ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

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
}

class MerojobScraper:
    """Professional scraper for Merojob.com listings."""

    def __init__(self, target_jobs: int = 30, max_pages: int = 5):
        self.target_jobs = target_jobs
        self.max_pages = max_pages
        self.request_delay = 1.5
        self.all_jobs: List[Dict[str, str]] = []
        self.seen_slugs: Set[str] = set()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_page(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[requests.Response]:
        """Fetch a page with error handling and logging."""
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def extract_rsc_data(self, html_content: str) -> List[Dict[str, str]]:
        """
        Extracts job data from Next.js React Server Component (RSC) streams.
        Next.js streams data via self.__next_f.push calls inside <script> tags.
        """
        jobs = []
        soup = BeautifulSoup(html_content, "html.parser")
        scripts = soup.find_all("script")

        for script in scripts:
            if not script.string or "self.__next_f.push" not in script.string:
                continue

            # This regex identifies JSON-like objects containing job markers
            job_matches = re.findall(
                r'\{[^{}]*"title"\s*:\s*"[^"]+?"[^{}]*"slug"\s*:\s*"[^"]+?"[^{}]*\}',
                script.string
            )

            for match in job_matches:
                try:
                    cleaned = match.replace('\\"', '"')
                    data = json.loads(cleaned)
                    
                    if "title" in data and "slug" in data:
                        job = self._process_job_object(data)
                        if job:
                            jobs.append(job)
                except (json.JSONDecodeError, KeyError):
                    continue
        return jobs

    def extract_from_html(self, html_content: str) -> List[Dict[str, str]]:
        """Fallback: Parse traditional HTML structure for listings."""
        jobs = []
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Scrape all reasonable job links
        for a in soup.find_all("a", href=True):
            href = a['href']
            # Filters out non-job URLs (employer pages, auth, etc)
            if not self._is_valid_job_link(href):
                continue

            slug = href.strip("/")
            if slug in self.seen_slugs:
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 2:
                continue

            # Identify company via parent lookups
            company = self._guess_company_name(a)

            jobs.append({
                "title": title,
                "company": company or "Contact Employer",
                "location": "Nepal",
                "job_url": f"{BASE_URL}/{slug}",
                "slug": slug
            })
        return jobs

    def _is_valid_job_link(self, href: str) -> bool:
        """Utility to check if a link points to a job listing."""
        exclude_patterns = [
            "/employer/", "/search", "/category", "/blog", "/login",
            "/register", "/faq", "/about", "/contact", "/training",
            "/events", "/cdn-cgi"
        ]
        return (
            href.startswith("/") and 
            len(href) > 5 and
            not any(p in href for p in exclude_patterns)
        )

    def _guess_company_name(self, link_element: Any) -> Optional[str]:
        """Examines parent hierarchy to find company context."""
        curr = link_element.parent
        for _ in range(5):
            if not curr: break
            # Look for explicit company links
            emp_link = curr.find("a", href=re.compile(r"/employer/"))
            if emp_link: return emp_link.get_text(strip=True)
            # Look for headers
            h3 = curr.find("h3")
            if h3 and h3 != link_element: return h3.get_text(strip=True)
            curr = curr.parent
        return None

    def _process_job_object(self, data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Cleans raw JSON data into standardized dictionary."""
        slug = data.get("slug")
        if not slug or slug in self.seen_slugs:
            return None

        self.seen_slugs.add(slug)
        
        company = "Not Specified"
        if "company" in data:
            comp_data = data["company"]
            company = comp_data.get("name") if isinstance(comp_data, dict) else comp_data

        return {
            "title": data.get("title", "Untitled Position"),
            "company": company or "Contact Employer",
            "location": data.get("location", "Nepal"),
            "job_url": f"{BASE_URL}/{slug}",
            "slug": slug
        }

    def run(self):
        """Orchestrates the scraping flow."""
        logger.info("Starting Merojob.com scraper...")
        
        # Phase 1: Homepage
        resp = self.fetch_page(BASE_URL)
        if resp:
            self.all_jobs.extend(self.extract_rsc_data(resp.text))
            self.all_jobs.extend(self.extract_from_html(resp.text))

        # Phase 2: Search Pages
        page = 1
        while len(self.all_jobs) < self.target_jobs and page <= self.max_pages:
            logger.info(f"Crawling search page {page}...")
            time.sleep(self.request_delay)
            
            resp = self.fetch_page(SEARCH_URL, params={"page": page})
            if not resp: break
            
            new_jobs = self.extract_rsc_data(resp.text)
            if not new_jobs:
                new_jobs = self.extract_from_html(resp.text)
            
            if not new_jobs: break
            self.all_jobs.extend(new_jobs)
            page += 1

        # Phase 3: Export
        self._export_results()

    def _export_results(self):
        """Deduplicates and saves to final files."""
        unique_jobs = []
        seen = set()
        for j in self.all_jobs:
            if j['job_url'] not in seen:
                seen.add(j['job_url'])
                # Clean slug for final output
                job_data = {k: v for k, v in j.items() if k != 'slug'}
                unique_jobs.append(job_data)

        logger.info(f"Found {len(unique_jobs)} unique jobs.")
        
        # Save JSON
        with open("jobs.json", "w", encoding="utf-8") as f:
            json.dump({"total": len(unique_jobs), "jobs": unique_jobs}, f, indent=2)
            
        # Save CSV
        with open("jobs.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "company", "location", "job_url"])
            writer.writeheader()
            writer.writerows(unique_jobs)
        
        logger.info("Data exported to jobs.json and jobs.csv")

if __name__ == "__main__":
    scraper = MerojobScraper(target_jobs=30)
    scraper.run()
