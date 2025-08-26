import sys
import os
import subprocess
import sqlite3
from datetime import datetime, timedelta
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, 
                             QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                             QMessageBox, QFileDialog, QGroupBox, QFormLayout, QDateEdit,
                             QCheckBox, QTextEdit, QHeaderView)
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, 
                             QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                             QMessageBox, QFileDialog, QGroupBox, QFormLayout, QDateEdit,
                             QCheckBox, QTextEdit, QHeaderView, QRadioButton, QDialog, QInputDialog)
import cv2
from pyzbar.pyzbar import decode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib import colors
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
# from twilio.rest import Client
import barcode
from barcode.writer import ImageWriter
import pandas as pd
from PIL import Image, ImageQt
import requests
from twilio.rest import Client
import threading
import time


class PharmacyDatabase:
    def __init__(self, db_file='pharmacy.db'):
        self.db_file = db_file
        self._initialize_database()
        
    def _initialize_database(self):
        if not os.path.exists(self.db_file):
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
            # Medicines table
            c.execute('''CREATE TABLE medicines
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT NOT NULL,
                         barcode TEXT UNIQUE,
                         batch_number TEXT,
                         price REAL NOT NULL,
                         mrp REAL NOT NULL,
                         quantity INTEGER NOT NULL,
                         expiry_date TEXT,
                         manufacturer TEXT,
                         category TEXT,
                         min_stock_level INTEGER DEFAULT 5)''')
            
            # Customers table
            c.execute('''CREATE TABLE customers
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT NOT NULL,
                         phone TEXT,
                         email TEXT,
                         address TEXT,
                         created_date TEXT)''')
            
            # Sales table
            c.execute('''CREATE TABLE sales
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         invoice_number TEXT UNIQUE,
                         customer_id INTEGER,
                         date TEXT NOT NULL,
                         total_amount REAL NOT NULL,
                         discount REAL DEFAULT 0,
                         tax REAL DEFAULT 0,
                         payment_method TEXT,
                         FOREIGN KEY(customer_id) REFERENCES customers(id))''')
            
            # Sale items table
            c.execute('''CREATE TABLE sale_items
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         sale_id INTEGER NOT NULL,
                         medicine_id INTEGER NOT NULL,
                         quantity INTEGER NOT NULL,
                         price REAL NOT NULL,
                         FOREIGN KEY(sale_id) REFERENCES sales(id),
                         FOREIGN KEY(medicine_id) REFERENCES medicines(id))''')
            
            # Users table
            c.execute('''CREATE TABLE users
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         username TEXT UNIQUE NOT NULL,
                         password TEXT NOT NULL,
                         role TEXT NOT NULL,
                         full_name TEXT)''')
            
            # Add admin user
            c.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                      ('admin', 'admin123', 'admin', 'Administrator'))
            
            conn.commit()
            conn.close()
    
    def _get_connection(self):
        return sqlite3.connect(self.db_file)
    
    # Medicine methods
    def add_medicine(self, medicine_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO medicines 
                         (name, barcode, batch_number, price, mrp, quantity, 
                          expiry_date, manufacturer, category, min_stock_level)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (medicine_data['name'], medicine_data['barcode'], 
                       medicine_data['batch_number'], medicine_data['price'],
                       medicine_data['mrp'], medicine_data['quantity'],
                       medicine_data['expiry_date'], medicine_data['manufacturer'],
                       medicine_data['category'], medicine_data['min_stock_level']))
            conn.commit()
            return c.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def update_medicine(self, medicine_id, medicine_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute('''UPDATE medicines SET 
                         name=?, barcode=?, batch_number=?, price=?, mrp=?,
                         quantity=?, expiry_date=?, manufacturer=?, category=?,
                         min_stock_level=?
                         WHERE id=?''',
                      (medicine_data['name'], medicine_data['barcode'], 
                       medicine_data['batch_number'], medicine_data['price'],
                       medicine_data['mrp'], medicine_data['quantity'],
                       medicine_data['expiry_date'], medicine_data['manufacturer'],
                       medicine_data['category'], medicine_data['min_stock_level'],
                       medicine_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def get_medicine_by_barcode(self, barcode):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM medicines WHERE barcode=?", (barcode,))
            return c.fetchone()
        finally:
            conn.close()
    
    def get_all_medicines(self):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM medicines ORDER BY name")
            return c.fetchall()
        finally:
            conn.close()
    
    def get_low_stock_medicines(self, threshold=None):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            if threshold:
                c.execute('''SELECT * FROM medicines 
                             WHERE quantity <= min_stock_level OR quantity <= ?
                             ORDER BY quantity ASC''', (threshold,))
            else:
                c.execute('''SELECT * FROM medicines 
                             WHERE quantity <= min_stock_level
                             ORDER BY quantity ASC''')
            return c.fetchall()
        finally:
            conn.close()
    
    def get_expired_medicines(self):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            c.execute("SELECT * FROM medicines WHERE expiry_date < ? ORDER BY expiry_date", (today,))
            return c.fetchall()
        finally:
            conn.close()
    
    def update_medicine_stock(self, medicine_id, quantity_change):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("UPDATE medicines SET quantity = quantity + ? WHERE id=?", 
                     (quantity_change, medicine_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    # Customer methods
    def add_customer(self, customer_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            created_date = datetime.now().strftime('%Y-%m-%d')
            c.execute('''INSERT INTO customers 
                         (name, phone, email, address, created_date)
                         VALUES (?, ?, ?, ?, ?)''',
                      (customer_data['name'], customer_data['phone'],
                       customer_data['email'], customer_data['address'],
                       created_date))
            conn.commit()
            return c.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def update_customer(self, customer_id, customer_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute('''UPDATE customers SET 
                         name=?, phone=?, email=?, address=?
                         WHERE id=?''',
                      (customer_data['name'], customer_data['phone'],
                       customer_data['email'], customer_data['address'],
                       customer_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def get_customer_by_phone(self, phone):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM customers WHERE phone=?", (phone,))
            return c.fetchone()
        finally:
            conn.close()
    
    def get_customer_by_id(self, customer_id):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM customers WHERE id=?", (customer_id,))
            return c.fetchone()
        finally:
            conn.close()
    
    def get_all_customers(self):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM customers ORDER BY name")
            return c.fetchall()
        finally:
            conn.close()
    
    # Sales methods
    def create_sale(self, sale_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            # Create sale record
            c.execute('''INSERT INTO sales 
                         (invoice_number, customer_id, date, total_amount, 
                          discount, tax, payment_method)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (sale_data['invoice_number'], sale_data['customer_id'],
                       sale_data['date'], sale_data['total_amount'],
                       sale_data['discount'], sale_data['tax'],
                       sale_data['payment_method']))
            sale_id = c.lastrowid
            
            # Add sale items
            for item in sale_data['items']:
                c.execute('''INSERT INTO sale_items 
                             (sale_id, medicine_id, quantity, price)
                             VALUES (?, ?, ?, ?)''',
                          (sale_id, item['medicine_id'], 
                           item['quantity'], item['price']))
                # Update stock
                c.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?",
                         (item['quantity'], item['medicine_id']))
            
            conn.commit()
            return sale_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def get_sales_report(self, start_date=None, end_date=None):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            if start_date and end_date:
                c.execute('''SELECT s.id, s.invoice_number, s.date, 
                                    c.name as customer_name, 
                                    s.total_amount, s.payment_method
                             FROM sales s
                             LEFT JOIN customers c ON s.customer_id = c.id
                             WHERE s.date BETWEEN ? AND ?
                             ORDER BY s.date DESC''', (start_date, end_date))
            else:
                c.execute('''SELECT s.id, s.invoice_number, s.date, 
                                    c.name as customer_name, 
                                    s.total_amount, s.payment_method
                             FROM sales s
                             LEFT JOIN customers c ON s.customer_id = c.id
                             ORDER BY s.date DESC''')
            return c.fetchall()
        finally:
            conn.close()
    
    def get_sale_details(self, sale_id):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            # Get sale header
            c.execute('''SELECT s.*, c.name as customer_name, c.phone, c.email
                         FROM sales s
                         LEFT JOIN customers c ON s.customer_id = c.id
                         WHERE s.id=?''', (sale_id,))
            sale_header = c.fetchone()
            
            if not sale_header:
                return None
            
            # Get sale items
            c.execute('''SELECT si.*, m.name as medicine_name, m.barcode
                         FROM sale_items si
                         JOIN medicines m ON si.medicine_id = m.id
                         WHERE si.sale_id=?''', (sale_id,))
            sale_items = c.fetchall()
            
            return {
                'header': sale_header,
                'items': sale_items
            }
        finally:
            conn.close()
    
    # User authentication
    def authenticate_user(self, username, password):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM users WHERE username=? AND password=?", 
                     (username, password))
            return c.fetchone()
        finally:
            conn.close()

class BarcodeScanner:
    def __init__(self):
        self.capture = None
        self.scanning = False
        self.barcode_data = None
        
    def start_scan(self):
        """Start scanning for barcode input from physical scanner (keyboard input)"""
        self.scanning = True
        self.barcode_data = None
        
        # In a real implementation, you would listen for scanner input
        # For this example, we'll simulate it with a dialog
        return self.simulate_scanner_input()
    
    def simulate_scanner_input(self):
        """Simulate barcode scanner input with a dialog"""
        from PyQt5.QtWidgets import QInputDialog
        barcode, ok = QInputDialog.getText(None, "Barcode Scanner", 
                                         "Scan barcode or enter manually:")
        if ok and barcode:
            return barcode
        return None
    
    def stop_scan(self):
        self.scanning = False

class PDFGenerator:
    @staticmethod
    def generate_invoice_pdf(invoice_data, file_path):
        # Use half of A4 size (width, height)
        page_width, page_height = letter
        page_height = page_height / 2  # Half A4 height
        
        c = canvas.Canvas(file_path, pagesize=(page_width, page_height))
        width, height = (page_width, page_height)
        
        # Set fonts
        c.setFont("Helvetica-Bold", 14)
        
        # Pharmacy header
        c.drawCentredString(width/2, height-30, "Mahavir Medical Store")
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height-45, "SHALIMAR SHOPPING CENTER, LALA NIGAM ROAD,COLOBA MARKET, MUMBAI 400005")
        c.drawCentredString(width/2, height-60, "Phone: 9821310312, 9821325949")
        
        # Draw a line separator
        c.line(50, height-70, width-50, height-70)
        
        # Invoice info
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height-90, f"Invoice #: {invoice_data['invoice_number']}")
        c.drawString(width-200, height-90, f"Date: {invoice_data['date']}")
        
        # Customer info
        c.setFont("Helvetica", 10)
        c.drawString(50, height-110, f"Customer: {invoice_data['customer_name']}")
        if invoice_data['customer_phone']:
            c.drawString(50, height-125, f"Phone: {invoice_data['customer_phone']}")
        
        # Items table header
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height-150, "Item")
        c.drawString(width-250, height-150, "Price")
        c.drawString(width-200, height-150, "Qty")
        c.drawString(width-150, height-150, "Total")
        
        # Draw line under header
        c.line(50, height-155, width-50, height-155)
        
        # Items
        y_position = height-170
        c.setFont("Helvetica", 9)
        for item in invoice_data['items']:
            # Wrap item name if too long
            item_name = item['medicine_name']
            if len(item_name) > 30:
                item_name = item_name[:27] + "..."
            
            c.drawString(50, y_position, item_name)
            c.drawString(width-250, y_position, f"₹{item['price']:.2f}")
            c.drawString(width-200, y_position, str(item['quantity']))
            c.drawString(width-150, y_position, f"₹{item['price'] * item['quantity']:.2f}")
            y_position -= 15
            
            # Add batch/expiry if space allows
            if y_position > 100:
                batch_info = f"Exp: {item.get('expiry_date', '')}"
                c.setFont("Helvetica-Oblique", 8)
                c.drawString(50, y_position, batch_info)
                c.setFont("Helvetica", 9)
                y_position -= 15
            
            # Check if we need a new page (unlikely for half A4)
            if y_position < 100:
                c.showPage()
                y_position = height-30
                c.setFont("Helvetica", 9)
        
        # Totals
        c.setFont("Helvetica-Bold", 10)
        c.drawString(width-200, y_position-20, "Subtotal:")
        c.drawString(width-150, y_position-20, f"₹{invoice_data['subtotal']:.2f}")
        
        c.drawString(width-200, y_position-35, "Discount:")
        c.drawString(width-150, y_position-35, f"₹{invoice_data['discount']:.2f}")
        
        c.drawString(width-200, y_position-50, "Tax (5% GST):")
        c.drawString(width-150, y_position-50, f"₹{invoice_data['tax']:.2f}")
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(width-200, y_position-70, "Total:")
        c.drawString(width-150, y_position-70, f"₹{invoice_data['total']:.2f}")
        
        # Payment method
        c.setFont("Helvetica", 10)
        c.drawString(50, y_position-90, f"Payment Method: {invoice_data['payment_method']}")
        
        # Footer
        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(width/2, 30, "Thank you! Visit us again!")
        
        c.save()

class NotificationService:
    def __init__(self):
        # These should be loaded from a config file in production
        self.email_settings = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': 'mahavirstore.coloba@gmail.com',
            'password': 'ycid tadr gklc laii',
            'from_email': 'mahavirstore.coloba@gmail.com'
        }
        
        self.whatsapp_settings = {
            'access_token': 'EAAKZCsOsKAEABPDSWwtO5q5FZBZCAQskBqP8IeDeDeM6RhSsFQQQXqsBjJwqXqv3aj8EZB4H2rs1mHPEElMOvU4IU8KrEzjEhN0DVHj8lqlh1HlYOs78K7hDyXuHIxgQYvNJDEz1JY1TkIOZBss96aAbTpjozbPnE7rmwuoVLNJ1jQXZBZCAnL5bVDKYnSezFg68Ynv5IwfMa0VP3vtVq2tLELRjDvHamaAttxZALB4TBwpY',
            'phone_number_id': '705267766011515'
            }
    
    def send_email(self, to_email, subject, body, attachment_path=None):
        if not self.email_settings['username'] or not self.email_settings['password']:
            print("Email not configured")
            return False
            
        msg = MIMEMultipart()
        msg['From'] = self.email_settings['from_email']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        if attachment_path:
            with open(attachment_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header('Content-Disposition', 'attachment', 
                                filename=os.path.basename(attachment_path))
                msg.attach(attach)
        
        try:
            server = smtplib.SMTP(self.email_settings['smtp_server'], 
                                 self.email_settings['smtp_port'])
            server.starttls()
            server.login(self.email_settings['username'], 
                        self.email_settings['password'])
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False
        
    def send_whatsapp_invoice(self, to_number, pdf_path):
        """
        Send a pharmacy bill (PDF) to customer via WhatsApp.
        Works in both sandbox (template) and production (document).
        """
        token = self.whatsapp_settings["access_token"]
        phone_number_id = self.whatsapp_settings["phone_number_id"]

        # ✅ Normalize phone number (must be like 919876543210)
        to_number = str(to_number).replace(" ", "").replace("+", "")

        headers = {"Authorization": f"Bearer {token}"}

        # ---------- Step 1: Upload the PDF ----------
        upload_url = f"https://graph.facebook.com/v22.0/{phone_number_id}/media"
        files = {
            "file": (os.path.basename(pdf_path), open(pdf_path, "rb"), "application/pdf")
        }
        data = {"messaging_product": "whatsapp"}

        upload_response = requests.post(upload_url, headers=headers, files=files, data=data)
        print("Upload response:", upload_response.text)

        if upload_response.status_code != 200:
            print("⚠️ Upload failed, cannot send invoice.")
            return False

        media_id = upload_response.json().get("id")

        # ---------- Step 2: Try sending as document ----------
        message_url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "document",
            "document": {
                "id": media_id,
                "caption": "🧾 Your Pharmacy Bill"
            },
            "type": "template",
            "template": {
                "name": "hello_world",  # 🔑 Replace with your own approved template name
                "language": {"code": "en_US"}
            }
            
        }
        

        send_response = requests.post(message_url, headers=headers, json=payload)
        print("Send response (Document):", send_response.text)

        if send_response.status_code == 200:
            print("✅ Invoice sent successfully via WhatsApp (document).")
            return True

        # ---------- Step 3: Sandbox fallback → send template ----------
        print("⚠️ Document message failed. Trying template fallback...")

        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": {
                "name": "hello_world",  # 🔑 Replace with your own approved template name
                "language": {"code": "en_US"}
            }
        }

        send_response = requests.post(message_url, headers=headers, json=payload)
        print("Send response (Template):", send_response.text)

        if send_response.status_code == 200:
            print("✅ Fallback template sent successfully.")
            return True

        print("❌ Failed to send invoice.")
        return False

class LoginWindow(QWidget):
    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        self.db = PharmacyDatabase()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Pharmacy System - Login')
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # Logo or title
        title = QLabel("Mahavir Medical Store")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2a6099;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Login form
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        form_layout.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.password_input)
        
        layout.addLayout(form_layout)
        
        # Login button
        login_btn = QPushButton("Login")
        login_btn.setStyleSheet("background-color: #2a6099; color: white; padding: 8px;")
        login_btn.clicked.connect(self.attempt_login)
        layout.addWidget(login_btn)
        
        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.error_label)
        
        self.setLayout(layout)
    
    def attempt_login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        
        if not username or not password:
            self.error_label.setText("Please enter both username and password")
            return
            
        user = self.db.authenticate_user(username, password)
        if user:
            self.on_login_success(user)
            self.close()
        else:
            self.error_label.setText("Invalid username or password")

class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.db = PharmacyDatabase()
        self.barcode_scanner = BarcodeScanner()
        self.notification_service = NotificationService()
        self.current_invoice_items = []
        self.init_ui()
        self.check_alerts()
        
        # Setup auto-alert check every hour
        self.alert_timer = QTimer()
        self.alert_timer.timeout.connect(self.check_alerts)
        self.alert_timer.start(3600000)  # 1 hour
        
    def init_ui(self):
        self.setWindowTitle(f"Mahavir Medical Store Billing System - {self.user[3]} ({self.user[2]})")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Menu bar
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        backup_action = file_menu.addAction('Backup Database')
        backup_action.triggered.connect(self.backup_database)
        
        export_action = file_menu.addAction('Export Reports')
        export_action.triggered.connect(self.export_reports)
        
        exit_action = file_menu.addAction('Exit')
        exit_action.triggered.connect(self.close)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = help_menu.addAction('About')
        about_action.triggered.connect(self.show_about)
        
        # Main tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Billing Tab
        self.setup_billing_tab()
        
        # Inventory Tab
        self.setup_inventory_tab()
        
        # Customers Tab
        self.setup_customers_tab()
        
        # Reports Tab
        self.setup_reports_tab()
        
        # Admin Tab (only for admin users)
        if self.user[2] == 'admin':
            self.setup_admin_tab()
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def setup_billing_tab(self):
        billing_tab = QWidget()
        layout = QVBoxLayout()
        billing_tab.setLayout(layout)
        
        # Top section - Customer and Barcode
        top_group = QGroupBox("Sale Information")
        top_layout = QHBoxLayout()
        
        # Customer info
        customer_form = QFormLayout()
        
        self.customer_phone_input = QLineEdit()
        self.customer_phone_input.setPlaceholderText("Enter phone number")
        customer_form.addRow("Customer Phone:", self.customer_phone_input)
        
        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText("Name (auto-filled if registered)")
        customer_form.addRow("Customer Name:", self.customer_name_input)
        
        self.customer_email_input = QLineEdit()
        self.customer_email_input.setPlaceholderText("Email (optional)")
        customer_form.addRow("Customer Email:", self.customer_email_input)
        
        top_layout.addLayout(customer_form)
        
        # Barcode section
        barcode_layout = QVBoxLayout()
        
        scan_btn = QPushButton("Scan Barcode")
        scan_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        scan_btn.clicked.connect(self.scan_barcode)
        barcode_layout.addWidget(scan_btn)
        
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Or enter barcode manually")
        barcode_layout.addWidget(self.barcode_input)
        
        add_btn = QPushButton("Add Item")
        add_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        add_btn.clicked.connect(self.add_item_to_invoice)
        barcode_layout.addWidget(add_btn)
        
        top_layout.addLayout(barcode_layout)
        top_group.setLayout(top_layout)
        layout.addWidget(top_group)
        
        # Middle section - Invoice items table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(6)
        self.invoice_table.setHorizontalHeaderLabels(["ID", "Medicine", "Batch", "Price", "Qty", "Total"])
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.invoice_table)
        
        # Bottom section - Totals and actions
        bottom_group = QGroupBox("Invoice Summary")
        bottom_layout = QHBoxLayout()
        
        # Totals
        totals_layout = QFormLayout()
        
        self.subtotal_label = QLabel("₹0.00")
        totals_layout.addRow("Subtotal:", self.subtotal_label)
        
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 100)
        self.discount_input.setValue(0)
        self.discount_input.setSuffix("%")
        totals_layout.addRow("Discount:", self.discount_input)
        
        self.tax_label = QLabel("₹0.00 (5% GST)")
        totals_layout.addRow("Tax:", self.tax_label)
        
        self.total_label = QLabel("₹0.00")
        totals_layout.addRow("Total:", self.total_label)
        
        bottom_layout.addLayout(totals_layout)
        
        # Payment and actions
        action_layout = QVBoxLayout()
        
        payment_group = QGroupBox("Payment Method")
        payment_layout = QHBoxLayout()
        
        self.payment_cash = QRadioButton("Cash")
        self.payment_cash.setChecked(True)
        payment_layout.addWidget(self.payment_cash)
        
        self.payment_card = QRadioButton("Card")
        payment_layout.addWidget(self.payment_card)
        
        self.payment_upi = QRadioButton("UPI")
        payment_layout.addWidget(self.payment_upi)
        
        payment_group.setLayout(payment_layout)
        action_layout.addWidget(payment_group)
        
        # Notification options
        notify_group = QGroupBox("Notifications")
        notify_layout = QHBoxLayout()
        
        self.email_checkbox = QCheckBox("Email Receipt")
        self.email_checkbox.setChecked(True)
        notify_layout.addWidget(self.email_checkbox)
        
        self.sms_checkbox = QCheckBox("SMS Receipt")
        self.sms_checkbox.setChecked(True)
        notify_layout.addWidget(self.sms_checkbox)
        
        notify_group.setLayout(notify_layout)
        action_layout.addWidget(notify_group)
        
        # Final buttons
        clear_btn = QPushButton("Clear Invoice")
        clear_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 8px;")
        clear_btn.clicked.connect(self.clear_invoice)
        action_layout.addWidget(clear_btn)
        
        complete_btn = QPushButton("Complete Sale")
        complete_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        complete_btn.clicked.connect(self.complete_sale)
        action_layout.addWidget(complete_btn)
        
        bottom_layout.addLayout(action_layout)
        bottom_group.setLayout(bottom_layout)
        layout.addWidget(bottom_group)
        
        self.tabs.addTab(billing_tab, "Billing")
        
        # Connect customer phone lookup
        self.customer_phone_input.editingFinished.connect(self.lookup_customer)
    
    def setup_inventory_tab(self):
        inventory_tab = QWidget()
        layout = QVBoxLayout()
        inventory_tab.setLayout(layout)
        
        # Search and filter
        search_group = QGroupBox("Search & Filter")
        search_layout = QHBoxLayout()
        
        self.inventory_search = QLineEdit()
        self.inventory_search.setPlaceholderText("Search medicines...")
        self.inventory_search.textChanged.connect(self.filter_inventory)
        search_layout.addWidget(self.inventory_search)
        
        filter_btn = QPushButton("Low Stock")
        filter_btn.setStyleSheet("background-color: #e9c46a; color: black; padding: 5px;")
        filter_btn.clicked.connect(lambda: self.filter_inventory(filter_low_stock=True))
        search_layout.addWidget(filter_btn)
        
        filter_btn = QPushButton("Expired")
        filter_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 5px;")
        filter_btn.clicked.connect(self.show_expired_medicines)
        search_layout.addWidget(filter_btn)
        
        # Add Clear Filter button
        clear_filter_btn = QPushButton("Clear Filter")
        clear_filter_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 5px;")
        clear_filter_btn.clicked.connect(self.clear_inventory_filter)
        search_layout.addWidget(clear_filter_btn)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Inventory table
        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(9)
        self.inventory_table.setHorizontalHeaderLabels(["ID", "Name", "Barcode", "Batch", "Price", "Stock", "Expiry", "Category", "Actions"])
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inventory_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.inventory_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add Medicine")
        add_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        add_btn.clicked.connect(self.show_add_medicine_dialog)
        btn_layout.addWidget(add_btn)
        
        import_btn = QPushButton("Import from CSV")
        import_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        import_btn.clicked.connect(self.import_medicines)
        btn_layout.addWidget(import_btn)
        
        export_btn = QPushButton("Export to CSV")
        export_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        export_btn.clicked.connect(self.export_medicines)
        btn_layout.addWidget(export_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(inventory_tab, "Inventory")
        self.load_inventory()
    
    def setup_customers_tab(self):
        customers_tab = QWidget()
        layout = QVBoxLayout()
        customers_tab.setLayout(layout)
        
        # Search
        search_group = QGroupBox("Search Customers")
        search_layout = QHBoxLayout()
        
        self.customer_search = QLineEdit()
        self.customer_search.setPlaceholderText("Search customers...")
        self.customer_search.textChanged.connect(self.filter_customers)
        search_layout.addWidget(self.customer_search)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Customers table
        self.customers_table = QTableWidget()
        self.customers_table.setColumnCount(7)  # Added Actions column
        self.customers_table.setHorizontalHeaderLabels(["ID", "Name", "Phone", "Email", "Address", "Joined", "Actions"])
        self.customers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.customers_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.customers_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add Customer")
        add_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        add_btn.clicked.connect(self.show_add_customer_dialog)
        btn_layout.addWidget(add_btn)
        
        export_btn = QPushButton("Export to CSV")
        export_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        export_btn.clicked.connect(self.export_customers)
        btn_layout.addWidget(export_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(customers_tab, "Customers")
        self.load_customers()
    
    def setup_reports_tab(self):
        reports_tab = QWidget()
        layout = QVBoxLayout()
        reports_tab.setLayout(layout)
        
        # Date range selection
        date_group = QGroupBox("Report Period")
        date_layout = QHBoxLayout()
        
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setCalendarPopup(True)
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.start_date)
        
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.end_date)
        
        generate_btn = QPushButton("Generate Report")
        generate_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 5px;")
        generate_btn.clicked.connect(self.generate_sales_report)
        date_layout.addWidget(generate_btn)
        
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        
        # Sales report table
        self.sales_report_table = QTableWidget()
        self.sales_report_table.setColumnCount(6)
        self.sales_report_table.setHorizontalHeaderLabels(["ID", "Invoice", "Date", "Customer", "Amount", "Payment"])
        self.sales_report_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sales_report_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sales_report_table.doubleClicked.connect(self.show_sale_details)
        layout.addWidget(self.sales_report_table)
        
        # Summary
        summary_group = QGroupBox("Summary")
        summary_layout = QFormLayout()
        
        self.total_sales_label = QLabel("₹0.00")
        summary_layout.addRow("Total Sales:", self.total_sales_label)
        
        self.cash_sales_label = QLabel("₹0.00")
        summary_layout.addRow("Cash Sales:", self.cash_sales_label)
        
        self.card_sales_label = QLabel("₹0.00")
        summary_layout.addRow("Card Sales:", self.card_sales_label)
        
        self.upi_sales_label = QLabel("₹0.00")
        summary_layout.addRow("UPI Sales:", self.upi_sales_label)
        
        self.total_customers_label = QLabel("0")
        summary_layout.addRow("Total Customers:", self.total_customers_label)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        export_btn = QPushButton("Export Report")
        export_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        export_btn.clicked.connect(self.export_sales_report)
        btn_layout.addWidget(export_btn)
        
        print_btn = QPushButton("Print Report")
        print_btn.setStyleSheet("background-color: #2a6099; color: white; padding: 8px;")
        btn_layout.addWidget(print_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(reports_tab, "Reports")
        self.generate_sales_report()
    
    def setup_admin_tab(self):
        admin_tab = QWidget()
        layout = QVBoxLayout()
        admin_tab.setLayout(layout)
        
        # Settings group
        settings_group = QGroupBox("System Settings")
        settings_layout = QFormLayout()
        
        self.pharmacy_name = QLineEdit("Mahavir Medical Store")
        settings_layout.addRow("Pharmacy Name:", self.pharmacy_name)
        
        self.pharmacy_address = QTextEdit()
        self.pharmacy_address.setPlainText("123 Medical Street, City - 123456")
        settings_layout.addRow("Address:", self.pharmacy_address)
        
        self.pharmacy_phone = QLineEdit("+91 9876543210")
        settings_layout.addRow("Phone:", self.pharmacy_phone)
        
        self.pharmacy_gst = QLineEdit("22AAAAA0000A1Z5")
        settings_layout.addRow("GSTIN:", self.pharmacy_gst)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Email/SMS settings
        notify_group = QGroupBox("Notification Settings")
        notify_layout = QFormLayout()
        
        self.smtp_server = QLineEdit("smtp.gmail.com")
        notify_layout.addRow("SMTP Server:", self.smtp_server)
        
        self.smtp_port = QSpinBox()
        self.smtp_port.setValue(587)
        notify_layout.addRow("SMTP Port:", self.smtp_port)
        
        self.email_username = QLineEdit("yourpharmacy@gmail.com")
        notify_layout.addRow("Email Username:", self.email_username)
        
        self.email_password = QLineEdit()
        self.email_password.setEchoMode(QLineEdit.Password)
        notify_layout.addRow("Email Password:", self.email_password)
        
        self.twilio_sid = QLineEdit()
        notify_layout.addRow("Twilio SID:", self.twilio_sid)
        
        self.twilio_token = QLineEdit()
        notify_layout.addRow("Twilio Token:", self.twilio_token)
        
        self.twilio_number = QLineEdit()
        notify_layout.addRow("Twilio Number:", self.twilio_number)
        
        notify_group.setLayout(notify_layout)
        layout.addWidget(notify_group)
        
        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        # Database management
        db_group = QGroupBox("Database Management")
        db_layout = QHBoxLayout()
        
        backup_btn = QPushButton("Backup Database")
        backup_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        backup_btn.clicked.connect(self.backup_database)
        db_layout.addWidget(backup_btn)
        
        restore_btn = QPushButton("Restore Database")
        restore_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 8px;")
        db_layout.addWidget(restore_btn)
        
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)
        
        self.tabs.addTab(admin_tab, "Admin")
    
    def scan_barcode(self):
        barcode = self.barcode_scanner.start_scan()
        if barcode:
            self.barcode_input.setText(barcode)
            self.add_item_to_invoice()
    
    def lookup_customer(self):
        phone = self.customer_phone_input.text()
        if phone:
            customer = self.db.get_customer_by_phone(phone)
            if customer:
                self.customer_name_input.setText(customer[1])
                self.customer_email_input.setText(customer[3] if customer[3] else "")
    
    def add_item_to_invoice(self):
        barcode = self.barcode_input.text()
        if not barcode:
            QMessageBox.warning(self, "Error", "Please enter or scan a barcode")
            return
            
        medicine = self.db.get_medicine_by_barcode(barcode)
        if not medicine:
            QMessageBox.warning(self, "Error", "Medicine not found in inventory")
            return
            
        # Check if already in invoice
        for item in self.current_invoice_items:
            if item['medicine_id'] == medicine[0]:
                item['quantity'] += 1
                self.update_invoice_table()
                return
                
        # Add new item
        self.current_invoice_items.append({
            'medicine_id': medicine[0],
            'medicine_name': medicine[1],
            'name': medicine[1],
            'barcode': medicine[2],
            'batch_number': medicine[3],
            'price': medicine[4],
            'mrp': medicine[5],
            'quantity': 1,
            'expiry_date': medicine[7]
        })
        
        self.update_invoice_table()
        self.barcode_input.clear()
    
    def update_invoice_table(self):
        self.invoice_table.setRowCount(len(self.current_invoice_items))
        
        subtotal = 0
        for row, item in enumerate(self.current_invoice_items):
            self.invoice_table.setItem(row, 0, QTableWidgetItem(str(item['medicine_id'])))
            self.invoice_table.setItem(row, 1, QTableWidgetItem(item['name']))
            self.invoice_table.setItem(row, 2, QTableWidgetItem(item['batch_number']))
            self.invoice_table.setItem(row, 3, QTableWidgetItem(f"₹{item['price']:.2f}"))
            
            qty_item = QTableWidgetItem(str(item['quantity']))
            self.invoice_table.setItem(row, 4, qty_item)
            
            total = item['price'] * item['quantity']
            self.invoice_table.setItem(row, 5, QTableWidgetItem(f"₹{total:.2f}"))
        
            subtotal += total
        
        # Calculate totals
        discount_percent = self.discount_input.value()
        discount_amount = subtotal * (discount_percent / 100)
        tax_amount = (subtotal - discount_amount) * 0.05  # 5% GST
        total_amount = subtotal - discount_amount + tax_amount
        
        self.subtotal_label.setText(f"₹{subtotal:.2f}")
        self.tax_label.setText(f"₹{tax_amount:.2f} (5% GST)")
        self.total_label.setText(f"₹{total_amount:.2f}")
    
    def clear_invoice(self):
        self.current_invoice_items = []
        self.invoice_table.setRowCount(0)
        self.subtotal_label.setText("₹0.00")
        self.tax_label.setText("₹0.00 (5% GST)")
        self.total_label.setText("₹0.00")
        self.discount_input.setValue(0)
        self.customer_phone_input.clear()
        self.customer_name_input.clear()
        self.customer_email_input.clear()
        self.payment_cash.setChecked(True)
    
    def complete_sale(self):
        if not self.current_invoice_items:
            QMessageBox.warning(self, "Error", "No items in the invoice")
            return
            
        # Get customer info
        customer_name = self.customer_name_input.text()
        customer_phone = self.customer_phone_input.text()
        customer_email = self.customer_email_input.text()
        
        # Create customer if not exists
        customer_id = None
        if customer_phone:
            customer = self.db.get_customer_by_phone(customer_phone)
            if not customer:
                customer_data = {
                    'name': customer_name if customer_name else "Walk-in Customer",
                    'phone': customer_phone,
                    'email': customer_email,
                    'address': ''
                }
                customer_id = self.db.add_customer(customer_data)
            else:
                customer_id = customer[0]
        
        # Get payment method
        payment_method = "Cash"
        if self.payment_card.isChecked():
            payment_method = "Card"
        elif self.payment_upi.isChecked():
            payment_method = "UPI"
        
        # Create sale data
        subtotal = sum(item['price'] * item['quantity'] for item in self.current_invoice_items)
        discount_percent = self.discount_input.value()
        discount_amount = subtotal * (discount_percent / 100)
        tax_amount = (subtotal - discount_amount) * 0.05
        total_amount = subtotal - discount_amount + tax_amount
        
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        sale_data = {
            'invoice_number': invoice_number,
            'customer_id': customer_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_amount': total_amount,
            'discount': discount_amount,
            'tax': tax_amount,
            'payment_method': payment_method,
            'items': self.current_invoice_items
        }
        
        # Save to database
        sale_id = self.db.create_sale(sale_data)
        if not sale_id:
            QMessageBox.critical(self, "Error", "Failed to save sale to database")
            return
            
        # Generate PDF
        invoice_data = {
            'invoice_number': invoice_number,
            'date': datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
            'customer_id': customer_id,
            'customer_name': customer_name if customer_name else "Walk-in Customer",
            'customer_phone': customer_phone,
            'customer_email': customer_email,
            'subtotal': subtotal,
            'discount': discount_amount,
            'tax': tax_amount,
            'total': total_amount,
            'payment_method': payment_method,
            'items': self.current_invoice_items
        }
        
        pdf_dir = "invoices"
        if not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir)
            
        pdf_path = os.path.join(pdf_dir, f"{invoice_number}.pdf")
        PDFGenerator.generate_invoice_pdf(invoice_data, pdf_path)
        
        
        # Send notifications
        if self.email_checkbox.isChecked() and customer_email:
            subject = f"Your Invoice from Mahavir Medical Store - {invoice_number}"
            body = f"Dear {customer_name},\n\nThank you for your purchase. Please find your invoice attached.\n\nTotal Amount: ₹{total_amount:.2f}\nPayment Method: {payment_method}\n\nPlease visit us again!"
            self.notification_service.send_email(customer_email, subject, body, pdf_path)
        
        if self.sms_checkbox.isChecked() and customer_phone:
            message = f"Thank you for shopping at Mahavir Medical Store. Your invoice #{invoice_number} amount is ₹{total_amount:.2f}. Please check your email for details."
            self.notification_service.send_whatsapp_invoice(customer_phone, pdf_path)
        
        # Ask if user wants to print receipt
        reply = QMessageBox.question(self, "Print Receipt", 
                                   f"Sale completed successfully!\nInvoice Number: {invoice_number}\nTotal Amount: ₹{total_amount:.2f}\n\nDo you want to print the receipt?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        
        if reply == QMessageBox.Yes:
            self.print_receipt(pdf_path)
        
        # Clear invoice
        self.clear_invoice()
        # Refresh reports
        self.generate_sales_report()
    
    import sys
import os
import sqlite3
from datetime import datetime, timedelta
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, 
                             QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                             QMessageBox, QFileDialog, QGroupBox, QFormLayout, QDateEdit,
                             QCheckBox, QTextEdit, QHeaderView)
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, 
                             QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                             QMessageBox, QFileDialog, QGroupBox, QFormLayout, QDateEdit,
                             QCheckBox, QTextEdit, QHeaderView, QRadioButton, QDialog, QInputDialog)
import cv2
from pyzbar.pyzbar import decode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib import colors
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
# from twilio.rest import Client
import barcode
from barcode.writer import ImageWriter
import pandas as pd
from PIL import Image, ImageQt
import requests
from twilio.rest import Client
import threading
import time


class PharmacyDatabase:
    def __init__(self, db_file='pharmacy.db'):
        self.db_file = db_file
        self._initialize_database()
        
    def _initialize_database(self):
        if not os.path.exists(self.db_file):
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
            # Medicines table
            c.execute('''CREATE TABLE medicines
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT NOT NULL,
                         barcode TEXT UNIQUE,
                         batch_number TEXT,
                         price REAL NOT NULL,
                         mrp REAL NOT NULL,
                         quantity INTEGER NOT NULL,
                         expiry_date TEXT,
                         manufacturer TEXT,
                         category TEXT,
                         min_stock_level INTEGER DEFAULT 5)''')
            
            # Customers table
            c.execute('''CREATE TABLE customers
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT NOT NULL,
                         phone TEXT,
                         email TEXT,
                         address TEXT,
                         created_date TEXT)''')
            
            # Sales table
            c.execute('''CREATE TABLE sales
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         invoice_number TEXT UNIQUE,
                         customer_id INTEGER,
                         date TEXT NOT NULL,
                         total_amount REAL NOT NULL,
                         discount REAL DEFAULT 0,
                         tax REAL DEFAULT 0,
                         payment_method TEXT,
                         FOREIGN KEY(customer_id) REFERENCES customers(id))''')
            
            # Sale items table
            c.execute('''CREATE TABLE sale_items
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         sale_id INTEGER NOT NULL,
                         medicine_id INTEGER NOT NULL,
                         quantity INTEGER NOT NULL,
                         price REAL NOT NULL,
                         FOREIGN KEY(sale_id) REFERENCES sales(id),
                         FOREIGN KEY(medicine_id) REFERENCES medicines(id))''')
            
            # Users table
            c.execute('''CREATE TABLE users
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         username TEXT UNIQUE NOT NULL,
                         password TEXT NOT NULL,
                         role TEXT NOT NULL,
                         full_name TEXT)''')
            
            # Add admin user
            c.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                      ('admin', 'admin123', 'admin', 'Administrator'))
            
            conn.commit()
            conn.close()
    
    def _get_connection(self):
        return sqlite3.connect(self.db_file)
    
    # Medicine methods
    def add_medicine(self, medicine_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO medicines 
                         (name, barcode, batch_number, price, mrp, quantity, 
                          expiry_date, manufacturer, category, min_stock_level)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (medicine_data['name'], medicine_data['barcode'], 
                       medicine_data['batch_number'], medicine_data['price'],
                       medicine_data['mrp'], medicine_data['quantity'],
                       medicine_data['expiry_date'], medicine_data['manufacturer'],
                       medicine_data['category'], medicine_data['min_stock_level']))
            conn.commit()
            return c.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def update_medicine(self, medicine_id, medicine_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute('''UPDATE medicines SET 
                         name=?, barcode=?, batch_number=?, price=?, mrp=?,
                         quantity=?, expiry_date=?, manufacturer=?, category=?,
                         min_stock_level=?
                         WHERE id=?''',
                      (medicine_data['name'], medicine_data['barcode'], 
                       medicine_data['batch_number'], medicine_data['price'],
                       medicine_data['mrp'], medicine_data['quantity'],
                       medicine_data['expiry_date'], medicine_data['manufacturer'],
                       medicine_data['category'], medicine_data['min_stock_level'],
                       medicine_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def get_medicine_by_barcode(self, barcode):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM medicines WHERE barcode=?", (barcode,))
            return c.fetchone()
        finally:
            conn.close()
    
    def get_all_medicines(self):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM medicines ORDER BY name")
            return c.fetchall()
        finally:
            conn.close()
    
    def get_low_stock_medicines(self, threshold=None):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            if threshold:
                c.execute('''SELECT * FROM medicines 
                             WHERE quantity <= min_stock_level OR quantity <= ?
                             ORDER BY quantity ASC''', (threshold,))
            else:
                c.execute('''SELECT * FROM medicines 
                             WHERE quantity <= min_stock_level
                             ORDER BY quantity ASC''')
            return c.fetchall()
        finally:
            conn.close()
    
    def get_expired_medicines(self):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            c.execute("SELECT * FROM medicines WHERE expiry_date < ? ORDER BY expiry_date", (today,))
            return c.fetchall()
        finally:
            conn.close()
    
    def update_medicine_stock(self, medicine_id, quantity_change):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("UPDATE medicines SET quantity = quantity + ? WHERE id=?", 
                     (quantity_change, medicine_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    # Customer methods
    def add_customer(self, customer_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            created_date = datetime.now().strftime('%Y-%m-%d')
            c.execute('''INSERT INTO customers 
                         (name, phone, email, address, created_date)
                         VALUES (?, ?, ?, ?, ?)''',
                      (customer_data['name'], customer_data['phone'],
                       customer_data['email'], customer_data['address'],
                       created_date))
            conn.commit()
            return c.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def update_customer(self, customer_id, customer_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute('''UPDATE customers SET 
                         name=?, phone=?, email=?, address=?
                         WHERE id=?''',
                      (customer_data['name'], customer_data['phone'],
                       customer_data['email'], customer_data['address'],
                       customer_id))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def get_customer_by_phone(self, phone):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM customers WHERE phone=?", (phone,))
            return c.fetchone()
        finally:
            conn.close()
    
    def get_customer_by_id(self, customer_id):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM customers WHERE id=?", (customer_id,))
            return c.fetchone()
        finally:
            conn.close()
    
    def get_all_customers(self):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM customers ORDER BY name")
            return c.fetchall()
        finally:
            conn.close()
    
    # Sales methods
    def create_sale(self, sale_data):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            # Create sale record
            c.execute('''INSERT INTO sales 
                         (invoice_number, customer_id, date, total_amount, 
                          discount, tax, payment_method)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (sale_data['invoice_number'], sale_data['customer_id'],
                       sale_data['date'], sale_data['total_amount'],
                       sale_data['discount'], sale_data['tax'],
                       sale_data['payment_method']))
            sale_id = c.lastrowid
            
            # Add sale items
            for item in sale_data['items']:
                c.execute('''INSERT INTO sale_items 
                             (sale_id, medicine_id, quantity, price)
                             VALUES (?, ?, ?, ?)''',
                          (sale_id, item['medicine_id'], 
                           item['quantity'], item['price']))
                # Update stock
                c.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?",
                         (item['quantity'], item['medicine_id']))
            
            conn.commit()
            return sale_id
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def get_sales_report(self, start_date=None, end_date=None):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            if start_date and end_date:
                c.execute('''SELECT s.id, s.invoice_number, s.date, 
                                    c.name as customer_name, 
                                    s.total_amount, s.payment_method
                             FROM sales s
                             LEFT JOIN customers c ON s.customer_id = c.id
                             WHERE s.date BETWEEN ? AND ?
                             ORDER BY s.date DESC''', (start_date, end_date))
            else:
                c.execute('''SELECT s.id, s.invoice_number, s.date, 
                                    c.name as customer_name, 
                                    s.total_amount, s.payment_method
                             FROM sales s
                             LEFT JOIN customers c ON s.customer_id = c.id
                             ORDER BY s.date DESC''')
            return c.fetchall()
        finally:
            conn.close()
    
    def get_sale_details(self, sale_id):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            # Get sale header
            c.execute('''SELECT s.*, c.name as customer_name, c.phone, c.email
                         FROM sales s
                         LEFT JOIN customers c ON s.customer_id = c.id
                         WHERE s.id=?''', (sale_id,))
            sale_header = c.fetchone()
            
            if not sale_header:
                return None
            
            # Get sale items
            c.execute('''SELECT si.*, m.name as medicine_name, m.barcode
                         FROM sale_items si
                         JOIN medicines m ON si.medicine_id = m.id
                         WHERE si.sale_id=?''', (sale_id,))
            sale_items = c.fetchall()
            
            return {
                'header': sale_header,
                'items': sale_items
            }
        finally:
            conn.close()
    
    # User authentication
    def authenticate_user(self, username, password):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM users WHERE username=? AND password=?", 
                     (username, password))
            return c.fetchone()
        finally:
            conn.close()

class BarcodeScanner:
    def __init__(self):
        self.capture = None
        self.scanning = False
        self.barcode_data = None
        
    def start_scan(self):
        """Start scanning for barcode input from physical scanner (keyboard input)"""
        self.scanning = True
        self.barcode_data = None
        
        # In a real implementation, you would listen for scanner input
        # For this example, we'll simulate it with a dialog
        return self.simulate_scanner_input()
    
    def simulate_scanner_input(self):
        """Simulate barcode scanner input with a dialog"""
        from PyQt5.QtWidgets import QInputDialog
        barcode, ok = QInputDialog.getText(None, "Barcode Scanner", 
                                         "Scan barcode or enter manually:")
        if ok and barcode:
            return barcode
        return None
    
    def stop_scan(self):
        self.scanning = False

class PDFGenerator:
    @staticmethod
    def generate_invoice_pdf(invoice_data, file_path):
        # Use half of A4 size (width, height)
        page_width, page_height = letter
        page_height = page_height / 2  # Half A4 height
        
        c = canvas.Canvas(file_path, pagesize=(page_width, page_height))
        width, height = (page_width, page_height)
        
        # Set fonts
        c.setFont("Helvetica-Bold", 14)
        
        # Pharmacy header
        c.drawCentredString(width/2, height-30, "Mahavir Medical Store")
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height-45, "SHALIMAR SHOPPING CENTER, LALA NIGAM ROAD,COLOBA MARKET, MUMBAI 400005")
        c.drawCentredString(width/2, height-60, "Phone: 9821310312, 9821325949")
        
        # Draw a line separator
        c.line(50, height-70, width-50, height-70)
        
        # Invoice info
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height-90, f"Invoice #: {invoice_data['invoice_number']}")
        c.drawString(width-200, height-90, f"Date: {invoice_data['date']}")
        
        # Customer info
        c.setFont("Helvetica", 10)
        c.drawString(50, height-110, f"Customer: {invoice_data['customer_name']}")
        if invoice_data['customer_phone']:
            c.drawString(50, height-125, f"Phone: {invoice_data['customer_phone']}")
        
        # Items table header
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height-150, "Item")
        c.drawString(width-250, height-150, "Price")
        c.drawString(width-200, height-150, "Qty")
        c.drawString(width-150, height-150, "Total")
        
        # Draw line under header
        c.line(50, height-155, width-50, height-155)
        
        # Items
        y_position = height-170
        c.setFont("Helvetica", 9)
        for item in invoice_data['items']:
            # Wrap item name if too long
            item_name = item['medicine_name']
            if len(item_name) > 30:
                item_name = item_name[:27] + "..."
            
            c.drawString(50, y_position, item_name)
            c.drawString(width-250, y_position, f"₹{item['price']:.2f}")
            c.drawString(width-200, y_position, str(item['quantity']))
            c.drawString(width-150, y_position, f"₹{item['price'] * item['quantity']:.2f}")
            y_position -= 15
            
            # Add batch/expiry if space allows
            if y_position > 100:
                batch_info = f"Exp: {item.get('expiry_date', '')}"
                c.setFont("Helvetica-Oblique", 8)
                c.drawString(50, y_position, batch_info)
                c.setFont("Helvetica", 9)
                y_position -= 15
            
            # Check if we need a new page (unlikely for half A4)
            if y_position < 100:
                c.showPage()
                y_position = height-30
                c.setFont("Helvetica", 9)
        
        # Totals
        c.setFont("Helvetica-Bold", 10)
        c.drawString(width-200, y_position-20, "Subtotal:")
        c.drawString(width-150, y_position-20, f"₹{invoice_data['subtotal']:.2f}")
        
        c.drawString(width-200, y_position-35, "Discount:")
        c.drawString(width-150, y_position-35, f"₹{invoice_data['discount']:.2f}")
        
        c.drawString(width-200, y_position-50, "Tax (5% GST):")
        c.drawString(width-150, y_position-50, f"₹{invoice_data['tax']:.2f}")
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(width-200, y_position-70, "Total:")
        c.drawString(width-150, y_position-70, f"₹{invoice_data['total']:.2f}")
        
        # Payment method
        c.setFont("Helvetica", 10)
        c.drawString(50, y_position-90, f"Payment Method: {invoice_data['payment_method']}")
        
        # Footer
        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(width/2, 30, "Thank you! Visit us again!")
        
        c.save()

