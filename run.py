#!/usr/bin/env python3
"""
Entry point for WordPress Article Maker
Run: python run.py
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.dashboard import app, socketio, DATA_DIR

# Ensure data directory exists with initial files
DATA_DIR.mkdir(exist_ok=True)

if not (DATA_DIR / 'processed_emails.json').exists():
    (DATA_DIR / 'processed_emails.json').write_text('[]')

if not (DATA_DIR / 'pending_articles.json').exists():
    (DATA_DIR / 'pending_articles.json').write_text('{}')

if not (DATA_DIR / 'published_articles.json').exists():
    (DATA_DIR / 'published_articles.json').write_text('[]')

if not (DATA_DIR / 'prompt_config.json').exists():
    default_prompt = {
        "system_prompt": """Tu es un rédacteur web. Transforme ce communiqué en article WordPress professionnel.
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
    }
    import json
    (DATA_DIR / 'prompt_config.json').write_text(json.dumps(default_prompt, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    print("🚀 WordPress Article Maker")
    print("📍 Dashboard: http://localhost:5050")
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)
