from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mail import Mail, Message
import bcrypt
import random
import config
import sqlite3
import os
from werkzeug.utils import secure_filename
import razorpay
import traceback
from flask import make_response, render_template
from datetime import datetime, timedelta
from utils.pdf_generator import generate_pdf
import secrets 



razorpay_client = razorpay.Client(
    auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)
)
app = Flask(__name__)
app.secret_key = config.SECRET_KEY


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config['ADMIN_UPLOAD_FOLDER'] = os.path.join(
    BASE_DIR, 'static', 'uploads', 'admin_profiles'
)

# Create folder if not exists
os.makedirs(app.config['ADMIN_UPLOAD_FOLDER'], exist_ok=True)

# ---------------- EMAIL CONFIGURATION ----------------
app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD

mail = Mail(app)

# -------------------- DB CONNECTION --------------------
def get_db_connection():
    conn = sqlite3.connect("smartcart.db")
    conn.row_factory = sqlite3.Row
    return conn

#--------------------Home---------------------------
@app.route('/')
def Home():
    return render_template("home.html",navbar_type ="public")
#------------------About-----------------------------
@app.route('/about')
def About():
    return render_template("about.html",navbar_type ="public")
#------------------------Contact-----------------------
@app.route('/contact')
def Contact():
    return render_template("contact.html",navbar_type ="public")
#------------------Base---------------------------------
@app.route('/base')
def Base():
    return render_template("base.html",navbar_type ="public")

# ---------------------------------------------------------
# ROUTE 1: ADMIN SIGNUP (SEND OTP)
# ---------------------------------------------------------
@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():

    # Show form
    if request.method == "GET":
        return render_template("admin/admin_signup.html" ,navbar_type ="public")

    # POST → Process signup
    name = request.form['name']
    email = request.form['email']

    # 1️⃣ Check if admin email already exists
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT admin_id FROM admin WHERE email=?", (email,))
    existing_admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if existing_admin:
        flash("This email is already registered. Please login instead.", "danger")
        return redirect('/admin-signup')

    # 2️⃣ Save user input temporarily in session
    session['signup_name'] = name
    session['signup_email'] = email

    # 3️⃣ Generate OTP and store in session
    otp = random.randint(100000, 999999)
    session['otp'] = otp

    # 4️⃣ Send OTP Email
    message = Message(
        subject="SmartCart Admin OTP",
        sender=config.MAIL_USERNAME,
        recipients=[email]
    )
    message.body = f"Your OTP for SmartCart Admin Registration is: {otp}"
    mail.send(message)

    flash("OTP sent to your email!", "success")
    return redirect('/verify-otp')

# ---------------------------------------------------------
# ROUTE 2: DISPLAY OTP PAGE
# ---------------------------------------------------------
@app.route('/verify-otp', methods=['GET'])
def verify_otp_get():
    return render_template("admin/verify_otp.html",navbar_type ="public")

# ---------------------------------------------------------
# ROUTE 3: VERIFY OTP + SAVE ADMIN
# ---------------------------------------------------------
@app.route('/verify-otp', methods=['POST'])
def verify_otp_post():
    
    # User submitted OTP + Password
    user_otp = request.form['otp']
    password = request.form['password']

    # Compare OTP
    if str(session.get('otp')) != str(user_otp):
        flash("Invalid OTP. Try again!", "danger")
        return redirect('/verify-otp')

    # Hash password using bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Insert admin into database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin (name, email, password) VALUES (?, ?, ?)",
        (session['signup_name'], session['signup_email'], hashed_password)
    )
    conn.commit()
    cursor.close()
    conn.close()

    # Clear temporary session data
    session.pop('otp', None)
    session.pop('signup_name', None)
    session.pop('signup_email', None)

    flash("Admin Registered Successfully!", "success")
    return redirect('/admin-login')

