from connection import engine
from sqlalchemy.sql import text
from calendar import monthrange
from fastapi import HTTPException
from indicators import Strategy
from risk_management import RiskManagement, RiskManagementD
import pandas as pd
from loguru import logger
from model import Kline, Kline_BTC, Kline_ETH, Kline_BNB, Kline_ADA, Kline_DOT

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
        self.initial_investment = self.current_balance
        self.trade_cycles = []
        self.in_position = False
        self.position = None
        self.price = 0
        self.dateposition = None
        self.profits = 0
        self.losses = 0
        self.is_cycle=None

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
        """
        Main trading loop using a multi-timeframe approach:
        - Loop through the 15-minute data.
        - When a 15-minute buy signal is found, fetch and filter 1-minute data from that time onward.
        - Then, scan the 1-minute data for a 1-minute buy signal to time the entry.
        """
        # Step 1: Fetch and process 15m data.
        if self.timeframe:
            data = self.fetch_data_from_db(self.timeframe)
        else : 
            data = self.fetch_data_from_db()

        logger.info(f"1m Data fetched: {data.head(5)}")
        if data.empty:
            logger.error("No data fetched from the database.")
            return

        data = Strategy(data)
        data = data.get_decision()  # Get buy signal

        # Loop through the 15m current_rows.
        for i in range(1, len(data)):
            current_row = data.iloc[i]
            if not self.in_position:


                if current_row['Signal'] == 1:
                    logger.info(f"1m entry signal found at {current_row['close_price']} on {current_row['open_time']}")
                    self.price = current_row['close_price']
                    self.dateposition = current_row['open_time']
                    self.position = 'LONG'
                    self.in_position = True


            if self.in_position:
                rm = RiskManagement(
                    priceorder=self.price,
                    currentprice=current_row['close_price'],
                    target_profit=self.target_profit,
                    stoploss=self.stoploss,
                    dollar_investment=self.current_balance,
                    atr=current_row['ATR']
                )
                try:
                    if rm.should_exit():
                        net_profit = rm.profit_or_loss

                        if rm.stop_loss_exit():
                            logger.info("Exited position based on stop-loss.")
                        elif rm.target_profit_exit():
                            logger.info(
                                f"Cycle finished at {current_row['close_price']} on {current_row['open_time']}, "
                                f"Profit: {net_profit}%; Entry was {self.price} at {self.dateposition}"
                            )
                        self.trade_cycles.append({
                            'Date Start': self.dateposition,
                            'Price Start': self.price,
                            'Position': self.position,
                            'Dollar Amount Start': self.current_balance,
                            'Date End': current_row['open_time'],
                            'Price End': current_row['close_price'],
                            'Dollar Amount End': self.current_balance + net_profit,
                            'Profit/Loss': net_profit
                        })
                        if net_profit > 0:
                            self.profits += net_profit
                        else:
                            self.losses += net_profit
                        self.in_position = False
                        if self.current_balance <= 0:
                            logger.warning("Account liquidated")
                            break
                        # 
                        self.current_balance = self.current_balance  + net_profit
                except SystemExit as e:
                    logger.error(f"Trading cycle stopped due to liquidation: {str(e)}")
                    break


    def calculate_metrics(self):
        """Calculate the requested performance and risk metrics."""
        if not self.trade_cycles:
            logger.error("No trades to analyze.")
            return {}

        trade_df = pd.DataFrame(self.trade_cycles)

        # Calculate profits and losses
        trade_df['Profit (%)'] = (
            (trade_df['Dollar Amount End'] - trade_df['Dollar Amount Start']) / trade_df['Dollar Amount Start'] * 100
        )

        # Calculate cycle time in minutes
        trade_df['Cycle Time'] = (
            pd.to_datetime(trade_df['Date End']) - pd.to_datetime(trade_df['Date Start'])
        ).dt.total_seconds() / 60

        # Count longs and shorts in profitable and loss trades
        profitable_longs = len(trade_df[(trade_df['Profit (%)'] > 0) & (trade_df['Position'] == 'LONG')])
        profitable_shorts = len(trade_df[(trade_df['Profit (%)'] > 0) & (trade_df['Position'] == 'SHORT')])
        loss_longs = len(trade_df[(trade_df['Profit (%)'] <= 0) & (trade_df['Position'] == 'LONG')])
        loss_shorts = len(trade_df[(trade_df['Profit (%)'] <= 0) & (trade_df['Position'] == 'SHORT')])

        # Total Trades, Win Rate, Loss Rate
        total_trades = len(trade_df)
        wins = trade_df[trade_df['Profit (%)'] > 0]
        losses = trade_df[trade_df['Profit (%)'] <= 0]
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        loss_rate = len(losses) / total_trades * 100 if total_trades > 0 else 0

        # Average Profit, Average Loss
        avg_profit = wins['Profit (%)'].mean() if not wins.empty else 0
        avg_loss = losses['Profit (%)'].mean() if not losses.empty else 0

        # ROI and Net Profit
        roi = (self.profits - self.initial_investment) / self.initial_investment * 100

        # Average Time per Cycle
        avg_time_per_cycle = trade_df['Cycle Time'].mean() if not trade_df['Cycle Time'].empty else 0

        # Metrics Dictionary
        metrics = {
            'Total Trades': total_trades,
            'Win Rate (%)': win_rate,
            'Loss Rate (%)': loss_rate,
            'Average Profit (%)': avg_profit,
            'Average Loss (%)': avg_loss,
            'ROI (%)': roi,
            'Net Profit ($)': self.profits,
            'Average Time per Cycle (minutes)': avg_time_per_cycle,
            'Profitable Long Trades': profitable_longs,
            'Profitable Short Trades': profitable_shorts,
            'Loss Long Trades': loss_longs,
            'Loss Short Trades': loss_shorts,
        }

        # Include detailed trades for profitable and loss trades
        metrics['Profitable Trades'] = wins.to_dict(orient='records')
        metrics['Loss Trades'] = losses.to_dict(orient='records')
        metrics['Net Profit'] = self.profits
        metrics['Net Loss'] = self.losses


        return metrics

 
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
trading_system.print_metrics()
"""profits = dm["Net Profit"]
monthly_profits.append(profits)
losses = dm["Net Loss"]
monthly_losses.append(losses)

print(monthly_profits)
print(monthly_losses)

"""
