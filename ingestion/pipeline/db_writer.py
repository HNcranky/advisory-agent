                       

import psycopg2
import json

def save_to_staging(doc):

    conn = psycopg2.connect(
        host="localhost",
        database="admission",
        user="postgres",
        password="password"
    )

    cur = conn.cursor()

    cur.execute("""
    INSERT INTO raw_admission_documents
    (source_url, university, year, data_json)
    VALUES (%s,%s,%s,%s)
    """, (
        doc.source_url,
        doc.university,
        doc.year,
        json.dumps(doc.model_dump())
    ))

    conn.commit()
    cur.close()
    conn.close()