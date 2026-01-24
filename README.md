# WordPress Article Maker

🚀 Système automatisé qui transforme les emails (communiqués de presse) en articles WordPress via IA.

![Dashboard](https://img.shields.io/badge/Dashboard-Flask-blue) ![AI](https://img.shields.io/badge/AI-Claude%20Sonnet-purple) ![WordPress](https://img.shields.io/badge/CMS-WordPress-green)

## ✨ Fonctionnalités

- **📧 Monitoring IMAP** - Récupération automatique des emails
- **🤖 Génération IA** - Transformation en articles via Claude Sonnet
- **📝 Preview** - Prévisualisation avant publication
- **🚀 Publication WordPress** - Envoi direct en brouillon
- **⚙️ Dashboard Web** - Interface de configuration complète
- **🔄 Mode automatique** - Workflow complet sans intervention

## 🏗️ Architecture

```
┌─────────────┐
│ IMAP Poller │ → Récupération emails
└──────┬──────┘
       ▼
┌─────────────────────┐
│ Parser & Converter  │ → HTML → Markdown
└──────┬──────────────┘
       ▼
┌─────────────────┐
│ Claude AI       │ → Génération article
└──────┬──────────┘
       ▼
┌─────────────────┐
│ WordPress API   │ → Publication draft
└─────────────────┘
```

## 📦 Installation

```bash
# Cloner le repo
git clone https://github.com/mkarki/wordpress-article-maker.git
cd wordpress-article-maker

# Installer les dépendances
pip install -r requirements.txt

# Copier et configurer
cp config.env.example config.env
# Éditer config.env avec vos identifiants
```

## ⚙️ Configuration

Éditer `config.env` :

```bash
# Email IMAP (Gmail nécessite un App Password)
IMAP_HOST=imap.gmail.com
IMAP_EMAIL=votre-email@gmail.com
IMAP_PASSWORD=xxxx xxxx xxxx xxxx

# WordPress (créer un Application Password dans WP Admin)
WP_URL=https://votre-site.com
WP_USER=votre-username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxx

# Options
CHECK_INTERVAL=300          # Intervalle en secondes
TARGET_LANG=fr              # Langue cible
MAX_EMAILS_PER_CYCLE=5      # Max emails par cycle
AUTO_PUBLISH=false          # Mode automatique
FILTER_SENDER=              # Filtrer par expéditeur (optionnel)
```

### 🔐 Gmail : Créer un App Password

1. Activer la **validation en 2 étapes** sur votre compte Google
2. Aller sur https://myaccount.google.com/apppasswords
3. Créer un mot de passe pour "Mail"
4. Copier le mot de passe généré (format: `xxxx xxxx xxxx xxxx`)

### 🔐 WordPress : Créer un Application Password

1. WordPress Admin → **Utilisateurs → Profil**
2. Section **"Mots de passe d'application"**
3. Créer un nouveau mot de passe

## 🚀 Utilisation

### Dashboard Web (recommandé)

```bash
python run.py
# Ouvrir http://localhost:5050
```

### Mode CLI (automatique)

```bash
python app/main.py
```

### Docker

```bash
docker build -t wordpress-article-maker .
docker run -d --env-file config.env -p 5050:5050 wordpress-article-maker
```

## 📊 Dashboard

Le dashboard web permet de :

| Onglet | Description |
|--------|-------------|
| 📧 **Emails** | Voir et sélectionner les emails à traiter |
| 📝 **Articles en attente** | Gérer les articles générés avant publication |
| 📊 **Historique** | Voir les articles publiés sur WordPress |
| ⚙️ **Configuration** | Configurer IMAP, WordPress, IA et le prompt |

## 💰 Coûts

- **Claude Sonnet 4** : ~$0.003 par article
- ~300 articles pour $1

## 📁 Structure

```
wordpress-article-maker/
├── app/                   # Code source
│   ├── __init__.py
│   ├── dashboard.py       # Dashboard Flask
│   ├── main.py            # Mode CLI automatique
│   └── templates/
│       └── dashboard.html # Interface web
├── data/                  # Données runtime (non versionné)
├── config.env             # Configuration (non versionné)
├── config.env.example     # Template de configuration
├── requirements.txt       # Dépendances Python
├── run.py                 # Point d'entrée
├── Dockerfile             # Déploiement Docker
├── README.md
└── LICENSE
```

## 📄 License

MIT License
