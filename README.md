# ssScrapeR
# SS.LV Real Estate Monitor

A Python automation script that monitors SS.LV real estate listings and sends email notifications for new properties matching your criteria.

## Features

- ✅ Monitors multiple SS.LV URLs simultaneously
- ✅ Tracks seen listings to avoid duplicate notifications
- ✅ Configurable search criteria (price, area, keywords)
- ✅ Email notifications with property details
- ✅ Runs in single-check mode (perfect for free hosting)

## Quick Start

### Option 1: Manual Runs (Replit Free Plan)

1. Run the script manually whenever you want to check for new listings:
   ```bash
   python ss_lv_monitor.py
   ```

2. Configure your email credentials as environment variables:
   - `EMAIL_FROM` - Your Gmail address
   - `EMAIL_PASSWORD` - Your Gmail app password
   - `EMAIL_TO` - Where to send notifications

### Option 2: Automated Daily Runs (GitHub Actions - Free)

1. Fork this repository to your GitHub account
2. Go to repository Settings → Secrets and variables → Actions
3. Add these secrets:
   - `EMAIL_FROM` - Your Gmail address
   - `EMAIL_PASSWORD` - Your Gmail app password  
   - `EMAIL_TO` - Where to send notifications
4. The script will automatically run daily at 8:00 AM UTC

## Configuration

Edit the `SEARCH_CRITERIA` in `ss_lv_monitor.py`:

```python
SEARCH_CRITERIA = {
    "max_price": 150000,     # Maximum price in EUR
    "min_price": 10000,      # Minimum price in EUR
    "min_area": 50,          # Minimum area in m²
    "keywords_include": ["māja", "zeme", "privātmāja", "dzīvoklis"],
    "keywords_exclude": ["bojāts", "avārijas", "slēgts"]
}
```

Add or modify URLs in `URLS_TO_MONITOR`:

```python
URLS_TO_MONITOR = [
    "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga-region/olaines-pag/filter/",
    "https://www.ss.lv/lv/real-estate/plots-and-lands/riga-region/olaines-pag/filter/"
]
```

## How It Works

1. **Scraping**: Extracts listing data from SS.LV pages
2. **Tracking**: Stores seen listing IDs in `listings_data.json`
3. **Filtering**: Applies your search criteria to new listings
4. **Notification**: Sends email alerts for matches
5. **Memory**: Prevents duplicate notifications

## Files

- `ss_lv_monitor.py` - Main monitoring script
- `listings_data.json` - Tracks seen listings
- `.github/workflows/daily-monitor.yml` - GitHub Actions automation
- `ss_lv_monitor.log` - Execution logs

## Requirements

- Python 3.11+
- beautifulsoup4
- requests
- schedule (for continuous mode)

## Gmail Setup

1. Enable 2-factor authentication on your Gmail account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. Use this app password (not your regular password) for `EMAIL_PASSWORD`
