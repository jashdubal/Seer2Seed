import requests
import xml.etree.ElementTree as ET
from operator import itemgetter
import os
from dotenv import load_dotenv
import logging
import sys
from urllib.parse import quote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get Jackett configuration from environment variables
JACKETT_URL = os.getenv("JACKETT_URL")
API_KEY = os.getenv("JACKETT_API_KEY")
INDEXERS = "all"  # Use "all" or specify comma-separated indexer IDs

# Movie details from your file
title = "Batman Begins"
year = 2005

def search_movie(query, year=None, limit=100):
    """Search for movie torrents using Jackett's Torznab API"""
    url = f"{JACKETT_URL}/api/v2.0/indexers/{INDEXERS}/results/torznab/api"
    
    # Build query parameters according to Jackett documentation
    params = {
        "apikey": API_KEY,
        "t": "movie",  # Search type: movie
        "q": query,    # Search query
        "limit": limit # Maximum number of results
    }
    
    # Add year if provided
    if year:
        params["year"] = year
    
    logger.info(f"Searching with params: {params}")
    logger.info(f"Request URL: {url}?apikey=HIDDEN&{('&'.join([f'{k}={v}' for k, v in params.items() if k != 'apikey']))}")
    
    try:
        response = requests.get(url, params=params)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Error response: {response.text}")
            return []
            
        # Parse XML response
        root = ET.fromstring(response.content)
        
        # The namespace used in Torznab responses
        ns = {'torznab': 'http://torznab.com/schemas/2015/feed'}
        
        results = []
        # Process each item in the response
        for item in root.findall('.//item'):
            result = {
                'title': item.find('title').text if item.find('title') is not None else 'Unknown',
                'link': item.find('link').text if item.find('link') is not None else '',
                'size': 0,
                'seeders': 0,
                'leechers': 0,
                'pubDate': item.find('pubDate').text if item.find('pubDate') is not None else '',
            }
            
            # Extract torznab attributes (size, seeders, leechers)
            for attr in item.findall('./torznab:attr', ns):
                name = attr.get('name')
                value = attr.get('value')
                
                if name == 'size':
                    result['size'] = int(value)
                elif name == 'seeders':
                    result['seeders'] = int(value)
                elif name == 'peers':
                    result['leechers'] = int(value) - result['seeders']
                elif name == 'downloadvolumefactor':
                    result['downloadFactor'] = float(value)
                elif name == 'uploadvolumefactor':
                    result['uploadFactor'] = float(value)
            
            # Format size for display
            result['formatted_size'] = format_size(result['size'])
            results.append(result)
        
        logger.info(f"Found {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Error searching Jackett: {e}", exc_info=True)
        return []

def format_size(size_bytes):
    """Format bytes to human-readable size"""
    if size_bytes == 0:
        return "0B"
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {size_names[i]}"

def main():
    logger.info(f"Starting search for movie: {title} ({year})")
    
    # Search for the movie title without year
    logger.info(f"Searching for: {title}")
    results1 = search_movie(title)
    
    # Search for the movie title with year
    logger.info(f"Searching for: {title} with year {year}")
    results2 = search_movie(title, year=year)
    
    # Combine results
    all_results = results1 + results2
    logger.info(f"Total combined results: {len(all_results)}")
    
    if not all_results:
        logger.warning("No results found!")
        return
    
    # Sort by number of seeders (descending)
    sorted_results = sorted(all_results, key=itemgetter('seeders'), reverse=True)
    
    # Display top 5 results
    print("\nTop 5 torrents with most seeds:")
    for i, result in enumerate(sorted_results[:5], 1):
        print(f"{i}. {result['title']}")
        print(f"   Size: {result['formatted_size']} | Seeds: {result['seeders']} | Leechers: {result['leechers']}")
        print(f"   Link: {result['link']}")
        print()

if __name__ == "__main__":
    main()







