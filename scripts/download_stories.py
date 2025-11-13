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
        raise WebDriverException(str(e))



# --- Configuration ---
INPUT_DIR = 'data/formatted/'
OUTPUT_DATA_FILE = 'data/data.json'
OUTPUT_ERRORS_FILE = 'data/errors.json'
ARTICLE_LIMIT = 5000  # Default limit for get_article

# --- End Configuration ---
def filename_to_headline(filename: str) -> str:
    """
    Converts a file name (e.g., 'violence-america-shooting.json') 
    into the expected headline format ('Violence America Shooting').
    """
    # 1. Remove extension (.json)
    name_no_ext = os.path.splitext(filename)[0]
    
    # 2. Replace dashes with spaces and capitalize the first letter of each word
    headline_parts = name_no_ext.replace('-', ' ').split()
    
    if not headline_parts:
        return ""
        
    # Capitalize every word as suggested by the example format
    processed_headline = ' '.join(word.capitalize() for word in headline_parts)
    return processed_headline

def setup_driver() -> webdriver.Chrome | None:
    """Initializes and configures a NEW Chrome driver that stays open but can be closed properly."""
    print("Setting up NEW Chrome Driver...")
    chrome_options = Options()
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.media_stream": 2
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.page_load_strategy = 'eager'

    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # These options help with proper shutdown
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("Driver successfully initialized.")
        return driver
    except WebDriverException as e:
        print(f"FATAL: WebDriver failed to initialize. Check ChromeDriver/Chrome setup: {e}", file=sys.stderr)
        return None

