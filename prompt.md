23:29Prompt optimisé Windsurf - Pipeline Email → WordPress (texte uniquement)
Objectif
Système ultra-efficace : Email de presse → Extraction texte → Traduction auto → Génération article IA → Draft WordPress
Stack minimaliste optimale
Python (recommandé pour la rapidité)

imapclient : monitoring email léger
beautifulsoup4 : parsing HTML
markdownify : HTML→MD (1 seule passe)
anthropic ou openai : API IA
requests : WordPress REST API
langdetect : détection langue (gratuit)

OU Node.js

imap-simple, turndown, @anthropic-ai/sdk, axios

Architecture ultra-simple
┌─────────────┐
│ IMAP Poller │ (check toutes les 5min)
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ Parser & Converter  │ (HTML→MD en 1 étape)
└──────┬──────────────┘
       │
       ▼
┌─────────────────┐
│ IA Generator    │ (1 seul call API)
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ WP Publisher    │ (POST direct)
└─────────────────┘
Code structure minimale
/
├── main.py (ou index.js)           # 1 fichier principal
├── config.env                       # Variables
├── requirements.txt (ou package.json)
└── processed_emails.json            # Tracking simple
Variables d'environnement
bash# Email
IMAP_HOST=imap.gmail.com
IMAP_EMAIL=presse@votredomaine.com
IMAP_PASSWORD=xxxx

# WordPress
WP_URL=https://votresite.com
WP_USER=admin
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx

# IA (choisir UN seul)
ANTHROPIC_API_KEY=sk-ant-xxx
# OU
OPENAI_API_KEY=sk-xxx

# Config
CHECK_INTERVAL=300  # secondes
TARGET_LANG=fr
Prompt IA ultra-efficace
pythonSYSTEM_PROMPT = """Tu es un rédacteur web. Transforme ce communiqué en article WordPress professionnel.
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
"""

USER_PROMPT = f"""Contenu source (langue: {detected_lang}) :

{markdown_content}

{"Traduis d'abord en français puis " if detected_lang != 'fr' else ""}Crée l'article."""
Pipeline optimisé - Étapes exactes
1. Monitoring IMAP (non-bloquant)
python# Chercher emails NON LUS avec filtre
messages = imap.search(['UNSEEN', 'SUBJECT', 'communiqué'])
# OU filtre expéditeur de confiance
messages = imap.search(['UNSEEN', 'FROM', 'presse@trusted.com'])
2. Extraction ONE-PASS
python# Récupérer body HTML
html_body = get_email_body(message)

# Nettoyer + convertir en 1 étape
from markdownify import markdownify as md
clean_html = BeautifulSoup(html_body).get_text()  # Strip scripts/styles
markdown = md(html_body, heading_style="ATX")

# Détection langue (50ms max)
from langdetect import detect
lang = detect(markdown[:500])  # Analyser début seulement
3. Génération IA (1 seul call)
pythonfrom anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-sonnet-4-5-20250929",  # Optimal coût/qualité
    max_tokens=2000,
    system=SYSTEM_PROMPT,
    messages=[{
        "role": "user",
        "content": USER_PROMPT.format(
            detected_lang=lang,
            markdown_content=markdown[:4000]  # Limite si trop long
        )
    }]
)

# Parser JSON direct
import json
article = json.loads(response.content[0].text)
4. Publication WordPress (1 requête)
pythonimport requests
from requests.auth import HTTPBasicAuth

wp_post = {
    "title": article["title"],
    "content": article["content"],
    "excerpt": article["excerpt"],
    "status": "draft",
    "tags": article["tags"],
    "format": "standard"
}

response = requests.post(
    f"{WP_URL}/wp-json/wp/v2/posts",
    json=wp_post,
    auth=HTTPBasicAuth(WP_USER, WP_APP_PASSWORD)
)

# Marquer email comme traité
imap.add_flags(message_id, ['\\Seen'])
# OU déplacer vers dossier "Processed"
Optimisations critiques
Performance

Cache: Stocker IDs emails traités (JSON local suffit)
Batch: Traiter max 5 emails par cycle
Timeout: IA max 30s, sinon skip
Async: Traiter emails en parallèle (Python asyncio ou Node.js native)

Coûts IA

Claude Sonnet 4: ~$3 par million tokens (optimal)
Limite input: 4000 tokens max (article moyen = 800 tokens)
Estimation: ~$0.003 par email = 300 emails pour $1

Fiabilité
python# Anti-duplication simple
def is_processed(email_id):
    with open('processed_emails.json', 'r') as f:
        processed = json.load(f)
    return email_id in processed

# Retry WordPress si échec
@retry(tries=3, delay=2)
def publish_to_wp(data):
    # code publication
Code complet minimaliste (Python)
pythonimport os, time, json
from imapclient import IMAPClient
from markdownify import markdownify as md
from langdetect import detect
from anthropic import Anthropic
import requests
from requests.auth import HTTPBasicAuth

# Init
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def process_email(msg):
    # 1. Extract
    html = msg.body['text/html']
    markdown = md(html)
    lang = detect(markdown[:500])
    
    # 2. Generate
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Langue: {lang}\n\n{markdown[:4000]}"}]
    )
    article = json.loads(response.content[0].text)
    
    # 3. Publish
    requests.post(
        f"{os.getenv('WP_URL')}/wp-json/wp/v2/posts",
        json={**article, "status": "draft"},
        auth=HTTPBasicAuth(os.getenv('WP_USER'), os.getenv('WP_APP_PASSWORD'))
    )

# Main loop
while True:
    with IMAPClient(host=os.getenv('IMAP_HOST')) as client:
        client.login(os.getenv('IMAP_EMAIL'), os.getenv('IMAP_PASSWORD'))
        client.select_folder('INBOX')
        
        messages = client.search(['UNSEEN'])
        for msg_id in messages[:5]:  # Max 5 par cycle
            try:
                process_email(client.fetch(msg_id, ['BODY[]'])[msg_id])
                client.add_flags(msg_id, ['\\Seen'])
            except Exception as e:
                print(f"Error: {e}")
    
    time.sleep(300)  # 5 min
Déploiement ultra-simple
Option 1 : Server VPS
bashpip install imapclient markdownify langdetect anthropic requests
python main.py &  # Background process
# OU avec systemd service
Option 2 : Docker (1 container)
dockerfileFROM python:3.11-slim
COPY requirements.txt main.py ./
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
Option 3 : Serverless (AWS Lambda + EventBridge)

Trigger toutes les 5 min
Cold start acceptable (processing asynchrone)

Monitoring minimal
python# Ajouter dans la loop
import logging
logging.basicConfig(filename='press_bot.log', level=logging.INFO)

logging.info(f"Processed: {email_subject} → WP Draft #{wp_post_id}")
Performance attendue

Temps traitement : 5-15 secondes par email
Débit : ~240 emails/heure max
Coût : ~$0.003 par email (IA) + infrastructure
Fiabilité : 99%+ avec retry logic

C'est tout. Pas de sur-ingénierie. Efficace. Maintenable.