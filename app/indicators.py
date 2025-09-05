from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
import pandas as pd
import talib
import numpy as np
from ta.volatility import AverageTrueRange




class DayTradingStrategy:
    def __init__(self, data_15m=None, data_1h=None):
        self.data_15m = data_15m.copy() if data_15m is not None else None
        self.data_1h = data_1h.copy() if data_1h is not None else None
        
        # Convert timestamps
        for df in [self.data_15m, self.data_1h]:
            if df is not None and "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])

    # ============== 1H TREND DIRECTION ==============
    def calculate_1h_trend(self):
        df = self.data_1h.copy()
        df["EMA_50"] = talib.EMA(df["close"], timeperiod=50)
        df["EMA_200"] = talib.EMA(df["close"], timeperiod=200)
        df["RSI_14"] = talib.RSI(df["close"], timeperiod=14)
        df["ADX_14"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=14)
        
        # VWAP approximation
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        df["VWAP"] = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        df["Volume_MA"] = talib.SMA(df["volume"], timeperiod=20)
        
        # Trend definitions
        df["Bullish_Trend"] = (df["EMA_50"] > df["EMA_200"]) & (df["close"] > df["VWAP"]) & (df["ADX_14"] > 20)
        df["Bearish_Trend"] = (df["EMA_50"] < df["EMA_200"]) & (df["close"] < df["VWAP"]) & (df["ADX_14"] > 20)
        df["Strong_Bullish"] = df["Bullish_Trend"] & (df["RSI_14"] > 55) & (df["volume"] > df["Volume_MA"])
        df["Strong_Bearish"] = df["Bearish_Trend"] & (df["RSI_14"] < 45) & (df["volume"] > df["Volume_MA"])
        # Candle patterns
        df["Engulfing_Bull"] = talib.CDLENGULFING(df["open"], df["high"], df["low"], df["close"]) == 100
        df["Engulfing_Bear"] = talib.CDLENGULFING(df["open"], df["high"], df["low"], df["close"]) == -100
        df["Shoulder_Bull"] = talib.CDLPIERCING(df["open"], df["high"], df["low"], df["close"]) > 0
        df["Shoulder_Bear"] = talib.CDLDARKCLOUDCOVER(df["open"], df["high"], df["low"], df["close"]) < 0
        # S/R levels
        df["SR_20_High"] = df["high"].rolling(20).max()
        df["SR_20_Low"] = df["low"].rolling(20).min()
        return df

    # ============== 15M ENTRY SIGNALS ==============
    def calculate_15m_entries(self):
        df = self.data_15m.copy()
        df["EMA_50"] = talib.EMA(df["close"], timeperiod=50)
        df["EMA_200"] = talib.EMA(df["close"], timeperiod=200)
        df["RSI_14"] = talib.RSI(df["close"], timeperiod=14)
        df["ADX_14"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=14)
        # VWAP approximation
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        df["VWAP"] = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        df["Volume_MA"] = talib.SMA(df["volume"], timeperiod=20)
        # S/R zones
        df["SR_20_High"] = df["high"].rolling(20).max()
        df["SR_20_Low"] = df["low"].rolling(20).min()
        # Candle patterns
        df["Engulfing_Bull"] = talib.CDLENGULFING(df["open"], df["high"], df["low"], df["close"]) == 100
        df["Engulfing_Bear"] = talib.CDLENGULFING(df["open"], df["high"], df["low"], df["close"]) == -100
        df["Shoulder_Bull"] = talib.CDLPIERCING(df["open"], df["high"], df["low"], df["close"]) > 0
        df["Shoulder_Bear"] = talib.CDLDARKCLOUDCOVER(df["open"], df["high"], df["low"], df["close"]) < 0
        return df

    # ============== GENERATE SIGNALS ==============
    def generate_signals(self):
        df_1h = self.calculate_1h_trend()
        df_15m = self.calculate_15m_entries()
        
        # Merge trend into 15m candles
        df_1h_trend = df_1h[["timestamp", "Strong_Bullish", "Strong_Bearish", "Engulfing_Bull", "Engulfing_Bear", "Shoulder_Bull", "Shoulder_Bear"]]
        df_15m = pd.merge_asof(
            df_15m.sort_values("timestamp"),
            df_1h_trend.sort_values("timestamp"),
            on="timestamp",
            direction="backward"
        )
        df_15m[["Strong_Bullish", "Strong_Bearish", "Engulfing_Bull", "Engulfing_Bear", "Shoulder_Bull", "Shoulder_Bear"]] = \
            df_15m[["Strong_Bullish", "Strong_Bearish", "Engulfing_Bull", "Engulfing_Bear", "Shoulder_Bull", "Shoulder_Bear"]].fillna(False)

        # Initialize signal
        df_15m["Signal"] = 0

        # ========= ENTRY CONDITIONS =========
        for i in range(len(df_15m)):
            row = df_15m.iloc[i]
            # LONG
            if row["Strong_Bullish"]:
                # Breakout above resistance with bullish candle pattern
                if row["close"] > row["SR_20_High"] and (row["Engulfing_Bull"] or row["Shoulder_Bull"]):
                    df_15m.at[i, "Signal"] = 1
                # Pullback near support with bullish candle pattern
                elif row["close"] > row["EMA_50"] and row["close"] <= row["SR_20_Low"] * 1.02 and (row["Engulfing_Bull"] or row["Shoulder_Bull"]):
                    df_15m.at[i, "Signal"] = 1
            # SHORT
            elif row["Strong_Bearish"]:
                # Breakdown below support with bearish candle pattern
                if row["close"] < row["SR_20_Low"] and (row["Engulfing_Bear"] or row["Shoulder_Bear"]):
                    df_15m.at[i, "Signal"] = -1
                # Pullback near resistance with bearish candle pattern
                elif row["close"] < row["EMA_50"] and row["close"] >= row["SR_20_High"] * 0.98 and (row["Engulfing_Bear"] or row["Shoulder_Bear"]):
                    df_15m.at[i, "Signal"] = -1

        return df_15m



