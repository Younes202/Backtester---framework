from connection import engine
from sqlalchemy.sql import text
from calendar import monthrange
from fastapi import HTTPException
from indicators import Strategy
from risk_management import RiskManagement, RiskManagementD
import pandas as pd
from loguru import logger
from model import Kline, Kline_BTC, Kline_ETH, Kline_BNB, Kline_ADA, Kline_DOT
from enum import Enum
import json


class SignalType(Enum):
    SIGNAL_0_4 = 0.4
    SIGNAL_0_5 = 0.5
    SIGNAL_1 = 1
    SIGNAL_1_5 = 1.5
    SIGNAL_2 = 2
    SIGNAL_2_5 = 2.5
    SIGNAL_3 = 3

    def investment_percentage(self):
        """Return the investment percentage based on the signal value."""
        if self in {SignalType.SIGNAL_0_4, SignalType.SIGNAL_0_5}:
            return 0.30  # 30%
        elif self in {SignalType.SIGNAL_1, SignalType.SIGNAL_1_5}:
            return 0.40  # 40%
        elif self in {SignalType.SIGNAL_2, SignalType.SIGNAL_2_5}:
            return 0.45  # 45%
        elif self == SignalType.SIGNAL_3:
            return 0.50  # 50%
        else:
            return 0  # Default case

    @staticmethod
    def check_last_signal(investment_1, investment_2):
        """Calculate the remaining portion of the investment based on signal values."""
        # Here, signal_1 and signal_2 are enum instances
        total_invested = investment_1 + investment_2
        to_be_invested_percentage = 1 - total_invested
        return round(to_be_invested_percentage, 2)

    
