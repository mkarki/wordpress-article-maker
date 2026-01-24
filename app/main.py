#!/usr/bin/env python3
"""
Email → WordPress Article Pipeline
Monitors IMAP inbox, extracts press releases, generates articles via Claude, publishes to WordPress.
"""

import os
import time
import json
import logging
import email
from email.header import decode_header
from pathlib import Path

from dotenv import load_dotenv
from imapclient import IMAPClient
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from langdetect import detect, LangDetectException
from anthropic import Anthropic
import requests
from requests.auth import HTTPBasicAuth
from retry import retry

# Load environment variables
load_dotenv('config.env')

# Configuration
IMAP_HOST = os.getenv('IMAP_HOST', 'imap.gmail.com')
IMAP_EMAIL = os.getenv('IMAP_EMAIL')
IMAP_PASSWORD = os.getenv('IMAP_PASSWORD')
WP_URL = os.getenv('WP_URL')
WP_USER = os.getenv('WP_USER')
WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 300))
TARGET_LANG = os.getenv('TARGET_LANG', 'fr')
MAX_EMAILS_PER_CYCLE = int(os.getenv('MAX_EMAILS_PER_CYCLE', 5))

# Paths
PROCESSED_FILE = Path(__file__).parent / 'processed_emails.json'
LOG_FILE = Path(__file__).parent / 'press_bot.log'

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# AI Prompt
SYSTEM_PROMPT = """Tu es un rédacteur web. Transforme ce communiqué en article WordPress professionnel.
Format de sortie JSON strict :
{
  "title": "titre SEO 60 caractères max",
  "content": "HTML propre avec <h2>, <p>, <strong>",
  "excerpt": "résumé 150 caractères",
  "tags": ["tag1", "tag2", "tag3"]
}

Règles :
- Titre accrocheur et clair
- 3-5 paragraphes structurés
- Pas de formules marketing excessives
- Préserve les informations factuelles importantes
- Réponds UNIQUEMENT avec le JSON, sans texte avant ou après"""

# Initialize Anthropic client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


def load_processed_emails() -> set:
    """Load set of processed email IDs."""
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE, 'r') as f:
            return set(json.load(f))
    return set()


def save_processed_email(email_id: str):
    """Add email ID to processed list."""
    processed = load_processed_emails()
    processed.add(email_id)
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(list(processed), f)


def is_processed(email_id: str) -> bool:
    """Check if email was already processed."""
    return email_id in load_processed_emails()


def decode_email_subject(subject) -> str:
    """Decode email subject properly."""
    if subject is None:
        return "Sans sujet"
    decoded_parts = decode_header(subject)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(encoding or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)


def get_email_body(msg_data) -> tuple[str, str]:
    """Extract HTML and text body from email message."""
    html_body = ""
    text_body = ""
    
    if b'BODY[]' in msg_data:
        raw_email = msg_data[b'BODY[]']
        email_message = email.message_from_bytes(raw_email)
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == 'text/html':
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    html_body = payload.decode(charset, errors='replace')
                elif content_type == 'text/plain' and not html_body:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    text_body = payload.decode(charset, errors='replace')
        else:
            content_type = email_message.get_content_type()
            payload = email_message.get_payload(decode=True)
            charset = email_message.get_content_charset() or 'utf-8'
            if content_type == 'text/html':
                html_body = payload.decode(charset, errors='replace')
            else:
                text_body = payload.decode(charset, errors='replace')
    
    return html_body, text_body


def extract_content(html_body: str, text_body: str) -> str:
    """Convert email content to clean markdown."""
    if html_body:
        soup = BeautifulSoup(html_body, 'html.parser')
        for tag in soup(['script', 'style', 'head', 'meta', 'link']):
            tag.decompose()
        markdown = md(str(soup), heading_style="ATX", strip=['img', 'a'])
    else:
        markdown = text_body
    
    lines = [line.strip() for line in markdown.split('\n') if line.strip()]
    return '\n\n'.join(lines)


def detect_language(text: str) -> str:
    """Detect language of text content."""
    try:
        return detect(text[:500])
    except LangDetectException:
        return 'unknown'


def generate_article(markdown_content: str, detected_lang: str) -> dict:
    """Generate WordPress article using Claude."""
    translation_instruction = f"Traduis d'abord en {TARGET_LANG} puis " if detected_lang != TARGET_LANG else ""
    
    user_prompt = f"""Contenu source (langue: {detected_lang}) :

{markdown_content[:4000]}

{translation_instruction}Crée l'article."""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    
    response_text = response.content[0].text.strip()
    if response_text.startswith('```'):
        response_text = response_text.split('\n', 1)[1]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
    
    return json.loads(response_text)


