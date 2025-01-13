import re
import time  # Import the time module for sleep delays
from datetime import datetime, timedelta
from urllib.parse import urljoin  # Import urljoin for constructing URLs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

# ----------------------------- Configuration -----------------------------

# List of category URLs to scrape
CATEGORY_URLS = [
    "https://www.prensa.com/judiciales/",
    "https://www.prensa.com/politica/",
    "https://www.prensa.com/economia/",
    "https://www.prensa.com/mundo/",
    "https://www.prensa.com/unidad-investigativa/"
]

# Number of days to look back
DAYS_BACK = 30

# Maximum number of pages to scrape per category to prevent infinite loops
MAX_PAGES = 140

# ----------------------------- Helper Functions -----------------------------

def setup_driver():
    """Set up the Selenium WebDriver with headless Chrome."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Initialize the Service object with webdriver-manager
    service = Service(ChromeDriverManager().install())

    # Initialize the WebDriver with the Service object
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def parse_relative_date(relative_str):
    """
    Parse relative date strings like 'hace 1 dia', 'hace 12 horas', etc.,
    and return a datetime object.
    """
    now = datetime.now()
    pattern = r'hace\s+(\d+)\s+(\w+)'
    match = re.search(pattern, relative_str.lower())
    if not match:
        return None

    quantity = int(match.group(1))
    unit = match.group(2)

    if 'hora' in unit:
        delta = timedelta(hours=quantity)
    elif 'minuto' in unit:
        delta = timedelta(minutes=quantity)
    elif 'dia' in unit or 'días' in unit:
        delta = timedelta(days=quantity)
    elif 'semana' in unit or 'semanas' in unit:
        delta = timedelta(weeks=quantity)
    elif 'mes' in unit or 'meses' in unit:
        delta = timedelta(days=30 * quantity)  # Approximation
    elif 'año' in unit or 'años' in unit:
        delta = timedelta(days=365 * quantity)  # Approximation
    else:
        return None

    return now - delta

def is_within_days(target_date, days=7):
    """Check if the target_date is within the last 'days' days."""
    cutoff = datetime.now() - timedelta(days=days)
    return target_date >= cutoff

def get_date_range():
    """Get the date range string for the filename."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DAYS_BACK)
    # Format dates as DD-MM-YYYY
    start_str = start_date.strftime('%d-%m-%Y')
    end_str = end_date.strftime('%d-%m-%Y')
    return f"{start_str}_{end_str}"

def format_article_entry(category, headline, article_date, description):
    """
    Format the article entry as desired:
    Category: [Category]
    [Headline]
    Date: [Date]
    Description: "lead"
    --------------------------------------------------------------------------------
    """
    formatted_entry = (
        f"Category: {category}\n"
        f"{headline}\n"
        f"Date: {article_date}\n"
        f'Description: "{description}"\n'
        f"{'-'*80}\n"
    )
    return formatted_entry

def construct_paginated_url(base_url, page_number):
    """
    Construct the URL for a given page number based on the pagination pattern.
    Example:
        base_url = "https://www.prensa.com/unidad-investigativa/"
        page_number = 2
        returns "https://www.prensa.com/unidad-investigativa/2/"
    """
    # Remove trailing slash if present
    if base_url.endswith('/'):
        base_url = base_url[:-1]
    paginated_url = f"{base_url}/{page_number}/"
    return paginated_url

# ----------------------------- Main Scraping Function -----------------------------

def scrape_la_prensa():
    driver = setup_driver()
    scraped_entries = []

    try:
        for category_url in CATEGORY_URLS:
            print(f"\nScraping Category URL: {category_url}")
            current_page = 1
            while current_page <= MAX_PAGES:
                if current_page == 1:
                    page_url = category_url
                else:
                    page_url = construct_paginated_url(category_url, current_page)

                print(f"Processing Page {current_page} of {category_url}")
                driver.get(page_url)

                # Wait until articles are loaded
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.story-box"))
                    )
                except:
                    print(f"No articles found on Page {current_page} of {category_url}.")
                    break  # No more articles/pages

                # Let dynamic content load
                time.sleep(2)

                # Parse the page source with BeautifulSoup
                soup = BeautifulSoup(driver.page_source, 'html.parser')

                # Find all articles
                articles = soup.find_all('div', class_=re.compile(r'story-box'))

                if not articles:
                    print(f"No articles found on Page {current_page} of {category_url}.")
                    break  # No more articles/pages

                articles_found = 0
                for article in articles:
                    # Extract headline
                    headline_tag = article.find('a', href=True)
                    if not headline_tag:
                        continue
                    headline = headline_tag.get_text(strip=True)

                    # Extract relative URL (not used in output as per user request)
                    relative_url = headline_tag['href']
                    # Ensure the URL is relative
                    if relative_url.startswith('http'):
                        # Convert to relative URL
                        relative_url = '/' + '/'.join(relative_url.split('/')[3:])

                    # Remove trailing slash from URL to prevent issues
                    relative_url = relative_url.rstrip('/')

                    # Extract date
                    date_tag = article.find('span', class_=re.compile(r'story-box-timeago'))
                    if not date_tag:
                        continue
                    relative_date_str = date_tag.get_text(strip=True)

                    # Parse date
                    article_date_obj = parse_relative_date(relative_date_str)
                    if not article_date_obj:
                        continue
                    article_date = article_date_obj.strftime('%Y-%m-%d %H:%M:%S')

                    # Extract description (NEW)
                    description_tag = article.find('span', class_=re.compile(r'story-box-lead'))
                    if description_tag:
                        description = description_tag.get_text(strip=True)
                    else:
                        description = "No description available."

                    # Check if within the last 7 days
                    if is_within_days(article_date_obj, DAYS_BACK):
                        # Determine category from URL
                        # Extract category name from URL
                        match = re.search(r'https://www\.prensa\.com/([^/]+)/', urljoin("https://www.prensa.com", relative_url))
                        category = match.group(1).replace('-', ' ').capitalize() if match else "Unknown"

                        # Format the entry with the new description
                        formatted_entry = format_article_entry(
                            category,
                            headline,
                            article_date,
                            description  # Pass the description here
                        )
                        scraped_entries.append(formatted_entry)
                        articles_found += 1

                print(f"Found {articles_found} articles on Page {current_page} of category.")

                # Stop paginating if no recent articles were found
                if articles_found == 0:
                    print(f"No recent articles found on Page {current_page}. Stopping pagination for this category.")
                    break

                current_page += 1

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        driver.quit()

    # Export scraped data to Text File
    if scraped_entries:
        date_range = get_date_range()
        filename = f"la_prensa_{date_range}.txt"
        with open(filename, 'w', encoding='utf-8') as txtfile:
            for entry in scraped_entries:
                txtfile.write(entry)
        print(f"\nScraping completed. Data exported to '{filename}'.")
    else:
        print("\nNo articles found within the specified date range.")

# ----------------------------- Execute Scraping -----------------------------

if __name__ == "__main__":
    scrape_la_prensa()
