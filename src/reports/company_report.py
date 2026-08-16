def get_company_report(db,company_id):
    company=db.connection.execute('SELECT * FROM companies WHERE id=?',(company_id,)).fetchone()
    evidence=db.connection.execute('SELECT * FROM competitor_evidence WHERE company_id=? ORDER BY last_verified DESC',(company_id,)).fetchall()
    signals=db.connection.execute('SELECT * FROM signals WHERE company_id=? ORDER BY detected_at DESC',(company_id,)).fetchall()
    return {'company':dict(company) if company else None,'evidence':[dict(x) for x in evidence],'signals':[dict(x) for x in signals]}

