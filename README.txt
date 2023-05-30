# build Docker image
docker build -t dashboard-scto .
docker build -t dashboard-scto --cache-from test-dashboard .

# test in local
docker run -p 8501:8501 dashboard-scto





# push the Docker image to Heroku Container Registry
heroku login
heroku create kedaikopi-qc

heroku ps:type worker=basic

heroku git:remote kedaikopi-qc
heroku stack:set container
git push heroku master