class Strategy:
    def __init__(self, data_15m=None, data_1h=None, data_4h=None):
        """
        Accepts up to three timeframes: 15m, 1h, 4h.
        All should be pandas DataFrames with OHLCV and 'timestamp' columns.
        """
        self.data_15m = data_15m.copy()
        self.data_1h = data_1h.copy() 
        self.data_4h = data_4h.copy() 

        # Convert timestamps
        for df in [self.data_15m, self.data_1h, self.data_4h]:
            if df is not None and "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])

    def calculate_indicators(self):
        # Calculate indicators for each timeframe if present
        if self.data_4h is not None:
            df = self.data_4h
            df['EMA50'] = EMAIndicator(close=df['close'], window=50).ema_indicator() if len(df) >= 50 else np.nan
            df['EMA200'] = EMAIndicator(close=df['close'], window=200).ema_indicator() if len(df) >= 200 else np.nan
            df['ADX'] = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx() if len(df) >= 14 else np.nan
            df['MACD'] = MACD(close=df['close'], window_slow=12, window_fast=6, window_sign=5).macd() if len(df) >= 12 else np.nan
            df['MACD_Signal'] = MACD(close=df['close'], window_slow=12, window_fast=6, window_sign=5).macd_signal() if len(df) >= 12 else np.nan
            df['Bias_Bull'] = (df['EMA50'] > df['EMA200']) & (df['MACD'] > df['MACD_Signal']) & (df['ADX'] > 25)
            df['Bias_Bear'] = (df['EMA50'] < df['EMA200']) & (df['MACD'] < df['MACD_Signal']) & (df['ADX'] > 25)
            self.data_4h = df

        if self.data_1h is not None:
            df = self.data_1h
            df['EMA50'] = EMAIndicator(close=df['close'], window=50).ema_indicator() if len(df) >= 50 else np.nan
            df['EMA200'] = EMAIndicator(close=df['close'], window=200).ema_indicator() if len(df) >= 200 else np.nan
            df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi() if len(df) >= 14 else np.nan
            df['MACD'] = MACD(close=df['close'], window_slow=12, window_fast=6, window_sign=5).macd() if len(df) >= 12 else np.nan
            df['MACD_Signal'] = MACD(close=df['close'], window_slow=12, window_fast=6, window_sign=5).macd_signal() if len(df) >= 12 else np.nan
            df['Volume_OK'] = df['volume'] > df['volume'].rolling(20).mean()
            df['Confirm_Long'] = (df['EMA50'] > df['EMA200']) & (df['MACD'] > df['MACD_Signal']) & (df['RSI'] > 50) & (df['Volume_OK'])
            df['Confirm_Short'] = (df['EMA50'] < df['EMA200']) & (df['MACD'] < df['MACD_Signal']) & (df['RSI'] < 50) & (df['Volume_OK'])
            self.data_1h = df

        if self.data_15m is not None:
            df = self.data_15m
            df['EMA50'] = EMAIndicator(close=df['close'], window=50).ema_indicator() if len(df) >= 50 else np.nan
            df['EMA200'] = EMAIndicator(close=df['close'], window=200).ema_indicator() if len(df) >= 200 else np.nan
            df['MACD'] = MACD(close=df['close'], window_slow=12, window_fast=6, window_sign=5).macd() if len(df) >= 12 else np.nan
            df['MACD_Signal'] = MACD(close=df['close'], window_slow=12, window_fast=6, window_sign=5).macd_signal() if len(df) >= 12 else np.nan
            df['ADX'] = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx() if len(df) >= 14 else np.nan
            df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi() if len(df) >= 14 else np.nan
            df['Volume_OK'] = df['volume'] > df['volume'].rolling(20).mean()
            df['Bullish_Structure'] = (df['high'] > df['high'].shift(1)) & (df['low'] > df['low'].shift(1))
            df['Bearish_Structure'] = (df['high'] < df['high'].shift(1)) & (df['low'] < df['low'].shift(1))
            self.data_15m = df

    def generate_signals(self):
        """
        Returns a DataFrame of 15m signals where all conditions across 4h, 1h, and 15m are met.
        Requires all three timeframes to be present.
        """
        self.calculate_indicators()
        if self.data_4h is None or self.data_1h is None or self.data_15m is None:
            raise ValueError("All three timeframes (15m, 1h, 4h) must be provided.")

        # Merge bias from 4h and confirmation from 1h into 15m
        df_4h = self.data_4h[['timestamp', 'Bias_Bull', 'Bias_Bear']]
        df_1h = self.data_1h[['timestamp', 'Confirm_Long', 'Confirm_Short']]
        df_15m = self.data_15m.copy()

        # Merge asof for latest bias/confirm at each 15m candle
        df_15m = pd.merge_asof(
            df_15m.sort_values("timestamp"),
            df_4h.sort_values("timestamp"),
            on="timestamp",
            direction="backward"
        )
        df_15m = pd.merge_asof(
            df_15m.sort_values("timestamp"),
            df_1h.sort_values("timestamp"),
            on="timestamp",
            direction="backward"
        )

        # Fill missing with False for boolean columns
        for col in ['Bias_Bull', 'Bias_Bear', 'Confirm_Long', 'Confirm_Short', 'Bullish_Structure', 'Bearish_Structure', 'Volume_OK']:
            if col in df_15m.columns:
                df_15m[col] = df_15m[col].fillna(False)

        # Fill missing with 0 for numeric columns
        for col in ['EMA50', 'EMA200', 'MACD', 'MACD_Signal', 'ADX']:
            if col in df_15m.columns:
                df_15m[col] = df_15m[col].fillna(0)

        # Signal: all conditions must be True
        df_15m['Signal'] = 0
        df_15m.loc[
            df_15m['Bias_Bull'] & df_15m['Confirm_Long'] &
            (df_15m['EMA50'] > df_15m['EMA200']) &
            (df_15m['MACD'] > df_15m['MACD_Signal']) &
            (df_15m['ADX'] > 20) &
            (df_15m['Bullish_Structure']) &
            (df_15m['Volume_OK']),
            'Signal'
        ] = 1

        df_15m.loc[
            df_15m['Bias_Bear'] & df_15m['Confirm_Short'] &
            (df_15m['EMA50'] < df_15m['EMA200']) &
            (df_15m['MACD'] < df_15m['MACD_Signal']) &
            (df_15m['ADX'] > 20) &
            (df_15m['Bearish_Structure']) &
            (df_15m['Volume_OK']),
            'Signal'
        ] = -1

        return df_15m[['timestamp', 'close', 'Signal']]


