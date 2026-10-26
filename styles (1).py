"""
Central stylesheet for the app — one CSS string, injected once from app.py.
"""

APP_CSS = """

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"]{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.main{
    background-color:#F4F6F9;
}

/* ---------- Hero header ---------- */
.hero{
    background: linear-gradient(120deg, #0F2A4A 0%, #1B4F72 55%, #21618C 100%);
    padding: 40px 32px;
    border-radius: 18px;
    text-align: left;
    margin-bottom: 28px;
    box-shadow: 0 8px 24px rgba(15, 42, 74, 0.25);
    border: 1px solid rgba(255,255,255,0.06);
}

.hero .eyebrow{
    color: #9CC3E5;
    font-size: 12.5px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin: 0 0 8px 0;
}

.hero h1{
    color: #FFFFFF;
    font-size: 34px;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
}

.hero p{
    color: #C9DCEE;
    font-size: 15px;
    margin-top: 10px;
    max-width: 620px;
    line-height: 1.5;
}

/* ---------- Section headings ---------- */
.section-heading{
    font-size: 20px;
    font-weight: 700;
    color: #1B2631;
    margin: 6px 0 14px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #E5E9EF;
}

/* ---------- Cards ---------- */
.card{
    background:#FFFFFF;
    padding:22px;
    border-radius:14px;
    border: 1px solid #EAEDF1;
    box-shadow:0px 2px 8px rgba(16, 24, 40, 0.05);
    margin-bottom: 16px;
}

.metric{
    background:#FFFFFF;
    padding:18px 12px;
    border-radius:12px;
    text-align:center;
    border: 1px solid #EAEDF1;
    box-shadow:0px 2px 6px rgba(16, 24, 40, 0.04);
}

.metric h2{
    margin: 0 0 4px 0;
    color: #1B4F72;
    font-size: 26px;
    font-weight: 800;
}

/* ---------- Badges ---------- */
.badge{
    display:inline-block;
    padding: 9px 22px;
    border-radius: 999px;
    color: white;
    font-weight: 700;
    font-size: 18px;
    letter-spacing: 0.2px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.12);
}

/* ---------- Warning card ---------- */
.warning-card{
    background:#FEF9F0;
    border-left: 5px solid #D68910;
    padding: 20px;
    border-radius: 10px;
    border-top: 1px solid #F6E5C6;
    border-right: 1px solid #F6E5C6;
    border-bottom: 1px solid #F6E5C6;
}

.warning-card h4{
    margin-top: 0;
    color: #9C640C;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"]{
    background-color: #0F2A4A;
}

section[data-testid="stSidebar"] *{
    color: #F0F4F8 !important;
}

section[data-testid="stSidebar"] .stCaption, 
section[data-testid="stSidebar"] small{
    color: #B7C6D9 !important;
}

/* ---------- Buttons ---------- */
.stDownloadButton button, .stButton button{
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid #1B4F72;
}

/* ---------- Footer ---------- */
.footer{
    text-align:center;
    color:#7B8794;
    margin-top:40px;
    padding-top: 20px;
    border-top: 1px solid #E5E9EF;
    font-size: 13.5px;
}

.footer h4{
    color:#1B2631;
    margin-bottom: 6px;
}

/* ---------- Overview stat strip ---------- */
.stat-card{
    background:#FFFFFF;
    padding:16px 14px;
    border-radius:12px;
    border: 1px solid #EAEDF1;
    box-shadow:0px 2px 6px rgba(16, 24, 40, 0.04);
    text-align:center;
}

.stat-card .stat-label{
    color:#7B8794;
    font-size:12px;
    font-weight:600;
    text-transform:uppercase;
    letter-spacing:0.5px;
    margin-bottom:4px;
}

.stat-card .stat-value{
    color:#1B2631;
    font-size:20px;
    font-weight:800;
}

"""
