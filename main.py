import sys
import sys, os
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
import shutil
import json

def resource_path(relative_path):
    """ Get absolute path to resource (works for dev and for PyInstaller) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


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
            
            # Settings table
            c.execute('''CREATE TABLE settings
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         key TEXT UNIQUE NOT NULL,
                         value TEXT NOT NULL)''')
            
            # Add admin user
            c.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                      ('mahavir', 'mahavir123', 'admin', 'Administrator'))
            
            # Add default settings
            default_settings = [
                ('pharmacy_name', 'Mahavir Medical Store'),
                ('pharmacy_address', 'SHALIMAR SHOPPING CENTER, LALA NIGAM ROAD,COLOBA MARKET, MUMBAI 400005'),
                ('pharmacy_phone', '9821310312, 9821325949'),
                ('pharmacy_email', 'your@gmail.com'),
                ('pharmacy_gst', 'Your GST Number'),
                ('invoice_prefix', 'INV'),
                ('invoice_start', '1001'),
                ('tax_rate', '5.0'),
                ('auto_print', 'False'),
                ('auto_backup', 'False'),
                ('backup_retention', '7'),
                ('smtp_server', 'smtp.gmail.com'),
                ('smtp_port', '587'),
                ('email_username', 'your@gmail.com'),
                ('email_password', ''),
                ('email_ssl', 'True'),
                ('whatsapp_token', ''),
                ('whatsapp_phone_id', ''),
                ('low_stock_alert', 'True'),
                ('expiry_alert', 'True'),
                ('alert_days', '30')
            ]
            
            c.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", default_settings)
            
            conn.commit()
            conn.close()
    
    def _get_connection(self):
        return sqlite3.connect(self.db_file)
    
    # Settings methods
    def get_setting(self, key):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("SELECT value FROM settings WHERE key=?", (key,))
            result = c.fetchone()
            return result[0] if result else None
        finally:
            conn.close()
    
    def update_setting(self, key, value):
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
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
    def generate_invoice_pdf(invoice_data, file_path, settings):
        # Use half of A4 size (width, height)
        page_width, page_height = letter
        page_height = page_height / 2  # Half A4 height
        
        c = canvas.Canvas(file_path, pagesize=(page_width, page_height))
        width, height = (page_width, page_height)
        
        # Set fonts
        c.setFont("Helvetica-Bold", 14)
        
        # Pharmacy header
        c.drawCentredString(width/2, height-30, settings.get('pharmacy_name', 'Mahavir Medical Store'))
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height-45, settings.get('pharmacy_address', ''))
        c.drawCentredString(width/2, height-60, f"Phone: {settings.get('pharmacy_phone', '')} | GST: {settings.get('pharmacy_gst', '')}")
        
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
        
        # Draw line before totals
        c.line(50, y_position-10, width-50, y_position-10)
        
        # Totals
        c.setFont("Helvetica-Bold", 10)
        c.drawString(width-200, y_position-20, "Subtotal:")
        c.drawString(width-150, y_position-20, f"₹{invoice_data['subtotal']:.2f}")
        
        c.drawString(width-200, y_position-35, "Discount:")
        c.drawString(width-150, y_position-35, f"₹{invoice_data['discount']:.2f}")
        
        tax_rate = float(settings.get('tax_rate', 5.0))
        c.drawString(width-200, y_position-50, f"Tax ({tax_rate}%):")
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
            'username': 'your@gmail.com',
            'password': 'your gmail access code',
            'from_email': 'your@gmail.com'
        }
        
        self.whatsapp_settings = {
            'access_token': 'your_whatsapp_token',
            'phone_number_id': 'your_whatsapp_phone_id'
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
        self.setFixedSize(430, 480)
        
        layout = QVBoxLayout()
        
        # Logo or title
        logo = QLabel()
        pixmap = QPixmap(resource_path("assets/logo2.png"))   # <-- put your logo path here
        pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("background: transparent;")
        layout.addWidget(logo)

         # Title text
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
        self.keep_scanning = False
        self.current_invoice_items = []
        self.invoice_counter = int(self.db.get_setting('invoice_start') or 1001)
        self.settings = self.load_settings_from_db()
        self.init_ui()
        self.check_alerts()
        # ===================================================================
        # Auto-backup timer (runs once every 24h)
        self.backup_enabled = False   # controlled by toggle
        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self.run_daily_backup)
        self.backup_timer.start(24 * 60 * 60 * 1000)  # every 24h
        # ==========================================================================

        
        # Setup auto-alert check every hour
        self.alert_timer = QTimer()
        self.alert_timer.timeout.connect(self.check_alerts)
        self.alert_timer.start(3600000)  # 1 hour
        
    def load_settings_from_db(self):
        """Load settings from database"""
        settings = {}
        keys = [
            'pharmacy_name', 'pharmacy_address', 'pharmacy_phone', 'pharmacy_email', 
            'pharmacy_gst', 'invoice_prefix', 'invoice_start', 'tax_rate', 'auto_print',
            'auto_backup', 'backup_retention', 'smtp_server', 'smtp_port', 'email_username',
            'email_password', 'email_ssl', 'whatsapp_token', 'whatsapp_phone_id',
            'low_stock_alert', 'expiry_alert', 'alert_days'
        ]
        
        for key in keys:
            settings[key] = self.db.get_setting(key)
            
        return settings
        
    def init_ui(self):
        # self.setup_settings_tab()
        self.setWindowTitle(f"Mahavir Medical Store Billing System - {self.user[3]}")
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

        self.setup_settings_tab()  
        
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
        self.customer_email_input.setPlaceholderText("Email ")
        customer_form.addRow("Customer Email:", self.customer_email_input)
        
        top_layout.addLayout(customer_form)
        
        # Barcode section
        barcode_layout = QVBoxLayout()
        
        scan_btn = QPushButton("Scan Barcode")
        scan_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        scan_btn.clicked.connect(self.scan_barcode)
        barcode_layout.addWidget(scan_btn)

        stop_btn = QPushButton("Stop Scanning")
        stop_btn.setStyleSheet("background-color: #e63946; color: white; padding: 8px;")
        stop_btn.clicked.connect(self.stop_scanning)
        barcode_layout.addWidget(stop_btn)
        
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
        self.invoice_table.setColumnCount(7)  # Added Actions column
        self.invoice_table.setHorizontalHeaderLabels(["ID", "Medicine", "Batch", "Price", "Qty", "Total", "Actions"])
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.invoice_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Prevent editing
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
        
        tax_rate = float(self.settings.get('tax_rate', 5.0))
        self.tax_label = QLabel(f"₹0.00 ({tax_rate}% GST)")
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
        self.sms_checkbox.setChecked(False)
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

    def stop_scanning(self):
        """Stop continuous barcode scanning"""
        self.keep_scanning = False
        
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
        self.inventory_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Prevent editing
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
        
        self.pharmacy_gst = QLineEdit("27AAAFM9811F1ZD")
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

    def setup_settings_tab(self):
        settings_tab = QWidget()
        layout = QVBoxLayout(settings_tab)
        
        # Create a tab widget for settings categories
        settings_tabs = QTabWidget()
        layout.addWidget(settings_tabs)
        
        # General Settings Tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # Pharmacy Information
        pharmacy_group = QGroupBox("Pharmacy Information")
        pharmacy_layout = QFormLayout()
        
        self.pharmacy_name = QLineEdit(self.settings.get('pharmacy_name', 'Mahavir Medical Store'))
        pharmacy_layout.addRow("Pharmacy Name:", self.pharmacy_name)
        
        self.pharmacy_address = QTextEdit()
        self.pharmacy_address.setPlainText(self.settings.get('pharmacy_address', ''))
        self.pharmacy_address.setMaximumHeight(80)
        pharmacy_layout.addRow("Address:", self.pharmacy_address)
        
        self.pharmacy_phone = QLineEdit(self.settings.get('pharmacy_phone', ''))
        pharmacy_layout.addRow("Phone:", self.pharmacy_phone)
        
        self.pharmacy_email = QLineEdit(self.settings.get('pharmacy_email', ''))
        pharmacy_layout.addRow("Email:", self.pharmacy_email)
        
        self.pharmacy_gst = QLineEdit(self.settings.get('pharmacy_gst', ''))
        pharmacy_layout.addRow("GSTIN:", self.pharmacy_gst)
        
        pharmacy_group.setLayout(pharmacy_layout)
        general_layout.addWidget(pharmacy_group)
        
        # Invoice Settings
        invoice_group = QGroupBox("Invoice Settings")
        invoice_layout = QFormLayout()
        
        self.invoice_prefix = QLineEdit(self.settings.get('invoice_prefix', 'INV'))
        invoice_layout.addRow("Invoice Prefix:", self.invoice_prefix)
        
        self.invoice_start = QSpinBox()
        self.invoice_start.setRange(1, 9999)
        self.invoice_start.setValue(int(self.settings.get('invoice_start', 1001)))
        invoice_layout.addRow("Starting Number:", self.invoice_start)
        
        self.tax_rate = QDoubleSpinBox()
        self.tax_rate.setRange(0, 30)
        self.tax_rate.setValue(float(self.settings.get('tax_rate', 5.0)))
        self.tax_rate.setSuffix("%")
        invoice_layout.addRow("Tax Rate:", self.tax_rate)
        
        self.auto_print = QCheckBox("Auto-print receipts after sale")
        self.auto_print.setChecked(self.settings.get('auto_print', 'False').lower() == 'true')
        invoice_layout.addRow("", self.auto_print)
        
        invoice_group.setLayout(invoice_layout)
        general_layout.addWidget(invoice_group)
        
        # Save general settings button
        save_general_btn = QPushButton("Save General Settings")
        save_general_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        save_general_btn.clicked.connect(self.save_general_settings)
        general_layout.addWidget(save_general_btn)
        
        general_layout.addStretch()
        settings_tabs.addTab(general_tab, "General")
        
        # Backup & Restore Tab
        backup_tab = QWidget()
        backup_layout = QVBoxLayout(backup_tab)
        
        # Auto Backup Settings
        backup_group = QGroupBox("Backup Settings")
        backup_form = QFormLayout()
        
        self.backup_checkbox = QCheckBox("Enable Daily Auto Backup")
        self.backup_checkbox.setChecked(self.settings.get('auto_backup', 'False').lower() == 'true')
        backup_form.addRow("Auto Backup:", self.backup_checkbox)
        
        self.backup_retention = QSpinBox()
        self.backup_retention.setRange(1, 365)
        self.backup_retention.setValue(int(self.settings.get('backup_retention', 7)))
        self.backup_retention.setSuffix(" days")
        backup_form.addRow("Retention Period:", self.backup_retention)
        
        backup_group.setLayout(backup_form)
        backup_layout.addWidget(backup_group)
        
        # Manual Backup Actions
        action_group = QGroupBox("Manual Actions")
        action_layout = QVBoxLayout()
        
        backup_now_btn = QPushButton("Backup Database Now")
        backup_now_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        backup_now_btn.clicked.connect(self.backup_database)
        action_layout.addWidget(backup_now_btn)
        
        restore_btn = QPushButton("Restore Database")
        restore_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 8px;")
        restore_btn.clicked.connect(self.restore_database)
        action_layout.addWidget(restore_btn)
        
        export_all_btn = QPushButton("Export All Data (CSV)")
        export_all_btn.setStyleSheet("background-color: #2a6099; color: white; padding: 8px;")
        export_all_btn.clicked.connect(self.export_all_data)
        action_layout.addWidget(export_all_btn)
        
        import_all_btn = QPushButton("Import Data (CSV)")
        import_all_btn.setStyleSheet("background-color: #2a6099; color: white; padding: 8px;")
        import_all_btn.clicked.connect(self.import_all_data)
        action_layout.addWidget(import_all_btn)
        
        action_group.setLayout(action_layout)
        backup_layout.addWidget(action_group)
        
        # Backup History
        history_group = QGroupBox("Recent Backups")
        history_layout = QVBoxLayout()
        
        self.backup_list = QTextEdit()
        self.backup_list.setReadOnly(True)
        self.backup_list.setMaximumHeight(120)
        history_layout.addWidget(self.backup_list)
        
        open_backup_dir_btn = QPushButton("Open Backup Folder")
        open_backup_dir_btn.setStyleSheet("background-color: #6a7f9f; color: white; padding: 5px;")
        open_backup_dir_btn.clicked.connect(self.open_backup_folder)
        history_layout.addWidget(open_backup_dir_btn)
        
        history_group.setLayout(history_layout)
        backup_layout.addWidget(history_group)
        
        backup_layout.addStretch()
        settings_tabs.addTab(backup_tab, "Backup & Restore")
        
        # Notification Settings Tab
        notify_tab = QWidget()
        notify_layout = QVBoxLayout(notify_tab)
        
        # Email Settings
        email_group = QGroupBox("Email Settings")
        email_form = QFormLayout()
        
        self.smtp_server = QLineEdit(self.settings.get('smtp_server', 'smtp.gmail.com'))
        email_form.addRow("SMTP Server:", self.smtp_server)
        
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(int(self.settings.get('smtp_port', 587)))
        email_form.addRow("SMTP Port:", self.smtp_port)
        
        self.email_username = QLineEdit(self.settings.get('email_username', ''))
        email_form.addRow("Email Username:", self.email_username)
        
        self.email_password = QLineEdit(self.settings.get('email_password', ''))
        self.email_password.setEchoMode(QLineEdit.Password)
        email_form.addRow("Email Password:", self.email_password)
        
        self.email_ssl = QCheckBox("Use SSL/TLS")
        self.email_ssl.setChecked(self.settings.get('email_ssl', 'True').lower() == 'true')
        email_form.addRow("", self.email_ssl)
        
        test_email_btn = QPushButton("Test Email Configuration")
        test_email_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 5px;")
        test_email_btn.clicked.connect(self.test_email_config)
        email_form.addRow("", test_email_btn)
        
        email_group.setLayout(email_form)
        notify_layout.addWidget(email_group)
        
        # WhatsApp Settings
        whatsapp_group = QGroupBox("WhatsApp Settings")
        whatsapp_form = QFormLayout()
        
        self.whatsapp_access_token = QLineEdit(self.settings.get('whatsapp_token', ''))
        self.whatsapp_access_token.setEchoMode(QLineEdit.Password)
        whatsapp_form.addRow("Access Token:", self.whatsapp_access_token)
        
        self.whatsapp_phone_id = QLineEdit(self.settings.get('whatsapp_phone_id', ''))
        whatsapp_form.addRow("Phone Number ID:", self.whatsapp_phone_id)
        
        test_whatsapp_btn = QPushButton("Test WhatsApp Configuration")
        test_whatsapp_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 5px;")
        test_whatsapp_btn.clicked.connect(self.test_whatsapp_config)
        whatsapp_form.addRow("", test_whatsapp_btn)
        
        whatsapp_group.setLayout(whatsapp_form)
        notify_layout.addWidget(whatsapp_group)
        
        # Alert Settings
        alert_group = QGroupBox("Alert Preferences")
        alert_form = QFormLayout()
        
        self.low_stock_alert = QCheckBox("Enable low stock alerts")
        self.low_stock_alert.setChecked(self.settings.get('low_stock_alert', 'True').lower() == 'true')
        alert_form.addRow("Stock Alerts:", self.low_stock_alert)
        
        self.expiry_alert = QCheckBox("Enable expiry alerts")
        self.expiry_alert.setChecked(self.settings.get('expiry_alert', 'True').lower() == 'true')
        alert_form.addRow("Expiry Alerts:", self.expiry_alert)
        
        self.alert_days = QSpinBox()
        self.alert_days.setRange(1, 90)
        self.alert_days.setValue(int(self.settings.get('alert_days', 30)))
        self.alert_days.setSuffix(" days before expiry")
        alert_form.addRow("Expiry Warning:", self.alert_days)
        
        alert_group.setLayout(alert_form)
        notify_layout.addWidget(alert_group)
        
        # Save notification settings button
        save_notify_btn = QPushButton("Save Notification Settings")
        save_notify_btn.setStyleSheet("background-color: #2a9d8f; color: white; padding: 8px;")
        save_notify_btn.clicked.connect(self.save_notification_settings)
        notify_layout.addWidget(save_notify_btn)
        
        notify_layout.addStretch()
        settings_tabs.addTab(notify_tab, "Notifications")
        
        # Developer Information Tab
        developer_tab = QWidget()
        developer_layout = QVBoxLayout(developer_tab)
        
        # Developer Information
        developer_group = QGroupBox("Developer Information")
        developer_form = QFormLayout()
        
        developer_name = QLabel("Arun Adhikari")
        developer_form.addRow("Name:", developer_name)
        
        developer_email = QLabel("arunadhikari0000@gmail.com")
        developer_form.addRow("Email:", developer_email)
        
        developer_phone = QLabel("+91 8291116159")
        developer_form.addRow("Phone:", developer_phone)
        
        developer_website = QLabel("https://arun7303.netlify.app/")
        developer_form.addRow("Website:", developer_website)
        
        developer_version = QLabel("1.8.2")
        developer_form.addRow("Version:", developer_version)
        
        developer_group.setLayout(developer_form)
        developer_layout.addWidget(developer_group)
        
        # About Section
        about_group = QGroupBox("About")
        about_layout = QVBoxLayout()
        
        about_text = QTextEdit()
        about_text.setPlainText("Mahavir Medical Store Billing System\n\n"
                            "A comprehensive pharmacy management solution with inventory tracking, "
                            "billing, customer management, and reporting features.\n\n"
                            "© 2025 All Rights Reserved")
        about_text.setReadOnly(True)
        about_text.setMaximumHeight(120)
        about_layout.addWidget(about_text)
        
        about_group.setLayout(about_layout)
        developer_layout.addWidget(about_group)
        
        developer_layout.addStretch()
        settings_tabs.addTab(developer_tab, "Developer Info")
        
        # System Info Tab
        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)
        
        # System Information
        sysinfo_group = QGroupBox("System Information")
        sysinfo_layout = QFormLayout()
        
        # Database info
        db_size = self.get_database_size()
        sysinfo_layout.addRow("Database Size:", QLabel(db_size))
        
        # Medicine count
        med_count = len(self.db.get_all_medicines())
        sysinfo_layout.addRow("Medicines in Database:", QLabel(str(med_count)))
        
        # Customer count
        cust_count = len(self.db.get_all_customers())
        sysinfo_layout.addRow("Customers in Database:", QLabel(str(cust_count)))
        
        # Sales count
        sales = self.db.get_sales_report()
        sysinfo_layout.addRow("Total Sales Records:", QLabel(str(len(sales))))
        
        # System info
        import platform
        sysinfo_layout.addRow("Python Version:", QLabel(platform.python_version()))
        sysinfo_layout.addRow("Operating System:", QLabel(platform.platform()))
        
        sysinfo_group.setLayout(sysinfo_layout)
        info_layout.addWidget(sysinfo_group)
        
        # Maintenance Actions
        maintenance_group = QGroupBox("Maintenance")
        maintenance_layout = QVBoxLayout()
        
        optimize_btn = QPushButton("Optimize Database")
        optimize_btn.setStyleSheet("background-color: #3a7ca5; color: white; padding: 8px;")
        optimize_btn.clicked.connect(self.optimize_database)
        maintenance_layout.addWidget(optimize_btn)
        
        clear_cache_btn = QPushButton("Clear Temporary Files")
        clear_cache_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 8px;")
        clear_cache_btn.clicked.connect(self.clear_temp_files)
        maintenance_layout.addWidget(clear_cache_btn)
        
        maintenance_group.setLayout(maintenance_layout)
        info_layout.addWidget(maintenance_group)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh System Info")
        refresh_btn.setStyleSheet("background-color: #6a7f9f; color: white; padding: 5px;")
        refresh_btn.clicked.connect(self.refresh_system_info)
        info_layout.addWidget(refresh_btn)
        
        info_layout.addStretch()
        settings_tabs.addTab(info_tab, "System Info")
        
        self.tabs.addTab(settings_tab, "Settings")
        self.update_backup_list()

    def save_general_settings(self):
        """Save general settings to database"""
        try:
            settings_to_save = {
                'pharmacy_name': self.pharmacy_name.text(),
                'pharmacy_address': self.pharmacy_address.toPlainText(),
                'pharmacy_phone': self.pharmacy_phone.text(),
                'pharmacy_email': self.pharmacy_email.text(),
                'pharmacy_gst': self.pharmacy_gst.text(),
                'invoice_prefix': self.invoice_prefix.text(),
                'invoice_start': str(self.invoice_start.value()),
                'tax_rate': str(self.tax_rate.value()),
                'auto_print': str(self.auto_print.isChecked()),
                'auto_backup': str(self.backup_checkbox.isChecked()),
                'backup_retention': str(self.backup_retention.value()),
                'smtp_server': self.smtp_server.text(),
                'smtp_port': str(self.smtp_port.value()),
                'email_username': self.email_username.text(),
                'email_password': self.email_password.text(),
                'email_ssl': str(self.email_ssl.isChecked()),
                'whatsapp_token': self.whatsapp_access_token.text(),
                'whatsapp_phone_id': self.whatsapp_phone_id.text(),
                'low_stock_alert': str(self.low_stock_alert.isChecked()),
                'expiry_alert': str(self.expiry_alert.isChecked()),
                'alert_days': str(self.alert_days.value())
            }
            
            for key, value in settings_to_save.items():
                self.db.update_setting(key, value)
                
            # Update current settings
            self.settings.update(settings_to_save)
            
            # Update tax label in billing tab
            tax_rate = float(self.settings.get('tax_rate', 5.0))
            self.tax_label.setText(f"₹0.00 ({tax_rate}% GST)")
            
            QMessageBox.information(self, "Success", "General settings saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def save_notification_settings(self):
        """Save notification settings to database"""
        self.save_general_settings()  # Reuse the same method

    def update_backup_list(self):
        """Update the list of recent backups"""
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            self.backup_list.setPlainText("No backups found.")
            return
            
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")], reverse=True)
        if backups:
            text = "Recent backups:\n"
            for backup in backups[:5]:  # Show only the 5 most recent
                backup_path = os.path.join(backup_dir, backup)
                size = os.path.getsize(backup_path) / (1024 * 1024)  # Size in MB
                text += f"{backup} ({size:.2f} MB)\n"
            self.backup_list.setPlainText(text)
        else:
            self.backup_list.setPlainText("No backups found.")

    def open_backup_folder(self):
        """Open the backup folder in the system file explorer"""
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        try:
            if os.name == 'nt':  # Windows
                os.startfile(backup_dir)
            elif os.name == 'mac':  # macOS
                os.system(f'open "{backup_dir}"')
            else:  # Linux
                os.system(f'xdg-open "{backup_dir}"')
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open backup folder: {e}")

    def restore_database(self):
        """Restore database from backup"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Restore Database", "", 
                                                "Database Files (*.db);;All Files (*)")
        if not file_path:
            return
            
        reply = QMessageBox.question(self, "Confirm Restore", 
                                "This will replace your current database with the backup. Continue?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # Close current database connection
                self.db._get_connection().close()
                
                # Replace database file
                import shutil
                shutil.copyfile(file_path, 'pharmacy.db')
                
                # Reinitialize database connection
                self.db = PharmacyDatabase()
                
                QMessageBox.information(self, "Success", "Database restored successfully! Please restart the application.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to restore database: {e}")

    def export_all_data(self):
        """Export all data to CSV files"""
        export_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not export_dir:
            return
            
        try:
            # Export medicines
            medicines = self.db.get_all_medicines()
            with open(os.path.join(export_dir, "medicines_export.csv"), 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'name', 'barcode', 'batch_number', 'price', 'mrp', 
                                'quantity', 'expiry_date', 'manufacturer', 'category', 'min_stock_level'])
                for med in medicines:
                    writer.writerow(med)
            
            # Export customers
            customers = self.db.get_all_customers()
            with open(os.path.join(export_dir, "customers_export.csv"), 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'name', 'phone', 'email', 'address', 'created_date'])
                for cust in customers:
                    writer.writerow(cust)
            
            # Export sales
            sales = self.db.get_sales_report()
            with open(os.path.join(export_dir, "sales_export.csv"), 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'invoice_number', 'date', 'customer_name', 'total_amount', 'payment_method'])
                for sale in sales:
                    writer.writerow(sale)
            
            QMessageBox.information(self, "Success", "All data exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export data: {e}")

    def import_all_data(self):
        """Import data from CSV files"""
        import_dir = QFileDialog.getExistingDirectory(self, "Select Import Directory")
        if not import_dir:
            return
            
        reply = QMessageBox.question(self, "Confirm Import", 
                                "This will import data from CSV files. Continue?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # Import medicines
                med_file = os.path.join(import_dir, "medicines_export.csv")
                if os.path.exists(med_file):
                    with open(med_file, 'r') as f:
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
                
                # Import customers
                cust_file = os.path.join(import_dir, "customers_export.csv")
                if os.path.exists(cust_file):
                    with open(cust_file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            customer_data = {
                                'name': row.get('name', ''),
                                'phone': row.get('phone', ''),
                                'email': row.get('email', ''),
                                'address': row.get('address', '')
                            }
                            self.db.add_customer(customer_data)
                
                self.load_inventory()
                self.load_customers()
                QMessageBox.information(self, "Success", "Data imported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import data: {e}")

    def test_email_config(self):
        """Test email configuration"""
        try:
            server = smtplib.SMTP(self.smtp_server.text(), self.smtp_port.value())
            server.starttls()
            server.login(self.email_username.text(), self.email_password.text())
            server.quit()
            QMessageBox.information(self, "Success", "Email configuration test successful!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Email test failed: {e}")

    def test_whatsapp_config(self):
        """Test WhatsApp configuration"""
        if not self.whatsapp_access_token.text() or not self.whatsapp_phone_id.text():
            QMessageBox.warning(self, "Error", "Please enter both Access Token and Phone Number ID")
            return
            
        try:
            # Simple test to verify credentials
            token = self.whatsapp_access_token.text()
            phone_number_id = self.whatsapp_phone_id.text()
            
            url = f"https://graph.facebook.com/v19.0/{phone_number_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "WhatsApp configuration test successful!")
            else:
                QMessageBox.critical(self, "Error", f"WhatsApp test failed: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"WhatsApp test failed: {e}")

    def get_database_size(self):
        """Get database file size"""
        try:
            size = os.path.getsize('pharmacy.db') / (1024 * 1024)  # Size in MB
            return f"{size:.2f} MB"
        except:
            return "Unknown"

    def optimize_database(self):
        """Optimize database performance"""
        try:
            conn = self.db._get_connection()
            c = conn.cursor()
            c.execute("VACUUM")
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Success", "Database optimized successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to optimize database: {e}")

    def clear_temp_files(self):
        """Clear temporary files"""
        try:
            temp_dirs = ["invoices", "temp"]
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    for file in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, file)
                        try:
                            if os.path.isfile(file_path):
                                os.unlink(file_path)
                        except Exception as e:
                            print(f"Error deleting {file_path}: {e}")
            
            QMessageBox.information(self, "Success", "Temporary files cleared successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear temporary files: {e}")

    def refresh_system_info(self):
        """Refresh system information"""
        # Update database size
        db_size = self.get_database_size()
        # This would need to be implemented with direct access to the labels
        # For simplicity, we'll just show a message
        QMessageBox.information(self, "Refreshed", "System information refreshed!")

    def run_daily_backup(self):
        """Triggered automatically every 24 hours by QTimer"""
        if self.backup_enabled:   # run only if toggle is ON
            self.auto_backup_database()
            self.statusBar().showMessage(
                f"Auto-backup completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                5000
            )

        
    def scan_barcode(self):
        """Continuously scan and add items until user stops"""
        self.keep_scanning = True
        while self.keep_scanning:
            barcode = self.barcode_scanner.start_scan()
            if barcode:
                self.barcode_input.setText(barcode)
                self.add_item_to_invoice()
            else:
                break  # if no barcode, stop loop
    
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
            
            # Add delete button for each item
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("background-color: #e76f51; color: white; padding: 2px;")
            delete_btn.clicked.connect(lambda _, r=row: self.delete_invoice_item(r))
            self.invoice_table.setCellWidget(row, 6, delete_btn)
        
            subtotal += total
        
        # Calculate totals
        discount_percent = self.discount_input.value()
        discount_amount = subtotal * (discount_percent / 100)
        tax_rate = float(self.settings.get('tax_rate', 5.0))
        tax_amount = (subtotal - discount_amount) * (tax_rate / 100)
        total_amount = subtotal - discount_amount + tax_amount
        
        self.subtotal_label.setText(f"₹{subtotal:.2f}")
        self.tax_label.setText(f"₹{tax_amount:.2f} ({tax_rate}% GST)")
        self.total_label.setText(f"₹{total_amount:.2f}")

    def delete_invoice_item(self, row):
        """Remove an item from the invoice"""
        if 0 <= row < len(self.current_invoice_items):
            self.current_invoice_items.pop(row)
            self.update_invoice_table()


    
    def clear_invoice(self):
        self.current_invoice_items = []
        self.invoice_table.setRowCount(0)
        self.subtotal_label.setText("₹0.00")
        tax_rate = float(self.settings.get('tax_rate', 5.0))
        self.tax_label.setText(f"₹0.00 ({tax_rate}% GST)")
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
        tax_rate = float(self.settings.get('tax_rate', 5.0))
        tax_amount = (subtotal - discount_amount) * (tax_rate / 100)
        total_amount = subtotal - discount_amount + tax_amount
        
        # Generate invoice number
        invoice_prefix = self.settings.get('invoice_prefix', 'INV')
        invoice_number = f"{invoice_prefix}-{self.invoice_counter:04d}"
        self.invoice_counter += 1
        
        # Update invoice start in database
        self.db.update_setting('invoice_start', str(self.invoice_counter))
        
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
        PDFGenerator.generate_invoice_pdf(invoice_data, pdf_path, self.settings)
        
        
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
        """Open the print dialog for the receipt"""
        try:
            # For Windows
            if os.name == 'nt':
                os.startfile(pdf_path, "print")
            # For macOS
            elif os.name == 'posix':
                os.system(f"lpr {pdf_path}")
            # For Linux
            else:
                os.system(f"lp {pdf_path}")
        except Exception as e:
            QMessageBox.warning(self, "Print Error", f"Could not print receipt: {str(e)}")
    
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
    
    def auto_backup_database(self):
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # File name like pharmacy_2025-08-21.db
        backup_name = f"pharmacy_{datetime.now().strftime('%Y-%m-%d')}.db"
        backup_path = os.path.join(backup_dir, backup_name)

        # Copy database
        try:
            shutil.copy2("pharmacy.db", backup_path)
            print(f"✅ Backup created: {backup_path}")
        except Exception as e:
            print(f"⚠️ Backup failed: {e}")
            return

        # Keep only last 7 backups
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")])
        if len(backups) > 7:
            for old_backup in backups[:-7]:
                os.remove(os.path.join(backup_dir, old_backup))
                print(f"🗑️ Removed old backup: {old_backup}")

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