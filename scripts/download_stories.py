import os
import json
from glob import glob
import sys
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException

# NOTE: The explicit HEADERS dictionary is no longer needed as Selenium
# uses the full set of real browser headers automatically.

def get_article(driver: webdriver.Chrome, url: str, limit: int = 5000) -> str | None:
    """
    Uses an existing Selenium driver to fetch the URL content, 
    parses the fully rendered HTML, extracts text from all <p> tags, 
    and truncates the result.
    
    Args:
        driver (webdriver.Chrome): The persistent Selenium driver instance.
        url (str): The URL to fetch.
        limit (int): The maximum number of characters to return (default 5000).

    Returns:
        str | None: The cleaned text content of the article, truncated to the 
                    limit, or None if the request failed or driver crashed.
    """
    
    if not url.startswith(('http://', 'https://')):
        print("Error: URL must start with 'http://' or 'https://'.")
        return None

    try:
        # Set the page load timeout (20 seconds for full page load)
        driver.set_page_load_timeout(20)

        # Navigate to the URL
        print(f"  -> Navigating to: {url[:50]}...")
        driver.get(url)
        
        # Get the fully rendered page source
        html_content = driver.page_source

        # Parse the content using Beautiful Soup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all <p> tags and extract their text content
        p_tags = soup.find_all('p')
        paragraph_list = [p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)]
        
        # Join the paragraphs into a single string
        article_text = '\n\n'.join(paragraph_list)

        # Apply the limit
        if len(article_text) > limit:
            final_text = article_text[:limit] + '...'
        else:
            final_text = article_text

        return final_text

    except TimeoutException:
        print(f"An error occurred: Page load timed out after 20 seconds for {url}", file=sys.stderr)
        return None
    except WebDriverException as e:
        # Crucial: If the driver dies here (e.g., connection lost), we raise 
        # the exception to the caller for rotation.
        raise e
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return None



# --- Configuration ---
INPUT_DIR = 'data/formatted/'
OUTPUT_DATA_FILE = 'data/data.json'
OUTPUT_ERRORS_FILE = 'data/errors.json'
ARTICLE_LIMIT = 5000  # Default limit for get_article

# --- End Configuration ---
def setup_driver() -> webdriver.Chrome | None:
    """Initializes and configures a NEW persistent headless Chrome driver."""
    print("Setting up NEW persistent Chrome Driver...")
    chrome_options = Options()
    
    # Stability and performance arguments for headless Linux/WSL2
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Removed --single-process and --disable-gpu as per user feedback
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-features=RendererCodeIntegrity")
    
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("Driver successfully initialized.")
        return driver
    except WebDriverException as e:
        print(f"FATAL: WebDriver failed to initialize. Check ChromeDriver/Chrome setup: {e}", file=sys.stderr)
        return None

