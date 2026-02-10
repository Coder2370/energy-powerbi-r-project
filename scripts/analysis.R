# analysis.R
#
# This script reads a processed dataset containing renewable energy share,
# energy use per capita, population and GDP per capita for selected countries.
# It produces a series of plots using ggplot2 and performs a basic
# clustering and forecasting exercise.  The output images are saved into
# the figures directory relative to this script.

# Helper function to ensure packages are installed
install_if_missing <- function(pkg){
  if (!require(pkg, character.only = TRUE)) {
    install.packages(pkg, repos = "https://cloud.r-project.org")
    library(pkg, character.only = TRUE)
  }
}

# Required packages
packages <- c("ggplot2", "dplyr", "forecast", "stats")
lapply(packages, install_if_missing)

# Read the processed data
# The working directory is assumed to be the scripts folder; adjust paths accordingly
project_root <- normalizePath(file.path(dirname(sys.frame(1)$ofile), ".."))
data_path <- file.path(project_root, "data", "processed_data.csv")
fig_path <- file.path(project_root, "figures")
if (!dir.exists(fig_path)) dir.create(fig_path)

data <- read.csv(data_path, stringsAsFactors = FALSE)

# Convert year to numeric for plotting
data$year <- as.numeric(as.character(data$year))

# 1. Renewable energy share trends
p1 <- ggplot(data, aes(x = year, y = renewable_share, colour = country_code)) +
  geom_line() +
  theme_minimal() +
  labs(
    title = "Renewable energy share over time",
    x = "Year",
    y = "Renewable share (% of final energy consumption)",
    colour = "Country"
  )

# Save plot
ggsave(filename = file.path(fig_path, "renewable_share_trends_R.png"), plot = p1, width = 10, height = 6)

# 2. Energy use per capita trends
p2 <- ggplot(data, aes(x = year, y = energy_use_per_capita, colour = country_code)) +
  geom_line() +
  theme_minimal() +
  labs(
    title = "Energy use per capita over time",
    x = "Year",
    y = "Energy use per capita (kg of oil equivalent)",
    colour = "Country"
  )

# Save plot
ggsave(filename = file.path(fig_path, "energy_use_per_capita_trends_R.png"), plot = p2, width = 10, height = 6)

# 3. Scatter plot for the latest year
latest_year <- max(data$year, na.rm = TRUE)
latest <- dplyr::filter(data, year == latest_year)

p3 <- ggplot(latest, aes(x = energy_use_per_capita, y = renewable_share, label = country_code)) +
  geom_point(aes(colour = country_code), size = 3) +
  geom_text(nudge_y = 0.5, size = 3, hjust = 1) +
  theme_minimal() +
  labs(
    title = paste("Renewable share vs. energy use per capita (", latest_year, ")", sep = ""),
    x = "Energy use per capita (kg of oil equivalent)",
    y = "Renewable share (% of final energy consumption)",
    colour = "Country"
  )

# Save plot
ggsave(filename = file.path(fig_path, "renewable_vs_energyuse_scatter_R.png"), plot = p3, width = 8, height = 6)

# 4. K‑means clustering on latest year (energy_use_per_capita vs renewable_share)
# Prepare data for clustering
cluster_data <- latest %>% dplyr::select(energy_use_per_capita, renewable_share) %>% na.omit()
row.names(cluster_data) <- latest$country_code[complete.cases(latest[, c("energy_use_per_capita", "renewable_share")])]

# Scale the variables
scaled_data <- scale(cluster_data)
set.seed(42)
kmeans_res <- kmeans(scaled_data, centers = 3, nstart = 10)
latest$cluster <- as.factor(kmeans_res$cluster)

p4 <- ggplot(latest, aes(x = energy_use_per_capita, y = renewable_share, colour = cluster)) +
  geom_point(size = 3) +
  theme_minimal() +
  labs(
    title = paste("K-means clustering on renewable share vs energy use per capita (", latest_year, ")", sep = ""),
    x = "Energy use per capita (kg of oil equivalent)",
    y = "Renewable share (% of final energy consumption)",
    colour = "Cluster"
  )

# Save plot
ggsave(filename = file.path(fig_path, "kmeans_clusters_R.png"), plot = p4, width = 8, height = 6)

# 5. Forecasting renewable share for the USA
usa_data <- dplyr::filter(data, country_code == "USA")
# Create a time series object.  We assume annual frequency starting from the minimum year.
ts_series <- ts(usa_data$renewable_share, start = min(usa_data$year), end = max(usa_data$year), frequency = 1)

# Fit an automatic ARIMA model
arima_model <- forecast::auto.arima(ts_series)
forecast_res <- forecast::forecast(arima_model, h = 10)

# Plot and save the forecast
png(filename = file.path(fig_path, "usa_renewable_share_forecast_R.png"), width = 800, height = 600)
plot(forecast_res, main = "Forecast of Renewable Energy Share for USA")
dev.off()

# End of script