class SwingStrategy:
        def __init__(self, data, timeframe_type):
            """
            data: DataFrame for the selected timeframe (4h, 1h, or 15m)
            timeframe_type: '4h', '1h', or '15m'
            """
            self.data = data.copy()
            self.timeframe_type = timeframe_type
            self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
            self.volatility_factor = 3.0
            self.min_volume_usdt = 1000000

        def calculate_indicators_4h(self):
            # 4h: Detect bias (trend direction) using EMAs, ADX, MACD, ATR
            self.data['EMA233'] = talib.EMA(self.data['close'], timeperiod=233)
            self.data['EMA55'] = talib.EMA(self.data['close'], timeperiod=55)
            self.data['ADX'] = talib.ADX(self.data['high'], self.data['low'], self.data['close'], timeperiod=14)
            macd, macdsignal, _ = talib.MACD(self.data['close'], fastperiod=12, slowperiod=26, signalperiod=9)
            self.data['MACD'] = macd
            self.data['MACD_Signal'] = macdsignal
            self.data['ATR'] = talib.ATR(self.data['high'], self.data['low'], self.data['close'], timeperiod=14) * self.volatility_factor
            if 'quote_asset_volume' in self.data.columns:
                self.data['Volume_OK'] = self.data['quote_asset_volume'] > self.min_volume_usdt
            else:
                self.data['Volume_OK'] = (self.data['volume'] * self.data['close']) > self.min_volume_usdt
            self.data['Bias_Bull'] = (self.data['EMA55'] > self.data['EMA233']) & (self.data['ADX'] > 25) & (self.data['MACD'] > self.data['MACD_Signal'])
            self.data['Bias_Bear'] = (self.data['EMA55'] < self.data['EMA233']) & (self.data['ADX'] > 25) & (self.data['MACD'] < self.data['MACD_Signal'])
            return self.data

        def calculate_indicators_1h(self):
            # 1h: Confirmation (pullback/pull-reset) using EMAs, RSI, MACD
            self.data['EMA21'] = talib.EMA(self.data['close'], timeperiod=21)
            self.data['EMA55'] = talib.EMA(self.data['close'], timeperiod=55)
            self.data['RSI'] = talib.RSI(self.data['close'], timeperiod=12)
            macd, macdsignal, _ = talib.MACD(self.data['close'], fastperiod=8, slowperiod=21, signalperiod=13)
            self.data['MACD'] = macd
            self.data['MACD_Signal'] = macdsignal
            self.data['ATR'] = talib.ATR(self.data['high'], self.data['low'], self.data['close'], timeperiod=14) * self.volatility_factor
            if 'quote_asset_volume' in self.data.columns:
                self.data['Volume_OK'] = self.data['quote_asset_volume'] > self.min_volume_usdt
            else:
                self.data['Volume_OK'] = (self.data['volume'] * self.data['close']) > self.min_volume_usdt
            # Pullback: price returns to EMA21/EMA55 zone with RSI not overbought/oversold
            self.data['Pullback_Long'] = (self.data['close'] > self.data['EMA21']) & (self.data['close'] > self.data['EMA55']) & (self.data['RSI'] > 45) & (self.data['RSI'] < 70)
            self.data['Pullback_Short'] = (self.data['close'] < self.data['EMA21']) & (self.data['close'] < self.data['EMA55']) & (self.data['RSI'] < 55) & (self.data['RSI'] > 30)
            return self.data

        def calculate_indicators_15m(self):
            # 15m: Entry (breakout/pull-reset) using price/EMA, MACD, ATR
            self.data['EMA21'] = talib.EMA(self.data['close'], timeperiod=21)
            self.data['EMA55'] = talib.EMA(self.data['close'], timeperiod=55)
            self.data['RSI'] = talib.RSI(self.data['close'], timeperiod=12)
            macd, macdsignal, _ = talib.MACD(self.data['close'], fastperiod=8, slowperiod=21, signalperiod=13)
            self.data['MACD'] = macd
            self.data['MACD_Signal'] = macdsignal
            self.data['ATR'] = talib.ATR(self.data['high'], self.data['low'], self.data['close'], timeperiod=14) * self.volatility_factor
            if 'quote_asset_volume' in self.data.columns:
                self.data['Volume_OK'] = self.data['quote_asset_volume'] > self.min_volume_usdt
            else:
                self.data['Volume_OK'] = (self.data['volume'] * self.data['close']) > self.min_volume_usdt
            # Breakout: price closes above recent high (long) or below recent low (short)
            self.data['Breakout_Long'] = (self.data['close'] > self.data['high'].rolling(10).max().shift(1)) & (self.data['MACD'] > self.data['MACD_Signal']) & (self.data['RSI'] > 50)
            self.data['Breakout_Short'] = (self.data['close'] < self.data['low'].rolling(10).min().shift(1)) & (self.data['MACD'] < self.data['MACD_Signal']) & (self.data['RSI'] < 50)
            # Pull-reset: price pulls back to EMA21/EMA55 zone after breakout
            self.data['PullReset_Long'] = (self.data['close'] > self.data['EMA21']) & (self.data['close'] > self.data['EMA55']) & (self.data['MACD'] > self.data['MACD_Signal'])
            self.data['PullReset_Short'] = (self.data['close'] < self.data['EMA21']) & (self.data['close'] < self.data['EMA55']) & (self.data['MACD'] < self.data['MACD_Signal'])
            return self.data

        def generate_signals(self):
            """
            For 4h: Only bias detection (no signal, just bias columns)
            For 1h: Only confirmation (no signal, just confirmation columns)
            For 15m: Entry signals, requires bias_4h and confirm_1h from higher timeframes
            """
            if self.timeframe_type == '4h':
                self.calculate_indicators_4h()
                self.data['Signal'] = 0  # Only bias, not entry
            elif self.timeframe_type == '1h':
                self.calculate_indicators_1h()
                self.data['Signal'] = 0  # Only confirmation, not entry
            elif self.timeframe_type == '15m':
                self.calculate_indicators_15m()
                self.data['Signal'] = 0
                # Compute bias_4h and confirm_1h internally using rolling window
                # Assume self.data has enough rows to look back for higher timeframe bias/confirm
                # For each 15m row, get the latest bias/confirm from 4h/1h
                # Here, for simplicity, use the most recent available value
                # In practice, you would pass in the 4h/1h dataframes and align timestamps
                # For demonstration, we simulate bias_4h and confirm_1h as columns if present
                bias_4h = self.data['Bias_Bull'] if 'Bias_Bull' in self.data.columns else pd.Series([False]*len(self.data), index=self.data.index)
                confirm_1h = self.data['Pullback_Long'] if 'Pullback_Long' in self.data.columns else pd.Series([False]*len(self.data), index=self.data.index)
                self.data['Signal'] = np.where(
                    bias_4h & confirm_1h & self.data['Breakout_Long'], 1,
                    np.where(
                        (~bias_4h) & (~confirm_1h) & self.data['Breakout_Short'], -1, 0
                    )
                )
            elif self.timeframe_type == '1m':
                # Calculate ATR for 1m timeframe
                self.data['atr'] = talib.ATR(self.data['high'], self.data['low'], self.data['close'], timeperiod=14)
            else:
                raise ValueError("Unsupported timeframe_type for SwingStrategy")
            return self.data

