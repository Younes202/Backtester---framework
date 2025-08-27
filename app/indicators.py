from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volume import VolumeWeightedAveragePrice
from ta.volatility import BollingerBands
import pandas as pd
import talib
import numpy as np
from ta.volatility import AverageTrueRange
from numba import cuda

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
        
        # Reset signal column
        self.data['Signal'] = 0
        
        # Common conditions for all timeframes
        bullish_conditions = (
            (self.data['EMA50'] > self.data['EMA200']) &
            (self.data['MACD'] > self.data['MACD_Signal']) &
            (self.data['Trend_Strength'])  # ADX > 20
        )
        
        bearish_conditions = (
            (self.data['EMA50'] < self.data['EMA200']) &
            (self.data['MACD'] < self.data['MACD_Signal']) &
            (self.data['Trend_Strength'])  # ADX > 20
        )

        # Timeframe-specific adjustments
        if self.timeframe_type == '4h':
            # 4h timeframe - bias detection
            self.data['Signal'] = np.where(
                bullish_conditions & (self.data['ADX'] > 25),
                1,  # Strong bullish bias
                np.where(
                    bearish_conditions & (self.data['ADX'] > 25),
                    -1,  # Strong bearish bias
                    0    # Neutral
                )
            )
        
        elif self.timeframe_type == '1h':
            # 1h timeframe - confirmation
            self.data['Signal'] = np.where(
                bullish_conditions & 
                (self.data['RSI'] > 50) & 
                (self.data['Volume_OK']),
                1,  # Long confirmation
                np.where(
                    bearish_conditions & 
                    (self.data['RSI'] < 50) & 
                    (self.data['Volume_OK']),
                    -1,  # Short confirmation
                    0    # No confirmation
                )
            )
        
        elif self.timeframe_type == '15m':
            # 15m timeframe - entries
            self.data['Signal'] = np.where(
                bullish_conditions & 
                (self.data['Bullish_Structure']) & 
                (self.data['Volatility_OK']),
                1,  # Long entry
                np.where(
                    bearish_conditions & 
                    (self.data['Bearish_Structure']) & 
                    (self.data['Volatility_OK']),
                    -1,  # Short entry
                    0    # No entry
                )
            )
        
        elif self.timeframe_type == '1m':
            # 1m timeframe - only calculate ATR
            self.data['atr'] = talib.ATR(self.data['high'], self.data['low'], 
                                    self.data['close'], timeperiod=14)
        
        return self.data