class TradingSystem:
    def __init__(self, **kwargs):
        self.month = kwargs.get('month')
        self.symbol = kwargs.get('symbol', "")
        self.target_profit = kwargs.get('target_profit', 5)
        self.stoploss = kwargs.get('stoploss', 30)
        self.leverage = kwargs.get('leverage', 100)
        self.fees = kwargs.get('fees', 0.1)
        self.current_balance = kwargs.get('initial_investment', 100)
        self.timeframe = kwargs.get('timeframe', None)
        self.balance_availbale = None
        self.initial_investment = self.current_balance
        self.trade_cycles = []
        self.profits = 0
        self.losses = 0
        self.is_cycle=[]
        self.opportunites={}

    def fetch_data_from_db(self, timeframe=None):
        if self.month:
            try:
                year, month_num = map(int, self.month.split("-"))
                _, last_day = monthrange(year, month_num)
                start_open_time = pd.Timestamp(f"{year}-{month_num:02d}-01")
                end_close_time = pd.Timestamp(f"{year}-{month_num:02d}-{last_day} 23:59:59")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")

            try:
                base_query = f"""
                SELECT open_time, close_time, open_price, high_price, low_price, close_price, volume
                FROM {self.symbol}
                """
                filters = []
                params = {}
                if start_open_time:
                    filters.append("open_time >= :start_open_time")
                    params["start_open_time"] = start_open_time
                if end_close_time:
                    filters.append("close_time <= :end_close_time")
                    params["end_close_time"] = end_close_time
                if filters:
                    base_query += " WHERE " + " AND ".join(filters)
                base_query += " ORDER BY open_time ASC"

                with engine.connect() as connection:
                    df = pd.read_sql_query(text(base_query), con=connection, params=params)
                # Reset the index so 'open_time' becomes a column
                  # Ensure that open_time is in datetime format and set as index for resampling

                if timeframe:   
                    # Set open_time as the index for resampling

                    # Resample the data to the desired frequency (e.g., 5T)
   # Perform the resampling with 'close_time' added as 'last'
        # Keep 'open_time' and 'close_time' as columns by not setting any index
                    resampled_df = df.resample(
                        timeframe, on='open_time'
                    ).agg({
                        'open_price': 'first',
                        'high_price': 'max',
                        'low_price': 'min',
                        'close_price': 'last',
                        'volume': 'sum',
                        'close_time': 'last'  # Include the last close_time in each resampled period
                    }).dropna().reset_index()  # Reset index to keep open_time as a column

                    return resampled_df

                else:
                    return df
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")



    def run_trading_cycle(self):
        """Main trading loop using a multi-timeframe approach."""
        if self.timeframe:
            data = self.fetch_data_from_db(self.timeframe)
        else: 
            data = self.fetch_data_from_db()

        logger.info(f"1m Data fetched: {data.head(5)}")
        if data.empty:
            logger.error("No data fetched from the database.")
            return

        data = Strategy(data)
        data = data.get_decision()  # Get buy signals

        for i in range(1, len(data)):
            current_row = data.iloc[i]

            # 🟢 Step 1: Check for Buy Signal
            if len(self.is_cycle) != 3 and current_row['Signal'] == 1:
                signal_name = current_row['type']
                signal = SignalType[signal_name]  
                logger.info(f"1m entry signal at {current_row['close_price']} on {current_row['open_time']} with type {signal.value} Threshold")
                
                self.price = current_row['close_price']
                
                if len(self.is_cycle) == 2:
                    percentage = SignalType.check_last_signal(self.is_cycle[0]["percentage"], self.is_cycle[1]["percentage"])
                else:
                    percentage = signal.investment_percentage()

                amount_invested = self.current_balance * percentage
                opportunities = {
                    "type": signal,
                    "buy_time": current_row['close_time'],
                    "buy_price": current_row['close_price'],
                    "profit": signal.value,
                    "amount_invested": amount_invested,
                    "percentage": percentage
                }

                # ✅ Append immediately
                self.is_cycle.append(opportunities)

            # 🛑 Step 2: Check for Sell Opportunities
            for cycle in [c for c in self.is_cycle if "sell_price" not in c]:  # 🔥 Boucle uniquement sur les cycles sans vente
                rm = RiskManagement(
                    priceorder=cycle.get("buy_price"),
                    currentprice=current_row['close_price'],
                    target_profit=cycle.get("profit"),
                    stoploss=self.stoploss,
                    dollar_investment=cycle.get("amount_invested"), 
                    atr=current_row['ATR']
                )

                if rm.should_exit():
                    net_profit = rm.profit_or_loss
                    cycle["sell_price"] = current_row['close_price']
                    cycle["sell_time"] = current_row['close_time']
                    cycle["profit_loss"] = net_profit

                    if rm.stop_loss_exit():
                        logger.info("Exited position based on stop-loss.")
                    elif rm.target_profit_exit():
                        logger.info(f"Cycle finished at {current_row['close_price']} on {current_row['close_time']} | Profit: {net_profit}% | Entry: {cycle.get('buy_price')} at {cycle.get('buy_time')}")

                    self.current_balance += net_profit
                    self.profits += max(0, net_profit)
                    self.losses += min(0, net_profit)
                    self.trade_cycles.append(cycle)
                    logger.info("No sell opportunity found for this sub cycle")

                    if self.current_balance <= 0:
                        logger.warning("Account liquidated")
                        break
                else:
                    logger.info("No sell opportunity found for this sub cycle")

            # 📌 Step 3: Reset cycle list if it reaches a limit
            if len(self.is_cycle) == 3:
                self.is_cycle = []


    def calculate_metrics(self):
        """Calculate the requested performance and risk metrics, and save trade cycles as JSON."""
        if not self.trade_cycles:
            logger.error("No trades to analyze.")
            return {}

        # Define the file path to save the data
        file_path = "trade_cycles.json"

        # Save trade cycles to JSON file
        try:
            with open(file_path, "w") as file:
                json.dump(self.trade_cycles, file, indent=4, default=str)  # Convert timestamps to strings
            logger.info(f"Trade cycles saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving trade cycles: {e}")

        print(self.current_balance)

        return {"status": "success", "message": f"Trade cycles saved to {file_path}"}


    def print_metrics(self):
        """Log and print the calculated metrics."""
        metrics = self.calculate_metrics()

        # Display metrics
        for key, value in metrics.items():
            if isinstance(value, (float, int)):
                logger.info(f"{key}: {value:.2f}")
            elif isinstance(value, list):
                logger.info(f"{key}: {len(value)} trades")
                for trade in value:
                    logger.info(trade)
            else:
                logger.info(f"{key}: {value}")
balance_total = 0
monthly_profits=[]
monthly_losses = []
trading_params = {
    "month":"2024-8",
    "symbol": "kline_btcs",                # Faster RSI for quiter. You shousld move it to the Trash.ck momentum detection
    "target_profit":0.5,
    "stoploss": 30,
    "leverage": 100,
    "initial_investment": 600,
    "timeframe": "1min"
    }

# Create a TradingSystem instance for the current month
trading_system = TradingSystem(**trading_params)

# Fetch data and run the trading cycle
trading_system.fetch_data_from_db()  # Ensure data is fetched
trading_system.run_trading_cycle()
# Get metrics for the current month
dm = trading_system.calculate_metrics()
"""profits = dm["Net Profit"]
monthly_profits.append(profits)
losses = dm["Net Loss"]
monthly_losses.append(losses)

print(monthly_profits)
print(monthly_losses)

"""
