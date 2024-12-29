

### STUDENT'S T =========
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

### POSITIVE UNIFORM =============
# Define the class for Positive Uniform distribution
setClass("posUnifDist", contains = "response")

# Constructor for posUnifDist
setGeneric("posUnifDist", function(y, pstart = NULL, fixed = NULL, ...) standardGeneric("posUnifDist"))

setMethod("posUnifDist", signature(y = "ANY"),
          function(y, pstart = NULL, fixed = NULL, ...) {
            y = matrix(y, length(y))  # Ensure y is a matrix
            x = matrix(1)  # Placeholder for design matrix
            
            # Filter only positive values
            valid_y = y[y > 0]
            if (length(valid_y) == 0) stop("No positive values found in the data for posUnifDist.")
            
            # Set initial parameters (min and max)
            parameters = list(min = min(valid_y), max = max(valid_y))
            if (!is.null(pstart)) parameters = list(min = pstart[1], max = pstart[2])
            
            npar = length(parameters)
            
            # Fixed parameters, default to FALSE
            if (is.null(fixed)) fixed = rep(FALSE, npar)
            
            new("posUnifDist", y = y, x = x, parameters = parameters, fixed = fixed, npar = npar)
          }
)

# Density method for posUnifDist
setMethod("dens", "posUnifDist",
          function(object, log = FALSE) {
            y = object@y
            pars = object@parameters
            
            # Uniform density for y > 0, set density to 0 otherwise
            density = ifelse(y > 0, dunif(y, min = pars$min, max = pars$max), 0)
            
            if (log) {
              return(log(density))
            } else {
              return(density)
            }
          }
)

# Fit method for posUnifDist
setMethod("fit", "posUnifDist",
          function(object, w) {
            if (missing(w)) w = rep(1, length(object@y))  # Default weights
            y = object@y
            
            # Filter only positive values and apply weights
            valid_y = y[y > 0 & w > 0]
            if (length(valid_y) == 0) stop("No positive values with positive weights for posUnifDist.")
            
            # Fit Uniform distribution by calculating min and max
            pars = c(min = min(valid_y), max = max(valid_y))
            
            object@parameters = list(min = pars["min"], max = pars["max"])
            return(object)
          }
)


### NEGATIVE WEIBULL ==========
# Define the class for Negative Weibull distribution
setClass("negWeibull", contains = "response")

# Constructor for negWeibull
setGeneric("negWeibull", function(y, pstart = NULL, fixed = NULL, ...) standardGeneric("negWeibull"))

setMethod("negWeibull", signature(y = "ANY"),
          function(y, pstart = NULL, fixed = NULL, ...) {
            y = matrix(y, length(y))  # Ensure y is a matrix
            
            # Filter only negative values
            valid_y = y[y < 0]
            if (length(valid_y) == 0) stop("No negative values found in the data for negWeibull.")
            
            valid_y = abs(valid_y)  # Convert to positive values for fitting
            x = matrix(1)  # Placeholder for design matrix
            
            # Set initial parameters (lambda and k)
            parameters = list(lambda = mean(valid_y), k = 1.5)
            if (!is.null(pstart)) parameters = list(lambda = pstart[1], k = pstart[2])
            
            npar = length(parameters)
            
            # Fixed parameters, default to FALSE
            if (is.null(fixed)) fixed = rep(FALSE, npar)
            
            new("negWeibull", y = y, x = x, parameters = parameters, fixed = fixed, npar = npar)
          }
)

# Density method for negWeibull
setMethod("dens", "negWeibull",
          function(object, log = FALSE) {
            y <- object@y
            pars <- object@parameters
            
            # Compute the density for Weibull
            density <- ifelse(y < 0,
                              (pars$k / pars$lambda) * ((abs(y) / pars$lambda)^(pars$k - 1)) * exp(-(abs(y) / pars$lambda)^pars$k),
                              0)  # Assign 0 for invalid values (y >= 0)

            if (log) {
              return(log(density))  # Return log density directly
            } else {
              return(density)  # Exponentiate to return regular density
            }
          }
)