class DayTradingStrategy:
    def __init__(self, data):
        self.data = data.copy()
        # Use 'timestamp' if present, else fallback to 'close_time'
        if 'timestamp' in self.data.columns:
            self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
        elif 'close_time' in self.data.columns:
            self.data['timestamp'] = pd.to_datetime(self.data['close_time'])

    def calculate_indicators(self):
        # Moving Averages
        self.data['EMA50'] = EMAIndicator(close=self.data['close'], window=50).ema_indicator() if len(self.data) >= 50 else np.nan
        self.data['EMA200'] = EMAIndicator(close=self.data['close'], window=200).ema_indicator() if len(self.data) >= 200 else np.nan
        # RSI
        self.data['RSI'] = RSIIndicator(close=self.data['close'], window=14).rsi() if len(self.data) >= 14 else np.nan
        # VWAP
        if all(col in self.data.columns for col in ['high', 'low', 'close', 'volume']):
            self.data['VWAP'] = VolumeWeightedAveragePrice(
                high=self.data['high'], low=self.data['low'],
                close=self.data['close'], volume=self.data['volume'], window=20
            ).volume_weighted_average_price()
        else:
            self.data['VWAP'] = np.nan
        # Support/Resistance
        self.data['Support'] = self.data['low'].rolling(window=20, min_periods=1).min()
        self.data['Resistance'] = self.data['high'].rolling(window=20, min_periods=1).max()
        # ATR for 1m timeframe
        self.data['atr'] = talib.ATR(self.data['high'], self.data['low'], self.data['close'], timeperiod=14)
        # Candle patterns (confirmation metric)
        self.data['Bullish_Engulfing'] = talib.CDLENGULFING(
            self.data['open'], self.data['high'], self.data['low'], self.data['close']
        ) > 0
        self.data['Bearish_Engulfing'] = talib.CDLENGULFING(
            self.data['open'], self.data['high'], self.data['low'], self.data['close']
        ) < 0
        self.data['Hammer'] = talib.CDLHAMMER(
            self.data['open'], self.data['high'], self.data['low'], self.data['close']
        ) > 0
        self.data['ShootingStar'] = talib.CDLSHOOTINGSTAR(
            self.data['open'], self.data['high'], self.data['low'], self.data['close']
        ) > 0

        # Advanced candle patterns (shoulders, head-and-shoulders, etc.)
        # Simple shoulder detection: local maxima/minima for head and shoulders
        self.data['LeftShoulder'] = (self.data['high'].shift(2) < self.data['high'].shift(1)) & (self.data['high'].shift(1) < self.data['high']) & (self.data['high'] > self.data['high'].shift(-1)) & (self.data['high'].shift(-1) > self.data['high'].shift(-2))
        self.data['Head'] = (self.data['high'] > self.data['high'].shift(1)) & (self.data['high'] > self.data['high'].shift(-1))
        self.data['RightShoulder'] = (self.data['high'].shift(-2) < self.data['high'].shift(-1)) & (self.data['high'].shift(-1) < self.data['high']) & (self.data['high'] > self.data['high'].shift(1)) & (self.data['high'].shift(1) > self.data['high'].shift(2))
        # Inverse head and shoulders (for lows)
        self.data['InverseLeftShoulder'] = (self.data['low'].shift(2) > self.data['low'].shift(1)) & (self.data['low'].shift(1) > self.data['low']) & (self.data['low'] < self.data['low'].shift(-1)) & (self.data['low'].shift(-1) < self.data['low'].shift(-2))
        self.data['InverseHead'] = (self.data['low'] < self.data['low'].shift(1)) & (self.data['low'] < self.data['low'].shift(-1))
        self.data['InverseRightShoulder'] = (self.data['low'].shift(-2) > self.data['low'].shift(-1)) & (self.data['low'].shift(-1) > self.data['low']) & (self.data['low'] < self.data['low'].shift(1)) & (self.data['low'].shift(1) < self.data['low'].shift(2))

        # --- Pullback and Breakout Concepts ---
        # Breakout above resistance: close > previous resistance
        self.data['Breakout_Long'] = self.data['close'] > self.data['Resistance'].shift(1)
        # Breakout below support: close < previous support
        self.data['Breakout_Short'] = self.data['close'] < self.data['Support'].shift(1)
        # Pullback to support: price drops to support after being above resistance
        self.data['Pullback_Long'] = (
            (self.data['close'].shift(1) > self.data['Resistance'].shift(1)) &
            (self.data['close'] < self.data['Support'])
        )
        # Pullback to resistance: price rises to resistance after being below support
        self.data['Pullback_Short'] = (
            (self.data['close'].shift(1) < self.data['Support'].shift(1)) &
            (self.data['close'] > self.data['Resistance'])
        )

        return self.data

    def generate_signals(self):
        self.calculate_indicators()
        self.data['Signal'] = 0

        # Trend bias
        bullish_bias = (self.data['EMA50'] > self.data['EMA200'])
        bearish_bias = (self.data['EMA50'] < self.data['EMA200'])

        # Candle pattern confirmation
        bullish_candle = (
            self.data['Bullish_Engulfing'] |
            self.data['Hammer'] |
            self.data['InverseHead'] | (self.data['InverseLeftShoulder'] & self.data['InverseRightShoulder'])
        )
        bearish_candle = (
            self.data['Bearish_Engulfing'] |
            self.data['ShootingStar'] |
            self.data['Head'] | (self.data['LeftShoulder'] & self.data['RightShoulder'])
        )

        # Buy confirmation: RSI < 30, EMA50 > EMA200, price above VWAP, breakout above resistance or pullback to support, plus bullish candle pattern
        buy_condition = (
            (self.data['RSI'] < 30) &
            bullish_bias &
            (self.data['close'] > self.data['VWAP']) &
            (
                self.data['Breakout_Long'] |  # breakout above resistance
                self.data['Pullback_Long']    # pullback to support
            ) &
            bullish_candle
        )

        # Sell confirmation: RSI > 70, EMA50 < EMA200, price below VWAP, breakout below support or pullback to resistance, plus bearish candle pattern
        sell_condition = (
            (self.data['RSI'] > 70) &
            bearish_bias &
            (self.data['close'] < self.data['VWAP']) &
            (
                self.data['Breakout_Short'] |  # breakout below support
                self.data['Pullback_Short']    # pullback to resistance
            ) &
            bearish_candle
        )

        self.data['Signal'] = np.where(
            buy_condition, 1,
            np.where(
                sell_condition, -1, 0
            )
        )

        # If last signal is always 0, relax conditions for edge cases
        if self.data['Signal'].iloc[-1] == 0:
            # Try a simple momentum-based fallback
            if len(self.data) > 1:
                if self.data['close'].iloc[-1] > self.data['close'].iloc[-2]:
                    self.data.loc[self.data.index[-1], 'Signal'] = 1
                elif self.data['close'].iloc[-1] < self.data['close'].iloc[-2]:
                    self.data.loc[self.data.index[-1], 'Signal'] = -1

        return self.data


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