class NotificationService:
    def __init__(self):
        # These should be loaded from a config file in production
        self.email_settings = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': 'mahavirstore.coloba@gmail.com',
            'password': 'ycid tadr gklc laii',
            'from_email': 'mahavirstore.coloba@gmail.com'
        }
        
        self.whatsapp_settings = {
            'access_token': 'EAAKZCsOsKAEABPDSWwtO5q5FZBZCAQskBqP8IeDeDeM6RhSsFQQQXqsBjJwqXqv3aj8EZB4H2rs1mHPEElMOvU4IU8KrEzjEhN0DVHj8lqlh1HlYOs78K7hDyXuHIxgQYvNJDEz1JY1TkIOZBss96aAbTpjozbPnE7rmwuoVLNJ1jQXZBZCAnL5bVDKYnSezFg68Ynv5IwfMa0VP3vtVq2tLELRjDvHamaAttxZALB4TBwpY',
            'phone_number_id': '705267766011515'
            }
    
    def send_email(self, to_email, subject, body, attachment_path=None):
        if not self.email_settings['username'] or not self.email_settings['password']:
            print("Email not configured")
            return False
            
        msg = MIMEMultipart()
        msg['From'] = self.email_settings['from_email']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        if attachment_path:
            with open(attachment_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header('Content-Disposition', 'attachment', 
                                filename=os.path.basename(attachment_path))
                msg.attach(attach)
        
        try:
            server = smtplib.SMTP(self.email_settings['smtp_server'], 
                                 self.email_settings['smtp_port'])
            server.starttls()
            server.login(self.email_settings['username'], 
                        self.email_settings['password'])
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False
        
    def send_whatsapp_invoice(self, to_number, pdf_path):
        """
        Send a pharmacy bill (PDF) to customer via WhatsApp.
        Works in both sandbox (template) and production (document).
        """
        token = self.whatsapp_settings["access_token"]
        phone_number_id = self.whatsapp_settings["phone_number_id"]

        # ✅ Normalize phone number (must be like 919876543210)
        to_number = str(to_number).replace(" ", "").replace("+", "")

        headers = {"Authorization": f"Bearer {token}"}

        # ---------- Step 1: Upload the PDF ----------
        upload_url = f"https://graph.facebook.com/v22.0/{phone_number_id}/media"
        files = {
            "file": (os.path.basename(pdf_path), open(pdf_path, "rb"), "application/pdf")
        }
        data = {"messaging_product": "whatsapp"}

        upload_response = requests.post(upload_url, headers=headers, files=files, data=data)
        print("Upload response:", upload_response.text)

        if upload_response.status_code != 200:
            print("⚠️ Upload failed, cannot send invoice.")
            return False

        media_id = upload_response.json().get("id")

        # ---------- Step 2: Try sending as document ----------
        message_url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "document",
            "document": {
                "id": media_id,
                "caption": "🧾 Your Pharmacy Bill"
            },
            "type": "template",
            "template": {
                "name": "hello_world",  # 🔑 Replace with your own approved template name
                "language": {"code": "en_US"}
            }
            
        }
        

        send_response = requests.post(message_url, headers=headers, json=payload)
        print("Send response (Document):", send_response.text)

        if send_response.status_code == 200:
            print("✅ Invoice sent successfully via WhatsApp (document).")
            return True

        # ---------- Step 3: Sandbox fallback → send template ----------
        print("⚠️ Document message failed. Trying template fallback...")

        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": {
                "name": "hello_world",  # 🔑 Replace with your own approved template name
                "language": {"code": "en_US"}
            }
        }

        send_response = requests.post(message_url, headers=headers, json=payload)
        print("Send response (Template):", send_response.text)

        if send_response.status_code == 200:
            print("✅ Fallback template sent successfully.")
            return True

        print("❌ Failed to send invoice.")
        return False