@retry(tries=3, delay=2, logger=logger)
def publish_to_wordpress(article: dict) -> int:
    """Publish article to WordPress as draft."""
    wp_post = {
        "title": article["title"],
        "content": article["content"],
        "excerpt": article["excerpt"],
        "status": "draft",
        "format": "standard"
    }
    
    response = requests.post(
        f"{WP_URL}/wp-json/wp/v2/posts",
        json=wp_post,
        auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD),
        timeout=30
    )
    response.raise_for_status()
    
    post_data = response.json()
    post_id = post_data.get('id')
    
    if article.get('tags') and post_id:
        create_and_assign_tags(post_id, article['tags'])
    
    return post_id


def create_and_assign_tags(post_id: int, tag_names: list):
    """Create tags if needed and assign to post."""
    tag_ids = []
    
    for tag_name in tag_names:
        search_response = requests.get(
            f"{WP_URL}/wp-json/wp/v2/tags",
            params={"search": tag_name},
            auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD),
            timeout=10
        )
        
        if search_response.ok and search_response.json():
            tag_ids.append(search_response.json()[0]['id'])
        else:
            create_response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/tags",
                json={"name": tag_name},
                auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD),
                timeout=10
            )
            if create_response.ok:
                tag_ids.append(create_response.json()['id'])
    
    if tag_ids:
        requests.post(
            f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
            json={"tags": tag_ids},
            auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD),
            timeout=10
        )


def process_email(client: IMAPClient, msg_id: int) -> bool:
    """Process a single email: extract, generate, publish."""
    email_uid = str(msg_id)
    
    if is_processed(email_uid):
        logger.info(f"Email {msg_id} already processed, skipping")
        return False
    
    msg_data = client.fetch([msg_id], ['BODY[]', 'ENVELOPE'])[msg_id]
    envelope = msg_data[b'ENVELOPE']
    subject = decode_email_subject(envelope.subject.decode() if envelope.subject else None)
    
    logger.info(f"Processing email: {subject}")
    
    html_body, text_body = get_email_body(msg_data)
    
    if not html_body and not text_body:
        logger.warning(f"No content found in email: {subject}")
        return False
    
    markdown_content = extract_content(html_body, text_body)
    
    if len(markdown_content) < 100:
        logger.warning(f"Email content too short: {subject}")
        return False
    
    detected_lang = detect_language(markdown_content)
    logger.info(f"Detected language: {detected_lang}")
    
    article = generate_article(markdown_content, detected_lang)
    logger.info(f"Generated article: {article['title']}")
    
    post_id = publish_to_wordpress(article)
    logger.info(f"Published to WordPress as draft #{post_id}")
    
    save_processed_email(email_uid)
    client.add_flags([msg_id], ['\\Seen'])
    
    logger.info(f"Processed: {subject} → WP Draft #{post_id}")
    return True


def run_pipeline():
    """Main pipeline loop."""
    logger.info("Starting Email → WordPress pipeline")
    logger.info(f"Monitoring: {IMAP_EMAIL}")
    logger.info(f"Publishing to: {WP_URL}")
    logger.info(f"Check interval: {CHECK_INTERVAL}s")
    
    while True:
        try:
            with IMAPClient(host=IMAP_HOST, ssl=True) as client:
                client.login(IMAP_EMAIL, IMAP_PASSWORD)
                client.select_folder('INBOX')
                
                messages = client.search(['UNSEEN'])
                logger.info(f"Found {len(messages)} unread emails")
                
                processed_count = 0
                for msg_id in messages[:MAX_EMAILS_PER_CYCLE]:
                    try:
                        if process_email(client, msg_id):
                            processed_count += 1
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse AI response for email {msg_id}: {e}")
                    except requests.RequestException as e:
                        logger.error(f"WordPress API error for email {msg_id}: {e}")
                    except Exception as e:
                        logger.error(f"Error processing email {msg_id}: {e}")
                
                if processed_count > 0:
                    logger.info(f"Processed {processed_count} emails this cycle")
                    
        except Exception as e:
            logger.error(f"IMAP connection error: {e}")
        
        logger.info(f"Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_pipeline()
