from loguru import logger

from loguru import logger

class RiskManagementFutures:
    def __init__(self, entry_price, current_price, risk_percent, profit_percent, atr, position_type, leverage, initial_margin, fees=0.0002):
        """
        Enhanced Binance USDT Perpetual Futures Risk Management with precise fee handling
        position_type: 1 (long) or -1 (short)
        fees: 0.0002 for Binance maker (0.02%)
        """
        self.raw_entry = entry_price  # Price without fees
        self.current_price = current_price
        self.risk_percent = risk_percent / 100
        self.profit_percent = profit_percent / 100
        self.leverage = leverage
        self.initial_margin = initial_margin
        self.atr = atr
        self.fees = fees
        self.position_type = 1 if position_type == 1 else -1
        self.maintenance_margin = 0.005  # Binance USDT-M default
        
        # Effective entry price after fees
        self.effective_entry = (self.raw_entry * (1 + self.fees) if self.position_type == 1 else self.raw_entry * (1 - self.fees))
        
        self._validate_parameters()
        self.position_size = (initial_margin * leverage) / self.raw_entry
        self.trade_risk = initial_margin * self.risk_percent
        self._calculate_liquidation_price()
        
        logger.info(f"Position initialized: {'LONG' if self.position_type == 1 else 'SHORT'} {self.position_size:.4f} contracts")
        logger.info(f"Effective entry: ${self.effective_entry:.2f} (incl. fees)")
        logger.info(f"Risk: ${self.trade_risk:.2f} | Liq: ${self.liquidation_price:.2f}")

    def _validate_parameters(self):
        """Validate all inputs"""
        if self.position_type not in [1, -1]:
            raise ValueError("Position type must be 1 (long) or -1 (short)")
        if self.leverage <= 0 or self.initial_margin <= 0:
            raise ValueError("Leverage and margin must be positive")
        if not 0 <= self.fees < 0.1:  # Reasonable fee check
            raise ValueError("Fees must be between 0% and 10%")

    def _calculate_liquidation_price(self):
        """Precise liquidation price with fee-adjusted entry"""
        if self.position_type == 1:
            self.liquidation_price = self.effective_entry * (1 - (1/self.leverage) + self.maintenance_margin)
        else:
            self.liquidation_price = self.effective_entry * (1 + (1/self.leverage) - self.maintenance_margin)

    def calculate_pnl(self, exit_price):
        """Exact PnL calculation with fees on both sides"""
        exit_price_net = exit_price * (1 - self.fees) if self.position_type == 1 else exit_price * (1 + self.fees)
        
        if self.position_type == 1:
            return (exit_price_net - self.effective_entry) * self.position_size
        else:
            return (self.effective_entry - exit_price_net) * self.position_size

    def calculate_take_profit_price(self):
        """Returns exact market price needed to hit profit target after all fees"""
        target_profit = self.initial_margin * self.profit_percent
        
        if self.position_type == 1:
            # For longs: (exit*(1-fee) - entry*(1+fee)) * size = target
            return (target_profit/self.position_size + self.effective_entry) / (1 - self.fees)
        else:
            # For shorts: (entry*(1-fee) - exit*(1+fee)) * size = target
            return (self.effective_entry - target_profit/self.position_size) / (1 + self.fees)

    def calculate_stop_loss_price(self):
        """Returns exact price where loss equals risk% after fees"""
        max_loss = abs(self.initial_margin * self.risk_percent)
        
        if self.position_type == 1:
            # (exit*(1-fee) - entry*(1+fee)) * size = -max_loss
            return (self.effective_entry - max_loss/self.position_size) / (1 - self.fees)
        else:
            # (entry*(1-fee) - exit*(1+fee)) * size = -max_loss
            return (self.effective_entry + max_loss/self.position_size) / (1 + self.fees)

    def should_exit(self):
        """Comprehensive exit check with precise calculations"""
        if (self.position_type == 1 and self.current_price <= self.liquidation_price) or \
           (self.position_type == -1 and self.current_price >= self.liquidation_price):
            pnl = self.calculate_pnl(self.current_price)
            print(f"💥 LIQUIDATED at {self.current_price:.2f}! Loss: ${abs(pnl):.2f}")
            return "LIQUIDATION"

        tp_price = self.calculate_take_profit_price()
        sl_price = self.calculate_stop_loss_price()

        if self.position_type == 1:
            if self.current_price >= tp_price:
                pnl = self.calculate_pnl(self.current_price)
                print(f"🟢 TP HIT: {self.current_price:.2f} | Profit: ${pnl:.2f}")
                return "PROFIT"
            elif self.current_price <= sl_price:
                pnl = self.calculate_pnl(self.current_price)
                print(f"🔴 SL HIT: {self.current_price:.2f} | Loss: ${abs(pnl):.2f}")
                return "LOSS"
        else:  # Short position
            if self.current_price <= tp_price:
                pnl = self.calculate_pnl(self.current_price)
                print(f"🟢 TP HIT: {self.current_price:.2f} | Profit: ${pnl:.2f}")
                return "PROFIT"
            elif self.current_price >= sl_price:
                pnl = self.calculate_pnl(self.current_price)
                print(f"🔴 SL HIT: {self.current_price:.2f} | Loss: ${abs(pnl):.2f}")
                return "LOSS"

        # Show running PnL
        current_pnl = self.calculate_pnl(self.current_price)
        status = "PROFIT" if current_pnl >= 0 else "LOSS"
        print(f"⏳ Current: ${current_pnl:.2f} ({status}) | TP: {tp_price:.2f} | SL: {sl_price:.2f}")
        return False

