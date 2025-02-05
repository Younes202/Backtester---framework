from loguru import logger


class RiskManagementF:
    def __init__(self, entry_price, current_price, risk_percent, profit_percent, 
                 leverage, initial_margin, atr, fees=0.0002, position_type="LONG"):
        """
        Binance USD-M Futures Risk Management System with ATR-based Trailing Profit
        """
        self.entry_price = entry_price
        self.current_price = current_price
        self.risk_percent = risk_percent / 100
        self.profit_percent = profit_percent / 100  # Flexible profit percentage
        self.leverage = leverage
        self.initial_margin = initial_margin
        self.atr = atr  # ATR value for dynamic exit strategy
        self.fees = fees
        self.position_type = position_type.upper()
        self.maintenance_margin = 0.004  # Binance default maintenance margin
        
        # Validate inputs
        self._validate_parameters()
        
        # Calculate derived values
        self.position_size = (initial_margin * leverage) / entry_price
        self.trade_risk = initial_margin * self.risk_percent
        self._calculate_liquidation_price()
        
        # Set initial take-profit price
        self.initial_tp_price = self.calculate_take_profit_price()

        logger.info(f"Position initialized: {self.position_type} {self.position_size:.2f} contracts")
        logger.info(f"Risk: ${self.trade_risk:.2f} ({risk_percent}% of margin)")
        logger.info(f"Liquidation price: {self.liquidation_price:.2f}")

    def _validate_parameters(self):
        """Ensure all parameters are within valid ranges"""
        if self.position_type not in ["LONG", "SHORT"]:
            raise ValueError("Position type must be 'LONG' or 'SHORT'")
        if self.leverage <= 0:
            raise ValueError("Leverage must be greater than 0")
        if self.risk_percent >= 1:
            raise ValueError("Risk percentage cannot be 100% or more")
        if self.profit_percent <= 0:
            raise ValueError("Profit percentage must be positive")
        if self.atr <= 0:
            raise ValueError("ATR must be a positive value")

    def _calculate_liquidation_price(self):
        """Calculate accurate liquidation price for USD-M futures"""
        if self.position_type == "LONG":
            self.liquidation_price = self.entry_price * (1 - (1/self.leverage) + self.maintenance_margin)
        else:
            self.liquidation_price = self.entry_price * (1 + (1/self.leverage) - self.maintenance_margin)

    def calculate_stop_loss_price(self):
        """Calculate stop-loss price based on risk percentage"""
        price_risk = self.trade_risk / self.position_size
        return (self.entry_price - price_risk) if self.position_type == "LONG" \
               else (self.entry_price + price_risk)

    def calculate_take_profit_price(self):
        """Calculate take-profit price ensuring net profit after fees"""
        target_profit = self.initial_margin * self.profit_percent  # Target net profit
        required_price_change = target_profit / self.position_size  # Adjusted for position size
        
        # Adjust for fees to ensure net profit is achieved
        fee_adjustment = self.fees * self.entry_price * 2  # Fees for entry and exit
        
        if self.position_type == "LONG":
            return self.entry_price + required_price_change + fee_adjustment
        else:
            return self.entry_price - required_price_change - fee_adjustment

    def calculate_pnl(self, exit_price):
        """Calculate profit/loss with fees"""
        if self.position_type == "LONG":
            price_change = exit_price - self.entry_price
        else:
            price_change = self.entry_price - exit_price
            
        gross_pnl = price_change * self.position_size
        fee = (self.entry_price + exit_price) * self.position_size * self.fees
        return gross_pnl - fee

    def check_liquidation(self):
        """Check if current price triggers liquidation"""
        if (self.position_type == "LONG" and self.current_price <= self.liquidation_price) or \
           (self.position_type == "SHORT" and self.current_price >= self.liquidation_price):
            logger.critical(f"Liquidation at {self.current_price:.2f}!")
            return True
        return False
    
    def get_exit_pnl(self):
        """Calculate PnL at current price"""
        pnl = self.calculate_pnl(self.current_price)
        logger.info(f"Net Profit/Loss at exit: ${pnl:.2f}")
        return pnl

    def stop_loss_exit(self):
        """Check if stop-loss condition is met"""
        sl_price = self.calculate_stop_loss_price()
        if (self.position_type == "LONG" and self.current_price <= sl_price) or \
           (self.position_type == "SHORT" and self.current_price >= sl_price):
            return True
        return False

    def target_profit_exit(self):
        """Check if take-profit condition is met"""
        dynamic_tp_price = self.initial_tp_price
        if self.position_type == "LONG" and self.current_price >= dynamic_tp_price:
            return True
        elif self.position_type == "SHORT" and self.current_price <= dynamic_tp_price:
            return True
        return False

    def should_exit(self):
        """Check exit conditions including stop-loss and take-profit"""
        if self.check_liquidation():
            logger.critical(f"Liquidation triggered at {self.current_price:.2f}")
            return "LIQUIDATION"  # Indicate that the exit is due to liquidation

        if self.stop_loss_exit():
            return "LOSS"  # Indicate that the exit is due to stop-loss

        if self.target_profit_exit():
            return "PROFIT"  # Indicate that the exit is due to take-profit

        return False  # No exit condition met



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