def process_roundups():
    """
    Manages the driver lifecycle, handles file iteration, and implements driver rotation 
    for resilience against WebDriver crashes.
    """
    
    driver = None # Initialize driver variable
    
    processed_data = []
    errored_paths = []
    
    if not os.path.isdir(INPUT_DIR):
        print(f"Error: Input directory '{INPUT_DIR}' not found.", file=sys.stderr)
        return
        
    json_files = glob(os.path.join(INPUT_DIR, '*.json'))
    if not json_files:
        print(f"No JSON files found in '{INPUT_DIR}'.", file=sys.stderr)
        return
        
    print(f"Found {len(json_files)} JSON files to process.")
    print("-" * 50)
    
    # Try to set up the driver once before starting the main loop
    driver = setup_driver()
    if not driver:
        return

    total_files = len(json_files)
    current_file_index = 0

    try:
        # Use a while loop to control flow, allowing us to retry the same index
        # when a WebDriver crash occurs.
        while current_file_index < total_files:
            file_path = json_files[current_file_index]
            file_name = os.path.basename(file_path)
            print(f"Processing file ({current_file_index + 1}/{total_files}): {file_name}")
            
            try:
                # 1. Load JSON data
                with open(file_path, 'r', encoding='utf-8') as f:
                    roundup = json.load(f)
                
                updated_roundup = roundup.copy()
                story_structure = updated_roundup.get('story', {})
                
                # 2. Iterate through 'left', 'center', and 'right' lists
                for bias_key in ['left', 'center', 'right']:
                    if bias_key in story_structure:
                        new_articles = []
                        
                        # Iterate through the list of URLs for the current bias
                        for url in story_structure[bias_key]:
                            article_text = None
                            
                            # Attempt to fetch the article up to 2 times (initial attempt + 1 retry)
                            for attempt in range(2):
                                
                                # Call the persistent get_article function
                                # If get_article throws a WebDriverException, it will be caught 
                                # by the outer try/except block.
                                article_article_text = get_article(driver, url, limit=ARTICLE_LIMIT)
                                
                                if article_article_text:
                                    print(f"  -> SUCCESS on attempt {attempt + 1}.")
                                    break  # Success, exit retry loop
                                
                                if attempt == 0:
                                    print("  -> Initial fetch failed. Retrying...")
                                    
                            # After the retry loop, check the final outcome
                            if article_article_text:
                                new_articles.append(article_article_text)
                            else:
                                # Failure after all attempts: Use failure message
                                new_articles.append(f"ARTICLE_FETCH_FAILED: {url}")
                                print(f"  -> WARNING: Failed to fetch content for {url} after all attempts. Using failure message.")
                                
                        story_structure[bias_key] = new_articles

                # 3. Add the fully processed roundup to the main data list
                processed_data.append(updated_roundup)
                print(f"File {file_name} processed successfully.")
                
                # CRITICAL: Only increment the index on successful file processing!
                current_file_index += 1 

            except WebDriverException as e:
                # --- DRIVER ROTATION LOGIC ---
                print(f"\nFATAL DRIVER CRASH detected during file {file_name}: {e}", file=sys.stderr)
                print("Attempting to rotate and replace the stale driver...", file=sys.stderr)
                
                # Quit the crashed driver instance
                if driver:
                    driver.quit()
                    
                # Initialize a new driver instance
                driver = setup_driver()
                
                if not driver:
                    print("ERROR: Failed to initialize new driver. Terminating process.", file=sys.stderr)
                    break # Break the while loop if driver setup fails
                
                # DO NOT increment current_file_index. The while loop will restart 
                # processing the currently failing file with the new driver.
                
            except Exception as e:
                # Handle generic file errors (e.g., bad JSON format)
                print(f"ERROR processing {file_name}: {e}. Skipping file.", file=sys.stderr)
                errored_paths.append({"path": file_path, "error": str(e)})
                current_file_index += 1 # Skip to the next file
    
    # --- CRITICAL CLEANUP BLOCK ---
    except KeyboardInterrupt:
        print("\nProcess interrupted by user (Ctrl+C). Performing graceful shutdown...", file=sys.stderr)
        # The finally block will handle the driver quit.
    
    finally:
        # 4. Global Driver Cleanup - Runs regardless of success, failure, or interrupt.
        if driver:
            driver.quit()
            print("\nPersistent Chrome Driver shut down.")

        # 5. Save Results (even on interrupt, save what we have processed so far)
        print("-" * 50)
        print("Saving current progress.")

        # Save successfully processed data
        with open(OUTPUT_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=4)
        print(f"Successfully processed {len(processed_data)} files and saved to {OUTPUT_DATA_FILE}")

        # Save errored paths
        with open(OUTPUT_ERRORS_FILE, 'w', encoding='utf-8') as f:
            json.dump(errored_paths, f, indent=4)
        print(f"Recorded {len(errored_paths)} errors and saved paths to {OUTPUT_ERRORS_FILE}")


if __name__ == '__main__':
    process_roundups()