import requests
from bs4 import BeautifulSoup
import sqlite3  # For database interaction
import time

def fetch_scripture_data(book_id, chapter_id):
    """Fetches scripture data from BYU's scriptures website.

    Args:
        book_id: The ID of the scripture book (e.g., 302).
        chapter_id: The ID of the chapter (e.g., 1).

    Returns:
        A dictionary containing the chapter information or None if an error occurred.
    """

    url = f"https://scriptures.byu.edu/scriptures/scriptures_ajax/{book_id}/{chapter_id}?verses="
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Save the raw HTML response to a file for inspection------------------------------------------------------------
        # with open(f'scripture_response_{book_id}_{chapter_id}.html', 'w', encoding='utf-8') as f:
        #     f.write(response.text)
        # print(f"Raw HTML saved to scripture_response_{book_id}_{chapter_id}.html")

        # The response will be in HTML.
        soup = BeautifulSoup(response.content, "html.parser")
        
        chapter_info = {}

        # Get the volume (Book of Mormon or Doctrine & Covenants)
        volume_elements = soup.find_all('span', class_='largecrumb')
        for element in volume_elements:
            text = element.get_text().strip().replace('\xa0', ' ')
            if text in ['Old Testament', 'New Testament', 'Book of Mormon', 'Doctrine & Covenants', 'Pearl of Great Price']:
                chapter_info['volume'] = text
                volume_abbrev = element.find_next('span', class_='smallcrumb')
                if volume_abbrev:
                    chapter_info['volume_abbrev'] = volume_abbrev.get_text().strip()
                break

        # Get the book (e.g., Second Nephi, Sections)
        book_elements = soup.find_all('li', class_='acrumb')
        if len(book_elements) >= 3:  # Book is always the third element
            book_element = book_elements[2].find('span', class_='largecrumb')
            if book_element:
                chapter_info['book'] = book_element.get_text().strip().replace('\xa0', ' ')
                book_abbrev = book_elements[2].find('span', class_='smallcrumb')
                if book_abbrev:
                    chapter_info['book_abbrev'] = book_abbrev.get_text().strip()

        # Get the chapter number
        chapter_element = soup.find('div', class_='navheading')
        if chapter_element:
            chapter_info['chapter'] = chapter_element.get_text().replace('CHAPTER ', '').strip()

        # Get verses
        verses_list = []
        verse_elements = soup.find_all('li', class_='versesblock')
        if not verse_elements:  # If no verses block, look for individual verse elements
            verse_elements = soup.find_all('li', id=True)  # Get all li elements with an id
        
        for verse_elem in verse_elements:
            verse_num = verse_elem.find('span', class_='verse')
            verse_text = verse_elem.get_text().strip()
            if verse_num:  # Only process elements that have a verse number
                # Remove the verse number from the beginning of verse_text
                verse_content = verse_text[len(verse_num.get_text()):].strip()
                verses_list.append({
                    'number': verse_num.get_text().strip(),
                    'text': verse_content
                })
        
        chapter_info['verses'] = verses_list

        return chapter_info

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def create_database():
    """Creates the database and table to store scripture data."""
    conn = sqlite3.connect('scriptures.db')
    cursor = conn.cursor()
    
    # First drop the table if it exists
    cursor.execute('DROP TABLE IF EXISTS verses')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verses (
            book_id INTEGER,
            chapter_id INTEGER,
            verse_number INTEGER,
            volume TEXT,
            volume_abbrev TEXT,
            book TEXT,
            book_abbrev TEXT,
            chapter TEXT,
            verse_text TEXT,
            PRIMARY KEY (book_id, chapter_id, verse_number)
        )
    ''')
    conn.commit()
    conn.close()

def store_data_in_database(book_id, chapter_id, data):
    """Stores scripture data in the database."""
    conn = sqlite3.connect('scriptures.db')
    cursor = conn.cursor()

    for verse in data.get('verses', []):
        cursor.execute('''
            INSERT OR REPLACE INTO verses (
                book_id, 
                chapter_id,
                verse_number,
                volume,
                volume_abbrev,
                book,
                book_abbrev,
                chapter,
                verse_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            book_id,
            chapter_id,
            int(verse['number']),
            data.get('volume', ''),
            data.get('volume_abbrev', ''),
            data.get('book', ''),
            data.get('book_abbrev', ''),
            data.get('chapter', ''),
            verse['text']
        ))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Define range of books and chapters to try
    book_id_range = range(101, 410)  # 101 to 410 inclusive
    chapter_id_range = range(1, 200)  # 1 to 200 inclusive

    create_database()
    
    for book_id in book_id_range:
        for chapter_id in chapter_id_range:
            print(f"Attempting book {book_id}, chapter {chapter_id}...")
            data = fetch_scripture_data(book_id, chapter_id)
            
            if data and data.get('verses'):  # Only store if we got valid data with verses
                print(f"Successfully fetched {data.get('book', 'Unknown book')}, Chapter {chapter_id}")
                store_data_in_database(book_id, chapter_id, data)
            else:
                print(f"No data for book {book_id}, chapter {chapter_id} - skipping")

            # Add a small delay to be nice to the server
            time.sleep(1)

print("Scripture fetching complete!")