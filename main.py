import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
import csv
import script
import zipfile
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def select_all_in_one_folder():
    folder_selected = filedialog.askdirectory()
    all_in_one_path.set(folder_selected)

def select_destination_folder():
    folder_selected = filedialog.askdirectory()
    destination_path.set(folder_selected)

def zip_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file),
                           os.path.relpath(os.path.join(root, file),
                                           os.path.join(folder_path, '..')))

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

    # Run the script to get SKUs of unfulfilled orders
    orders = script.get_data('Order')
    unfulfilled_skus = []
    not_found = []
    for order in orders:
        if order.fulfillment_status is None:
            for line_item in order.line_items:
                if line_item.sku:  # Ensure SKU is not None
                    unfulfilled_skus.append((order.id, line_item.sku, line_item.quantity))

    for order_id, sku, quantity in unfulfilled_skus:
        # Determine file category and find the source image
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
            continue  # Skip non-poster and non-sticker SKUs

        # Ensure the target folder exists
        os.makedirs(target_folder, exist_ok=True)

        # Copy the file to the target folder based on quantity
        sku_file = os.path.join(all_in_one, f"{filename}.jpg")
        if os.path.exists(sku_file):
            for i in range(quantity):
                shutil.copy(sku_file, os.path.join(target_folder, f"{filename}_{i+1} copy.jpg"))
        else:
            not_found.append((order_id, sku, quantity))

    # Record not found SKUs in a .csv file
    with open(os.path.join(destination, 'not_found.csv'), mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Order ID", "SKU", "Quantity"])
        for order_id, sku, quantity in not_found:
            writer.writerow([order_id, sku, quantity])

    # Zip the destination folder
    date_str = datetime.now().strftime("%d%m%Y")
    zip_filename = f"{date_str}onlineorder.zip"
    zip_filepath = os.path.join(destination, zip_filename)
    zip_folder(destination, zip_filepath)

    messagebox.showinfo("Success", "Process completed")

root = tk.Tk()
root.title("Operation Automation")

all_in_one_path = tk.StringVar()
destination_path = tk.StringVar()

tk.Label(root, text="All in one folder:").grid(row=0, column=0, padx=10, pady=10)
tk.Entry(root, textvariable=all_in_one_path, width=50).grid(row=0, column=1, padx=10, pady=10)
tk.Button(root, text="Browse", command=select_all_in_one_folder).grid(row=0, column=2, padx=10, pady=10)

tk.Label(root, text="Destination folder:").grid(row=1, column=0, padx=10, pady=10)
tk.Entry(root, textvariable=destination_path, width=50).grid(row=1, column=1, padx=10, pady=10)
tk.Button(root, text="Browse", command=select_destination_folder).grid(row=1, column=2, padx=10, pady=10)

tk.Button(root, text="Run", command=run_script).grid(row=2, column=1, padx=10, pady=10)

root.mainloop()