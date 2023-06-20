# build Docker image
docker build -t dashboard-scto .
docker build -t dashboard-scto --cache-from test-dashboard .

# test in local
docker run -p 8501:8501 dashboard-scto
