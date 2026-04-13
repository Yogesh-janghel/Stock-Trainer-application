import os
import pandas as pd
import requests
from io import StringIO
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, url_for, redirect, flash
import yfinance as yf
import plotly.graph_objs as go
from flask_bcrypt import Bcrypt
from decimal import Decimal
import re
from datetime import datetime
from flask_apscheduler import APScheduler

# Load environment variables
load_dotenv()

from models import db, User, Transaction, Holding, Stock

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'stox')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Scheduler Configuration
app.config['SCHEDULER_API_ENABLED'] = True
scheduler = APScheduler()

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)

def update_stock_list():
    """Fetches the Nifty 50 list and updates the database with names and current prices."""
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)
            
            symbols = [s + ".NS" for s in df['Symbol'].tolist()]
            
            # Fetch all prices in one batch
            tickers = yf.Tickers(" ".join(symbols))
            
            for index, row in df.iterrows():
                symbol = row['Symbol'] + ".NS"
                name = row['Company Name']
                
                # Try to get price from batch fetch
                try:
                    price_data = tickers.tickers[symbol].history(period='1d')
                    price = float(price_data['Close'].iloc[-1]) if not price_data.empty else None
                except:
                    price = None
                
                stock = Stock.query.filter_by(symbol=symbol).first()
                if not stock:
                    stock = Stock(symbol=symbol, name=name, current_price=Decimal(str(price)) if price else None)
                    db.session.add(stock)
                else:
                    stock.name = name
                    if price:
                        stock.current_price = Decimal(str(price))
                stock.last_updated = datetime.utcnow()
            
            db.session.commit()
            print(f"[{datetime.now()}] Stock prices updated successfully.")
            return True
    except Exception as e:
        print(f"Error updating stock list: {e}")
    return False

# Background Job: Update prices every 15 minutes
@scheduler.task('interval', id='do_update_prices', minutes=15)
def scheduled_update():
    with app.app_context():
        update_stock_list()

# Create tables and populate stock list if empty
with app.app_context():
    db.create_all()
    if Stock.query.count() == 0:
        update_stock_list()
    
    # Start scheduler
    if not scheduler.running:
        scheduler.init_app(app)
        scheduler.start()

@app.route('/refresh_prices')
def refresh_prices():
    if not session.get('loggedin'):
        return redirect(url_for('login'))
    if update_stock_list():
        flash("Market prices updated!", "success")
    else:
        flash("Failed to update prices.", "danger")
    return redirect(request.referrer or url_for('home'))

def refresh_fetchData(x):
    """Fetches stock data and robustly handles MultiIndex columns to avoid KeyError."""
    print(f"Fetching data for {x}...")
    # Using 1mo/1d for stable candlestick data
    data = yf.download(tickers=x, period='1mo', interval='1d', progress=False)
    
    if data.empty:
        print(f"No data found for {x}.")
        return data

    # Defensive MultiIndex Handling
    if isinstance(data.columns, pd.MultiIndex):
        # Case 1: Ticker is in level 0 (e.g., Ticker -> Open)
        if x in data.columns.get_level_values(0):
            data = data.xs(x, axis=1, level=0)
        # Case 2: Ticker is in level 1 (e.g., Open -> Ticker)
        elif x in data.columns.get_level_values(1):
            data = data.xs(x, axis=1, level=1)
        else:
            # Case 3: Fallback - find which level has 'Open'
            for i in range(data.columns.nlevels):
                if 'Open' in data.columns.get_level_values(i):
                    data.columns = data.columns.get_level_values(i)
                    break

    # Final check to ensure we have the right columns
    required_cols = ['Open', 'High', 'Low', 'Close']
    missing_cols = [col for col in required_cols if col not in data.columns]
    
    if missing_cols:
        print(f"Warning: Still missing columns {missing_cols} for {x}. Current columns: {list(data.columns)}")
        # Last resort: if there's only one ticker, sometimes stacking/resetting helps
        if len(data.columns) >= 5: # Open, High, Low, Close, Adj Close...
             # If columns are just the ticker name repeated, we force-rename based on typical yfinance order
             if all(col == x for col in data.columns[:5]):
                 data.columns = ['Adj Close', 'Close', 'High', 'Low', 'Open', 'Volume'][:len(data.columns)]
    
    print(f"Successfully processed {x}: {len(data)} rows. Columns: {list(data.columns)}")
    return data
    
