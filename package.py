import PyInstaller.__main__

PyInstaller.__main__.run([
    'pharmacy_system.py',
    '--onefile',
    '--windowed',
    '--name=PharmacyBillingSystem',
    '--icon=pharmacy.ico',  # Optional: add an icon file
    '--add-data=pharmacy.db;.',  # Include the database file
    '--add-data=invoices;invoices'  # Include invoices directory
])