# =================================================================
# ROUTE 4: ADMIN LOGIN PAGE (GET + POST)
# =================================================================
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():

    # Show login page
    if request.method == 'GET':
        return render_template("admin/admin_login.html",navbar_type ="public")

    # POST → Validate login
    email = request.form['email']
    password = request.form['password']

    # Step 1: Check if admin email exists
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admin WHERE email=?", (email,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if admin is None:
        flash("Email not found! Please register first.", "danger")
        return redirect('/admin-login')

    # Step 2: Compare entered password with hashed password
    stored_hashed_password = admin['password'].encode('utf-8')

    if not bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
        flash("Incorrect password! Try again.", "danger")
        return redirect('/admin-login')

    # Step 5: If login success → Create admin session
    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_email'] = admin['email']

    flash("Login Successful!", "success")
    return redirect('/admin-dashboard')

# =================================================================
# ROUTE 5: ADMIN DASHBOARD (PROTECTED ROUTE)
# =================================================================
@app.route('/admin-dashboard')
def admin_dashboard():

    # Admin login check
    if 'admin_id' not in session:
        flash("Please login to access dashboard!", "danger")
        return redirect('/admin-login')

    try:
        conn = sqlite3.connector.connect(
            host="localhost",
            user="root",
            password="9381540490",   # <-- nee MySQL password pettu
            database="smartcart_db"   # <-- nee original DB name pettu
        )

        cursor = conn.cursor(dictionary=True)

        # Get all products
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()

        # Get categories for dropdown
        cursor.execute("SELECT DISTINCT category FROM products")
        categories = cursor.fetchall()

        cursor.close()
        conn.close()

    except Exception as e:
        print("DB Error:", e)
        products = []
        categories = []

    return render_template(
        "admin/dashboard.html",
        admin_name=session['admin_name'],
        products=products,
        categories=categories,
        navbar_type="admin"
    )


# =================================================================
# ROUTE 6: ADMIN LOGOUT
# =================================================================
@app.route('/admin-logout')
def admin_logout():

    # Clear admin session
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_email', None)

    flash("Logged out successfully.", "success")
    return redirect('/admin-login')

# ------------------- IMAGE UPLOAD PATH -------------------
UPLOAD_FOLDER = 'static/uploads/product_images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# =================================================================
# ROUTE 7: SHOW ADD PRODUCT PAGE (Protected Route)
# =================================================================
@app.route('/admin/add-item', methods=['GET'])
def add_item_page():

    # Only logged-in admin can access
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    return render_template("admin/add_item.html",navbar_type="admin")

# =================================================================
# ROUTE 8: ADD PRODUCT INTO DATABASE
# =================================================================
@app.route('/admin/add-item', methods=['POST'])
def add_item():

    # Check admin session
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    # 1️⃣ Get form data
    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']
    image_file = request.files['image']

    # 2️⃣ Validate image upload
    if image_file.filename == "":
        flash("Please upload a product image!", "danger")
        return redirect('/admin/add-item')

    # 3️⃣ Secure the file name
    filename = secure_filename(image_file.filename)

    # 4️⃣ Create full path
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # 5️⃣ Save image into folder
    image_file.save(image_path)

    # 6️⃣ Insert product into database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO products (name, description, category, price, image) VALUES (?, ?, ?, ?, ?)",
        (name, description, category, price, filename)
    )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Product added successfully!", "success")
    return redirect('/admin/add-item')

# =================================================================
# ROUTE 9: UPDATED PRODUCT LIST WITH SEARCH + CATEGORY FILTER
# =================================================================
@app.route('/admin/item-list')
def item_list():

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ Fetch category list for dropdown
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    # 2️⃣ Build dynamic query based on filters
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append("%" + search + "%")

    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/item_list.html",
        products=products,
        categories=categories, navbar_type="admin"
    )

#=================================================================
# ROUTE 10: VIEW SINGLE PRODUCT DETAILS
# =================================================================
@app.route('/admin/view-item/<int:item_id>')
def view_item(item_id):

    # Check admin session
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = ?", (item_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/view_item.html", product=product,navbar_type="admin")

