# WordPress Article Maker

🚀 Automated pipeline that transforms emails (press releases) into WordPress articles using AI.

![Dashboard](https://img.shields.io/badge/Dashboard-Flask-blue) ![AI](https://img.shields.io/badge/AI-Multi--Provider-purple) ![WordPress](https://img.shields.io/badge/CMS-WordPress-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

- **📧 IMAP Monitoring** - Automatic email fetching from any mailbox
- **🤖 Multi-AI Support** - Claude, GPT-4, Gemini, or Ollama (local)
- **📝 Preview Mode** - Review articles before publishing
- **🚀 WordPress Publishing** - Direct draft publishing via REST API
- **⚙️ Web Dashboard** - Full configuration interface with real-time notifications
- **🔄 Auto Mode** - Fully automated workflow without manual intervention
- **🎨 Custom Prompts** - Customize AI instructions for your writing style

## 🏗️ Architecture

```
┌─────────────┐
│ IMAP Poller │ → Fetch emails
└──────┬──────┘
       ▼
┌─────────────────────┐
│ Parser & Converter  │ → HTML → Markdown
└──────┬──────────────┘
       ▼
┌─────────────────┐
│ AI Generator    │ → Generate article (Claude/GPT/Gemini/Ollama)
└──────┬──────────┘
       ▼
┌─────────────────┐
│ WordPress API   │ → Publish as draft
└─────────────────┘
```

## 📦 Installation

```bash
# Clone the repo
git clone https://github.com/mkarki/wordpress-article-maker.git
cd wordpress-article-maker

# Install dependencies
pip install -r requirements.txt

# Copy and configure
cp config.env.example config.env
# Edit config.env with your credentials
```

## ⚙️ Configuration

Edit `config.env`:

```bash
# Email IMAP (Gmail requires App Password)
IMAP_HOST=imap.gmail.com
IMAP_EMAIL=your-email@gmail.com
IMAP_PASSWORD=xxxx xxxx xxxx xxxx

# WordPress (create Application Password in WP Admin)
WP_URL=https://your-site.com
WP_USER=your-username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx

# AI Provider (anthropic, openai, gemini, ollama)
AI_PROVIDER=anthropic

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929

# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o

# Google Gemini
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-1.5-pro

# Ollama (local)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Options
CHECK_INTERVAL=300          # Check interval in seconds
TARGET_LANG=en              # Target language
MAX_EMAILS_PER_CYCLE=5      # Max emails per cycle
AUTO_PUBLISH=false          # Auto mode
FILTER_SENDER=              # Filter by sender (optional)
```

### 🔐 Gmail: Create App Password

1. Enable **2-Step Verification** on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Create a password for "Mail"
4. Copy the generated password (format: `xxxx xxxx xxxx xxxx`)

### 🔐 WordPress: Create Application Password

1. WordPress Admin → **Users → Profile**
2. Section **"Application Passwords"**
3. Create a new password

## 🚀 Usage

### Web Dashboard (recommended)

```bash
python run.py
# Open http://localhost:5050
```

### CLI Mode (automatic)

```bash
python app/main.py
```

### Docker

```bash
docker build -t wordpress-article-maker .
docker run -d --env-file config.env -p 5050:5050 wordpress-article-maker
```

## 📊 Dashboard

The web dashboard allows you to:

| Tab | Description |
|-----|-------------|
| 📧 **Emails** | View and select emails to process |
| 📝 **Pending Articles** | Manage generated articles before publishing |
| 📊 **History** | View articles published to WordPress |
| ⚙️ **Configuration** | Configure IMAP, WordPress, AI provider and prompt |

## 🤖 Supported AI Providers

| Provider | Models |
|----------|--------|
| **Anthropic** | Claude Sonnet 4.5, Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku |
| **OpenAI** | GPT-4o, GPT-4o Mini, GPT-4 Turbo, GPT-3.5 Turbo |
| **Google** | Gemini 1.5 Pro, Gemini 1.5 Flash, Gemini Pro |
| **Ollama** | Any local model (llama3, mistral, etc.) |

## 💰 Costs

- **Claude Sonnet 4**: ~$0.003 per article
- **GPT-4o**: ~$0.005 per article
- **Gemini 1.5 Pro**: ~$0.002 per article
- **Ollama**: Free (local)

## 📁 Structure

```
wordpress-article-maker/
├── app/                   # Source code
│   ├── __init__.py
│   ├── dashboard.py       # Flask dashboard
│   ├── main.py            # CLI mode
│   └── templates/
│       └── dashboard.html # Web interface
├── data/                  # Runtime data (not versioned)
├── config.env             # Configuration (not versioned)
├── config.env.example     # Configuration template
├── requirements.txt       # Python dependencies
├── run.py                 # Entry point
├── Dockerfile             # Docker deployment
├── README.md
└── LICENSE
```

## 📄 License

MIT License
