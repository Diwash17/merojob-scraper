# 🇳🇵 Merojob.com Web Scraper

A simple Python web scraper that extracts job listings from [Merojob.com](https://merojob.com) — Nepal's leading job portal.

## Features

- Scrapes **job title**, **company name**, and **location** from Merojob.com
- Extracts **20-30+ job listings** across multiple pages
- Saves data in both **JSON** and **CSV** formats
- Built-in **error handling** for missing data and network issues
- Polite scraping with **request delays** to avoid overloading the server
- **Deduplication** to ensure no repeated listings

## Requirements

- Python 3.7 or higher
- `requests` library
- `beautifulsoup4` library

## Installation

1. **Clone or download** this project:

   ```bash
   cd merojob-scraper
   ```

2. **(Recommended)** Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate        # macOS/Linux
   venv\Scripts\activate           # Windows
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the scraper with a single command:

```bash
python scraper.py
```

### Output Files

The scraper creates two output files in the same directory:

| File         | Format | Description                              |
| ------------ | ------ | ---------------------------------------- |
| `jobs.json`  | JSON   | Structured data with metadata            |
| `jobs.csv`   | CSV    | Flat format, ready for Excel/Sheets      |

### JSON Output Structure

```json
{
  "metadata": {
    "source": "merojob.com",
    "scraped_at": "2025-03-13T21:30:00",
    "total_jobs": 30
  },
  "jobs": [
    {
      "title": "Software Engineer",
      "company": "Tech Company Nepal",
      "location": "Kathmandu",
      "job_url": "https://merojob.com/software-engineer-123"
    }
  ]
}
```

### CSV Output

The CSV file has the following columns:

| Column     | Description                    |
| ---------- | ------------------------------ |
| `title`    | Job title / position name      |
| `company`  | Hiring company or organization |
| `location` | Job location in Nepal          |
| `job_url`  | Direct link to the job listing |

## Configuration

You can adjust these settings at the top of `scraper.py`:

| Variable        | Default | Description                          |
| --------------- | ------- | ------------------------------------ |
| `TARGET_JOBS`   | `30`    | Minimum number of jobs to scrape     |
| `MAX_PAGES`     | `5`     | Maximum search pages to crawl        |
| `REQUEST_DELAY` | `1.5`   | Delay between requests (seconds)     |
| `JSON_OUTPUT`   | `jobs.json` | JSON output filename             |
| `CSV_OUTPUT`    | `jobs.csv`  | CSV output filename              |

## How It Works

1. **Fetches** the Merojob homepage and search pages using HTTP requests
2. **Parses** embedded Next.js RSC (React Server Component) data from `<script>` tags
3. **Falls back** to HTML parsing if RSC data is not available
4. **Deduplicates** results based on job URL/slug
5. **Enriches** jobs missing location data by visiting individual job pages
6. **Exports** the clean data to JSON and CSV files

## 💡 Technical Challenges & Solutions

### 1. Handling Next.js RSC Streams
Modern websites like Merojob move away from static HTML to **React Server Components (RSC)**. The data isn't in the HTML tags; it's streamed in a `self.__next_f.push()` script block.
- **Solution:** I implemented a custom regex-based JSON parser that extracts these dynamic fragments and converts them into structured Python objects.

### 2. Polite Rate Limiting
Scraping too fast can get your IP blocked. 
- **Solution:** Integrated a `Session` object with custom headers and a `1.5s` request delay to mimic human behavior and stay within fair-use limits.

### 3. Data Cleaning
Raw data is often messy (duplicate slugs, inconsistent company names).
- **Solution:** Used Python `Sets` for O(1) deduplication and custom heuristics to "guess" company names when missing from the primary data stream.

## 📁 Sample Data for Interviews
To see the results without running the code, check the `samples/` directory:
- [Sample JSON](samples/sample_jobs.json)
- [Sample CSV](samples/sample_jobs.csv)
