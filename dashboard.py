#!/usr/bin/env python3
"""
Dashboard Web pour Email → WordPress Pipeline
Configuration, preview emails, génération articles avec notifications temps réel
"""

import os
import json
import email
import threading
from datetime import datetime
from email.header import decode_header
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv, set_key
from imapclient import IMAPClient
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from langdetect import detect, LangDetectException
from anthropic import Anthropic
import requests
from requests.auth import HTTPBasicAuth

# Load environment
load_dotenv('config.env')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wordpress-article-maker-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Paths
CONFIG_FILE = Path(__file__).parent / 'config.env'
PROCESSED_FILE = Path(__file__).parent / 'processed_emails.json'
PENDING_FILE = Path(__file__).parent / 'pending_articles.json'
PUBLISHED_FILE = Path(__file__).parent / 'published_articles.json'
PROMPT_FILE = Path(__file__).parent / 'prompt_config.json'

# Cache for emails
email_cache = []
pending_articles = {}
published_articles = []

# Email classification - spam/promo keywords to EXCLUDE
SPAM_KEYWORDS = [
    # Promotions
    'promo', 'promotion', 'soldes', 'réduction', 'discount', 'offre spéciale',
    'code promo', 'bon plan', 'vente flash', 'black friday', 'cyber monday',
    'deal', 'save', 'off', '% off', 'free shipping', 'livraison gratuite',
    'unsubscribe', 'se désabonner', 'désinscrire', 'opt-out',
    # Marketing
    'newsletter', 'weekly digest', 'daily digest', 'recap hebdo',
    'votre commande', 'your order', 'order confirmation', 'confirmation de commande',
    'tracking', 'suivi de colis', 'shipment', 'expédition',
    # Social/notifications
    'liked your', 'commented on', 'mentioned you', 'tagged you',
    'new follower', 'nouveau follower', 'connection request',
    'password reset', 'réinitialisation', 'verify your email', 'vérifiez',
    'security alert', 'alerte de sécurité', 'new sign-in', 'nouvelle connexion',
    # Spam patterns
    'click here', 'cliquez ici', 'act now', 'limited time', 'temps limité',
    'congratulations', 'félicitations', 'you won', 'vous avez gagné',
    'urgent', 'important update', 'action required',
]

# Spam sender domains to EXCLUDE
SPAM_DOMAINS = [
    'noreply', 'no-reply', 'notifications', 'newsletter', 'marketing',
    'promo', 'deals', 'offers', 'support', 'billing', 'account',
    'mailer', 'mailchimp', 'sendgrid', 'amazonses', 'postmaster',
    'facebookmail', 'linkedin', 'twitter', 'instagram', 'tiktok',
    'spotify', 'netflix', 'apple', 'google', 'microsoft', 'amazon',
    'paypal', 'stripe', 'shopify', 'aliexpress', 'wish', 'shein',
]

# Press release keywords to INCLUDE (positive signals)
PRESS_KEYWORDS = [
    # French
    'communiqué de presse', 'communiqué', 'cp:', '[cp]', 
    'annonce officielle', 'lancement', 'inauguration',
    'partenariat', 'acquisition', 'fusion', 'levée de fonds',
    'nomination', 'nommé', 'rejoint', 'nouveau directeur', 'nouveau pdg',
    'étude', 'rapport', 'baromètre', 'enquête', 'sondage',
    'innovation', 'brevet', 'r&d', 'recherche',
    # English
    'press release', 'media release', 'news release', 'pr:',
    'announces', 'announcement', 'launches', 'unveils',
    'partnership', 'acquisition', 'merger', 'funding round',
    'appoints', 'names', 'joins as', 'new ceo', 'new cto',
    'study', 'report', 'survey', 'research',
]

# Trusted press/media domains (always interesting)
TRUSTED_DOMAINS = [
    'presse', 'press', 'media', 'rp@', 'pr@', 'communication',
    'agence', 'agency', 'relations-publiques', 'publicrelations',
]


