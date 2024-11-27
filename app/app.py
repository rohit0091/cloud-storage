import os
import stat
import subprocess
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder="templates")
app.secret_key = "your_secret_key"  # Set to a random string for security
storage_path = r"E:\My Cloud Storage"

# Load user data
user_data_file = os.path.join(storage_path, "data", "users.xlsx")

# Initialize user data file if it doesn't exist
if not os.path.exists(user_data_file):
    os.makedirs(os.path.join(storage_path, "data"), exist_ok=True)
    df = pd.DataFrame(columns=["email", "username", "password"])
    with pd.ExcelWriter(user_data_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

# Function to create a folder and grant full control to the user
def create_folder_with_full_control(email):
    user_folder = os.path.join(storage_path, "users", email)

    # Step 1: Create the folder if it doesn't exist
    if not os.path.exists(user_folder):
        try:
            os.makedirs(user_folder, exist_ok=True)
            print(f"Created folder: {user_folder}")
        except PermissionError as e:
            print(f"Permission denied while creating folder: {user_folder}")
            flash("Unable to create folder. Please check folder permissions.")
            return False

    # Step 2: Grant full control permission to the user (current user in this case)
    try:
        folder_path = os.path.abspath(user_folder)  # Get absolute path
        command = f'icacls "{folder_path}" /grant {os.getlogin()}:(F)'
        subprocess.run(command, check=True, shell=True)
        print(f"Full control granted to {os.getlogin()} for folder: {folder_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error setting permissions: {e}")
        flash("Error setting folder permissions. Please check folder access.")
        return False

    return True

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()  # Strip spaces from email
        password = request.form["password"].strip()  # Strip spaces from password

        # Print for debugging purposes
        print(f"Attempted login with email: '{email}' and password: '{password}'")

        # Read users data from the Excel file
        users = pd.read_excel(user_data_file, engine="openpyxl")

        # Convert email and password columns to string type (to avoid .str accessor issues)
        users['email'] = users['email'].astype(str).str.strip()
        users['password'] = users['password'].astype(str).str.strip()

        # Print users DataFrame to debug
        print(f"Loaded users data: \n{users}")

        # Check if email and password match
        matching_user = users[(users["email"] == email) & (users["password"] == password)]

        if not matching_user.empty:
            # Successful login
            session["user"] = email
            print(f"User {email} logged in successfully.")  # Debugging log
            return redirect(url_for("dashboard"))  # Redirect to dashboard
        else:
            # Failed login
            flash("Invalid login credentials")  # Inform the user if login fails
            print("Invalid credentials.")  # Debugging log

    return render_template("login.html")  # Render login page



@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate the form inputs
        if not email or not username or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        # Load existing user data
        users = pd.read_excel(user_data_file, engine="openpyxl")

        # Check if email already exists
        if email not in users["email"].values:
            # Create a new user entry
            new_user = {"email": email, "username": username, "password": password}
            users = pd.concat([users, pd.DataFrame([new_user])], ignore_index=True)

            # Save updated data back to the Excel file
            users.to_excel(user_data_file, index=False, engine="openpyxl")

            # Create the user folder and set permissions
            if create_folder_with_full_control(email):
                flash("Registration successful. Please log in.")
                return redirect(url_for("login"))
            else:
                flash("Unable to create user folder with proper permissions.")
                return redirect(url_for("register"))
        else:
            flash("Email already exists. Please use a different email.")
    
    return render_template("register.html")  # Render the registration page

import pandas as pd
from pathlib import Path

@app.route('/dashboard', methods=["GET", "POST"])
def dashboard():
    if "user" not in session:  # Ensure the user is logged in
        print("User not logged in!")  # Debugging log
        return redirect(url_for("login"))

    # Read username from Excel file
    excel_path = Path("E:/My Cloud Storage/data/users.xlsx")
    df = pd.read_excel(excel_path)
    
    # Find username for the logged-in user's email
    user_row = df[df['email'] == session["user"]]
    username = user_row['username'].iloc[0] if not user_row.empty else session["user"]

    # Define the user folder path for the logged-in user
    user_folder = os.path.join(storage_path, "users", session["user"])

    # Handle file and folder operations
    if request.method == "POST":
        if "file" in request.files:  # Upload a file
            file = request.files["file"]
            if file.filename:  # Save the uploaded file
                file_path = os.path.join(user_folder, secure_filename(file.filename))
                file.save(file_path)
        elif "new_folder" in request.form:  # Create a folder
            folder_name = request.form["new_folder"]
            os.makedirs(os.path.join(user_folder, folder_name), exist_ok=True)
        elif "new_file" in request.form:  # Create an empty file
            file_name = request.form["new_file"]
            open(os.path.join(user_folder, file_name), 'w').close()

    # Get a list of files and folders for the current user
    items = os.listdir(user_folder)
    return render_template("dashboard.html", items=items, username=username)


@app.route('/download/<filename>')
def download(filename):
    if "user" not in session:  # Ensure the user is logged in
        return redirect(url_for("login"))

    user_folder = os.path.join(storage_path, "users", session["user"])
    file_path = os.path.join(user_folder, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash("File not found.")
        return redirect(url_for("dashboard"))

@app.route('/delete/<item>', methods=["POST"])
def delete_item(item):
    if "user" not in session:  # Ensure the user is logged in
        return redirect(url_for("login"))

    user_folder = os.path.join(storage_path, "users", session["user"])
    item_path = os.path.join(user_folder, item)

    if os.path.exists(item_path):
        try:
            # If it's a file, delete the file
            if os.path.isfile(item_path):
                os.remove(item_path)
                flash(f"File '{item}' deleted successfully.")
            # If it's a folder, delete the folder and its contents
            elif os.path.isdir(item_path):
                os.rmdir(item_path)  # You can use shutil.rmtree() to remove non-empty folders
                flash(f"Folder '{item}' deleted successfully.")
            return redirect(url_for("dashboard"))
        except PermissionError:
            flash(f"Permission denied while deleting '{item}'.")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"An error occurred while deleting '{item}': {str(e)}")
            return redirect(url_for("dashboard"))
    else:
        flash(f"'{item}' does not exist.")
        return redirect(url_for("dashboard"))

@app.route('/logout')
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