class RiskManagement:
    def __init__(self, priceorder, currentprice, target_profit, stoploss, dollar_investment, atr, fees=0.1):
        self.priceorder = priceorder        # Entry price (buy price)
        self.currentprice = currentprice    # Current market price
        self.target_profit = target_profit  # Target profit percentage (entered manually)
        self.stoploss = stoploss            # Stop-loss percentage
        self.dollar_investment = dollar_investment  # Amount invested in dollars
        self.atr = atr                      # Average True Range (ATR)
        self.fees = fees / 100              # Trading fee as a decimal (e.g., 0.1% = 0.001)
        self.profit_or_loss = None          # Will be set when exit condition is triggered

    def calculate_price_from_target(self):
        """  
        Calculates the target price based on the provided target profit.
        Considers trading fees on both entry and exit.
        """
        # Target price adjusted for trading fees
        target_price = self.priceorder * (1 + self.target_profit / 100)
        target_price_after_fees = target_price * (1 + self.fees)  # Adjust for exit fees
        logger.info(f"Target price after including fees: {target_price_after_fees:.2f}")
        return target_price_after_fees

    def calculate_dollar_profit(self, target_price):
        """Calculates the dollar profit based on the target price."""
        # Number of units purchased
        units = self.dollar_investment / self.priceorder
        # Profit per unit
        profit_per_unit = target_price - self.priceorder
        # Total profit in dollars
        dollar_profit = profit_per_unit * units
        return dollar_profit

    def target_profit_exit(self):
        """Exit based on the target profit, adjusted by ATR."""
        target_price = self.calculate_price_from_target()  # Calculate target price after fees
        adjusted_target_price = target_price + (self.atr * 0.5)  # Adjust target based on ATR (can change multiplier)
        logger.info(f"Checking target profit exit condition at adjusted price: {adjusted_target_price:.2f}")

        if self.currentprice >= adjusted_target_price:
            # Calculate profit in dollars
            dollar_profit = self.calculate_dollar_profit(adjusted_target_price)
            total_dollars_after_profit = self.dollar_investment + dollar_profit
            self.profit_or_loss = dollar_profit  # Store the profit
            logger.info(f"Adjusted target price reached: {self.currentprice:.2f}. Profit: ${dollar_profit:.2f}. Total after profit: ${total_dollars_after_profit:.2f}. Exiting position.")
            return dollar_profit, total_dollars_after_profit
        return None, None

    def stop_loss_exit(self):
        """Exit based on stop-loss level, adjusted by ATR."""
        stop_loss_price = self.priceorder - (self.priceorder * (self.stoploss / 100))
        adjusted_stop_loss_price = stop_loss_price - (self.atr * 0.5)  # Adjust stop-loss based on ATR
        if self.currentprice <= adjusted_stop_loss_price:
            units = self.dollar_investment / self.priceorder
            loss_per_unit = self.priceorder - self.currentprice
            dollar_loss = loss_per_unit * units
            total_dollars_after_loss = self.dollar_investment - dollar_loss
            self.profit_or_loss = -dollar_loss  # Store the loss
            logger.info(f"Adjusted stop-loss price reached: {self.currentprice:.2f}. Loss: ${dollar_loss:.2f}. Total after loss: ${total_dollars_after_loss:.2f}. Exiting position.")
            return True
        return False

    def should_exit(self):
        """Main function to determine if any exit condition is met."""
        if self.stop_loss_exit():
            logger.info("Exiting position due to stop-loss condition.")
            return True  # Exit due to stop-loss condition
        
        dollar_profit, total_dollars = self.target_profit_exit()
        if dollar_profit is not None:
            logger.info(f"Exiting position due to reaching target profit of {self.target_profit:.2f}%. Profit: ${dollar_profit:.2f}. Total: ${total_dollars:.2f}")
            return True  # Exit due to reaching target profit

        return False  # No exit condition met, hold the position


