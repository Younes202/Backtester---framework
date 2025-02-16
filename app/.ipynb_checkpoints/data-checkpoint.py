import httpx
import pandas as pd
from datetime import datetime
from loguru import logger
import os
from connection import get_db, Database
from model import Kline, Kline_BTC, Kline_ETH, Kline_BNB, Kline_ADA, Kline_DOT, Kline_BTCS
from sqlalchemy.orm import Session
import time  # For sleep functionality
import asyncio


class BinanceFuturesKlines:
    def __init__(self, symbol, interval, start_time, end_time):
        self.symbol = symbol
        self.interval = interval
        self.start_time = start_time
        self.end_time = end_time
        logger.info(f"Initialized BinanceFuturesKlines with symbol={symbol}, interval={interval}")

    async def fetch_and_save_klines(self):
        try:
            all_data = []  # To hold all fetched data
            current_start_time = self.start_time
            max_limit = 1000  # Binance API's maximum limit for klines per request

            while current_start_time < self.end_time:
                logger.info(f"Fetching data starting from {current_start_time}")

                # Fetch data for the current chunk
                chunk_data = await self.fetch_data_from_binance(current_start_time)
                if not chunk_data:
                    logger.warning(f"No data fetched starting from {current_start_time}. Exiting loop.")
                    break

                all_data.extend(chunk_data)

                # Update the start time to the closeTime of the last kline
                current_start_time = datetime.fromtimestamp(chunk_data[-1][6] / 1000)  # closeTime in ms

                # Sleep to avoid hitting API rate limits
                await asyncio.sleep(1)

            # Convert to DataFrame, process, and save
            df = self.convert_data_to_dataframe(all_data)
            self.save_to_csv(df)
            logger.info("All data fetched and saved successfully!")

        except Exception as e:
            logger.error(f"Error during fetching and saving klines: {e}")
            raise

    async def fetch_data_from_binance(self, start_time):
        base_url = "https://api.binance.com/api/v3/klines"  # SPOT MARKET API
        async with httpx.AsyncClient() as client:
            params = {
                "symbol": self.symbol,
                "interval": self.interval,
                "startTime": int(start_time.timestamp() * 1000),  # Convert to ms
                "limit": 1000,  # Maximum data points per request
            }

            try:
                response = await client.get(base_url, params=params)
                response.raise_for_status()
                klines = response.json()

                if not klines:
                    logger.info(f"No data returned starting from {start_time}.")
                    return []

                logger.info(f"Fetched {len(klines)} klines starting from {start_time}")
                return klines

            except httpx.RequestError as e:
                logger.error(f"Error fetching data from Binance Futures API: {e}")
                raise

    def convert_data_to_dataframe(self, data):
        if not data:
            logger.error("No data available for conversion.")
            raise ValueError("No data available to convert to DataFrame.")

        # Define column names as per API response
        column_names = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignored"
        ]

        logger.info("Converting fetched data to DataFrame.")
        df = pd.DataFrame(data, columns=column_names)

        # Select necessary columns and process them
        df = df[["open_time", "open", "high", "low", "close", "volume", "close_time"]]
        df["open_time"] = pd.to_datetime(df["open_time"], unit='ms')
        df["close_time"] = pd.to_datetime(df["close_time"], unit='ms')
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)

        logger.info("Data conversion to DataFrame completed.")
        return df

    def save_to_csv(self, df):
        output_dir = "spot_klines_data"
        os.makedirs(output_dir, exist_ok=True)

        # Save all data into a single file
        file_path = os.path.join(output_dir, f"{self.symbol}_{self.interval}_{self.start_time.year}-{self.end_time.year}.csv")
        df.to_csv(file_path, mode='w', header=True, index=False)
        logger.info(f"Saved all data to {file_path}")


# Main Function to Run
async def main():
    # Define parameters
    symbol = "BTCUSDT"
    interval = "1D"  # 1-minute interval
    start_time = datetime(2024, 1, 1)
    end_time = datetime(2025, 1, 31, 23, 59, 59)  # Last second of Jan 31, 2025


    # Initialize the Binance Futures Klines class
    klines_fetcher = BinanceFuturesKlines(symbol, interval, start_time, end_time)

    # Fetch and save klines
    await klines_fetcher.fetch_and_save_klines()


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())


"""
db_manager = Database()

def save_csv_to_db(csv_file: str, db: Session):

    # Step 1: Read the CSV file into a pandas DataFrame
    df = pd.read_csv(csv_file)

    # Step 2: Iterate through each row and save it into the database
    for _, row in df.iterrows():
        # Create each Kline object and insert it into the database
        db_manager.create(
            db,
            Kline_BTCS,
            open_time=row["open_time"],
            close_time=row["close_time"],
            open_price=row["open"],
            high_price=row["high"],
            low_price=row["low"],
            close_price=row["close"],
            volume=row["volume"],
        )

    # Step 3: Commit the transaction to save the data
    db.commit()

    # Step 4: Success message
    print(f"Successfully saved data from {csv_file} to the database!")

# Get a session directly using get_db()
db = get_db()

# CSV file to save
csv_file = 'spot_klines_data/BTCUSDT_1m_2024-2025.csv'

# Save the CSV data to the database
save_csv_to_db(csv_file, db)

# Close the session after operations
db.close()
# Main function for doge and save to csv
"""