# Fit method for negWeibull
setMethod("fit", "negWeibull",
          function(object, w) {
            if (missing(w)) w = rep(1, length(object@y))  # Default weights
            y = object@y
            
            # Filter only negative values and apply weights
            valid_y = y[y < 0 & w > 0]
            if (length(valid_y) == 0) stop("No negative values with positive weights for negWeibull.")
            
            valid_y = abs(valid_y)  # Convert to positive values for fitting
            
            # Use object@parameters for starting values
            start_values <- list(scale = object@parameters$lambda, shape = object@parameters$k)
            
            # Fit Weibull distribution using starting values
            fit <- MASS::fitdistr(valid_y, "weibull", start = start_values)
            
            # Update object parameters with fitted values
            object@parameters$lambda <- fit$estimate["scale"]
            object@parameters$k <- fit$estimate["shape"]
            
            return(object)
          }
)

### POSITIVE WEIBULL ========
# Define the class for Positive Weibull distribution
setClass("posWeibull", contains = "response")

# Constructor for posWeibull
setGeneric("posWeibull", function(y, pstart = NULL, fixed = NULL, ...) standardGeneric("posWeibull"))

setMethod("posWeibull", signature(y = "ANY"),
          function(y, pstart = NULL, fixed = NULL, ...) {
            y <- matrix(y, length(y))  # Ensure y is a matrix
            
            # Filter only positive values
            valid_y <- y[y > 0]
            if (length(valid_y) == 0) stop("No positive values found in the data for posWeibull.")
            
            x <- matrix(1)  # Placeholder for design matrix
            
            # Set initial parameters (lambda and k)
            parameters <- list(lambda = mean(valid_y), k = 1.5)
            if (!is.null(pstart)) parameters <- list(lambda = pstart[1], k = pstart[2])
            
            # Fixed parameters, default to FALSE
            npar <- length(parameters)
            if (is.null(fixed)) fixed <- rep(FALSE, npar)
            
            new("posWeibull", y = y, x = x, parameters = parameters, fixed = fixed, npar = npar)
          }
)

# Density method for posWeibull
setMethod("dens", "posWeibull",
          function(object, log = FALSE) {
            y <- object@y
            pars <- object@parameters
            
            # Compute the density for Weibull
            density <- ifelse(y > 0,
                              (pars$k / pars$lambda) * ((y / pars$lambda)^(pars$k - 1)) * exp(-(y / pars$lambda)^pars$k),
                              0)  # Assign 0 for invalid values (y <= 0)
            
            if (log) {
              return(log(density))
            } else {
              return(density)
            }
          }
)

# Fit method for posWeibull
setMethod("fit", "posWeibull",
          function(object, w) {
            if (missing(w)) w <- rep(1, length(object@y))  # Default weights
            y <- object@y
            
            # Filter only positive values and apply weights
            valid_y <- y[y > 0 & w > 0]
            if (length(valid_y) == 0) stop("No positive values with positive weights for posWeibull.")
            
            # Use object@parameters for starting values
            start_values <- list(scale = object@parameters$lambda, shape = object@parameters$k)
            
            # Fit Weibull distribution using starting values
            fit <- MASS::fitdistr(valid_y, "weibull", start = start_values)
            
            # Update object parameters with fitted values
            object@parameters$lambda <- fit$estimate["scale"]
            object@parameters$k <- fit$estimate["shape"]
            
            return(object)
          }
)

# Predict method for posWeibull
setMethod("predict", "posWeibull",
          function(object) {
            # Return the mean of the Weibull distribution
            pars <- object@parameters
            return(pars$lambda * gamma(1 + 1 / pars$k))
          }
)








### POSITIVE GAMMA =========
setClass("posGamma", contains = "response")

setGeneric("posGamma", function(y, pstart = NULL, fixed = NULL, ...) standardGeneric("posGamma"))

setMethod("posGamma", signature(y = "ANY"),
          function(y, pstart = NULL, fixed = NULL, ...) {
            y <- matrix(y, length(y))  # Ensure y is a matrix
            
            # Filter only positive values
            valid_y <- y[y > 0]
            if (length(valid_y) == 0) stop("No positive values found for posGamma.")
            
            # Set initial parameters
            parameters <- list(shape = 2, rate = 1)  # Default values
            if (!is.null(pstart)) {
              parameters <- list(shape = pstart[1], rate = pstart[2])
            }
            
            npar <- length(parameters)
            if (is.null(fixed)) fixed <- rep(FALSE, npar)
            
            new("posGamma", y = y, x = matrix(1), parameters = parameters, fixed = fixed, npar = npar)
          }
)

