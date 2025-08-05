import asyncio
import httpx
import pandas as pd
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingViewForexKlines:
    def __init__(self, symbol, interval, start_time, end_time):
        self.symbol = symbol.replace("FX:", "")  # Remove FX: prefix
        self.interval = interval
        self.start_time = start_time
        self.end_time = end_time
        logger.info(f"Initialized TradingView Forex Fetcher: {symbol}, {interval}")

    async def fetch_and_save_klines(self):
        try:
            all_data = await self.fetch_all_data()
            if all_data:
                df = self.convert_to_dataframe(all_data)
                self.save_to_csv(df)
                logger.info("Forex data saved successfully!")
            else:
                logger.warning("No data was fetched")
        except Exception as e:
            logger.error(f"Error in fetching forex data: {e}")
            raise

    async def fetch_all_data(self):
        all_data = []
        current_start = self.start_time
        
        while current_start < self.end_time:
            logger.info(f"Fetching data from {current_start}")
            chunk = await self.fetch_chunk(current_start)
            
            if not chunk:
                break
                
            all_data.extend(chunk)
            current_start = self.get_next_start(chunk[-1][0])
            await asyncio.sleep(1)  # Rate limiting
            
        return all_data

    async def fetch_chunk(self, start_time):
        url = "https://price-aggregator.tradingview.com/v2/aggregate"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://www.tradingview.com"
        }
        params = {
            "symbols": [f"FX:{self.symbol}"],
            "currency": "USD",
            "range_from": int(start_time.timestamp()),
            "range_to": int(self.end_time.timestamp()),
            "resolution": self.interval
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(url, headers=headers, params=params)
                r.raise_for_status()
                data = r.json()
                
                if not data.get("data"):
                    return []
                    
                return data["data"][f"FX:{self.symbol}"]["candles"]
                
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return []

    def get_next_start(self, last_timestamp):
        interval_map = {
            "1D": timedelta(days=1),
            "4H": timedelta(hours=4),
            "1H": timedelta(hours=1),
            "15M": timedelta(minutes=15),
            "5M": timedelta(minutes=5),
            "1M": timedelta(minutes=1)
        }
        return datetime.fromtimestamp(last_timestamp) + interval_map.get(self.interval, timedelta(minutes=1))

    def convert_to_dataframe(self, data):
        df = pd.DataFrame(data, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["time"] = pd.to_datetime(df["timestamp"], unit="s")
        return df[["time", "Open", "High", "Low", "Close", "Volume"]]

    def save_to_csv(self, df):
        os.makedirs("forex_data", exist_ok=True)
        filename = f"forex_data/{self.symbol}_{self.interval}.csv"
        df.to_csv(filename, index=False)
        logger.info(f"Saved to {filename}")

async def main():
    fetcher = TradingViewForexKlines(
        symbol="EURUSD",  # Without FX: prefix
        interval="15M",
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 1, 2)  # Smaller range for testing
    )
    await fetcher.fetch_and_save_klines()

if __name__ == "__main__":
    asyncio.run(main())