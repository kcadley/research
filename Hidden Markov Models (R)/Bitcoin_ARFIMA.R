# creating time series
library(zoo)

# plotting
library(ggplot2)
library(ggthemes) # https://jrnold.github.io/ggthemes/
library(patchwork)
library(grid)
library(gridExtra)
library(gt)
library(formattable)

# forecasting
library(forecast)
library(arfima)
library(tseries)
library(dplyr)
library(rugarch)
library(lmtest)
library(dgof)
library(nortest)
library(goftest)
library(FinTS)
library(rugarch)
library(fGarch)
library(fracdiff)
library(MASS)
library(depmixS4)
library(fGarch)

# distributions
library(gamlss)
library(gamlss.dist)
library(gamlss.add)
library(univariateML)
library(fitdistrplus)
library(VGAM)
library(retimes)
library(nortest)
library(QRM)

# functions
source("./functions_custom.R")
source("./distributions_custom.R")

### load data ===============================================================

data = read.csv("./Data/BITCOIN.csv", header = TRUE)
data$Price = data$Price
data$Date = data$Date
stats_plot(data, "Price")

# convert to time series
data$Price = log(data$Price)
data$Date = as.Date(data$Date, format="%m/%d/%y")
tsData = zoo(data$Price, order.by = data$Date)
data$Obs = as.numeric(data$Date - min(data$Date) + 1)

# find, filter, drop NAs
sum(is.na(data$Price))
dataWithNA = data[apply(is.na(data), 1, any), ]
print(dataWithNA)

# dropping NA (all holidays)
data = na.omit(data)

### investigate ================================================================
# vanilla
stats_plot(data, "Price")

# differenced
diffData = data[2:nrow(data),]
diffData$Price = diff(data$Price)
stats_plot(diffData, "Price") # overdifferenced

# fractionally differenced
fracModel = fracdiff(data$Price, nar=0, nma=0)
fracData = data
fracData$Price = diffseries(data$Price, fracModel$d)
stats_plot(fracData, "Price")

# trimmed
trimFracData = fracData[500:nrow(fracData),]
stats_plot(fracData[500:nrow(fracData),], "Price")

### ARFIMA ================================================================

# ARFIMA
arfimaModel = NULL
arfimaAICc = 0
for (p in 0:2)
{
  for (q in 0:2)
  {
    
    # ARFIMA (dynamic mean)
    testModel = arfima(fracData$Price, order=c(p, 0, q), fixed=list(frac=fracModel$d), dmean=TRUE)
    resids = residuals(testModel)[[1]]
    testAICc = custom_AICc(resids, p, q, 1)  # additional param for dynamic mean
    
    if (testAICc < arfimaAICc)
    {
      arfimaAICc = testAICc
      arfimaModel = testModel
    }
    
    # ARFIMA (no dynamic mean)
    testModel = arfima(fracData$Price, order=c(p, 0, q), fixed=list(frac=fracModel$d), dmean=FALSE)
    resids = residuals(testModel)[[1]]
    testAICc = custom_AICc(resids, p, q, 0)
    
    if (testAICc < arfimaAICc)
    {
      arfimaAICc = testAICc
      arfimaModel = testModel
    }
    
  }
}


meanModel = arfimaModel
resids = residuals(meanModel)[[1]]
residsSqrd = residuals(meanModel)[[1]]^2
fittedDiff = fitted(meanModel)[[1]]
fittedLog = data$Price - resids

# fits
fittedData = data[20:nrow(data),]
fittedData$FittedDiff = fittedDiff[20:length(fittedDiff)]
fittedData$Fitted = fittedData$Price - resids[20:length(resids)]
fittedData$Resids = resids[20:length(resids)]
fittedData$ResidsSqrd = residsSqrd[20:length(residsSqrd)]

stats_plot(fittedData, "FittedDiff")
stats_plot(fittedData, "Fitted")
stats_plot(fittedData, "Resids")
stats_plot(fittedData, "ResidsSqrd")

### HMM ========================================================================

# segment into "states"
upper = na.omit(fittedData$FittedDiff[(fittedData$FittedDiff > 0)]) # returns > 0
lower = na.omit(fittedData$FittedDiff[(fittedData$FittedDiff <= 0)])  # returns <= 0

# confirm distributions
stats_plot(data.frame(Upper=upper), "Upper")
stats_plot(data.frame(Lower=lower), "Lower")

find_distro(upper)
find_distro(lower)

# custom distribution

# built response model distributions
response_models = list( list( posWeibull(fittedData$FittedDiff) ),
                        list( negWeibull(fittedData$FittedDiff) ))

# build transition probabilities...
# First transInit:
# 0.8: Prob of staying in Bull.
# 0.2: Prob of transitioning from Bull to Bear.
# 1.0: Price change coefficient for staying in Bull. (how much will .8 change)
# −1.0: Price change coefficient for transitioning to Bear.  (how much will .2 change)

# Second transInit:
# 0.2: Prob of transitioning from Bear to Bull.
# 0.8: Prob of staying in Bear.
# −1.0: Price change coefficient for transitioning to Bull. (how much will .2 change)
# 1.0: Price change coefficient for staying in Bear. (how much will .8 change)