class FuturesStrategyScalping:
    def __init__(self, data):
        self.data = data.copy()
        # Ensure timestamp exists
        if 'timestamp' not in self.data.columns:
            self.data['timestamp'] = pd.to_datetime(self.data['close_time'])
        # Convert all numeric columns
        self.data[['open','high','low','close','volume']] = \
            self.data[['open','high','low','close','volume']].apply(pd.to_numeric, errors='coerce')

    def calculate_indicators(self):
        # Ultra-fast EMAs for 3m
        self.data['EMA3'] = self.data['close'].ewm(span=3, adjust=False).mean()
        self.data['EMA8'] = self.data['close'].ewm(span=8, adjust=False).mean()
        # RSI - very sensitive
        self.data['RSI_2'] = RSIIndicator(close=self.data['close'], window=2).rsi()
        self.data['RSI_6'] = RSIIndicator(close=self.data['close'], window=6).rsi()
        # ATR for volatility filter
        atr = AverageTrueRange(high=self.data['high'], low=self.data['low'], close=self.data['close'], window=7)
        self.data['ATR'] = atr.average_true_range()
        # Smart volume filter (percentile)
        if 'volume' in self.data.columns:
            self.data['Vol_P30'] = self.data['volume'].rolling(12).quantile(0.3)
            self.data['Volume_Active'] = self.data['volume'] > self.data['Vol_P30'] * 1.05
        else:
            self.data['Volume_Active'] = True
        # Price momentum
        self.data['Momentum'] = self.data['close'] - self.data['close'].shift(3)
        # Small range filter (avoid chop)
        self.data['Small_Range'] = self.data['ATR'] < self.data['ATR'].rolling(20).mean() * 0.9

        # --- Pullback and Reset based on Support/Resistance ---
        # Support: recent swing lows, Resistance: recent swing highs
        self.data['Support'] = self.data['low'].rolling(window=20, min_periods=1).min()
        self.data['Resistance'] = self.data['high'].rolling(window=20, min_periods=1).max()
        # Pullback: price returns to support after being above resistance
        self.data['Pullback'] = (
            (self.data['close'].shift(1) > self.data['Resistance'].shift(1)) &
            (self.data['close'] < self.data['Support'])
        )
        # Reset: price returns to resistance after being below support
        self.data['Reset'] = (
            (self.data['close'].shift(1) < self.data['Support'].shift(1)) &
            (self.data['close'] > self.data['Resistance'])
        )
        return self.data

    def generate_signals(self):
        self.calculate_indicators()
        self.data['Signal'] = 0

        # LONG: Price above both EMAs, RSI_2 rising but not overbought, momentum positive, volume active, low chop, pullback condition
        self.data.loc[
            (self.data['close'] > self.data['EMA3']) &
            (self.data['EMA3'] > self.data['EMA8']) &
            (self.data['RSI_2'] > 35) & (self.data['RSI_2'] < 75) &
            (self.data['RSI_2'] > self.data['RSI_2'].shift(1)) &
            (self.data['Momentum'] > 0) &
            (self.data['Volume_Active']) &
            (self.data['Small_Range']) &
            (self.data['Pullback']),
            'Signal'
        ] = 1

        # SHORT: Price below both EMAs, RSI_2 falling but not oversold, momentum negative, volume active, low chop, reset condition
        self.data.loc[
            (self.data['close'] < self.data['EMA3']) &
            (self.data['EMA3'] < self.data['EMA8']) &
            (self.data['RSI_2'] < 65) & (self.data['RSI_2'] > 25) &
            (self.data['RSI_2'] < self.data['RSI_2'].shift(1)) &
            (self.data['Momentum'] < 0) &
            (self.data['Volume_Active']) &
            (self.data['Small_Range']) &
            (self.data['Reset']),
            'Signal'
        ] = -1

        # Pullback/Reset signals (standalone)
        # Long on pullback to support, short on reset to resistance
        self.data.loc[
            (self.data['Pullback']) &
            (self.data['RSI_2'] > 35) & (self.data['Momentum'] > 0),
            'Signal'
        ] = 1

        self.data.loc[
            (self.data['Reset']) &
            (self.data['RSI_2'] < 65) & (self.data['Momentum'] < 0),
            'Signal'
        ] = -1

        # If still no signals, relax volume and range filters
        if self.data['Signal'].abs().sum() == 0:
            self.data['Signal'] = 0
            self.data.loc[
            (self.data['close'] > self.data['EMA3']) &
            (self.data['EMA3'] > self.data['EMA8']) &
            (self.data['RSI_2'] > 35) & (self.data['RSI_2'] < 75) &
            (self.data['Momentum'] > 0) &
            (self.data['Pullback']),
            'Signal'
            ] = 1
            self.data.loc[
            (self.data['close'] < self.data['EMA3']) &
            (self.data['EMA3'] < self.data['EMA8']) &
            (self.data['RSI_2'] < 65) & (self.data['RSI_2'] > 25) &
            (self.data['Momentum'] < 0) &
            (self.data['Reset']),
            'Signal'
            ] = -1

        return self.data