class MultiTimeframeRiskManager:
    def __init__(
        self,
        entry_price,
        current_price,
        dollar_investment,
        target_profit_pct,
        stop_loss_pct,
        atr_1d,
        atr_1h,
        atr_15m,
        atr_weighting=None  # dict like {'1d':0.5, '1h':0.3, '15m':0.2}
    ):
        self.entry_price = entry_price
        self.current_price = current_price
        self.dollar_investment = dollar_investment
        self.target_profit_pct = target_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.atr_1d = atr_1d
        self.atr_1h = atr_1h
        self.atr_15m = atr_15m

        # Default weighting if none given (equal weight)
        if atr_weighting is None:
            self.atr_weighting = {'1d': 0.5, '1h': 0.3, '15m': 0.2}
        else:
            self.atr_weighting = atr_weighting

        self.profit_or_loss = None

    def combined_atr(self):
        """Calculate combined ATR based on weighting"""
        combined = (
            self.atr_1d * self.atr_weighting.get('1d', 0) +
            self.atr_1h * self.atr_weighting.get('1h', 0) +
            self.atr_15m * self.atr_weighting.get('15m', 0)
        )
        return combined

    def calculate_stop_loss_price(self):
        """Calculate dynamic stop loss price using combined ATR"""
        combined_atr = self.combined_atr()
        sl_price_pct = self.stop_loss_pct / 100
        # Adjust stop loss by combined ATR (you can tune multiplier here)
        adjusted_sl = self.entry_price - (sl_price_pct * self.entry_price) - (combined_atr * 0.5)
        return adjusted_sl

    def calculate_take_profit_price(self):
        """Calculate dynamic take profit price using combined ATR"""
        combined_atr = self.combined_atr()
        tp_price_pct = self.target_profit_pct / 100
        # Adjust take profit by combined ATR (tune multiplier here)
        adjusted_tp = self.entry_price + (tp_price_pct * self.entry_price) + (combined_atr * 0.5)
        return adjusted_tp

    def check_stop_loss(self):
        sl_price = self.calculate_stop_loss_price()
        if self.current_price <= sl_price:
            self.profit_or_loss = (self.current_price - self.entry_price) * (self.dollar_investment / self.entry_price)
            return True
        return False

    def check_take_profit(self):
        tp_price = self.calculate_take_profit_price()
        if self.current_price >= tp_price:
            self.profit_or_loss = (self.current_price - self.entry_price) * (self.dollar_investment / self.entry_price)
            return True
        return False

    def should_exit(self):
        if self.check_stop_loss():
            return 'stop_loss', self.profit_or_loss
        elif self.check_take_profit():
            return 'take_profit', self.profit_or_loss
        else:
            return 'hold', None



