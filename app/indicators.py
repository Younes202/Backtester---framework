from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volume import VolumeWeightedAveragePrice
from ta.volatility import BollingerBands
import pandas as pd
import talib
import numpy as np
from ta.volatility import AverageTrueRange

class Strategy:
    def __init__(self, data, timeframe_type):
        self.data = data.copy()
        self.timeframe_type = timeframe_type
        self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])

    def calculate_indicators(self):
        self.data['EMA50'] = EMAIndicator(close=self.data['close'], window=50).ema_indicator() if len(self.data) >= 50 else np.nan
        self.data['EMA200'] = EMAIndicator(close=self.data['close'], window=200).ema_indicator() if len(self.data) >= 200 else np.nan
        self.data['RSI'] = RSIIndicator(close=self.data['close'], window=14).rsi() if len(self.data) >= 14 else np.nan
        
        if len(self.data) >= 12:  # MACD needs at least window_slow periods
            macd = MACD(close=self.data['close'], window_slow=12, window_fast=6, window_sign=5)
            self.data['MACD'] = macd.macd()
            self.data['MACD_Signal'] = macd.macd_signal()
        else:
            self.data['MACD'] = np.nan
            self.data['MACD_Signal'] = np.nan
        
        if len(self.data) >= 14:
            self.data['ADX'] = ADXIndicator(high=self.data['high'], low=self.data['low'], close=self.data['close'], window=14).adx()
        else:
            self.data['ADX'] = np.nan
        
        if len(self.data) >= 20:
            bb = BollingerBands(close=self.data['close'], window=20, window_dev=2)
            self.data['BB_Width'] = bb.bollinger_hband() - bb.bollinger_lband()
        else:
            self.data['BB_Width'] = np.nan

        if all(col in self.data.columns for col in ['high', 'low', 'close', 'volume']):
            self.data['VWAP'] = VolumeWeightedAveragePrice(
                high=self.data['high'], low=self.data['low'],
                close=self.data['close'], volume=self.data['volume'], window=20
            ).volume_weighted_average_price()

        self.data['Volume_OK'] = self.data['volume'] > self.data['volume'].rolling(20).mean()
        self.data['Volatility_OK'] = self.data['BB_Width'] > self.data['BB_Width'].rolling(20).mean()
        self.data['Trend_Strength'] = self.data['ADX'] > 20
        self.data['Bullish_Engulfing'] = talib.CDLENGULFING(
            self.data['open'], self.data['high'], self.data['low'], self.data['close']
        ) > 0

        return self.data

    def detect_fvg(self):
        self.data['FVG'] = (
            (self.data['low'].shift(1) > self.data['high'].shift(-1)) |
            (self.data['high'].shift(1) < self.data['low'].shift(-1))
        )
        return self.data

    def detect_cisd(self):
        self.data['Higher_High'] = self.data['high'] > self.data['high'].shift(1)
        self.data['Higher_Low'] = self.data['low'] > self.data['low'].shift(1)
        self.data['Bullish_Structure'] = self.data['Higher_High'] & self.data['Higher_Low']
        self.data['Lower_High'] = self.data['high'] < self.data['high'].shift(1)
        self.data['Lower_Low'] = self.data['low'] < self.data['low'].shift(1)
        self.data['Bearish_Structure'] = self.data['Lower_High'] & self.data['Lower_Low']
        self.data['atr'] = talib.ATR(self.data['high'], self.data['low'], self.data['close'], timeperiod=14)
        return self.data

    def generate_signals(self):
        self.calculate_indicators()
        self.detect_fvg()
        self.detect_cisd()
        self.data['Signal'] = 0



        if self.timeframe_type == '1h':
            # Bullish: 1, Bearish: -1, None: 0
            self.data['Signal'] = np.where(
                self.data['Bullish_Structure'] &
                (self.data['MACD'] > self.data['MACD_Signal']) &
                (self.data['RSI'].diff() > 0),
                1,
                np.where(
                    self.data['Bearish_Structure'] &
                    (self.data['MACD'] < self.data['MACD_Signal']) &
                    (self.data['RSI'].diff() < 0),
                    -1,
                    0
                )
            )

        elif self.timeframe_type == '15m':
            # Bullish: 1, Bearish: -1, None: 0
            self.data['Signal'] = np.where(
                (self.data['close'] > self.data['EMA50']) &
                (self.data['Bullish_Structure']) &
                (self.data['MACD'] > self.data['MACD_Signal']) &
                (self.data['atr'] < self.data['atr'].rolling(20).mean()),
                1,
                np.where(
                    (self.data['close'] < self.data['EMA50']) &
                    (self.data['Bearish_Structure']) &
                    (self.data['MACD'] < self.data['MACD_Signal']) &
                    (self.data['atr'] < self.data['atr'].rolling(20).mean()),
                    -1,
                    0
                )
            )

        return self.data
        