class LoginWindow(QWidget):
    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        self.db = PharmacyDatabase()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Pharmacy System - Login')
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # Logo or title
        title = QLabel("Mahavir Medical Store")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2a6099;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Login form
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        form_layout.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.password_input)
        
        layout.addLayout(form_layout)
        
        # Login button
        login_btn = QPushButton("Login")
        login_btn.setStyleSheet("background-color: #2a6099; color: white; padding: 8px;")
        login_btn.clicked.connect(self.attempt_login)
        layout.addWidget(login_btn)
        
        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.error_label)
        
        self.setLayout(layout)
    
    def attempt_login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        
        if not username or not password:
            self.error_label.setText("Please enter both username and password")
            return
            
        user = self.db.authenticate_user(username, password)
        if user:
            self.on_login_success(user)
            self.close()
        else:
            self.error_label.setText("Invalid username or password")

class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.db = PharmacyDatabase()
        self.barcode_scanner = BarcodeScanner()
        self.notification_service = NotificationService()
        self.current_invoice_items = []
        self.init_ui()
        self.check_alerts()
        
        # Setup auto-alert check every hour
        self.alert_timer = QTimer()
        self.alert_timer.timeout.connect(self.check_alerts)
        self.alert_timer.start(3600000)  # 1 hour
        
    def init_ui(self):
        self.setWindowTitle(f"Mahavir Medical Store Billing System - {self.user[3]} ({self.user[2]})")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Menu bar
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        backup_action = file_menu.addAction('Backup Database')
        backup_action.triggered.connect(self.backup_database)
        
        export_action = file_menu.addAction('Export Reports')
        export_action.triggered.connect(self.export_reports)
        
        exit_action = file_menu.addAction('Exit')
        exit_action.triggered.connect(self.close)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = help_menu.addAction('About')
        about_action.triggered.connect(self.show_about)
        
        # Main tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Billing Tab
        self.setup_billing_tab()
        
        # Inventory Tab
        self.setup_inventory_tab()
        
        # Customers Tab
        self.setup_customers_tab()
        
        # Reports Tab
        self.setup_reports_tab()
        
        # Admin Tab (only for admin users)
        if self.user[2] == 'admin':
            self.setup_admin_tab()
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def setup_billing_tab(self):
        billing_tab = QWidget()
        layout = QVBoxLayout()
        billing_tab.setLayout(layout)
        
        # Top section - Customer and Barcode
        top_group = QGroupBox("Sale Information")
        top_layout = QHBoxLayout()
        
        # Customer info
        customer_form = QFormLayout()
        
        self.customer_phone_input = QLineEdit()
        self.customer_phone_input.setPlaceholderText("Enter phone number")
        customer_form.addRow("Customer Phone:", self.customer_phone_input)
        
        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText("Name (auto-filled if registered)")
        customer_form.addRow("Customer Name:", self.customer_name_input)
        
        self.customer_email_input = QLineEdit()
        self.customer_email_input.setPlaceholderText("Email (optional)")
        customer_form.addRow("Customer Email:", self.customer_email_input)
        
        top_layout.addLayout(customer_form)
        
        # Barcode section
        barcode_layout = QVBoxLayout()
        
        scan_btn = QPushButton("Scan Barcode")
        scan_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        scan_btn.clicked.connect(self.scan_barcode)
        barcode_layout.addWidget(scan_btn)
        
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Or enter barcode manually")
        barcode_layout.addWidget(self.barcode_input)
        
        add_btn = QPushButton("Add Item")
        add_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        add_btn.clicked.connect(self.add_item_to_invoice)
        barcode_layout.addWidget(add_btn)
        
        top_layout.addLayout(barcode_layout)
        top_group.setLayout(top_layout)
        layout.addWidget(top_group)
        
        # Middle section - Invoice items table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(6)
        self.invoice_table.setHorizontalHeaderLabels(["ID", "Medicine", "Batch", "Price", "Qty", "Total"])
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.invoice_table)
        
        # Bottom section - Totals and actions
        bottom_group = QGroupBox("Invoice Summary")
        bottom_layout = QHBoxLayout()
        
        # Totals
        totals_layout = QFormLayout()
        
        self.subtotal_label = QLabel("₹0.00")
        totals_layout.addRow("Subtotal:", self.subtotal_label)
        
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 100)
        self.discount_input.setValue(0)
        self.discount_input.setSuffix("%")
        totals_layout.addRow("Discount:", self.discount_input)
        
        self.tax_label = QLabel("₹0.00 (5% GST)")
        totals_layout.addRow("Tax:", self.tax_label)
        
        self.total_label = QLabel("₹0.00")
        totals_layout.addRow("Total:", self.total_label)
        
        bottom_layout.addLayout(totals_layout)
        
        # Payment and actions
        action_layout = QVBoxLayout()
        
        payment_group = QGroupBox("Payment Method")
        payment_layout = QHBoxLayout()
        
        self.payment_cash = QRadioButton("Cash")
        self.payment_cash.setChecked(True)
        payment_layout.addWidget(self.payment_cash)
        
        self.payment_card = QRadioButton("Card")
        payment_layout.addWidget(self.payment_card)
        
        self.payment_upi = QRadioButton("UPI")
        payment_layout.addWidget(self.payment_upi)
        
        payment_group.setLayout(payment_layout)
        action_layout.addWidget(payment_group)
        
        # Notification options
        notify_group = QGroupBox("Notifications")
        notify_layout = QHBoxLayout()
        
        self.email_checkbox = QCheckBox("Email Receipt")
        self.email_checkbox.setChecked(True)
        notify_layout.addWidget(self.email_checkbox)
        
        self.sms_checkbox = QCheckBox("SMS Receipt")
        self.sms_checkbox.setChecked(True)
        notify_layout.addWidget(self.sms_checkbox)
        
        notify_group.setLayout(notify_layout)
        action_layout.addWidget(notify_group)
        
        # Final buttons
        clear_btn = QPushButton("Clear Invoice")
        clear_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 8px;")
        clear_btn.clicked.connect(self.clear_invoice)
        action_layout.addWidget(clear_btn)
        
        complete_btn = QPushButton("Complete Sale")
        complete_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        complete_btn.clicked.connect(self.complete_sale)
        action_layout.addWidget(complete_btn)
        
        bottom_layout.addLayout(action_layout)
        bottom_group.setLayout(bottom_layout)
        layout.addWidget(bottom_group)
        
        self.tabs.addTab(billing_tab, "Billing")
        
        # Connect customer phone lookup
        self.customer_phone_input.editingFinished.connect(self.lookup_customer)
    
    def setup_inventory_tab(self):
        inventory_tab = QWidget()
        layout = QVBoxLayout()
        inventory_tab.setLayout(layout)
        
        # Search and filter
        search_group = QGroupBox("Search & Filter")
        search_layout = QHBoxLayout()
        
        self.inventory_search = QLineEdit()
        self.inventory_search.setPlaceholderText("Search medicines...")
        self.inventory_search.textChanged.connect(self.filter_inventory)
        search_layout.addWidget(self.inventory_search)
        
        filter_btn = QPushButton("Low Stock")
        filter_btn.setStyleSheet("background-color: #e9c46a; color: black; padding: 5px;")
        filter_btn.clicked.connect(lambda: self.filter_inventory(filter_low_stock=True))
        search_layout.addWidget(filter_btn)
        
        filter_btn = QPushButton("Expired")
        filter_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 5px;")
        filter_btn.clicked.connect(self.show_expired_medicines)
        search_layout.addWidget(filter_btn)
        
        # Add Clear Filter button
        clear_filter_btn = QPushButton("Clear Filter")
        clear_filter_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 5px;")
        clear_filter_btn.clicked.connect(self.clear_inventory_filter)
        search_layout.addWidget(clear_filter_btn)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Inventory table
        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(9)
        self.inventory_table.setHorizontalHeaderLabels(["ID", "Name", "Barcode", "Batch", "Price", "Stock", "Expiry", "Category", "Actions"])
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inventory_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.inventory_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add Medicine")
        add_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        add_btn.clicked.connect(self.show_add_medicine_dialog)
        btn_layout.addWidget(add_btn)
        
        import_btn = QPushButton("Import from CSV")
        import_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        import_btn.clicked.connect(self.import_medicines)
        btn_layout.addWidget(import_btn)
        
        export_btn = QPushButton("Export to CSV")
        export_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        export_btn.clicked.connect(self.export_medicines)
        btn_layout.addWidget(export_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(inventory_tab, "Inventory")
        self.load_inventory()
    
    def setup_customers_tab(self):
        customers_tab = QWidget()
        layout = QVBoxLayout()
        customers_tab.setLayout(layout)
        
        # Search
        search_group = QGroupBox("Search Customers")
        search_layout = QHBoxLayout()
        
        self.customer_search = QLineEdit()
        self.customer_search.setPlaceholderText("Search customers...")
        self.customer_search.textChanged.connect(self.filter_customers)
        search_layout.addWidget(self.customer_search)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Customers table
        self.customers_table = QTableWidget()
        self.customers_table.setColumnCount(7)  # Added Actions column
        self.customers_table.setHorizontalHeaderLabels(["ID", "Name", "Phone", "Email", "Address", "Joined", "Actions"])
        self.customers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.customers_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.customers_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add Customer")
        add_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        add_btn.clicked.connect(self.show_add_customer_dialog)
        btn_layout.addWidget(add_btn)
        
        export_btn = QPushButton("Export to CSV")
        export_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        export_btn.clicked.connect(self.export_customers)
        btn_layout.addWidget(export_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(customers_tab, "Customers")
        self.load_customers()
    
    def setup_reports_tab(self):
        reports_tab = QWidget()
        layout = QVBoxLayout()
        reports_tab.setLayout(layout)
        
        # Date range selection
        date_group = QGroupBox("Report Period")
        date_layout = QHBoxLayout()
        
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setCalendarPopup(True)
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.start_date)
        
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.end_date)
        
        generate_btn = QPushButton("Generate Report")
        generate_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 5px;")
        generate_btn.clicked.connect(self.generate_sales_report)
        date_layout.addWidget(generate_btn)
        
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        
        # Sales report table
        self.sales_report_table = QTableWidget()
        self.sales_report_table.setColumnCount(6)
        self.sales_report_table.setHorizontalHeaderLabels(["ID", "Invoice", "Date", "Customer", "Amount", "Payment"])
        self.sales_report_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sales_report_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sales_report_table.doubleClicked.connect(self.show_sale_details)
        layout.addWidget(self.sales_report_table)
        
        # Summary
        summary_group = QGroupBox("Summary")
        summary_layout = QFormLayout()
        
        self.total_sales_label = QLabel("₹0.00")
        summary_layout.addRow("Total Sales:", self.total_sales_label)
        
        self.cash_sales_label = QLabel("₹0.00")
        summary_layout.addRow("Cash Sales:", self.cash_sales_label)
        
        self.card_sales_label = QLabel("₹0.00")
        summary_layout.addRow("Card Sales:", self.card_sales_label)
        
        self.upi_sales_label = QLabel("₹0.00")
        summary_layout.addRow("UPI Sales:", self.upi_sales_label)
        
        self.total_customers_label = QLabel("0")
        summary_layout.addRow("Total Customers:", self.total_customers_label)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        export_btn = QPushButton("Export Report")
        export_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        export_btn.clicked.connect(self.export_sales_report)
        btn_layout.addWidget(export_btn)
        
        print_btn = QPushButton("Print Report")
        print_btn.setStyleSheet("background-color: #2a6099; color: white; padding: 8px;")
        btn_layout.addWidget(print_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(reports_tab, "Reports")
        self.generate_sales_report()
    
    def setup_admin_tab(self):
        admin_tab = QWidget()
        layout = QVBoxLayout()
        admin_tab.setLayout(layout)
        
        # Settings group
        settings_group = QGroupBox("System Settings")
        settings_layout = QFormLayout()
        
        self.pharmacy_name = QLineEdit("Mahavir Medical Store")
        settings_layout.addRow("Pharmacy Name:", self.pharmacy_name)
        
        self.pharmacy_address = QTextEdit()
        self.pharmacy_address.setPlainText("123 Medical Street, City - 123456")
        settings_layout.addRow("Address:", self.pharmacy_address)
        
        self.pharmacy_phone = QLineEdit("+91 9876543210")
        settings_layout.addRow("Phone:", self.pharmacy_phone)
        
        self.pharmacy_gst = QLineEdit("22AAAAA0000A1Z5")
        settings_layout.addRow("GSTIN:", self.pharmacy_gst)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Email/SMS settings
        notify_group = QGroupBox("Notification Settings")
        notify_layout = QFormLayout()
        
        self.smtp_server = QLineEdit("smtp.gmail.com")
        notify_layout.addRow("SMTP Server:", self.smtp_server)
        
        self.smtp_port = QSpinBox()
        self.smtp_port.setValue(587)
        notify_layout.addRow("SMTP Port:", self.smtp_port)
        
        self.email_username = QLineEdit("yourpharmacy@gmail.com")
        notify_layout.addRow("Email Username:", self.email_username)
        
        self.email_password = QLineEdit()
        self.email_password.setEchoMode(QLineEdit.Password)
        notify_layout.addRow("Email Password:", self.email_password)
        
        self.twilio_sid = QLineEdit()
        notify_layout.addRow("Twilio SID:", self.twilio_sid)
        
        self.twilio_token = QLineEdit()
        notify_layout.addRow("Twilio Token:", self.twilio_token)
        
        self.twilio_number = QLineEdit()
        notify_layout.addRow("Twilio Number:", self.twilio_number)
        
        notify_group.setLayout(notify_layout)
        layout.addWidget(notify_group)
        
        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        # Database management
        db_group = QGroupBox("Database Management")
        db_layout = QHBoxLayout()
        
        backup_btn = QPushButton("Backup Database")
        backup_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        backup_btn.clicked.connect(self.backup_database)
        db_layout.addWidget(backup_btn)
        
        restore_btn = QPushButton("Restore Database")
        restore_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 8px;")
        db_layout.addWidget(restore_btn)
        
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)
        
        self.tabs.addTab(admin_tab, "Admin")
    
    def scan_barcode(self):
        barcode = self.barcode_scanner.start_scan()
        if barcode:
            self.barcode_input.setText(barcode)
            self.add_item_to_invoice()
    
    def lookup_customer(self):
        phone = self.customer_phone_input.text()
        if phone:
            customer = self.db.get_customer_by_phone(phone)
            if customer:
                self.customer_name_input.setText(customer[1])
                self.customer_email_input.setText(customer[3] if customer[3] else "")
    
    def add_item_to_invoice(self):
        barcode = self.barcode_input.text()
        if not barcode:
            QMessageBox.warning(self, "Error", "Please enter or scan a barcode")
            return
            
        medicine = self.db.get_medicine_by_barcode(barcode)
        if not medicine:
            QMessageBox.warning(self, "Error", "Medicine not found in inventory")
            return
            
        # Check if already in invoice
        for item in self.current_invoice_items:
            if item['medicine_id'] == medicine[0]:
                item['quantity'] += 1
                self.update_invoice_table()
                return
                
        # Add new item
        self.current_invoice_items.append({
            'medicine_id': medicine[0],
            'medicine_name': medicine[1],
            'name': medicine[1],
            'barcode': medicine[2],
            'batch_number': medicine[3],
            'price': medicine[4],
            'mrp': medicine[5],
            'quantity': 1,
            'expiry_date': medicine[7]
        })
        
        self.update_invoice_table()
        self.barcode_input.clear()
    
    def update_invoice_table(self):
        self.invoice_table.setRowCount(len(self.current_invoice_items))
        
        subtotal = 0
        for row, item in enumerate(self.current_invoice_items):
            self.invoice_table.setItem(row, 0, QTableWidgetItem(str(item['medicine_id'])))
            self.invoice_table.setItem(row, 1, QTableWidgetItem(item['name']))
            self.invoice_table.setItem(row, 2, QTableWidgetItem(item['batch_number']))
            self.invoice_table.setItem(row, 3, QTableWidgetItem(f"₹{item['price']:.2f}"))
            
            qty_item = QTableWidgetItem(str(item['quantity']))
            self.invoice_table.setItem(row, 4, qty_item)
            
            total = item['price'] * item['quantity']
            self.invoice_table.setItem(row, 5, QTableWidgetItem(f"₹{total:.2f}"))
        
            subtotal += total
        
        # Calculate totals
        discount_percent = self.discount_input.value()
        discount_amount = subtotal * (discount_percent / 100)
        tax_amount = (subtotal - discount_amount) * 0.05  # 5% GST
        total_amount = subtotal - discount_amount + tax_amount
        
        self.subtotal_label.setText(f"₹{subtotal:.2f}")
        self.tax_label.setText(f"₹{tax_amount:.2f} (5% GST)")
        self.total_label.setText(f"₹{total_amount:.2f}")
    
    def clear_invoice(self):
        self.current_invoice_items = []
        self.invoice_table.setRowCount(0)
        self.subtotal_label.setText("₹0.00")
        self.tax_label.setText("₹0.00 (5% GST)")
        self.total_label.setText("₹0.00")
        self.discount_input.setValue(0)
        self.customer_phone_input.clear()
        self.customer_name_input.clear()
        self.customer_email_input.clear()
        self.payment_cash.setChecked(True)
    
    def complete_sale(self):
        if not self.current_invoice_items:
            QMessageBox.warning(self, "Error", "No items in the invoice")
            return
            
        # Get customer info
        customer_name = self.customer_name_input.text()
        customer_phone = self.customer_phone_input.text()
        customer_email = self.customer_email_input.text()
        
        # Create customer if not exists
        customer_id = None
        if customer_phone:
            customer = self.db.get_customer_by_phone(customer_phone)
            if not customer:
                customer_data = {
                    'name': customer_name if customer_name else "Walk-in Customer",
                    'phone': customer_phone,
                    'email': customer_email,
                    'address': ''
                }
                customer_id = self.db.add_customer(customer_data)
            else:
                customer_id = customer[0]
        
        # Get payment method
        payment_method = "Cash"
        if self.payment_card.isChecked():
            payment_method = "Card"
        elif self.payment_upi.isChecked():
            payment_method = "UPI"
        
        # Create sale data
        subtotal = sum(item['price'] * item['quantity'] for item in self.current_invoice_items)
        discount_percent = self.discount_input.value()
        discount_amount = subtotal * (discount_percent / 100)
        tax_amount = (subtotal - discount_amount) * 0.05
        total_amount = subtotal - discount_amount + tax_amount
        
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        sale_data = {
            'invoice_number': invoice_number,
            'customer_id': customer_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_amount': total_amount,
            'discount': discount_amount,
            'tax': tax_amount,
            'payment_method': payment_method,
            'items': self.current_invoice_items
        }
        
        # Save to database
        sale_id = self.db.create_sale(sale_data)
        if not sale_id:
            QMessageBox.critical(self, "Error", "Failed to save sale to database")
            return
            
        # Generate PDF
        invoice_data = {
            'invoice_number': invoice_number,
            'date': datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
            'customer_id': customer_id,
            'customer_name': customer_name if customer_name else "Walk-in Customer",
            'customer_phone': customer_phone,
            'customer_email': customer_email,
            'subtotal': subtotal,
            'discount': discount_amount,
            'tax': tax_amount,
            'total': total_amount,
            'payment_method': payment_method,
            'items': self.current_invoice_items
        }
        
        pdf_dir = "invoices"
        if not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir)
            
        pdf_path = os.path.join(pdf_dir, f"{invoice_number}.pdf")
        PDFGenerator.generate_invoice_pdf(invoice_data, pdf_path)
        
        
        # Send notifications
        if self.email_checkbox.isChecked() and customer_email:
            subject = f"Your Invoice from Mahavir Medical Store - {invoice_number}"
            body = f"Dear {customer_name},\n\nThank you for your purchase. Please find your invoice attached.\n\nTotal Amount: ₹{total_amount:.2f}\nPayment Method: {payment_method}\n\nPlease visit us again!"
            self.notification_service.send_email(customer_email, subject, body, pdf_path)
        
        if self.sms_checkbox.isChecked() and customer_phone:
            message = f"Thank you for shopping at Mahavir Medical Store. Your invoice #{invoice_number} amount is ₹{total_amount:.2f}. Please check your email for details."
            self.notification_service.send_whatsapp_invoice(customer_phone, pdf_path)
        
        # Ask if user wants to print receipt
        reply = QMessageBox.question(self, "Print Receipt", 
                                   f"Sale completed successfully!\nInvoice Number: {invoice_number}\nTotal Amount: ₹{total_amount:.2f}\n\nDo you want to print the receipt?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        
        if reply == QMessageBox.Yes:
            self.print_receipt(pdf_path)
        
        # Clear invoice
        self.clear_invoice()
        # Refresh reports
        self.generate_sales_report()
    
    def print_receipt(self, pdf_path):
        """Open the system print dialog for the receipt (not auto-print)"""
        try:
            if os.name == 'nt':  # Windows
                # Open in default PDF viewer with print dialog
                os.startfile(pdf_path, "print")   # Opens in Adobe/Edge print dialog
            elif sys.platform == "darwin":  # macOS
                os.system(f"open -a Preview.app {pdf_path}")
            else:  # Linux
                os.system(f"xdg-open {pdf_path}")
        except Exception as e:
            QMessageBox.warning(self, "Print Error", f"Could not open print dialog: {str(e)}")
    
    def load_inventory(self):
        medicines = self.db.get_all_medicines()
        self.inventory_table.setRowCount(len(medicines))
        
        for row, medicine in enumerate(medicines):
            self.inventory_table.setItem(row, 0, QTableWidgetItem(str(medicine[0])))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(medicine[1]))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(medicine[2] if medicine[2] else ""))
            self.inventory_table.setItem(row, 3, QTableWidgetItem(medicine[3] if medicine[3] else ""))
            self.inventory_table.setItem(row, 4, QTableWidgetItem(f"₹{medicine[4]:.2f}"))
            
            qty_item = QTableWidgetItem(str(medicine[6]))
            if medicine[6] <= (medicine[10] if medicine[10] else 5):
                qty_item.setBackground(Qt.yellow)
            self.inventory_table.setItem(row, 5, qty_item)
            
            expiry_item = QTableWidgetItem(medicine[7] if medicine[7] else "")
            if medicine[7] and datetime.strptime(medicine[7], '%Y-%m-%d').date() < datetime.now().date():
                expiry_item.setBackground(Qt.red)
            self.inventory_table.setItem(row, 6, expiry_item)
            
            self.inventory_table.setItem(row, 7, QTableWidgetItem(medicine[8] if medicine[8] else ""))
            
            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 2px;")
            edit_btn.clicked.connect(lambda _, id=medicine[0]: self.edit_medicine(id))
            btn_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 2px;")
            delete_btn.clicked.connect(lambda _, id=medicine[0]: self.delete_medicine(id))
            btn_layout.addWidget(delete_btn)
            
            btn_widget.setLayout(btn_layout)
            self.inventory_table.setCellWidget(row, 8, btn_widget)
    
    def clear_inventory_filter(self):
        """Clear the inventory filter and show all medicines"""
        self.inventory_search.clear()
        self.load_inventory()
    
    def filter_inventory(self, text=None, filter_low_stock=False):
        if filter_low_stock:
            medicines = self.db.get_low_stock_medicines()
        elif text:
            medicines = [m for m in self.db.get_all_medicines() 
                        if text.lower() in m[1].lower() or 
                        (m[2] and text in m[2])]
        else:
            medicines = self.db.get_all_medicines()
            
        self.inventory_table.setRowCount(len(medicines))
        for row, medicine in enumerate(medicines):
            self.inventory_table.setItem(row, 0, QTableWidgetItem(str(medicine[0])))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(medicine[1]))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(medicine[2] if medicine[2] else ""))
            self.inventory_table.setItem(row, 3, QTableWidgetItem(medicine[3] if medicine[3] else ""))
            self.inventory_table.setItem(row, 4, QTableWidgetItem(f"₹{medicine[4]:.2f}"))
            
            qty_item = QTableWidgetItem(str(medicine[6]))
            if medicine[6] <= (medicine[10] if medicine[10] else 5):
                qty_item.setBackground(Qt.yellow)
            self.inventory_table.setItem(row, 5, qty_item)
            
            expiry_item = QTableWidgetItem(medicine[7] if medicine[7] else "")
            if medicine[7] and datetime.strptime(medicine[7], '%Y-%m-%d').date() < datetime.now().date():
                expiry_item.setBackground(Qt.red)
            self.inventory_table.setItem(row, 6, expiry_item)
            
            self.inventory_table.setItem(row, 7, QTableWidgetItem(medicine[8] if medicine[8] else ""))
    
    def show_expired_medicines(self):
        medicines = self.db.get_expired_medicines()
        self.inventory_table.setRowCount(len(medicines))
        
        for row, medicine in enumerate(medicines):
            self.inventory_table.setItem(row, 0, QTableWidgetItem(str(medicine[0])))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(medicine[1]))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(medicine[2] if medicine[2] else ""))
            self.inventory_table.setItem(row, 3, QTableWidgetItem(medicine[3] if medicine[3] else ""))
            self.inventory_table.setItem(row, 4, QTableWidgetItem(f"₹{medicine[4]:.2f}"))
            
            qty_item = QTableWidgetItem(str(medicine[6]))
            qty_item.setBackground(Qt.red)
            self.inventory_table.setItem(row, 5, qty_item)
            
            expiry_item = QTableWidgetItem(medicine[7] if medicine[7] else "")
            expiry_item.setBackground(Qt.red)
            self.inventory_table.setItem(row, 6, expiry_item)
            
            self.inventory_table.setItem(row, 7, QTableWidgetItem(medicine[8] if medicine[8] else ""))
    
    def show_add_medicine_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Medicine")
        dialog.setFixedSize(400, 500)
        
        layout = QFormLayout()
        
        self.med_name = QLineEdit()
        layout.addRow("Name*:", self.med_name)
        
        self.med_barcode = QLineEdit()
        layout.addRow("Barcode:", self.med_barcode)
        
        self.med_batch = QLineEdit()
        layout.addRow("Batch Number:", self.med_batch)
        
        self.med_price = QDoubleSpinBox()
        self.med_price.setRange(0, 99999)
        self.med_price.setPrefix("₹")
        layout.addRow("Price*:", self.med_price)
        
        self.med_mrp = QDoubleSpinBox()
        self.med_mrp.setRange(0, 99999)
        self.med_mrp.setPrefix("₹")
        layout.addRow("MRP*:", self.med_mrp)
        
        self.med_qty = QSpinBox()
        self.med_qty.setRange(0, 9999)
        layout.addRow("Quantity*:", self.med_qty)
        
        self.med_expiry = QDateEdit()
        self.med_expiry.setDate(QDate.currentDate().addYears(1))
        self.med_expiry.setCalendarPopup(True)
        layout.addRow("Expiry Date:", self.med_expiry)
        
        self.med_manufacturer = QLineEdit()
        layout.addRow("Manufacturer:", self.med_manufacturer)
        
        self.med_category = QComboBox()
        self.med_category.addItems(["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Other"])
        layout.addRow("Category:", self.med_category)
        
        self.med_min_stock = QSpinBox()
        self.med_min_stock.setRange(1, 999)
        self.med_min_stock.setValue(5)
        layout.addRow("Min Stock Level:", self.med_min_stock)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white;")
        save_btn.clicked.connect(lambda: self.save_medicine(dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e76f51; color: white;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def save_medicine(self, dialog):
        if not self.med_name.text() or self.med_price.value() == 0 or self.med_mrp.value() == 0:
            QMessageBox.warning(self, "Error", "Please fill all required fields (*)")
            return
            
        medicine_data = {
            'name': self.med_name.text(),
            'barcode': self.med_barcode.text(),
            'batch_number': self.med_batch.text(),
            'price': self.med_price.value(),
            'mrp': self.med_mrp.value(),
            'quantity': self.med_qty.value(),
            'expiry_date': self.med_expiry.date().toString('yyyy-MM-dd'),
            'manufacturer': self.med_manufacturer.text(),
            'category': self.med_category.currentText(),
            'min_stock_level': self.med_min_stock.value()
        }
        
        medicine_id = self.db.add_medicine(medicine_data)
        if medicine_id:
            QMessageBox.information(self, "Success", "Medicine added successfully!")
            self.load_inventory()
            dialog.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to add medicine to database")
    
    def edit_medicine(self, medicine_id):
        medicine = None
        for m in self.db.get_all_medicines():
            if m[0] == medicine_id:
                medicine = m
                break
                
        if not medicine:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Medicine")
        dialog.setFixedSize(400, 500)
        
        layout = QFormLayout()
        
        self.edit_med_name = QLineEdit(medicine[1])
        layout.addRow("Name*:", self.edit_med_name)
        
        self.edit_med_barcode = QLineEdit(medicine[2] if medicine[2] else "")
        layout.addRow("Barcode:", self.edit_med_barcode)
        
        self.edit_med_batch = QLineEdit(medicine[3] if medicine[3] else "")
        layout.addRow("Batch Number:", self.edit_med_batch)
        
        self.edit_med_price = QDoubleSpinBox()
        self.edit_med_price.setRange(0, 99999)
        self.edit_med_price.setPrefix("₹")
        self.edit_med_price.setValue(medicine[4])
        layout.addRow("Price*:", self.edit_med_price)
        
        self.edit_med_mrp = QDoubleSpinBox()
        self.edit_med_mrp.setRange(0, 99999)
        self.edit_med_mrp.setPrefix("₹")
        self.edit_med_mrp.setValue(medicine[5])
        layout.addRow("MRP*:", self.edit_med_mrp)
        
        self.edit_med_qty = QSpinBox()
        self.edit_med_qty.setRange(0, 9999)
        self.edit_med_qty.setValue(medicine[6])
        layout.addRow("Quantity*:", self.edit_med_qty)
        
        self.edit_med_expiry = QDateEdit()
        if medicine[7]:
            self.edit_med_expiry.setDate(QDate.fromString(medicine[7], 'yyyy-MM-dd'))
        else:
            self.edit_med_expiry.setDate(QDate.currentDate().addYears(1))
        self.edit_med_expiry.setCalendarPopup(True)
        layout.addRow("Expiry Date:", self.edit_med_expiry)
        
        self.edit_med_manufacturer = QLineEdit(medicine[8] if medicine[8] else "")
        layout.addRow("Manufacturer:", self.edit_med_manufacturer)
        
        self.edit_med_category = QComboBox()
        self.edit_med_category.addItems(["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Other"])
        if medicine[9]:
            index = self.edit_med_category.findText(medicine[9])
            if index >= 0:
                self.edit_med_category.setCurrentIndex(index)
        layout.addRow("Category:", self.edit_med_category)
        
        self.edit_med_min_stock = QSpinBox()
        self.edit_med_min_stock.setRange(1, 999)
        self.edit_med_min_stock.setValue(medicine[10] if medicine[10] else 5)
        layout.addRow("Min Stock Level:", self.edit_med_min_stock)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white;")
        save_btn.clicked.connect(lambda: self.update_medicine_data(medicine_id, dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e76f51; color: white;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def update_medicine_data(self, medicine_id, dialog):
        if not self.edit_med_name.text() or self.edit_med_price.value() == 0 or self.edit_med_mrp.value() == 0:
            QMessageBox.warning(self, "Error", "Please fill all required fields (*)")
            return
            
        medicine_data = {
            'name': self.edit_med_name.text(),
            'barcode': self.edit_med_barcode.text(),
            'batch_number': self.edit_med_batch.text(),
            'price': self.edit_med_price.value(),
            'mrp': self.edit_med_mrp.value(),
            'quantity': self.edit_med_qty.value(),
            'expiry_date': self.edit_med_expiry.date().toString('yyyy-MM-dd'),
            'manufacturer': self.edit_med_manufacturer.text(),
            'category': self.edit_med_category.currentText(),
            'min_stock_level': self.edit_med_min_stock.value()
        }
        
        if self.db.update_medicine(medicine_id, medicine_data):
            QMessageBox.information(self, "Success", "Medicine updated successfully!")
            self.load_inventory()
            dialog.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to update medicine in database")
    
    def delete_medicine(self, medicine_id):
        reply = QMessageBox.question(self, 'Confirm Delete', 
                                   'Are you sure you want to delete this medicine?',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            conn = self.db._get_connection()
            c = conn.cursor()
            try:
                c.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))
                conn.commit()
                self.load_inventory()
                QMessageBox.information(self, "Success", "Medicine deleted successfully!")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to delete medicine: {e}")
            finally:
                conn.close()
    
    def import_medicines(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Medicines", "", 
                                                  "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    medicine_data = {
                        'name': row.get('name', ''),
                        'barcode': row.get('barcode', ''),
                        'batch_number': row.get('batch_number', ''),
                        'price': float(row.get('price', 0)),
                        'mrp': float(row.get('mrp', 0)),
                        'quantity': int(row.get('quantity', 0)),
                        'expiry_date': row.get('expiry_date', ''),
                        'manufacturer': row.get('manufacturer', ''),
                        'category': row.get('category', ''),
                        'min_stock_level': int(row.get('min_stock_level', 5))
                    }
                    self.db.add_medicine(medicine_data)
            
            self.load_inventory()
            QMessageBox.information(self, "Success", "Medicines imported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import medicines: {e}")
    
    def export_medicines(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Medicines", "medicines_export.csv", 
                                                  "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
            
        try:
            medicines = self.db.get_all_medicines()
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'name', 'barcode', 'batch_number', 'price', 'mrp', 
                                'quantity', 'expiry_date', 'manufacturer', 'category', 'min_stock_level'])
                for med in medicines:
                    writer.writerow(med)
            
            QMessageBox.information(self, "Success", "Medicines exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export medicines: {e}")
    
    def load_customers(self):
        customers = self.db.get_all_customers()
        self.customers_table.setRowCount(len(customers))
        
        for row, customer in enumerate(customers):
            self.customers_table.setItem(row, 0, QTableWidgetItem(str(customer[0])))
            self.customers_table.setItem(row, 1, QTableWidgetItem(customer[1]))
            self.customers_table.setItem(row, 2, QTableWidgetItem(customer[2] if customer[2] else ""))
            self.customers_table.setItem(row, 3, QTableWidgetItem(customer[3] if customer[3] else ""))
            self.customers_table.setItem(row, 4, QTableWidgetItem(customer[4] if customer[4] else ""))
            self.customers_table.setItem(row, 5, QTableWidgetItem(customer[5] if customer[5] else ""))
            
            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 2px;")
            edit_btn.clicked.connect(lambda _, id=customer[0]: self.edit_customer(id))
            btn_layout.addWidget(edit_btn)
            
            btn_widget.setLayout(btn_layout)
            self.customers_table.setCellWidget(row, 6, btn_widget)
    
    def filter_customers(self):
        text = self.customer_search.text()
        customers = [c for c in self.db.get_all_customers() 
                    if text.lower() in c[1].lower() or 
                    (c[2] and text in c[2])]
                    
        self.customers_table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            self.customers_table.setItem(row, 0, QTableWidgetItem(str(customer[0])))
            self.customers_table.setItem(row, 1, QTableWidgetItem(customer[1]))
            self.customers_table.setItem(row, 2, QTableWidgetItem(customer[2] if customer[2] else ""))
            self.customers_table.setItem(row, 3, QTableWidgetItem(customer[3] if customer[3] else ""))
            self.customers_table.setItem(row, 4, QTableWidgetItem(customer[4] if customer[4] else ""))
            self.customers_table.setItem(row, 5, QTableWidgetItem(customer[5] if customer[5] else ""))
            
            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 2px;")
            edit_btn.clicked.connect(lambda _, id=customer[0]: self.edit_customer(id))
            btn_layout.addWidget(edit_btn)
            
            btn_widget.setLayout(btn_layout)
            self.customers_table.setCellWidget(row, 6, btn_widget)
    
    def show_add_customer_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Customer")
        dialog.setFixedSize(400, 300)
        
        layout = QFormLayout()
        
        self.cust_name = QLineEdit()
        layout.addRow("Name*:", self.cust_name)
        
        self.cust_phone = QLineEdit()
        layout.addRow("Phone*:", self.cust_phone)
        
        self.cust_email = QLineEdit()
        layout.addRow("Email:", self.cust_email)
        
        self.cust_address = QTextEdit()
        self.cust_address.setFixedHeight(80)
        layout.addRow("Address:", self.cust_address)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white;")
        save_btn.clicked.connect(lambda: self.save_customer(dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e76f51; color: white;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def edit_customer(self, customer_id):
        customer = self.db.get_customer_by_id(customer_id)
        if not customer:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Customer")
        dialog.setFixedSize(400, 300)
        
        layout = QFormLayout()
        
        self.edit_cust_name = QLineEdit(customer[1])
        layout.addRow("Name*:", self.edit_cust_name)
        
        self.edit_cust_phone = QLineEdit(customer[2] if customer[2] else "")
        layout.addRow("Phone*:", self.edit_cust_phone)
        
        self.edit_cust_email = QLineEdit(customer[3] if customer[3] else "")
        layout.addRow("Email:", self.edit_cust_email)
        
        self.edit_cust_address = QTextEdit()
        self.edit_cust_address.setFixedHeight(80)
        self.edit_cust_address.setPlainText(customer[4] if customer[4] else "")
        layout.addRow("Address:", self.edit_cust_address)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white;")
        save_btn.clicked.connect(lambda: self.update_customer_data(customer_id, dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e76f51; color: white;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def update_customer_data(self, customer_id, dialog):
        if not self.edit_cust_name.text() or not self.edit_cust_phone.text():
            QMessageBox.warning(self, "Error", "Please fill all required fields (*)")
            return
            
        customer_data = {
            'name': self.edit_cust_name.text(),
            'phone': self.edit_cust_phone.text(),
            'email': self.edit_cust_email.text(),
            'address': self.edit_cust_address.toPlainText()
        }
        
        if self.db.update_customer(customer_id, customer_data):
            QMessageBox.information(self, "Success", "Customer updated successfully!")
            self.load_customers()
            dialog.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to update customer in database")
    
    def save_customer(self, dialog):
        if not self.cust_name.text() or not self.cust_phone.text():
            QMessageBox.warning(self, "Error", "Please fill all required fields (*)")
            return
            
        customer_data = {
            'name': self.cust_name.text(),
            'phone': self.cust_phone.text(),
            'email': self.cust_email.text(),
            'address': self.cust_address.toPlainText()
        }
        
        customer_id = self.db.add_customer(customer_data)
        if customer_id:
            QMessageBox.information(self, "Success", "Customer added successfully!")
            self.load_customers()
            dialog.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to add customer to database")
    
    def export_customers(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Customers", "customers_export.csv", 
                                                  "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
            
        try:
            customers = self.db.get_all_customers()
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'name', 'phone', 'email', 'address', 'created_date'])
                for cust in customers:
                    writer.writerow(cust)
            
            QMessageBox.information(self, "Success", "Customers exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export customers: {e}")
    
    def generate_sales_report(self):
        start_date = self.start_date.date().toString('yyyy-MM-dd')
        end_date = self.end_date.date().toString('yyyy-MM-dd')
        
        sales = self.db.get_sales_report(start_date, end_date)
        self.sales_report_table.setRowCount(len(sales))
        
        total_sales = 0
        cash_sales = 0
        card_sales = 0
        upi_sales = 0
        
        for row, sale in enumerate(sales):
            self.sales_report_table.setItem(row, 0, QTableWidgetItem(str(sale[0])))
            self.sales_report_table.setItem(row, 1, QTableWidgetItem(sale[1]))
            self.sales_report_table.setItem(row, 2, QTableWidgetItem(sale[2]))
            self.sales_report_table.setItem(row, 3, QTableWidgetItem(sale[3] if sale[3] else "Walk-in"))
            self.sales_report_table.setItem(row, 4, QTableWidgetItem(f"₹{sale[4]:.2f}"))
            self.sales_report_table.setItem(row, 5, QTableWidgetItem(sale[5]))
            
            total_sales += sale[4]
            if sale[5] == "Cash":
                cash_sales += sale[4]
            elif sale[5] == "Card":
                card_sales += sale[4]
            elif sale[5] == "UPI":
                upi_sales += sale[4]
        
        # Update summary
        self.total_sales_label.setText(f"₹{total_sales:.2f}")
        self.cash_sales_label.setText(f"₹{cash_sales:.2f}")
        self.card_sales_label.setText(f"₹{card_sales:.2f}")
        self.upi_sales_label.setText(f"₹{upi_sales:.2f}")
        
        # Count unique customers
        customer_count = len(set(s[3] for s in sales if s[3]))
        self.total_customers_label.setText(str(customer_count))
    
    def show_sale_details(self, index):
        sale_id = int(self.sales_report_table.item(index.row(), 0).text())
        sale_details = self.db.get_sale_details(sale_id)
        
        if not sale_details:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Sale Details - Invoice #{sale_details['header'][1]}")
        dialog.setFixedSize(600, 500)
        
        layout = QVBoxLayout()
        
        # Header info
        header_group = QGroupBox("Invoice Information")
        header_layout = QFormLayout()
        
        header_layout.addRow("Invoice Number:", QLabel(sale_details['header'][1]))
        header_layout.addRow("Date:", QLabel(sale_details['header'][3]))
        header_layout.addRow("Customer:", QLabel(sale_details['header'][8] if sale_details['header'][8] else "Walk-in Customer"))
        header_layout.addRow("Payment Method:", QLabel(sale_details['header'][7]))
        header_layout.addRow("Total Amount:", QLabel(f"₹{sale_details['header'][4]:.2f}"))
        
        header_group.setLayout(header_layout)
        layout.addWidget(header_group)
        
        # Items table
        items_table = QTableWidget()
        items_table.setColumnCount(5)
        items_table.setHorizontalHeaderLabels(["Medicine", "Batch", "Price", "Qty", "Total"])
        items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        items_table.setRowCount(len(sale_details['items']))
        for row, item in enumerate(sale_details['items']):
            items_table.setItem(row, 0, QTableWidgetItem(item[5]))
            items_table.setItem(row, 1, QTableWidgetItem(item[6] if item[6] else ""))
            items_table.setItem(row, 2, QTableWidgetItem(f"₹{item[4]:.2f}"))
            items_table.setItem(row, 3, QTableWidgetItem(str(item[3])))
            items_table.setItem(row, 4, QTableWidgetItem(f"₹{item[3]*item[4]:.2f}"))
        
        layout.addWidget(items_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        print_btn = QPushButton("Print Invoice")
        print_btn.setStyleSheet("background-color: #3a7ca5; color: white;")
        btn_layout.addWidget(print_btn)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background-color: #e76f51; color: white;")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def export_sales_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Sales Report", "sales_report.csv", 
                                                  "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
            
        try:
            start_date = self.start_date.date().toString('yyyy-MM-dd')
            end_date = self.end_date.date().toString('yyyy-MM-dd')
            sales = self.db.get_sales_report(start_date, end_date)
            
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'invoice_number', 'date', 'customer_name', 'total_amount', 'payment_method'])
                for sale in sales:
                    writer.writerow(sale)
            
            QMessageBox.information(self, "Success", "Sales report exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export sales report: {e}")
    
    def backup_database(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Backup Database", "pharmacy_backup.db", 
                                                  "Database Files (*.db);;All Files (*)")
        if not file_path:
            return
            
        try:
            import shutil
            shutil.copyfile('pharmacy.db', file_path)
            QMessageBox.information(self, "Success", "Database backup created successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create backup: {e}")
    
    def export_reports(self):
        options = ["Sales Report", "Inventory Report", "Customer List"]
        item, ok = QInputDialog.getItem(self, "Export Report", "Select report to export:", options, 0, False)
        
        if ok and item:
            if item == "Sales Report":
                self.export_sales_report()
            elif item == "Inventory Report":
                self.export_medicines()
            elif item == "Customer List":
                self.export_customers()
    
    def save_settings(self):
        # In a real application, you would save these to a config file
        QMessageBox.information(self, "Settings Saved", "System settings have been saved")
    
    def check_alerts(self):
        # Check low stock
        low_stock = self.db.get_low_stock_medicines()
        if low_stock:
            msg = "Low stock alert for the following medicines:\n\n"
            for med in low_stock:
                msg += f"{med[1]} (Current: {med[6]}, Min: {med[10] if med[10] else 5})\n"
            
            QMessageBox.warning(self, "Low Stock Alert", msg)
        
        # Check expired medicines
        expired = self.db.get_expired_medicines()
        if expired:
            msg = "Expired medicines alert:\n\n"
            for med in expired:
                msg += f"{med[1]} (Expired on: {med[7]})\n"
            
            QMessageBox.critical(self, "Expired Medicines Alert", msg)
    
    def show_about(self):
        about_text = """<h2>Mahavir Medical Store Billing System</h2>
        <p>Version 1.0</p>
        <p>Developed by Your Name</p>
        <p>Contact: your.email@example.com</p>
        <p>© 2023 All Rights Reserved</p>"""
        
        QMessageBox.about(self, "About", about_text)

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Show login window
    login_window = LoginWindow(on_login_success=lambda user: MainWindow(user).show())
    login_window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
    
    def load_inventory(self):
        medicines = self.db.get_all_medicines()
        self.inventory_table.setRowCount(len(medicines))
        
        for row, medicine in enumerate(medicines):
            self.inventory_table.setItem(row, 0, QTableWidgetItem(str(medicine[0])))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(medicine[1]))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(medicine[2] if medicine[2] else ""))
            self.inventory_table.setItem(row, 3, QTableWidgetItem(medicine[3] if medicine[3] else ""))
            self.inventory_table.setItem(row, 4, QTableWidgetItem(f"₹{medicine[4]:.2f}"))
            
            qty_item = QTableWidgetItem(str(medicine[6]))
            if medicine[6] <= (medicine[10] if medicine[10] else 5):
                qty_item.setBackground(Qt.yellow)
            self.inventory_table.setItem(row, 5, qty_item)
            
            expiry_item = QTableWidgetItem(medicine[7] if medicine[7] else "")
            if medicine[7] and datetime.strptime(medicine[7], '%Y-%m-%d').date() < datetime.now().date():
                expiry_item.setBackground(Qt.red)
            self.inventory_table.setItem(row, 6, expiry_item)
            
            self.inventory_table.setItem(row, 7, QTableWidgetItem(medicine[8] if medicine[8] else ""))
            
            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 2px;")
            edit_btn.clicked.connect(lambda _, id=medicine[0]: self.edit_medicine(id))
            btn_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 2px;")
            delete_btn.clicked.connect(lambda _, id=medicine[0]: self.delete_medicine(id))
            btn_layout.addWidget(delete_btn)
            
            btn_widget.setLayout(btn_layout)
            self.inventory_table.setCellWidget(row, 8, btn_widget)
    
    def clear_inventory_filter(self):
        """Clear the inventory filter and show all medicines"""
        self.inventory_search.clear()
        self.load_inventory()
    
    def filter_inventory(self, text=None, filter_low_stock=False):
        if filter_low_stock:
            medicines = self.db.get_low_stock_medicines()
        elif text:
            medicines = [m for m in self.db.get_all_medicines() 
                        if text.lower() in m[1].lower() or 
                        (m[2] and text in m[2])]
        else:
            medicines = self.db.get_all_medicines()
            
        self.inventory_table.setRowCount(len(medicines))
        for row, medicine in enumerate(medicines):
            self.inventory_table.setItem(row, 0, QTableWidgetItem(str(medicine[0])))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(medicine[1]))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(medicine[2] if medicine[2] else ""))
            self.inventory_table.setItem(row, 3, QTableWidgetItem(medicine[3] if medicine[3] else ""))
            self.inventory_table.setItem(row, 4, QTableWidgetItem(f"₹{medicine[4]:.2f}"))
            
            qty_item = QTableWidgetItem(str(medicine[6]))
            if medicine[6] <= (medicine[10] if medicine[10] else 5):
                qty_item.setBackground(Qt.yellow)
            self.inventory_table.setItem(row, 5, qty_item)
            
            expiry_item = QTableWidgetItem(medicine[7] if medicine[7] else "")
            if medicine[7] and datetime.strptime(medicine[7], '%Y-%m-%d').date() < datetime.now().date():
                expiry_item.setBackground(Qt.red)
            self.inventory_table.setItem(row, 6, expiry_item)
            
            self.inventory_table.setItem(row, 7, QTableWidgetItem(medicine[8] if medicine[8] else ""))
    
    def show_expired_medicines(self):
        medicines = self.db.get_expired_medicines()
        self.inventory_table.setRowCount(len(medicines))
        
        for row, medicine in enumerate(medicines):
            self.inventory_table.setItem(row, 0, QTableWidgetItem(str(medicine[0])))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(medicine[1]))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(medicine[2] if medicine[2] else ""))
            self.inventory_table.setItem(row, 3, QTableWidgetItem(medicine[3] if medicine[3] else ""))
            self.inventory_table.setItem(row, 4, QTableWidgetItem(f"₹{medicine[4]:.2f}"))
            
            qty_item = QTableWidgetItem(str(medicine[6]))
            qty_item.setBackground(Qt.red)
            self.inventory_table.setItem(row, 5, qty_item)
            
            expiry_item = QTableWidgetItem(medicine[7] if medicine[7] else "")
            expiry_item.setBackground(Qt.red)
            self.inventory_table.setItem(row, 6, expiry_item)
            
            self.inventory_table.setItem(row, 7, QTableWidgetItem(medicine[8] if medicine[8] else ""))
    
    def show_add_medicine_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Medicine")
        dialog.setFixedSize(400, 500)
        
        layout = QFormLayout()
        
        self.med_name = QLineEdit()
        layout.addRow("Name*:", self.med_name)
        
        self.med_barcode = QLineEdit()
        layout.addRow("Barcode:", self.med_barcode)
        
        self.med_batch = QLineEdit()
        layout.addRow("Batch Number:", self.med_batch)
        
        self.med_price = QDoubleSpinBox()
        self.med_price.setRange(0, 99999)
        self.med_price.setPrefix("₹")
        layout.addRow("Price*:", self.med_price)
        
        self.med_mrp = QDoubleSpinBox()
        self.med_mrp.setRange(0, 99999)
        self.med_mrp.setPrefix("₹")
        layout.addRow("MRP*:", self.med_mrp)
        
        self.med_qty = QSpinBox()
        self.med_qty.setRange(0, 9999)
        layout.addRow("Quantity*:", self.med_qty)
        
        self.med_expiry = QDateEdit()
        self.med_expiry.setDate(QDate.currentDate().addYears(1))
        self.med_expiry.setCalendarPopup(True)
        layout.addRow("Expiry Date:", self.med_expiry)
        
        self.med_manufacturer = QLineEdit()
        layout.addRow("Manufacturer:", self.med_manufacturer)
        
        self.med_category = QComboBox()
        self.med_category.addItems(["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Other"])
        layout.addRow("Category:", self.med_category)
        
        self.med_min_stock = QSpinBox()
        self.med_min_stock.setRange(1, 999)
        self.med_min_stock.setValue(5)
        layout.addRow("Min Stock Level:", self.med_min_stock)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white;")
        save_btn.clicked.connect(lambda: self.save_medicine(dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e76f51; color: white;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def save_medicine(self, dialog):
        if not self.med_name.text() or self.med_price.value() == 0 or self.med_mrp.value() == 0:
            QMessageBox.warning(self, "Error", "Please fill all required fields (*)")
            return
            
        medicine_data = {
            'name': self.med_name.text(),
            'barcode': self.med_barcode.text(),
            'batch_number': self.med_batch.text(),
            'price': self.med_price.value(),
            'mrp': self.med_mrp.value(),
            'quantity': self.med_qty.value(),
            'expiry_date': self.med_expiry.date().toString('yyyy-MM-dd'),
            'manufacturer': self.med_manufacturer.text(),
            'category': self.med_category.currentText(),
            'min_stock_level': self.med_min_stock.value()
        }
        
        medicine_id = self.db.add_medicine(medicine_data)
        if medicine_id:
            QMessageBox.information(self, "Success", "Medicine added successfully!")
            self.load_inventory()
            dialog.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to add medicine to database")
    
    def edit_medicine(self, medicine_id):
        medicine = None
        for m in self.db.get_all_medicines():
            if m[0] == medicine_id:
                medicine = m
                break
                
        if not medicine:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Medicine")
        dialog.setFixedSize(400, 500)
        
        layout = QFormLayout()
        
        self.edit_med_name = QLineEdit(medicine[1])
        layout.addRow("Name*:", self.edit_med_name)
        
        self.edit_med_barcode = QLineEdit(medicine[2] if medicine[2] else "")
        layout.addRow("Barcode:", self.edit_med_barcode)
        
        self.edit_med_batch = QLineEdit(medicine[3] if medicine[3] else "")
        layout.addRow("Batch Number:", self.edit_med_batch)
        
        self.edit_med_price = QDoubleSpinBox()
        self.edit_med_price.setRange(0, 99999)
        self.edit_med_price.setPrefix("₹")
        self.edit_med_price.setValue(medicine[4])
        layout.addRow("Price*:", self.edit_med_price)
        
        self.edit_med_mrp = QDoubleSpinBox()
        self.edit_med_mrp.setRange(0, 99999)
        self.edit_med_mrp.setPrefix("₹")
        self.edit_med_mrp.setValue(medicine[5])
        layout.addRow("MRP*:", self.edit_med_mrp)
        
        self.edit_med_qty = QSpinBox()
        self.edit_med_qty.setRange(0, 9999)
        self.edit_med_qty.setValue(medicine[6])
        layout.addRow("Quantity*:", self.edit_med_qty)
        
        self.edit_med_expiry = QDateEdit()
        if medicine[7]:
            self.edit_med_expiry.setDate(QDate.fromString(medicine[7], 'yyyy-MM-dd'))
        else:
            self.edit_med_expiry.setDate(QDate.currentDate().addYears(1))
        self.edit_med_expiry.setCalendarPopup(True)
        layout.addRow("Expiry Date:", self.edit_med_expiry)
        
        self.edit_med_manufacturer = QLineEdit(medicine[8] if medicine[8] else "")
        layout.addRow("Manufacturer:", self.edit_med_manufacturer)
        
        self.edit_med_category = QComboBox()
        self.edit_med_category.addItems(["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Other"])
        if medicine[9]:
            index = self.edit_med_category.findText(medicine[9])
            if index >= 0:
                self.edit_med_category.setCurrentIndex(index)
        layout.addRow("Category:", self.edit_med_category)
        
        self.edit_med_min_stock = QSpinBox()
        self.edit_med_min_stock.setRange(1, 999)
        self.edit_med_min_stock.setValue(medicine[10] if medicine[10] else 5)
        layout.addRow("Min Stock Level:", self.edit_med_min_stock)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white;")
        save_btn.clicked.connect(lambda: self.update_medicine_data(medicine_id, dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e76f51; color: white;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def update_medicine_data(self, medicine_id, dialog):
        if not self.edit_med_name.text() or self.edit_med_price.value() == 0 or self.edit_med_mrp.value() == 0:
            QMessageBox.warning(self, "Error", "Please fill all required fields (*)")
            return
            
        medicine_data = {
            'name': self.edit_med_name.text(),
            'barcode': self.edit_med_barcode.text(),
            'batch_number': self.edit_med_batch.text(),
            'price': self.edit_med_price.value(),
            'mrp': self.edit_med_mrp.value(),
            'quantity': self.edit_med_qty.value(),
            'expiry_date': self.edit_med_expiry.date().toString('yyyy-MM-dd'),
            'manufacturer': self.edit_med_manufacturer.text(),
            'category': self.edit_med_category.currentText(),
            'min_stock_level': self.edit_med_min_stock.value()
        }
        
        if self.db.update_medicine(medicine_id, medicine_data):
            QMessageBox.information(self, "Success", "Medicine updated successfully!")
            self.load_inventory()
            dialog.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to update medicine in database")
    
    def delete_medicine(self, medicine_id):
        reply = QMessageBox.question(self, 'Confirm Delete', 
                                   'Are you sure you want to delete this medicine?',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            conn = self.db._get_connection()
            c = conn.cursor()
            try:
                c.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))
                conn.commit()
                self.load_inventory()
                QMessageBox.information(self, "Success", "Medicine deleted successfully!")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to delete medicine: {e}")
            finally:
                conn.close()
    
    def import_medicines(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Medicines", "", 
                                                  "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    medicine_data = {
                        'name': row.get('name', ''),
                        'barcode': row.get('barcode', ''),
                        'batch_number': row.get('batch_number', ''),
                        'price': float(row.get('price', 0)),
                        'mrp': float(row.get('mrp', 0)),
                        'quantity': int(row.get('quantity', 0)),
                        'expiry_date': row.get('expiry_date', ''),
                        'manufacturer': row.get('manufacturer', ''),
                        'category': row.get('category', ''),
                        'min_stock_level': int(row.get('min_stock_level', 5))
                    }
                    self.db.add_medicine(medicine_data)
            
            self.load_inventory()
            QMessageBox.information(self, "Success", "Medicines imported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import medicines: {e}")
    
    def export_medicines(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Medicines", "medicines_export.csv", 
                                                  "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
            
        try:
            medicines = self.db.get_all_medicines()
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'name', 'barcode', 'batch_number', 'price', 'mrp', 
                                'quantity', 'expiry_date', 'manufacturer', 'category', 'min_stock_level'])
                for med in medicines:
                    writer.writerow(med)
            
            QMessageBox.information(self, "Success", "Medicines exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export medicines: {e}")
    
    def load_customers(self):
        customers = self.db.get_all_customers()
        self.customers_table.setRowCount(len(customers))
        
        for row, customer in enumerate(customers):
            self.customers_table.setItem(row, 0, QTableWidgetItem(str(customer[0])))
            self.customers_table.setItem(row, 1, QTableWidgetItem(customer[1]))
            self.customers_table.setItem(row, 2, QTableWidgetItem(customer[2] if customer[2] else ""))
            self.customers_table.setItem(row, 3, QTableWidgetItem(customer[3] if customer[3] else ""))
            self.customers_table.setItem(row, 4, QTableWidgetItem(customer[4] if customer[4] else ""))
            self.customers_table.setItem(row, 5, QTableWidgetItem(customer[5] if customer[5] else ""))
            
            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 2px;")
            edit_btn.clicked.connect(lambda _, id=customer[0]: self.edit_customer(id))
            btn_layout.addWidget(edit_btn)
            
            btn_widget.setLayout(btn_layout)
            self.customers_table.setCellWidget(row, 6, btn_widget)
    
    def filter_customers(self):
        text = self.customer_search.text()
        customers = [c for c in self.db.get_all_customers() 
                    if text.lower() in c[1].lower() or 
                    (c[2] and text in c[2])]
                    
        self.customers_table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            self.customers_table.setItem(row, 0, QTableWidgetItem(str(customer[0])))
            self.customers_table.setItem(row, 1, QTableWidgetItem(customer[1]))
            self.customers_table.setItem(row, 2, QTableWidgetItem(customer[2] if customer[2] else ""))
            self.customers_table.setItem(row, 3, QTableWidgetItem(customer[3] if customer[3] else ""))
            self.customers_table.setItem(row, 4, QTableWidgetItem(customer[4] if customer[4] else ""))
            self.customers_table.setItem(row, 5, QTableWidgetItem(customer[5] if customer[5] else ""))
            
            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 2px;")
            edit_btn.clicked.connect(lambda _, id=customer[0]: self.edit_customer(id))
            btn_layout.addWidget(edit_btn)
            
            btn_widget.setLayout(btn_layout)
            self.customers_table.setCellWidget(row, 6, btn_widget)
    
    def show_add_customer_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add New Customer")
        dialog.setFixedSize(400, 300)
        
        layout = QFormLayout()
        
        self.cust_name = QLineEdit()
        layout.addRow("Name*:", self.cust_name)
        
        self.cust_phone = QLineEdit()
        layout.addRow("Phone*:", self.cust_phone)
        
        self.cust_email = QLineEdit()
        layout.addRow("Email:", self.cust_email)
        
        self.cust_address = QTextEdit()
        self.cust_address.setFixedHeight(80)
        layout.addRow("Address:", self.cust_address)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white;")
        save_btn.clicked.connect(lambda: self.save_customer(dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e76f51; color: white;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def edit_customer(self, customer_id):
        customer = self.db.get_customer_by_id(customer_id)
        if not customer:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Customer")
        dialog.setFixedSize(400, 300)
        
        layout = QFormLayout()
        
        self.edit_cust_name = QLineEdit(customer[1])
        layout.addRow("Name*:", self.edit_cust_name)
        
        self.edit_cust_phone = QLineEdit(customer[2] if customer[2] else "")
        layout.addRow("Phone*:", self.edit_cust_phone)
        
        self.edit_cust_email = QLineEdit(customer[3] if customer[3] else "")
        layout.addRow("Email:", self.edit_cust_email)
        
        self.edit_cust_address = QTextEdit()
        self.edit_cust_address.setFixedHeight(80)
        self.edit_cust_address.setPlainText(customer[4] if customer[4] else "")
        layout.addRow("Address:", self.edit_cust_address)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2a9d8f; color: white;")
        save_btn.clicked.connect(lambda: self.update_customer_data(customer_id, dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e76f51; color: white;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def update_customer_data(self, customer_id, dialog):
        if not self.edit_cust_name.text() or not self.edit_cust_phone.text():
            QMessageBox.warning(self, "Error", "Please fill all required fields (*)")
            return
            
        customer_data = {
            'name': self.edit_cust_name.text(),
            'phone': self.edit_cust_phone.text(),
            'email': self.edit_cust_email.text(),
            'address': self.edit_cust_address.toPlainText()
        }
        
        if self.db.update_customer(customer_id, customer_data):
            QMessageBox.information(self, "Success", "Customer updated successfully!")
            self.load_customers()
            dialog.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to update customer in database")
    
    def save_customer(self, dialog):
        if not self.cust_name.text() or not self.cust_phone.text():
            QMessageBox.warning(self, "Error", "Please fill all required fields (*)")
            return
            
        customer_data = {
            'name': self.cust_name.text(),
            'phone': self.cust_phone.text(),
            'email': self.cust_email.text(),
            'address': self.cust_address.toPlainText()
        }
        
        customer_id = self.db.add_customer(customer_data)
        if customer_id:
            QMessageBox.information(self, "Success", "Customer added successfully!")
            self.load_customers()
            dialog.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to add customer to database")
    
    def export_customers(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Customers", "customers_export.csv", 
                                                  "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
            
        try:
            customers = self.db.get_all_customers()
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'name', 'phone', 'email', 'address', 'created_date'])
                for cust in customers:
                    writer.writerow(cust)
            
            QMessageBox.information(self, "Success", "Customers exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export customers: {e}")
    
    def generate_sales_report(self):
        start_date = self.start_date.date().toString('yyyy-MM-dd')
        end_date = self.end_date.date().toString('yyyy-MM-dd')
        
        sales = self.db.get_sales_report(start_date, end_date)
        self.sales_report_table.setRowCount(len(sales))
        
        total_sales = 0
        cash_sales = 0
        card_sales = 0
        upi_sales = 0
        
        for row, sale in enumerate(sales):
            self.sales_report_table.setItem(row, 0, QTableWidgetItem(str(sale[0])))
            self.sales_report_table.setItem(row, 1, QTableWidgetItem(sale[1]))
            self.sales_report_table.setItem(row, 2, QTableWidgetItem(sale[2]))
            self.sales_report_table.setItem(row, 3, QTableWidgetItem(sale[3] if sale[3] else "Walk-in"))
            self.sales_report_table.setItem(row, 4, QTableWidgetItem(f"₹{sale[4]:.2f}"))
            self.sales_report_table.setItem(row, 5, QTableWidgetItem(sale[5]))
            
            total_sales += sale[4]
            if sale[5] == "Cash":
                cash_sales += sale[4]
            elif sale[5] == "Card":
                card_sales += sale[4]
            elif sale[5] == "UPI":
                upi_sales += sale[4]
        
        # Update summary
        self.total_sales_label.setText(f"₹{total_sales:.2f}")
        self.cash_sales_label.setText(f"₹{cash_sales:.2f}")
        self.card_sales_label.setText(f"₹{card_sales:.2f}")
        self.upi_sales_label.setText(f"₹{upi_sales:.2f}")
        
        # Count unique customers
        customer_count = len(set(s[3] for s in sales if s[3]))
        self.total_customers_label.setText(str(customer_count))
    
    def show_sale_details(self, index):
        sale_id = int(self.sales_report_table.item(index.row(), 0).text())
        sale_details = self.db.get_sale_details(sale_id)
        
        if not sale_details:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Sale Details - Invoice #{sale_details['header'][1]}")
        dialog.setFixedSize(600, 500)
        
        layout = QVBoxLayout()
        
        # Header info
        header_group = QGroupBox("Invoice Information")
        header_layout = QFormLayout()
        
        header_layout.addRow("Invoice Number:", QLabel(sale_details['header'][1]))
        header_layout.addRow("Date:", QLabel(sale_details['header'][3]))
        header_layout.addRow("Customer:", QLabel(sale_details['header'][8] if sale_details['header'][8] else "Walk-in Customer"))
        header_layout.addRow("Payment Method:", QLabel(sale_details['header'][7]))
        header_layout.addRow("Total Amount:", QLabel(f"₹{sale_details['header'][4]:.2f}"))
        
        header_group.setLayout(header_layout)
        layout.addWidget(header_group)
        
        # Items table
        items_table = QTableWidget()
        items_table.setColumnCount(5)
        items_table.setHorizontalHeaderLabels(["Medicine", "Batch", "Price", "Qty", "Total"])
        items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        items_table.setRowCount(len(sale_details['items']))
        for row, item in enumerate(sale_details['items']):
            items_table.setItem(row, 0, QTableWidgetItem(item[5]))
            items_table.setItem(row, 1, QTableWidgetItem(item[6] if item[6] else ""))
            items_table.setItem(row, 2, QTableWidgetItem(f"₹{item[4]:.2f}"))
            items_table.setItem(row, 3, QTableWidgetItem(str(item[3])))
            items_table.setItem(row, 4, QTableWidgetItem(f"₹{item[3]*item[4]:.2f}"))
        
        layout.addWidget(items_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        print_btn = QPushButton("Print Invoice")
        print_btn.setStyleSheet("background-color: #3a7ca5; color: white;")
        btn_layout.addWidget(print_btn)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background-color: #e76f51; color: white;")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def export_sales_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Sales Report", "sales_report.csv", 
                                                  "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return
            
        try:
            start_date = self.start_date.date().toString('yyyy-MM-dd')
            end_date = self.end_date.date().toString('yyyy-MM-dd')
            sales = self.db.get_sales_report(start_date, end_date)
            
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'invoice_number', 'date', 'customer_name', 'total_amount', 'payment_method'])
                for sale in sales:
                    writer.writerow(sale)
            
            QMessageBox.information(self, "Success", "Sales report exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export sales report: {e}")
    
    def backup_database(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Backup Database", "pharmacy_backup.db", 
                                                  "Database Files (*.db);;All Files (*)")
        if not file_path:
            return
            
        try:
            import shutil
            shutil.copyfile('pharmacy.db', file_path)
            QMessageBox.information(self, "Success", "Database backup created successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create backup: {e}")
    
    def export_reports(self):
        options = ["Sales Report", "Inventory Report", "Customer List"]
        item, ok = QInputDialog.getItem(self, "Export Report", "Select report to export:", options, 0, False)
        
        if ok and item:
            if item == "Sales Report":
                self.export_sales_report()
            elif item == "Inventory Report":
                self.export_medicines()
            elif item == "Customer List":
                self.export_customers()
    
    def save_settings(self):
        # In a real application, you would save these to a config file
        QMessageBox.information(self, "Settings Saved", "System settings have been saved")
    
    def check_alerts(self):
        # Check low stock
        low_stock = self.db.get_low_stock_medicines()
        if low_stock:
            msg = "Low stock alert for the following medicines:\n\n"
            for med in low_stock:
                msg += f"{med[1]} (Current: {med[6]}, Min: {med[10] if med[10] else 5})\n"
            
            QMessageBox.warning(self, "Low Stock Alert", msg)
        
        # Check expired medicines
        expired = self.db.get_expired_medicines()
        if expired:
            msg = "Expired medicines alert:\n\n"
            for med in expired:
                msg += f"{med[1]} (Expired on: {med[7]})\n"
            
            QMessageBox.critical(self, "Expired Medicines Alert", msg)
    
    def show_about(self):
        about_text = """<h2>Mahavir Medical Store Billing System</h2>
        <p>Version 1.0</p>
        <p>Developed by Your Name</p>
        <p>Contact: your.email@example.com</p>
        <p>© 2023 All Rights Reserved</p>"""
        
        QMessageBox.about(self, "About", about_text)

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Show login window
    login_window = LoginWindow(on_login_success=lambda user: MainWindow(user).show())
    login_window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()