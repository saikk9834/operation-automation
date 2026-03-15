[![Python application test with Github Actions](https://github.com/perceptronq/operation-automation/actions/workflows/actions.yml/badge.svg)](https://github.com/perceptronq/operation-automation/actions/workflows/actions.yml)

Setting up google drive api and service account

 a. Go to https://console.cloud.google.com/ <br>
 b. Create a new project <br>
 c. Enable the Google Drive API for your project <br>
 d. Create a service account. Give your service account a name and description. <br>
 e. Under Grant this service account access to project, select Project and choose the appropriate role. For Drive API access, you'll likely need at least the Storage Object Viewer role. <br>
 f. After creating the service account, you'll see a list of service accounts. Find the one you just created and click on its name. <br>
 g. Click the `Keys` tab <br>
 h. Click Add key and select JSON as the key type. <br>
 i. Click `Create`. This will download a JSON file containing your service account credentials. This file is your `credentials.json`. Store it in the same directory as that of cloned repo. <br>
 j. Share your Google Drive folder with the service account email. <br>
 k. Open the folder, find the folder id in the URL. Update the `folder_id` variable in main.py <br>


create a .env file which must contain 2 parameters:
```
TOKEN='shopify-app-api'
MERCHANT='merchant-name'
SENDER_EMAIL='sender-email-address'
SENDER_PASSWORD='sender-email-password'
```


Instructions to run the app:

```
git clone https://github.com/perceptronq/operation-automation.git

cd operation-automation

python -m venv venv

(for linux)
source venv/bin/activate

(for windows)
venv\Scripts\activate

pip install -r requirements.txt

python main.py
 
```
Generate a spec file
`pyinstaller main.py --name Automate --onefile --windowed --specpath .`

Add this to Automate.spec
```
datas=[
        ('credentials.json', '.'),
        ('.env', '.'),
    ],
```

Build executable
`pyinstaller main.py --name Automate --onefile --windowed --add-data "credentials.json:." --add-data ".env:."`
