import numpy as np

def exercise_val(underlying : float, 
                 strike : float, 
                 otype : str, 
                 up : float, 
                 numUp : int, 
                 numDown : int) -> float:
    '''
    
    Calculates the exercise value of an option at expiration.


    Parameters
    ----------
    `underlying` : float
        The price of the underlying at time 0.
    
    `strike` : float
        The strike price of the option.

    `otype` : str
        The type of option: ["put", "call"]
    
    `up` : float
        The expected amount of volatiilty over a single period.
    
    `numUp` : int
        The number of periods with positive volatility moves.

    `numDown` : int
        The number of periods with negative volatility moves.
    
        
    Returns
    -------
    `float`
        The value of the option at expiration.
    
    '''
    
    if otype == "call":
        price = underlying * up**(numUp - numDown) - strike

    elif otype == "put":
        price = strike - underlying * up**(numUp - numDown)

    if price < 0:
        price = 0

    return price

def binom_val(nextUpNode : float, 
              nextDownNode : float, 
              probUp : float, 
              discount : float) -> float:
    '''
    
    Calculates the binomial value of an option.


    Parameters
    ----------
    `nextUpNode` : float
        The value of the next period's option if a positive volatility move
        occurs.
    
    `nextDownNode` : float
        The value of the next period's option if a negative volatility move
        occurs.
    
    `probUp` : float
        The probability of a positive volatility move occuring.
    
    `discount` : float
        The discount factor to apply to the expected value of the binomial option.
    
    Returns
    -------
    `float`
        The binomial value of the option.

    '''

    price = (probUp * nextUpNode + (1 - probUp) * nextDownNode) * discount

    if price < 0:
        price = 0

    return price

def build_final_nodes(numIncrements : int, 
                      underlying : float, 
                      strike : float, 
                      up : float, 
                      otype : str) -> list:
    '''
    
    Builds the final tree of nodes for binomial option pricing.


    Parameters
    ----------
    `numIncrements` : int
        The number of trees to build for the binomial model.
    
    `underlying` : float
        The price of the underlying at time 0.
    
    `up` : float
        The expected amount of volatiilty over a single period.

    `strike` : float
        The strike price of the option.

    `otype` : str
        The type of option being priced: ["put", "call"]

    Returns
    -------
    `list`
        A list of decending node values, with each node representing a
        potential final value of the option being priced.

    '''

    numNodes = numIncrements + 1
    nodes = []

    for node in range(0, numNodes):
        numUp = numNodes - node
        numDown = node
        nodes.append(exercise_val(underlying, strike, otype, up, numUp, numDown))

    return nodes

def recurse_trees(nodes : list, 
                  up : float, 
                  probUp : float, 
                  discount : float) -> list:
    '''
    
    Recursively builds trees within the binomial option pricing matrix.


    Parameters
    ----------
    `nodes` : list
        The final tree of nodes for the binimial model, created with
        "build_final_nodes()".

    `up` : float
        The expected amount of volatiilty over a single period.

    `probUp` : float
        The probability of a positive volatility move occuring.
    
    `discount` : float
        The discount factor to apply to the expected value of the binomial 
        options.

    Returns
    -------
    `list`
        A list of all binomial option trees, with the final option price
        at the very last index: [final nodes -> single node]

    '''

    if not isinstance(nodes[0], list):
        nodes = [nodes]

    if len(nodes[-1]) == 1:
        return nodes

    newNodes = []

    for i in range(1, len(nodes[-1])):
        binom = binom_val(nodes[-1][i-1], nodes[-1][i], probUp, discount)
        newNodes.append(binom)

    nodes.append(newNodes)

    return recurse_trees(nodes, up, probUp, discount)

def BOPM(vol : float, 
         incrementTenor : float, 
         discountTenor : float,
         rf : float, 
         underlyingPrice : float, 
         strike : float, 
         otype : str, 
         numIncrements : int) -> list:
    '''
    
    Prices a European option via the Binomial Option Pricing Model.
    

    Parameters
    ----------
    `vol` : float
        The underlying instrument's implied volatility.

    `incrementTenor` : float
        The length of time between each tree as a fraction of a year using
        trading daycount conventions.

    `discountTenor` : float
        The length of time between each tree as a fraction of a year using
        interest rate daycount conventions.

    `rf` : float
        The domestic risk-free interest rate.

    `underlyingPrice` : float
        The underlying instrument's price at time 0.

    `otype` : str
        The type of option being priced: ["put", "call"]

    `numIncrements` : int
        The number of trees to build for the binomial model.

    Returns
    -------
    `list`
        A list of all binomial option trees, with the final option price
        at the very first index: [single node -> final nodes]
    
    '''

    # continuously compounded interest rate equivalent
    ccr = 360 * np.log(1 + rf / 360)
    
    # discount factor
    discount = np.exp((-ccr) * discountTenor)

    # binomial values
    a = 1
    up = np.exp(vol * np.sqrt(incrementTenor))
    b = np.sqrt(a**2 * (np.exp(vol**2 * incrementTenor) - 1))
    up = ((a**2 + b**2 + 1) + np.sqrt((a**2 + b**2 + 1)**2 - 4 * a**2)) / (2 * a)
    down = 1/up
    probUp = (a - down) / (up - down)
    
    # model
    nodes = build_final_nodes(numIncrements, underlyingPrice, strike, up, otype)
    forest = recurse_trees(nodes, up, probUp, discount)
    forest.reverse()

    return forest

