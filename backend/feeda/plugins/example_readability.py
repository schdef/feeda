"""Example plugin: extracts clean article summary if missing."""
from bs4 import BeautifulSoup

def register(hooks):
    hooks.register('process_article', extract_readable_content)

async def extract_readable_content(article: dict):
    if not article.get('summary') and article.get('content'):
        soup = BeautifulSoup(article['content'], 'html.parser')
        article['summary'] = soup.get_text(separator=' ', strip=True)[:250]