def refresh_Graph(data, x):
    fig = go.Figure()

    # Candlestick - explicitly using the index which is already Datetime
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'], 
        name='Price'
    ))

    # Add titles and professional styling
    fig.update_layout(
        title=f'{x} Share Price Evolution (Last 30 Days)',
        yaxis_title='Stock Price (INR)',
        template='plotly_white',
        xaxis_rangeslider_visible=True,
        height=600,
        margin=dict(l=50, r=20, t=80, b=50),
        xaxis=dict(
            type='date',
            rangeslider=dict(visible=True)
        )
    )

    return fig

def plot_data(y):
    # Fetch data for the chart
    z = refresh_fetchData(y)
    if z.empty:
        return "<div class='alert alert-warning'>No market data available for this stock right now. Please try again later.</div>"
    
    fig = refresh_Graph(z, y)
    # Use include_plotlyjs=False because we included it in base.html CDN
    return fig.to_html(full_html=False, include_plotlyjs=False, config={'displayModeBar': False})

def currentPrice(symbol):
    try:
        ticker_yahoo = yf.Ticker(symbol)
        data = ticker_yahoo.history(period='1d')
        if not data.empty:
            price = float(data['Close'].iloc[-1])
            
            # Update cache in DB
            stock = Stock.query.filter_by(symbol=symbol).first()
            if stock:
                stock.current_price = Decimal(str(price))
                stock.last_updated = datetime.utcnow()
                db.session.commit()
            return price
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
    
    # Fallback to cached price if available
    stock = Stock.query.filter_by(symbol=symbol).first()
    if stock and stock.current_price:
        return float(stock.current_price)
    return 0

def buyStock(user_id, symbol, price, quantity, total_cost, new_balance):
    try:
        # Record Transaction
        txn = Transaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type='BUY',
            price=Decimal(str(price)),
            quantity=quantity,
            total_cost=Decimal(str(total_cost))
        )
        db.session.add(txn)

        # Update User Balance
        user = User.query.get(user_id)
        user.balance = Decimal(str(new_balance))

        # Update Holding
        holding = Holding.query.filter_by(user_id=user_id, symbol=symbol).first()
        if not holding:
            holding = Holding(user_id=user_id, symbol=symbol, shares_available=quantity)
            db.session.add(holding)
        else:
            holding.shares_available += quantity

        db.session.commit()
        return "Purchased Successfully"
    except Exception as e:
        db.session.rollback()
        return f"Error: {str(e)}"

def sellStock(user_id, price, quantity, sa, symbol):
    try:
        total_price = Decimal(str(price)) * Decimal(str(quantity))
        
        # Record Transaction
        txn = Transaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type='SELL',
            price=Decimal(str(price)),
            quantity=quantity,
            total_cost=total_price
        )
        db.session.add(txn)

        # Update User Balance
        user = User.query.get(user_id)
        user.balance += total_price

        # Update Holding
        holding = Holding.query.filter_by(user_id=user_id, symbol=symbol).first()
        if holding:
            holding.shares_available -= int(quantity)
            if holding.shares_available <= 0:
                db.session.delete(holding)
        
        db.session.commit()
        return 'Transaction Successful'
    except Exception as e:
        db.session.rollback()
        return f"Error: {str(e)}"

@app.route('/')
def start():
    return render_template('welcome.html')

@app.route('/login' , methods = ['GET' , 'POST'])
def login():
    msg = ""
    session['loggedin'] = False
    if request.method == 'POST':
        username = request.form['username']
        pw = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user:
            if bcrypt.check_password_hash(user.password, pw):
                session['loggedin'] = True
                session['id'] = user.id
                session['amount'] = float(user.balance)
                session['username'] = user.username
                return redirect(url_for('home'))
            else:
                msg = "Incorrect"
        else:
            msg = "User Doesn't Exist"
    return render_template('login.html' , msg = msg)

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('amount', None)
    return redirect('/')

