
# Assuming the fetch_data_from_db method is part of a class with a SQLAlchemy engine 'engine' and a 'month' attribute.
from calendar import monthrange
from fastapi import HTTPException
import pandas as pd
from sqlalchemy.sql import text
from app.connection import engine
from app.indicators import Strategy

class TradingStrategyTester:
    def __init__(self, engine, month=None):
        self.engine = engine
        self.month = month
    
    def fetch_data(self):
        # Fetch data using the provided method
        df = self.fetch_data_from_db()
        return df

    def test_strategy(self, df):
        strategy = Strategy(df)
        strategy.logic_strategy()
        df_signals = strategy.get_decision()
        return df_signals

    def fetch_data_from_db(self):
        if self.month:
            try:
                # Parse month input
                year, month_num = map(int, self.month.split("-"))
                _, last_day = monthrange(year, month_num)
                start_open_time = pd.Timestamp(f"{year}-{month_num:02d}-01")
                end_close_time = pd.Timestamp(f"{year}-{month_num:02d}-{last_day} 23:59:59")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")

            try:
                # Initialize the base query
                base_query = """
                SELECT open_time, close_time, open_price, high_price, low_price, close_price, volume
                FROM klines
                """
                filters = []
                params = {}

                # Add filters for start and end times
                if start_open_time:
                    filters.append("open_time >= :start_open_time")
                    params["start_open_time"] = start_open_time
                if end_close_time:
                    filters.append("close_time <= :end_close_time")
                    params["end_close_time"] = end_close_time

                # Add WHERE clause dynamically if filters exist
                if filters:
                    base_query += " WHERE " + " AND ".join(filters)

                # Add ordering
                base_query += " ORDER BY open_time ASC"

                # Fetch data
                with self.engine.connect() as connection:
                    df = pd.read_sql_query(
                        text(base_query),
                        con=connection,
                        params=params,
                    )
                return df
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Example Usage:
# Assuming 'engine' is your SQLAlchemy engine and you want to test for a specific month
tester = TradingStrategyTester(engine, month="2024-12")
data = tester.fetch_data()
signals = tester.test_strategy(data)
print(signals)

print(len(signals))







