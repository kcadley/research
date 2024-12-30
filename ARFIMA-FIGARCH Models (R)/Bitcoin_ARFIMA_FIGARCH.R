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

source("./functions_custom.R")

### loading data ===============================================================

data = read.csv("./Data/BITCOIN.csv", header = TRUE)

# convert to time series
data$Price = log(data$Price)
data$Date = as.Date(data$Date, format="%m/%d/%y")
tsData <- zoo(data$Price, order.by = data$Date)
data$Obs = as.numeric(data$Date - min(data$Date) + 1)

# find, filter, drop NAs
sum(is.na(data$Price))
dataWithNA <- data[apply(is.na(data), 1, any), ]
data = data[data$Date > as.Date("2015-01-18"), ]
data <- na.omit(data)

### investigate ================================================================
# vanilla
statsPlot(data, "Price")

# differenced
diffData = data
diffData$Price = c(NA, diff(data$Price))
statsPlot(diffData, "Price")

# fractionally differenced
fracModel = fracdiff(data$Price, nar=0, nma=0)
fracData = data
fracData$Price = diffseries(data$Price, fracModel$d)
statsPlot(fracData, "Price")

# trimmed
trimFracDiff = fracData[50:nrow(fracData),]
statsPlot(trimFracDiff, "Price")

### ARIMA vs ARFIMA =====================================================================

# ARIMA (NA, full difference too close to white noise)
arimaModel = NULL
arimaAICc = 0
for (p in 0:2)
{
  for (q in 0:2)
  {
    
    # ARIMA (dynamic mean)
    testModel = arfima(data$Price, order=c(p, 1, q), fixed=list(frac=0), dmean=TRUE)
    resids = residuals(testModel)[[1]]
    testAICc = custom_AICc(resids, p, q, 1)  # additional param for dynamic mean
    
    if (testAICc < arimaAICc)
    {
      arimaAICc = testAICc
      arimaModel = testModel
    }
    
    # ARIMA (no dynamic mean)
    testModel = arfima(data$Price, order=c(p, 1, q), fixed=list(frac=0), dmean=FALSE)
    resids = residuals(testModel)[[1]]
    testAICc = custom_AICc(resids, p, q, 0)
    
    if (testAICc < arimaAICc)
    {
      arimaAICc = testAICc
      arimaModel = testModel
    }
    
  }
}

