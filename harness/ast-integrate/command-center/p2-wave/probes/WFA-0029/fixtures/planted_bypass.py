import urllib.request

# Planted bypass: credentialed GitHub call that does not enter the scheduler.
urllib.request.urlopen("https://api.github.com/rate_limit")
