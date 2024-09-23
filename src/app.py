from flask import Flask , render_template , request , session , url_for , redirect
import mysql.connector as c
import MySQLdb.cursors
import yfinance as yf
import plotly.graph_objs as go
from flask_bcrypt import Bcrypt

import re

app = Flask(__name__)
app.secret_key = 'stox'
bcrypt = Bcrypt(app)

db  = c.connect(
    host = 'localhost',
    user = 'root',
    password = 'password',
    database = 'project'
)

mc = db.cursor(MySQLdb.cursors.DictCursor)

def plot_data(y):
    #use THESE "ADANIENT.NS , APOLLOHOSP.NS , HDFCBANK.NS , RELIANCE.NS"
    z = refresh_fetchData(y)
    fig = refresh_Graph(z,y)
    return fig.to_html(config={'displayModeBar': False})

def currentPrice(tickers):
    try:
        ticker_yahoo = yf.Ticker(tickers)
        data = ticker_yahoo.history()
        return (float)(data['Close'].iloc[-1])
    except:
        return 0

def buyStock(id , Stock_Symbol , price , shares , cost , new_bal):
    sql = "INSERT INTO TRANSACTIONSBUY (idusers, Stock_Symbol, CurrentBuyPrice, BuyQuantity, TotalPriceBuy) values (%s , %s , %s , %s , %s)"
    val = (id , Stock_Symbol , price , shares , cost)
    mc.execute(sql,val)
    db.commit()
    sql = "UPDATE users SET amount_available = %s WHERE (idusers = %s)"
    val = (new_bal , id)
    mc.execute(sql , val)
    db.commit()
    sql = "SELECT * FROM savailable WHERE idusers = %s AND Stock_Symbol = %s"
    val = (id,Stock_Symbol)
    mc.execute(sql,val)
    exist = mc.fetchone()
    if exist == None:
        sql = "select sum(BuyQuantity) from transactionsbuy where idusers = %s and Stock_Symbol = %s"
        val = (id,Stock_Symbol)
        mc.execute(sql,val)
        buy = mc.fetchone()
        totalBuy = 0
        if buy[0] == None:
            totalBuy = 0
        else:
            totalBuy = (int)(buy[0])

        sql = "select sum(SellQuantity) from transactionssell where idusers = %s and Stock_Symbol = %s"       
        val = (id,Stock_Symbol)
        mc.execute(sql,val)
        sell = mc.fetchone()
        totalSell = 0

        if sell[0] == None:
            totalSell = 0
        else:
            totalSell = (int)(sell[0])
        
        share_avail = totalBuy - totalSell
        sql = "insert into savailable (idusers , Stock_Symbol , Shares_Available) values (%s,%s,%s)"
        val = (id,Stock_Symbol,share_avail)
        mc.execute(sql,val)
        db.commit()
                
    else:
        sql = "select sum(BuyQuantity) from transactionsbuy where idusers = %s and Stock_Symbol = %s"
        val = (id,Stock_Symbol)
        mc.execute(sql,val)
        buy = mc.fetchone()
        totalBuy = 0
        if buy[0] == None:
            totalBuy = 0
        else:
            totalBuy = (int)(buy[0])

        sql = "select sum(SellQuantity) from transactionssell where idusers = %s and Stock_Symbol = %s"       
        val = (id,Stock_Symbol)
        mc.execute(sql,val)
        sell = mc.fetchone()
        totalSell = 0

        if sell[0] == None:
            totalSell = 0
        else:
            totalSell = (int)(sell[0])
        
        share_avail = totalBuy - totalSell
        sql = "UPDATE savailable SET Shares_Available = %s WHERE idusers = %s AND Stock_Symbol = %s"
        val = (share_avail,id,Stock_Symbol)
        mc.execute(sql,val)
        db.commit()

    msg = "Purchased Successfully"
    return msg


