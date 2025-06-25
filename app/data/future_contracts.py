import requests
import pandas as pd
import time
import os

def fetch_bybit_klines_save_csv(
    symbol="BTCUSDT",
    category="linear",
    interval="1m",  # 3-minute interval
    start_time="2024-06-22",
    end_time="2025-06-22",
    limit=1000,
    output_file=None
):
    if output_file is None:
        output_file = f"futures-klines/{symbol.lower()}_{interval}_{start_time}_{end_time}.csv"

    base_url = "https://api.bybit.com/v5/market/kline"
    start_ts = int(pd.Timestamp(start_time).timestamp() * 1000)
    end_ts = int(pd.Timestamp(end_time).timestamp() * 1000)

    interval_ms = int(interval) * 60 * 1000  # 3 minutes in ms
    all_klines = []

    seen_timestamps = set()

    print(f"Fetching klines for {symbol} from {start_time} to {end_time} with interval {interval} minutes")

    while start_ts < end_ts:
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "start": start_ts,
            "limit": limit
        }

        # Bybit API returns klines in descending order (latest first)
        # So we set 'end' to start_ts + limit * interval_ms - 1, but not beyond end_ts
        batch_end_ts = min(start_ts + (limit * interval_ms) - 1, end_ts)
        params["end"] = batch_end_ts

        response = requests.get(base_url, params=params)
        data = response.json()

        if data.get("retCode") != 0:
            print("Error fetching data:", data.get("retMsg"))
            break

        klines = data.get("result", {}).get("list", [])
        if not klines:
            print("No more data returned by API.")
            break

        # Bybit returns klines in reverse order, so sort by timestamp ascending
        klines = sorted(klines, key=lambda x: int(x[0]))

        new_klines = [k for k in klines if int(k[0]) not in seen_timestamps and start_ts <= int(k[0]) <= end_ts]

        if not new_klines:
            print("Duplicate data returned; advancing manually.")
            start_ts += interval_ms * limit
            continue

        for k in new_klines:
            seen_timestamps.add(int(k[0]))
            all_klines.append(k)

        latest_timestamp = int(new_klines[-1][0])
        start_ts = latest_timestamp + interval_ms

        print(f"Fetched {len(new_klines)} new klines. Next start: {pd.to_datetime(start_ts, unit='ms')}")

        # If we reached or passed end_ts, stop
        if start_ts > end_ts:
            break

        time.sleep(0.25)

    if not all_klines:
        print("No data fetched.")
        return

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    df = pd.DataFrame(all_klines, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
    for col in ["open", "high", "low", "close", "volume", "turnover"]:
        df[col] = df[col].astype(float)
    df = df.sort_values("timestamp").reset_index(drop=True)

    df = df[(df["timestamp"] >= pd.Timestamp(start_time)) & (df["timestamp"] <= pd.Timestamp(end_time))]

    df.to_csv(output_file, index=False)
    print(f"✅ Saved {len(df)} rows to '{output_file}'")

# Run it
fetch_bybit_klines_save_csv(
    symbol="BTCUSDT",
    interval="3",
    start_time="2024-06-22",
    end_time="2025-06-22"
)
