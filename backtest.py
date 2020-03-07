import time
from strategy import Strategy

NO_POSITION = 0
LONG_OPEN = 1
SHORT_OPEN = 2


class Backtester:
    def __init__(self, strategy, pyramiding=1, stake_percent=0.05, initial_capital=1, leverage=5, commission=0.075):
        """ Strategies have both data and indicators.
            The backtester iterates through the data as generated by the strategy
            and calculates metrics over time.
            The backtester assumes that the data is accurate and any indicators
            have been calculated correctly (i.e. not using future data).
            The idea is that each time the backtester iterates through a new row of data,
            that is equivalent to a new row of kline data being received by the bot,
            indicators updated and decisions made on it.
        """
        print('creating new backtester')

        self.exchange = MockExchange(initial_capital=initial_capital, leverage=leverage, commission=commission)

        self.strategy = strategy
        self.initial_capital = initial_capital
        self.total_equity = initial_capital
        self.exchange_commission = commission
        self.leverage = leverage
        self.max_pyramid = pyramiding
        self.stake_percent = stake_percent
        self.n_trades = 0
        self.total_realised_pl = 0
        self.state = NO_POSITION
        self.current_position = None
        self.pyramid_size = 0

        self.run_backtest()

    def _get_order_size(self, size_btc, cur_price):
        """ Given the amount of BTC you want to stake, returns the amount of contracts to buy
            at the current price, such that the given BTC amount (including fees) is used as margin
        """
        return size_btc * (1 - (self.exchange_commission * self.leverage)) * cur_price * self.leverage

    def run_backtest(self):
        print('running backtest')

        self.state = NO_POSITION      
        for index, row in self.strategy.df.iterrows():
            order_size = self._get_order_size(self.stake_percent * self.total_equity, row['close'])
            if row['long'] == 1:
                self._long(row['close'], order_size)
            elif row['short'] == 1:
                self._short(row['close'], order_size)
            elif (row['exitshort'] == 1) or (row['exitlong'] == 1):
                self._exit_position(row['close'])

        print('backtest complete')
        print('total positions: ' + str(self.n_trades))
        print('total pl: ' + str(self.total_realised_pl))
        print()


    def _long(self, cur_price, contracts):
        if self.state == NO_POSITION:
            # open new long position
            self.exchange.open_position(long=True, contracts=contracts, cur_price=cur_price)
            self.pyramid_size = 1
            self.state = LONG_OPEN
            self.total_equity -= self.stake_percent * self.total_equity
        elif self.state == LONG_OPEN:
            # pyramid new long position if max pyramid isn't already reached
            if self.pyramid_size < self.max_pyramid:
                print('pyramidding orders not yet implemented')
            # else do nothing
        elif self.state == SHORT_OPEN:
            # close open long and open a short
            self._exit_position(cur_price)
            self.exchange.open_position(long=True, contracts=contracts, cur_price=cur_price)
            self.pyramid_size = 1
            self.total_equity -= self.stake_percent * self.total_equity
            self.state = LONG_OPEN

    def _short(self, cur_price, contracts):
        if self.state == NO_POSITION:
            # open new long position
            self.exchange.open_position(long=False, contracts=contracts, cur_price=cur_price)
            self.pyramid_size = 1
            self.state = SHORT_OPEN
            self.total_equity -= self.stake_percent * self.total_equity
        elif self.state == SHORT_OPEN:
            # pyramid new long position if max pyramid isn't already reached
            if self.pyramid_size < self.max_pyramid:
                print('pyramidding orders not yet implemented')
            # else do nothing
        elif self.state == LONG_OPEN:
            # close open long and open a short
            self._exit_position(cur_price)
            self.exchange.open_position(long=False, contracts=contracts, cur_price=cur_price)
            self.pyramid_size = 1
            self.total_equity -= self.stake_percent * self.total_equity
            self.state = SHORT_OPEN

    def _exit_position(self, cur_price):
        if self.state != NO_POSITION:
            realised_pl = self.exchange.close_position(cur_price)
            self.total_realised_pl += realised_pl
            self.n_trades += 1
            self.state = NO_POSITION
            self.pyramid_size = 0
            self.current_position = None
            self.total_equity += realised_pl
            


class MockExchange:
    def __init__(self, initial_capital=1, leverage=5, commission=0.075):
        self.capital = initial_capital
        self.leverage = leverage
        self.commission = commission
        self.position = None
        self.trading_history = []

    def open_position(self, long=True, contracts=100, cur_price=0):
        self.position = Position(long, contracts, cur_price, self.leverage)

    def close_position(self, cur_price):
        res = self.position.close(cur_price)
        self.trading_history.append(self.position)
        self.position = None
        return res  * (1 - self.commission) # exchange takes commission

    def analyse_history(self):
        # look at trading history and generate some metrics
        priont('not yet implemented')

class Position:
    def __init__(self, long=True, contracts=100, start_price=0, leverage=5):
        self.long = long
        self.contracts = contracts
        self.start_price = start_price
        self.leverage = leverage

    def close(self, end_price=0):
        """ Return the realised P&L of this position, minus fees
        """
        self.end_price = end_price
        realised_pl = self.leverage * (1 - abs(self.end_price / self.start_price))
        return realised_pl

    # TODO: Work out if an order has been liquidated/hit its stop loss/hit its take profit

    