def load_existing_data() -> tuple[list, list, set]:
    """
    Loads existing processed data and a set of filenames already attempted, 
    using the headline heuristic as a fallback.
    """
    processed_data = []
    errored_paths = []
    processed_filenames = set()

    # 1. Create a mapping of INPUT FILE NAME -> EXPECTED HEADLINE
    input_file_headline_map = {}
    all_input_files = glob(os.path.join(INPUT_DIR, '*.json'))
    
    for file_path in all_input_files:
        filename = os.path.basename(file_path)
        expected_headline = filename_to_headline(filename)
        input_file_headline_map[filename] = expected_headline

    # 2. Load successfully processed data (OUTPUT_DATA_FILE)
    if os.path.exists(OUTPUT_DATA_FILE):
        try:
            with open(OUTPUT_DATA_FILE, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                
                for item in loaded_data:
                    # Always append item to running list
                    processed_data.append(item)
                    
                    is_file_identified = False

                    if 'headline' in item and not is_file_identified:
                        output_headline = item['headline']
                        
                        # Compare the output headline against all expected input headlines
                        for filename, expected_headline in input_file_headline_map.items():
                            if output_headline.strip() == expected_headline.strip():
                                processed_filenames.add(filename)
                                # Since the headline might not be 100% unique, we rely on 
                                # the assumption that the input files contain distinct headlines.
                                is_file_identified = True
                                break 
                                
            print(f"Resuming: Loaded {len(processed_data)} previously processed files from {OUTPUT_DATA_FILE}.")
        except Exception as e:
            print(f"Warning: Could not load {OUTPUT_DATA_FILE} ({e}). Starting fresh data log.", file=sys.stderr)

    # 3. Load errored paths (OUTPUT_ERRORS_FILE)
    if os.path.exists(OUTPUT_ERRORS_FILE):
        try:
            with open(OUTPUT_ERRORS_FILE, 'r', encoding='utf-8') as f:
                errored_paths = json.load(f)
                for item in errored_paths:
                    # The path contains the filename which we use for tracking
                    filename = os.path.basename(item['path'])
                    processed_filenames.add(filename)
            print(f"Resuming: Loaded {len(errored_paths)} previously errored files from {OUTPUT_ERRORS_FILE}.")
        except Exception as e:
            print(f"Warning: Could not load {OUTPUT_ERRORS_FILE} ({e}). Starting fresh error log.", file=sys.stderr)
            
    # Return all loaded data structures
    return processed_data, errored_paths, processed_filenames

def process_roundups():
    """
    Manages the driver lifecycle, handles file iteration, and implements driver rotation 
    for resilience against WebDriver crashes, and resumes progress from saved files.
    """
    
    # 1. Load existing checkpoint data
    processed_data, errored_paths, processed_filenames = load_existing_data()
    driver = None 

    if not os.path.isdir(INPUT_DIR):
        print(f"Error: Input directory '{INPUT_DIR}' not found.", file=sys.stderr)
        return
        
    all_json_files = glob(os.path.join(INPUT_DIR, '*.json'))
    
    # 2. Filter files to process only those not yet completed
    json_files_to_process = [
        f for f in all_json_files 
        if os.path.basename(f) not in processed_filenames
    ]
    
    if not json_files_to_process:
        print(f"All {len(all_json_files)} files have already been processed or logged as errors. Exiting.")
        return
        
    print(f"Total files found: {len(all_json_files)}")
    print(f"Files to process (unprocessed/new): {len(json_files_to_process)}")
    print("-" * 50)
    
    # Try to set up the driver once before starting the main loop
    driver = setup_driver()
    if not driver:
        return

    total_files_to_process = len(json_files_to_process)
    current_file_index = 0

    try:
        # Use a while loop to control flow, allowing us to retry the same index
        # when a WebDriver crash occurs.
        while current_file_index < total_files_to_process:
            file_path = json_files_to_process[current_file_index]
            file_name = os.path.basename(file_path)
            
            print(f"Processing file ({current_file_index + 1}/{total_files_to_process}): {file_name}")
            
            try:
                # 3. Process the file
                with open(file_path, 'r', encoding='utf-8') as f:
                    roundup = json.load(f)
                
                updated_roundup = roundup.copy()
                story_structure = updated_roundup.get('story', {})
                
                # 4. Iterate through 'left', 'center', and 'right' lists
                for bias_key in ['left', 'center', 'right']:
                    if bias_key in story_structure:
                        new_articles = []
                        
                        for url in story_structure[bias_key]:
                            article_article_text = None
                            for attempt in range(2):
                                
                                # Call the persistent get_article function
                                article_article_text = get_article(driver, url, limit=ARTICLE_LIMIT)
                                
                                if article_article_text:
                                    print(f"  -> SUCCESS on attempt {attempt + 1}.")
                                    break
                                
                                if attempt == 0:
                                    print("  -> Initial fetch failed. Retrying...")
                                    
                            if article_article_text:
                                new_articles.append(article_article_text)
                            else:
                                new_articles.append(f"ARTICLE_FETCH_FAILED: {url}")
                                print(f"  -> WARNING: Failed to fetch content for {url} after all attempts. Using failure message.")
                                
                        story_structure[bias_key] = new_articles

                # 5. Add the fully processed roundup to the main data list
                processed_data.append(updated_roundup)
                print(f"File {file_name} processed successfully.")
                
                # CRITICAL: Only increment the index on successful file processing!
                current_file_index += 1 

            except WebDriverException as e:
                # --- DRIVER ROTATION LOGIC (Fatal Error) ---
                print(f"\nFATAL DRIVER CRASH detected during file {file_name}: {e}", file=sys.stderr)
                print("Attempting to rotate and replace the stale driver...", file=sys.stderr)
                
                if driver:
                    driver.quit()
                    
                driver = setup_driver()
                
                if not driver:
                    print("ERROR: Failed to initialize new driver. Terminating process.", file=sys.stderr)
                    break 
                
                # DO NOT increment current_file_index. Retry the current file with the new driver.
                
            except Exception as e:
                # 6. Handle generic file errors (e.g., bad JSON format)
                print(f"ERROR processing {file_name}: {e}. Skipping file.", file=sys.stderr)
                # Ensure the file is logged as errored so we don't try it again next time
                errored_paths.append({"path": file_path, "error": str(e)})
                # Log the file name as processed/errored to prevent immediate retry on next run
                processed_filenames.add(file_name) 
                current_file_index += 1 # Skip to the next file
    
    # --- CRITICAL CLEANUP BLOCK ---
    except KeyboardInterrupt:
        print("\nProcess interrupted by user (Ctrl+C). Performing graceful shutdown...", file=sys.stderr)
    
    finally:
        # 7. Global Driver Cleanup 
        if driver:
            driver.quit()
            print("\nPersistent Chrome Driver shut down.")

        # 8. Save Results (save all cumulative data)
        print("-" * 50)
        print("Saving cumulative results.")

        with open(OUTPUT_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=4)
        print(f"Saved {len(processed_data)} total processed files to {OUTPUT_DATA_FILE}")

        with open(OUTPUT_ERRORS_FILE, 'w', encoding='utf-8') as f:
            json.dump(errored_paths, f, indent=4)
        print(f"Recorded {len(errored_paths)} total errors and saved paths to {OUTPUT_ERRORS_FILE}")

if __name__ == '__main__':
    process_roundups()