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

### loading data ===============================================================

data = read.csv("/Users/karstencadley/Desktop/Time Series Forecasting/Data/Bitcoin/Daily_01DEC14-20DEC2024_FRED.csv", header = TRUE)

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


### functions ==================================================================
statsPlot = function(data, y)
{
  target = data[[y]]
  
  ### basic stats
  basicStats = data.frame(mu = round(mean(target, na.rm=TRUE), 5), 
                          sigma = round(sd(target, na.rm=TRUE), 5),
                          variance = round(sd(target, na.rm=TRUE)^2, 5))
  
  rownames(basicStats) <- NULL
  
  basicPlt = tableGrob(basicStats, rows="", theme=ttheme_default(base_size=12))
  
  ### relevant tests
  # zero mean
  tests = t.test(target, mu=0)
  tests = data.frame(test="T-Test", p.value = round(tests$p.value, 5), h0="Zero Mean")
  
  # non stationary
  adfTest = adf.test(na.omit(target))
  adfTest = data.frame(test="Ad-Fuller", p.value = round(adfTest$p.value, 5), h0="Non-Stationary")
  tests = rbind(tests, adfTest)
  
  # normally distributed (weight towards tails)
  adTest = nortest::ad.test(target)
  adTest = data.frame(test="Anderson-Darling", p.value = round(adTest$p.value, 5), h0="Norm Distributed")
  tests = rbind(tests, adTest)
  
  # autocorrelated
  ljungs = numeric(4)
  for (i in 1:4)
  {
    ljTest = Box.test(target, lag = i*12, type = "Ljung-Box")
    ljungs[i] = round(ljTest$p.value, 3)
  }
  ljungsResult = paste(ljungs[1], ljungs[2], ljungs[3], ljungs[4])
  lbTest = data.frame(test="Ljung-Box", p.value = ljungsResult, h0="Not Autocorrelated")
  tests = rbind(tests, lbTest)
  
  # ARCH effect
  engles = numeric(5)
  for (i in 1:5)
  {
    engleTest = ArchTest(target, lags = i)
    engles[i] = round(engleTest$p.value, 3)
  }
  engleResult = paste(engles[1], engles[2], engles[3], engles[4], engles[5])
  eTest = data.frame(test="Engle", p.value = engleResult, h0="No ARCH Effect")
  tests = rbind(tests, eTest)
  
  # turn into table
  testPlt = gt(tests)
  
  # merge with basic stats
  statsPlt = (wrap_elements(basicPlt) / testPlt)
  
  ### plots
  rollVar <- rollapply(target, width=10, FUN=var, fill=NA, align="right")
  
  timePlt = ggplot(data=data.frame(Values=target, Obs=c(1:length(target))), aes(x=Obs, y=Values)) +
    geom_line(linetype=1, color="black") +
    geom_hline(yintercept=mean(target), linetype=2, color="blue") +
    theme_minimal() +
    labs(title="Series")
  
  varPlt = ggplot(data=data.frame(rollVar=rollVar, Obs=c(1:length(target))), aes(x=Obs, y=rollVar)) +
    geom_line(linetype=1, color="black") +
    theme_minimal() +
    labs(title="Rolling Variance", y="10-Period Variance")
  
  qqPlt = ggplot(data = data.frame(values=target), aes(sample=values)) +
    stat_qq() +
    stat_qq_line(linetype=2, color="blue") +
    labs(title="Distribution", x = "Theoretical Quantiles", y = "Sample Quantiles") +
    theme_minimal()
  
  acfPlt = ggAcf(na.omit(target)) + 
    theme_minimal() + 
    labs(title="ACF", y=NULL) +
    theme(panel.grid.major.x = element_blank(),
          panel.grid.minor.x = element_blank(),
          panel.grid.minor.y = element_blank())
  
  pacfPlt = ggPacf(na.omit(target)) + 
    theme_minimal() + 
    labs(title="PACF", y=NULL) +
    theme(panel.grid.major.x = element_blank(),
          panel.grid.minor.x = element_blank(),
          panel.grid.minor.y = element_blank())
  
  # create final plot
  finalPlt = ((timePlt | statsPlt) + plot_layout(widths=c(2,1))) / 
    (varPlt | qqPlt) /
    (acfPlt | pacfPlt)
  
  return(finalPlt)
  
}