setMethod("dens", "posGamma",
          function(object, log = FALSE) {
            y <- object@y
            pars <- object@parameters
            
            # Compute density for Gamma
            density <- ifelse(y > 0,
                              dgamma(y, shape = pars$shape, rate = pars$rate, log = log),
                              if (log) -Inf else 0)  # Log density is -Inf for invalid values
            
            return(density)
          }
)

setMethod("fit", "posGamma",
          function(object, w) {
            if (missing(w)) w <- rep(1, length(object@y))  # Default weights
            y <- object@y
            
            # Filter only positive values and apply weights
            valid_y <- y[y > 0 & w > 0]
            if (length(valid_y) == 0) stop("No valid positive values for Gamma fitting.")
            
            # Fit Gamma distribution using MASS::fitdistr
            fit <- MASS::fitdistr(valid_y, "gamma", start = list(shape = object@parameters$shape, rate = object@parameters$rate))
            
            # Update object parameters with fitted values
            object@parameters$shape <- fit$estimate["shape"]
            object@parameters$rate <- fit$estimate["rate"]
            
            return(object)
          }
)

setMethod("predict", "posGamma",
  function(object) {
    pars <- object@parameters
    return(pars$shape / pars$rate)
  }
)


### NEGATIVE GAMMA
setClass("negGamma", contains = "response")

setGeneric("negGamma", function(y, pstart = NULL, fixed = NULL, ...) standardGeneric("negGamma"))

setMethod("negGamma", signature(y = "ANY"),
          function(y, pstart = NULL, fixed = NULL, ...) {
            y <- matrix(y, length(y))  # Ensure y is a matrix
            
            # Filter only negative values
            valid_y <- y[y < 0]
            if (length(valid_y) == 0) stop("No negative values found for negGamma.")
            
            # Set initial parameters
            parameters <- list(shape = 2, rate = 1)  # Default values
            if (!is.null(pstart)) {
              parameters <- list(shape = pstart[1], rate = pstart[2])
            }
            
            npar <- length(parameters)
            if (is.null(fixed)) fixed <- rep(FALSE, npar)
            
            new("negGamma", y = y, x = matrix(1), parameters = parameters, fixed = fixed, npar = npar)
          }
)

setMethod("dens", "negGamma",
          function(object, log = FALSE) {
            y <- object@y
            pars <- object@parameters
            
            # Transform negative values to positive for Gamma PDF
            density <- ifelse(y < 0,
                              dgamma(-y, shape = pars$shape, rate = pars$rate, log = log),  # Use -y for density calculation
                              if (log) -Inf else 0)  # Log density is -Inf for invalid values
            
            return(density)
          }
)

setMethod("fit", "negGamma",
          function(object, w) {
            if (missing(w)) w <- rep(1, length(object@y))  # Default weights
            y <- object@y
            
            # Filter only negative values and apply weights
            valid_y <- y[y < 0 & w > 0]
            if (length(valid_y) == 0) stop("No valid negative values for Gamma fitting.")
            
            # Transform negative values to positive for fitting
            valid_y <- -valid_y
            
            # Fit Gamma distribution using MASS::fitdistr
            fit <- MASS::fitdistr(valid_y, "gamma", start = list(shape = object@parameters$shape, rate = object@parameters$rate))
            
            # Update object parameters with fitted values
            object@parameters$shape <- fit$estimate["shape"]
            object@parameters$rate <- fit$estimate["rate"]
            
            return(object)
          }
)

setMethod("predict", "negGamma",
          function(object) {
            pars <- object@parameters
            return(-pars$shape / pars$rate)  # Mean of the negative Gamma distribution
          }
)


### POSITIVE LOGNORMAL =======
setClass("posLogNormal", contains = "response")

setGeneric("posLogNormal", function(y, pstart = NULL, fixed = NULL, ...) standardGeneric("posLogNormal"))

setMethod("posLogNormal", signature(y = "ANY"),
          function(y, pstart = NULL, fixed = NULL, ...) {
            y <- matrix(y, length(y))  # Ensure y is a matrix
            
            # Filter only positive values
            valid_y <- y[y > 0]
            if (length(valid_y) == 0) stop("No positive values found for posLogNormal.")
            
            # Set initial parameters
            parameters <- list(meanlog = log(mean(valid_y)), sdlog = log(sd(valid_y)))  # Default values
            if (!is.null(pstart)) {
              parameters <- list(meanlog = pstart[1], sdlog = pstart[2])
            }
            
            npar <- length(parameters)
            if (is.null(fixed)) fixed <- rep(FALSE, npar)
            
            new("posLogNormal", y = y, x = matrix(1), parameters = parameters, fixed = fixed, npar = npar)
          }
)

