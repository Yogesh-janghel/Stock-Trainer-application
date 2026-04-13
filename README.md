# Stock Trainer Application 

A professional-grade stock market trading simulator built with Python and Flask. This application provides a risk-free environment for users to learn trading strategies using real-time data from the Nifty 50 (NSE).

## 🌐 Live Demo

The application is live and accessible here:
👉 https://stock-trainer-application.onrender.com/

## 🚀 Overview
Originally built 4 years ago, this application has been modernized with a cloud-ready architecture, a robust ORM layer, and a sleek "Emerald Gradient" UI.

## 🛠 Backend Architecture & Tech Stack

### Core Framework
- **Flask**: A lightweight WSGI web application framework.
- **SQLAlchemy (ORM)**: Migrated from raw SQL to Object-Relational Mapping for high security against SQL injection and database flexibility (currently configured for **Supabase/Postgres**).
- **Flask-Bcrypt**: Industry-standard password hashing (salted) for secure authentication.
- **Flask-APScheduler**: Handles automated background tasks for real-time market price synchronization.

### Data & Financial Logic
- **yfinance (Yahoo Finance API)**: Fetches real-time market data, including daily OHLC (Open, High, Low, Close) values and historical data.
- **Pandas**: Used for processing Nifty 50 component lists and handling complex financial dataframes.
- **Decimal/Numeric Support**: All financial calculations (balances, costs, prices) are handled using the `Decimal` type to prevent floating-point rounding errors.

### Database Schema (Cloud-Ready)
The database is structured into four primary models:
1. **User**: Stores credentials (hashed), email, current virtual balance, and account timestamps.
2. **Stock**: A dynamic cache of the Nifty 50 list, storing symbols, company names, and the latest fetched prices.
3. **Transaction**: A unified ledger recording every 'BUY' and 'SELL' event with volume, price, and total cost.
4. **Holding**: Tracks the user's current portfolio, ensuring unique constraints on (User + Stock) combinations.

## ✨ Features
- **Real-time Nifty 50 Sync**: Automatically downloads the latest 50 top-cap Indian stocks.
- **Interactive Candlestick Charts**: Dynamic, zoomable charts powered by **Plotly.js**.
- **Automated Price Engine**: Background workers refresh market prices every 15 minutes.
- **Emerald Theme UI**: A modern, responsive design using custom CSS gradients and Bootstrap 5.
- **Virtual Capital**: Every new user starts with ₹5,00,000 in virtual money.

## ⚙️ Installation & Setup

1. **Clone the repository**
2. **Create a Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: .\venv\Scripts\activate
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r src/requirements.txt
   ```
4. **Configure Environment Variables**:
   Create a `.env` file in the `src/` directory:
   ```ini
   SECRET_KEY=your_secret_key_here
   SQLALCHEMY_DATABASE_URI=postgresql://postgres:password@your-supabase-url:5432/postgres
   ```

## 🌍 Deployment on Render

### Step 1: Prepare your Code
Ensure your code is pushed to a GitHub repository. Render will pull directly from your repo.

### Step 2: Create a Web Service on Render
1. Log in to [Render.com](https://render.com).
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository.

### Step 3: Configure Settings
- **Root Directory**: `src` (or leave blank if your app.py is at the root, adjust accordingly).
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app` (You may need to add `gunicorn` to your `requirements.txt`).

### Step 4: Add Environment Variables
In the Render dashboard for your service:
1. Go to **Environment**.
2. Add `SECRET_KEY` and `SQLALCHEMY_DATABASE_URI` (your Supabase link).
3. Render will deploy automatically!

---
*Note: This project is intended for educational purposes only. No real money is involved in any transactions.*
