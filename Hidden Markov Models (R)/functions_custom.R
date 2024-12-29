
stats_plot = function(data, y)
{
  target = data[[y]]
  
  ### basic stats
  basicStats = data.frame(mu = round(mean(target, na.rm=TRUE), 5), 
                          sigma = round(sd(target, na.rm=TRUE), 5),
                          variance = round(sd(target, na.rm=TRUE)^2, 5))
  
  rownames(basicStats) = NULL
  
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
  statsPlt = (wrap_elements(basicPlt) | testPlt)
  
  ### plots
  rollVar = rollapply(target, width=10, FUN=var, fill=NA, align="right")
  
  timePlt = ggplot(data=data.frame(Values=target, Obs=c(1:length(target))), aes(x=Obs, y=Values)) +
    geom_line(linetype=1, color="black") +
    geom_hline(yintercept=mean(target), linetype=2, color="blue") +
    theme_minimal() +
    labs(title="Series")
  
  varPlt = ggplot(data=data.frame(rollVar=rollVar, Obs=c(1:length(target))), aes(x=Obs, y=rollVar)) +
    geom_line(linetype=1, color="black") +
    theme_minimal() +
    labs(title="Rolling Variance", y="10-Period Variance")
  
  
  bin_width = (max(target, na.rm = TRUE) - min(target, na.rm = TRUE)) / 30 # 30 bins
  distPlt = ggplot(data=data.frame(column=target), aes(x=column)) +
    geom_histogram(aes(y = ..density..), binwidth=bin_width, fill = "grey", color = "black", alpha = 0.7) +
    geom_density(color = "blue", linewidth = 1) +
    labs(title = "Distribution") +
    theme_minimal()
  
  
  qqPlt = ggplot(data = data.frame(values=target), aes(sample=values)) +
    stat_qq() +
    stat_qq_line(linetype=2, color="blue") +
    labs(title="Quantiles", x = "Theoretical Quantiles", y = "Sample Quantiles") +
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
  finalPlt = statsPlt / 
    (timePlt | distPlt) /
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

find_distro = function(data)
{
  
  # plots
  descdist(data)
  
  # normal
  tryCatch(
    {
      normalResult = ks.test(data, "pnorm", mean = mean(data), sd = sd(data))
      print(paste("Normal:", normalResult$p.value))
    },
    error = function(e)
    {
      print("Normal: FAIL")
      message(conditionMessage(e))
    }
  )
  
  # student's t
  tryCatch(
    {
      studentFit = fit.st(data)
      m = studentFit$par.ests[["mu"]]
      s = studentFit$par.ests[["sigma"]]
      df = studentFit$par.ests[["nu"]]
      studentsResult = ks.test(data, function(x) pt((x - m) / s, df = df))
      print(paste("Student's T:", studentsResult$p.value))
    },
    error = function(e)
    {
      print("Student's T: FAIL")
      message(conditionMessage(e))
    }
  )
  
  # uniform
  tryCatch(
    {
      uniformResult = ad.test(data, null = "punif")
      print(paste("Uniform:", uniformResult$p.value))
    },
    error = function(e)
    {
      print("Uniform: FAIL")
      message(conditionMessage(e))
    }
  )
  
  # exponential
  tryCatch(
    {
      lambdaEst = 1 / mean(abs(data))
      expResult = ks.test(abs(data), "pexp", rate = lambdaEst)
      print(paste("Exponential (Abs Val):", expResult$p.value))
    },
    error = function(e)
    {
      print("Exponential: FAIL")
      message(conditionMessage(e))
    }
  )
  
  # logistic
  tryCatch(
    {
      sEst = sd(data) * sqrt(3) / pi  # Scale parameter
      logisticResult = ks.test(data, "plogis", location = mean(data), scale = sEst)
      print(paste("Logistic:", logisticResult$p.value))
    },
    error = function(e)
    {
      print("Logistic: FAIL")
      message(conditionMessage(e))
    }
  )
  
  
  # lognormal
  tryCatch(
    {
      logResult = ks.test(abs(data), "plnorm", meanlog = mean(log(abs(data))), sdlog = sd(log(data)))
      print(paste("Log Normal (Abs Val):", logResult$p.value))
    },
    error = function(e)
    {
      print("Log Normal (Abs Val): FAIL")
      message(conditionMessage(e))
    }
  )
  
  
  # gamma
  tryCatch(
    {
      gammaFit = fitdistr(abs(data), "gamma")
      shapeEst = gammaFit$estimate["shape"]
      rateEst = gammaFit$estimate["rate"]
      gammaResult = ks.test(abs(data), "pgamma", shape = shapeEst, rate = rateEst)
      print(paste("Gamma (Abs Val):", gammaResult$p.value))
    },
    error = function(e)
    {
      print("Gamma (Abs Val): FAIL")
      message(conditionMessage(e))
    }
  )
  
  
  # weibull
  tryCatch(
    {
      weibull_fit = fitdistr(abs(data[data != 0]), densfun = "weibull")
      shape_est = weibull_fit$estimate["shape"]
      scale_est = weibull_fit$estimate["scale"]
      weibullResult = ks.test(abs(data), "pweibull", shape = shape_est, scale = scale_est)
      print(paste("Weibull (Abs Val):", weibullResult$p.value))
    },
    error = function(e)
    {
      print("Weibull (Abs Val): FAIL")
      message(conditionMessage(e))
    }
  )
  
  # laplace
  tryCatch(
    {
      plaplace <- function(x, location, scale) {
        if (length(x) == 0) {
          return(numeric(0))  # Return zero-length numeric vector
        }
        p <- ifelse(x < location, 
                    0.5 * exp((x - location) / scale), 
                    1 - 0.5 * exp(-(x - location) / scale))
        return(p)
      }
      
      dlaplace <- function(x, location, scale) {
        if (length(x) == 0) {
          return(numeric(0))  # Return zero-length numeric vector for density
        }
        d <- 1 / (2 * scale) * exp(-abs(x - location) / scale)
        return(d)
      }
      
      laplaceFit <- fitdist(data, dlaplace, start = list(location = mean(data), scale = sd(data)))
      location = laplaceFit$estimate["location"]
      scale = laplaceFit$estimate["scale"]
      
      laplaceResult = ks.test(data, plaplace, location = location, scale = scale)
      print(paste("Laplace:", laplaceResult$p.value))
    },
    error = function(e)
    {
      print("Laplace (Abs Val): FAIL")
      message(conditionMessage(e))
    }
  )
  
}

median_smooth = function(data, window_size = 3)
{
  
  smoothedFront = numeric(length(data) - window_size + 1)
  smoothedBack = numeric(window_size - 1)
  
  # smooth front
  for (i in 1:(length(data) - window_size + 1))
  {
    smoothedFront[i] = median(data[i:(i + window_size - 1)])
  }
  
  # smooth back
  for (i in 0:(window_size - 2))
  {
    smoothedBack[i+1] = median(data[(length(data) - i - (window_size-1)):length(data) - i])
  }
  
  smoothed = c(smoothedFront, smoothedBack)
  
  return(smoothed)
  
}