class SwingStrategy:
    def __init__(self, data, timeframe_type):
        self.data = data.copy()
        self.timeframe_type = timeframe_type
        self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
        
        # Initialize all indicator columns
        self.data['EMA50'] = np.nan
        self.data['EMA200'] = np.nan
        self.data['RSI'] = np.nan
        self.data['MACD'] = np.nan
        self.data['MACD_Signal'] = np.nan
        self.data['ADX'] = np.nan
        self.data['BB_Width'] = np.nan
        self.data['VWAP'] = np.nan
        self.data['Volume_OK'] = False
        self.data['Volatility_OK'] = False
        self.data['Trend_Strength'] = False
        self.data['Bullish_Engulfing'] = False
        self.data['FVG'] = False
        self.data['Higher_High'] = False
        self.data['Higher_Low'] = False
        self.data['Bullish_Structure'] = False
        self.data['Lower_High'] = False
        self.data['Lower_Low'] = False
        self.data['Bearish_Structure'] = False
        self.data['atr'] = np.nan
        
        # Price action columns
        self.data['swing_high'] = np.nan
        self.data['swing_low'] = np.nan
        self.data['pullback_zone'] = False
        self.data['breakout_confirmed'] = False

    def calculate_indicators(self):
        """Calculate all technical indicators using talib"""
        # EMAs
        if len(self.data) >= 50:
            self.data['EMA50'] = talib.EMA(self.data['close'], timeperiod=50)
        if len(self.data) >= 200:
            self.data['EMA200'] = talib.EMA(self.data['close'], timeperiod=200)
        
        # RSI
        if len(self.data) >= 14:
            self.data['RSI'] = talib.RSI(self.data['close'], timeperiod=14)
        
        # MACD
        if len(self.data) >= 26:  # Slow EMA period
            macd, macdsignal, macdhist = talib.MACD(self.data['close'], fastperiod=12, slowperiod=26, signalperiod=9)
            self.data['MACD'] = macd
            self.data['MACD_Signal'] = macdsignal
        
        # ADX
        if len(self.data) >= 14:
            self.data['ADX'] = talib.ADX(self.data['high'], self.data['low'], self.data['close'], timeperiod=14)
        
        # Bollinger Bands
        if len(self.data) >= 20:
            upper, middle, lower = talib.BBANDS(self.data['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
            self.data['BB_Width'] = upper - lower
        
        # VWAP (manual calculation)
        if all(col in self.data.columns for col in ['high', 'low', 'close', 'volume']):
            typical_price = (self.data['high'] + self.data['low'] + self.data['close']) / 3
            vwap = (typical_price * self.data['volume']).rolling(window=20, min_periods=1).sum() / self.data['volume'].rolling(window=20, min_periods=1).sum()
            self.data['VWAP'] = vwap
        
        # Volume and volatility conditions
        if len(self.data) >= 20:
            self.data['Volume_OK'] = self.data['volume'] > self.data['volume'].rolling(20).mean()
            self.data['Volatility_OK'] = self.data['BB_Width'] > self.data['BB_Width'].rolling(20).mean()
        
        # Trend strength
        self.data['Trend_Strength'] = self.data['ADX'] > 20
        
        # Candlestick patterns
        self.data['Bullish_Engulfing'] = talib.CDLENGULFING(self.data['open'], self.data['high'], self.data['low'], self.data['close']) > 0
        
        # FVG detection
        self.data['FVG'] = (
            (self.data['low'].shift(1) > self.data['high'].shift(-1)) |
            (self.data['high'].shift(1) < self.data['low'].shift(-1))
        )

        # Market structure
        self.data['Higher_High'] = self.data['high'] > self.data['high'].shift(1)
        self.data['Higher_Low'] = self.data['low'] > self.data['low'].shift(1)
        self.data['Bullish_Structure'] = self.data['Higher_High'] & self.data['Higher_Low']
        self.data['Lower_High'] = self.data['high'] < self.data['high'].shift(1)
        self.data['Lower_Low'] = self.data['low'] < self.data['low'].shift(1)
        self.data['Bearish_Structure'] = self.data['Lower_High'] & self.data['Lower_Low']
        
        # ATR
        if len(self.data) >= 14:
            self.data['atr'] = talib.ATR(self.data['high'], self.data['low'], self.data['close'], timeperiod=14)
        
        return self.data

    def calculate_swings(self, window=3):
        """Identify swing highs/lows for pullback detection"""
        self.data['swing_high'] = self.data['high'].rolling(window).apply(
            lambda x: x.iloc[1] if (x.iloc[1] == x.max()) else np.nan, raw=False
        )
        self.data['swing_low'] = self.data['low'].rolling(window).apply(
            lambda x: x.iloc[1] if (x.iloc[1] == x.min()) else np.nan, raw=False
        )
        return self.data

    def detect_pullback_zones(self):
        """Mark valid pullback/retest areas"""
        self.data['pullback_zone'] = (
            # Uptrend pullback condition
            ((self.data['close'] > self.data['EMA200']) & 
                (self.data['low'] <= self.data['EMA50']) & 
                (self.data['low'].shift(1) > self.data['EMA50'])) |
            
            # Downtrend retest condition
            ((self.data['close'] < self.data['EMA200']) & 
                (self.data['high'] >= self.data['EMA50']) & 
                (self.data['high'].shift(1) < self.data['EMA50']))
        )
        return self.data

    def confirm_breakouts(self):
        """Validate breakouts from consolidation"""
        self.data['breakout_confirmed'] = (
            # Bullish breakout
            ((self.data['close'] > self.data['swing_high'].shift(1)) &
                (self.data['volume'] > self.data['volume'].rolling(5).mean())) |
            
            # Bearish breakout
            ((self.data['close'] < self.data['swing_low'].shift(1)) &
                (self.data['volume'] > self.data['volume'].rolling(5).mean()))
        )
        return self.data

    def generate_signals(self):
        self.calculate_indicators()
        self.calculate_swings()
        self.detect_pullback_zones()
        self.confirm_breakouts()
        
        if self.timeframe_type == '1h':
            # Enhanced 1H signal with price action filters
            self.data['Signal'] = np.where(
                (self.data['Bullish_Structure']) &
                (self.data['MACD'] > self.data['MACD_Signal']) &
                (self.data['pullback_zone']) &  # New filter
                (self.data['close'] > self.data['EMA50']),  # Breakout confirmation
                1,
                np.where(
                    (self.data['Bearish_Structure']) &
                    (self.data['MACD'] < self.data['MACD_Signal']) &
                    (self.data['pullback_zone']) &  # New filter
                    (self.data['close'] < self.data['EMA50']),  # Breakdown confirmation
                    -1,
                    0
                )
            )

        elif self.timeframe_type == '15m':
            # Enhanced 15M signal with tighter entry logic
            self.data['Signal'] = np.where(
                (self.data['close'] > self.data['EMA50']) &
                (self.data['Bullish_Structure']) &
                (self.data['pullback_zone']) &  # Must be in pullback zone
                (self.data['breakout_confirmed']) &  # New breakout confirmation
                (self.data['atr'] < self.data['atr'].rolling(20).mean()),
                1,
                np.where(
                    (self.data['close'] < self.data['EMA50']) &
                    (self.data['Bearish_Structure']) &
                    (self.data['pullback_zone']) &  # Must be in retest zone
                    (self.data['breakout_confirmed']) &  # New breakdown confirmation
                    (self.data['atr'] < self.data['atr'].rolling(20).mean()),
                    -1,
                    0
                )
            )
        return self.data





""""
if self.timeframe_type == '1d':
    # Bullish: 1, Bearish: -1, None: 0
    self.data['Signal'] = np.where(
        (self.data['EMA50'] > self.data['EMA200']) &
        (self.data['RSI'] > 55) &
        (self.data['MACD'] > self.data['MACD_Signal']),
        1,
        np.where(
            (self.data['EMA50'] < self.data['EMA200']) &
            (self.data['RSI'] < 45) &
            (self.data['MACD'] < self.data['MACD_Signal']),
            -1,
            0
        )
    )
"""

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
        return self.data

    def generate_signals(self):
        self.calculate_indicators()
        self.data['Signal'] = 0

        # LONG: Price above both EMAs, RSI_2 rising but not overbought, momentum positive, volume active, low chop
        self.data.loc[
            (self.data['close'] > self.data['EMA3']) &
            (self.data['EMA3'] > self.data['EMA8']) &
            (self.data['RSI_2'] > 35) & (self.data['RSI_2'] < 75) &
            (self.data['RSI_2'] > self.data['RSI_2'].shift(1)) &
            (self.data['Momentum'] > 0) &
            (self.data['Volume_Active']) &
            (self.data['Small_Range']),
            'Signal'
        ] = 1

        # SHORT: Price below both EMAs, RSI_2 falling but not oversold, momentum negative, volume active, low chop
        self.data.loc[
            (self.data['close'] < self.data['EMA3']) &
            (self.data['EMA3'] < self.data['EMA8']) &
            (self.data['RSI_2'] < 65) & (self.data['RSI_2'] > 25) &
            (self.data['RSI_2'] < self.data['RSI_2'].shift(1)) &
            (self.data['Momentum'] < 0) &
            (self.data['Volume_Active']) &
            (self.data['Small_Range']),
            'Signal'
        ] = -1

        # If still no signals, relax volume and range filters
        if self.data['Signal'].abs().sum() == 0:
            self.data['Signal'] = 0
            self.data.loc[
                (self.data['close'] > self.data['EMA3']) &
                (self.data['EMA3'] > self.data['EMA8']) &
                (self.data['RSI_2'] > 35) & (self.data['RSI_2'] < 75) &
                (self.data['Momentum'] > 0),
                'Signal'
            ] = 1
            self.data.loc[
                (self.data['close'] < self.data['EMA3']) &
                (self.data['EMA3'] < self.data['EMA8']) &
                (self.data['RSI_2'] < 65) & (self.data['RSI_2'] > 25) &
                (self.data['Momentum'] < 0),
                'Signal'
            ] = -1

        # Final check
        if self.data['Signal'].abs().sum() == 0:
            print("❌ CRITICAL: Still no signals - check data/indicators")
            print(self.data[['timestamp','close','EMA3','EMA8','RSI_2','Momentum']].tail(10))

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