def sellStock(userid , price , shares , sa , Stock_Symbol):
    sql = "SELECT amount_available FROM USERS WHERE idusers = %s"
    val = (userid,)
    mc.execute(sql,val)
    balance = mc.fetchone()
    cost = price * (int)(shares)
    new_share = sa - (int)(shares)
    new_balance = (float)(balance[0]) + cost
    if new_share == 0:
        sql = "DELETE FROM savailable WHERE idusers = %s AND Stock_Symbol = %s"
        val = (userid , Stock_Symbol)
        mc.execute(sql,val)
        db.commit()
    else:
        sql = "UPDATE savailable SET Shares_Available = %s WHERE idusers = %s AND Stock_Symbol = %s"
        val = (new_share , userid , Stock_Symbol)
        mc.execute(sql,val)
        db.commit()
    sql = "UPDATE users SET amount_available = %s WHERE idusers = %s"
    val = (new_balance , userid)
    mc.execute(sql , val)
    db.commit()
    sql = 'INSERT INTO TRANSACTIONSSELL (idusers , Stock_Symbol , CurrentSellPrice , SellQuantity , TotalSellPrice) VALUES (%s , %s , %s , %s , %s)'
    val = (userid , Stock_Symbol , price , shares , cost)
    mc.execute(sql,val)
    db.commit()
    msg = 'Transaction Successfull'
    return msg


def refresh_fetchData(x):
    data = yf.download(tickers=x, period='1d', interval='1m')
    # Print data
    return data
    
def refresh_Graph(data,x):
    fig = go.Figure()

     # Candlestick
    fig.add_trace(go.Candlestick(x=data.index,
                                open=data['Open'],
                                high=data['High'],
                                low=data['Low'],
                                close=data['Close'], name='market data'))

        # Add titles
    fig.update_layout(
            title=x + ' Enterprise live share price evolution',
            yaxis_title='Stock Price (INR per Shares)')

        # X-Axes
    fig.update_xaxes(
        rangeslider_visible=True,
        rangeselector=dict(
            buttons=list([
                dict(count=15, label="15m", step="minute", stepmode="backward"),
                dict(count=45, label="45m", step="minute", stepmode="backward"),
                dict(count=1, label="1h", step="hour", stepmode="todate"),
                dict(count=3, label="3h", step="hour", stepmode="backward"),
                dict(step="all")
            ])
        )
    )

    return fig

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
        sql = "SELECT password FROM USERS WHERE USERNAME = %s "
        val = (username,)
        mc.execute(sql, val)
        data = mc.fetchone()
        if data:
            password = data[0]
            if bcrypt.check_password_hash(password , pw):
                sql = "SELECT * FROM USERS WHERE USERNAME = %s AND PASSWORD = %s"
                val = (username, password)
                mc.execute(sql, val)
                account = mc.fetchone()
                session['loggedin'] = True
                session['id'] = account[0]
                session['amount'] = account[4]
                session['username'] = account[1]
                return redirect('home')
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
    return redirect('/')

