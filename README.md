# Updating the Contact Form and Students listed in Attendance

To add new students to the attendance scanner, you must..
1) Get the URL of the CSV contact form. Instead of /edit at the end of the link, replace it with /export?format=csv
2) Sign into [https://stuypulse-attendance.appspot.com/admin/settings](https://stuypulse-attendance.appspot.com/admin/settings).
3) Replace the URL with the URL found at Step 1.

# Attendance ID Scanner

Run the scanner by executing `./scanner.sh`

An optional `--offline` flag can be passed to the scanner to run it without an Internet connection.

Alternatively, an experimental Python version of the scanner is available (`scanner.py`) with the same features.

## Setting up a local development environment
#### Installing the SDK
1) Download and install the [Google App Engine SDK for Python](https://cloud.google.com/appengine/docs/standard/python/download)
#### Install dependencies
1) Install python-pip with `sudo apt-get install python-pip`
2) Install all dependencies by running `mkdir google-appengine/libs; pip install -t google-appengine/libs -r google-appengine/requirements.txt`
#### Running the development web server
1) You will need a google web service client account, follow the instructions here: [Create a Google Service account](https://cloud.google.com/docs/authentication/getting-started)
2) Set your environment variables, and set up your testing environment with this template: [Template](https://gist.github.com/vs2961/f0679ce6f9d1f38ef6e75c42acc726a2)
3) Run the above file once you set up everything
4) Go to [localhost:5000](http://localhost:5000) in a browser
#### Configure the scanner
1) Open `scanner.sh` and change the line `SERVER_ADDR=https://stuypulse-attendance.appspot.com/` to `SERVER_ADDR=localhost:8080`
2) For the experimental Python version, change the contents of the `SERVER_ADDRESS` variable to `localhost:8080`
#### Create an administrator
Visit `localhost:5000/admin/create_admin` to create an administrator
#### Deploying to Google App Engine
1) Run `gcloud config set project stuypulse-attendance`
2) Run `gcloud app deploy`
#### Automatic Email Not Working
It may be possible that less secure apps got turned on for our automatic gmail account. Please contact the web developers to turn it back off.