setMethod("dens", "posLogNormal",
          function(object, log = FALSE) {
            y <- object@y
            pars <- object@parameters
            
            # Compute density for Log-Normal
            density <- ifelse(y > 0,
                              dlnorm(y, meanlog = pars$meanlog, sdlog = pars$sdlog, log = log),
                              if (log) -Inf else 0)  # Log density is -Inf for invalid values
            
            return(density)
          }
)

setMethod("fit", "posLogNormal",
          function(object, w) {
            if (missing(w)) w <- rep(1, length(object@y))  # Default weights
            y <- object@y
            
            # Filter only positive values and apply weights
            valid_y <- y[y > 0 & w > 0]
            if (length(valid_y) == 0) stop("No valid positive values for Log-Normal fitting.")
            
            # Log-transform the positive values
            log_y <- log(valid_y)
            
            # Fit a normal distribution to the log-transformed values
            fit <- MASS::fitdistr(log_y, "normal")
            
            # Update object parameters with fitted values
            object@parameters$meanlog <- fit$estimate["mean"]
            object@parameters$sdlog <- fit$estimate["sd"]
            
            return(object)
          }
)

setMethod("predict", "posLogNormal",
          function(object) {
            pars <- object@parameters
            return(exp(pars$meanlog + (pars$sdlog^2) / 2))  # Mean of the Log-Normal distribution
          }
)
### POSITIVE BETA =====
# Define the class for Positive Beta distribution
setClass("posBeta", contains = "response")

# Constructor for posBeta
setGeneric("posBeta", function(y, pstart = NULL, fixed = NULL, ...) standardGeneric("posBeta"))

setMethod("posBeta", signature(y = "ANY"),
          function(y, pstart = NULL, fixed = NULL, ...) {
            y <- matrix(y, length(y))  # Ensure y is a matrix
            
            # Filter values between 0 and 1
            valid_y <- y[y > 0 & y < 1]
            if (length(valid_y) == 0) stop("No valid values in (0, 1) for posBeta.")
            
            # Set initial parameters
            parameters <- list(shape1 = 2, shape2 = 2)  # Default values
            if (!is.null(pstart)) {
              parameters <- list(shape1 = pstart[1], shape2 = pstart[2])
            }
            
            npar <- length(parameters)
            if (is.null(fixed)) fixed <- rep(FALSE, npar)
            
            new("posBeta", y = y, x = matrix(1), parameters = parameters, fixed = fixed, npar = npar)
          }
)

# Density method for posBeta
setMethod("dens", "posBeta",
          function(object, log = FALSE) {
            y <- object@y
            pars <- object@parameters
            
            # Compute density for Beta
            density <- ifelse(y > 0 & y < 1,
                              dbeta(y, shape1 = pars$shape1, shape2 = pars$shape2, log = log),
                              if (log) -Inf else 0)  # Assign -Inf (log) or 0 (regular) for invalid values
            
            return(density)
          }
)

# Fit method for posBeta
setMethod("fit", "posBeta",
          function(object, w) {
            if (missing(w)) w <- rep(1, length(object@y))  # Default weights
            y <- object@y
            
            # Filter values between 0 and 1 and apply weights
            valid_y <- y[y > 0 & y < 1 & w > 0]
            if (length(valid_y) == 0) stop("No valid values in (0, 1) for Beta fitting.")
            
            # Fit Beta distribution using MASS::fitdistr
            fit <- MASS::fitdistr(valid_y, dbeta, 
                                  start = list(shape1 = object@parameters$shape1, 
                                               shape2 = object@parameters$shape2))
            
            # Update object parameters with fitted values
            object@parameters$shape1 <- fit$estimate["shape1"]
            object@parameters$shape2 <- fit$estimate["shape2"]
            
            return(object)
          }
)

# Predict method for posBeta (Mean of the Beta distribution)
setMethod("predict", "posBeta",
          function(object) {
            pars <- object@parameters
            return(pars$shape1 / (pars$shape1 + pars$shape2))  # Mean of the Beta distribution
          }
)