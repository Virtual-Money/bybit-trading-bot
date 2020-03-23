from datetime import datetime
import time

import optuna
import pandas as pd
import ta

from backtest import Backtester
from exchange.bybit_exchange import BybitExchange
from strategies.wt_strategy import WTStrategy
from strategies.thm_strategy import THMStrategy

class BasePipeline:
    def __init__(self, test=True, load_klines=True, validate=True):
        self.validate = validate
        if load_klines:
            
            exchange = BybitExchange(test=test)

            n_windows = 5
            window_size = 144
            n_klines = n_windows * window_size
            data = exchange.get_klines(symbol="BTCUSD", interval="5", limit=n_klines)

            if self.validate:
                n_train = 3
                train_set_threshold = n_train * window_size

                self.train_set = data[:train_set_threshold]
                self.test_set = data[train_set_threshold:]
            else:
                self.train_set = data

    def _update_config_file(self, best_params):
        config = configparser.ConfigParser()
        config['DEFAULT'] = {   
            'WT_OPEN_LONG_THRESHOLD' : best_params.get('wt_open_long'),
            'WT_OPEN_SHORT_THRESHOLD' : best_params.get('wt_open_short'),
            'MFI_LONG_THRESHOLD' : best_params.get('mfi_long'),
            'MFI_SHORT_THRESHOLD' : best_params.get('mfi_short'),
            'WT_EXIT_LONG_THRESHOLD' : best_params.get('wt_exit_long'),
            'WT_EXIT_SHORT_THRESHOLD' : best_params.get('wt_exit_short')
        }
        with open('strategies/configs/wt_config.ini', 'w') as configfile:
            config.write(configfile)

    def load_kline_data(self, data):
        pass

    def load_params(self, filename):
        pass

    def run_pipeline(self):
        param_config = configparser.ConfigParser()
        param_config.read('strategies/configs/wt_config.ini')
        cur_wt_open_long = float(param_config['DEFAULT']['WT_OPEN_LONG_THRESHOLD'])
        new_wt_open_long_max = min(cur_wt_open_long+40, 100)
        new_wt_open_long_min = max(cur_wt_open_long-40, -100)
        cur_wt_open_short = float(param_config['DEFAULT']['WT_OPEN_SHORT_THRESHOLD'])
        new_wt_open_short_max = min(cur_wt_open_short+40, 100)
        new_wt_open_short_min = max(cur_wt_open_short-40, -100)
        cur_mfi_long = float(param_config['DEFAULT']['MFI_LONG_THRESHOLD'])
        new_mfi_long_max = 15
        new_mfi_long_min = -15
        cur_mfi_short = float(param_config['DEFAULT']['MFI_SHORT_THRESHOLD'])
        new_mfi_short_max = 15
        new_mfi_short_min = -15
        cur_wt_exit_long = float(param_config['DEFAULT']['WT_EXIT_LONG_THRESHOLD'])
        new_wt_exit_long_max = min(cur_wt_exit_long+40, 100)
        new_wt_exit_long_min = max(cur_wt_exit_long-40, -10)
        cur_wt_exit_short = float(param_config['DEFAULT']['WT_EXIT_SHORT_THRESHOLD'])
        new_wt_exit_short_max = min(cur_wt_exit_short+40, 10)
        new_wt_exit_short_min = max(cur_wt_exit_short-40, -100)

        def objective(trial):
            test_strategy = WTStrategy(
                wt_open_long = trial.suggest_uniform('wt_open_long', new_wt_open_long_min, new_wt_open_long_max),
                wt_open_short = trial.suggest_uniform('wt_open_short', new_wt_open_short_min, new_wt_open_short_max),
                mfi_long = trial.suggest_uniform('mfi_long', new_mfi_long_min, new_mfi_long_max),
                mfi_short = trial.suggest_uniform('mfi_short', new_mfi_short_min, new_mfi_short_max),
                wt_exit_long = trial.suggest_uniform('wt_exit_long', new_wt_exit_long_min, new_wt_exit_long_max),
                wt_exit_short = trial.suggest_uniform('wt_exit_short', new_wt_exit_short_min, new_wt_exit_short_max),
            )

            test_strategy.load_klines(data=self.train_set)
        
            backtester = Backtester(strategy=test_strategy, stake_percent=0.05, pyramiding=12)
            # backtester.print_report()
            return (-1 * backtester.get_sharpe_ratio())

        if self.validate:
            while True:
                study = optuna.create_study()
                study.optimize(objective, n_trials=30)
                print(study.best_params)
                validation_strat = WTStrategy(
                        wt_open_long = study.best_params.get('wt_open_long'),
                        wt_open_short = study.best_params.get('wt_open_short'),
                        mfi_long = study.best_params.get('mfi_long'),
                        mfi_short = study.best_params.get('mfi_short'),
                        wt_exit_long = study.best_params.get('wt_exit_long'),
                        wt_exit_short = study.best_params.get('wt_exit_short'),
                )
                validation_strat.load_klines(data=self.test_set)
                backtester = Backtester(strategy=validation_strat, stake_percent=0.05, pyramiding=12)
                print(f"Validation report:::")
                backtester.print_report()
                print(f"sharpe ratio: {backtester.get_sharpe_ratio()}")

                if backtester.get_sharpe_ratio() > 0.01:
                    print(f"Found successful strategy on the validation set.")
                    print(study.best_params)
                    break
        else:
            study = optuna.create_study()
            study.optimize(objective, n_trials=30)
            print(study.best_params)
        self._update_config_file(study.best_params)
