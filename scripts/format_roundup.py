import os
import json
from bs4 import BeautifulSoup
from glob import glob

# --- Configuration ---
INPUT_DIR = 'data/roundups_raw'
OUTPUT_DIR = 'data/formatted/roundups_json'
# --- End Configuration ---

def format_filename_as_headline(filename: str) -> str:
    """
    Converts a file name (e.g., 'a-sample-file.html') into a title case headline
    (e.g., 'A Sample File').
    """
    base_name = os.path.splitext(filename)[0]
    return ' '.join(word.capitalize() for word in base_name.split('-'))

def extract_text_between(soup, start_text: str, end_text: str) -> str:
    """
    Extracts and cleans all text content between two specific headings.
    """
    start_tag = soup.find(lambda tag: tag.name in ['h2', 'h3'] and start_text in tag.get_text(strip=True))
    end_tag = soup.find(lambda tag: tag.name in ['h2', 'h3'] and end_text in tag.get_text(strip=True))

    if not start_tag or not end_tag:
        return ""

    content_text = []
    current_tag = start_tag.next_sibling
    
    while current_tag and current_tag != end_tag:
        # Check if the tag is an element and not just a NavigableString
        if current_tag.name: 
            content_text.append(current_tag.get_text(strip=True))
        current_tag = current_tag.next_sibling

    # Combine all pieces of text and clean up extra whitespace
    return ' '.join(content_text).strip()

def extract_story_links(soup) -> dict:
    """
    Extracts the story links categorized by 'left', 'center', and 'right' bias.
    """
    story = {
        "left": [],
        "center": [],
        "right": []
    }
    
    # The 'Featured Coverage of this Story' marks the start of the relevant section
    start_heading = soup.find(lambda tag: tag.name in ['h2', 'h3'] and "Featured Coverage of this Story" in tag.get_text(strip=True))
    
    if not start_heading:
        return story

    # Find the main container (usually a <div>) that holds the story items
    # We look for the next sibling of the start_heading which contains the links
    story_container = start_heading.find_next_sibling()

    if not story_container:
        return story

    # Find all divs that define the bias (Right, Left, Center)
    for bias_div in story_container.find_all('div', class_=lambda c: c and 'global-bias-label' in c):
        bias_text = bias_div.get_text(strip=True).replace('From the ', '').lower()
        
        # Determine the key ('right', 'left', or 'center')
        key = None
        if 'right' in bias_text:
            key = 'right'
        elif 'left' in bias_text:
            key = 'left'
        elif 'center' in bias_text:
            key = 'center'
            
        if key:
            # The link (<a> tag) is usually the next sibling after the bias-div's parent
            # or a direct sibling in the structure
            link_tag = bias_div.find_next_sibling('a', href=lambda h: h and h.startswith('https'))
            
            if link_tag and link_tag.get('href'):
                story[key].append(link_tag['href'])

    return story

def process_file(file_path: str):
    """
    Main function to process a single HTML file and convert it to JSON structure.
    """
    file_name = os.path.basename(file_path)
    print(f"Processing: {file_name}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Headline
    headline = format_filename_as_headline(file_name)

    # 2. Summary
    summary = extract_text_between(
        soup, 
        start_text="Summary from the AllSides News Team", 
        end_text="Featured Coverage of this Story"
    )

    # 3. Story Links
    story_links = extract_story_links(soup)

    # Final JSON structure
    roundup_data = {
        "headline": headline,
        "summary": summary,
        "story": story_links
    }

    # Save to JSON
    output_filename = os.path.splitext(file_name)[0] + '.json'
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(roundup_data, f, indent=4)
        
    print(f"  -> Saved to: {output_path}")

def main():
    """
    Initializes directories and processes all HTML files.
    """
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory created/verified: {OUTPUT_DIR}/")

    # Get a list of all HTML files in the input directory
    html_files = glob(os.path.join(INPUT_DIR, '*.html'))
    
    if not html_files:
        print(f"Error: No HTML files found in the directory '{INPUT_DIR}'.")
        print("Please ensure you have run 'pip install beautifulsoup4' and that your raw files are in the correct folder.")
        return

    print(f"Found {len(html_files)} files to process.")
    print("-" * 30)

    for file_path in html_files:
        try:
            process_file(file_path)
        except Exception as e:
            print(f"An error occurred while processing {file_path}: {e}")

    print("-" * 30)
    print("Processing complete.")

if __name__ == '__main__':
    main()