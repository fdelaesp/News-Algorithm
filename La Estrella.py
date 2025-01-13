import re
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import nltk
from nltk.tokenize import sent_tokenize

# Ensure NLTK data is downloaded
nltk.download('punkt', quiet=True)

# ----------------------------- Configuration -----------------------------

# List of category URLs to scrape
CATEGORY_URLS = [
    "https://www.laestrella.com.pa/panama/nacional",
    "https://www.laestrella.com.pa/panama/politica",
    "https://www.laestrella.com.pa/panama/poligrafo",
    "https://www.laestrella.com.pa/mundo",
    "https://www.laestrella.com.pa/economia",
]

# Number of days to look back
DAYS_BACK = 30

# Maximum number of pages to scrape per category to prevent infinite loops
MAX_PAGES = 140

# Timeout for WebDriverWait (in seconds)
WAIT_TIMEOUT = 10

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

def parse_date(date_str):
    """
    Parse date strings and return a datetime object.
    """
    try:
        # Remove any extra spaces and parse date
        date_str = date_str.strip()
        date_obj = datetime.strptime(date_str, '%d/%m/%Y %H:%M')
        return date_obj
    except Exception as e:
        print(f"Date parsing error: {e}")
        return None

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

def format_article_entry(category, headline, article_date, summary):
    """
    Format the article entry as desired:
    Category: [Category]
    [Headline]
    Date: [Date]
    Summary: "..."
    --------------------------------------------------------------------------------
    """
    formatted_entry = (
        f"Category: {category}\n"
        f"{headline}\n"
        f"Date: {article_date}\n"
        f'Summary: "{summary}"\n'
        f"{'-'*80}\n"
    )
    return formatted_entry

def construct_paginated_url(base_url, page_number):
    """
    Construct the URL for a given page number based on the pagination pattern.
    """
    if page_number == 1:
        return base_url
    else:
        return f"{base_url}/pagina/{page_number}"

def summarize_text(text, sentences_count=3):
    """
    Summarize the text by extracting the top N sentences.
    """
    sentences = sent_tokenize(text)
    if len(sentences) <= sentences_count:
        return text
    else:
        return ' '.join(sentences[:sentences_count])

# ----------------------------- Main Scraping Function -----------------------------

def scrape_la_estrella():
    driver = setup_driver()
    scraped_entries = []

    try:
        for category_url in CATEGORY_URLS:
            print(f"\nScraping Category URL: {category_url}")
            current_page = 1
            while current_page <= MAX_PAGES:
                page_url = construct_paginated_url(category_url, current_page)

                print(f"Processing Page {current_page} of {category_url}")
                driver.get(page_url)

                try:
                    # Wait until articles are loaded
                    WebDriverWait(driver, WAIT_TIMEOUT).until(
                        EC.presence_of_all_elements_located((By.CLASS_NAME, 'element'))
                    )
                except Exception as e:
                    print(f"Timeout waiting for articles to load on Page {current_page} of {category_url}.")
                    break  # Move to the next category

                # Parse the page source with BeautifulSoup
                soup = BeautifulSoup(driver.page_source, 'html.parser')

                # Find all articles
                articles = soup.find_all('article', class_=lambda x: x and 'element' in x)

                if not articles:
                    print(f"No articles found on Page {current_page} of {category_url}.")
                    break  # No more articles/pages

                articles_found = 0
                for article in articles:
                    # Extract article URL and headline
                    a_tag = article.find('a', href=True)
                    if not a_tag:
                        continue
                    article_url = urljoin("https://www.laestrella.com.pa", a_tag['href'])
                    headline_span = a_tag.find('span', class_='priority-content')
                    if not headline_span:
                        continue
                    headline = headline_span.get_text(strip=True)

                    print(f"\nProcessing Article: {headline}")
                    print(f"Article URL: {article_url}")

                    # Navigate to the article page to extract the date and summary
                    driver.get(article_url)

                    try:
                        # Wait until the date element is present
                        WebDriverWait(driver, WAIT_TIMEOUT).until(
                            EC.presence_of_element_located((By.CLASS_NAME, 'date'))
                        )
                        # Wait until at least one <p class="p_1"> is present
                        WebDriverWait(driver, WAIT_TIMEOUT).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'p.p_1'))
                        )
                    except Exception as e:
                        print(f"Timeout waiting for content to load in article: {headline}")
                        continue  # Skip this article

                    # Parse the article page
                    article_soup = BeautifulSoup(driver.page_source, 'html.parser')

                    # Extract date from <li class="date"> element
                    date_li = article_soup.find('li', class_='date')
                    if date_li:
                        date_str = date_li.get_text(strip=True)
                        print(f"Extracted Date String: {date_str}")
                    else:
                        print(f"No date found for article: {headline}")
                        continue

                    # Parse date
                    article_date_obj = parse_date(date_str)
                    if not article_date_obj:
                        print(f"Could not parse date for article: {headline}")
                        continue
                    article_date = article_date_obj.strftime('%Y-%m-%d %H:%M:%S')

                    # Check if within the last 7 days
                    if not is_within_days(article_date_obj, DAYS_BACK):
                        print(f"Article '{headline}' is older than {DAYS_BACK} days. Skipping.")
                        continue

                    # Extract article content from <p class="p_1"> elements
                    content_paragraphs = article_soup.find_all('p', class_='p_1')
                    if content_paragraphs:
                        article_text = ' '.join(p.get_text(strip=True) for p in content_paragraphs)
                        print(f"Extracted Article Text: {article_text[:100]}...")  # Print first 100 chars
                        # Summarize the article
                        summary = summarize_text(article_text)
                    else:
                        print(f"No content found for article: {headline}")
                        summary = "No content available."

                    # Determine category from URL
                    category = category_url.rstrip('/').split('/')[-1].capitalize()

                    # Format the entry
                    formatted_entry = format_article_entry(
                        category,
                        headline,
                        article_date,
                        summary
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
        filename = f"la_estrella_{date_range}.txt"
        with open(filename, 'w', encoding='utf-8') as txtfile:
            for entry in scraped_entries:
                txtfile.write(entry)
        print(f"\nScraping completed. Data exported to '{filename}'.")
    else:
        print("\nNo articles found within the specified date range.")

# ----------------------------- Execute Scraping -----------------------------

if __name__ == "__main__":
    scrape_la_estrella()