@app.route('/register' , methods = ['GET' , 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        pw = request.form['password']
        password = bcrypt.generate_password_hash(pw).decode('utf-8')
        email = request.form['email']
        sql = "SELECT * FROM USERS WHERE USERNAME = %s"
        val = (username ,)
        mc.execute(sql , val)
        account = mc.fetchone()
        if account:
            msg = 'Account already exists !'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address !'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers !'
        elif not username or not password or not email:
            msg = 'Please fill out the form !'
        else:
            sql = "INSERT INTO users (username , email , password) VALUES (%s , %s , %s)"
            val = (username, email, password )
            mc.execute(sql , val)
            db.commit()
            msg = "account created"
        
    return render_template('register.html' , msg = msg)

@app.route('/home/transactions')
def transactions():
    if session['loggedin'] == False :
        msg = 'login first'
        return render_template('login.html' , msg = msg)
    
    sql = "SELECT Stock_Symbol, Shares_Available FROM savailable WHERE idusers = %s"
    val = (session['id'],)
    mc.execute(sql,val)
    result_set = mc.fetchall()

    sql = "SELECT Stock_Symbol, CurrentBuyPrice, BuyQuantity, TotalPriceBuy FROM transactionsbuy WHERE idusers = %s"
    val = (session['id'],)
    mc.execute(sql,val)
    result_set2 = mc.fetchall()

    sql = "SELECT Stock_Symbol, CurrentSellPrice, SellQuantity, TotalSellPrice FROM transactionssell WHERE idusers = %s"
    val = (session['id'],)
    mc.execute(sql,val)
    result_set3 = mc.fetchall()
    
    return render_template('user.html', result_set = result_set , result_set3 = result_set3 , result_set2 = result_set2)

@app.route('/home')
def index():
    if session['loggedin'] == False :
        msg = 'login first'
        return render_template('login.html' , msg = msg)
    
    sql = "SELECT Stock_Symbol FROM savailable WHERE idusers = %s"
    val = (session['id'],)
    mc.execute(sql,val)
    shares_existing = mc.fetchall()
    return render_template('home.html' , amount = session['amount'] , username = session['username'] , shares = shares_existing)


@app.route('/home/buyList')
def listbuy():
    if session['loggedin'] == False :
        msg = 'login first'
        return render_template('login.html' , msg = msg)
    return render_template('buyList.html')

@app.route('/home/sellList')
def listSell():
    if session['loggedin'] == False :
        msg = 'login first'
        return render_template('login.html' , msg = msg)
    return render_template('sellList.html')
    



@app.route('/home/buyList/<stock_symbol>' , methods = ['GET' , 'POST'])
def buyShare(stock_symbol):
    msg =''
    if session['loggedin'] == False :
        msg = 'login first'
        return render_template('login.html' , msg = msg)
    
    
    if request.method == 'POST':
        shares = request.form['BuyQuant']
        userid = session['id']
        sql = "SELECT amount_available FROM USERS WHERE idusers = %s"
        val = (userid,)
        mc.execute(sql,val)
        balance = mc.fetchone()

        price = currentPrice(stock_symbol) 
        cost = price * (int)(shares)
        if((float)(balance[0]) >= (float)(cost)):  
            new_balance = (float)(balance[0]) - (float)(cost)
            msg = buyStock(session['id'] , stock_symbol , price , shares , cost , new_balance)
        else:
            msg = "NOT ENOUGH BALANCE"
                     
    return render_template('share-buy.html', plot=plot_data(stock_symbol) , msg = msg , price = (str)(currentPrice(stock_symbol)) , SS = stock_symbol , stock_symbol = stock_symbol)

@app.route('/home/sellList/<stock_symbol>' , methods = ['GET' , 'POST'])
def sellShare(stock_symbol):
    msg =''
    if session['loggedin'] == False :
        msg = 'login first'
        return render_template('login.html' , msg = msg)
    
    if request.method == 'POST':
        shares = request.form['SellQuant']
        userid = session['id']
        sql = "SELECT Shares_Available FROM savailable WHERE idusers = %s AND Stock_Symbol = %s"
        val = (userid , stock_symbol)
        mc.execute(sql,val)
        shareAvailable = mc.fetchone()

        sa = 0

        if shareAvailable is not None:
            sa = (int)(shareAvailable[0])

        if(sa >= (int)(shares)):
            price = currentPrice(stock_symbol)
            msg = sellStock(userid , price , shares , sa , stock_symbol)
        else:
            msg = "Not Enough Stocks"
            

        
    return render_template('share-sell.html' , msg = msg , plot = plot_data(stock_symbol) , price = currentPrice(stock_symbol) , stock_symbol = stock_symbol , SS = stock_symbol)



if __name__ == '__main__':
    app.run(debug = True)
