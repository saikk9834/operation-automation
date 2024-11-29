import tkinter as tk
from tkinter import filedialog, messagebox
import sys
import os
import shutil
import csv
import script
import zipfile
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores the path in sys._MEIPASS
        base_path = sys._MEIPASS  # pylint: disable=no-member
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

load_dotenv(dotenv_path=resource_path(".env"))

def select_all_in_one_folder():
    folder_selected = filedialog.askdirectory()
    all_in_one_path.set(folder_selected)


def select_destination_folder():
    folder_selected = filedialog.askdirectory()
    destination_path.set(folder_selected)


def zip_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, _, files in os.walk(folder_path):
            for file in files:
                zipf.write(
                    os.path.join(root_dir, file),
                    os.path.relpath(
                        os.path.join(root_dir, file), os.path.join(folder_path, "..")
                    ),
                )


def remove_empty_folders(path):
    for root_dir, dirs, files in os.walk(path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root_dir, dir_name)
            if not os.listdir(dir_path):
                os.rmdir(dir_path)


def upload_to_drive(file_path, folder_id):
    try:
        SCOPES = ["https://www.googleapis.com/auth/drive.file"]
        SERVICE_ACCOUNT_FILE = resource_path("credentials.json")
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("drive", "v3", credentials=credentials)
        file_metadata = {
            "name": os.path.basename(file_path),
            "parents": [folder_id],
        }
        media = MediaFileUpload(
            file_path,
            mimetype="application/zip",
            resumable=True,
        )
        print(f"Starting upload of {file_path} to Google Drive...")
        file = (
            service.files()  # pylint: disable=no-member
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,name,webViewLink",
            )
            .execute()
        )
        permission = {"type": "anyone", "role": "reader"}
        service.permissions().create(
            fileId=file.get("id"), body=permission
        ).execute()  # pylint: disable=no-member
        print("Upload successful!")
        print(f"File Name: {file.get('name')}")
        print(f"File ID: {file.get('id')}")
        print(f"Web View Link: {file.get('webViewLink')}")
        return file.get("webViewLink")
    except FileNotFoundError as e:
        print(f"Error: File not found - {str(e)}")
        raise
    except HttpError as e:
        print(f"Error: Google Drive API error - {str(e)}")
        raise
    except Exception as e:
        print(f"Error: Unexpected error occurred - {str(e)}")
        raise


def send_email(shared_link, recipient_email):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = "Shared Google Drive Link"
    body = f"Here is the shared link to the uploaded file: {shared_link}"
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        print("Email sent successfully")
    except smtplib.SMTPException as e:
        print(f"Error: Unable to send email - {str(e)}")


def run_script():
    all_in_one = all_in_one_path.get()
    destination = destination_path.get()
    if not all_in_one or not destination:
        messagebox.showerror("Error", "Both paths must be set")
        return
    if not os.path.exists(all_in_one):
        messagebox.showerror("Error", "All in one folder path does not exist")
        return
    if not os.path.exists(destination):
        messagebox.showerror("Error", "Destination folder path does not exist")
        return
    orders = script.get_data("Order")
    unfulfilled_skus = []
    not_found = []
    for order in orders:
        if order.fulfillment_status is None:
            for line_item in order.line_items:
                if line_item.sku:
                    unfulfilled_skus.append(
                        (order.id, line_item.sku, line_item.quantity)
                    )
    for order_id, sku, quantity in unfulfilled_skus:
        if sku is None:
            continue
        if "STIC" in sku:
            filename = sku
            target_folder = os.path.join(destination, "stickers")
        elif sku.endswith("A3"):
            filename = sku[:-2]
            target_folder = os.path.join(destination, "A3")
        elif sku.endswith("A4"):
            filename = sku[:-2]
            target_folder = os.path.join(destination, "A4")
        elif sku.endswith("A5"):
            filename = sku[:-2]
            target_folder = os.path.join(destination, "A5")
        elif sku.endswith("PP"):
            filename = sku[:-2]
            target_folder = os.path.join(destination, "PP")
        else:
            continue
        os.makedirs(target_folder, exist_ok=True)
        subfolder_name = f"{quantity} copy"
        subfolder_path = os.path.join(target_folder, subfolder_name)
        os.makedirs(subfolder_path, exist_ok=True)
        # Recursively search for the file in all_in_one and subfolders
        file_found = False
        for ext in [".jpg", ".jpeg", ".png"]:
            for root_dir, _, files in os.walk(all_in_one):
                for file in files:
                    if file == f"{filename}{ext}":
                        sku_file = os.path.join(root_dir, file)
                        shutil.copy(sku_file, subfolder_path)
                        file_found = True
                        break
                if file_found:
                    break
            if file_found:
                break
        if not file_found:
            not_found.append((order_id, sku, quantity))
    with open(
        os.path.join(destination, "not_found.csv"),
        mode="w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["Order ID", "SKU", "Quantity"])
        for order_id, sku, quantity in not_found:
            writer.writerow([order_id, sku, quantity])
    remove_empty_folders(destination)
    date_str = datetime.now().strftime("%d%m%Y")
    zip_filename = f"{date_str}onlineorder.zip"
    zip_filepath = os.path.join(destination, zip_filename)
    zip_folder(destination, zip_filepath)
    try:
        folder_id = "1N0C4KXzR3RIUf1iSFPlXWNQUqsCoitnn"
        shared_link = upload_to_drive(zip_filepath, folder_id)
        recipient_email = "mayankch283@gmail.com"
        send_email(shared_link, recipient_email)
        messagebox.showinfo(
            "Success", "Process completed and file uploaded to Google Drive"
        )
    except Exception as e:
        messagebox.showerror("Error", f"Upload failed: {str(e)}")


root = tk.Tk()
root.title("Operation Automation")

all_in_one_path = tk.StringVar()
destination_path = tk.StringVar()

tk.Label(root, text="All in one folder:").grid(row=0, column=0, padx=10, pady=10)
tk.Entry(root, textvariable=all_in_one_path, width=50).grid(
    row=0, column=1, padx=10, pady=10
)
tk.Button(root, text="Browse", command=select_all_in_one_folder).grid(
    row=0, column=2, padx=10, pady=10
)

tk.Label(root, text="Destination folder:").grid(row=1, column=0, padx=10, pady=10)
tk.Entry(root, textvariable=destination_path, width=50).grid(
    row=1, column=1, padx=10, pady=10
)
tk.Button(root, text="Browse", command=select_destination_folder).grid(
    row=1, column=2, padx=10, pady=10
)

tk.Button(root, text="Run", command=run_script).grid(row=2, column=1, padx=10, pady=10)

root.mainloop()