# =================================================================
# ROUTE 11: SHOW UPDATE FORM WITH EXISTING DATA
# =================================================================
@app.route('/admin/update-item/<int:item_id>', methods=['GET'])
def update_item_page(item_id):

    # Check login
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    # Fetch product data
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = ?", (item_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/update_item.html", product=product)

# =================================================================
# ROUTE 12: UPDATE PRODUCT + OPTIONAL IMAGE REPLACE
# =================================================================
@app.route('/admin/update-item/<int:item_id>', methods=['POST'])
def update_item(item_id):

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    # 1️⃣ Get updated form data
    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']

    new_image = request.files['image']

    # 2️⃣ Fetch old product data
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id = ?", (item_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    old_image_name = product['image']

    # 3️⃣ If admin uploaded a new image → replace it
    if new_image and new_image.filename != "":
        
        # Secure filename
        from werkzeug.utils import secure_filename
        new_filename = secure_filename(new_image.filename)

        # Save new image
        new_image_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        new_image.save(new_image_path)

        # Delete old image file
        old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], old_image_name)
        if os.path.exists(old_image_path):
            os.remove(old_image_path)

        final_image_name = new_filename

    else:
        # No new image uploaded → keep old one
        final_image_name = old_image_name

    # 4️⃣ Update product in the database
    cursor.execute("""
        UPDATE products
        SET name=?, description=?, category=?, price=?, image=?
        WHERE product_id=?
    """, (name, description, category, price, final_image_name, item_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Product updated successfully!", "success")
    return redirect('/admin/item-list')

# =================================================================
# ROUTE13: DELETE PRODUCT (DELETE DB ROW + DELETE IMAGE FILE)
# =================================================================
@app.route('/admin/delete-item/<int:item_id>')
def delete_item(item_id):

    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ Fetch product to get image name
    cursor.execute("SELECT image FROM products WHERE product_id=?", (item_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    image_name = product['image']

    # Delete image from folder
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_name)
    if os.path.exists(image_path):
        os.remove(image_path)

    # 2️⃣ Delete product from DB
    cursor.execute("DELETE FROM products WHERE product_id=?", (item_id,))
    conn.commit()
    cursor.execute(
    "UPDATE products SET is_active=FALSE WHERE product_id=?",
    (item_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Product deleted successfully!", "success")
    return redirect('/admin/item-list')

# =================================================================
# ROUTE 14: SHOW ADMIN PROFILE DATA
# =================================================================
@app.route('/admin/profile', methods=['GET'])
def admin_profile():

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admin WHERE admin_id = ?", (admin_id,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/admin_profile.html", admin=admin, navbar_type="admin")

# =================================================================
# ROUTE 15: UPDATE ADMIN PROFILE (NAME, EMAIL, PASSWORD, IMAGE)
# =================================================================
@app.route('/admin/profile', methods=['GET', 'POST'])
def admin_profile_update():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # IMPORTANT

    admin_id = session.get('admin_id')

    cursor.execute("SELECT * FROM admin WHERE admin_id = ?", (admin_id,))
    admin = cursor.fetchone()

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        image = request.files['profile_image']

        old_image_name = admin['profile_image']

        # Image upload
        if image and image.filename != "":
            image_name = image.filename
            image.save(os.path.join('static/uploads/admin_profiles', image_name))
        else:
            image_name = old_image_name

        # Password update only if entered
        if password:
            cursor.execute("""
                UPDATE admin
                SET name=?, email=?, password=?, profile_image=?
                WHERE admin_id=?
            """, (name, email, password, image_name, admin_id))
        else:
            cursor.execute("""
                UPDATE admin
                SET name=?, email=?, profile_image=?
                WHERE admin_id=?
            """, (name, email, image_name, admin_id))

        conn.commit()

        flash("Profile Updated Successfully!", "success")
        return redirect('/admin/profile')

    return render_template('admin/admin_profile.html', admin=admin)

# ---------------Admin Forget password---------------
@app.route('/admin-forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():

    if request.method == 'POST':
        email = request.form['email']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM admin WHERE email=?", (email,))
        admin = cursor.fetchone()

        if not admin:
            flash("Please enter valid registered email!", "danger")
            return redirect('/admin-forgot-password')

        token = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(minutes=15)

        cursor.execute(
            "UPDATE admin SET reset_token=?, token_expiry=? WHERE email=?",
            (token, expiry, email)
        )
        conn.commit()

        reset_link = url_for('admin_reset_password', token=token, _external=True)

        msg = Message(
            subject="Reset Your Admin Password",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = f"Click the link to reset password:\n{reset_link}"
        mail.send(msg)

        flash("Reset link sent to your email!", "success")
        return redirect('/admin-login')

    return render_template('admin/forgot_password.html', navbar_type="public")

# ------------Admin reset password------------
@app.route('/admin-reset-password/<token>', methods=['GET', 'POST'])
def admin_reset_password(token):

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1️⃣ Find admin by token
    cursor.execute(
        "SELECT * FROM admin WHERE reset_token=?",
        (token,)
    )
    admin = cursor.fetchone()

    # 2️⃣ Invalid or expired token
    if not admin or admin['token_expiry'] < datetime.utcnow():
        flash("Invalid or expired reset link!", "danger")
        return redirect('/admin-login')

    # 3️⃣ If form submitted → update password
    if request.method == 'POST':
        new_password = request.form['password']

        hashed_password = bcrypt.hashpw(
            new_password.encode('utf-8'),
            bcrypt.gensalt()
        )

        cursor.execute(
            """
            UPDATE admin
            SET password=?, reset_token=NULL, token_expiry=NULL
            WHERE admin_id=?
            """,
            (hashed_password, admin['admin_id'])
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash("Password updated successfully. Please login!", "success")
        return redirect('/admin-login')

    return render_template(
        "admin/reset_password.html",
        navbar_type="public"
    )

# ROUTE: USER REGISTRATION
# =================================================================
@app.route('/user-register', methods=['GET', 'POST'])
def user_register():

    if request.method == 'GET':
        return render_template("user/user_register.html",navbar_type ="public")

    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    # Check if user already exists
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        flash("Email already registered! Please login.", "danger")
        return redirect('/user-register')

    # Hash password
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Insert new user
    cursor.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        (name, email, hashed_password)
    )
    conn.commit()

    cursor.close()
    conn.close()

    flash("Registration successful! Please login.", "success")
    return redirect('/user-login')

# =================================================================
# ROUTE: USER LOGIN
# =================================================================
@app.route('/user-login', methods=['GET', 'POST'])
def user_login():

    if request.method == 'GET':
        return render_template("user/user_login.html",navbar_type ="public")

    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        flash("Email not found! Please register.", "danger")
        return redirect('/user-login')

    # Verify password
    if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        flash("Incorrect password!", "danger")
        return redirect('/user-login')

    # Create user session
    session['user_id'] = user['user_id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']

    flash("Login successful!", "success")
    return redirect('/user-dashboard')

# =================================================================
# ROUTE: USER DASHBOARD
# =================================================================
@app.route('/user-dashboard')
def user_dashboard():

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Categories
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    # Products
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append("%" + search + "%")

    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "user/user_home.html",
        user_name=session['user_name'],
        products=products,
        categories=categories,
        navbar_type="user"
    )

# =================================================================
# ROUTE: USER LOGOUT
# =================================================================
@app.route('/user-logout')
def user_logout():
    
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)

    flash("Logged out successfully!", "success")
    return redirect('/user-login')

# =================================================================
# ROUTE: USER PRODUCT LISTING (SEARCH + FILTER)
# =================================================================
@app.route('/user/products')
def user_products():

    # Optional: restrict only logged-in users
    if 'user_id' not in session:
        flash("Please login to view products!", "danger")
        return redirect('/user-login')

    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch categories for filter dropdown
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    # Build dynamic SQL
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append("%" + search + "%")

    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "user/user_products.html",
        products=products,
        categories=categories,
        navbar_type="user"
    )

# =================================================================
# ROUTE: USER PRODUCT DETAILS PAGE
# =================================================================
@app.route('/user/product/<int:product_id>')
def user_product_details(product_id):

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/user/products')

    return render_template("user/product_details.html", product=product,navbar_type="user")

# =================================================================
# ADD ITEM TO CART
# =================================================================
@app.route('/user/add-to-cart/<int:product_id>')
def add_to_cart(product_id):

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    # Create cart if doesn't exist
    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    # Get product
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id=?", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    if not product:
        flash("Product not found.", "danger")
        return redirect(request.referrer)

    pid = str(product_id)

    # If exists → increase quantity
    if pid in cart:
        cart[pid]['quantity'] += 1
    else:
        cart[pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1
        }

    session['cart'] = cart

    flash("Item added to cart!", "success")
    return redirect(request.referrer)   # ⭐ Return to same page

# =================================================================
# VIEW CART PAGE
# =================================================================
@app.route('/user/cart')
def view_cart():

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    cart = session.get('cart', {})

    # Calculate total
    grand_total = sum(item['price'] * item['quantity'] for item in cart.values())

    return render_template("user/cart.html", cart=cart, grand_total=grand_total)
#---------------inject cart----------
@app.context_processor
def inject_cart_count():

    cart = session.get('cart', {})

    total_items = 0
    for item in cart.values():
        total_items += item.get('quantity', 0)

    return dict(cart_count=total_items)
# =================================================================
# INCREASE QUANTITY
# =================================================================
@app.route('/user/cart/increase/<pid>')
def increase_quantity(pid):

    cart = session.get('cart', {})

    if pid in cart:
        cart[pid]['quantity'] += 1

    session['cart'] = cart
    return redirect('/user/cart')

# =================================================================
# DECREASE QUANTITY
# =================================================================
@app.route('/user/cart/decrease/<pid>')
def decrease_quantity(pid):

    cart = session.get('cart', {})

    if pid in cart:
        cart[pid]['quantity'] -= 1

        # If quantity becomes 0 → remove item
        if cart[pid]['quantity'] <= 0:
            cart.pop(pid)

    session['cart'] = cart
    return redirect('/user/cart')

# =================================================================
# REMOVE ITEM
# =================================================================
@app.route('/user/cart/remove/<pid>')
def remove_from_cart(pid):

    cart = session.get('cart', {})

    if pid in cart:
        cart.pop(pid)

    session['cart'] = cart

    flash("Item removed!", "success")
    return redirect('/user/cart')

# =================================================================
# ROUTE: CREATE RAZORPAY ORDER
# =================================================================
@app.route('/user/pay')
def user_pay():

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    cart = session.get('cart', {})

    if not cart:
        flash("Your cart is empty!", "danger")
        return redirect('/user/products')

    # Calculate total amount
    total_amount = sum(item['price'] * item['quantity'] for item in cart.values())
    razorpay_amount = int(total_amount * 100)  # convert to paise

    # Create Razorpay order
    razorpay_order = razorpay_client.order.create({
        "amount": razorpay_amount,
        "currency": "INR",
        "payment_capture": "1"
    })

    session['razorpay_order_id'] = razorpay_order['id']

    return render_template(
        "user/payment.html",
        amount=total_amount,
        key_id=config.RAZORPAY_KEY_ID,
        order_id=razorpay_order['id']
    )

# =================================================================
# TEMP SUCCESS PAGE (Verification in Day 13)
# =================================================================
@app.route('/payment-success')
def payment_success():

    payment_id = request.args.get('payment_id')
    order_id = request.args.get('order_id')

    if not payment_id:
        flash("Payment failed!", "danger")
        return redirect('/user/cart')

    return render_template(
        "user/payment_success.html",
        payment_id=payment_id,
        order_id=order_id
    )

#------------order success-------------------------
@app.route('/user/order-success/<int:order_db_id>')
def order_success(order_db_id):
    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=? AND user_id=?", (order_db_id, session['user_id']))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=?", (order_db_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/user/products')

    return render_template("user/order_success.html", order=order, items=items)

# ------------------------------
# Route: Verify Payment and Store Order
# ------------------------------
@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    if 'user_id' not in session:
        flash("Please login to complete the payment.", "danger")
        return redirect('/user-login')

    # Read values posted from frontend
    razorpay_payment_id = request.form.get('razorpay_payment_id')
    razorpay_order_id = request.form.get('razorpay_order_id')
    razorpay_signature = request.form.get('razorpay_signature')

    if not (razorpay_payment_id and razorpay_order_id and razorpay_signature):
        flash("Payment verification failed (missing data).", "danger")
        return redirect('/user/cart')

    # Build verification payload required by Razorpay client.utility
    payload = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        # This will raise an error if signature invalid
        razorpay_client.utility.verify_payment_signature(payload)

    except Exception as e:
        # Verification failed
        app.logger.error("Razorpay signature verification failed: ?", str(e))
        flash("Payment verification failed. Please contact support.", "danger")
        return redirect('/user/cart')

    # Signature verified — now store order and items into DB
    user_id = session['user_id']
    cart = session.get('cart', {})

    if not cart:
        flash("Cart is empty. Cannot create order.", "danger")
        return redirect('/user/products')

    # Calculate total amount (ensure same as earlier)
    total_amount = sum(item['price'] * item['quantity'] for item in cart.values())

    # DB insert: orders and order_items
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Insert into orders table
        cursor.execute("""
            INSERT INTO orders (user_id, razorpay_order_id, razorpay_payment_id, amount, payment_status)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, razorpay_order_id, razorpay_payment_id, total_amount, 'paid'))

        order_db_id = cursor.lastrowid  # newly created order's primary key

        # Insert all items
        for pid_str, item in cart.items():
            product_id = int(pid_str)
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?, ?)
            """, (order_db_id, product_id, item['name'], item['quantity'], item['price']))

        # Commit transaction
        conn.commit()

        # Clear cart and temporary razorpay order id
        session.pop('cart', None)
        session.pop('razorpay_order_id', None)

        flash("Payment successful and order placed!", "success")
        return redirect(f"/user/order-success/{order_db_id}")

    except Exception as e:
        # Rollback and log error
        conn.rollback()
        app.logger.error("Order storage failed: ?\n?", str(e), traceback.format_exc())
        flash("There was an error saving your order. Contact support.", "danger")
        return redirect('/user/cart')

    finally:
        cursor.close()
        conn.close()

# ----------------------------
# GENERATE INVOICE PDF
# ----------------------------
@app.route("/user/download-invoice/<int:order_id>")
def download_invoice(order_id):

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    # Fetch order
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=? AND user_id=?",
                   (order_id, session['user_id']))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/user/my-orders')

    # Render invoice HTML
    html = render_template("user/invoice.html", order=order, items=items)

    pdf = generate_pdf(html)
    if not pdf:
        flash("Error generating PDF", "danger")
        return redirect('/user/my-orders')

    # Prepare response
    response = make_response(pdf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f"attachment; filename=invoice_{order_id}.pdf"

    return response

#-------------address route------------------------
@app.route("/user/address", methods=["GET", "POST"])
def address():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        cursor.execute("""
            INSERT INTO addresses
            (user_id, full_name, phone, address_line, city, state, pincode)
            VALUES (?, ?, ?, ?,?, ?, ?)
        """, (
            session["user_id"],
            request.form["full_name"],
            request.form["phone"],
            request.form["address"],
            request.form["city"],
            request.form["state"],
            request.form["pincode"]
        ))

        conn.commit()
        conn.close()

        return redirect("/user/pay")

    return render_template("/user/address.html")

#----------------my orders-------------------
@app.route('/user/my-orders')
def my_orders():

    if 'user_id' not in session:
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)   # ✅ IMPORTANT

    cursor.execute("""
        SELECT order_id, amount, payment_status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session['user_id'],))

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("user/my_orders.html",
        orders=orders)

# ------------------------ RUN SERVER -----------------------
if __name__ == "__main__":
    app.run(debug=True)