def classify_email(subject: str, content: str, sender_email: str) -> bool:
    """
    Smart email classification to detect real press releases.
    Returns True if email is likely a press release, False otherwise.
    """
    subject_lower = subject.lower()
    content_lower = content.lower()[:1000]  # Check first 1000 chars
    sender_lower = sender_email.lower()
    
    # Minimum content length
    if len(content) < 300:
        return False
    
    # Check for spam/promo keywords (EXCLUDE)
    spam_score = 0
    for kw in SPAM_KEYWORDS:
        if kw in subject_lower:
            spam_score += 3  # Subject match = stronger signal
        if kw in content_lower:
            spam_score += 1
    
    # Check sender domain for spam patterns
    for domain in SPAM_DOMAINS:
        if domain in sender_lower:
            spam_score += 5
    
    # If high spam score, reject
    if spam_score >= 5:
        return False
    
    # Check for press release keywords (INCLUDE)
    press_score = 0
    for kw in PRESS_KEYWORDS:
        if kw in subject_lower:
            press_score += 4  # Subject match = stronger signal
        if kw in content_lower:
            press_score += 2
    
    # Check for trusted sender domains
    for domain in TRUSTED_DOMAINS:
        if domain in sender_lower:
            press_score += 5
    
    # Content quality signals
    word_count = len(content.split())
    if 300 <= word_count <= 2000:  # Typical press release length
        press_score += 2
    
    # Has quotes (press releases often have quotes)
    if '"' in content or '«' in content:
        press_score += 1
    
    # Has contact info pattern
    if 'contact' in content_lower and ('@' in content or 'tel' in content_lower):
        press_score += 2
    
    # Decision: press_score must be positive and higher than spam_score
    return press_score >= 4 and press_score > spam_score


def load_config():
    """Load current configuration."""
    load_dotenv('config.env', override=True)
    return {
        'imap_host': os.getenv('IMAP_HOST', 'imap.gmail.com'),
        'imap_email': os.getenv('IMAP_EMAIL', ''),
        'imap_password': os.getenv('IMAP_PASSWORD', ''),
        'wp_url': os.getenv('WP_URL', ''),
        'wp_user': os.getenv('WP_USER', ''),
        'wp_app_password': os.getenv('WP_APP_PASSWORD', ''),
        'anthropic_api_key': os.getenv('ANTHROPIC_API_KEY', ''),
        'check_interval': os.getenv('CHECK_INTERVAL', '300'),
        'target_lang': os.getenv('TARGET_LANG', 'fr'),
        'max_emails_per_cycle': os.getenv('MAX_EMAILS_PER_CYCLE', '5'),
        'auto_publish': os.getenv('AUTO_PUBLISH', 'false'),
        'filter_sender': os.getenv('FILTER_SENDER', ''),
        'ai_provider': os.getenv('AI_PROVIDER', 'anthropic'),
        'anthropic_model': os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5-20250929'),
        'openai_api_key': os.getenv('OPENAI_API_KEY', ''),
        'openai_model': os.getenv('OPENAI_MODEL', 'gpt-4o'),
        'gemini_api_key': os.getenv('GEMINI_API_KEY', ''),
        'gemini_model': os.getenv('GEMINI_MODEL', 'gemini-1.5-pro'),
        'ollama_url': os.getenv('OLLAMA_URL', 'http://localhost:11434'),
        'ollama_model': os.getenv('OLLAMA_MODEL', 'llama3'),
    }


def save_config(config):
    """Save configuration to file."""
    for key, value in config.items():
        env_key = key.upper()
        set_key(str(CONFIG_FILE), env_key, value)
    load_dotenv('config.env', override=True)


def load_processed_emails():
    """Load set of processed email IDs."""
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE, 'r') as f:
            return set(json.load(f))
    return set()


def load_pending_articles():
    """Load pending articles awaiting approval."""
    global pending_articles
    if PENDING_FILE.exists():
        with open(PENDING_FILE, 'r') as f:
            pending_articles = json.load(f)
    return pending_articles


def save_pending_articles():
    """Save pending articles."""
    with open(PENDING_FILE, 'w') as f:
        json.dump(pending_articles, f, ensure_ascii=False, indent=2)


