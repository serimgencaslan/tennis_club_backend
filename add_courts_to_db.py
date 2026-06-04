import sqlite3

conn = sqlite3.connect('sqlite:////var/data/tennis.db') # Veritabanı dosya adınız farklıysa güncelleyin
cursor = conn.cursor()

courts = [('Kort 1', 'active'), ('Kort 2', 'active'), ('Kort 3', 'active')]
cursor.executemany("INSERT INTO courts (name, status) VALUES (?, ?)", courts)

conn.commit()
conn.close()
print("Kortlar başarıyla eklendi!")