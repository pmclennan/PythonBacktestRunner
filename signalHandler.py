import pandas as pd
import numpy as np
import datetime
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

class signalHandler:
    """
    Class for acting as a broker or handling signals of the backtest process.
    """
    
    def __init__(self, stop_loss, take_profit, guaranteed_sl, broker_cost, data, currency, frequency, start_date, end_date, storeIndicators = 1):

        """
        Parameters:
        stopLoss (float): Stop loss level in absolute value, not pips.
        takeProfit (float): Take profit level in absolute value, not pips.
        guaranteedSl (bool): Whether to implement a guaranteed stoploss/takeprofit, or if stop conditions are based on the next available price.
            Worth reading online regarding this point as this is topical with the use of brokers and impacts spreads/costs. 
        brokerCost (float): Flat cost of broker in absolute value, not pips.
        data (pd.DataFrame): The data used in the backtest.
        currency (str): String representation of the currency pair.
        frequency (str): String representation of the data frequency/interval.
        start_date (datetime): Start date of the backtest.
        end_date (datetime): End date of the backtest.
        storeIndicators (int): Integer Boolean representation for whether to store calculated indicator values in the history file.

        Note that these inputs should be handled automatically by the Backtest loadBroker method.
        """
        
        
        self.original_stop_loss = stop_loss
        self.original_take_profit = take_profit
        self.guaranteed_sl = guaranteed_sl #Boolean
        self.broker_cost = broker_cost
        self.data = data
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.currency = currency
        self.frequency = frequency
        self.start_date = start_date
        self.end_date = end_date                
        self.storeIndicators = storeIndicators
        if self.storeIndicators == 1:
            self.indicatorDf = pd.DataFrame()        

        self.prev_traded_position = 0
        self.prev_traded_price = None
        self.total_profit = 0

        data['signal'] = ''
        data['action'] = ''
        data['position'] = ''
        data['P/L'] = ''
        data['Total profit'] = ''
        data['Executed price'] = ''
        data['Take Profit'] = ''
        data['Stop Loss'] = ''

        n = len(data)
        self.signal_list = [""]*n
        self.action = [""]*n
        self.position = [""]*n
        self.arr_PL = [""]*n 
        self.arr_total_profit = [""]*n 
        self.executed_price = [""]*n
        self.stop_loss_px_list = [""]*n
        self.take_profit_px_list = [""]*n
        self.current_action = ""
        
        self.trades_total = 0
        self.trades_won = 0
        self.trades_lost = 0
        self.trades_tied = 0       
        self.summary_df = pd.DataFrame()

    def bandPL(self,PL):
        """
        A function for finalising the PL level as well as hitting guaranteed stoploss/take profit.

        Parameters:
        PL (float): The pre-fee/cost P&L once a trade is closed.

        Returns:
        PL (float): The net P&L once a trade is closed, accounting for if a guaranteed limit is hit + the flat broker cost/fee.
        """

        if self.guaranteed_sl:
            if PL > self.take_profit:
                PL = self.take_profit
            elif PL < self.stop_loss:
                PL = self.stop_loss
        else:
            PL = PL
        PL -= self.broker_cost
        return PL

    def closeTrade(self,PL, bid_price, ask_price, index):
        """
        Function called to handle updating attributes once a trade is closed.
        Parameters:
        PL (float): The P&L after bandPL to be added to the total profit.
        """
        
        #Count in total trades
        self.trades_total += 1

        # Reseting Current position,action and other attributes.
        if self.prev_traded_position == -1:
            self.current_action = "close short"
        elif self.prev_traded_position == 1:
            self.current_action = "close long"        
        
        self.store_executed_price(bid_price, ask_price, index)
        self.total_profit += PL

        self.prev_traded_position = 0
        self.prev_traded_price = None

        self.stop_loss = self.original_stop_loss
        self.take_profit = self.original_take_profit
        self.take_profit_px = 0
        self.stop_loss_px = 0

        #Count if trade is succesful or not
        #NB Rounding to handle Floating Point Error
        if round(PL, 5) > 0:
            self.trades_won += 1
        elif round(PL, 5) < 0:
            self.trades_lost += 1
        elif round(PL, 5) == 0:
            self.trades_tied += 1
        
    def saveStats(self, PL, index):
        """
        Function used to save stats for the results files.

        Parameters:
        PL (float): The current P&L to save.
        index (int): The input index for where to save the stats in context of the history file.
        """
                
        if self.prev_traded_position == 1:
            self.action[index] = self.current_action
        
        elif self.prev_traded_position == -1:
            self.action[index] = self.current_action
        
        elif self.prev_traded_position == 0:
            self.action[index] = self.current_action
        
        self.arr_PL[index] = PL
        self.arr_total_profit[index] = self.total_profit
        self.position[index] = self.prev_traded_position

    def getHistory(self):        
        """
        Function used to summarise the backtest history once finalised.
        Aggregates everything into a dataframe - appending stats & indicatorDF to the input OHLC (+ bid/ask) data.
        
        Parameters:
        None

        Returns:
        self.data (pd.DataFrame): The finalised history dataframe.
        """        

        self.data['signal'] = self.signal_list
        self.data['action'] = self.action
        self.data['position'] = self.position
        self.data['P/L'] = self.arr_PL
        self.data['Total profit'] = self.arr_total_profit
        self.data['Executed price'] = self.executed_price
        self.data['Stop Loss'] = self.stop_loss_px_list
        self.data['Take Profit'] = self.take_profit_px_list

        #Indicator DF
        if self.storeIndicators == 1:
            insertIdx = self.data.columns.get_loc('signal')
            insertDF = self.indicatorDf.drop(columns = 'time')
            for i in range(len(insertDF.columns)):
                self.data.insert(loc = i + insertIdx, column = insertDF.columns.values[i], value = insertDF.iloc[:, i])

        return self.data
    
    def getSummary(self):
        """
        Function used for the summary of the backtest results.
        Summarises basic information of the backtest and total trade statistics.

        Parameters:
        None

        Returns:
        self.summary_df (pd.DataFrame): The resulting summary dataframe.
        """
        self.summary_df['Start'] = [self.start_date.strftime("%Y-%m-%d %H:%S")]
        self.summary_df['End'] = self.end_date.strftime("%Y-%m-%d %H:%S")
        self.summary_df['Currency Pair'] = [self.currency]
        self.summary_df['Frequency'] = [self.frequency]
        self.summary_df['Total Trades'] = [self.trades_total]
        self.summary_df['Total P/L'] = [self.arr_total_profit[-1]]
        self.summary_df['Total P/L (pips)'] = [self.arr_total_profit[-1] * 10000]
        self.summary_df['Trades Won (n)'] = [self.trades_won]
        self.summary_df['Trades Won (%)'] = [(self.trades_won/self.trades_total) * 100 if self.trades_total > 0 else 0]
        self.summary_df['Trades Lost (n)'] = [self.trades_lost]
        self.summary_df['Trades Lost (%)'] = [(self.trades_lost/self.trades_total) * 100 if self.trades_total > 0 else 0]
        self.summary_df['Trades Tied (n)'] = [self.trades_tied]
        self.summary_df['Trades Tied (%)'] = [(self.trades_tied/self.trades_total) * 100 if self.trades_total > 0 else 0]
        return self.summary_df
    
    # Used to store signal for final summary df
    def storeSignalAndIndicators(self, signal, indicatorDf, index):
        """
        A function used to store the signal and indicator details at every iteration.

        Parameters:
        signal (int): The signal output from the trading strategy.
        indicatorDF (pd.DataFrame or None): The dataframe containing indicator values from the trading strategy.
        index (int): The index to store these statistics in reference to the history data.
        """

        if self.storeIndicators == 1 and indicatorDf is not None:
            if self.indicatorDf.empty:
                self.indicatorDf = indicatorDf
            else:
                self.indicatorDf = self.indicatorDf.append(indicatorDf.iloc[-1], ignore_index=True)
        self.signal_list[index] = signal
        
    def store_executed_price(self, bid_price, ask_price, index):
        """
        A function to store the trade executed price in the history.

        Parameters:
        bid_price (float): The current bid price from the input data.
        ask_price (float): The current ask price from the input data.
            NB these are both substituted as Close price in the backtest if not bid/ask available.
        index (int): The index to store these statistics in reference to the history data.
        """

        if self.current_action == "buy" or self.current_action == "close short":
            self.executed_price[index] = ask_price
        elif self.current_action == "short" or self.current_action == "close long":
            self.executed_price[index] = bid_price

    ############### Actions ###############
    def buy(self, bid_price, ask_price, index):
        """
        A function used to simulate a buy trade in the backtest.

        Parameters:
        bid_price (float): The current bid price from the input data.
        ask_price (float): The current ask price from the input data.
            NB these are both substituted as Close price in the backtest if not bid/ask available.
        index (int): The index to store this trade in reference to the history data.

        TODO: consider the updateLimits method. This can be enabled to widen limits if a stronger signal is received.
        
        """
        
        PL = 0 #Reset at the trade
        if self.prev_traded_position == 0:
            self.current_action = "buy"
            self.prev_traded_position = 1
            self.prev_traded_price = ask_price #Executed at ask for a buy     
            self.stop_loss_px = self.prev_traded_price + self.stop_loss
            self.stop_loss_px_list[index] = self.stop_loss_px
            self.take_profit_px = self.prev_traded_price + self.take_profit
            self.take_profit_px_list[index] = self.take_profit
            self.saveStats(PL,index)
            self.store_executed_price(bid_price, ask_price, index)

        elif self.prev_traded_position == 1:
            # Reciving a stroger buy signal
            #self.updateLimits(self.original_stop_loss, self.original_take_profit, ask_price, index) 
            self.checkStopConditions(bid_price, ask_price, index) #Disregard for now, as we've just updated limits.

        elif self.prev_traded_position == -1:
            self.current_action = "close short"
            PL = (self.prev_traded_position*(ask_price - self.prev_traded_price)) #Executed at ask for a buy 
            PL = self.bandPL(PL)
            self.closeTrade(PL, bid_price, ask_price, index)
            self.saveStats(PL,index)
            self.store_executed_price(bid_price, ask_price, index)

        else: 
            raise Exception ("Unknown Signal!")

    def sell(self, bid_price, ask_price, index):
        """
        A function used to simulate a sell trade in the backtest.

        Parameters:
        bid_price (float): The current bid price from the input data.
        ask_price (float): The current ask price from the input data.
            NB these are both substituted as Close price in the backtest if not bid/ask available.
        index (int): The index to store this trade in reference to the history data.

        TODO: consider the updateLimits method. This can be enabled to widen limits if a stronger signal is received.
        
        """        
        
        PL = 0 # <----- Default for if currently holding
        if self.prev_traded_position == 0:
            self.current_action = "short"
            self.prev_traded_position = -1
            self.prev_traded_price = bid_price #Executed at bid for a sell
            self.stop_loss_px = self.prev_traded_price - self.stop_loss
            self.stop_loss_px_list[index] = self.stop_loss_px
            self.take_profit_px = self.prev_traded_price - self.take_profit
            self.take_profit_px_list[index] = self.take_profit_px
            self.saveStats(PL,index)
            self.store_executed_price(bid_price, ask_price, index)

        elif self.prev_traded_position == -1:
            # Reciving a stroger sell signal, 
            #self.updateLimits(self.original_stop_loss, self.original_take_profit, bid_price, index) #Switched this off.
            self.checkStopConditions(bid_price, ask_price ,index) #Disregard for now, as we've just updated limits.
        
        elif self.prev_traded_position == 1:
            self.current_action = "close long"
            PL = (self.prev_traded_position*(bid_price - self.prev_traded_price)) #Executed at bid for a sell + flat spread
            PL = self.bandPL(PL)
            self.closeTrade(PL, bid_price, ask_price, index)
            self.saveStats(PL,index)
            self.store_executed_price(bid_price, ask_price, index)
        else: 
            raise Exception ("Unknown Signal!")
    
    def checkStopConditions(self, bid_price, ask_price, index):
        """
        Function used to check stop conditions at each iteration and close trade if limits are hit.

        Parameters:
        bid_price (float): The current bid price from the input data.
        ask_price (float): The current ask price from the input data.
            NB these are both substituted as Close price in the backtest if not bid/ask available.
        index (int): The index to store this information in reference to the history data.

        Returns:
        self.total_profit (float): The current total profit at this index.

        """
        PL = 0
        self.current_action = "hold"
        
        if self.prev_traded_position == -1:

            PL = (self.prev_traded_position*(ask_price - self.prev_traded_price)) #MtM PL when short based off ask price (as if we were to buy to close the short)
            
            #Take Profit
            if self.take_profit_px >= ask_price:
                PL = self.bandPL(PL) 
                self.closeTrade(PL, bid_price, ask_price, index)

            #Stop Loss
            elif self.stop_loss_px <= ask_price:
                PL = self.bandPL(PL)
                self.closeTrade(PL, bid_price, ask_price, index)

        elif self.prev_traded_position == 1:

            PL = (self.prev_traded_position*(bid_price - self.prev_traded_price)) #MtM PL when long based off bid price (as if we were to sell to close the long)
            
            #Take Profit
            if self.take_profit_px <= bid_price:                
                PL = self.bandPL(PL) 
                self.closeTrade(PL, bid_price, ask_price, index)  

            #Stop Loss
            elif self.stop_loss_px >= bid_price:
                PL = self.bandPL(PL)
                self.closeTrade(PL, bid_price, ask_price, index)         

        self.saveStats(PL,index)
        return self.total_profit

    def updateLimits(self, stop_loss, take_profit, curr_price, index):
        """
        A function being considered to adjust limits based on a stronger signal received - currently not enabled.
        Resets the stop_loss_px and take_profit_px that the checkStopConditions checks.

        Parameters:
        stop_loss (float): The stop_loss amount applied to reset the limit by.
        take_profit (float): The take_profit amount applied to reset the limit by.
            NB: Both are in absolute values and not pips.
        curr_price (float): The relevant price to apply the stop_loss/take_profit around.
        index (int): The current index to apply this to.

        """

        #At this stage just realign the stoploss/takeprofit around the current price

        self.stop_loss_px = curr_price + (self.prev_traded_position * self.stop_loss)
        self.take_profit_px = curr_price + (self.prev_traded_position * self.take_profit)

        self.stop_loss_px_list[index] = self.stop_loss_px
        self.take_profit_px_list[index] = self.take_profit_px