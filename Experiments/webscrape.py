import requests
import bs4
import typing

ALLSIDES = 'http://www.allsides.com'
HEADLINES = '/headline-roundups'
def get_html(url:str):
    # use header to mimic a browser visit
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/',
        'Connection': 'keep-alive'
    }

    with requests.Session() as session:
        session.headers.update(headers)
        try:
            r = session.get(url)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None

    soup = bs4.BeautifulSoup(r.text, 'html.parser')
    return soup

def get_roundup_headlines(soup:bs4.BeautifulSoup):
    table = soup.find('table', class_='views-table')
    if not isinstance(table, bs4.element.Tag):
        print("Invalid table: ", table)
        return []

    rows:bs4.element.ResultSet = table.find_all('tr')

    headlines = []
    
    for row in rows:
        element = row.find(['td', 'th'])
        if not isinstance(element, bs4.element.Tag):
            continue

        content = element.find('a')
        if not isinstance(content, bs4.element.Tag):
            continue

        href = content.get('href')
        headlines.append(str(href))
    return headlines

def get_headline_description(soup:bs4.BeautifulSoup):
    description_div = soup.find('div', class_='story-id-page-description')
    if not isinstance(description_div, bs4.element.Tag):
        return ""
    description = description_div.get_text()
    return description

def get_left_center_right(soup:bs4.BeautifulSoup):

    def extract_link(div:bs4.element.Tag):
        a_tag = div.find('a')
        if not isinstance(a_tag, bs4.element.Tag):
            return ''
        href = a_tag.get('href')
        return str(href)

    left = soup.find('div', class_=['news-item left'])
    if isinstance(left, bs4.element.Tag):
        left = extract_link(left)
    center = soup.find('div', class_=['news-item center'])
    if isinstance(center, bs4.element.Tag):
        center = extract_link(center)
    right = soup.find('div', class_=['news-item right'])
    if isinstance(right, bs4.element.Tag):
        right = extract_link(right)

    return str(left), str(center), str(right)

def join_text_body(soup:bs4.BeautifulSoup):
    body_div = soup.find_all('p')
    if not isinstance(body_div, bs4.element.ResultSet):
        return ""
    body = "\n".join([p.get_text() for p in body_div if isinstance(p, bs4.element.Tag)])
    return body

if __name__ == '__main__':
    soup = get_html(ALLSIDES + HEADLINES)
    if not soup:
        exit(1)
    head = get_roundup_headlines(soup)

    for headline in head:
        headline_content = get_html(ALLSIDES + headline)
        if not headline_content:
            break
        left, center, right = get_left_center_right(headline_content)
        print("Left: ", left)
        print("Center: ", center)
        print("Right: ", right)
        description = get_headline_description(headline_content)

        left_soup = get_html(left) if left else None
        center_soup = get_html(center) if center else None
        right_soup = get_html(right) if right else None
        if left_soup:
            left_body = join_text_body(left_soup)
            print("\n\nLeft Body: ", left_body)
        if center_soup:
            center_body = join_text_body(center_soup)
            print("\n\nCenter Body: ", center_body)
        if right_soup:
            right_body = join_text_body(right_soup)
            print("\n\nRight Body: ", right_body)
        break