def load_published_articles():
    """Load published articles history."""
    global published_articles
    if PUBLISHED_FILE.exists():
        with open(PUBLISHED_FILE, 'r') as f:
            published_articles = json.load(f)
    return published_articles


def save_published_article(entry):
    """Add entry to published articles history."""
    global published_articles
    load_published_articles()
    published_articles.insert(0, entry)  # Add at beginning (newest first)
    with open(PUBLISHED_FILE, 'w') as f:
        json.dump(published_articles, f, ensure_ascii=False, indent=2)


def load_prompt_config():
    """Load AI prompt configuration."""
    if PROMPT_FILE.exists():
        with open(PROMPT_FILE, 'r') as f:
            return json.load(f)
    return {"system_prompt": ""}


def save_prompt_config(prompt):
    """Save AI prompt configuration."""
    with open(PROMPT_FILE, 'w') as f:
        json.dump({"system_prompt": prompt}, f, ensure_ascii=False, indent=2)


def call_ai_provider(config: dict, system_prompt: str, user_prompt: str) -> str:
    """Call the configured AI provider and return the response text."""
    provider = config.get('ai_provider', 'anthropic').lower()
    
    if provider == 'anthropic':
        from anthropic import Anthropic
        client = Anthropic(api_key=config['anthropic_api_key'])
        response = client.messages.create(
            model=config.get('anthropic_model', 'claude-sonnet-4-5-20250929'),
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text.strip()
    
    elif provider == 'openai':
        from openai import OpenAI
        client = OpenAI(api_key=config['openai_api_key'])
        response = client.chat.completions.create(
            model=config.get('openai_model', 'gpt-4o'),
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    
    elif provider == 'gemini':
        import google.generativeai as genai
        genai.configure(api_key=config['gemini_api_key'])
        model = genai.GenerativeModel(config.get('gemini_model', 'gemini-1.5-pro'))
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = model.generate_content(full_prompt)
        return response.text.strip()
    
    elif provider == 'ollama':
        ollama_url = config.get('ollama_url', 'http://localhost:11434')
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": config.get('ollama_model', 'llama3'),
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json().get('response', '').strip()
    
    else:
        raise ValueError(f"Unknown AI provider: {provider}")


def decode_email_subject(subject):
    """Decode email subject properly."""
    if subject is None:
        return "Sans sujet"
    if isinstance(subject, bytes):
        subject = subject.decode('utf-8', errors='replace')
    decoded_parts = decode_header(subject)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(encoding or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)


def get_email_body(msg_data):
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


def extract_content(html_body, text_body):
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


def detect_language(text):
    """Detect language of text content."""
    try:
        return detect(text[:500])
    except LangDetectException:
        return 'unknown'


def fetch_emails():
    """Fetch unread emails from IMAP."""
    global email_cache
    config = load_config()
    
    if not config['imap_email'] or not config['imap_password']:
        return []
    
    try:
        with IMAPClient(host=config['imap_host'], ssl=True) as client:
            client.login(config['imap_email'], config['imap_password'])
            client.select_folder('INBOX')
            
            # Search for emails - filter by sender if configured
            filter_sender = config.get('filter_sender', '').strip()
            if filter_sender:
                messages = client.search(['SINCE', '01-Jan-2026', 'FROM', filter_sender])
            else:
                messages = client.search(['SINCE', '01-Jan-2026'])
            processed = load_processed_emails()
            
            emails = []
            for msg_id in messages[-20:]:  # Get last 20 (most recent)
                if str(msg_id) in processed:
                    continue
                    
                msg_data = client.fetch([msg_id], ['BODY[]', 'ENVELOPE', 'INTERNALDATE'])[msg_id]
                envelope = msg_data[b'ENVELOPE']
                date = msg_data[b'INTERNALDATE']
                
                subject = decode_email_subject(envelope.subject)
                sender = envelope.from_[0] if envelope.from_ else None
                sender_email = f"{sender.mailbox.decode()}@{sender.host.decode()}" if sender else "Unknown"
                sender_name = sender.name.decode() if sender and sender.name else sender_email
                
                html_body, text_body = get_email_body(msg_data)
                markdown = extract_content(html_body, text_body)
                lang = detect_language(markdown)
                
                # All emails from trusted sender are interesting
                is_interesting = True
                
                emails.append({
                    'id': str(msg_id),
                    'subject': subject,
                    'sender_name': sender_name,
                    'sender_email': sender_email,
                    'date': date.strftime('%Y-%m-%d %H:%M'),
                    'preview': markdown[:300] + '...' if len(markdown) > 300 else markdown,
                    'content': markdown,
                    'language': lang,
                    'is_interesting': is_interesting,
                    'word_count': len(markdown.split())
                })
            
            # Sort by date (newest first)
            emails.sort(key=lambda x: x['date'], reverse=True)
            email_cache = emails
            return emails
            
    except Exception as e:
        socketio.emit('notification', {
            'type': 'error',
            'message': f'Erreur IMAP: {str(e)}'
        })
        return []


def generate_article_preview(email_id):
    """Generate article preview using Claude."""
    config = load_config()
    
    # Find email in cache
    email_data = next((e for e in email_cache if e['id'] == email_id), None)
    if not email_data:
        return None
    
    target_lang = config['target_lang']
    detected_lang = email_data['language']
    
    # Load custom prompt from config
    prompt_config = load_prompt_config()
    system_prompt = prompt_config.get('system_prompt', '')

    translation_instruction = f"Traduis d'abord en {target_lang} puis " if detected_lang != target_lang else ""
    
    user_prompt = f"""Contenu source (langue: {detected_lang}) :

{email_data['content'][:4000]}

{translation_instruction}Crée l'article."""

    try:
        response_text = call_ai_provider(config, system_prompt, user_prompt)
        
        # Clean response
        if response_text.startswith('```'):
            response_text = response_text.split('\n', 1)[1]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
        
        article = json.loads(response_text)
        article['email_id'] = email_id
        article['email_subject'] = email_data['subject']
        article['generated_at'] = datetime.now().isoformat()
        
        # Store in pending
        pending_articles[email_id] = article
        save_pending_articles()
        
        return article
        
    except Exception as e:
        socketio.emit('notification', {
            'type': 'error',
            'message': f'Erreur génération: {str(e)}'
        })
        return None


def publish_article(email_id):
    """Publish pending article to WordPress."""
    config = load_config()
    load_pending_articles()  # Reload from file
    
    if email_id not in pending_articles:
        return False, f"Article non trouvé (ID: {email_id})"
    
    article = pending_articles[email_id]
    
    try:
        # Ensure content is properly formatted
        content = article.get("content", "")
        if not content:
            return False, "Contenu de l'article vide"
        
        wp_post = {
            "title": article["title"],
            "content": content,
            "excerpt": article.get("excerpt", ""),
            "status": "draft",
            "format": "standard"
        }
        
        print(f"Publishing to WordPress: {article['title']}")
        print(f"Content length: {len(content)} chars")
        
        response = requests.post(
            f"{config['wp_url']}/wp-json/wp/v2/posts",
            json=wp_post,
            auth=HTTPBasicAuth(config['wp_user'], config['wp_app_password']),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=30
        )
        response.raise_for_status()
        
        post_data = response.json()
        post_id = post_data.get('id')
        
        # Mark as processed
        processed = load_processed_emails()
        processed.add(email_id)
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(list(processed), f)
        
        # Save to published history
        published_entry = {
            'post_id': post_id,
            'title': article['title'],
            'email_subject': article.get('email_subject', ''),
            'published_at': datetime.now().isoformat(),
            'wp_url': f"{config['wp_url']}/?p={post_id}"
        }
        save_published_article(published_entry)
        
        # Remove from pending
        del pending_articles[email_id]
        save_pending_articles()
        
        return True, post_id
        
    except Exception as e:
        return False, str(e)


# Routes
@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'GET':
        config = load_config()
        # Mask sensitive data
        if config['imap_password']:
            config['imap_password'] = '••••••••'
        if config['wp_app_password']:
            config['wp_app_password'] = '••••••••'
        if config['anthropic_api_key']:
            config['anthropic_api_key'] = config['anthropic_api_key'][:10] + '••••••••'
        return jsonify(config)
    else:
        data = request.json
        save_config(data)
        socketio.emit('notification', {
            'type': 'success',
            'message': 'Configuration sauvegardée'
        })
        return jsonify({'status': 'ok'})


@app.route('/api/emails')
def api_emails():
    emails = fetch_emails()
    return jsonify(emails)


@app.route('/api/emails/<email_id>')
def api_email_detail(email_id):
    email_data = next((e for e in email_cache if e['id'] == email_id), None)
    if email_data:
        return jsonify(email_data)
    return jsonify({'error': 'Email not found'}), 404


@app.route('/api/generate/<email_id>', methods=['POST'])
def api_generate(email_id):
    socketio.emit('notification', {
        'type': 'info',
        'message': 'Génération de l\'article en cours...'
    })
    
    article = generate_article_preview(email_id)
    if article:
        socketio.emit('notification', {
            'type': 'success',
            'message': f'Article généré: {article["title"]}'
        })
        socketio.emit('article_generated', article)
        return jsonify(article)
    return jsonify({'error': 'Generation failed'}), 500


@app.route('/api/publish/<email_id>', methods=['POST'])
def api_publish(email_id):
    success, result = publish_article(email_id)
    if success:
        socketio.emit('notification', {
            'type': 'success',
            'message': f'Article publié en draft (ID: {result})'
        })
        return jsonify({'status': 'ok', 'post_id': result})
    return jsonify({'error': result}), 500


@app.route('/api/pending')
def api_pending():
    load_pending_articles()
    return jsonify(list(pending_articles.values()))


@app.route('/api/pending/<email_id>', methods=['DELETE'])
def api_delete_pending(email_id):
    if email_id in pending_articles:
        del pending_articles[email_id]
        save_pending_articles()
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/published')
def api_published():
    """Get published articles history."""
    load_published_articles()
    return jsonify(published_articles)


@app.route('/api/prompt', methods=['GET', 'POST'])
def api_prompt():
    """Get or update AI prompt configuration."""
    if request.method == 'GET':
        config = load_prompt_config()
        return jsonify(config)
    else:
        data = request.json
        save_prompt_config(data.get('system_prompt', ''))
        socketio.emit('notification', {
            'type': 'success',
            'message': 'Prompt IA sauvegardé'
        })
        return jsonify({'status': 'ok'})


@app.route('/api/test-connection', methods=['POST'])
def api_test_connection():
    config = load_config()
    results = {'imap': False, 'wordpress': False, 'anthropic': False}
    
    # Test IMAP
    try:
        with IMAPClient(host=config['imap_host'], ssl=True) as client:
            client.login(config['imap_email'], config['imap_password'])
            results['imap'] = True
    except Exception as e:
        results['imap_error'] = str(e)
    
    # Test WordPress
    try:
        response = requests.get(
            f"{config['wp_url']}/wp-json/wp/v2/posts",
            auth=HTTPBasicAuth(config['wp_user'], config['wp_app_password']),
            timeout=10
        )
        results['wordpress'] = response.status_code == 200
    except Exception as e:
        results['wordpress_error'] = str(e)
    
    # Test Anthropic
    try:
        client = Anthropic(api_key=config['anthropic_api_key'])
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        results['anthropic'] = True
    except Exception as e:
        results['anthropic_error'] = str(e)
    
    return jsonify(results)


# SocketIO events
@socketio.on('connect')
def handle_connect():
    emit('notification', {
        'type': 'info',
        'message': 'Connecté au dashboard'
    })


@socketio.on('refresh_emails')
def handle_refresh():
    emails = fetch_emails()
    emit('emails_updated', emails)
    interesting = [e for e in emails if e['is_interesting']]
    if interesting:
        emit('notification', {
            'type': 'info',
            'message': f'{len(interesting)} email(s) intéressant(s) détecté(s)'
        })


if __name__ == '__main__':
    load_pending_articles()
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)
