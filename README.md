Setting up google drive api and service account

 a. Go to https://console.cloud.google.com/
 b. Create a new project
 c. Enable the Google Drive API for your project
 d. Create a service account. Give your service account a name and description.
 e. Under Grant this service account access to project, select Project and choose the appropriate role. For Drive API access, you'll likely need at least the Storage Object Viewer role.
 f. After creating the service account, you'll see a list of service accounts. Find the one you just created and click on its name.
 g. Click the `Keys` tab
 h. Click Add key and select JSON as the key type.
 i. Click `Create`. This will download a JSON file containing your service account credentials. This file is your `credentials.json`. Store it in the same directory as that of cloned repo.
 j. Share your Google Drive folder with the service account email.
 k. Open the folder, find the folder id in the URL. Update the `folder_id` variable in main.py


create a .env file which must contain 2 parameters:
```
TOKEN= 'shopify-app-api'
MERCHANT= 'merchant-name'
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
