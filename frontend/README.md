# 🍽️ AI Food Website Auditor

An AI-powered website intelligence and quality auditing platform for restaurants, cafes, bakeries, food businesses, and other Food & Beverage websites.

The system accepts a public website URL, scans the website using HTTP requests and Playwright browser automation, extracts real business information, structures the data, and presents the results through a professional dashboard.

## 🚀 Features

- 🌐 Scan any publicly accessible food/restaurant website
- ⚡ HTTP + Playwright hybrid website scanning
- 🤖 AI-powered analysis using LangChain and Ollama
- 🍔 Automatic menu extraction
- 📋 Structured menu tables
- 💰 Menu prices and currencies
- 📞 Phone and contact information
- 📧 Email extraction
- 📍 Restaurant address and location
- 🕐 Opening hours detection
- 📅 Reservation information
- 🛒 Online ordering information
- 📱 Social media detection
- 🏪 Restaurant/business profile
- 🔎 Website and SEO information
- ⚙️ Technical website information
- 🧠 AI-generated website insights
- 🕘 Scan history
- 🔄 Re-scan functionality
- 🌙 Persistent dark/light mode
- 📊 Professional dashboard
- 📥 Downloadable audit reports
- 📱 Responsive interface
- 🌍 Designed for websites from different countries, currencies and languages

## 🧠 How It Works

```text
User enters restaurant URL
        ↓
FastAPI receives URL
        ↓
HTTP Website Scanner
        ↓
If necessary → Playwright Browser Scanner
        ↓
Rendered website content
        ↓
Information Extraction
        ↓
Structured Restaurant Data
        ↓
LangChain + Ollama AI Analysis
        ↓
FastAPI JSON Response
        ↓
React Dashboard
        ↓
Restaurant Information + AI Insights + Report