class RiskManagementD:
    def __init__(self, priceorder, currentprice, stoploss, dollar_investment, atr, fees=0.1, dynamic_profit_multiplier=1.5):
        self.priceorder = priceorder        # Entry price (buy price)
        self.currentprice = currentprice    # Current market price
        self.stoploss = stoploss            # Stop-loss percentage
        self.dollar_investment = dollar_investment  # Amount invested in dollars
        self.atr = atr                      # Average True Range (ATR)
        self.fees = fees / 100              # Trading fee as a decimal (e.g., 0.1% = 0.001)
        self.dynamic_profit_multiplier = dynamic_profit_multiplier  # Multiplier for ATR-based dynamic target
        self.profit_or_loss = None          # Will be set when exit condition is triggered

    def calculate_price_from_target(self):
        """  
        Calculates the dynamic target price based on ATR and market conditions.
        Considers trading fees on both entry and exit.
        """
        # Target price dynamically adjusted using ATR
        dynamic_target_price = self.priceorder + (self.atr * self.dynamic_profit_multiplier)
        target_price_after_fees = dynamic_target_price * (1 + self.fees)  # Adjust for exit fees
        logger.info(f"Dynamic target price after including fees: {target_price_after_fees:.2f}")
        return target_price_after_fees

    def calculate_dollar_profit(self, target_price):
        """Calculates the dollar profit based on the dynamic target price."""
        # Number of units purchased
        units = self.dollar_investment / self.priceorder
        # Profit per unit
        profit_per_unit = target_price - self.priceorder
        # Total profit in dollars
        dollar_profit = profit_per_unit * units
        return dollar_profit

    def target_profit_exit(self):
        """Exit based on the dynamic profit target, adjusted by ATR."""
        target_price = self.calculate_price_from_target()  # Calculate dynamic target price after fees
        
        logger.info(f"Checking dynamic profit exit condition at adjusted price: {target_price:.2f}")

        if self.currentprice >= target_price:
            # Calculate profit in dollars
            dollar_profit = self.calculate_dollar_profit(target_price)
            total_dollars_after_profit = self.dollar_investment + dollar_profit
            self.profit_or_loss = dollar_profit  # Store the profit
            logger.info(f"Dynamic target price reached: {self.currentprice:.2f}. Profit: ${dollar_profit:.2f}. Total after profit: ${total_dollars_after_profit:.2f}. Exiting position.")
            return dollar_profit, total_dollars_after_profit
        return None, None

    def stop_loss_exit(self):
        """Exit based on stop-loss level, adjusted by ATR."""
        stop_loss_price = self.priceorder - (self.priceorder * (self.stoploss / 100))
        adjusted_stop_loss_price = stop_loss_price - (self.atr * 0.5)  # Adjust stop-loss based on ATR
        if self.currentprice <= adjusted_stop_loss_price:
            units = self.dollar_investment / self.priceorder
            loss_per_unit = self.priceorder - self.currentprice
            dollar_loss = loss_per_unit * units
            total_dollars_after_loss = self.dollar_investment - dollar_loss
            self.profit_or_loss = -dollar_loss  # Store the loss
            logger.info(f"Adjusted stop-loss price reached: {self.currentprice:.2f}. Loss: ${dollar_loss:.2f}. Total after loss: ${total_dollars_after_loss:.2f}. Exiting position.")
            return True
        return False
    

    def should_exit(self):
        """Main function to determine if any exit condition is met."""
        if self.stop_loss_exit():
            logger.info("Exiting position due to stop-loss condition.")
            return True  # Exit due to stop-loss condition
        
        dollar_profit, total_dollars = self.target_profit_exit()
        if dollar_profit is not None:
            logger.info(f"Exiting position due to reaching dynamic target profit. Profit: ${dollar_profit:.2f}. Total: ${total_dollars:.2f}")
            return True  # Exit due to reaching dynamic target profit

        return False  # No exit condition met, hold the position

# In your main code where you're checking for exit:



"""if __name__ == "__main__":
    # Example configuration
    risk_mgr = RiskManagement(
        entry_price=60390.8,
        current_price=63546.1,
        risk_percent=85,        # Risk 90% of initial margin
        profit_percent=50,      # Net 50% profit target
        leverage=10,
        initial_margin=1000,
        atr=0.091,                # ATR (trailing profit adjustment)
        position_type="LONG"
    )

    if risk_mgr.should_exit():  # Check if we should exit the position
        net_profit = risk_mgr.get_exit_pnl()

        if risk_mgr.stop_loss_exit():
            logger.info(f"Exited position based on stop-loss with {net_profit}")
        elif risk_mgr.target_profit_exit():
            logger.info(f"Cycle finished at "
                        f"with a profit of: {net_profit} "
                        f"")
                """