@app.route('/register' , methods = ['GET' , 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        pw = request.form['password']
        email = request.form['email']
        
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        
        if existing_user:
            msg = 'Account already exists !'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address !'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers !'
        elif not username or not pw or not email:
            msg = 'Please fill out the form !'
        else:
            password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')
            new_user = User(username=username, email=email, password=password_hash)
            db.session.add(new_user)
            db.session.commit()
            msg = "account created"
        
    return render_template('register.html' , msg = msg)


@app.route('/home/transactions')
def transactions():
    if not session.get('loggedin'):
        return render_template('login.html', msg='login first')
    
    user_id = session['id']
    holdings = Holding.query.filter_by(user_id=user_id).all()
    # Format holdings for template (expecting list of tuples or similar)
    result_set = [(h.symbol, h.shares_available) for h in holdings]

    buys = Transaction.query.filter_by(user_id=user_id, transaction_type='BUY').all()
    result_set2 = [(t.symbol, float(t.price), t.quantity, float(t.total_cost)) for t in buys]

    sells = Transaction.query.filter_by(user_id=user_id, transaction_type='SELL').all()
    result_set3 = [(t.symbol, float(t.price), t.quantity, float(t.total_cost)) for t in sells]
    
    return render_template('user.html', result_set=result_set, result_set3=result_set3, result_set2=result_set2)

@app.route('/home')
def home():
    if not session.get('loggedin'):
        return render_template('login.html', msg='login first')
    
    user = User.query.get(session['id'])
    session['amount'] = float(user.balance) # Refresh balance in session
    
    holdings = Holding.query.filter_by(user_id=session['id']).all()
    shares_existing = [(h.symbol,) for h in holdings]
    
    return render_template('home.html', amount=session['amount'], username=session['username'], shares=shares_existing)

@app.route('/home/buyList')
def listbuy():
    if not session.get('loggedin'):
        return render_template('login.html', msg='login first')
    stocks = Stock.query.all()
    return render_template('buyList.html', stocks=stocks)

@app.route('/home/sellList')
def listSell():
    if not session.get('loggedin'):
        return render_template('login.html', msg='login first')
    # For selling, we can show either all stocks or only what the user holds.
    # The user asked for a real-time list of top 50, so we'll show all but highlight holdings if needed.
    # To keep it consistent with buyList, we'll pass all stocks.
    stocks = Stock.query.all()
    return render_template('sellList.html', stocks=stocks)

@app.route('/refresh_stocks')
def refresh_stocks():
    if update_stock_list():
        flash("Stock list updated successfully!", "success")
    else:
        flash("Failed to update stock list.", "danger")
    return redirect(url_for('listbuy'))

@app.route('/home/buyList/<stock_symbol>', methods=['GET', 'POST'])
def buyShare(stock_symbol):
    if not session.get('loggedin'):
        return render_template('login.html', msg='login first')
    
    msg = ''
    if request.method == 'POST':
        try:
            shares_to_buy = int(request.form['BuyQuant'])
            user = User.query.get(session['id'])
            price = Decimal(str(currentPrice(stock_symbol)))
            cost = price * shares_to_buy
            
            if user.balance >= cost:
                new_balance = user.balance - cost
                msg = buyStock(user.id, stock_symbol, float(price), shares_to_buy, float(cost), float(new_balance))
                session['amount'] = float(User.query.get(user.id).balance)
            else:
                msg = "NOT ENOUGH BALANCE"
        except Exception as e:
            msg = f"Error: {str(e)}"
                     
    price_str = str(currentPrice(stock_symbol))
    return render_template('share-buy.html', plot=plot_data(stock_symbol), msg=msg, price=price_str, SS=stock_symbol, stock_symbol=stock_symbol)

@app.route('/home/sellList/<stock_symbol>', methods=['GET', 'POST'])
def sellShare(stock_symbol):
    if not session.get('loggedin'):
        return render_template('login.html', msg='login first')
    
    msg = ''
    if request.method == 'POST':
        try:
            shares_to_sell = int(request.form['SellQuant'])
            holding = Holding.query.filter_by(user_id=session['id'], symbol=stock_symbol).first()
            
            if holding and holding.shares_available >= shares_to_sell:
                price = currentPrice(stock_symbol)
                msg = sellStock(session['id'], price, shares_to_sell, holding.shares_available, stock_symbol)
                session['amount'] = float(User.query.get(session['id']).balance)
            else:
                msg = "Not Enough Stocks"
        except Exception as e:
            msg = f"Error: {str(e)}"
            
    holding = Holding.query.filter_by(user_id=session['id'], symbol=stock_symbol).first()
    sa = holding.shares_available if holding else 0

    return render_template('share-sell.html', msg=msg, plot=plot_data(stock_symbol), price=currentPrice(stock_symbol), stock_symbol=stock_symbol, SS=stock_symbol, sa=sa)


if __name__ == '__main__':
    app.run(debug = True)