class MultiTimeframeStrategy:
    def __init__(self, data_15m, data_1h):
        """
        Enhanced strategy class with complete indicator calculation
        data_15m: DataFrame with 15-minute OHLCV data (must contain close_time)
        data_1h: DataFrame with 1-hour OHLCV data (must contain close_time)
        """
        # Clean and prepare data
        self.data_15m = self._prepare_data(data_15m.copy(), '15m')
        self.data_1h = self._prepare_data(data_1h.copy(), '1h')
        
    def _prepare_data(self, df, timeframe):
        """Prepare and validate data"""
        # Check essential columns
        essential_cols = ['open', 'high', 'low', 'close', 'volume', 'close_time']
        missing_cols = [col for col in essential_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing columns in {timeframe} data: {missing_cols}")
        
        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df['close_time']):
            df['close_time'] = pd.to_datetime(df['close_time'])
        
        # Clean data
        df_clean = df.dropna(subset=essential_cols, how='any')
        df_clean = df_clean[df_clean['volume'] > 0]
        df_clean = df_clean.sort_values('close_time')
        
        # Validate
        if df_clean.empty:
            raise ValueError(f"{timeframe} data is empty after cleaning")
        if len(df_clean) < 50:
            print(f"Warning: {timeframe} data has only {len(df_clean)} points")
            
        return df_clean.reset_index(drop=True)
    
    def calculate_15m_indicators(self):
        """Calculate 15m timeframe indicators"""
        df = self.data_15m
        
        # EMAs
        df['EMA9_15m'] = EMAIndicator(df['close'], 9).ema_indicator()
        df['EMA21_15m'] = EMAIndicator(df['close'], 21).ema_indicator()
        
        # MACD (requires minimum 26 periods)
        if len(df) >= 26:
            macd = MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
            df['MACD_15m'] = macd.macd()
            df['MACD_Signal_15m'] = macd.macd_signal()
            df['MACD_Hist_15m'] = macd.macd_diff()
        else:
            df[['MACD_15m', 'MACD_Signal_15m', 'MACD_Hist_15m']] = np.nan
        
        # RSI (requires minimum 14 periods)
        df['RSI_14_15m'] = RSIIndicator(df['close'], 14).rsi() if len(df) >= 14 else np.nan
        
        # ATR (requires minimum 14 periods)
        df['ATR_15m'] = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14
        ).average_true_range() if len(df) >= 14 else np.nan
        
        return df.dropna().copy()
        
    def calculate_1h_indicators(self):
        """Calculate 1h timeframe indicators"""
        df = self.data_1h
        
        # EMAs
        df['EMA20_1h'] = EMAIndicator(df['close'], 20).ema_indicator()
        df['EMA50_1h'] = EMAIndicator(df['close'], 50).ema_indicator()
        df['EMA200_1h'] = EMAIndicator(df['close'], 200).ema_indicator() if len(df) >= 200 else np.nan
        
        # MACD
        if len(df) >= 26:
            macd = MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
            df['MACD_1h'] = macd.macd()
            df['MACD_Signal_1h'] = macd.macd_signal()
            df['MACD_Hist_1h'] = macd.macd_diff()
        else:
            df[['MACD_1h', 'MACD_Signal_1h', 'MACD_Hist_1h']] = np.nan
        
        # RSI
        df['RSI_14_1h'] = RSIIndicator(df['close'], 14).rsi() if len(df) >= 14 else np.nan
        df['RSI_7_1h'] = RSIIndicator(df['close'], 7).rsi() if len(df) >= 7 else np.nan
        
        # ATR
        df['ATR_1h'] = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14
        ).average_true_range() if len(df) >= 14 else np.nan
        
        return df.dropna().copy()
        
    def calculate_all_indicators(self):
        """Calculate indicators for both timeframes"""
        df_15m = self.calculate_15m_indicators()
        df_1h = self.calculate_1h_indicators()
        
        if df_15m.empty or df_1h.empty:
            raise ValueError("Insufficient data after indicator calculation")

        return df_15m, df_1h

# Usage Example:

"""
if __name__ == "__main__":
# Assuming you have data_15m and data_1h DataFrames
strategy = MultiTimeframeStrategy(data_15m, data_1h)
data_15m_indicators, data_1h_indicators = strategy.calculate_all_indicators()

print("15m Data with Indicators:")
print(data_15m_indicators[['close_time', 'close', 'EMA9_15m', 'EMA21_15m', 'RSI_14_15m']].tail())

print("\n1h Data with Indicators:")
print(data_1h_indicators[['close_time', 'close', 'EMA20_1h', 'EMA50_1h', 'RSI_14_1h']].tail())

"""