# ARFIMA
arfimaModel = NULL
arfimaAICc = 0
for (p in 0:2)
{
  for (q in 0:2)
  {
    
    # ARFIMA (dynamic mean)
    testModel = arfima(data$Price, order=c(p, 0, q), fixed=list(frac=fracModel$d), dmean=TRUE)
    resids = residuals(testModel)[[1]]
    testAICc = custom_AICc(resids, p, q, 1)  # additional param for dynamic mean
    
    if (testAICc < arfimaAICc)
    {
      arfimaAICc = testAICc
      arfimaModel = testModel
    }
    
    # ARFIMA (no dynamic mean)
    testModel = arfima(data$Price, order=c(p, 0, q), fixed=list(frac=fracModel$d), dmean=FALSE)
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

stats_plot(fittedData, "Fitted")
stats_plot(fittedData, "FittedDiff")
stats_plot(fittedData, "Resids")
stats_plot(fittedData, "ResidsSqrd")

# fits
fit_plot(data[20:nrow(data),], "Price", fittedData, "Fitted")

# residuals
statsPlot(fittedData, "Resids")
statsPlot(fittedData, "ResidsSqrd")

### ARCH vs GARCH vs FIGARCH ===================================================

### FIGARCH
figarchSpec  = ugarchspec(variance.model=list(model="fiGARCH", garchOrder=c(1,1)),
                          mean.model=list(armaOrder=c(0,0), include.mean=FALSE),
                          distribution.model="std") # (original data distribution)

figarchModel = ugarchfit(spec=figarchSpec, data=fittedData$Resids)

# manual fit (fitted() and residuals() fail)
omega = coef(figarchModel)[["omega"]]
alpha1 = coef(figarchModel)[["alpha1"]]
beta1 = coef(figarchModel)[["beta1"]]
delta = coef(figarchModel)[["delta"]]


figarchVar = numeric(length(fittedData$Resids))
figarchVar[1] = var(fittedData$Resids) # initialize first unconditional variance

for (t in 2:length(fittedData$Resids))
{
  fracLag = (1 - (1 - delta) * (t - 1)^(-delta)) * figarchVar[t - 1]
  figarchVar[t] = omega + alpha1 * (fittedData$Resids[t - 1]^2) + beta1 * fracLag
}


figarchFit = fittedData
figarchFit$FittedVar = figarchVar
figarchResids = fittedData$Resids / sqrt(figarchVar)
figarchFit$VarResids = figarchResids

stats_plot(figarchFit, "VarResids")

# *** MINUS 1 PARAMATERS FOR "SHAPE" IN COEFFICIENTS (from setting distribution to "std")
# *** PLUS 1 FOR FRACTIONAL INTERGRATION
figarchAICc = custom_AICc(figarchFit$VarResids, 1, 1, 3) # 1 p, 1 q, 1 const, 1 delta, 1 fractional


### GARCH
garchSpec  = ugarchspec(variance.model=list(model="fGARCH", submodel="GARCH", garchOrder=c(1,1)),
                        mean.model=list(armaOrder=c(0,0), include.mean=FALSE),
                        distribution.model="std")

garchModel = ugarchfit(spec=garchSpec, data=fittedData$Resids)


# manual fit (fitted() and residuals() fail)
omega = coef(garchModel)[["omega"]]
alpha1 = coef(garchModel)[["alpha1"]]
beta1 = coef(garchModel)[["beta1"]]

garchVar = numeric(length(fittedData$Resids))
garchVar[1] = omega / (1 - alpha1 - beta1) # initialize first unconditional variance

for (t in 2:length(fittedData$Resids))
{
  garchVar[t] = omega + alpha1 * (fittedData$Resids[t - 1]^2) + beta1 * garchVar[t-1]
}

garchFit = fittedData
garchFit$FittedVar = garchVar
garchResids = fittedData$Resids / sqrt(garchVar)
garchFit$VarResids = garchResids

stats_plot(garchFit, "VarResids")

garchAICc = custom_AICc(garchFit$VarResids, 1, 1, 2) # 1 p, 1 q, 1 const (omega) + prior estimated var


### ARCH

# select best ARCH based on AICc
n = nrow(fittedData)
archAICc = 0
archModel = NULL
archFit = NULL


for (q in 1:10)
{
  
  archSpec  = ugarchspec(variance.model=list(model="fGARCH", submodel="GARCH", garchOrder=c(0,q)),
                         mean.model=list(armaOrder=c(0,0), include.mean=FALSE),
                         distribution.model="std")
  
  tryCatch(
    {
      testModel = ugarchfit(spec=archSpec, data=fittedData$Resids)
      
      # coefficients
      omega <- coef(testModel)[["omega"]]
      alphas <- coef(testModel)[grep("^alpha", names(coef(testModel)))]
      
      # initialize variance
      testVar <- numeric(length(fittedData$Resids))
      testVar[1:q] <- var(fittedData$Resids)  # Initialize first q unconditional variances
      
      # conditional variance
      for (t in (q + 1):length(fittedData$Resids)) {
        testVar[t] <- omega + sum(alphas * (fittedData$Resids[(t - 1):(t - q)]^2))
      }
      
      # calculate residuals
      archResids <- fittedData$Resids / sqrt(testVar)
      
      # custom AICc
      archAICc = custom_AICc(archResids, 0, q, 1) # 1 p, 1 q, 1 const (omega)
      
      
      if (testAICc == archAICc)
      {
        archModel = testModel
        archAICc = testAICc
        archVar = testVar
      }
      
      if (testAICc < archAICc)
      {
        archModel = testModel
        archAICc = testAICc
        archVar = testVar
      }
      
    },warning = function(w) {
      message(conditionMessage(w))
    }
  )
  
}

archFit = fittedData
archFit$FittedVar = testVar
archResids = fittedData$Resids / sqrt(testVar)
archFit$VarResids = archResids

# choose best model:
figarchAICc
garchAICc
archAICc

stats_plot(figarchFit, "FittedVar")












