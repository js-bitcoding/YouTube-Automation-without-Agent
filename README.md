# 🎥 YouTube Automation Project

A full-stack AI-powered YouTube automation system, built to streamline content creation — from script generation to thumbnail validation.

---

### 🖼 3. Thumbnail Finder & Validator
- Downloads thumbnails from YouTube
- Filters for:
  - Face presence
  - Color contrast
  - Readable text
- Saves valid thumbnails locally and in PostgreSQL
- Scores thumbnails for CTR potential

### ✍️ 4. Script Generator
- Input: Title or video idea
- Output: Hook + full script
- Modes: Short-form, Long-form, Listicle, Storytelling
- Styles: Hype, Serious, Casual, Storyteller
- Optional tone training from:
  - Text scripts
  - Voice memos
  - YouTube links

---

## 📦 Setup

### 1. Clone the Repo
```bash
git clone https://github.com/your-username/youtube-automation.git
cd youtube-automation

## add the model name "vosk-model-small-en-us-0.15" inside the folder "action_models"

python -m venv venv
venv\Scripts\activate  # On Windows

pip install -r requirements.txt

## add your API keys like YOUTUBE_API_KEY, GEMINI_API_KEY, DATABASE_URL in .env file