transition = list( transInit(~FittedDiff, nst = 2, data=fittedData, pstart = c(0.8, 0.2, 1.0, -1.0), prob=TRUE),
                   transInit(~FittedDiff, nst = 2, data=fittedData, pstart = c(0.2, 0.8, -1.0, 1.0), prob=TRUE))

# set an initial state (second every time)
prior = transInit(~1, ns = 2, pstart = c(0.0, 1.0), data=data.frame(1))

# model
mod = makeDepmix(response = response_models, 
                 transition = transition, 
                 prior = prior, 
                 homogeneous = FALSE) # lets transition probs change over time

# fit model
fittedModel = fit(mod, emcontrol=em.control(rand=TRUE)) # as needed: em.control(tol=1e-8, maxit=1000, rand=TRUE)


# pull states
hiddenStatesSmooth = data.frame(posterior(fittedModel, type="smoothing"))
colnames(hiddenStatesSmooth) = c("Bull", "Bear")

hiddenStatesViterbi = data.frame(posterior(fittedModel, type="viterbi"))
colnames(hiddenStatesViterbi) = c("State", "Bull", "Bear")

hiddenStatesGlobal = posterior(fittedModel, type="global")
hiddenStatesGlobal = data.frame(State=hiddenStatesGlobal)

hiddenStatesLocal = posterior(fittedModel, type="local")
hiddenStatesLocal = data.frame(State=hiddenStatesLocal)

hiddenStatesFiltered = data.frame(posterior(fittedModel, type="filtering"))
colnames(hiddenStatesFiltered) = c("Bull", "Bear")


### Plotting ===================================================================
# pre-categorized
regimes = data[20:nrow(data),]
regimes$State = hiddenStatesViterbi$State

regimePlt = ggplot(regimes, aes(x=seq_along(Price), y=Price, group=1, color=as.factor(State))) +
  geom_line(linewidth = 1) +
  scale_color_manual(values = c("red", "blue"), name = "State") +
  labs(x = "Time", y = "Price", title = "Price by State") +
  theme_minimal()
regimePlt


# pre-categorized (original scale)
regimes = data[20:nrow(data),]
regimes$Price = exp(regimes$Price)
regimes$State = hiddenStatesViterbi$State

regimePlt = ggplot(regimes, aes(x=seq_along(Price), y=Price, group=1, color=as.factor(State))) +
  geom_line(linewidth = 1) +
  scale_color_manual(values = c("red", "blue"), name = "State") +
  labs(x = "Time", y = "Price", title = "Price by State") +
  theme_minimal()
regimePlt

# pre-categorized (original scale) + smoothed
regimes = data[20:nrow(data),]
regimes$Price = exp(regimes$Price)
regimes$State = hiddenStatesViterbi$State

regimes$State = as.integer(median_smooth(regimes$State, 31))

regimePlt = ggplot(regimes, aes(x=seq_along(Price), y=Price, group=1, color=as.factor(State))) +
  geom_line(linewidth = 1) +
  scale_color_manual(values = c("red", "blue"), name = "State") +
  labs(x = "Time", y = "Price", title = "Price by State") +
  theme_minimal()
regimePlt


# non-categorized
regimes = data[20:nrow(data),]
regimes$State = as.integer(hiddenStatesFiltered$Bull < hiddenStatesFiltered$Bear) + 1 # 1 if bear market -> +1 to both (S1 = bull, S2 = bear)

regimePlt = ggplot(regimes, aes(x=seq_along(Price), y=Price, group=1, color=as.factor(State))) +
  geom_line(linewidth = 1) +
  scale_color_manual(values = c("red", "blue"), name = "State") +
  labs(x = "Time", y = "Price", title = "Price by State") +
  theme_minimal()
regimePlt


# non-categorized (original scale)
regimes = data[20:nrow(data),]
regimes$Price = exp(regimes$Price)
regimes$State = as.integer(hiddenStatesFiltered$Bull < hiddenStatesFiltered$Bear) + 1 # 1 if bear market -> +1 to both (S1 = bull, S2 = bear)

regimePlt = ggplot(regimes, aes(x=seq_along(Price), y=Price, group=1, color=as.factor(State))) +
  geom_line(linewidth = 1) +
  scale_color_manual(values = c("red", "blue"), name = "State") +
  labs(x = "Time", y = "Price", title = "Price by State") +
  theme_minimal()
regimePlt

# non-categorized (original scale) + smoothed
regimes = data[20:nrow(data),]
regimes$Price = exp(regimes$Price)
regimes$State = as.integer(hiddenStatesFiltered$Bull < hiddenStatesFiltered$Bear) + 1 # 1 if bear market -> +1 to both (S1 = bull, S2 = bear)

regimes$State = as.integer(median_smooth(regimes$State, 31))

regimePlt = ggplot(regimes, aes(x=seq_along(Price), y=Price, group=1, color=as.factor(State))) +
  geom_line(linewidth = 1) +
  scale_color_manual(values = c("red", "blue"), name = "State") +
  labs(x = "Time", y = "Price", title = "Price by State") +
  theme_minimal()
regimePlt