custom_AICc = function(resids, p, q, addParam=0)
{
  
  N = length(na.omit(resids))

  aicc = N * log(sum(resids^2) / N) + 2 * (p + q + 1 + addParam) * (N / (N - p - q - 2 - addParam))
  
  return(aicc)
}

studentsT = function(data)
{
  
  "
  normal
  gamma
  students
  "

    fit = fitdistr(data, "t", start = list(m = mean(data), s = sd(data), df = 5), 
                  lower = c(-Inf, 1e-6, 1))
  m = fit$estimate["m"]
  s = fit$estimate["s"]
  df = fit$estimate["df"]
  
  # Step 2: Perform the KS test
  ks_result = ks.test(data, function(x) pt((x - m) / s, df = df))
  
  return(ks_result$p.value)
  
}

### investigate ================================================================
# vanilla
statsPlot(data, "Price")

# differenced
diffData = data[2:nrow(data),]
diffData$Price = diff(data$Price)
statsPlot(diffData, "Price")

# fractionally differenced
fracModel = fracdiff(data$Price, nar=0, nma=0)
fracData = data
fracData$Price = diffseries(data$Price, fracModel$d)
statsPlot(fracData, "Price")

# trimmed
statsPlot(fracData[500:nrow(fracData),], "Price")
fracData = fracData[500:nrow(fracData),]

### ARIMA vs ARFIMA ============================================================

# ARFIMA
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

# ARIMA
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

# Best Model
if (arfimaAICc < arimaAICc)
{
  fittedMeanModel = arfimaModel
}else
{
  fittedMeanModel = arimaModel  
}

# fits
fittedData = data[2:nrow(data),]
fittedData$Fitted = data$Price[-1] - residuals(fittedMeanModel)[[1]]
fittedData$Resids = residuals(fittedMeanModel)[[1]]
fittedData$ResidsSqrd = residuals(fittedMeanModel)[[1]]^2

statsPlot(fittedData, "Resids")
statsPlot(fittedData, "ResidsSqrd")

### HMM ========================================================================
# on diff
mod <- depmix(Price~1, 
              data = diffData, 
              nstates = 2, 
              family = gaussian(), 
              trstart = c(0.8, 0.2, 0.2, 0.8))  # initial transition probabilities

fittedModel = fit(mod, emcontrol=em.control(rand=TRUE))

# of fracdiff
mod <- depmix(Price~1, 
              data = fracData, 
              nstates = 2, 
              family = gaussian(), 
              trstart = c(0.8, 0.2, 0.2, 0.8))  # initial transition probabilities

fittedModel = fit(mod, emcontrol=em.control(rand=TRUE))

# on resids
mod <- depmix(Resids~1, 
              data = fittedData, 
              nstates = 2, 
              family = gaussian(), 
              trstart = c(0.8, 0.2, 0.2, 0.8))  # initial transition probabilities

fittedModel = fit(mod, emcontrol=em.control(rand=TRUE))

# custom t-distribution 
# student's t class
setClass("tDist", contains = "response")

# Constructor for tDist
setGeneric("tDist", function(y, pstart = NULL, fixed = NULL, ...) standardGeneric("tDist"))

