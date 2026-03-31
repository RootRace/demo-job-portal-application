# 🚀 Vettorix | Executive Career Intelligence Portal
---

## 📜 Legacy Documentation Data
**Install requirements:**
`flask python-dotenv pymupdf python-docx spacy`
`python -m spacy download en_core_web_sm` --> AI model for resume parsing
`en_core_web_trf` (large) / `en_core_web_sm` (small)

**Deployment:**
`web: gunicorn "app:create_app()"`

---

Vettorix is a high-end, AI-powered job portal designed for executive-level recruitment. It features automated resume parsing, a dynamic vetting engine, real-time notifications, and advanced recruiter analytics.

---


## 🛠️ Infrastructure Setup

### 1. Requirements
Ensure you have Python 3.8+ installed. Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. AI Model Initialization
Vettorix uses `spaCy` for high-accuracy NLP parsing. Download the required model:
```bash
python -m spacy download en_core_web_sm
```
> [!NOTE]
> For higher accuracy in production, you can switch to `en_core_web_trf` (requires more RAM).

---

## 🚀 Getting Started

### 🟢 Run Locally
```bash
python run.py
```
The server will start at **http://localhost:5000**.

### 🧪 Seed Test Accounts
To quickly start testing with pre-loaded recruiters, admins, and candidates:
```bash
python seed.py
```

### 🔐 Active Demo Accounts
| Role | Name | Email | Password |
| :--- | :--- | :--- | :--- |
| **Admin** | Super Admin | `admin@portal.com` | `Admin@123` |
| **Recruiter** | Rachel Morgan | `rachel.morgan@portal.com` | `Recruiter@1` |
| **Candidate** | Ethan Hunt | `ethan.hunt@mail.com` | `Candidate@1` |

---

## 🌐 Deployment
The portal is optimized for production-grade WSGI servers:
```bash
gunicorn "app:create_app()"
```

## 🏗️ Technical Stack
- **Backend:** Flask / Python 3.8+
- **Database:** SQLite (with optimized SQL indexing)
- **NLP:** spaCy (Natural Language Processing)
- **Frontend:** Vanilla CSS / JavaScript (AJAX/Polling)
- **Design:** Executive Premium Theme (HSL Color System)

---
© 2026 Vettorix Infrastructure. All Rights Reserved.