setMethod("tDist", signature(y = "ANY"), 
          function(y, pstart = NULL, fixed = NULL, ...) {
            
            y = matrix(y, length(y))
            
            x = matrix(1)
            
            parameters = list(mu = mean(y), sigma = sd(y), df = 5)
            
            if (!is.null(pstart)) parameters = list(mu = pstart[1], sigma = pstart[2], df = pstart[3])
            
            npar = length(parameters)
            
            if (is.null(fixed))
            {
              fixed = rep(FALSE, npar)
            }
            
            new("tDist", y = y, x = x, parameters = parameters, fixed = fixed, npar = npar)
          })

# Density method for tDist
setMethod("dens", "tDist", function(object, log = FALSE) {
  
  y = object@y
  
  pars = object@parameters
  
  density = dt((y - pars$mu) / pars$sigma, df = pars$df) / pars$sigma
  
  if (log) 
  {
    return(log(density))
    
  }else
  {
    return(density)
  }
})

# Fit method for tDist
setMethod("fit", "tDist", function(object, w) {
  if (missing(w))
  {
    w = rep(1, length(object@y))  # Default weights
  }
  
  y = object@y
  
  fit = MASS::fitdistr(y, "t", start = list(m = mean(y), s = sd(y), df = 5), lower=c(-Inf, 1e-16, 3)) # ensures std become negative
  
  pars = fit$estimate
  
  object@parameters = list(mu = pars["m"], sigma = pars["s"], df = pars["df"])
  
  return(object)
})

# segment into "states"
upper = na.omit(fracData$Price[(fracData$Price > 0)])
lower = na.omit(fracData$Price[(fracData$Price <= 0)])

# confirm distributions
studentsT(upper)
studentsT(lower)

# built response model distributions
pstartUpper = c( mean(upper), sd(upper), 5)
pstartLower = c( mean(lower), sd(lower), 5)
response_models = list( list( tDist(fracData$Price, pstart = pstartUp) ),
                        list( tDist(fracData$Price, pstart = pstartDown) ))

# build transition probabilities
transition = list( transInit(~Price, nst = 2, data=fracData, pstart = c(0.8, 0.2, 1.0, -1.0), prob=TRUE),
                   transInit(~Price, nst = 2, data=fracData, pstart = c(0.2, 0.8, -1.0, 1.0), prob=TRUE))

# set an initial state (second every time)
prior <- transInit(~1, ns = 2, pstart = c(0.0, 1.0), data=data.frame(1))

# model
mod <- makeDepmix(response = response_models, 
                  transition = transition, 
                  prior = prior, 
                  homogeneous = FALSE) # lets transition probs change over time

# fit model
fittedModel = fit(mod, emcontrol=em.control(rand=TRUE)) # as needed: em.control(tol=1e-8, maxit=1000, rand=TRUE)


# pull states
hiddenStatesSmooth = posterior(fittedModel, type="smoothing")
hiddenStatesViterbi = posterior(fittedModel, type="viterbi")
hiddenStatesGlobal = posterior(fittedModel, type="global")
hiddenStatesLocal = posterior(fittedModel, type="local")
hiddenStatesFiltered = posterior(fittedModel, type="filtering")


### Plotting ===================================================================
# pre-categorized
regimes = data[500:nrow(data),]
regimes$State = hiddenStatesViterbi[[1]]

regimePlt = ggplot(regimes, aes(x=seq_along(Price), y=Price, group=1, color=as.factor(State))) +
  geom_line(linewidth = 1) +
  scale_color_manual(values = c("red", "blue"), name = "State") +
  labs(x = "Time", y = "Price", title = "Price by State") +
  theme_minimal()
regimePlt

# non-categorized
regimes = data[500:nrow(data),]
regimes$State = as.integer(hiddenStatesSmooth[,1] > hiddenStatesSmooth[,2])

regimePlt = ggplot(regimes, aes(x=seq_along(Price), y=Price, group=1, color=as.factor(State))) +
  geom_line(linewidth = 1) +
  scale_color_manual(values = c("blue", "red"), name = "State") +
  labs(x = "Time", y = "Price", title = "Price by State") +
  theme_minimal()
regimePlt













